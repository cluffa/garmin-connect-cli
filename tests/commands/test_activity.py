"""Tests for the activity command group."""

import json
import os

from typer.testing import CliRunner

from garmin_cli import client
from garmin_cli.cli import app

runner = CliRunner()

ACT = {"activityId": 1, "activityName": "Run", "distance": 5000.0, "ownerId": 9}


class FakeClient:
    def get_activities(self, start=0, limit=20, activitytype=None):
        return [ACT]

    def get_activity(self, activity_id):
        return ACT

    def download_activity(self, activity_id, fmt):
        return b"fake-garmin-data"



# ── list ──────────────────────────────────────────────────────────────────


def test_list_is_slim(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "list"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert "ownerId" not in data[0]


def test_list_full(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["--full", "activity", "list"])
    data = json.loads(result.stdout)["data"]
    assert data[0]["ownerId"] == 9


def test_list_with_limit(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "list", "--limit", "5"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert len(data) == 1


def test_list_with_start(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "list", "--start", "10"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["ok"] is True


# ── get ───────────────────────────────────────────────────────────────────


def test_get_is_slim(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "get", "1"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data["activityId"] == 1
    assert "ownerId" not in data


def test_get_full(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["--full", "activity", "get", "1"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data["ownerId"] == 9


# ── download ──────────────────────────────────────────────────────────────


def test_download_tcx(monkeypatch, tmp_path):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["activity", "download", "1", "--format-file", "tcx"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data["bytes"] == len(b"fake-garmin-data")
    assert os.path.isfile("activity_1.tcx")


def test_download_with_out(monkeypatch, tmp_path):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, [
        "activity", "download", "1", "--format-file", "gpx", "--out", "custom.gpx",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data["path"] == "custom.gpx"
    assert os.path.isfile("custom.gpx")


def test_download_invalid_format(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "download", "1", "--format-file", "csv"])
    assert result.exit_code == 2
    err = json.loads(result.stderr)
    assert err["error"]["type"] == "usage"


def test_download_rejects_path_traversal(monkeypatch, tmp_path):
    """A traversal-laden activity id must not derive an out-of-cwd path."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["activity", "download", "../../etc/passwd"])
    assert result.exit_code == 2
    assert json.loads(result.stderr)["error"]["type"] == "usage"
    assert not os.path.exists(tmp_path.parent.parent / "etc" / "passwd.tcx")


def test_download_traversal_id_allowed_with_explicit_out(monkeypatch, tmp_path):
    """An explicit --out bypasses the id-derived filename guard."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(
        app, ["activity", "download", "../weird", "--out", "safe.tcx"]
    )
    assert result.exit_code == 0
    assert os.path.isfile("safe.tcx")


# ── help ──────────────────────────────────────────────────────────────────


def test_activity_group_help_shows_commands():
    result = runner.invoke(app, ["activity", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "get" in result.stdout
    assert "download" in result.stdout
