"""Gemeinsame Fehlerbehandlung für CLI-Befehle."""

from __future__ import annotations

import typer
from pydantic import ValidationError

from adfc_nc.config import load_settings
from adfc_nc.inventory import InventoryError
from adfc_nc.nextcloud.errors import AuthenticationError, NextcloudError, RateLimitError
from adfc_nc.nextcloud.users import User, load_users


def load_users_or_exit(*, track_inventory: bool = False, search: str = "") -> list[User]:
    """Lädt Benutzer und übersetzt Fehler in CLI-Meldungen und Exit-Codes."""
    try:
        settings = load_settings()
        return load_users(settings, search=search, track_inventory=track_inventory)
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
