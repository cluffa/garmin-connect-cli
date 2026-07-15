from __future__ import annotations

import typer

from garmin_cli import client
from garmin_cli.dates import parse_date, parse_range
from garmin_cli.output import command_output
from garmin_cli.projections import project

health_app = typer.Typer(help="Retrieve health/wellness data.", no_args_is_help=True)


def _iso(date_str: str) -> str:
    return parse_date(date_str).isoformat()


def _iso_range(range_str: str) -> tuple[str, str]:
    start, end = parse_range(range_str)
    return start.isoformat(), end.isoformat()


@health_app.command()
@command_output
def steps(date_range: str = typer.Argument("today")):
    """Daily steps over a date or range."""
    start, end = _iso_range(date_range)
    return project("steps", client.load_client().get_daily_steps(start, end))


@health_app.command(name="heart-rate")
@command_output
def heart_rate(date_str: str = typer.Argument("today")):
    """Heart-rate data for a date."""
    return project("heart_rate", client.load_client().get_heart_rates(_iso(date_str)))


@health_app.command()
@command_output
def sleep(date_str: str = typer.Argument("today")):
    """Sleep data for a date."""
    return project("sleep", client.load_client().get_sleep_data(_iso(date_str)))


@health_app.command(name="body-battery")
@command_output
def body_battery(date_range: str = typer.Argument("today")):
    """Body Battery over a date or range."""
    start, end = _iso_range(date_range)
    return project("body_battery", client.load_client().get_body_battery(start, end))


@health_app.command()
@command_output
def hrv(date_str: str = typer.Argument("today")):
    """HRV data for a date."""
    return project("hrv", client.load_client().get_hrv_data(_iso(date_str)))


@health_app.command()
@command_output
def stress(date_str: str = typer.Argument("today")):
    """Stress data for a date."""
    return project("stress", client.load_client().get_stress_data(_iso(date_str)))


@health_app.command()
@command_output
def weight(date_range: str = typer.Argument("today")):
    """Weigh-ins over a date or range."""
    start, end = _iso_range(date_range)
    return project("weight", client.load_client().get_weigh_ins(start, end))
