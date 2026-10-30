from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from typer.testing import CliRunner

from adfc_nc.cli import app
from adfc_nc.commands import common as common_command
from adfc_nc.commands import inventory as inventory_command
from adfc_nc.commands import users as users_command
from adfc_nc.inventory import InventoryError
from adfc_nc.nextcloud.errors import AuthenticationError
from adfc_nc.nextcloud.users import AgeBasis, User

RUNNER = CliRunner()
BERLIN = ZoneInfo("Europe/Berlin")


def _user(
    user_id: str = "jdoe",
    *,
    display_name: str = "Jane Doe",
    email: str | None = "jane@example.org",
    enabled: bool = True,
    age_days: int | None = 70,
    age_basis: AgeBasis = AgeBasis.FIRST_LOGIN,
    inactive_days: int | None = 70,
    never_logged_in: bool = False,
    is_resource: bool = False,
) -> User:
    last_login = None if never_logged_in else datetime(2026, 7, 1, 12, 0, tzinfo=BERLIN)
    return User(
        id=user_id,
        display_name=display_name,
        email=email,
        enabled=enabled,
        last_login=last_login,
        group_ids=("admins",),
        group_names=("Administratoren",),
        first_login=last_login,
        age_days=age_days,
        age_basis=age_basis,
        age_is_lower_bound=age_basis is not AgeBasis.UNKNOWN,
        age_bound_at=last_login,
        inactive_days=inactive_days,
        never_logged_in=never_logged_in,
        is_resource=is_resource,
    )


def _patch_users(monkeypatch: pytest.MonkeyPatch, users: list[User]) -> None:
    monkeypatch.setattr(users_command, "load_users_or_exit", lambda **kwargs: users)


def test_users_list_json_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_users(monkeypatch, [_user()])

    result = RUNNER.invoke(app, ["users", "list", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["id"] == "jdoe"
    assert payload[0]["display_name"] == "Jane Doe"
    assert payload[0]["email"] == "jane@example.org"
    assert payload[0]["is_resource"] is False
    assert payload[0]["type"] == "user"
    assert payload[0]["groups"] == [{"id": "admins", "display_name": "Administratoren"}]
    assert payload[0]["last_login"].startswith("2026-07-01T12:00:00")


def test_users_list_table_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_users(monkeypatch, [_user()])

    result = RUNNER.invoke(app, ["users", "list"], color=False)

    assert result.exit_code == 0
    assert "jdoe" in result.output
    assert "Jane Doe" in result.output
    assert "2026-07-01" in result.output
    assert "aktiv" in result.output


def test_users_list_filters_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_users(monkeypatch, [_user("active"), _user("disabled", enabled=False)])

    result = RUNNER.invoke(app, ["users", "list", "--status", "disabled", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["id"] for item in payload] == ["disabled"]


def test_users_list_filters_resource_type(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_users(
        monkeypatch,
        [_user("jdoe"), _user("OCMaster", is_resource=True)],
    )

    result = RUNNER.invoke(app, ["users", "list", "--type", "resource", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["id"] for item in payload] == ["OCMaster"]
    assert payload[0]["type"] == "resource"


def test_users_stale_filters_by_age_and_inactivity(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_users(
        monkeypatch,
        [
            _user("stale"),
            _user("young", age_days=10),
            _user("active", inactive_days=10),
        ],
    )

    result = RUNNER.invoke(app, ["users", "stale", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["id"] for item in payload] == ["stale"]
    assert payload[0]["age_days"] == 70
    assert payload[0]["age_basis"] == "first_login"
    assert payload[0]["inactive_days"] == 70


def test_users_stale_excludes_resource_users_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_users(
        monkeypatch,
        [_user("jdoe"), _user("OCMaster", is_resource=True)],
    )

    result = RUNNER.invoke(app, ["users", "stale", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["id"] for item in payload] == ["jdoe"]
    assert "Ressourcenbenutzer" in result.output


def test_users_stale_includes_resource_users_with_type_all(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_users(
        monkeypatch,
        [_user("jdoe"), _user("OCMaster", is_resource=True)],
    )

    result = RUNNER.invoke(app, ["users", "stale", "--type", "all", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert {item["id"] for item in payload} == {"jdoe", "OCMaster"}


def test_users_stale_can_filter_resource_users_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_users(
        monkeypatch,
        [_user("jdoe"), _user("OCMaster", is_resource=True)],
    )

    result = RUNNER.invoke(app, ["users", "stale", "--type", "resource", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["id"] for item in payload] == ["OCMaster"]
    assert payload[0]["is_resource"] is True


def test_users_stale_includes_never_logged_in_with_known_age(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_users(
        monkeypatch,
        [_user("never", inactive_days=None, never_logged_in=True)],
    )

    result = RUNNER.invoke(app, ["users", "stale", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["id"] == "never"
    assert payload[0]["never_logged_in"] is True
    assert payload[0]["inactive_days"] is None


def test_users_stale_includes_pre_nc31(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_users(
        monkeypatch,
        [_user("old", age_days=None, age_basis=AgeBasis.PRE_NC31)],
    )

    result = RUNNER.invoke(app, ["users", "stale", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["age_basis"] == "pre_nc31"


def test_users_stale_excludes_unknown_age_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_users(
        monkeypatch,
        [_user("unknown", age_days=None, age_basis=AgeBasis.UNKNOWN)],
    )

    result = RUNNER.invoke(app, ["users", "stale", "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == []
    assert "unbekanntem Alter" in result.output


def test_users_stale_includes_unknown_age_on_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_users(
        monkeypatch,
        [_user("unknown", age_days=None, age_basis=AgeBasis.UNKNOWN)],
    )

    result = RUNNER.invoke(
        app,
        ["users", "stale", "--include-unknown-age", "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["id"] for item in payload] == ["unknown"]
    assert payload[0]["age_basis"] == "unknown"
    assert payload[0]["age_days"] is None


def test_users_stale_searches_locally(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_users(
        monkeypatch,
        [
            _user("jdoe"),
            _user("msmith", display_name="Max Smith", email="max@example.org"),
        ],
    )

    result = RUNNER.invoke(app, ["users", "stale", "--search", "max", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [item["id"] for item in payload] == ["msmith"]


def test_users_stale_table_output(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_users(monkeypatch, [_user("stale")])

    result = RUNNER.invoke(app, ["users", "stale"], color=False)

    assert result.exit_code == 0
    assert "stale" in result.output
    assert "≥ 70 T" in result.output
    assert "70 T" in result.output


def test_users_list_reports_authentication_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common_command, "load_settings", lambda: object())

    def fail(settings: object, **kwargs: object) -> list[User]:
        raise AuthenticationError("Zugangsdaten abgelehnt")

    monkeypatch.setattr(common_command, "load_users", fail)

    result = RUNNER.invoke(app, ["users", "list"])

    assert result.exit_code == 3
    assert "Zugangsdaten abgelehnt" in result.output


def test_inventory_sync_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        inventory_command,
        "load_users_or_exit",
        lambda **kwargs: [_user()],
    )

    result = RUNNER.invoke(app, ["inventory", "sync"])

    assert result.exit_code == 0
    assert "1 Benutzer" in result.output


def test_inventory_sync_reports_inventory_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common_command, "load_settings", lambda: object())

    def fail(settings: object, **kwargs: object) -> list[User]:
        raise InventoryError("Inventar kaputt")

    monkeypatch.setattr(common_command, "load_users", fail)

    result = RUNNER.invoke(app, ["inventory", "sync"])

    assert result.exit_code == 1
    assert "Inventar kaputt" in result.output
