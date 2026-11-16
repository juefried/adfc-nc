"""Einstiegspunkt der ADFC-Nextcloud-CLI."""

from __future__ import annotations

import os
import sys
from collections.abc import Sequence

import typer

from adfc_nc.commands.groups import groups_app
from adfc_nc.commands.inventory import inventory_app
from adfc_nc.commands.users import users_app

_COMPLETION_ENV_VARS = (
    "_ADFC_NC_COMPLETE",
    "_TYPER_COMPLETE_ARGS",
    "_TYPER_COMPLETE_WORD_TO_COMPLETE",
)

app = typer.Typer(
    help="Administrationswerkzeug für die ADFC-Nextcloud-Instanz.",
    no_args_is_help=True,
)
app.add_typer(users_app, name="users")
app.add_typer(groups_app, name="groups")
app.add_typer(inventory_app, name="inventory")


def clear_completion_environment_for_help(arguments: Sequence[str]) -> None:
    """Entfernt hängengebliebene Completion-Variablen bei expliziten Hilfeaufrufen."""
    if not any(argument in {"-h", "--help"} for argument in arguments):
        return
    for name in _COMPLETION_ENV_VARS:
        os.environ.pop(name, None)


def main() -> None:
    """Startet die CLI."""
    clear_completion_environment_for_help(sys.argv[1:])
    app()
