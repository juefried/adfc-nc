from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
import respx
from typer.testing import CliRunner

from adfc_nc.cli import app
from adfc_nc.commands import common as common_command
from adfc_nc.commands import groups as groups_command
from adfc_nc.config import Settings
from adfc_nc.nextcloud.errors import AuthenticationError
from adfc_nc.nextcloud.groups import (
    build_group_report,
    load_group_reports,
    load_stale_group_reports,
)
from adfc_nc.nextcloud.users import AgeBasis, User
from adfc_nc.stale import StaleCriteria, UserStatus, UserType, is_stale_candidate

RUNNER = CliRunner()
BERLIN = ZoneInfo("Europe/Berlin")
NOW = datetime(2026, 10, 30, 12, 0, tzinfo=BERLIN)
BASE_URL = "https://by.adfc-clouds.de"
USERS_URL = f"{BASE_URL}/ocs/v2.php/cloud/users/details"
GROUPS_URL = f"{BASE_URL}/ocs/v2.php/cloud/groups/details"

GROUP_NAMES = {
    "KV_Augsburg_Land": "KV Augsburg Land",
    "KV_Augsburg_Service": "KV Augsburg Service",
    "KV_Augsburg_Stadt": "KV Augsburg Stadt",
    "KV_Muenchen": "KV München",
    "LV_Augsburg": "LV Augsburg",
}


def _user(
    user_id: str,
    *,
    display_name: str | None = None,
    group_ids: tuple[str, ...] = (),
    last_login: datetime | None = None,
    never_logged_in: bool = False,
    enabled: bool = True,
    is_resource: bool = False,
    age_days: int | None = 70,
    age_basis: AgeBasis = AgeBasis.FIRST_LOGIN,
    inactive_days: int | None = 70,
) -> User:
    login = last_login
    if login is None and not never_logged_in:
        login = NOW
    return User(
        id=user_id,
        display_name=display_name or user_id,
        email=f"{user_id}@example.org",
        enabled=enabled,
        last_login=login,
        group_ids=group_ids,
        group_names=group_ids,
        first_login=login,
        age_days=age_days,
        age_basis=age_basis,
        age_is_lower_bound=age_basis is not AgeBasis.UNKNOWN,
        age_bound_at=login,
        inactive_days=inactive_days,
        never_logged_in=never_logged_in,
        is_resource=is_resource,
    )


def _augsburg_users() -> list[User]:
    return [
        _user(
            "anna",
            display_name="Anna",
            group_ids=("KV_Augsburg_Land", "LV_Augsburg"),
        ),
        _user(
            "bernd",
            display_name="Bernd",
            group_ids=("KV_Augsburg_Stadt",),
        ),
        _user(
            "carla",
            display_name="Carla",
            group_ids=("KV_Muenchen",),
        ),
        _user(
            "OC_Service",
            display_name="OC Service",
            group_ids=("KV_Augsburg_Service",),
            is_resource=True,
        ),
    ]


def _ok_payload(data: object) -> dict[str, object]:
    return {"ocs": {"meta": {"status": "ok", "statuscode": 200}, "data": data}}


def test_build_group_report_finds_substring_across_name_parts() -> None:
    users = _augsburg_users()

    report = build_group_report("Augsburg", GROUP_NAMES, users)

    assert [group.id for group in report.groups] == [
        "KV_Augsburg_Land",
        "KV_Augsburg_Service",
        "KV_Augsburg_Stadt",
        "LV_Augsburg",
    ]
    assert [user.id for user in report.users] == ["anna", "bernd"]
    assert [group.id for group in report.matching_groups(users[0])] == [
        "KV_Augsburg_Land",
        "LV_Augsburg",
    ]


def test_build_group_report_matches_display_name_with_spaces() -> None:
    report = build_group_report("KV Augsburg Land", GROUP_NAMES, _augsburg_users())

    assert [group.id for group in report.groups] == ["KV_Augsburg_Land"]


