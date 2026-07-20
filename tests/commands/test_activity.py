"""Tests for the activity command group."""

import json
import os

from typer.testing import CliRunner

from garmin_cli import client
from garmin_cli.cli import app

runner = CliRunner()

ACT = {"activityId": 1, "activityName": "Run", "distance": 5000.0, "ownerId": 9}

ACT_WITH_SPLITS = {
    "activityId": 42,
    "activityName": "Track Workout",
    "summaryDTO": {
        "startTimeLocal": "2026-07-16T10:00:00",
        "distance": 8046.7,
        "duration": 2700.0,
        "averageHR": 145,
        "maxHR": 170,
    },
    "splitSummaries": [
        {
            "distance": 1609.34,
            "duration": 540.0,
            "averageHR": 130,
            "maxHR": 140,
            "splitType": "INTERVAL_WARMUP",
            "averageRunCadence": 155.0,
        },
        {
            "distance": 4828.02,
            "duration": 1560.0,
            "averageHR": 160,
            "maxHR": 173,
            "splitType": "INTERVAL_ACTIVE",
            "averageRunCadence": 162.0,
            "strideLength": 1.24,
            "verticalOscillation": 9.5,
        },
        {
            "distance": 1609.34,
            "duration": 600.0,
            "averageHR": 135,
            "maxHR": 142,
            "splitType": "INTERVAL_COOLDOWN",
            "averageRunCadence": 152.0,
        },
    ],
}


LAP_DTOS = [
    {
        "distance": 1609.34,
        "duration": 540.0,
        "movingDuration": 538.0,
        "averageHR": 130.0,
        "maxHR": 140.0,
        "averageRunCadence": 155.0,
        "intensityType": "WARMUP",
        "calories": 120.0,
        "strideLength": 1.05,
        "verticalOscillation": 8.5,
        "averagePower": 320.0,
        "normalizedPower": 325.0,
        "groundContactTime": 290.0,
        "startTimeGMT": "2026-07-16T14:00:00.0",
    },
    {
        "distance": 4828.02,
        "duration": 1560.0,
        "movingDuration": 1550.0,
        "averageHR": 160.0,
        "maxHR": 173.0,
        "averageRunCadence": 162.0,
        "intensityType": "ACTIVE",
        "calories": 350.0,
        "strideLength": 1.24,
        "verticalOscillation": 9.5,
        "averagePower": 350.0,
        "normalizedPower": 358.0,
        "groundContactTime": 285.0,
        "startTimeGMT": "2026-07-16T14:10:00.0",
    },
    {
        "distance": 1609.34,
        "duration": 600.0,
        "movingDuration": 592.0,
        "averageHR": 135.0,
        "maxHR": 142.0,
        "averageRunCadence": 152.0,
        "intensityType": "COOLDOWN",
        "calories": 100.0,
        "startTimeGMT": "2026-07-16T14:36:00.0",
    },
]


class FakeClient:
    def get_activities(self, start=0, limit=20, activitytype=None):
        return [ACT]

    def get_activity(self, activity_id):
        if int(activity_id) == 42:
            return ACT_WITH_SPLITS
        return ACT

    def get_activity_splits(self, activity_id):
        return {"activityId": int(activity_id), "lapDTOs": LAP_DTOS}

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


def test_list_miles_adds_pace_and_distance_mi(monkeypatch):
    """--miles computes distance_mi and pace_per_mi in slim projection."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "list", "--miles"])
    data = json.loads(result.stdout)["data"]
    assert "distance_mi" in data[0]
    assert "pace_per_mi" in data[0]


def test_list_miles_short_flag(monkeypatch):
    """-m is a valid short alias for --miles."""
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "list", "-m"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert "distance_mi" in data[0]


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


# ── splits ────────────────────────────────────────────────────────────────


def test_splits_projects_correct_keys(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "splits", "42"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert "splits" in data
    assert data["total_distance_mi"] == 5.0
    assert "total_duration_sec" in data
    assert data["lap_count"] == 3
    assert len(data["splits"]) == 3

    split0 = data["splits"][0]
    assert "distance_mi" in split0
    assert "duration_min" in split0
    assert "pace_per_mi" in split0
    assert "lap_type" in split0


def test_splits_split_type_labels(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "splits", "42"])
    data = json.loads(result.stdout)["data"]
    labels = [s["lap_type"] for s in data["splits"]]
    assert labels == ["Warmup", "Active", "Cooldown"]


def test_splits_pace_format(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "splits", "42"])
    data = json.loads(result.stdout)["data"]
    # Warmup: 540s / 60 = 9.0 min, 1609.34m / 1609.34 = 1.0 mi → 9:00/mi
    assert data["splits"][0]["pace_per_mi"] == "9:00"
    # Active: 1560s / 60 = 26.0 min, 4828.02m / 1609.34 = 3.0 mi → 8:40/mi
    assert data["splits"][1]["pace_per_mi"] == "8:40"


def test_splits_optional_fields_present(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "splits", "42"])
    data = json.loads(result.stdout)["data"]
    split1 = data["splits"][1]
    assert split1["stride_length"] == 1.24
    assert split1["vertical_oscillation"] == 9.5
    assert split1["avg_power"] == 350.0
    assert split1["normalized_power"] == 358.0
    split0 = data["splits"][0]
    assert "stride_length" in split0  # LAP_DTOS[0] has strideLength


def test_splits_full_returns_raw(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["--full", "activity", "splits", "42"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert data["activityId"] == 42
    assert data["lapDTOs"][0]["intensityType"] == "WARMUP"


def test_splits_toon_format(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["--format", "toon", "activity", "splits", "42"])
    assert result.exit_code == 0
    assert "Warmup" in result.stdout
    assert "Active" in result.stdout
    assert "Cooldown" in result.stdout


def test_activity_group_help_shows_commands():
    result = runner.invoke(app, ["activity", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "get" in result.stdout
    assert "download" in result.stdout
    assert "splits" in result.stdout
