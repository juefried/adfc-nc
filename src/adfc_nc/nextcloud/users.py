"""Benutzerabfragen über die OCS-Provisioning-API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from zoneinfo import ZoneInfo

from adfc_nc.config import Settings
from adfc_nc.inventory import InventoryRecord, InventoryUser, open_inventory
from adfc_nc.nextcloud.client import NextcloudClient
from adfc_nc.nextcloud.errors import UnexpectedResponseError

_BERLIN = ZoneInfo("Europe/Berlin")
_USERS_PATH = "/ocs/v2.php/cloud/users/details"
_GROUPS_PATH = "/ocs/v2.php/cloud/groups/details"
_EPOCH_MILLISECONDS_THRESHOLD = 10_000_000_000


class AgeBasis(StrEnum):
    """Herkunft des berechneten Benutzeralters."""

    EXACT = "exact"
    FIRST_SEEN = "first_seen"
    FIRST_LOGIN = "first_login"
    LAST_LOGIN = "last_login"
    PRE_NC31 = "pre_nc31"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class User:
    """Ein Benutzer mit den für die Administration relevanten Feldern."""

    id: str
    display_name: str
    email: str | None
    enabled: bool
    last_login: datetime | None
    group_ids: tuple[str, ...]
    group_names: tuple[str, ...]
    first_login: datetime | None = None
    first_login_pre_nc31: bool = False
    created_at: datetime | None = None
    first_seen_at: datetime | None = None
    first_seen_source: str | None = None
    age_days: int | None = None
    age_basis: AgeBasis = AgeBasis.UNKNOWN
    age_is_lower_bound: bool = False
    age_bound_at: datetime | None = None
    inactive_days: int | None = None
    never_logged_in: bool = False
    is_resource: bool = False


def load_users(
    settings: Settings,
    *,
    search: str = "",
    track_inventory: bool = False,
    now: datetime | None = None,
) -> list[User]:
    """Lädt alle Benutzer samt Gruppen, Login-Zeiten und optionalem Inventar."""
    moment = now or datetime.now(tz=UTC)
    with NextcloudClient(settings) as client:
        group_names = fetch_group_names(client)
        details = fetch_user_details(client, search=search)

    base_users = [
        to_user(
            item,
            group_names,
            now=moment,
            resource_user_prefix=settings.resource_user_prefix,
        )
        for item in details
    ]
    if not track_inventory:
        return base_users

    with open_inventory(settings.state_dir / "inventory.sqlite3") as inventory:
        inventory.sync(
            [
                InventoryUser(
                    user_id=user.id,
                    display_name=user.display_name,
                    email=user.email,
                    enabled=user.enabled,
                    first_login_at=user.first_login,
                    last_login_at=user.last_login,
                )
                for user in base_users
            ],
            now=moment,
        )
        records = inventory.get_many([user.id for user in base_users])

    return [
        to_user(
            item,
            group_names,
            record=records.get(str(item.get("id"))),
            now=moment,
            resource_user_prefix=settings.resource_user_prefix,
        )
        for item in details
    ]


def fetch_user_details(
    client: NextcloudClient,
    *,
    search: str = "",
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Lädt die Benutzerdetails über den NC-34-Endpunkt `/cloud/users/details`."""
    params: dict[str, str] = {"search": search} if search else {}
    return list(
        client.iter_paged_mapping(
            _USERS_PATH,
            "users",
            limit=limit,
            params=params or None,
        )
    )


def fetch_group_names(client: NextcloudClient, *, limit: int = 500) -> dict[str, str]:
    """Lädt die Zuordnung von Gruppenkennung zu Anzeigename."""
    names: dict[str, str] = {}
    for item in client.iter_paged_list(_GROUPS_PATH, "groups", limit=limit):
        group_id = item.get("id")
        if not isinstance(group_id, str) or not group_id:
            raise UnexpectedResponseError("Gruppe ohne gültige Kennung erhalten.")
        display_name = item.get("displayname") or group_id
        names[group_id] = str(display_name)
    return names


