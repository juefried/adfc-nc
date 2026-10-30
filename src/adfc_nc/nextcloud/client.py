"""HTTP-Client für die Nextcloud-OCS-API."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import Any

import httpx

from adfc_nc.config import Settings
from adfc_nc.nextcloud.errors import (
    AuthenticationError,
    NextcloudError,
    OCSResponseError,
    RateLimitError,
    UnexpectedResponseError,
)

_DEFAULT_LIMIT = 500
_MAX_PAGES = 10_000
_MAX_RATE_LIMIT_ATTEMPTS = 3
_DEFAULT_RETRY_AFTER = 60.0


class NextcloudClient:
    """Kapselt Authentifizierung, Fehlerabbildung und Paging der OCS-API."""

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.base_url.rstrip("/"),
            auth=(settings.admin_user, settings.admin_password),
            headers={
                "OCS-APIRequest": "true",
                "Accept": "application/json",
            },
            timeout=settings.timeout_seconds,
            verify=settings.verify_tls,
            transport=transport,
            follow_redirects=True,
        )

    def __enter__(self) -> NextcloudClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Schließt den HTTP-Client."""
        self._client.close()

    def get_data(self, path: str, params: Mapping[str, str | int] | None = None) -> Any:
        """Führt einen GET-Request aus und liefert den Inhalt von `ocs.data`."""
        query = dict(params or {})
        query.setdefault("format", "json")
        response = self._get(path, query)
        if response.status_code in (401, 403):
            raise AuthenticationError("Die Nextcloud-Instanz hat die Zugangsdaten abgelehnt.")
        if response.status_code >= 400:
            raise NextcloudError(f"HTTP {response.status_code} bei {path}.")
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise UnexpectedResponseError(
                f"Die Antwort von {path} ist kein gültiges JSON."
            ) from exc
        return self._extract_ocs_data(payload, path)

    def iter_paged_mapping(
        self,
        path: str,
        key: str,
        *,
        limit: int = _DEFAULT_LIMIT,
        params: Mapping[str, str | int] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Liefert die Einträge einer paginierten OCS-Antwort als Objektliste."""
        base_params = dict(params or {})
        seen: set[str] = set()
        offset = 0

        for _ in range(_MAX_PAGES):
            data = self.get_data(path, {**base_params, "limit": limit, "offset": offset})
            if not isinstance(data, dict):
                raise UnexpectedResponseError(f"Unerwartete OCS-Nutzlast von {path}.")
            batch = data.get(key)
            if not isinstance(batch, dict):
                raise UnexpectedResponseError(f"Unerwarteter OCS-Schlüssel '{key}' von {path}.")
            if not batch:
                return

            new_ids = [item_id for item_id in batch if str(item_id) not in seen]
            if not new_ids:
                return

            for item_id in new_ids:
                seen.add(str(item_id))
                item = batch[item_id]
                if not isinstance(item, dict):
                    raise UnexpectedResponseError(f"Unerwarteter Eintrag in '{key}' von {path}.")
                yield item

            if len(batch) < limit:
                return
            offset += limit

        raise NextcloudError(f"Paging für {path} hat das Sicherheitslimit erreicht.")

    def iter_paged_list(
        self,
        path: str,
        key: str,
        *,
        limit: int = _DEFAULT_LIMIT,
        params: Mapping[str, str | int] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Liefert die Einträge einer paginierten OCS-Liste."""
        base_params = dict(params or {})
        seen: set[str] = set()
        offset = 0

        for _ in range(_MAX_PAGES):
            data = self.get_data(path, {**base_params, "limit": limit, "offset": offset})
            if not isinstance(data, dict):
                raise UnexpectedResponseError(f"Unerwartete OCS-Nutzlast von {path}.")
            batch = data.get(key)
            if not isinstance(batch, list):
                raise UnexpectedResponseError(f"Unerwarteter OCS-Schlüssel '{key}' von {path}.")
            if not batch:
                return

            new_count = 0
            for item in batch:
                if not isinstance(item, dict):
                    raise UnexpectedResponseError(f"Unerwarteter Eintrag in '{key}' von {path}.")
                signature = str(item.get("id", "")) or json.dumps(
                    item, sort_keys=True, ensure_ascii=False
                )
                if signature in seen:
                    continue
                seen.add(signature)
                new_count += 1
                yield item

            if new_count == 0 or len(batch) < limit:
                return
            offset += limit

        raise NextcloudError(f"Paging für {path} hat das Sicherheitslimit erreicht.")

    def _get(self, path: str, params: Mapping[str, str | int]) -> httpx.Response:
        for attempt in range(_MAX_RATE_LIMIT_ATTEMPTS):
            try:
                response = self._client.get(path, params=params)
            except httpx.HTTPError as exc:
                raise NextcloudError(f"Netzwerkfehler bei {path}: {type(exc).__name__}.") from exc
            if response.status_code != 429:
                return response
            if attempt + 1 >= _MAX_RATE_LIMIT_ATTEMPTS:
                break
            time.sleep(self._retry_after_seconds(response))
        raise RateLimitError(
            "Die Nextcloud-Instanz hat das Rate Limit nicht rechtzeitig aufgehoben."
        )

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float:
        raw = response.headers.get("Retry-After")
        if raw is None:
            return _DEFAULT_RETRY_AFTER
        try:
            return max(0.0, float(raw))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                return _DEFAULT_RETRY_AFTER
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return max(0.0, (parsed - datetime.now(tz=UTC)).total_seconds())

    @staticmethod
    def _extract_ocs_data(payload: Any, path: str) -> Any:
        if not isinstance(payload, dict):
            raise UnexpectedResponseError(f"Unerwartete Antwortstruktur von {path}.")
        ocs = payload.get("ocs")
        if not isinstance(ocs, dict):
            raise UnexpectedResponseError(f"Antwort ohne OCS-Block von {path}.")
        meta = ocs.get("meta")
        if not isinstance(meta, dict):
            raise UnexpectedResponseError(f"Antwort ohne OCS-Metadaten von {path}.")

        status = str(meta.get("status", "")).lower()
        statuscode = meta.get("statuscode")
        if status:
            if status != "ok":
                message = meta.get("message") or "unbekannter OCS-Fehler"
                raise OCSResponseError(f"{message} ({path})")
        elif statuscode not in (100, 200, "100", "200", None):
            message = meta.get("message") or "unbekannter OCS-Fehler"
            raise OCSResponseError(f"{message} ({path})")

        return ocs.get("data", {})
