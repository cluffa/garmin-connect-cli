"""Tests for the `workout audio-note` command group."""

import copy
import json

import pytest
from typer.testing import CliRunner

from garmin_cli import client
from garmin_cli.cli import app

runner = CliRunner()


def make_workout():
    return {
        "workoutId": 42,
        "workoutName": "Notes Test",
        "workoutAudioNote": None,
        "workoutAudioNoteUuid": None,
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "workoutSteps": [
                    {
                        "stepOrder": 1,
                        "type": "ExecutableStepDTO",
                        "stepAudioNote": None,
                        "stepAudioNoteUuid": None,
                    },
                    {
                        "stepOrder": 2,
                        "type": "ExecutableStepDTO",
                        "stepAudioNote": None,
                        "stepAudioNoteUuid": None,
                    },
                ],
            }
        ],
    }


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeApi:
    def __init__(self, workout):
        self.workout = workout
        self.deletes = []

    def post(self, domain, path, files=None, api=False):
        return {
            "audioNoteUuid": "uuid-1",
            "audioNoteUrl": "https://example.test/uuid-1.mp3",
            "expirationTimestamp": 999,
        }

    def request(self, method, domain, path, params=None):
        return FakeResponse(copy.deepcopy(self.workout))

    def put(self, domain, path, json=None, api=False):
        self.workout = copy.deepcopy(json)
        return {}

    def delete(self, domain, path, params=None):
        self.deletes.append((path, params))
        return None


class FakeGarmin:
    """Stands in for the garminconnect Garmin object (commands use .client)."""

    def __init__(self, workout):
        self.client = FakeApi(workout)


@pytest.fixture()
def mp3(tmp_path):
    path = tmp_path / "cue.mp3"
    path.write_bytes(b"fake-mp3-bytes")
    return path


@pytest.fixture()
def fake(monkeypatch):
    garmin = FakeGarmin(make_workout())
    monkeypatch.setattr(client, "load_client", lambda: garmin)
    return garmin


def test_add_to_step(fake, mp3):
    result = runner.invoke(
        app,
        ["workout", "audio-note", "add", "42", "--file", str(mp3), "--step", "2"],
    )
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["data"]["audioNoteUuid"] == "uuid-1"
    assert out["data"]["stepOrder"] == 2
    step = fake.client.workout["workoutSegments"][0]["workoutSteps"][1]
    assert step["stepAudioNoteUuid"] == "uuid-1"


def test_add_to_workout(fake, mp3):
    result = runner.invoke(
        app,
        ["workout", "audio-note", "add", "42", "--file", str(mp3), "--workout"],
    )
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["data"]["workout"] is True
    assert fake.client.workout["workoutAudioNoteUuid"] == "uuid-1"


def test_add_requires_exactly_one_target(fake, mp3):
    neither = runner.invoke(
        app, ["workout", "audio-note", "add", "42", "--file", str(mp3)]
    )
    assert neither.exit_code == 2
    assert json.loads(neither.stderr)["error"]["type"] == "usage"

    both = runner.invoke(
        app,
        [
            "workout", "audio-note", "add", "42",
            "--file", str(mp3), "--step", "1", "--workout",
        ],
    )
    assert both.exit_code == 2
    assert json.loads(both.stderr)["error"]["type"] == "usage"


def test_add_missing_file_yields_usage_envelope(fake, tmp_path):
    result = runner.invoke(
        app,
        [
            "workout", "audio-note", "add", "42",
            "--file", str(tmp_path / "nope.mp3"), "--step", "1",
        ],
    )
    assert result.exit_code == 2
    err = json.loads(result.stderr)
    assert err["error"]["type"] == "usage"
    assert "Traceback" not in result.stderr


def test_list(fake):
    fake.client.workout["workoutSegments"][0]["workoutSteps"][0][
        "stepAudioNoteUuid"
    ] = "uuid-9"
    result = runner.invoke(app, ["workout", "audio-note", "list", "42"])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["data"]["workoutAudioNoteUuid"] is None
    assert out["data"]["steps"] == [
        {"stepOrder": 1, "audioNoteUuid": "uuid-9"}
    ]


def test_remove_from_step(fake):
    step = fake.client.workout["workoutSegments"][0]["workoutSteps"][0]
    step["stepAudioNote"] = {"audioNoteUuid": "uuid-7"}
    step["stepAudioNoteUuid"] = "uuid-7"
    result = runner.invoke(
        app, ["workout", "audio-note", "remove", "42", "--step", "1"]
    )
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["data"]["removedAudioNoteUuid"] == "uuid-7"
    # the fake stores a copy on PUT, so re-read from its current state
    step = fake.client.workout["workoutSegments"][0]["workoutSteps"][0]
    assert step["stepAudioNoteUuid"] is None
    assert fake.client.deletes == [
        ("workout-service/workout/audionote", {"audiouuid": "uuid-7"})
    ]
