"""CLI-Befehle für Gruppen."""

from __future__ import annotations

from typing import Annotated

import typer

from adfc_nc.commands.common import (
    HelpOnMissingCommand,
    load_group_reports_or_exit,
    load_stale_group_reports_or_exit,
    require_subcommand,
)
from adfc_nc.output import output_group_reports
from adfc_nc.stale import StaleCriteria, UserStatus, UserType

groups_app = typer.Typer(
    help="Gruppen durchsuchen und Mitglieder auswerten.",
    callback=require_subcommand,
    invoke_without_command=True,
)


@groups_app.command("search", cls=HelpOnMissingCommand)
def search_groups(
    queries: Annotated[
        list[str],
        typer.Argument(
            help="Vollständiger Gruppenname oder Teilstring, z. B. Augsburg.",
        ),
    ],
    user_type: Annotated[
        UserType,
        typer.Option("--type", help="Benutzer oder Ressourcenbenutzer."),
    ] = UserType.USER,
    json_output: Annotated[bool, typer.Option("--json", help="Ausgabe als JSON.")] = False,
) -> None:
    """Sucht Gruppen und listet deren Mitglieder samt letzter Anmeldung."""
    reports = load_group_reports_or_exit(queries=queries, user_type=user_type)
    output_group_reports(reports, as_json=json_output)


@groups_app.command("stale", cls=HelpOnMissingCommand)
def stale_groups(
    queries: Annotated[
        list[str],
        typer.Argument(
            help="Vollständiger Gruppenname oder Teilstring, z. B. Augsburg.",
        ),
    ],
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
    json_output: Annotated[bool, typer.Option("--json", help="Ausgabe als JSON.")] = False,
) -> None:
    """Listet Deaktivierungs-Kandidaten in den gefundenen Gruppen."""
    criteria = StaleCriteria(
        min_age_days=min_age_days,
        inactive_days=inactive_days,
        include_unknown_age=include_unknown_age,
        status=status,
    )
    reports = load_stale_group_reports_or_exit(
        queries=queries,
        user_type=user_type,
        criteria=criteria,
    )
    output_group_reports(reports, as_json=json_output)
