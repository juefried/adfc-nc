from __future__ import annotations

import httpx
import pytest
import respx

from adfc_nc.config import Settings
from adfc_nc.nextcloud.client import NextcloudClient
from adfc_nc.nextcloud.errors import AuthenticationError, OCSResponseError, RateLimitError

BASE_URL = "https://by.adfc-clouds.de"
USERS_PATH = "/ocs/v2.php/cloud/users/details"
USERS_URL = f"{BASE_URL}{USERS_PATH}"


def _ok_payload(data: object) -> dict[str, object]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": data}}


@respx.mock
def test_get_data_returns_ocs_payload(settings: Settings) -> None:
    route = respx.get(USERS_URL).mock(
        return_value=httpx.Response(200, json=_ok_payload({"users": {"a": {"id": "a"}}}))
    )

    with NextcloudClient(settings) as client:
        data = client.get_data(USERS_PATH, {"limit": 1})

    assert data == {"users": {"a": {"id": "a"}}}
    assert route.called
    request = route.calls[0].request
    assert request.headers["OCS-APIRequest"] == "true"
    assert request.headers["Accept"] == "application/json"
    assert request.url.params["format"] == "json"
    assert request.url.params["limit"] == "1"


@respx.mock
def test_get_data_rejects_bad_credentials(settings: Settings) -> None:
    respx.get(USERS_URL).mock(return_value=httpx.Response(401))

    with NextcloudClient(settings) as client, pytest.raises(AuthenticationError):
        client.get_data(USERS_PATH)


@respx.mock
def test_get_data_rejects_ocs_error(settings: Settings) -> None:
    payload = {
        "ocs": {
            "meta": {"status": "failure", "statuscode": 400, "message": "kaputt"},
            "data": {},
        }
    }
    respx.get(USERS_URL).mock(return_value=httpx.Response(200, json=payload))

    with NextcloudClient(settings) as client, pytest.raises(OCSResponseError, match="kaputt"):
        client.get_data(USERS_PATH)


@respx.mock
def test_get_data_retries_after_rate_limit(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    route = respx.get(USERS_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=_ok_payload({})),
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr("adfc_nc.nextcloud.client.time.sleep", sleeps.append)

    with NextcloudClient(settings) as client:
        data = client.get_data(USERS_PATH)

    assert data == {}
    assert sleeps == [0.0]
    assert route.call_count == 2


@respx.mock
def test_get_data_fails_when_rate_limit_persists(settings: Settings) -> None:
    route = respx.get(USERS_URL).mock(
        return_value=httpx.Response(429, headers={"Retry-After": "0"})
    )

    with NextcloudClient(settings) as client, pytest.raises(RateLimitError):
        client.get_data(USERS_PATH)

    assert route.call_count == 3
