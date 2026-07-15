"""Tests for the workout command group."""

import json

from typer.testing import CliRunner

from garmin_cli import client, state
from garmin_cli.cli import app

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
