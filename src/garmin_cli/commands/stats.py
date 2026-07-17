from __future__ import annotations

from datetime import date, timedelta

import typer

from garmin_cli import client, dates
from garmin_cli.output import command_output
from garmin_cli.projections import project

_METERS_PER_MILE = 1609.34

stats_app = typer.Typer(help="Summaries and training status.", no_args_is_help=True)


@stats_app.command()
@command_output
def summary(date_str: str = typer.Argument("today")):
    """Daily user summary."""
    return project(
        "summary",
        client.load_client().get_user_summary(dates.parse_date(date_str).isoformat()),
    )


@stats_app.command(name="training-status")
@command_output
def training_status(date_str: str = typer.Argument("today")):
    """Training status for a date."""
    return project(
        "training_status",
        client.load_client().get_training_status(dates.parse_date(date_str).isoformat()),
    )


@stats_app.command()
@command_output
def readiness(date_str: str = typer.Argument("today")):
    """Training readiness for a date."""
    return project(
        "readiness",
        client.load_client().get_training_readiness(dates.parse_date(date_str).isoformat()),
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
    s = dates.parse_date(start).isoformat()
    e = dates.parse_date(end).isoformat()
    return project(
        "progress",
        client.load_client().get_progress_summary_between_dates(s, e, metric),
    )


@stats_app.command()
@command_output
def weekly(date_str: str = typer.Argument("today")):
    """Weekly running mileage summary.

    Shows total mileage, run count, longest run, duration, and comparisons
    against the previous week and a rolling 4-week average for the 7-day
    window ending on *date_str* (default: today).
    """
    end_date = dates.parse_date(date_str)
    start_date = end_date - timedelta(days=6)

    # Pull enough activities to cover 4+ weeks of history for the averages.
    garmin = client.load_client()
    activities = garmin.get_activities(0, 200)

    # Filter to running activities only.
    runs = [
        a for a in activities
        if a.get("parentTypeId") == 1
    ]

    def _in_window(a: dict, w_start: date, w_end: date) -> bool:
        raw = a.get("startTimeLocal") or a.get("startTimeGMT") or ""
        try:
            d = date.fromisoformat(raw[:10])
        except (ValueError, IndexError):
            return False
        return w_start <= d <= w_end

    def _distance_mi(a: dict) -> float:
        d = a.get("distance")
        return d / _METERS_PER_MILE if d else 0.0

    # Current week (7-day window ending on end_date).
    week_runs = [a for a in runs if _in_window(a, start_date, end_date)]
    week_total_mi = sum(_distance_mi(a) for a in week_runs)
    run_count = len(week_runs)
    longest_run_mi = max((_distance_mi(a) for a in week_runs), default=0.0)
    total_duration_hours = round(
        sum((a.get("duration") or 0) for a in week_runs) / 3600, 1
    )
    avg_daily_mi = round(week_total_mi / 7, 2)

    # Previous week (7-day window immediately before this week).
    prev_start = start_date - timedelta(days=7)
    prev_end = start_date - timedelta(days=1)
    prev_week_runs = [a for a in runs if _in_window(a, prev_start, prev_end)]
    previous_week_mi = round(sum(_distance_mi(a) for a in prev_week_runs), 2)

    # Rolling 4-week average (current week + 3 prior weeks).
    four_start = start_date - timedelta(days=21)
    four_runs = [a for a in runs if _in_window(a, four_start, end_date)]
    four_week_mi = sum(_distance_mi(a) for a in four_runs)
    four_week_avg_mi = round(four_week_mi / 4, 2)

    return project("weekly_volume", {
        "week_total_mi": round(week_total_mi, 2),
        "previous_week_mi": previous_week_mi,
        "four_week_avg_mi": four_week_avg_mi,
        "run_count": run_count,
        "longest_run_mi": round(longest_run_mi, 2),
        "total_duration_hours": total_duration_hours,
        "avg_daily_mi": avg_daily_mi,
        "window": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
        },
    })
