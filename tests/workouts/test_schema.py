import pytest

from garmin_cli.output import UsageError
from garmin_cli.workouts.schema import load_plan, spec_json_schema

SINGLE = """
{"name":"Easy","sport":"running","steps":[{"type":"warmup","duration":{"time":"10min"}}]}
"""

BATCH = """
{"workouts":[
  {"name":"A","sport":"running","date":"2026-07-21","steps":[
    {"repeat":3,"steps":[
      {"type":"interval","duration":{"distance":"1km"},"target":{"pace":["4:00/km","3:50/km"]}},
      {"type":"recovery","duration":{"time":"2min"}}
    ]}
  ]}
]}
"""


def test_single_normalized_to_plan():
    plan = load_plan(SINGLE)
    assert len(plan.workouts) == 1
    assert plan.workouts[0].name == "Easy"
    assert plan.workouts[0].date is None


def test_batch_with_repeat():
    plan = load_plan(BATCH)
    w = plan.workouts[0]
    assert w.date == "2026-07-21"
    group = w.steps[0]
    assert group.repeat == 3
    assert len(group.steps) == 2


def test_note_and_notes_accepted():
    plan = load_plan(
        '{"name":"x","sport":"running","notes":"coach note",'
        '"steps":[{"type":"warmup","duration":{"time":"5min"},"note":"easy"}]}'
    )
    w = plan.workouts[0]
    assert w.notes == "coach note"
    assert w.steps[0].note == "easy"


def test_note_and_notes_optional():
    w = load_plan(SINGLE).workouts[0]
    assert w.notes is None
    assert w.steps[0].note is None


def test_unknown_step_field_still_rejected():
    with pytest.raises(UsageError):
        load_plan(
            '{"name":"x","sport":"running",'
            '"steps":[{"type":"warmup","duration":{"time":"5min"},"bogus":1}]}'
        )


def test_invalid_json():
    with pytest.raises(UsageError):
        load_plan("{not json")


def test_invalid_sport():
    with pytest.raises(UsageError):
        load_plan('{"name":"x","sport":"swimming","steps":[]}')


def test_schema_export_has_workouts():
    schema = spec_json_schema()
    assert "workouts" in schema["properties"]
