"""Tests for the stats command group."""

import json
from datetime import date

from typer.testing import CliRunner

from garmin_cli import client, dates, state
from garmin_cli.cli import app

runner = CliRunner()


class FakeClient:
    def get_user_summary(self, cdate):
        return {"cdate": cdate, "totalSteps": 8000}

    def get_personal_record(self):
        return [{"typeId": 1}]

    def get_progress_summary_between_dates(self, start, end, metric="distance", groupbyactivities=True):
        return {"start": start, "end": end}


def setup_function():
    state.fmt = "json"


def test_summary(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(dates, "parse_date", lambda t, today=None: date(2026, 7, 15))
    result = runner.invoke(app, ["stats", "summary"])
    data = json.loads(result.stdout)["data"]
    assert data["steps"] == 8000


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
