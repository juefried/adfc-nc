"""Ausgabe von Benutzerlisten als Tabelle oder JSON."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from rich.console import Console
from rich.table import Table

from adfc_nc.nextcloud.groups import GroupReport
from adfc_nc.nextcloud.users import AgeBasis, User
from adfc_nc.stale import StaleCriteria


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


def output_group_reports(reports: Sequence[GroupReport], *, as_json: bool) -> None:
    """Gibt Gruppenauswertungen menschenlesbar oder als JSON aus."""
    if as_json:
        print(
            json.dumps(
                [_group_report_to_dict(report) for report in reports],
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    console = Console(width=200)
    for index, report in enumerate(reports):
        if index:
            console.print()
        console.print(f"[bold]Suchbegriff:[/bold] {report.query}")
        stale = report.criteria is not None
        if report.criteria is not None:
            console.print(f"Kriterien: {_format_stale_criteria(report.criteria)}")
        if not report.groups:
            console.print("Keine Kandidaten gefunden." if stale else "Keine Gruppen gefunden.")
            continue
        if not report.users:
            console.print(
                "Keine Kandidaten gefunden."
                if stale
                else "Keine Mitglieder in den gefundenen Gruppen."
            )
            console.print("[bold]Gruppen:[/bold]")
            console.print(_build_group_overview_table(report))
            continue
        console.print("[bold]Benutzer:[/bold]")
        console.print(_build_group_users_table(report))
        console.print("[bold]Gruppen:[/bold]")
        console.print(_build_group_overview_table(report))


def _group_report_to_dict(report: GroupReport) -> dict[str, object]:
    groups = [
        {
            "id": group.id,
            "display_name": group.display_name,
            "member_count": sum(1 for user in report.users if group.id in user.group_ids),
            "member_ids": [user.id for user in report.users if group.id in user.group_ids],
        }
        for group in report.groups
    ]
    payload: dict[str, object] = {
        "query": report.query,
        "type": report.user_type.value,
        "groups": groups,
        "users": [
            _group_user_to_dict(user, stale=report.criteria is not None) for user in report.users
        ],
    }
    if report.criteria is not None:
        payload["criteria"] = {
            "min_age_days": report.criteria.min_age_days,
            "inactive_days": report.criteria.inactive_days,
            "include_unknown_age": report.criteria.include_unknown_age,
            "status": report.criteria.status.value,
        }
    return payload


def _group_user_to_dict(user: User, *, stale: bool) -> dict[str, object]:
    data: dict[str, object] = {
        "id": user.id,
        "display_name": user.display_name,
        "email": user.email,
        "enabled": user.enabled,
        "is_resource": user.is_resource,
        "type": _user_type_value(user),
        "last_login": _iso(user.last_login),
        "never_logged_in": user.never_logged_in,
    }
    if stale:
        data.update(
            {
                "created_at": _iso(user.created_at),
                "first_seen_at": _iso(user.first_seen_at),
                "first_seen_source": user.first_seen_source,
                "age_days": user.age_days,
                "age_basis": user.age_basis.value,
                "age_is_lower_bound": user.age_is_lower_bound,
                "age_bound_at": _iso(user.age_bound_at),
                "first_login": _iso(user.first_login),
                "inactive_days": user.inactive_days,
            }
        )
    return data


def _build_group_overview_table(report: GroupReport) -> Table:
    table = Table(header_style="bold")
    table.add_column("Gruppe", no_wrap=True)
    table.add_column("Anzeigename")
    table.add_column("Anzahl", no_wrap=True)
    table.add_column("Mitglieder-Kennungen")

    for group in report.groups:
        member_ids = [user.id for user in report.users if group.id in user.group_ids]
        table.add_row(
            group.id,
            group.display_name,
            str(len(member_ids)),
            ", ".join(member_ids) or "-",
        )
    return table


def _build_group_users_table(report: GroupReport) -> Table:
    stale = report.criteria is not None
    table = Table(header_style="bold")
    table.add_column("Kennung", no_wrap=True)
    table.add_column("Typ", no_wrap=True)
    table.add_column("Name")
    table.add_column("E-Mail")
    if stale:
        table.add_column("Angelegt")
        table.add_column("Alter", no_wrap=True)
    table.add_column("Letzte Anmeldung")
    if stale:
        table.add_column("Inaktiv", no_wrap=True)
    table.add_column("Angemeldet", no_wrap=True)
    table.add_column("Status", no_wrap=True)

    for user in report.users:
        row = [
            user.id,
            _user_type(user),
            user.display_name,
            user.email or "-",
        ]
        if stale:
            row.extend([_format_created_at(user), _format_age(user)])
        row.extend(
            [
                _format_last_login(user.last_login),
                "nie" if user.never_logged_in else "ja",
                "aktiv" if user.enabled else "deaktiviert",
            ]
        )
        if stale:
            row.insert(7, _format_inactive(user))
        table.add_row(*row)
    return table


def _format_stale_criteria(criteria: StaleCriteria) -> str:
    unknown = "einbezogen" if criteria.include_unknown_age else "ausgeschlossen"
    return (
        f"Alter ≥ {criteria.min_age_days} T, "
        f"inaktiv ≥ {criteria.inactive_days} T, "
        f"Status {criteria.status.value}, "
        f"unbekanntes Alter {unknown}"
    )


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
