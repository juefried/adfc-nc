from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import respx

from adfc_nc.config import Settings
from adfc_nc.inventory import InventoryRecord, InventoryStore
from adfc_nc.nextcloud.client import NextcloudClient
from adfc_nc.nextcloud.users import (
    AgeBasis,
    fetch_group_names,
    fetch_user_details,
    load_users,
    parse_first_login,
    parse_last_login,
    to_user,
)

BASE_URL = "https://by.adfc-clouds.de"
USERS_URL = f"{BASE_URL}/ocs/v2.php/cloud/users/details"
GROUPS_URL = f"{BASE_URL}/ocs/v2.php/cloud/groups/details"
BERLIN = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 29, 12, 0, tzinfo=BERLIN)


def _ok_payload(data: object) -> dict[str, object]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": data}}


def test_parse_last_login_prefers_seconds() -> None:
    details = {"lastLoginTimestamp": 1_700_000_000, "lastLogin": 1_600_000_000_000}

    result = parse_last_login(details)

    assert result == datetime.fromtimestamp(1_700_000_000, tz=BERLIN)


def test_parse_last_login_normalizes_milliseconds() -> None:
    details = {"lastLogin": 1_700_000_000_000}

    result = parse_last_login(details)

    assert result == datetime.fromtimestamp(1_700_000_000, tz=BERLIN)


def test_parse_last_login_returns_none_for_zero() -> None:
    assert parse_last_login({"lastLoginTimestamp": 0, "lastLogin": 0}) is None


def test_parse_first_login_positive() -> None:
    value, pre_nc31 = parse_first_login({"firstLoginTimestamp": 1_700_000_000})

    assert value == datetime.fromtimestamp(1_700_000_000, tz=BERLIN)
    assert pre_nc31 is False


def test_parse_first_login_pre_nc31() -> None:
    value, pre_nc31 = parse_first_login({"firstLoginTimestamp": -1})

    assert value is None
    assert pre_nc31 is True


def test_parse_first_login_zero() -> None:
    assert parse_first_login({"firstLoginTimestamp": 0}) == (None, False)


def test_to_user_extracts_fields_and_group_names() -> None:
    details = {
        "id": "jdoe",
        "displayname": "Jane Doe",
        "email": "jane@example.org",
        "enabled": False,
        "firstLoginTimestamp": 1_600_000_000,
        "lastLoginTimestamp": 1_700_000_000,
        "groups": ["admins"],
    }

    user = to_user(details, {"admins": "Administratoren"}, now=NOW)

    assert user.id == "jdoe"
    assert user.display_name == "Jane Doe"
    assert user.email == "jane@example.org"
    assert user.enabled is False
    assert user.group_ids == ("admins",)
    assert user.group_names == ("Administratoren",)
    assert user.last_login == datetime.fromtimestamp(1_700_000_000, tz=BERLIN)
    assert user.age_basis is AgeBasis.FIRST_LOGIN
    assert user.age_is_lower_bound is True
    assert user.age_bound_at == datetime.fromtimestamp(1_600_000_000, tz=BERLIN)


def test_to_user_marks_pre_nc31_accounts_as_old() -> None:
    details = {
        "id": "old",
        "firstLoginTimestamp": -1,
        "lastLoginTimestamp": 1_700_000_000,
    }

    user = to_user(details, {}, now=NOW)

    assert user.age_basis is AgeBasis.PRE_NC31
    assert user.age_days is None
    assert user.age_is_lower_bound is True
    assert user.never_logged_in is False


def test_to_user_uses_exact_created_at_from_inventory() -> None:
    created_at = datetime(2025, 1, 15, 12, 0, tzinfo=BERLIN)
    record = InventoryRecord(
        user_id="jdoe",
        first_seen_at=created_at,
        first_seen_source="first_seen",
        last_seen_at=NOW,
        created_at=created_at,
        created_source="import",
        first_login_at=None,
        last_login_at=None,
        display_name="Jane Doe",
        email="jane@example.org",
        enabled=True,
    )

    user = to_user({"id": "jdoe"}, {}, record=record, now=NOW)

    assert user.age_basis is AgeBasis.EXACT
    assert user.age_days == (NOW - created_at).days
    assert user.age_is_lower_bound is False
    assert user.created_at == created_at


