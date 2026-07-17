"""Tests for the stats command group."""

import json
from datetime import date

import pytest
from typer.testing import CliRunner

from garmin_cli import client, dates
from garmin_cli.cli import app

runner = CliRunner()


class FakeClient:
    def get_user_summary(self, cdate):
        return {
            "cdate": cdate,
            "totalSteps": 8000,
            "averageSpo2": 96,
            "avgWakingRespirationValue": 14.0,
        }

    def get_personal_record(self):
        return [{"typeId": 1}]

    def get_progress_summary_between_dates(self, start, end, metric="distance", groupbyactivities=True):
        return {"start": start, "end": end}

    def get_activities(self, start=0, limit=20, activityType=None):
        # Return a mix of running and non-running activities across
        # the three weeks surrounding 2026-07-15.
        return _WEEKLY_ACTIVITIES


# 2026-07-15 is a Wednesday.  The 7-day window ends on 07-15
# → Mon 07-09 through Wed 07-15.
_WEEKLY_ACTIVITIES = [
    # This week (07-09 – 07-15): 3 runs.
    {
        "activityId": 1,
        "parentTypeId": 1,
        "startTimeLocal": "2026-07-14 06:00:00",
        "distance": 16093.4,   # 10.00 mi
        "duration": 3600,       # 1 h
    },
    {
        "activityId": 2,
        "parentTypeId": 1,
        "startTimeLocal": "2026-07-11 07:00:00",
        "distance": 8046.7,    # 5.00 mi
        "duration": 1800,       # 0.5 h
    },
    {
        "activityId": 3,
        "parentTypeId": 1,
        "startTimeLocal": "2026-07-09 06:30:00",
        "distance": 1609.34,   # 1.00 mi
        "duration": 600,        # 0.167 h
    },
    # Non-running activity — must be excluded.
    {
        "activityId": 9,
        "parentTypeId": 2,     # cycling
        "startTimeLocal": "2026-07-14 12:00:00",
        "distance": 50000,
        "duration": 7200,
    },
    # Previous week (07-02 – 07-08): 1 run.
    {
        "activityId": 4,
        "parentTypeId": 1,
        "startTimeLocal": "2026-07-05 06:00:00",
        "distance": 3218.68,   # 2.00 mi
        "duration": 900,
    },
    # Three weeks prior (06-18 – 07-01): 2 runs.
    {
        "activityId": 5,
        "parentTypeId": 1,
        "startTimeLocal": "2026-06-28 06:00:00",
        "distance": 4828.02,   # 3.00 mi
        "duration": 1500,
    },
    {
        "activityId": 6,
        "parentTypeId": 1,
        "startTimeLocal": "2026-06-20 06:00:00",
        "distance": 6437.36,   # 4.00 mi
        "duration": 2100,
    },
]


def test_summary(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(dates, "parse_date", lambda t, today=None: date(2026, 7, 15))
    result = runner.invoke(app, ["stats", "summary"])
    data = json.loads(result.stdout)["data"]
    assert data["steps"] == 8000
    assert data["avg_spo2"] == 96
    assert data["avg_respiration"] == 14.0


def test_records(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["stats", "records"])
    assert json.loads(result.stdout)["data"][0]["typeId"] == 1


def test_progress(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(
        dates,
        "parse_date",
        lambda t, today=None: date(2026, 7, 1) if t == "2026-07-01" else date(2026, 7, 15),
    )
    result = runner.invoke(app, ["stats", "progress", "2026-07-01", "today"])
    data = json.loads(result.stdout)["data"]
    assert data["start"] == "2026-07-01"


# ── weekly ─────────────────────────────────────────────────────────────────


def test_weekly_defaults_to_today(monkeypatch):
    """stats weekly with no argument uses 'today'."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(dates, "parse_date", lambda t, today=None: date(2026, 7, 15))
    result = runner.invoke(app, ["stats", "weekly"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    # Week total: 10 + 5 + 1 = 16 mi
    assert data["week_total_mi"] == 16.0
    assert data["run_count"] == 3
    assert data["longest_run_mi"] == 10.0
    # Total duration: 3600 + 1800 + 600 = 6000 s → 1.7 h
    assert data["total_duration_hours"] == 1.7
    assert data["avg_daily_mi"] == pytest.approx(16.0 / 7, abs=0.01)
    # Previous week: 2.0 mi
    assert data["previous_week_mi"] == 2.0
    # 4-week window: this week (3 runs / 16 mi) + prev week (1 run / 2 mi)
    # + 2 older runs (3 + 4 = 7 mi) = 25 mi → avg 6.25
    assert data["four_week_avg_mi"] == 6.25


def test_weekly_includes_window(monkeypatch):
    """The response includes a window object with start/end dates."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(dates, "parse_date", lambda t, today=None: date(2026, 7, 15))
    result = runner.invoke(app, ["stats", "weekly"])
    data = json.loads(result.stdout)["data"]
    assert data["window"]["start"] == "2026-07-09"
    assert data["window"]["end"] == "2026-07-15"


def test_weekly_with_explicit_date(monkeypatch):
    """stats weekly with an explicit ISO date uses that as the window end."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(
        dates,
        "parse_date",
        lambda t, today=None: date(2026, 8, 1),
    )
    result = runner.invoke(app, ["stats", "weekly", "2026-08-01"])
    data = json.loads(result.stdout)["data"]
    # Window: 2026-07-26 – 2026-08-01.  No runs in this window.
    assert data["week_total_mi"] == 0
    assert data["run_count"] == 0
    assert data["longest_run_mi"] == 0.0
    assert data["total_duration_hours"] == 0.0
    assert data["avg_daily_mi"] == 0.0


def test_weekly_respects_full_flag(monkeypatch):
    """--full returns the raw dict unchanged (no projection)."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(dates, "parse_date", lambda t, today=None: date(2026, 7, 15))
    result = runner.invoke(app, ["--full", "stats", "weekly"])
    data = json.loads(result.stdout)["data"]
    # Same keys because project_weekly_volume is a passthrough.
    assert data["week_total_mi"] == 16.0
