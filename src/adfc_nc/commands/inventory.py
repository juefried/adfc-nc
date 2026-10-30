"""CLI-Befehle für das lokale Inventar."""

from __future__ import annotations

import typer

from adfc_nc.commands.common import load_users_or_exit

inventory_app = typer.Typer(help="Lokales Benutzerinventar verwalten.")


@inventory_app.command("sync")
def sync_inventory() -> None:
    """Aktualisiert das lokale Inventar aus der Nextcloud-Instanz."""
    users = load_users_or_exit(track_inventory=True)
    typer.echo(f"Inventar aktualisiert: {len(users)} Benutzer.")
