"""Lokales Inventar für Benutzerdaten, die die OCS-API nicht liefert."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType


class InventoryError(Exception):
    """Das lokale Inventar konnte nicht gelesen oder geschrieben werden."""


@dataclass(frozen=True)
class InventoryUser:
    """Momentaufnahme eines Benutzers für die Inventar-Aktualisierung."""

    user_id: str
    display_name: str
    email: str | None
    enabled: bool
    first_login_at: datetime | None
    last_login_at: datetime | None


@dataclass(frozen=True)
class InventoryRecord:
    """Gespeicherte Inventardaten eines Benutzers."""

    user_id: str
    first_seen_at: datetime
    first_seen_source: str
    last_seen_at: datetime
    created_at: datetime | None
    created_source: str | None
    first_login_at: datetime | None
    last_login_at: datetime | None
    display_name: str
    email: str | None
    enabled: bool


_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    first_seen_source TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    created_at TEXT,
    created_source TEXT,
    first_login_at TEXT,
    last_login_at TEXT,
    display_name TEXT NOT NULL,
    email TEXT,
    enabled INTEGER NOT NULL
)
"""


class InventoryStore:
    """SQLite-basiertes Inventar für Benutzerdaten."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute(_SCHEMA)
        self._ensure_first_seen_source()
        self._connection.commit()

    def __enter__(self) -> InventoryStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Schließt die Datenbankverbindung."""
        self._connection.close()

    def sync(self, users: Sequence[InventoryUser], *, now: datetime | None = None) -> None:
        """Aktualisiert das Inventar mit der aktuellen Benutzerliste."""
        moment = now or datetime.now(tz=UTC)
        existing = self.get_many([user.user_id for user in users])
        is_initial_sync = self._user_count() == 0
        rows: list[tuple[object, ...]] = []

        for user in users:
            record = existing.get(user.user_id)
            first_seen = record.first_seen_at if record else moment
            first_seen_source = (
                record.first_seen_source
                if record
                else ("baseline" if is_initial_sync else "first_seen")
            )
            created_at = record.created_at if record else None
            created_source = record.created_source if record else None
            first_login = _earliest(
                record.first_login_at if record else None,
                user.first_login_at,
            )
            last_login = _latest(
                record.last_login_at if record else None,
                user.last_login_at,
            )
            rows.append(
                (
                    user.user_id,
                    first_seen.isoformat(),
                    first_seen_source,
                    moment.isoformat(),
                    created_at.isoformat() if created_at else None,
                    created_source,
                    first_login.isoformat() if first_login else None,
                    last_login.isoformat() if last_login else None,
                    user.display_name,
                    user.email,
                    1 if user.enabled else 0,
                )
            )

        self._connection.executemany(
            """
            INSERT INTO users (
                user_id, first_seen_at, first_seen_source, last_seen_at,
                created_at, created_source, first_login_at, last_login_at,
                display_name, email, enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_seen_at = excluded.last_seen_at,
                created_at = excluded.created_at,
                created_source = excluded.created_source,
                first_login_at = excluded.first_login_at,
                last_login_at = excluded.last_login_at,
                display_name = excluded.display_name,
                email = excluded.email,
                enabled = excluded.enabled
            """,
            rows,
        )
        self._connection.commit()

    def set_created_at(
        self,
        user_id: str,
        created_at: datetime,
        *,
        source: str = "import",
    ) -> None:
        """Setzt ein exaktes Anlagedatum für einen Benutzer."""
        self._connection.execute(
            """
            UPDATE users
            SET created_at = ?, created_source = ?
            WHERE user_id = ?
            """,
            (created_at.isoformat(), source, user_id),
        )
        self._connection.commit()

    def get_many(self, user_ids: Sequence[str]) -> dict[str, InventoryRecord]:
        """Lädt Inventardaten für die angegebenen Benutzerkennungen."""
        result: dict[str, InventoryRecord] = {}
        ids = list(user_ids)
        for start in range(0, len(ids), 500):
            chunk = ids[start : start + 500]
            placeholders = ", ".join("?" for _ in chunk)
            rows = self._connection.execute(
                f"SELECT * FROM users WHERE user_id IN ({placeholders})",
                chunk,
            )
            result.update({str(row["user_id"]): _row_to_record(row) for row in rows})
        return result

    def _ensure_first_seen_source(self) -> None:
        columns = {str(row["name"]) for row in self._connection.execute("PRAGMA table_info(users)")}
        if "first_seen_source" not in columns:
            self._connection.execute(
                "ALTER TABLE users ADD COLUMN first_seen_source TEXT NOT NULL DEFAULT 'baseline'"
            )

    def _user_count(self) -> int:
        row = self._connection.execute("SELECT COUNT(*) AS count FROM users").fetchone()
        assert row is not None
        return int(row["count"])


@contextmanager
def open_inventory(path: Path) -> Iterator[InventoryStore]:
    """Öffnet das Inventar und übersetzt Datei-/Datenbankfehler."""
    try:
        with InventoryStore(path) as store:
            yield store
    except (OSError, sqlite3.Error) as exc:
        raise InventoryError("Das lokale Inventar konnte nicht verarbeitet werden.") from exc


def _row_to_record(row: sqlite3.Row) -> InventoryRecord:
    return InventoryRecord(
        user_id=str(row["user_id"]),
        first_seen_at=datetime.fromisoformat(str(row["first_seen_at"])),
        first_seen_source=str(row["first_seen_source"]),
        last_seen_at=datetime.fromisoformat(str(row["last_seen_at"])),
        created_at=_parse_optional(row["created_at"]),
        created_source=str(row["created_source"]) if row["created_source"] else None,
        first_login_at=_parse_optional(row["first_login_at"]),
        last_login_at=_parse_optional(row["last_login_at"]),
        display_name=str(row["display_name"]),
        email=str(row["email"]) if row["email"] else None,
        enabled=bool(row["enabled"]),
    )


def _parse_optional(value: object) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(str(value))


def _earliest(left: datetime | None, right: datetime | None) -> datetime | None:
    values = [value for value in (left, right) if value is not None]
    return min(values) if values else None


def _latest(left: datetime | None, right: datetime | None) -> datetime | None:
    values = [value for value in (left, right) if value is not None]
    return max(values) if values else None
