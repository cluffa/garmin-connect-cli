from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from garmin_cli.output import UsageError


class Target(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pace: list[str] | None = None
    hr: list[float] | None = None
    power: list[float] | None = None
    speed: list[str] | None = None


class Duration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: str | None = None
    distance: str | None = None


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["warmup", "interval", "recovery", "cooldown"]
    duration: Duration
    target: Target | None = None


class RepeatGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repeat: int
    steps: list["Step | RepeatGroup"]


class WorkoutSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    sport: Literal["running", "cycling"]
    date: str | None = None
    steps: list["Step | RepeatGroup"]


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workouts: list[WorkoutSpec]


RepeatGroup.model_rebuild()
WorkoutSpec.model_rebuild()


def load_plan(raw: str) -> Plan:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise UsageError(f"invalid JSON: {e}") from None
    if not isinstance(data, dict):
        raise UsageError("spec must be a JSON object")
    if "workouts" not in data:
        data = {"workouts": [data]}
    try:
        return Plan.model_validate(data)
    except ValidationError as e:
        raise UsageError(f"invalid workout spec: {e.errors()[:3]}") from None


def spec_json_schema() -> dict:
    return Plan.model_json_schema()
