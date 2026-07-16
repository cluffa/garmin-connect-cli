from __future__ import annotations

import typer

from garmin_cli import client
from garmin_cli.output import command_output

badge_app = typer.Typer(
    help="Badges and challenges.", no_args_is_help=True
)


@badge_app.command()
@command_output
def earned(
    limit: int = typer.Option(20, "--limit", "-n", help="Number to show."),
):
    """List recently earned badges."""
    data = client.load_client().get_earned_badges()
    sorted_data = sorted(
        data, key=lambda b: b.get("badgeEarnedDate", ""), reverse=True
    )
    return sorted_data[:limit]


@badge_app.command()
@command_output
def in_progress():
    """List badges in progress."""
    return client.load_client().get_in_progress_badges()


@badge_app.command()
@command_output
def available(
    start: int = typer.Option(1, "--start", help="Start index."),
    limit: int = typer.Option(20, "--limit", "-n", help="Number to show."),
):
    """List available badge challenges."""
    return client.load_client().get_available_badge_challenges(start, limit)


@badge_app.command()
@command_output
def adhoc(
    start: int = typer.Option(1, "--start", help="Start index."),
    limit: int = typer.Option(20, "--limit", "-n", help="Number to show."),
):
    """List ad-hoc challenges."""
    return client.load_client().get_adhoc_challenges(start, limit)


@badge_app.command()
@command_output
def challenges(
    start: int = typer.Option(1, "--start", help="Start index."),
    limit: int = typer.Option(20, "--limit", "-n", help="Number to show."),
):
    """List all badge challenges."""
    return client.load_client().get_badge_challenges(start, limit)
