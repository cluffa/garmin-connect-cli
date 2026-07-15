import pytest

from garmin_cli.output import UsageError
from garmin_cli.workouts.schema import load_plan
from garmin_cli.workouts.translate import summarize, translate


def _spec(raw):
    return load_plan(raw).workouts[0]


def test_translate_simple_running():
    spec = _spec(
        '{"name":"Easy","sport":"running","steps":['
        '{"type":"warmup","duration":{"time":"10min"}},'
        '{"type":"cooldown","duration":{"time":"5min"}}]}'
    )
    workout = translate(spec)
    d = workout.to_dict()
    assert d["workoutName"] == "Easy"
    assert d["sportType"]["sportTypeKey"] == "running"
    steps = d["workoutSegments"][0]["workoutSteps"]
    assert len(steps) == 2
    assert d["estimatedDurationInSecs"] == 900


def test_translate_repeat_and_pace_target():
    spec = _spec(
        '{"name":"Intervals","sport":"running","steps":['
        '{"repeat":5,"steps":['
        '{"type":"interval","duration":{"distance":"1km"},"target":{"pace":["4:00/km","3:50/km"]}},'
        '{"type":"recovery","duration":{"time":"2min"}}]}]}'
    )
    workout = translate(spec)
    d = workout.to_dict()
    group = d["workoutSegments"][0]["workoutSteps"][0]
    assert group["type"] == "RepeatGroupDTO"
    assert group["numberOfIterations"] == 5
    interval = group["workoutSteps"][0]
    assert interval["targetType"]["workoutTargetTypeKey"] == "pace.zone"
    assert interval["targetValueOne"] < interval["targetValueTwo"]


def test_cycling_power_target():
    spec = _spec(
        '{"name":"FTP","sport":"cycling","steps":['
        '{"type":"interval","duration":{"time":"20min"},"target":{"power":[200,240]}}]}'
    )
    d = translate(spec).to_dict()
    step = d["workoutSegments"][0]["workoutSteps"][0]
    assert step["targetType"]["workoutTargetTypeKey"] == "power.zone"
    assert step["targetValueOne"] == 200
    assert step["targetValueTwo"] == 240


def test_pace_target_on_cycling_rejected():
    spec = _spec(
        '{"name":"bad","sport":"cycling","steps":['
        '{"type":"interval","duration":{"time":"5min"},"target":{"pace":["4:00/km","3:50/km"]}}]}'
    )
    with pytest.raises(UsageError):
        translate(spec)


def test_summarize():
    spec = _spec(
        '{"name":"Easy","sport":"running","steps":['
        '{"type":"warmup","duration":{"time":"10min"}}]}'
    )
    s = summarize(spec)
    assert s == {
        "name": "Easy",
        "sport": "running",
        "estimatedDurationInSecs": 600,
        "stepCount": 1,
    }