def test_build_group_report_returns_empty_without_match() -> None:
    report = build_group_report("Rheinland", GROUP_NAMES, _augsburg_users())

    assert report.groups == ()
    assert report.users == ()


def test_build_group_report_marks_never_logged_in_users() -> None:
    user = _user(
        "never",
        group_ids=("KV_Augsburg_Stadt",),
        never_logged_in=True,
        inactive_days=None,
    )

    report = build_group_report("Augsburg", GROUP_NAMES, [user])

    assert report.users[0].never_logged_in is True
    assert report.users[0].last_login is None


def test_build_group_report_filters_by_user_type() -> None:
    users = _augsburg_users()

    all_report = build_group_report("Augsburg", GROUP_NAMES, users, user_type=UserType.ALL)
    user_report = build_group_report("Augsburg", GROUP_NAMES, users, user_type=UserType.USER)
    resource_report = build_group_report(
        "Augsburg",
        GROUP_NAMES,
        users,
        user_type=UserType.RESOURCE,
    )

    assert {user.id for user in all_report.users} == {"anna", "bernd", "OC_Service"}
    assert {user.id for user in user_report.users} == {"anna", "bernd"}
    assert {user.id for user in resource_report.users} == {"OC_Service"}


def test_is_stale_candidate_matches_users_stale_criteria() -> None:
    criteria = StaleCriteria(min_age_days=60, inactive_days=60)

    assert is_stale_candidate(_user("stale", age_days=90, inactive_days=90), criteria)
    assert is_stale_candidate(
        _user("never", age_days=90, never_logged_in=True, inactive_days=None),
        criteria,
    )
    assert not is_stale_candidate(_user("young", age_days=10, inactive_days=90), criteria)
    assert not is_stale_candidate(_user("active", age_days=90, inactive_days=10), criteria)
    assert not is_stale_candidate(
        _user("unknown", age_days=None, age_basis=AgeBasis.UNKNOWN, inactive_days=90),
        criteria,
    )
    assert is_stale_candidate(
        _user("unknown", age_days=None, age_basis=AgeBasis.UNKNOWN, inactive_days=90),
        StaleCriteria(min_age_days=60, inactive_days=60, include_unknown_age=True),
    )


def test_is_stale_candidate_applies_status_filter() -> None:
    criteria = StaleCriteria(status=UserStatus.DISABLED)

    assert is_stale_candidate(
        _user("disabled", enabled=False, age_days=90, inactive_days=90),
        criteria,
    )
    assert not is_stale_candidate(
        _user("active", enabled=True, age_days=90, inactive_days=90),
        criteria,
    )


@respx.mock
def test_load_group_reports_fetches_once_for_multiple_queries(settings: Settings) -> None:
    respx.get(GROUPS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_ok_payload(
                {
                    "groups": [
                        {"id": "KV_Augsburg_Stadt", "displayname": "KV Augsburg Stadt"},
                        {"id": "KV_Muenchen", "displayname": "KV München"},
                    ]
                }
            ),
        )
    )
    respx.get(USERS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_ok_payload(
                {
                    "users": {
                        "anna": {
                            "id": "anna",
                            "displayname": "Anna",
                            "lastLoginTimestamp": 1_700_000_000,
                            "groups": ["KV_Augsburg_Stadt"],
                        }
                    }
                }
            ),
        )
    )

    reports = load_group_reports(settings, ["Augsburg", "Muenchen"], now=NOW)

    assert [report.query for report in reports] == ["Augsburg", "Muenchen"]
    assert [group.id for group in reports[0].groups] == ["KV_Augsburg_Stadt"]
    assert [user.id for user in reports[0].users] == ["anna"]
    assert reports[1].users == ()
    assert respx.calls.call_count == 2


