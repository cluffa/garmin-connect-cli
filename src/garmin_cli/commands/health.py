from __future__ import annotations

import typer

from garmin_cli import client
from garmin_cli.dates import parse_date, parse_range
from garmin_cli.output import command_output
from garmin_cli.projections import project
from garmin_cli.series import MAX_RANGE_DAYS, day_series

health_app = typer.Typer(help="Retrieve health/wellness data.", no_args_is_help=True)

_MAX_DAYS_OPT = typer.Option(
    MAX_RANGE_DAYS,
    "--max-days",
    help="Cap on days fetched for a range; each day is one request to Garmin.",
)


def _iso(date_str: str) -> str:
    return parse_date(date_str).isoformat()


def _iso_range(range_str: str) -> tuple[str, str]:
    start, end = parse_range(range_str)
    return start.isoformat(), end.isoformat()


# ── Natively range-capable: one request covers the whole span ──


@health_app.command()
@command_output
def steps(date_range: str = typer.Argument("today")):
    """Daily steps over a date or range."""
    start, end = _iso_range(date_range)
    return project("steps", client.load_client().get_daily_steps(start, end))


@health_app.command(name="body-battery")
@command_output
def body_battery(date_range: str = typer.Argument("today")):
    """Body Battery over a date or range."""
    start, end = _iso_range(date_range)
    return project("body_battery", client.load_client().get_body_battery(start, end))


@health_app.command()
@command_output
def weight(date_range: str = typer.Argument("today")):
    """Weigh-ins over a date or range."""
    start, end = _iso_range(date_range)
    return project("weight", client.load_client().get_weigh_ins(start, end))


@health_app.command(name="weekly-steps")
@command_output
def weekly_steps(
    date_str: str = typer.Argument("today"),
    weeks: int = typer.Option(52, "--weeks", help="Number of weeks ending at the date."),
):
    """Weekly step aggregates ending at a date — one request per year of data."""
    return project(
        "weekly_steps", client.load_client().get_weekly_steps(_iso(date_str), weeks)
    )


@health_app.command(name="weekly-stress")
@command_output
def weekly_stress(
    date_str: str = typer.Argument("today"),
    weeks: int = typer.Option(52, "--weeks", help="Number of weeks ending at the date."),
):
    """Weekly stress aggregates ending at a date — one request per year of data."""
    return project(
        "weekly_stress", client.load_client().get_weekly_stress(_iso(date_str), weeks)
    )


# ── Single-date upstream: a range costs one request per day ────


@health_app.command(name="heart-rate")
@command_output
def heart_rate(
    date_range: str = typer.Argument("today"),
    max_days: int = _MAX_DAYS_OPT,
):
    """Heart-rate data for a date or range."""
    return day_series(
        "heart_rate", client.load_client().get_heart_rates, date_range, max_days
    )


@health_app.command()
@command_output
def sleep(
    date_range: str = typer.Argument("today"),
    max_days: int = _MAX_DAYS_OPT,
):
    """Sleep data for a date or range."""
    return day_series(
        "sleep", client.load_client().get_sleep_data, date_range, max_days
    )


@health_app.command()
@command_output
def hrv(
    date_range: str = typer.Argument("today"),
    max_days: int = _MAX_DAYS_OPT,
):
    """HRV data for a date or range."""
    return day_series("hrv", client.load_client().get_hrv_data, date_range, max_days)


@health_app.command()
@command_output
def stress(
    date_range: str = typer.Argument("today"),
    max_days: int = _MAX_DAYS_OPT,
):
    """Stress data for a date or range."""
    return day_series(
        "stress", client.load_client().get_stress_data, date_range, max_days
    )
