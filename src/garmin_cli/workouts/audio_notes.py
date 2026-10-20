"""Audio notes for saved workouts.

Garmin Connect supports short spoken notes (MP3, up to 15 seconds) attached
to a workout as a whole or to an individual step; a music-capable watch
plays them through paired headphones as the step begins.  The
``garminconnect`` library exposes none of this, so the functions here drive
the underlying connectapi client (``garmin.client``) directly:

- upload: ``POST workout-service/workout/audionote/upload`` (multipart,
  field ``file``) -> ``{"audioNoteUuid", "audioNoteUrl", ...}``
- attach: fetch the workout with ``includeAudioNotes=true``, set
  ``stepAudioNote``/``stepAudioNoteUuid`` on the target step (or
  ``workoutAudioNote``/``workoutAudioNoteUuid`` on the workout), then PUT
  the whole workout back.
- remove: clear those fields, PUT, then
  ``DELETE workout-service/workout/audionote?audiouuid=<uuid>``.

Every function takes *api* — the raw client — so tests can substitute a
fake without touching auth.
"""

from __future__ import annotations

from pathlib import Path

from garmin_cli.output import ApiError, UsageError

_UPLOAD_PATH = "workout-service/workout/audionote/upload"
_DELETE_PATH = "workout-service/workout/audionote"


def _workout_path(workout_id) -> str:
    return f"workout-service/workout/{workout_id}"


def get_workout(api, workout_id) -> dict:
    """Fetch a workout with its audio-note metadata included."""
    resp = api.request(
        "GET",
        "connectapi",
        _workout_path(workout_id),
        params={"includeAudioNotes": "true"},
    )
    return resp.json()


def upload_note(api, file_path) -> dict:
    """Upload an MP3 and return Garmin's audio-note metadata for it."""
    path = Path(file_path)
    if not path.is_file():
        raise UsageError(f"audio file not found: {file_path}")
    with path.open("rb") as fh:
        meta = api.post(
            "connectapi",
            _UPLOAD_PATH,
            files={"file": (path.name, fh, "audio/mpeg")},
            api=True,
        )
    if not isinstance(meta, dict) or not meta.get("audioNoteUuid"):
        raise ApiError(f"unexpected audio-note upload response: {meta!r}")
    return meta


def _walk_steps(steps):
    for step in steps or []:
        yield step
        yield from _walk_steps(step.get("workoutSteps"))


def iter_steps(workout):
    """Yield every step in *workout*, descending into repeat groups."""
    for segment in workout.get("workoutSegments") or []:
        yield from _walk_steps(segment.get("workoutSteps"))


def find_step(workout, step_order: int):
    """Return the step whose ``stepOrder`` matches, or ``None``.

    Steps nest: a repeat group is itself a step whose ``workoutSteps``
    hold the children, so the search is recursive.
    """
    for step in iter_steps(workout):
        if step.get("stepOrder") == step_order:
            return step
    return None


def describe_notes(workout) -> dict:
    """Summarize which parts of *workout* carry audio notes."""
    steps = [
        {
            "stepOrder": step.get("stepOrder"),
            "audioNoteUuid": step["stepAudioNoteUuid"],
        }
        for step in iter_steps(workout)
        if step.get("stepAudioNoteUuid")
    ]
    return {
        "workoutId": workout.get("workoutId"),
        "workoutAudioNoteUuid": workout.get("workoutAudioNoteUuid"),
        "steps": steps,
    }


def list_notes(api, workout_id) -> dict:
    """Fetch *workout_id* and describe its audio notes."""
    return describe_notes(get_workout(api, workout_id))


def _delete_note(api, uuid: str) -> None:
    api.delete("connectapi", _DELETE_PATH, params={"audiouuid": uuid})


def add_note(api, workout_id, file_path, step_order: int | None = None) -> dict:
    """Upload *file_path* and attach it to a step or the whole workout.

    With ``step_order=None`` the note attaches to the workout itself.
    Replacing an existing note deletes the old upload afterwards, since
    Garmin leaves replaced uploads orphaned otherwise.
    """
    meta = upload_note(api, file_path)
    uuid = meta["audioNoteUuid"]
    workout = get_workout(api, workout_id)
    if step_order is None:
        holder, fields, target = (
            workout,
            ("workoutAudioNote", "workoutAudioNoteUuid"),
            {"workout": True},
        )
    else:
        holder = find_step(workout, step_order)
        if holder is None:
            raise UsageError(
                f"workout {workout_id} has no step with stepOrder {step_order}"
            )
        fields = ("stepAudioNote", "stepAudioNoteUuid")
        target = {"stepOrder": step_order}
    old_uuid = holder.get(fields[1])
    holder[fields[0]] = meta
    holder[fields[1]] = uuid
    api.put("connectapi", _workout_path(workout_id), json=workout, api=True)
    if old_uuid and old_uuid != uuid:
        _delete_note(api, old_uuid)
    return {
        "workoutId": workout.get("workoutId", workout_id),
        **target,
        "audioNoteUuid": uuid,
        "audioNoteUrl": meta.get("audioNoteUrl"),
    }


def remove_note(api, workout_id, step_order: int | None = None) -> dict:
    """Detach the audio note from a step (or the workout) and delete it.

    The reference is cleared and saved first, so a failed upload delete
    never leaves the workout pointing at a note that no longer exists.
    """
    workout = get_workout(api, workout_id)
    if step_order is None:
        holder, fields, target = (
            workout,
            ("workoutAudioNote", "workoutAudioNoteUuid"),
            {"workout": True},
        )
        missing = f"workout {workout_id} has no workout-level audio note"
    else:
        holder = find_step(workout, step_order)
        if holder is None:
            raise UsageError(
                f"workout {workout_id} has no step with stepOrder {step_order}"
            )
        fields = ("stepAudioNote", "stepAudioNoteUuid")
        target = {"stepOrder": step_order}
        missing = (
            f"step {step_order} of workout {workout_id} has no audio note"
        )
    uuid = holder.get(fields[1])
    if not uuid:
        raise UsageError(missing)
    holder[fields[0]] = None
    holder[fields[1]] = None
    api.put("connectapi", _workout_path(workout_id), json=workout, api=True)
    _delete_note(api, uuid)
    return {
        "workoutId": workout.get("workoutId", workout_id),
        **target,
        "removedAudioNoteUuid": uuid,
    }
