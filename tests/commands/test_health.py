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

    def get_weekly_steps(self, end, weeks):
        return [{"end": end, "weeks": weeks, "totalSteps": 70000}]

    def get_weekly_stress(self, end, weeks):
        return [{"end": end, "weeks": weeks, "value": 31}]


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


# ── Range support on single-date-upstream endpoints ────────────


def test_hrv_range_returns_one_entry_per_day(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "hrv", "2026-07-13:2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert [e["date"] for e in data] == ["2026-07-13", "2026-07-14", "2026-07-15"]
    assert data[0]["data"]["weeklyAvg"] == 42


def test_sleep_range_projects_each_day(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "sleep", "2026-07-14:2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert len(data) == 2
    assert data[0]["data"]["duration_hours"] == 8.0


def test_stress_range(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "stress", "2026-07-14:2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert [e["data"]["avgStressLevel"] for e in data] == [27, 27]


def test_heart_rate_range(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "heart-rate", "2026-07-14:2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert [e["data"]["resting"] for e in data] == [48, 48]


def test_range_authenticates_once_not_once_per_day(monkeypatch):
    """A 30-day range must not re-login 30 times."""
    calls = {"n": 0}

    def counting_load_client():
        calls["n"] += 1
        return FakeClient()

    monkeypatch.setattr(client, "load_client", counting_load_client)
    result = runner.invoke(app, ["health", "hrv", "2026-07-01:2026-07-30"])
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)["data"]) == 30
    assert calls["n"] == 1


def test_range_over_limit_exits_usage_error(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(
        app, ["health", "hrv", "2026-01-01:2026-07-15", "--max-days", "10"]
    )
    assert result.exit_code == 2
    err = json.loads(result.stderr)
    assert err["ok"] is False
    assert err["error"]["type"] == "usage"


def test_hrv_single_date_shape_is_unchanged(monkeypatch):
    """Adding ranges must not change what a bare date returns."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "hrv", "2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert isinstance(data, dict)
    assert data["weeklyAvg"] == 42


# ── Natively range-capable weekly aggregates ───────────────────


def test_weekly_steps(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "weekly-steps", "2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data[0]["weeks"] == 52
    assert data[0]["totalSteps"] == 70000


def test_weekly_steps_custom_weeks(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(
        app, ["health", "weekly-steps", "2026-07-15", "--weeks", "12"]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"][0]["weeks"] == 12


def test_weekly_stress(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["health", "weekly-stress", "2026-07-15"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data[0]["value"] == 31
    assert data[0]["end"] == "2026-07-15"
