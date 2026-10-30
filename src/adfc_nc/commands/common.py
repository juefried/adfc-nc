"""Gemeinsame Fehlerbehandlung für CLI-Befehle."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import NoReturn

import typer
from pydantic import ValidationError
from typer._click.core import Context
from typer._click.exceptions import MissingParameter
from typer.core import TyperCommand

from adfc_nc.config import load_settings
from adfc_nc.inventory import InventoryError
from adfc_nc.nextcloud.errors import AuthenticationError, NextcloudError, RateLimitError
from adfc_nc.nextcloud.groups import (
    GroupReport,
    load_group_reports,
    load_stale_group_reports,
)
from adfc_nc.nextcloud.users import User, load_users
from adfc_nc.stale import StaleCriteria, UserType


class HelpOnMissingCommand(TyperCommand):
    """Zeigt Hilfe mit Hinweis, wenn ein Pflichtargument fehlt."""

    def parse_args(self, ctx: Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except MissingParameter:
            _show_help_and_exit(ctx)


def require_subcommand(ctx: Context) -> None:
    """Zeigt Hilfe mit Hinweis, wenn eine Befehlsgruppe ohne Befehl läuft."""
    if ctx.invoked_subcommand is None:
        _show_help_and_exit(ctx)


def _show_help_and_exit(ctx: Context) -> NoReturn:
    typer.echo(ctx.get_help())
    typer.echo(f"Weitere Hilfe: {ctx.command_path} --help")
    raise typer.Exit(code=2)


@contextmanager
def _translated_errors() -> Iterator[None]:
    try:
        yield
    except ValidationError as exc:
        fields = ", ".join(".".join(str(part) for part in error["loc"]) for error in exc.errors())
        typer.echo(f"Konfiguration ungültig: {fields}", err=True)
        raise typer.Exit(code=2) from exc
    except AuthenticationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=3) from exc
    except RateLimitError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=4) from exc
    except InventoryError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    except NextcloudError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


def load_users_or_exit(*, track_inventory: bool = False, search: str = "") -> list[User]:
    """Lädt Benutzer und übersetzt Fehler in CLI-Meldungen und Exit-Codes."""
    with _translated_errors():
        settings = load_settings()
        return load_users(settings, search=search, track_inventory=track_inventory)


def load_group_reports_or_exit(
    *,
    queries: Sequence[str],
    user_type: UserType,
) -> list[GroupReport]:
    """Lädt Gruppenauswertungen und übersetzt Fehler in CLI-Meldungen."""
    with _translated_errors():
        settings = load_settings()
        return load_group_reports(settings, queries, user_type=user_type)


def load_stale_group_reports_or_exit(
    *,
    queries: Sequence[str],
    user_type: UserType,
    criteria: StaleCriteria,
) -> list[GroupReport]:
    """Lädt Kandidaten-Auswertungen und übersetzt Fehler in CLI-Meldungen."""
    with _translated_errors():
        settings = load_settings()
        return load_stale_group_reports(
            settings,
            queries,
            user_type=user_type,
            criteria=criteria,
        )
