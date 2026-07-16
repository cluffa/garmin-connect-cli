"""Tests for the badge command group."""

import json

from typer.testing import CliRunner

from garmin_cli import client
from garmin_cli.cli import app

runner = CliRunner()


class FakeClient:
    def get_earned_badges(self):
        return [
            {"badgeName": "old", "badgeEarnedDate": "2026-01-01"},
            {"badgeName": "new", "badgeEarnedDate": "2026-07-01"},
            {"badgeName": "mid", "badgeEarnedDate": "2026-04-01"},
        ]

    def get_in_progress_badges(self):
        return [{"badgeName": "wip"}]

    def get_available_badge_challenges(self, start, limit):
        return [{"start": start, "limit": limit}]

    def get_adhoc_challenges(self, start, limit):
        return [{"start": start, "limit": limit}]

    def get_badge_challenges(self, start, limit):
        return [{"start": start, "limit": limit}]


def test_earned_sorted_newest_first(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["badge", "earned"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert [b["badgeName"] for b in data] == ["new", "mid", "old"]


def test_earned_respects_limit(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["badge", "earned", "--limit", "2"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert [b["badgeName"] for b in data] == ["new", "mid"]


def test_in_progress(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["badge", "in-progress"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data[0]["badgeName"] == "wip"


def test_available_passes_pagination(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["badge", "available", "--start", "3", "--limit", "5"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data[0] == {"start": 3, "limit": 5}


def test_adhoc_defaults(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["badge", "adhoc"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data[0] == {"start": 1, "limit": 20}


def test_challenges_defaults(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["badge", "challenges"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data[0] == {"start": 1, "limit": 20}
