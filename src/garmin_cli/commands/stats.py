from __future__ import annotations

import typer

from garmin_cli import client
from garmin_cli.dates import parse_date
from garmin_cli.output import command_output
from garmin_cli.projections import project

stats_app = typer.Typer(help="Summaries and training status.", no_args_is_help=True)


@stats_app.command()
@command_output
def summary(date_str: str = typer.Argument("today")):
    """Daily user summary."""
    return project(
        "summary",
        client.load_client().get_user_summary(parse_date(date_str).isoformat()),
    )


@stats_app.command(name="training-status")
@command_output
def training_status(date_str: str = typer.Argument("today")):
    """Training status for a date."""
    return project(
        "training_status",
        client.load_client().get_training_status(parse_date(date_str).isoformat()),
    )


@stats_app.command()
@command_output
def readiness(date_str: str = typer.Argument("today")):
    """Training readiness for a date."""
    return project(
        "readiness",
        client.load_client().get_training_readiness(parse_date(date_str).isoformat()),
    )


@stats_app.command()
@command_output
def records():
    """Personal records."""
    return project("records", client.load_client().get_personal_record())


@stats_app.command()
@command_output
def progress(
    start: str = typer.Argument(...),
    end: str = typer.Argument(...),
    metric: str = typer.Option("distance", "--metric"),
):
    """Progress summary between two dates."""
    s = parse_date(start).isoformat()
    e = parse_date(end).isoformat()
    return project(
        "progress",
        client.load_client().get_progress_summary_between_dates(s, e, metric),
    )
