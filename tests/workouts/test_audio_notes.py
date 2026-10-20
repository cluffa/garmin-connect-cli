"""Tests for garmin_cli.workouts.audio_notes against a fake connectapi client."""

import copy

import pytest

from garmin_cli.output import UsageError
from garmin_cli.workouts import audio_notes


def _step(order, **extra):
    step = {
        "stepOrder": order,
        "type": "ExecutableStepDTO",
        "stepAudioNote": None,
        "stepAudioNoteUuid": None,
    }
    step.update(extra)
    return step


def make_workout():
    """A workout DTO: warmup, a repeat group with two children, cooldown."""
    return {
        "workoutId": 42,
        "workoutName": "Notes Test",
        "workoutAudioNote": None,
        "workoutAudioNoteUuid": None,
        "workoutSegments": [
            {
                "segmentOrder": 1,
                "workoutSteps": [
                    _step(1),
                    {
                        "stepOrder": 2,
                        "type": "RepeatGroupDTO",
                        "numberOfIterations": 2,
                        "workoutSteps": [_step(3), _step(4)],
                    },
                    _step(5),
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
    """Records calls and serves a mutable copy of the workout fixture."""

    def __init__(self, workout):
        self.workout = workout
        self.posts = []
        self.puts = []
        self.deletes = []
        self._uploads = 0

    def post(self, domain, path, files=None, api=False):
        assert domain == "connectapi"
        assert api is True
        self._uploads += 1
        uuid = f"uuid-{self._uploads}"
        self.posts.append((path, files["file"][0]))
        return {
            "audioNoteUuid": uuid,
            "audioNoteUrl": f"https://example.test/{uuid}.mp3",
            "expirationTimestamp": 999,
        }

    def request(self, method, domain, path, params=None):
        assert method == "GET"
        assert domain == "connectapi"
        assert params == {"includeAudioNotes": "true"}
        return FakeResponse(copy.deepcopy(self.workout))

    def put(self, domain, path, json=None, api=False):
        assert domain == "connectapi"
        self.puts.append(copy.deepcopy(json))
        self.workout = copy.deepcopy(json)
        return {}

    def delete(self, domain, path, params=None):
        assert domain == "connectapi"
        self.deletes.append((path, params))
        return None


@pytest.fixture()
def mp3(tmp_path):
    path = tmp_path / "cue.mp3"
    path.write_bytes(b"fake-mp3-bytes")
    return path


@pytest.fixture()
def api():
    return FakeApi(make_workout())


def test_add_note_to_flat_step(api, mp3):
    result = audio_notes.add_note(api, 42, mp3, step_order=1)
    assert result["audioNoteUuid"] == "uuid-1"
    assert result["stepOrder"] == 1
    assert api.posts[0][0] == "workout-service/workout/audionote/upload"
    assert api.posts[0][1] == "cue.mp3"
    step = audio_notes.find_step(api.workout, 1)
    assert step["stepAudioNoteUuid"] == "uuid-1"
    assert step["stepAudioNote"]["audioNoteUuid"] == "uuid-1"
    # exactly one PUT, carrying the mutated workout
    assert len(api.puts) == 1
    assert audio_notes.find_step(api.puts[0], 1)["stepAudioNoteUuid"] == "uuid-1"


def test_add_note_to_nested_step(api, mp3):
    result = audio_notes.add_note(api, 42, mp3, step_order=3)
    assert result["stepOrder"] == 3
    group = audio_notes.find_step(api.workout, 2)
    assert group["type"] == "RepeatGroupDTO"
    child = group["workoutSteps"][0]
    assert child["stepOrder"] == 3
    assert child["stepAudioNoteUuid"] == "uuid-1"
    # siblings untouched
    assert audio_notes.find_step(api.workout, 4)["stepAudioNoteUuid"] is None


def test_add_note_to_workout(api, mp3):
    result = audio_notes.add_note(api, 42, mp3)
    assert result["workout"] is True
    assert result["audioNoteUuid"] == "uuid-1"
    assert api.workout["workoutAudioNoteUuid"] == "uuid-1"
    assert api.workout["workoutAudioNote"]["audioNoteUuid"] == "uuid-1"


def test_add_note_replacing_deletes_old_upload(api, mp3):
    step = audio_notes.find_step(api.workout, 5)
    step["stepAudioNote"] = {"audioNoteUuid": "old-uuid"}
    step["stepAudioNoteUuid"] = "old-uuid"
    audio_notes.add_note(api, 42, mp3, step_order=5)
    # the fake stores a copy on PUT, so re-read from its current state
    step = audio_notes.find_step(api.workout, 5)
    assert step["stepAudioNoteUuid"] == "uuid-1"
    assert api.deletes == [
        ("workout-service/workout/audionote", {"audiouuid": "old-uuid"})
    ]


def test_add_note_missing_step(api, mp3):
    with pytest.raises(UsageError, match="stepOrder 99"):
        audio_notes.add_note(api, 42, mp3, step_order=99)


def test_add_note_missing_file(api, tmp_path):
    with pytest.raises(UsageError, match="not found"):
        audio_notes.add_note(api, 42, tmp_path / "nope.mp3", step_order=1)
    assert api.posts == []  # nothing uploaded


def test_list_notes(api):
    api.workout["workoutAudioNoteUuid"] = "workout-uuid"
    audio_notes.find_step(api.workout, 4)["stepAudioNoteUuid"] = "step-uuid"
    out = audio_notes.list_notes(api, 42)
    assert out == {
        "workoutId": 42,
        "workoutAudioNoteUuid": "workout-uuid",
        "steps": [{"stepOrder": 4, "audioNoteUuid": "step-uuid"}],
    }


def test_list_notes_empty(api):
    out = audio_notes.list_notes(api, 42)
    assert out["workoutAudioNoteUuid"] is None
    assert out["steps"] == []


def test_remove_step_note(api):
    step = audio_notes.find_step(api.workout, 1)
    step["stepAudioNote"] = {"audioNoteUuid": "uuid-x"}
    step["stepAudioNoteUuid"] = "uuid-x"
    result = audio_notes.remove_note(api, 42, step_order=1)
    assert result["removedAudioNoteUuid"] == "uuid-x"
    assert result["stepOrder"] == 1
    step = audio_notes.find_step(api.workout, 1)
    assert step["stepAudioNote"] is None
    assert step["stepAudioNoteUuid"] is None
    assert api.deletes == [
        ("workout-service/workout/audionote", {"audiouuid": "uuid-x"})
    ]
    # the PUT that cleared the reference happened before the delete
    assert len(api.puts) == 1
    cleared = audio_notes.find_step(api.puts[0], 1)
    assert cleared["stepAudioNoteUuid"] is None


def test_remove_workout_note(api):
    api.workout["workoutAudioNote"] = {"audioNoteUuid": "uuid-w"}
    api.workout["workoutAudioNoteUuid"] = "uuid-w"
    result = audio_notes.remove_note(api, 42)
    assert result["removedAudioNoteUuid"] == "uuid-w"
    assert result["workout"] is True
    assert api.workout["workoutAudioNoteUuid"] is None
    assert api.deletes == [
        ("workout-service/workout/audionote", {"audiouuid": "uuid-w"})
    ]


def test_remove_missing_note_is_usage_error(api):
    with pytest.raises(UsageError, match="no audio note"):
        audio_notes.remove_note(api, 42, step_order=1)
    assert api.puts == []
    assert api.deletes == []


def test_remove_missing_step_is_usage_error(api):
    with pytest.raises(UsageError, match="stepOrder 99"):
        audio_notes.remove_note(api, 42, step_order=99)
