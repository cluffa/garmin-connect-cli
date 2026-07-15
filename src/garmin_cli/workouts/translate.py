from __future__ import annotations

from garminconnect.workout import (
    ConditionType,
    CyclingWorkout,
    ExecutableStep,
    RepeatGroup as GarminRepeat,
    RunningWorkout,
    SportType,
    StepType,
    TargetType,
    WorkoutSegment,
)

from garmin_cli.output import UsageError
from garmin_cli.workouts import units
from garmin_cli.workouts.schema import RepeatGroup, Step, WorkoutSpec

_STEP_TYPE = {
    "warmup": (StepType.WARMUP, "warmup", 1),
    "cooldown": (StepType.COOLDOWN, "cooldown", 2),
    "interval": (StepType.INTERVAL, "interval", 3),
    "recovery": (StepType.RECOVERY, "recovery", 4),
}

# Sport default speeds (m/s) for estimating distance-step duration when no target given.
_DEFAULT_SPEED = {"running": 1000 / 300, "cycling": 25000 / 3600}  # 5:00/km, 25 km/h


def _end_condition(duration) -> tuple[dict, float]:
    if duration.time is not None:
        secs = units.parse_duration(duration.time)
        return (
            {
                "conditionTypeId": ConditionType.TIME,
                "conditionTypeKey": "time",
                "displayOrder": 2,
                "displayable": True,
            },
            secs,
        )
    if duration.distance is not None:
        meters = units.parse_distance(duration.distance)
        return (
            {
                "conditionTypeId": ConditionType.DISTANCE,
                "conditionTypeKey": "distance",
                "displayOrder": 3,
                "displayable": True,
            },
            meters,
        )
    raise UsageError("duration must set 'time' or 'distance'")


def _target(target, sport: str) -> tuple[dict | None, float | None, float | None]:
    if target is None:
        return None, None, None
    if target.pace is not None:
        if sport != "running":
            raise UsageError("pace target is only valid for running")
        v1, v2 = sorted(units.parse_pace(p) for p in target.pace)
        return _target_dict(TargetType.PACE_ZONE, "pace.zone"), v1, v2
    if target.speed is not None:
        v1, v2 = sorted(units.parse_pace(s) for s in target.speed)
        return _target_dict(TargetType.SPEED_ZONE, "speed.zone"), v1, v2
    if target.power is not None:
        if sport != "cycling":
            raise UsageError("power target is only valid for cycling")
        v1, v2 = sorted(float(x) for x in target.power)
        return _target_dict(TargetType.POWER_ZONE, "power.zone"), v1, v2
    if target.hr is not None:
        v1, v2 = sorted(float(x) for x in target.hr)
        return _target_dict(TargetType.HEART_RATE_ZONE, "heart.rate.zone"), v1, v2
    return None, None, None


def _target_dict(type_id: int, key: str) -> dict:
    return {"workoutTargetTypeId": type_id, "workoutTargetTypeKey": key, "displayOrder": 1}


_NO_TARGET = {
    "workoutTargetTypeId": TargetType.NO_TARGET,
    "workoutTargetTypeKey": "no.target",
    "displayOrder": 1,
}


def _estimate_step_seconds(duration, target, sport: str) -> float:
    if duration.time is not None:
        return units.parse_duration(duration.time)
    meters = units.parse_distance(duration.distance)
    speed = _DEFAULT_SPEED[sport]
    if target is not None and (target.pace or target.speed):
        vals = target.pace or target.speed
        speeds = [units.parse_pace(v) for v in vals]
        speed = sum(speeds) / len(speeds)
    return meters / speed


def _build_step(step: Step, order: int, sport: str) -> tuple[ExecutableStep, float]:
    type_id, type_key, type_order = _STEP_TYPE[step.type]
    end_cond, end_val = _end_condition(step.duration)
    target_dict, v1, v2 = _target(step.target, sport)
    executable = ExecutableStep(
        stepOrder=order,
        stepType={"stepTypeId": type_id, "stepTypeKey": type_key, "displayOrder": type_order},
        endCondition=end_cond,
        endConditionValue=end_val,
        targetType=target_dict or _NO_TARGET,
    )
    if v1 is not None:
        executable.targetValueOne = v1
        executable.targetValueTwo = v2
    return executable, _estimate_step_seconds(step.duration, step.target, sport)


def _build_items(items, sport, order_ref) -> tuple[list, float]:
    built = []
    total = 0.0
    for item in items:
        if isinstance(item, RepeatGroup):
            children, child_secs = _build_items(item.steps, sport, order_ref)
            group = GarminRepeat(
                stepOrder=order_ref[0],
                stepType={
                    "stepTypeId": StepType.REPEAT,
                    "stepTypeKey": "repeat",
                    "displayOrder": 6,
                },
                numberOfIterations=item.repeat,
                workoutSteps=children,
                endCondition={
                    "conditionTypeId": ConditionType.ITERATIONS,
                    "conditionTypeKey": "iterations",
                    "displayOrder": 7,
                    "displayable": False,
                },
                endConditionValue=float(item.repeat),
            )
            order_ref[0] += 1
            built.append(group)
            total += child_secs * item.repeat
        else:
            executable, secs = _build_step(item, order_ref[0], sport)
            order_ref[0] += 1
            built.append(executable)
            total += secs
    return built, total


def translate(spec: WorkoutSpec):
    order_ref = [1]
    steps, total_secs = _build_items(spec.steps, spec.sport, order_ref)
    sport_id = SportType.RUNNING if spec.sport == "running" else SportType.CYCLING
    segment = WorkoutSegment(
        segmentOrder=1,
        sportType={"sportTypeId": sport_id, "sportTypeKey": spec.sport, "displayOrder": 1},
        workoutSteps=steps,
    )
    cls = RunningWorkout if spec.sport == "running" else CyclingWorkout
    return cls(
        workoutName=spec.name,
        estimatedDurationInSecs=int(round(total_secs)),
        workoutSegments=[segment],
    )


def summarize(spec: WorkoutSpec) -> dict:
    workout = translate(spec)
    return {
        "name": spec.name,
        "sport": spec.sport,
        "estimatedDurationInSecs": workout.estimatedDurationInSecs,
        "stepCount": len(spec.steps),
    }
