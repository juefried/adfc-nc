from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from adfc_nc.inventory import InventoryStore, InventoryUser

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)


def _inventory_user(
    user_id: str = "jdoe",
    *,
    first_login_at: datetime | None = None,
    last_login_at: datetime | None = None,
    enabled: bool = True,
) -> InventoryUser:
    return InventoryUser(
        user_id=user_id,
        display_name="Jane Doe",
        email="jane@example.org",
        enabled=enabled,
        first_login_at=first_login_at,
        last_login_at=last_login_at,
    )


def test_sync_stores_first_seen_and_login_times(tmp_path: Path) -> None:
    first_login = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    last_login = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)

    with InventoryStore(tmp_path / "inventory.sqlite3") as store:
        store.sync(
            [_inventory_user(first_login_at=first_login, last_login_at=last_login)],
            now=NOW,
        )
        record = store.get_many(["jdoe"])["jdoe"]

    assert record.first_seen_at == NOW
    assert record.first_seen_source == "baseline"
    assert record.last_seen_at == NOW
    assert record.first_login_at == first_login
    assert record.last_login_at == last_login
    assert record.created_at is None


def test_sync_preserves_first_seen_and_exact_created_at(tmp_path: Path) -> None:
    created_at = datetime(2025, 1, 15, 12, 0, tzinfo=UTC)
    later = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)

    with InventoryStore(tmp_path / "inventory.sqlite3") as store:
        store.sync([_inventory_user()], now=NOW)
        store.set_created_at("jdoe", created_at)
        store.sync([_inventory_user()], now=later)
        record = store.get_many(["jdoe"])["jdoe"]

    assert record.first_seen_at == NOW
    assert record.first_seen_source == "baseline"
    assert record.last_seen_at == later
    assert record.created_at == created_at
    assert record.created_source == "import"


def test_sync_marks_later_new_users_as_first_seen(tmp_path: Path) -> None:
    later = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)

    with InventoryStore(tmp_path / "inventory.sqlite3") as store:
        store.sync([_inventory_user("existing")], now=NOW)
        store.sync([_inventory_user("existing"), _inventory_user("new")], now=later)
        records = store.get_many(["existing", "new"])

    assert records["existing"].first_seen_source == "baseline"
    assert records["new"].first_seen_source == "first_seen"
    assert records["new"].first_seen_at == later


def test_sync_keeps_earliest_first_login_and_latest_last_login(tmp_path: Path) -> None:
    first_login = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    later_first_login = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    last_login = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
    later_last_login = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    later_sync = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)

    with InventoryStore(tmp_path / "inventory.sqlite3") as store:
        store.sync(
            [_inventory_user(first_login_at=first_login, last_login_at=last_login)],
            now=NOW,
        )
        store.sync(
            [
                _inventory_user(
                    first_login_at=later_first_login,
                    last_login_at=later_last_login,
                    enabled=False,
                )
            ],
            now=later_sync,
        )
        record = store.get_many(["jdoe"])["jdoe"]

    assert record.first_login_at == first_login
    assert record.last_login_at == later_last_login
    assert record.enabled is False


def test_get_many_without_ids_returns_empty_mapping(tmp_path: Path) -> None:
    with InventoryStore(tmp_path / "inventory.sqlite3") as store:
        assert store.get_many([]) == {}
