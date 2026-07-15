"""Tests for the workout command group."""

import json

import pytest
from typer.testing import CliRunner

from garmin_cli import client, state
from garmin_cli.cli import app
from garmin_cli.output import AuthError

runner = CliRunner()

PLAN = json.dumps(
    {
        "workouts": [
            {
                "name": "A",
                "sport": "running",
                "date": "2026-07-21",
                "steps": [
                    {"type": "warmup", "duration": {"time": "10min"}}
                ],
            },
            {
                "name": "B",
                "sport": "running",
                "steps": [
                    {"type": "cooldown", "duration": {"time": "5min"}}
                ],
            },
        ]
    }
)


class FakeClient:
    def __init__(self):
        self.uploaded = []
        self.scheduled = []

    def upload_workout(self, payload):
        wid = 100 + len(self.uploaded)
        self.uploaded.append(payload)
        return {"workoutId": wid}

    def schedule_workout(self, workout_id, date_str):
        self.scheduled.append((workout_id, date_str))
        return {"workoutScheduleId": 500 + len(self.scheduled)}

    def get_workouts(self, start=0, limit=100):
        return [{"workoutId": 1, "workoutName": "A"}]


def setup_function():
    state.fmt = "json"
    state.full = False


def test_validate_dry_run(monkeypatch):
    # validate must not touch the client at all
    monkeypatch.setattr(
        client,
        "load_client",
        lambda: (_ for _ in ()).throw(AssertionError()),
    )
    result = runner.invoke(app, ["workout", "validate", "--json", PLAN])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["data"]["results"][0]["estimatedDurationInSecs"] == 600
    assert out["data"]["created"] == 2  # both valid


def test_create_batch_schedules(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(client, "load_client", lambda: fake)
    result = runner.invoke(app, ["workout", "create", "--json", PLAN])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["data"]["created"] == 2
    assert out["data"]["results"][0]["scheduledId"] == 501
    assert fake.scheduled == [(100, "2026-07-21")]  # only A had a date


def test_create_partial_failure(monkeypatch):
    fake = FakeClient()

    def boom(payload):
        raise RuntimeError("garmin 500")

    fake.upload_workout = boom
    monkeypatch.setattr(client, "load_client", lambda: fake)
    result = runner.invoke(app, ["workout", "create", "--json", PLAN])
    assert result.exit_code == 4
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert out["data"]["failed"] == 2


def test_list(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["workout", "list"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"][0]["workoutName"] == "A"


def test_schema_command():
    result = runner.invoke(app, ["workout", "schema"])
    assert result.exit_code == 0
    assert "workouts" in json.loads(result.stdout)["data"]["properties"]


# ── regression: output-envelope contract ────────────────────────────


def test_create_malformed_json_yields_usage_envelope():
    """Malformed --json must produce a usage error envelope on stderr, exit 2."""
    result = runner.invoke(app, ["workout", "create", "--json", "{bad"])
    assert result.exit_code == 2
    err = json.loads(result.stderr)
    assert err == {
        "ok": False,
        "error": {"type": "usage", "message": "invalid JSON: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)"},
    }


def test_create_unauthenticated_yields_auth_envelope(monkeypatch):
    """AuthError during client load must produce an auth envelope on stderr, exit 3."""
    monkeypatch.setattr(
        client, "load_client", lambda: (_ for _ in ()).throw(AuthError("not authenticated"))
    )
    result = runner.invoke(app, ["workout", "create", "--json", PLAN])
    assert result.exit_code == 3
    err = json.loads(result.stderr)
    assert err == {
        "ok": False,
        "error": {"type": "auth", "message": "not authenticated"},
    }


def test_create_batch_invalid_target_continues_on_error(monkeypatch):
    """A per-item UsageError (e.g. pace on cycling) must not abort the batch.

    Valid workouts must still be created, the failed item reported with
    ``ok=False``, and the batch exits 4 (partial failure).
    """
    fake = FakeClient()
    monkeypatch.setattr(client, "load_client", lambda: fake)

    # Workout A is valid; Workout B has a pace target on a cycling sport
    plan_with_bad = json.dumps(
        {
            "workouts": [
                {"name": "A", "sport": "running", "steps": [
                    {"type": "warmup", "duration": {"time": "10min"}}
                ]},
                {"name": "B", "sport": "cycling", "steps": [
                    {"type": "interval", "duration": {"time": "5min"},
                     "target": {"pace": ["6:00/mi"]}}
                ]},
            ]
        }
    )

    result = runner.invoke(app, ["workout", "create", "--json", plan_with_bad])
    assert result.exit_code == 4
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert out["data"]["created"] == 1
    assert out["data"]["failed"] == 1
    # Workout A should have been created
    assert out["data"]["results"][0]["ok"] is True
    assert out["data"]["results"][0]["workoutId"] == 100
    # Workout B should have a usage error
    assert out["data"]["results"][1]["ok"] is False
    assert out["data"]["results"][1]["error"]["type"] == "usage"
