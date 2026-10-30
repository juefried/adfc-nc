"""Einstiegspunkt der ADFC-Nextcloud-CLI."""

import typer

from adfc_nc.commands.groups import groups_app
from adfc_nc.commands.inventory import inventory_app
from adfc_nc.commands.users import users_app

app = typer.Typer(
    help="Administrationswerkzeug für die ADFC-Nextcloud-Instanz.",
    no_args_is_help=True,
)
app.add_typer(users_app, name="users")
app.add_typer(groups_app, name="groups")
app.add_typer(inventory_app, name="inventory")


def main() -> None:
    """Startet die CLI."""
    app()