def to_user(
    details: dict[str, Any],
    group_names: dict[str, str],
    *,
    record: InventoryRecord | None = None,
    now: datetime | None = None,
    resource_user_prefix: str = "OC",
) -> User:
    """Wandelt einen OCS-Benutzereintrag in ein `User`-Objekt um."""
    moment = now or datetime.now(tz=UTC)
    user_id = details.get("id")
    if not isinstance(user_id, str) or not user_id:
        raise UnexpectedResponseError("Benutzer ohne gültige Kennung erhalten.")

    display_name = details.get("displayname") or details.get("display-name") or user_id
    email = details.get("email")
    group_ids = _extract_group_ids(details.get("groups"))
    first_login, first_login_pre_nc31 = parse_first_login(details)
    last_login = parse_last_login(details)
    created_at = record.created_at if record else None
    first_seen_at = record.first_seen_at if record else None
    first_seen_source = record.first_seen_source if record else None
    first_seen_bound = (
        record.first_seen_at
        if record is not None and record.first_seen_source != "baseline"
        else None
    )
    age_days, age_basis, age_is_lower_bound, age_bound_at = calculate_age(
        created_at=created_at,
        first_seen_at=first_seen_bound,
        first_login=first_login,
        last_login=last_login,
        pre_nc31=first_login_pre_nc31,
        now=moment,
    )

    return User(
        id=user_id,
        display_name=str(display_name),
        email=str(email) if email else None,
        enabled=_as_bool(details.get("enabled", True)),
        last_login=last_login,
        group_ids=group_ids,
        group_names=tuple(group_names.get(group_id, group_id) for group_id in group_ids),
        first_login=first_login,
        first_login_pre_nc31=first_login_pre_nc31,
        created_at=created_at,
        first_seen_at=first_seen_at,
        first_seen_source=first_seen_source,
        age_days=age_days,
        age_basis=age_basis,
        age_is_lower_bound=age_is_lower_bound,
        age_bound_at=age_bound_at,
        inactive_days=_days_since(last_login, moment) if last_login else None,
        never_logged_in=last_login is None and first_login is None and not first_login_pre_nc31,
        is_resource=bool(resource_user_prefix) and user_id.startswith(resource_user_prefix),
    )


def parse_first_login(details: dict[str, Any]) -> tuple[datetime | None, bool]:
    """Liest den Erstlogin; `-1` markiert ein Konto von vor Nextcloud 31."""
    raw = _parse_int(details.get("firstLoginTimestamp"))
    if raw is None:
        raw = _parse_int(details.get("firstLogin"))
    if raw is None or raw == 0:
        return None, False
    if raw < 0:
        return None, True
    if raw >= _EPOCH_MILLISECONDS_THRESHOLD:
        raw //= 1000
    return datetime.fromtimestamp(raw, tz=_BERLIN), False


def parse_last_login(details: dict[str, Any]) -> datetime | None:
    """Liest den letzten Login aus Sekunden- oder Millisekundenwerten."""
    epoch = _parse_epoch(details.get("lastLoginTimestamp"))
    if epoch is None:
        epoch = _parse_epoch(details.get("lastLogin"))
    if epoch is None:
        return None
    if epoch >= _EPOCH_MILLISECONDS_THRESHOLD:
        epoch //= 1000
    return datetime.fromtimestamp(epoch, tz=_BERLIN)


def calculate_age(
    *,
    created_at: datetime | None,
    first_seen_at: datetime | None,
    first_login: datetime | None,
    last_login: datetime | None,
    pre_nc31: bool,
    now: datetime,
) -> tuple[int | None, AgeBasis, bool, datetime | None]:
    """Berechnet Alter und Herkunft aus exakten oder ableitbaren Zeitpunkten."""
    if created_at is not None:
        return _days_since(created_at, now), AgeBasis.EXACT, False, created_at

    if pre_nc31:
        return None, AgeBasis.PRE_NC31, True, None

    login_candidates: list[tuple[int, AgeBasis, datetime]] = []
    for value, basis in ((first_login, AgeBasis.FIRST_LOGIN), (last_login, AgeBasis.LAST_LOGIN)):
        if value is not None:
            login_candidates.append((_days_since(value, now), basis, value))
    if login_candidates:
        age, basis, bound = max(login_candidates, key=lambda candidate: candidate[0])
        return age, basis, True, bound

    if first_seen_at is not None:
        return _days_since(first_seen_at, now), AgeBasis.FIRST_SEEN, True, first_seen_at
    return None, AgeBasis.UNKNOWN, False, None


def _days_since(value: datetime, now: datetime) -> int:
    return max(0, (now - value).days)


def _parse_epoch(value: Any) -> int | None:
    epoch = _parse_int(value)
    return epoch if epoch is not None and epoch > 0 else None


def _parse_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str) and value.strip().lstrip("-").isdigit():
        return int(value.strip())
    return None


def _extract_group_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(group_id) for group_id in value if group_id)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in {"", "0", "false", "no"}
    return bool(value)
