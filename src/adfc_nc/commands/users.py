"""CLI-Befehle für Benutzer."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

import typer

from adfc_nc.commands.common import load_users_or_exit
from adfc_nc.nextcloud.users import AgeBasis, User
from adfc_nc.output import output_stale_users, output_users

users_app = typer.Typer(help="Benutzer der Nextcloud-Instanz verwalten.")


class SortOrder(StrEnum):
    """Sortierreihenfolge der Benutzerliste."""

    ID = "id"
    LAST_LOGIN = "last-login"


class StaleSortOrder(StrEnum):
    """Sortierreihenfolge der Stale-Liste."""

    INACTIVE = "inactive"
    AGE = "age"
    ID = "id"


class UserStatus(StrEnum):
    """Statusfilter der Benutzerliste."""

    ALL = "all"
    ACTIVE = "active"
    DISABLED = "disabled"


class UserType(StrEnum):
    """Unterscheidung zwischen normalen Benutzern und Ressourcenbenutzern."""

    ALL = "all"
    USER = "user"
    RESOURCE = "resource"


@users_app.command("list")
def list_users(
    json_output: Annotated[bool, typer.Option("--json", help="Ausgabe als JSON.")] = False,
    search: Annotated[
        str,
        typer.Option("--search", help="Nach Kennung oder Name filtern."),
    ] = "",
    sort_order: Annotated[
        SortOrder,
        typer.Option("--sort", help="Sortierung der Liste."),
    ] = SortOrder.ID,
    status: Annotated[
        UserStatus,
        typer.Option("--status", help="Statusfilter."),
    ] = UserStatus.ALL,
    user_type: Annotated[
        UserType,
        typer.Option("--type", help="Benutzer oder Ressourcenbenutzer."),
    ] = UserType.ALL,
) -> None:
    """Listet Benutzer mit Name, E-Mail, letzter Anmeldung und Gruppen."""
    users = load_users_or_exit(search=search)
    filtered = _filter_users(users, status, user_type)
    output_users(_sort_users(filtered, sort_order), as_json=json_output)


@users_app.command("stale")
def stale_users(
    min_age_days: Annotated[
        int,
        typer.Option("--min-age-days", min=1, help="Mindestalter in Tagen."),
    ] = 60,
    inactive_days: Annotated[
        int,
        typer.Option("--inactive-days", min=1, help="Mindestinaktivität in Tagen."),
    ] = 60,
    include_unknown_age: Annotated[
        bool,
        typer.Option(
            "--include-unknown-age",
            help="Benutzer mit unbekanntem Alter einbeziehen.",
        ),
    ] = False,
    status: Annotated[
        UserStatus,
        typer.Option("--status", help="Statusfilter."),
    ] = UserStatus.ALL,
    user_type: Annotated[
        UserType,
        typer.Option("--type", help="Benutzer oder Ressourcenbenutzer."),
    ] = UserType.USER,
    sort_order: Annotated[
        StaleSortOrder,
        typer.Option("--sort", help="Sortierung der Liste."),
    ] = StaleSortOrder.INACTIVE,
    search: Annotated[
        str,
        typer.Option("--search", help="Nach Kennung, Name oder E-Mail filtern."),
    ] = "",
    json_output: Annotated[bool, typer.Option("--json", help="Ausgabe als JSON.")] = False,
) -> None:
    """Listet alte, inaktive Benutzer anhand von Alter und letzter Anmeldung."""
    users = load_users_or_exit(track_inventory=True)
    filtered = _filter_stale(
        users,
        min_age_days=min_age_days,
        inactive_days=inactive_days,
        include_unknown_age=include_unknown_age,
        status=status,
        user_type=user_type,
        search=search,
    )
    excluded_unknown = _count_unknown_excluded(
        users,
        inactive_days=inactive_days,
        status=status,
        user_type=user_type,
        include_unknown_age=include_unknown_age,
        search=search,
    )
    excluded_resources = _count_resource_excluded(
        users,
        min_age_days=min_age_days,
        inactive_days=inactive_days,
        include_unknown_age=include_unknown_age,
        status=status,
        user_type=user_type,
        search=search,
    )
    output_stale_users(_sort_stale(filtered, sort_order), as_json=json_output)
    if excluded_unknown:
        typer.echo(
            f"Hinweis: {excluded_unknown} Benutzer mit unbekanntem Alter nicht enthalten "
            "(--include-unknown-age).",
            err=True,
        )
    if excluded_resources:
        typer.echo(
            f"Hinweis: {excluded_resources} Ressourcenbenutzer nicht enthalten (--type all).",
            err=True,
        )


def _filter_users(
    users: list[User],
    status: UserStatus,
    user_type: UserType,
) -> list[User]:
    return [
        user for user in users if _type_matches(user, user_type) and _status_matches(user, status)
    ]


def _filter_stale(
    users: list[User],
    *,
    min_age_days: int,
    inactive_days: int,
    include_unknown_age: bool,
    status: UserStatus,
    user_type: UserType,
    search: str,
) -> list[User]:
    return [
        user
        for user in users
        if _type_matches(user, user_type)
        and _search_matches(user, search)
        and _status_matches(user, status)
        and _matches_stale(user, min_age_days, inactive_days, include_unknown_age)
    ]


def _matches_stale(
    user: User,
    min_age_days: int,
    inactive_days: int,
    include_unknown_age: bool,
) -> bool:
    if not _inactive_matches(user, inactive_days):
        return False
    if user.age_days is not None and user.age_days >= min_age_days:
        return True
    if user.age_basis is AgeBasis.PRE_NC31:
        return True
    return include_unknown_age and user.age_basis is AgeBasis.UNKNOWN


def _count_unknown_excluded(
    users: list[User],
    *,
    inactive_days: int,
    status: UserStatus,
    user_type: UserType,
    include_unknown_age: bool,
    search: str,
) -> int:
    if include_unknown_age:
        return 0
    return sum(
        1
        for user in users
        if _type_matches(user, user_type)
        and _search_matches(user, search)
        and _status_matches(user, status)
        and _inactive_matches(user, inactive_days)
        and user.age_basis is AgeBasis.UNKNOWN
    )


def _count_resource_excluded(
    users: list[User],
    *,
    min_age_days: int,
    inactive_days: int,
    include_unknown_age: bool,
    status: UserStatus,
    user_type: UserType,
    search: str,
) -> int:
    if user_type is not UserType.USER:
        return 0
    return sum(
        1
        for user in users
        if user.is_resource
        and _search_matches(user, search)
        and _status_matches(user, status)
        and _matches_stale(user, min_age_days, inactive_days, include_unknown_age)
    )


def _search_matches(user: User, search: str) -> bool:
    if not search:
        return True
    needle = search.casefold()
    return (
        needle in user.id.casefold()
        or needle in user.display_name.casefold()
        or (user.email is not None and needle in user.email.casefold())
    )


def _type_matches(user: User, user_type: UserType) -> bool:
    if user_type is UserType.USER:
        return not user.is_resource
    if user_type is UserType.RESOURCE:
        return user.is_resource
    return True


def _status_matches(user: User, status: UserStatus) -> bool:
    if status is UserStatus.ACTIVE:
        return user.enabled
    if status is UserStatus.DISABLED:
        return not user.enabled
    return True


def _inactive_matches(user: User, inactive_days: int) -> bool:
    if user.never_logged_in:
        return True
    return user.inactive_days is not None and user.inactive_days >= inactive_days


def _sort_users(users: list[User], sort_order: SortOrder) -> list[User]:
    if sort_order is SortOrder.LAST_LOGIN:
        return sorted(
            users,
            key=lambda user: (
                user.last_login is None,
                -(user.last_login.timestamp() if user.last_login else 0.0),
            ),
        )
    return sorted(users, key=lambda user: user.id.casefold())


def _sort_stale(users: list[User], sort_order: StaleSortOrder) -> list[User]:
    if sort_order is StaleSortOrder.AGE:
        return sorted(users, key=_age_sort_key)
    if sort_order is StaleSortOrder.ID:
        return sorted(users, key=lambda user: user.id.casefold())
    return sorted(users, key=_inactive_sort_key)


def _age_sort_key(user: User) -> tuple[int, int, str]:
    if user.age_basis is AgeBasis.PRE_NC31:
        rank = 0
    elif user.age_days is not None:
        rank = 1
    else:
        rank = 2
    return (rank, -(user.age_days or 0), user.id.casefold())


def _inactive_sort_key(user: User) -> tuple[bool, int, str]:
    return (not user.never_logged_in, -(user.inactive_days or 0), user.id.casefold())