@respx.mock
def test_load_stale_group_reports_uses_inventory_and_filters_candidates(
    settings: Settings,
) -> None:
    old_login = int((NOW - timedelta(days=90)).timestamp())
    respx.get(GROUPS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_ok_payload(
                {
                    "groups": [
                        {"id": "KV_Augsburg_Stadt", "displayname": "KV Augsburg Stadt"},
                    ]
                }
            ),
        )
    )
    respx.get(USERS_URL).mock(
        return_value=httpx.Response(
            200,
            json=_ok_payload(
                {
                    "users": {
                        "stale": {
                            "id": "stale",
                            "displayname": "Stale",
                            "firstLoginTimestamp": old_login,
                            "lastLoginTimestamp": old_login,
                            "groups": ["KV_Augsburg_Stadt"],
                        },
                        "young": {
                            "id": "young",
                            "displayname": "Young",
                            "firstLoginTimestamp": int((NOW - timedelta(days=10)).timestamp()),
                            "lastLoginTimestamp": int((NOW - timedelta(days=10)).timestamp()),
                            "groups": ["KV_Augsburg_Stadt"],
                        },
                        "OC_Old": {
                            "id": "OC_Old",
                            "displayname": "OC Old",
                            "firstLoginTimestamp": old_login,
                            "lastLoginTimestamp": old_login,
                            "groups": ["KV_Augsburg_Stadt"],
                        },
                    }
                }
            ),
        )
    )

    reports = load_stale_group_reports(
        settings,
        ["Augsburg"],
        criteria=StaleCriteria(),
        now=NOW,
    )

    assert [user.id for user in reports[0].users] == ["stale"]
    assert [group.id for group in reports[0].groups] == ["KV_Augsburg_Stadt"]
    assert reports[0].criteria == StaleCriteria()


