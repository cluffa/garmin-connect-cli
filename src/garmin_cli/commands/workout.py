"""Workout sub-commands: create, validate, list, get, delete, schedule,
unschedule, scheduled, schema, and the audio-note sub-group."""

from __future__ import annotations

import sys

import typer

from garmin_cli import client
from garmin_cli.dates import parse_date, parse_range
from garmin_cli.output import (
    CliError,
    InternalError,
    UsageError,
    command_output,
    emit_batch,
    emit_error,
)
from garmin_cli.workouts import audio_notes
from garmin_cli.workouts.schema import load_plan, spec_json_schema
from garmin_cli.workouts.translate import summarize, translate

workout_app = typer.Typer(
    help="Create and manage workouts.", no_args_is_help=True
)


def _read_spec(json_opt: str | None, file_opt: str | None) -> str:
    """Return a raw workout spec string from exactly one of ``--json``,
    ``--file``, or stdin.  Raises ``UsageError`` when the source is
    ambiguous or missing."""
    sources = [s for s in (json_opt, file_opt) if s is not None]
    if len(sources) > 1:
        raise UsageError("provide exactly one of --json or --file")
    if json_opt is not None:
        return json_opt
    if file_opt is not None:
        with open(file_opt) as fh:
            return fh.read()
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise UsageError("provide a spec via --json, --file, or stdin")


@workout_app.command()
def create(
    json_opt: str = typer.Option(None, "--json", help="Inline JSON spec."),
    file_opt: str = typer.Option(None, "--file", help="Path to JSON spec."),
):
    """Create (and schedule, if 'date' set) one or many workouts."""
    try:
        plan = load_plan(_read_spec(json_opt, file_opt))
        garmin = client.load_client()
    except CliError as e:
        emit_error(e)
    except OSError as e:
        emit_error(UsageError(str(e)))
    except Exception as e:  # noqa: BLE001 - no traceback should reach the user
        emit_error(InternalError(str(e)))
    results = []
    for i, spec in enumerate(plan.workouts):
        entry = {"index": i, "name": spec.name}
        try:
            payload = translate(spec).to_dict()
            created = garmin.upload_workout(payload)
            workout_id = (
                created.get("workoutId") if isinstance(created, dict) else None
            )
            entry.update(ok=True, workoutId=workout_id)
            if spec.date:
                date_str = parse_date(spec.date).isoformat()
                sched = garmin.schedule_workout(workout_id, date_str)
                entry["scheduledId"] = (
                    sched.get("workoutScheduleId")
                    if isinstance(sched, dict)
                    else None
                )
        except UsageError as e:
            entry.update(ok=False, error={"type": "usage", "message": e.message})
        except Exception as e:  # noqa: BLE001
            entry.update(ok=False, error={"type": "api", "message": str(e)})
        results.append(entry)
    emit_batch(results)


@workout_app.command()
def validate(
    json_opt: str = typer.Option(None, "--json"),
    file_opt: str = typer.Option(None, "--file"),
):
    """Validate + translate + estimate a spec without uploading."""
    try:
        plan = load_plan(_read_spec(json_opt, file_opt))
    except CliError as e:
        emit_error(e)
    except OSError as e:
        emit_error(UsageError(str(e)))
    except Exception as e:  # noqa: BLE001 - no traceback should reach the user
        emit_error(InternalError(str(e)))
    results = []
    for i, spec in enumerate(plan.workouts):
        entry = {"index": i}
        try:
            entry.update(ok=True, **summarize(spec))
        except Exception as e:  # noqa: BLE001
            entry.update(ok=False, error={"type": "usage", "message": str(e)})
        results.append(entry)
    emit_batch(results)


@workout_app.command(name="list")
@command_output
def list_():
    """List saved workouts."""
    return client.load_client().get_workouts()


@workout_app.command()
@command_output
def get(workout_id: str = typer.Argument(...)):
    """Get one workout by id."""
    return client.load_client().get_workout_by_id(workout_id)


@workout_app.command()
@command_output
def delete(workout_id: str = typer.Argument(...)):
    """Delete a workout."""
    client.load_client().delete_workout(workout_id)
    return {"deleted": workout_id}


@workout_app.command()
@command_output
def schedule(
    workout_id: str = typer.Argument(...),
    date_str: str = typer.Argument(...),
):
    """Schedule an existing workout onto a date."""
    resolved = parse_date(date_str).isoformat()
    return client.load_client().schedule_workout(workout_id, resolved)


@workout_app.command()
@command_output
def unschedule(scheduled_id: str = typer.Argument(...)):
    """Remove a scheduled workout from the calendar."""
    client.load_client().unschedule_workout(scheduled_id)
    return {"unscheduled": scheduled_id}


@workout_app.command()
@command_output
def scheduled(date_range: str = typer.Argument("today")):
    """List scheduled workouts over a date or range (iterates months)."""
    start, end = parse_range(date_range)
    garmin = client.load_client()
    seen = set()
    out = []
    cursor = start
    while cursor <= end:
        key = (cursor.year, cursor.month)
        if key not in seen:
            seen.add(key)
            out.append(
                garmin.get_scheduled_workouts(cursor.year, cursor.month)
            )
        # advance to first of next month
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1, day=1)
    return {"range": [start.isoformat(), end.isoformat()], "months": out}


@workout_app.command()
@command_output
def schema():
    """Emit the simplified workout JSON schema."""
    return spec_json_schema()


# ── audio notes ─────────────────────────────────────────────────────
# Spoken MP3 notes (max 15 s) attached to a workout or one of its steps.
# The garminconnect library has no support for them, so these commands go
# through garmin_cli.workouts.audio_notes on the raw connectapi client.

audio_note_app = typer.Typer(
    help="Manage spoken audio notes on workouts and steps.",
    no_args_is_help=True,
)
workout_app.add_typer(audio_note_app, name="audio-note")


def _resolve_step(step: int | None, workout_flag: bool) -> int | None:
    """Map the --step/--workout pair to a stepOrder (None = whole workout)."""
    if step is not None and workout_flag:
        raise UsageError("provide only one of --step or --workout")
    if step is None and not workout_flag:
        raise UsageError("specify a target: --step <stepOrder> or --workout")
    return step


@audio_note_app.command(name="add")
@command_output
def audio_note_add(
    workout_id: str = typer.Argument(...),
    file_opt: str = typer.Option(..., "--file", help="MP3 file (max 15 seconds)."),
    step: int | None = typer.Option(
        None, "--step", help="stepOrder of the step to attach the note to."
    ),
    workout_flag: bool = typer.Option(
        False, "--workout", help="Attach the note to the workout itself."
    ),
):
    """Upload an MP3 and attach it as an audio note."""
    step_order = _resolve_step(step, workout_flag)
    api = client.load_client().client
    return audio_notes.add_note(api, workout_id, file_opt, step_order)


@audio_note_app.command(name="list")
@command_output
def audio_note_list(workout_id: str = typer.Argument(...)):
    """Show which steps (and the workout itself) carry audio notes."""
    api = client.load_client().client
    return audio_notes.list_notes(api, workout_id)


@audio_note_app.command(name="remove")
@command_output
def audio_note_remove(
    workout_id: str = typer.Argument(...),
    step: int | None = typer.Option(
        None, "--step", help="stepOrder of the step to remove the note from."
    ),
    workout_flag: bool = typer.Option(
        False, "--workout", help="Remove the workout-level note."
    ),
):
    """Remove an audio note from a step or from the workout itself."""
    step_order = _resolve_step(step, workout_flag)
    api = client.load_client().client
    return audio_notes.remove_note(api, workout_id, step_order)
