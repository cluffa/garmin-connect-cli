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

    def get_sleep_data(self, cdate):
        return {"dailySleepDTO": {"sleepTimeSeconds": 28800}, "cdate": cdate}

    def get_body_battery(self, start, end):
        return [{"start": start, "end": end}]

    def get_hrv_data(self, cdate):
        return {"cdate": cdate, "weeklyAvg": 42}

    def get_stress_data(self, cdate):
        return {"cdate": cdate, "avgStressLevel": 27}

    def get_weigh_ins(self, start, end):
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


def test_sleep_projected(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "sleep", "2026-07-15"])
    assert result.exit_code == 0
    # 28800s / 3600 == 8h, exercising the sleep projection wiring.
    assert json.loads(result.stdout)["data"]["duration_hours"] == 8.0


def test_body_battery_range(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "body-battery", "2026-07-08:2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data[0] == {"start": "2026-07-08", "end": "2026-07-15"}


def test_hrv_for_date(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "hrv", "2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data["cdate"] == "2026-07-15"
    assert data["weeklyAvg"] == 42


def test_stress_for_date(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "stress", "2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data["cdate"] == "2026-07-15"
    assert data["avgStressLevel"] == 27


def test_weight_range(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "weight", "2026-07-08:2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data[0] == {"start": "2026-07-08", "end": "2026-07-15"}
