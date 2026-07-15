"""Tests for the health command group."""

import json
from datetime import date

from typer.testing import CliRunner

from garmin_cli import client, dates
from garmin_cli.cli import app

runner = CliRunner()


class FakeClient:
    def get_heart_rates(self, cdate):
        return {"cdate": cdate, "resting": 48}

    def get_daily_steps(self, start, end):
        return [{"start": start, "end": end}]


def test_heart_rate_default_today(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(dates, "parse_date", lambda t, today=None: date(2026, 7, 15))
    result = runner.invoke(app, ["health", "heart-rate"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"]["resting"] == 48


def test_steps_range(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(
        dates,
        "parse_range",
        lambda t, today=None: (date(2026, 7, 8), date(2026, 7, 15)),
    )
    result = runner.invoke(app, ["health", "steps", "2026-07-08:2026-07-15"])
    data = json.loads(result.stdout)["data"]
    assert data[0]["start"] == "2026-07-08"