def test_groups_search_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    report = build_group_report("Augsburg", GROUP_NAMES, _augsburg_users())
    monkeypatch.setattr(
        groups_command,
        "load_group_reports_or_exit",
        lambda **kwargs: [report],
    )

    result = RUNNER.invoke(app, ["groups", "search", "Augsburg", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["query"] == "Augsburg"
    assert payload[0]["type"] == "user"
    groups = {group["id"]: group for group in payload[0]["groups"]}
    assert groups["KV_Augsburg_Land"]["member_ids"] == ["anna"]
    assert groups["LV_Augsburg"]["member_ids"] == ["anna"]
    assert groups["KV_Augsburg_Stadt"]["member_ids"] == ["bernd"]
    assert groups["KV_Augsburg_Service"]["member_ids"] == []
    users = {user["id"]: user for user in payload[0]["users"]}
    assert set(users) == {"anna", "bernd"}
    assert users["anna"]["last_login"].startswith("2026-10-30T12:00:00")
    assert users["anna"]["never_logged_in"] is False
    assert "groups" not in users["anna"]
    assert "memberships" not in payload[0]


def test_groups_search_passes_type_filter(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_load(**kwargs: object) -> list[object]:
        captured.update(kwargs)
        return [
            build_group_report(
                "Augsburg",
                GROUP_NAMES,
                _augsburg_users(),
                user_type=kwargs["user_type"],
            )
        ]

    monkeypatch.setattr(groups_command, "load_group_reports_or_exit", fake_load)

    result = RUNNER.invoke(
        app,
        ["groups", "search", "Augsburg", "--type", "all", "--json"],
    )

    assert result.exit_code == 0
    assert captured["user_type"] is UserType.ALL
    payload = json.loads(result.stdout)
    assert payload[0]["type"] == "all"
    assert {user["id"] for user in payload[0]["users"]} == {
        "anna",
        "bernd",
        "OC_Service",
    }


def test_groups_stale_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    criteria = StaleCriteria(
        min_age_days=90,
        inactive_days=30,
        include_unknown_age=True,
        status=UserStatus.ACTIVE,
    )
    report = build_group_report(
        "Augsburg",
        GROUP_NAMES,
        [
            _user(
                "stale",
                display_name="Stale",
                group_ids=("KV_Augsburg_Stadt",),
                age_days=120,
                inactive_days=90,
            )
        ],
        include_empty_groups=False,
        criteria=criteria,
    )

    def fake_load(**kwargs: object) -> list[object]:
        captured.update(kwargs)
        return [report]

    monkeypatch.setattr(groups_command, "load_stale_group_reports_or_exit", fake_load)

    result = RUNNER.invoke(
        app,
        [
            "groups",
            "stale",
            "Augsburg",
            "--min-age-days",
            "90",
            "--inactive-days",
            "30",
            "--include-unknown-age",
            "--status",
            "active",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert captured["criteria"] == criteria
    assert captured["user_type"] is UserType.USER
    payload = json.loads(result.stdout)
    assert payload[0]["criteria"] == {
        "min_age_days": 90,
        "inactive_days": 30,
        "include_unknown_age": True,
        "status": "active",
    }
    assert [user["id"] for user in payload[0]["users"]] == ["stale"]
    assert payload[0]["users"][0]["age_days"] == 120
    assert payload[0]["users"][0]["inactive_days"] == 90


def test_groups_search_table_output(monkeypatch: pytest.MonkeyPatch) -> None:
    report = build_group_report("Augsburg", GROUP_NAMES, _augsburg_users())
    monkeypatch.setattr(
        groups_command,
        "load_group_reports_or_exit",
        lambda **kwargs: [report],
    )

    result = RUNNER.invoke(app, ["groups", "search", "Augsburg"], color=False)

    assert result.exit_code == 0
    assert "Benutzer:" in result.output
    assert "Gruppen:" in result.output
    assert "KV_Augsburg_Land" in result.output
    assert "Mitglieder-Kennungen" in result.output
    assert "anna" in result.output
    assert "ja" in result.output


def test_groups_stale_table_output(monkeypatch: pytest.MonkeyPatch) -> None:
    criteria = StaleCriteria()
    report = build_group_report(
        "Augsburg",
        GROUP_NAMES,
        [
            _user(
                "stale",
                display_name="Stale",
                group_ids=("KV_Augsburg_Stadt",),
                age_days=90,
                inactive_days=90,
            )
        ],
        include_empty_groups=False,
        criteria=criteria,
    )
    monkeypatch.setattr(
        groups_command,
        "load_stale_group_reports_or_exit",
        lambda **kwargs: [report],
    )

    result = RUNNER.invoke(app, ["groups", "stale", "Augsburg"], color=False)

    assert result.exit_code == 0
    assert "Kriterien:" in result.output
    assert "Alter" in result.output
    assert "≥ 90 T" in result.output
    assert "Inaktiv" in result.output
    assert "KV_Augsburg_Stadt" in result.output


@pytest.mark.parametrize(
    "args",
    [
        ["users"],
        ["groups"],
        ["inventory"],
        ["groups", "search"],
        ["groups", "search", "--json"],
        ["groups", "stale"],
        ["groups", "stale", "--min-age-days", "30"],
    ],
)
def test_incomplete_commands_show_help_and_hint(args: list[str]) -> None:
    result = RUNNER.invoke(app, args, color=False)

    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "--help" in result.output


def test_unknown_option_remains_a_usage_error() -> None:
    result = RUNNER.invoke(app, ["groups", "search", "--bogus"], color=False)

    assert result.exit_code == 2
    assert "No such option" in result.output


def test_groups_search_reports_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common_command, "load_settings", lambda: object())

    def fail(settings: object, queries: object, **kwargs: object) -> object:
        raise AuthenticationError("Zugangsdaten abgelehnt")

    monkeypatch.setattr(common_command, "load_group_reports", fail)

    result = RUNNER.invoke(app, ["groups", "search", "Augsburg"])

    assert result.exit_code == 3
    assert "Zugangsdaten abgelehnt" in result.output


def test_groups_stale_reports_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common_command, "load_settings", lambda: object())

    def fail(settings: object, queries: object, **kwargs: object) -> object:
        raise AuthenticationError("Zugangsdaten abgelehnt")

    monkeypatch.setattr(common_command, "load_stale_group_reports", fail)

    result = RUNNER.invoke(app, ["groups", "stale", "Augsburg"])

    assert result.exit_code == 3
    assert "Zugangsdaten abgelehnt" in result.output
