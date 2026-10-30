"""Ausgabe von Benutzerlisten als Tabelle oder JSON."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from rich.console import Console
from rich.table import Table

from adfc_nc.nextcloud.users import AgeBasis, User


def output_users(users: Sequence[User], *, as_json: bool) -> None:
    """Gibt die Benutzerliste menschenlesbar oder als JSON aus."""
    if as_json:
        print(json.dumps([_user_to_dict(user) for user in users], ensure_ascii=False, indent=2))
        return
    Console(width=200).print(_build_table(users))


def output_stale_users(users: Sequence[User], *, as_json: bool) -> None:
    """Gibt die Stale-Liste mit Alters- und Inaktivitätsdaten aus."""
    if as_json:
        print(
            json.dumps(
                [_stale_user_to_dict(user) for user in users],
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    Console(width=200).print(_build_stale_table(users))


def _user_to_dict(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "enabled": user.enabled,
        "is_resource": user.is_resource,
        "type": _user_type_value(user),
        "last_login": user.last_login.isoformat(timespec="seconds") if user.last_login else None,
        "groups": [
            {"id": group_id, "display_name": group_name}
            for group_id, group_name in zip(user.group_ids, user.group_names, strict=True)
        ],
    }


def _stale_user_to_dict(user: User) -> dict[str, object]:
    return {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "enabled": user.enabled,
        "is_resource": user.is_resource,
        "type": _user_type_value(user),
        "created_at": _iso(user.created_at),
        "first_seen_at": _iso(user.first_seen_at),
        "first_seen_source": user.first_seen_source,
        "age_days": user.age_days,
        "age_basis": user.age_basis.value,
        "age_is_lower_bound": user.age_is_lower_bound,
        "age_bound_at": _iso(user.age_bound_at),
        "first_login": _iso(user.first_login),
        "last_login": _iso(user.last_login),
        "inactive_days": user.inactive_days,
        "never_logged_in": user.never_logged_in,
        "groups": [
            {"id": group_id, "display_name": group_name}
            for group_id, group_name in zip(user.group_ids, user.group_names, strict=True)
        ],
    }


def _build_stale_table(users: Sequence[User]) -> Table:
    table = Table(header_style="bold")
    table.add_column("Kennung", no_wrap=True)
    table.add_column("Typ", no_wrap=True)
    table.add_column("Name")
    table.add_column("E-Mail")
    table.add_column("Angelegt")
    table.add_column("Alter", no_wrap=True)
    table.add_column("Letzte Anmeldung")
    table.add_column("Inaktiv", no_wrap=True)
    table.add_column("Gruppen")
    table.add_column("Status", no_wrap=True)

    for user in users:
        table.add_row(
            user.id,
            _user_type(user),
            user.display_name,
            user.email or "-",
            _format_created_at(user),
            _format_age(user),
            _format_last_login(user.last_login),
            _format_inactive(user),
            ", ".join(user.group_names) or "-",
            "aktiv" if user.enabled else "deaktiviert",
        )
    return table


def _build_table(users: Sequence[User]) -> Table:
    table = Table(header_style="bold")
    table.add_column("Kennung", no_wrap=True)
    table.add_column("Typ", no_wrap=True)
    table.add_column("Name")
    table.add_column("E-Mail")
    table.add_column("Letzte Anmeldung")
    table.add_column("Gruppen")
    table.add_column("Status", no_wrap=True)

    for user in users:
        table.add_row(
            user.id,
            _user_type(user),
            user.display_name,
            user.email or "-",
            _format_last_login(user.last_login),
            ", ".join(user.group_names) or "-",
            "aktiv" if user.enabled else "deaktiviert",
        )
    return table


def _format_last_login(value: datetime | None) -> str:
    if value is None:
        return "nie"
    return value.strftime("%Y-%m-%d %H:%M:%S %Z")


def _format_created_at(user: User) -> str:
    if user.created_at is not None:
        return user.created_at.strftime("%Y-%m-%d")
    if user.age_basis is AgeBasis.PRE_NC31:
        return "vor NC31"
    if user.age_bound_at is not None:
        return f"≤ {user.age_bound_at.strftime('%Y-%m-%d')}"
    return "unbekannt"


def _format_age(user: User) -> str:
    if user.age_days is None:
        return "vor NC31" if user.age_basis is AgeBasis.PRE_NC31 else "unbekannt"
    prefix = "≥ " if user.age_is_lower_bound else ""
    return f"{prefix}{user.age_days} T"


def _format_inactive(user: User) -> str:
    if user.never_logged_in:
        return "nie"
    if user.inactive_days is None:
        return "-"
    return f"{user.inactive_days} T"


def _iso(value: datetime | None) -> str | None:
    return value.isoformat(timespec="seconds") if value else None


def _user_type(user: User) -> str:
    return "Ressource" if user.is_resource else "Benutzer"


def _user_type_value(user: User) -> str:
    return "resource" if user.is_resource else "user"