def test_to_user_falls_back_to_first_seen() -> None:
    first_seen = datetime(2026, 1, 1, 12, 0, tzinfo=BERLIN)
    record = InventoryRecord(
        user_id="jdoe",
        first_seen_at=first_seen,
        first_seen_source="first_seen",
        last_seen_at=NOW,
        created_at=None,
        created_source=None,
        first_login_at=None,
        last_login_at=None,
        display_name="Jane Doe",
        email=None,
        enabled=True,
    )

    user = to_user({"id": "jdoe"}, {}, record=record, now=NOW)

    assert user.age_basis is AgeBasis.FIRST_SEEN
    assert user.age_days == (NOW - first_seen).days
    assert user.never_logged_in is True


def test_to_user_detects_resource_users_by_prefix() -> None:
    resource = to_user({"id": "OCMaster"}, {}, now=NOW)
    normal = to_user({"id": "jdoe"}, {}, now=NOW)
    custom = to_user({"id": "SVC_backup"}, {}, now=NOW, resource_user_prefix="SVC")

    assert resource.is_resource is True
    assert normal.is_resource is False
    assert custom.is_resource is True


def test_to_user_without_age_source_is_unknown() -> None:
    user = to_user({"id": "jdoe"}, {}, now=NOW)

    assert user.age_basis is AgeBasis.UNKNOWN
    assert user.age_days is None
    assert user.age_is_lower_bound is False
    assert user.never_logged_in is True


def test_to_user_treats_baseline_first_seen_as_unknown() -> None:
    record = InventoryRecord(
        user_id="jdoe",
        first_seen_at=NOW,
        first_seen_source="baseline",
        last_seen_at=NOW,
        created_at=None,
        created_source=None,
        first_login_at=None,
        last_login_at=None,
        display_name="Jane Doe",
        email=None,
        enabled=True,
    )

    user = to_user({"id": "jdoe"}, {}, record=record, now=NOW)

    assert user.age_basis is AgeBasis.UNKNOWN
    assert user.age_days is None
    assert user.first_seen_source == "baseline"


@respx.mock
def test_fetch_user_details_paginates(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        if offset == 0:
            data = {"users": {"a": {"id": "a"}, "b": {"id": "b"}}}
        else:
            data = {"users": {"c": {"id": "c"}}}
        return httpx.Response(200, json=_ok_payload(data))

    respx.get(USERS_URL).mock(side_effect=handler)

    with NextcloudClient(settings) as client:
        details = fetch_user_details(client, limit=2)

    assert [item["id"] for item in details] == ["a", "b", "c"]


@respx.mock
def test_fetch_user_details_stops_on_repeated_page(settings: Settings) -> None:
    route = respx.get(USERS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_ok_payload({"users": {"a": {"id": "a"}, "b": {"id": "b"}}}),
        )
    )

    with NextcloudClient(settings) as client:
        details = fetch_user_details(client, limit=2)

    assert [item["id"] for item in details] == ["a", "b"]
    assert route.call_count == 2


@respx.mock
def test_fetch_group_names_resolves_display_names(settings: Settings) -> None:
    respx.get(GROUPS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_ok_payload({"groups": [{"id": "admins", "displayname": "Administratoren"}]}),
        )
    )

    with NextcloudClient(settings) as client:
        names = fetch_group_names(client)

    assert names == {"admins": "Administratoren"}


@respx.mock
def test_load_users_tracks_inventory(settings: Settings) -> None:
    respx.get(GROUPS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_ok_payload({"groups": [{"id": "admins", "displayname": "Administratoren"}]}),
        )
    )
    respx.get(USERS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_ok_payload(
                {
                    "users": {
                        "jdoe": {
                            "id": "jdoe",
                            "displayname": "Jane Doe",
                            "email": "jane@example.org",
                            "enabled": True,
                            "firstLoginTimestamp": 1_600_000_000,
                            "lastLoginTimestamp": 1_700_000_000,
                            "groups": ["admins"],
                        }
                    }
                }
            ),
        )
    )

    users = load_users(settings, track_inventory=True, now=NOW)

    assert users[0].age_basis is AgeBasis.FIRST_LOGIN
    assert users[0].first_seen_at == NOW
    assert users[0].group_names == ("Administratoren",)
    with InventoryStore(settings.state_dir / "inventory.sqlite3") as store:
        record = store.get_many(["jdoe"])["jdoe"]
    assert record.first_seen_at == NOW
    assert record.last_login_at == datetime.fromtimestamp(1_700_000_000, tz=BERLIN)
