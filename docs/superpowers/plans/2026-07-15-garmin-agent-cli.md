# Garmin Connect Agent-First CLI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `uv`-packaged Python CLI (`garmin`) that wraps `python-garminconnect` so an external AI agent can program workouts and retrieve data through a clean, JSON-first tool surface.

**Architecture:** A Typer app with command groups (`auth`, `workout`, `activity`, `health`, `stats`, plus `capabilities`). Every command returns a `{ok, data}` / `{ok, error}` envelope with meaningful exit codes. Pure logic (unit parsing, date shorthands, workout translation, slim projections) is isolated in dependency-free modules and thoroughly unit-tested; command modules are thin wrappers over a mocked Garmin client.

**Tech Stack:** Python 3.11+, `uv`, Typer, `python-garminconnect` (incl. its `garminconnect.workout` pydantic models), `python-toon` (imports as `toon`), pytest.

## Global Constraints

- Python **>= 3.11**. Managed and run via **`uv`** only.
- Entry point: **`garmin = "garmin_cli.cli:app"`**.
- Package source under **`src/garmin_cli/`** (src layout).
- Dependencies: **`garminconnect`**, **`typer`**, **`python-toon`**, **`pydantic`** (transitive via garminconnect, but declared explicitly). Dev: **`pytest`**.
- **No live Garmin API calls in tests** — always mock the client.
- Every command's terminal output is a single envelope; **success → stdout**, **error → stderr**.
- Exit codes: `0` ok · `2` usage/invalid input · `3` auth · `4` Garmin API error · `1` internal.
- Output default **`json`** (compact, no indentation); **`--format toon`** opt-in; **`--full`** opt-in on read endpoints.
- Token cache dir: `GARMINTOKENS` env var if set, else `~/.garmin-cli`.

---

## File Structure

- `pyproject.toml` — uv project, deps, entry point.
- `src/garmin_cli/__init__.py` — version.
- `src/garmin_cli/state.py` — process-wide output options (`fmt`, `full`).
- `src/garmin_cli/output.py` — envelope, `CliError` hierarchy, exit codes, json/toon render, `command_output` decorator, `emit_batch`.
- `src/garmin_cli/dates.py` — date shorthand + range parsing.
- `src/garmin_cli/workouts/units.py` — parse durations, distances, paces.
- `src/garmin_cli/workouts/schema.py` — simplified-spec pydantic models + JSON-schema export + input loading.
- `src/garmin_cli/workouts/translate.py` — spec → `garminconnect.workout` models + estimated duration.
- `src/garmin_cli/projections.py` — slim views for read endpoints.
- `src/garmin_cli/client.py` — auth/session, token cache, load-or-fail.
- `src/garmin_cli/commands/auth.py` · `workout.py` · `activity.py` · `health.py` · `stats.py` · `meta.py`.
- `src/garmin_cli/cli.py` — Typer app, global callback, group wiring.
- `tests/…` — mirrors the above.

---

### Task 1: Project scaffold + Typer skeleton

**Files:**
- Create: `pyproject.toml`, `src/garmin_cli/__init__.py`, `src/garmin_cli/state.py`, `src/garmin_cli/cli.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: `garmin_cli.cli:app` (Typer app); `garmin_cli.state` module with mutable attributes `fmt: str = "json"` and `full: bool = False`.

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "garmin-cli"
version = "0.1.0"
description = "Agent-first CLI for Garmin Connect"
requires-python = ">=3.11"
dependencies = [
    "garminconnect",
    "typer",
    "python-toon",
    "pydantic>=2",
]

[project.scripts]
garmin = "garmin_cli.cli:app"

[dependency-groups]
dev = ["pytest"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/garmin_cli"]
```

- [ ] **Step 2: Write `src/garmin_cli/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 3: Write `src/garmin_cli/state.py`**

```python
"""Process-wide output options set by the top-level CLI callback."""

fmt: str = "json"
full: bool = False
```

- [ ] **Step 4: Write `src/garmin_cli/cli.py` (skeleton)**

```python
import typer

from garmin_cli import state

app = typer.Typer(
    add_completion=False,
    help="Agent-first CLI for Garmin Connect.",
    no_args_is_help=True,
)


@app.callback()
def main(
    fmt: str = typer.Option("json", "--format", help="Output format: json or toon."),
    full: bool = typer.Option(False, "--full", help="Return full raw payloads."),
) -> None:
    """Global options applied to every command."""
    if fmt not in ("json", "toon"):
        raise typer.BadParameter("format must be 'json' or 'toon'")
    state.fmt = fmt
    state.full = full
```

- [ ] **Step 5: Write the failing smoke test in `tests/test_smoke.py`**

```python
from typer.testing import CliRunner

from garmin_cli.cli import app

runner = CliRunner()


def test_help_runs():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Garmin Connect" in result.output
```

- [ ] **Step 6: Sync deps and run the test**

Run: `uv sync && uv run pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/garmin_cli tests/test_smoke.py
git commit -m "feat: scaffold uv project and Typer skeleton"
```

---

### Task 2: Output envelope, errors, and rendering

**Files:**
- Create: `src/garmin_cli/output.py`
- Test: `tests/test_output.py`

**Interfaces:**
- Produces:
  - `class CliError(Exception)` with attributes `type: str`, `exit_code: int`.
  - `class UsageError(CliError)` (type `"usage"`, code `2`), `class AuthError(CliError)` (type `"auth"`, code `3`), `class ApiError(CliError)` (type `"api"`, code `4`).
  - `def render(envelope: dict) -> str` — compact JSON, or TOON when `state.fmt == "toon"`.
  - `def command_output(fn)` — decorator: runs `fn`, prints `{ok:true,data:fn()}` to stdout / exit 0; maps `CliError` → stderr envelope + its exit code; any other exception → `{ok:false,error:{type:"internal",...}}` + exit 1.
  - `def emit_batch(results: list[dict]) -> None` — prints `{ok: all-ok, data:{results, created, failed}}` to stdout; exit 0 if all ok else 4.

- [ ] **Step 1: Write failing tests in `tests/test_output.py`**

```python
import json

import pytest

from garmin_cli import state
from garmin_cli import output
from garmin_cli.output import (
    AuthError,
    UsageError,
    command_output,
    emit_batch,
    render,
)


def setup_function():
    state.fmt = "json"
    state.full = False


def test_render_json_compact():
    out = render({"ok": True, "data": {"a": 1}})
    assert out == '{"ok":true,"data":{"a":1}}'


def test_render_toon_uses_toon(monkeypatch):
    state.fmt = "toon"
    out = render({"ok": True, "data": {"rows": [{"x": 1}, {"x": 2}]}})
    assert "rows[2]" in out  # TOON tabular header


def test_command_output_success(capsys):
    @command_output
    def cmd():
        return {"hello": "world"}

    with pytest.raises(SystemExit) as exc:
        cmd()
    assert exc.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": True, "data": {"hello": "world"}}


def test_command_output_cli_error(capsys):
    @command_output
    def cmd():
        raise AuthError("no token")

    with pytest.raises(SystemExit) as exc:
        cmd()
    assert exc.value.code == 3
    err = json.loads(capsys.readouterr().err)
    assert err == {"ok": False, "error": {"type": "auth", "message": "no token"}}


def test_command_output_unexpected_error(capsys):
    @command_output
    def cmd():
        raise ValueError("boom")

    with pytest.raises(SystemExit) as exc:
        cmd()
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert err["error"]["type"] == "internal"


def test_emit_batch_all_ok(capsys):
    with pytest.raises(SystemExit) as exc:
        emit_batch([{"index": 0, "ok": True}])
    assert exc.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["data"]["created"] == 1
    assert out["data"]["failed"] == 0


def test_emit_batch_partial_failure(capsys):
    with pytest.raises(SystemExit) as exc:
        emit_batch([{"index": 0, "ok": True}, {"index": 1, "ok": False}])
    assert exc.value.code == 4
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["data"] == {
        "results": [{"index": 0, "ok": True}, {"index": 1, "ok": False}],
        "created": 1,
        "failed": 1,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_output.py -v`
Expected: FAIL (`ModuleNotFoundError: garmin_cli.output`).

- [ ] **Step 3: Write `src/garmin_cli/output.py`**

```python
import functools
import json
import sys

import toon

from garmin_cli import state


class CliError(Exception):
    type = "internal"
    exit_code = 1

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UsageError(CliError):
    type = "usage"
    exit_code = 2


class AuthError(CliError):
    type = "auth"
    exit_code = 3


class ApiError(CliError):
    type = "api"
    exit_code = 4


def render(envelope: dict) -> str:
    if state.fmt == "toon":
        return toon.encode(envelope)
    return json.dumps(envelope, separators=(",", ":"), default=str)


def _emit(envelope: dict, stream, code: int) -> None:
    print(render(envelope), file=stream)
    raise SystemExit(code)


def command_output(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            data = fn(*args, **kwargs)
        except CliError as e:
            _emit({"ok": False, "error": {"type": e.type, "message": e.message}}, sys.stderr, e.exit_code)
        except Exception as e:  # noqa: BLE001 - top-level guard
            _emit({"ok": False, "error": {"type": "internal", "message": str(e)}}, sys.stderr, 1)
        else:
            _emit({"ok": True, "data": data}, sys.stdout, 0)

    return wrapper


def emit_batch(results: list[dict]) -> None:
    created = sum(1 for r in results if r.get("ok"))
    failed = len(results) - created
    envelope = {
        "ok": failed == 0,
        "data": {"results": results, "created": created, "failed": failed},
    }
    _emit(envelope, sys.stdout, 0 if failed == 0 else 4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_output.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/garmin_cli/output.py tests/test_output.py
git commit -m "feat: output envelope, error types, json/toon rendering"
```

---

### Task 3: Unit parsing (durations, distances, paces)

**Files:**
- Create: `src/garmin_cli/workouts/__init__.py`, `src/garmin_cli/workouts/units.py`
- Test: `tests/workouts/test_units.py`

**Interfaces:**
- Produces (all raise `output.UsageError` on bad input):
  - `def parse_duration(text: str) -> float` — seconds. Accepts `"90s"`, `"10min"`, `"1h"`, `"1h30min"`, `"1:30"` (mm:ss), `"1:30:00"` (hh:mm:ss).
  - `def parse_distance(text: str) -> float` — meters. Accepts `"400m"`, `"1km"`, `"1.5km"`, `"1mi"`.
  - `def parse_pace(text: str) -> float` — meters/second. Accepts `"4:00/km"`, `"7:30/mi"`.

- [ ] **Step 1: Write `src/garmin_cli/workouts/__init__.py`**

```python
```

- [ ] **Step 2: Write failing tests in `tests/workouts/test_units.py`**

```python
import pytest

from garmin_cli.output import UsageError
from garmin_cli.workouts import units


def test_parse_duration_seconds():
    assert units.parse_duration("90s") == 90


def test_parse_duration_minutes():
    assert units.parse_duration("10min") == 600


def test_parse_duration_compound():
    assert units.parse_duration("1h30min") == 5400


def test_parse_duration_colon_mmss():
    assert units.parse_duration("1:30") == 90


def test_parse_duration_colon_hhmmss():
    assert units.parse_duration("1:30:00") == 5400


def test_parse_duration_bad():
    with pytest.raises(UsageError):
        units.parse_duration("banana")


def test_parse_distance_meters():
    assert units.parse_distance("400m") == 400


def test_parse_distance_km():
    assert units.parse_distance("1.5km") == 1500


def test_parse_distance_miles():
    assert round(units.parse_distance("1mi"), 1) == 1609.3


def test_parse_pace_per_km():
    # 4:00/km -> 240 s per 1000 m -> 4.1667 m/s
    assert round(units.parse_pace("4:00/km"), 3) == 4.167


def test_parse_pace_per_mile():
    # 8:00/mi -> 480 s per 1609.34 m -> 3.353 m/s
    assert round(units.parse_pace("8:00/mi"), 3) == 3.353


def test_parse_pace_bad():
    with pytest.raises(UsageError):
        units.parse_pace("fast")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/workouts/test_units.py -v`
Expected: FAIL (module not found).

- [ ] **Step 4: Write `src/garmin_cli/workouts/units.py`**

```python
import re

from garmin_cli.output import UsageError

METERS_PER_MILE = 1609.34


def _mmss_to_seconds(text: str) -> float | None:
    parts = text.split(":")
    if not all(p.isdigit() for p in parts):
        return None
    if len(parts) == 2:
        m, s = parts
        return int(m) * 60 + int(s)
    if len(parts) == 3:
        h, m, s = parts
        return int(h) * 3600 + int(m) * 60 + int(s)
    return None


_DUR_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(h|hr|hours?|m|min|mins?|minutes?|s|sec|secs?|seconds?)")
_DUR_FACTOR = {"h": 3600, "hr": 3600, "m": 60, "min": 60, "s": 1, "sec": 1}


def parse_duration(text: str) -> float:
    text = text.strip().lower()
    if ":" in text:
        secs = _mmss_to_seconds(text)
        if secs is not None:
            return float(secs)
        raise UsageError(f"invalid duration: {text!r}")
    total = 0.0
    matched = False
    for value, unit in _DUR_UNIT.findall(text):
        matched = True
        key = unit[0] if unit[0] in "hms" else unit
        total += float(value) * _DUR_FACTOR[key]
    if not matched:
        raise UsageError(f"invalid duration: {text!r}")
    return total


_DIST = re.compile(r"^(\d+(?:\.\d+)?)\s*(mi|miles?|km|m|meters?)$")


def parse_distance(text: str) -> float:
    m = _DIST.match(text.strip().lower())
    if not m:
        raise UsageError(f"invalid distance: {text!r}")
    value, unit = float(m.group(1)), m.group(2)
    if unit.startswith("mi"):
        return value * METERS_PER_MILE
    if unit.startswith("km"):
        return value * 1000
    return value


_PACE = re.compile(r"^(\d+):(\d{1,2})\s*/\s*(km|mi)$")


def parse_pace(text: str) -> float:
    m = _PACE.match(text.strip().lower())
    if not m:
        raise UsageError(f"invalid pace: {text!r}")
    minutes, seconds, unit = int(m.group(1)), int(m.group(2)), m.group(3)
    per_unit_seconds = minutes * 60 + seconds
    distance = METERS_PER_MILE if unit == "mi" else 1000.0
    if per_unit_seconds <= 0:
        raise UsageError(f"invalid pace: {text!r}")
    return distance / per_unit_seconds
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/workouts/test_units.py -v`
Expected: PASS (12 tests).

- [ ] **Step 6: Commit**

```bash
git add src/garmin_cli/workouts/__init__.py src/garmin_cli/workouts/units.py tests/workouts/test_units.py
git commit -m "feat: duration/distance/pace unit parsing"
```

---

### Task 4: Date shorthand parsing

**Files:**
- Create: `src/garmin_cli/dates.py`
- Test: `tests/test_dates.py`

**Interfaces:**
- Produces:
  - `def parse_date(text: str, *, today: date | None = None) -> date` — accepts `YYYY-MM-DD`, `today`, `yesterday`, `-Nd`, `+Nd`, `-Nw`, `+Nw`. `today` defaults to `date.today()`.
  - `def parse_range(text: str, *, today: date | None = None) -> tuple[date, date]` — accepts `start:end`; a single date returns `(d, d)`.
  - Raises `output.UsageError` on bad input.

- [ ] **Step 1: Write failing tests in `tests/test_dates.py`**

```python
from datetime import date

import pytest

from garmin_cli.dates import parse_date, parse_range
from garmin_cli.output import UsageError

REF = date(2026, 7, 15)


def test_iso():
    assert parse_date("2026-07-01", today=REF) == date(2026, 7, 1)


def test_today():
    assert parse_date("today", today=REF) == REF


def test_yesterday():
    assert parse_date("yesterday", today=REF) == date(2026, 7, 14)


def test_offset_days_back():
    assert parse_date("-7d", today=REF) == date(2026, 7, 8)


def test_offset_days_forward():
    assert parse_date("+7d", today=REF) == date(2026, 7, 22)


def test_offset_weeks():
    assert parse_date("-1w", today=REF) == date(2026, 7, 8)


def test_bad_date():
    with pytest.raises(UsageError):
        parse_date("someday", today=REF)


def test_range_explicit():
    assert parse_range("2026-07-01:2026-07-07", today=REF) == (
        date(2026, 7, 1),
        date(2026, 7, 7),
    )


def test_range_relative():
    assert parse_range("-7d:today", today=REF) == (date(2026, 7, 8), REF)


def test_range_single_date():
    assert parse_range("today", today=REF) == (REF, REF)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_dates.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write `src/garmin_cli/dates.py`**

```python
import re
from datetime import date, timedelta

from garmin_cli.output import UsageError

_OFFSET = re.compile(r"^([+-]\d+)([dw])$")


def parse_date(text: str, *, today: date | None = None) -> date:
    today = today or date.today()
    text = text.strip().lower()
    if text == "today":
        return today
    if text == "yesterday":
        return today - timedelta(days=1)
    m = _OFFSET.match(text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = n * (7 if unit == "w" else 1)
        return today + timedelta(days=days)
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise UsageError(f"invalid date: {text!r}") from None


def parse_range(text: str, *, today: date | None = None) -> tuple[date, date]:
    text = text.strip()
    if ":" in text and not _looks_like_iso_datetime(text):
        start_s, end_s = text.split(":", 1)
        return parse_date(start_s, today=today), parse_date(end_s, today=today)
    single = parse_date(text, today=today)
    return single, single


def _looks_like_iso_datetime(text: str) -> bool:
    # Guard against ever being handed a time component; ranges use bare dates only.
    return "T" in text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_dates.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/garmin_cli/dates.py tests/test_dates.py
git commit -m "feat: date shorthand and range parsing"
```

---

### Task 5: Workout spec schema + input loading

**Files:**
- Create: `src/garmin_cli/workouts/schema.py`
- Test: `tests/workouts/test_schema.py`

**Interfaces:**
- Produces:
  - Pydantic models: `Target`, `Duration`, `Step`, `RepeatGroup`, `WorkoutSpec` (fields: `name: str`, `sport: Literal["running","cycling"]`, `date: str | None`, `steps: list[Step | RepeatGroup]`), `Plan` (field: `workouts: list[WorkoutSpec]`).
  - `def load_plan(raw: str) -> Plan` — parses a JSON string; accepts either a `{"workouts":[...]}` object or a bare single-workout object (normalized to a one-item plan); raises `output.UsageError` on invalid JSON or schema.
  - `def spec_json_schema() -> dict` — the JSON Schema for a `Plan`.

- [ ] **Step 1: Write failing tests in `tests/workouts/test_schema.py`**

```python
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


def test_invalid_json():
    with pytest.raises(UsageError):
        load_plan("{not json")


def test_invalid_sport():
    with pytest.raises(UsageError):
        load_plan('{"name":"x","sport":"swimming","steps":[]}')


def test_schema_export_has_workouts():
    schema = spec_json_schema()
    assert "workouts" in schema["properties"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/workouts/test_schema.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write `src/garmin_cli/workouts/schema.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/workouts/test_schema.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/garmin_cli/workouts/schema.py tests/workouts/test_schema.py
git commit -m "feat: simplified workout spec models and loader"
```

---

### Task 6: Workout translation to Garmin models

**Files:**
- Create: `src/garmin_cli/workouts/translate.py`
- Test: `tests/workouts/test_translate.py`

**Interfaces:**
- Consumes: `schema.WorkoutSpec`, `schema.Step`, `schema.RepeatGroup`; `units.parse_duration/parse_distance/parse_pace`.
- Produces:
  - `def translate(spec: WorkoutSpec) -> BaseWorkout` — returns a `garminconnect.workout.RunningWorkout` or `CyclingWorkout` with segments/steps and a computed `estimatedDurationInSecs`.
  - `def summarize(spec: WorkoutSpec) -> dict` — `{"name","sport","estimatedDurationInSecs","stepCount"}` for dry-run output.
  - Raises `output.UsageError` on invalid target/sport combinations.

**Notes:** The library's `create_*` helpers do not attach target *values*, so this module builds `ExecutableStep`/`RepeatGroup` models directly (they allow extra fields for `targetValueOne`/`targetValueTwo`). Step/end/target type IDs come from the library's `StepType`/`ConditionType`/`TargetType` constant classes.

- [ ] **Step 1: Write failing tests in `tests/workouts/test_translate.py`**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/workouts/test_translate.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write `src/garmin_cli/workouts/translate.py`**

```python
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
            {"conditionTypeId": ConditionType.TIME, "conditionTypeKey": "time",
             "displayOrder": 2, "displayable": True},
            secs,
        )
    if duration.distance is not None:
        meters = units.parse_distance(duration.distance)
        return (
            {"conditionTypeId": ConditionType.DISTANCE, "conditionTypeKey": "distance",
             "displayOrder": 3, "displayable": True},
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


_NO_TARGET = {"workoutTargetTypeId": TargetType.NO_TARGET,
              "workoutTargetTypeKey": "no.target", "displayOrder": 1}


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
                stepType={"stepTypeId": StepType.REPEAT, "stepTypeKey": "repeat", "displayOrder": 6},
                numberOfIterations=item.repeat,
                workoutSteps=children,
                endCondition={"conditionTypeId": ConditionType.ITERATIONS,
                              "conditionTypeKey": "iterations", "displayOrder": 7, "displayable": False},
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/workouts/test_translate.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/garmin_cli/workouts/translate.py tests/workouts/test_translate.py
git commit -m "feat: translate workout specs to Garmin workout models"
```

---

### Task 7: Client / auth session

**Files:**
- Create: `src/garmin_cli/client.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `output.AuthError`.
- Produces:
  - `def token_dir() -> str` — `GARMINTOKENS` env or `~/.garmin-cli`.
  - `def load_client(factory=Garmin) -> Garmin` — builds a client and resumes from the cached token; raises `AuthError` if no valid token. `factory` is injectable for tests.
  - `def do_login(prompt_mfa, factory=Garmin) -> None` — reads `GARMIN_EMAIL`/`GARMIN_PASSWORD`, logs in (auto-saves token to `token_dir()`); raises `AuthError` if creds missing or login fails. `prompt_mfa` is a `() -> str` callback.
  - `def logout() -> None` — removes the cached token dir contents.
  - `def token_status() -> bool` — True if `load_client()` succeeds.

- [ ] **Step 1: Write failing tests in `tests/test_client.py`**

```python
import pytest

from garmin_cli import client
from garmin_cli.output import AuthError


class FakeGarmin:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.logged_in = False

    def login(self, tokenstore=None):
        if getattr(FakeGarmin, "fail", False):
            raise RuntimeError("no tokens")
        self.tokenstore = tokenstore
        self.logged_in = True
        return (None, None)


def test_token_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path))
    assert client.token_dir() == str(tmp_path)


def test_token_dir_default(monkeypatch):
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    assert client.token_dir().endswith(".garmin-cli")


def test_load_client_success(monkeypatch):
    FakeGarmin.fail = False
    g = client.load_client(factory=FakeGarmin)
    assert g.logged_in is True


def test_load_client_no_token(monkeypatch):
    FakeGarmin.fail = True
    with pytest.raises(AuthError):
        client.load_client(factory=FakeGarmin)
    FakeGarmin.fail = False


def test_do_login_missing_creds(monkeypatch):
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    with pytest.raises(AuthError):
        client.do_login(prompt_mfa=lambda: "000000", factory=FakeGarmin)


def test_do_login_success(monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    FakeGarmin.fail = False
    client.do_login(prompt_mfa=lambda: "000000", factory=FakeGarmin)  # no raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_client.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write `src/garmin_cli/client.py`**

```python
from __future__ import annotations

import os
import shutil
from pathlib import Path

from garminconnect import Garmin

from garmin_cli.output import AuthError


def token_dir() -> str:
    env = os.getenv("GARMINTOKENS")
    if env:
        return env
    return str(Path.home() / ".garmin-cli")


def load_client(factory=Garmin):
    store = token_dir()
    garmin = factory()
    try:
        garmin.login(store)
    except Exception as e:  # noqa: BLE001
        raise AuthError(f"no valid token; run `garmin auth login` ({e})") from None
    return garmin


def do_login(prompt_mfa, factory=Garmin) -> None:
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        raise AuthError("GARMIN_EMAIL and GARMIN_PASSWORD must be set")
    store = token_dir()
    Path(store).mkdir(parents=True, exist_ok=True)
    garmin = factory(email=email, password=password, prompt_mfa=prompt_mfa)
    try:
        garmin.login(store)
    except Exception as e:  # noqa: BLE001
        raise AuthError(f"login failed: {e}") from None


def logout() -> None:
    store = Path(token_dir())
    if store.exists():
        shutil.rmtree(store, ignore_errors=True)


def token_status() -> bool:
    try:
        load_client()
        return True
    except AuthError:
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/garmin_cli/client.py tests/test_client.py
git commit -m "feat: Garmin client auth/session with token cache"
```

---

### Task 8: Auth commands

**Files:**
- Create: `src/garmin_cli/commands/__init__.py`, `src/garmin_cli/commands/auth.py`
- Modify: `src/garmin_cli/cli.py` (wire `auth` group)
- Test: `tests/commands/test_auth.py`

**Interfaces:**
- Consumes: `client.do_login/logout/token_status`, `output.command_output`.
- Produces: Typer sub-app `auth_app` with `login`, `status`, `logout`.

- [ ] **Step 1: Write `src/garmin_cli/commands/__init__.py`**

```python
```

- [ ] **Step 2: Write failing tests in `tests/commands/test_auth.py`**

```python
import json

from typer.testing import CliRunner

from garmin_cli import client, state
from garmin_cli.cli import app

runner = CliRunner()


def setup_function():
    state.fmt = "json"


def test_status_reports_bool(monkeypatch):
    monkeypatch.setattr(client, "token_status", lambda: True)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out == {"ok": True, "data": {"authenticated": True}}


def test_login_success(monkeypatch):
    called = {}
    monkeypatch.setattr(client, "do_login", lambda prompt_mfa: called.setdefault("ok", True))
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0
    assert called["ok"] is True
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/commands/test_auth.py -v`
Expected: FAIL (cannot import `auth` group / command missing).

- [ ] **Step 4: Write `src/garmin_cli/commands/auth.py`**

```python
import typer

from garmin_cli import client
from garmin_cli.output import command_output

auth_app = typer.Typer(help="Authenticate to Garmin Connect.", no_args_is_help=True)


@auth_app.command()
@command_output
def login():
    """Log in using GARMIN_EMAIL/GARMIN_PASSWORD; prompts for MFA if required."""
    client.do_login(prompt_mfa=lambda: typer.prompt("MFA code"))
    return {"loggedIn": True, "tokenDir": client.token_dir()}


@auth_app.command()
@command_output
def status():
    """Report whether a valid cached token exists."""
    return {"authenticated": client.token_status()}


@auth_app.command()
@command_output
def logout():
    """Delete the cached token."""
    client.logout()
    return {"loggedOut": True}
```

- [ ] **Step 5: Wire the group in `src/garmin_cli/cli.py`**

Add after the callback:

```python
from garmin_cli.commands.auth import auth_app

app.add_typer(auth_app, name="auth")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/commands/test_auth.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add src/garmin_cli/commands tests/commands/test_auth.py src/garmin_cli/cli.py
git commit -m "feat: auth login/status/logout commands"
```

---

### Task 9: Slim projections

**Files:**
- Create: `src/garmin_cli/projections.py`
- Test: `tests/test_projections.py`

**Interfaces:**
- Consumes: `state.full`.
- Produces:
  - `def project(kind: str, payload)` — returns `payload` unchanged when `state.full` is True; otherwise a slimmed view per `kind`. Kinds: `"activity"`, `"activity_list"`. Unknown kinds pass through unchanged.
  - `def slim_activity(a: dict) -> dict` — keys: `activityId`, `activityName`, `startTimeLocal`, `activityType`, `distance`, `duration`, `averageHR`, `maxHR`, `averageSpeed`, `calories` (missing keys omitted).

- [ ] **Step 1: Write failing tests in `tests/test_projections.py`**

```python
from garmin_cli import state
from garmin_cli.projections import project, slim_activity

RAW = {
    "activityId": 1,
    "activityName": "Run",
    "startTimeLocal": "2026-07-15 06:00",
    "activityType": {"typeKey": "running"},
    "distance": 5000.0,
    "duration": 1500.0,
    "averageHR": 150,
    "maxHR": 172,
    "averageSpeed": 3.3,
    "calories": 320,
    "ownerId": 999,
    "deviceId": 888,
}


def setup_function():
    state.full = False


def test_slim_activity_drops_noise():
    slim = slim_activity(RAW)
    assert "ownerId" not in slim
    assert slim["activityId"] == 1
    assert slim["averageHR"] == 150


def test_project_full_passthrough():
    state.full = True
    assert project("activity", RAW) == RAW


def test_project_activity_list():
    state.full = False
    out = project("activity_list", [RAW, RAW])
    assert len(out) == 2
    assert "ownerId" not in out[0]


def test_unknown_kind_passthrough():
    state.full = False
    assert project("mystery", {"x": 1}) == {"x": 1}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_projections.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write `src/garmin_cli/projections.py`**

```python
from __future__ import annotations

from garmin_cli import state

_ACTIVITY_KEYS = [
    "activityId", "activityName", "startTimeLocal", "activityType",
    "distance", "duration", "averageHR", "maxHR", "averageSpeed", "calories",
]


def slim_activity(a: dict) -> dict:
    return {k: a[k] for k in _ACTIVITY_KEYS if k in a}


def project(kind: str, payload):
    if state.full:
        return payload
    if kind == "activity" and isinstance(payload, dict):
        return slim_activity(payload)
    if kind == "activity_list" and isinstance(payload, list):
        return [slim_activity(a) for a in payload]
    return payload
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_projections.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/garmin_cli/projections.py tests/test_projections.py
git commit -m "feat: slim projections for read endpoints"
```

---

### Task 10: Workout commands

**Files:**
- Create: `src/garmin_cli/commands/workout.py`
- Modify: `src/garmin_cli/cli.py`
- Test: `tests/commands/test_workout.py`

**Interfaces:**
- Consumes: `client.load_client`, `schema.load_plan/spec_json_schema`, `translate.translate/summarize`, `dates.parse_date/parse_range`, `output.command_output/emit_batch/ApiError/UsageError`.
- Produces: Typer sub-app `workout_app` with `create`, `validate`, `list`, `get`, `delete`, `schedule`, `unschedule`, `scheduled`, `schema`.
- Helper: `def _read_spec(json_opt, file_opt) -> str` — returns the raw spec string from `--json`, `--file`, or stdin (exactly one source; else `UsageError`).

- [ ] **Step 1: Write failing tests in `tests/commands/test_workout.py`**

```python
import json

from typer.testing import CliRunner

from garmin_cli import client, state
from garmin_cli.cli import app

runner = CliRunner()

PLAN = json.dumps({"workouts": [
    {"name": "A", "sport": "running", "date": "2026-07-21",
     "steps": [{"type": "warmup", "duration": {"time": "10min"}}]},
    {"name": "B", "sport": "running",
     "steps": [{"type": "cooldown", "duration": {"time": "5min"}}]},
]})


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
    monkeypatch.setattr(client, "load_client", lambda: (_ for _ in ()).throw(AssertionError()))
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/commands/test_workout.py -v`
Expected: FAIL (workout group missing).

- [ ] **Step 3: Write `src/garmin_cli/commands/workout.py`**

```python
from __future__ import annotations

import sys

import typer

from garmin_cli import client
from garmin_cli.dates import parse_date, parse_range
from garmin_cli.output import UsageError, command_output, emit_batch
from garmin_cli.workouts.schema import Plan, load_plan, spec_json_schema
from garmin_cli.workouts.translate import summarize, translate

workout_app = typer.Typer(help="Create and manage workouts.", no_args_is_help=True)


def _read_spec(json_opt: str | None, file_opt: str | None) -> str:
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
    plan: Plan = load_plan(_read_spec(json_opt, file_opt))
    garmin = client.load_client()
    results = []
    for i, spec in enumerate(plan.workouts):
        entry = {"index": i, "name": spec.name}
        try:
            payload = translate(spec).to_dict()
            created = garmin.upload_workout(payload)
            workout_id = created.get("workoutId") if isinstance(created, dict) else None
            entry.update(ok=True, workoutId=workout_id)
            if spec.date:
                date_str = parse_date(spec.date).isoformat()
                sched = garmin.schedule_workout(workout_id, date_str)
                entry["scheduledId"] = (
                    sched.get("workoutScheduleId") if isinstance(sched, dict) else None
                )
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
    plan: Plan = load_plan(_read_spec(json_opt, file_opt))
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
def schedule(workout_id: str = typer.Argument(...), date_str: str = typer.Argument(...)):
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
            out.append(garmin.get_scheduled_workouts(cursor.year, cursor.month))
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
```

- [ ] **Step 4: Wire the group in `src/garmin_cli/cli.py`**

```python
from garmin_cli.commands.workout import workout_app

app.add_typer(workout_app, name="workout")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/commands/test_workout.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add src/garmin_cli/commands/workout.py tests/commands/test_workout.py src/garmin_cli/cli.py
git commit -m "feat: workout create/validate/list/get/delete/schedule/scheduled/schema"
```

---

### Task 11: Activity commands

**Files:**
- Create: `src/garmin_cli/commands/activity.py`
- Modify: `src/garmin_cli/cli.py`
- Test: `tests/commands/test_activity.py`

**Interfaces:**
- Consumes: `client.load_client`, `projections.project`, `output.command_output/UsageError`, `Garmin.ActivityDownloadFormat`.
- Produces: Typer sub-app `activity_app` with `list`, `get`, `download`.

- [ ] **Step 1: Write failing tests in `tests/commands/test_activity.py`**

```python
import json

from typer.testing import CliRunner

from garmin_cli import client, state
from garmin_cli.cli import app

runner = CliRunner()

ACT = {"activityId": 1, "activityName": "Run", "distance": 5000.0, "ownerId": 9}


class FakeClient:
    def get_activities(self, start=0, limit=20, activitytype=None):
        return [ACT]

    def get_activity(self, activity_id):
        return ACT


def setup_function():
    state.fmt = "json"
    state.full = False


def test_list_is_slim(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["activity", "list"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    assert "ownerId" not in data[0]


def test_list_full(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["--full", "activity", "list"])
    data = json.loads(result.stdout)["data"]
    assert data[0]["ownerId"] == 9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/commands/test_activity.py -v`
Expected: FAIL (activity group missing).

- [ ] **Step 3: Write `src/garmin_cli/commands/activity.py`**

```python
from __future__ import annotations

import typer
from garminconnect import Garmin

from garmin_cli import client
from garmin_cli.output import UsageError, command_output
from garmin_cli.projections import project

activity_app = typer.Typer(help="Retrieve activities.", no_args_is_help=True)

_FORMATS = {
    "tcx": Garmin.ActivityDownloadFormat.TCX,
    "gpx": Garmin.ActivityDownloadFormat.GPX,
    "fit": Garmin.ActivityDownloadFormat.ORIGINAL,
}


@activity_app.command(name="list")
@command_output
def list_(
    limit: int = typer.Option(20, "--limit"),
    start: int = typer.Option(0, "--start"),
    activity_type: str = typer.Option(None, "--type"),
):
    """List recent activities (slim by default)."""
    data = client.load_client().get_activities(start, limit, activity_type)
    return project("activity_list", data)


@activity_app.command()
@command_output
def get(activity_id: str = typer.Argument(...)):
    """Get one activity's details (slim by default)."""
    data = client.load_client().get_activity(activity_id)
    return project("activity", data)


@activity_app.command()
@command_output
def download(
    activity_id: str = typer.Argument(...),
    fmt: str = typer.Option("tcx", "--format-file", help="tcx | gpx | fit"),
    out: str = typer.Option(None, "--out", help="Output file path."),
):
    """Download an activity file."""
    if fmt not in _FORMATS:
        raise UsageError("format must be tcx, gpx, or fit")
    data = client.load_client().download_activity(activity_id, _FORMATS[fmt])
    path = out or f"activity_{activity_id}.{fmt}"
    with open(path, "wb") as fh:
        fh.write(data)
    return {"path": path, "bytes": len(data)}
```

Note: the file-format option is `--format-file` because `--format` is reserved as the global json/toon option.

- [ ] **Step 4: Wire the group in `src/garmin_cli/cli.py`**

```python
from garmin_cli.commands.activity import activity_app

app.add_typer(activity_app, name="activity")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/commands/test_activity.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/garmin_cli/commands/activity.py tests/commands/test_activity.py src/garmin_cli/cli.py
git commit -m "feat: activity list/get/download commands"
```

---

### Task 12: Health commands

**Files:**
- Create: `src/garmin_cli/commands/health.py`
- Modify: `src/garmin_cli/cli.py`
- Test: `tests/commands/test_health.py`

**Interfaces:**
- Consumes: `client.load_client`, `dates.parse_date/parse_range`, `output.command_output`.
- Produces: Typer sub-app `health_app` with `steps`, `heart-rate`, `sleep`, `body-battery`, `hrv`, `stress`, `weight`. Single-date commands accept a date shorthand (default `today`); range-capable commands (`steps`, `body-battery`, `weight`) accept a range.

- [ ] **Step 1: Write failing tests in `tests/commands/test_health.py`**

```python
import json
from datetime import date

from typer.testing import CliRunner

from garmin_cli import client, dates, state
from garmin_cli.cli import app

runner = CliRunner()


class FakeClient:
    def get_heart_rates(self, cdate):
        return {"cdate": cdate, "resting": 48}

    def get_daily_steps(self, start, end):
        return [{"start": start, "end": end}]


def setup_function():
    state.fmt = "json"
    monkey_today(date(2026, 7, 15))


def monkey_today(ref):
    import garmin_cli.dates as d
    d.date  # ensure imported


def test_heart_rate_default_today(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(dates, "parse_date", lambda t, today=None: date(2026, 7, 15))
    result = runner.invoke(app, ["health", "heart-rate"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["data"]["resting"] == 48


def test_steps_range(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(
        dates, "parse_range", lambda t, today=None: (date(2026, 7, 8), date(2026, 7, 15))
    )
    result = runner.invoke(app, ["health", "steps", "-7d:today"])
    data = json.loads(result.stdout)["data"]
    assert data[0]["start"] == "2026-07-08"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/commands/test_health.py -v`
Expected: FAIL (health group missing).

- [ ] **Step 3: Write `src/garmin_cli/commands/health.py`**

```python
from __future__ import annotations

import typer

from garmin_cli import client
from garmin_cli.dates import parse_date, parse_range
from garmin_cli.output import command_output

health_app = typer.Typer(help="Retrieve health/wellness data.", no_args_is_help=True)


def _iso(date_str: str) -> str:
    return parse_date(date_str).isoformat()


def _iso_range(range_str: str) -> tuple[str, str]:
    start, end = parse_range(range_str)
    return start.isoformat(), end.isoformat()


@health_app.command()
@command_output
def steps(date_range: str = typer.Argument("today")):
    """Daily steps over a date or range."""
    start, end = _iso_range(date_range)
    return client.load_client().get_daily_steps(start, end)


@health_app.command(name="heart-rate")
@command_output
def heart_rate(date_str: str = typer.Argument("today")):
    """Heart-rate data for a date."""
    return client.load_client().get_heart_rates(_iso(date_str))


@health_app.command()
@command_output
def sleep(date_str: str = typer.Argument("today")):
    """Sleep data for a date."""
    return client.load_client().get_sleep_data(_iso(date_str))


@health_app.command(name="body-battery")
@command_output
def body_battery(date_range: str = typer.Argument("today")):
    """Body Battery over a date or range."""
    start, end = _iso_range(date_range)
    return client.load_client().get_body_battery(start, end)


@health_app.command()
@command_output
def hrv(date_str: str = typer.Argument("today")):
    """HRV data for a date."""
    return client.load_client().get_hrv_data(_iso(date_str))


@health_app.command()
@command_output
def stress(date_str: str = typer.Argument("today")):
    """Stress data for a date."""
    return client.load_client().get_stress_data(_iso(date_str))


@health_app.command()
@command_output
def weight(date_range: str = typer.Argument("today")):
    """Weigh-ins over a date or range."""
    start, end = _iso_range(date_range)
    return client.load_client().get_weigh_ins(start, end)
```

- [ ] **Step 4: Wire the group in `src/garmin_cli/cli.py`**

```python
from garmin_cli.commands.health import health_app

app.add_typer(health_app, name="health")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/commands/test_health.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/garmin_cli/commands/health.py tests/commands/test_health.py src/garmin_cli/cli.py
git commit -m "feat: health data commands"
```

---

### Task 13: Stats commands

**Files:**
- Create: `src/garmin_cli/commands/stats.py`
- Modify: `src/garmin_cli/cli.py`
- Test: `tests/commands/test_stats.py`

**Interfaces:**
- Consumes: `client.load_client`, `dates.parse_date`, `output.command_output`.
- Produces: Typer sub-app `stats_app` with `summary`, `training-status`, `readiness`, `records`, `progress`.

- [ ] **Step 1: Write failing tests in `tests/commands/test_stats.py`**

```python
import json
from datetime import date

from typer.testing import CliRunner

from garmin_cli import client, dates, state
from garmin_cli.cli import app

runner = CliRunner()


class FakeClient:
    def get_user_summary(self, cdate):
        return {"cdate": cdate, "totalSteps": 8000}

    def get_personal_record(self):
        return [{"typeId": 1}]

    def get_progress_summary_between_dates(self, start, end, metric="distance", groupbyactivities=True):
        return {"start": start, "end": end}


def setup_function():
    state.fmt = "json"


def test_summary(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(dates, "parse_date", lambda t, today=None: date(2026, 7, 15))
    result = runner.invoke(app, ["stats", "summary"])
    assert json.loads(result.stdout)["data"]["totalSteps"] == 8000


def test_records(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    result = runner.invoke(app, ["stats", "records"])
    assert json.loads(result.stdout)["data"][0]["typeId"] == 1


def test_progress(monkeypatch):
    monkeypatch.setattr(client, "load_client", lambda: FakeClient())
    monkeypatch.setattr(
        dates, "parse_date",
        lambda t, today=None: date(2026, 7, 1) if t == "2026-07-01" else date(2026, 7, 15),
    )
    result = runner.invoke(app, ["stats", "progress", "2026-07-01", "today"])
    data = json.loads(result.stdout)["data"]
    assert data["start"] == "2026-07-01"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/commands/test_stats.py -v`
Expected: FAIL (stats group missing).

- [ ] **Step 3: Write `src/garmin_cli/commands/stats.py`**

```python
from __future__ import annotations

import typer

from garmin_cli import client
from garmin_cli.dates import parse_date
from garmin_cli.output import command_output

stats_app = typer.Typer(help="Summaries and training status.", no_args_is_help=True)


@stats_app.command()
@command_output
def summary(date_str: str = typer.Argument("today")):
    """Daily user summary."""
    return client.load_client().get_user_summary(parse_date(date_str).isoformat())


@stats_app.command(name="training-status")
@command_output
def training_status(date_str: str = typer.Argument("today")):
    """Training status for a date."""
    return client.load_client().get_training_status(parse_date(date_str).isoformat())


@stats_app.command()
@command_output
def readiness(date_str: str = typer.Argument("today")):
    """Training readiness for a date."""
    return client.load_client().get_training_readiness(parse_date(date_str).isoformat())


@stats_app.command()
@command_output
def records():
    """Personal records."""
    return client.load_client().get_personal_record()


@stats_app.command()
@command_output
def progress(
    start: str = typer.Argument(...),
    end: str = typer.Argument(...),
    metric: str = typer.Option("distance", "--metric"),
):
    """Progress summary between two dates."""
    s = parse_date(start).isoformat()
    e = parse_date(end).isoformat()
    return client.load_client().get_progress_summary_between_dates(s, e, metric)
```

- [ ] **Step 4: Wire the group in `src/garmin_cli/cli.py`**

```python
from garmin_cli.commands.stats import stats_app

app.add_typer(stats_app, name="stats")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/commands/test_stats.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/garmin_cli/commands/stats.py tests/commands/test_stats.py src/garmin_cli/cli.py
git commit -m "feat: stats and training-status commands"
```

---

### Task 14: Capabilities discovery command

**Files:**
- Create: `src/garmin_cli/commands/meta.py`
- Modify: `src/garmin_cli/cli.py`
- Test: `tests/commands/test_meta.py`

**Interfaces:**
- Consumes: `garmin_cli.cli.app` (introspected), `schema.spec_json_schema`, `output.command_output`.
- Produces: top-level command `capabilities` returning `{"commands": [...], "workoutSchema": {...}}`, where `commands` lists each group/command name and its help text by walking the Typer/Click command tree.

- [ ] **Step 1: Write failing tests in `tests/commands/test_meta.py`**

```python
import json

from typer.testing import CliRunner

from garmin_cli import state
from garmin_cli.cli import app

runner = CliRunner()


def setup_function():
    state.fmt = "json"


def test_capabilities_lists_groups_and_schema():
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    names = {c["name"] for c in data["commands"]}
    assert {"workout create", "activity list", "stats summary"} <= names
    assert "workouts" in data["workoutSchema"]["properties"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/commands/test_meta.py -v`
Expected: FAIL (capabilities command missing).

- [ ] **Step 3: Write `src/garmin_cli/commands/meta.py`**

```python
from __future__ import annotations

import typer
import click

from garmin_cli.output import command_output
from garmin_cli.workouts.schema import spec_json_schema


def _walk(command: click.Command, prefix: str, out: list) -> None:
    if isinstance(command, click.Group):
        for name, sub in command.commands.items():
            child_prefix = f"{prefix} {name}".strip()
            _walk(sub, child_prefix, out)
    else:
        out.append({"name": prefix, "help": (command.help or "").strip()})


def register(app: typer.Typer) -> None:
    @app.command()
    @command_output
    def capabilities():
        """Emit all commands and the workout schema for one-call discovery."""
        cli_command = typer.main.get_command(app)
        commands: list[dict] = []
        _walk(cli_command, "", commands)
        commands = [c for c in commands if c["name"] and c["name"] != "capabilities"]
        return {"commands": sorted(commands, key=lambda c: c["name"]), "workoutSchema": spec_json_schema()}
```

- [ ] **Step 4: Wire it in `src/garmin_cli/cli.py`** (after all `add_typer` calls, so the tree is complete)

```python
from garmin_cli.commands.meta import register as register_meta

register_meta(app)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/commands/test_meta.py -v`
Expected: PASS (1 test).

- [ ] **Step 6: Run the full suite**

Run: `uv run pytest -v`
Expected: PASS (all tests).

- [ ] **Step 7: Commit**

```bash
git add src/garmin_cli/commands/meta.py tests/commands/test_meta.py src/garmin_cli/cli.py
git commit -m "feat: capabilities discovery command"
```

---

### Task 15: End-to-end smoke + README

**Files:**
- Create: `README.md`
- Test: `tests/test_e2e_offline.py`

**Interfaces:**
- Consumes: everything wired so far. No new production interfaces.

- [ ] **Step 1: Write `tests/test_e2e_offline.py` (offline flows that don't touch Garmin)**

```python
import json

from typer.testing import CliRunner

from garmin_cli import state
from garmin_cli.cli import app

runner = CliRunner()

PLAN = json.dumps({"workouts": [
    {"name": "Wk1 Tue", "sport": "running", "date": "2026-07-21", "steps": [
        {"type": "warmup", "duration": {"time": "10min"}},
        {"repeat": 5, "steps": [
            {"type": "interval", "duration": {"distance": "1km"}, "target": {"pace": ["4:00/km", "3:50/km"]}},
            {"type": "recovery", "duration": {"time": "2min"}},
        ]},
        {"type": "cooldown", "duration": {"time": "10min"}},
    ]},
]})


def setup_function():
    state.fmt = "json"


def test_validate_full_week():
    result = runner.invoke(app, ["workout", "validate", "--json", PLAN])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert out["data"]["results"][0]["name"] == "Wk1 Tue"


def test_validate_toon_output():
    result = runner.invoke(app, ["--format", "toon", "workout", "validate", "--json", PLAN])
    assert result.exit_code == 0
    assert "results" in result.stdout  # TOON still names the array


def test_schema_roundtrip():
    result = runner.invoke(app, ["workout", "schema"])
    schema = json.loads(result.stdout)["data"]
    assert schema["properties"]["workouts"]
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `uv run pytest tests/test_e2e_offline.py -v`
Expected: PASS (3 tests).

- [ ] **Step 3: Write `README.md`**

```markdown
# garmin-cli

Agent-first CLI for Garmin Connect. Every command emits a JSON envelope
(`{"ok":true,"data":...}` / `{"ok":false,"error":...}`) with meaningful exit codes,
designed to be driven by an AI agent.

## Setup

```bash
uv sync
export GARMIN_EMAIL=you@example.com
export GARMIN_PASSWORD=...
uv run garmin auth login        # prompts for MFA if enabled; caches token to ~/.garmin-cli
```

## Discovery

```bash
uv run garmin capabilities      # all commands + the workout JSON schema, one call
uv run garmin workout schema    # just the workout spec schema
```

## Program a week in one call

```bash
uv run garmin workout validate --json '{"workouts":[...]}'   # dry-run, no upload
uv run garmin workout create   --json '{"workouts":[...]}'   # create + schedule
```

## Global options

- `--format json|toon` — compact JSON (default) or TOON.
- `--full` — return raw payloads instead of slim projections (read endpoints).

## Commands

- `auth`: `login`, `status`, `logout`
- `workout`: `create`, `validate`, `list`, `get`, `delete`, `schedule`, `unschedule`, `scheduled`, `schema`
- `activity`: `list`, `get`, `download`
- `health`: `steps`, `heart-rate`, `sleep`, `body-battery`, `hrv`, `stress`, `weight`
- `stats`: `summary`, `training-status`, `readiness`, `records`, `progress`

Dates accept `YYYY-MM-DD`, `today`, `yesterday`, `-7d`, `+7d`, and ranges `start:end`.
```

- [ ] **Step 4: Run the whole suite once more**

Run: `uv run pytest -v`
Expected: PASS (all tests).

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_e2e_offline.py
git commit -m "docs: README and offline end-to-end tests"
```

---

## Self-Review Notes

- **Spec coverage:** auth (§3) → Tasks 7–8; envelope/exit codes (§4) → Task 2; workout input sources + single/batch + create-and-schedule + failure semantics (§5) → Tasks 5,6,10; data commands (§6) → Tasks 11–13; date shorthands (§7) → Task 4; capabilities (§8) → Task 14; slim + `--full` (§9.1) → Tasks 9,11; TOON (§9.2) → Tasks 2,15; testing (§11) → every task. All spec sections mapped.
- **Deviation logged:** `activity download` uses `--format-file` (not `--format`) because `--format` is the reserved global json/toon option; noted in Task 11.
- **Deviation logged:** translation builds `ExecutableStep`/`RepeatGroup` models directly rather than via the library's `create_*` helpers, because those helpers do not attach target *values* (§5.2's intent — mapping onto the library's typed models — is preserved).
- **`get_scheduled_workouts` is per (year, month)** — the `scheduled` command iterates months across the range (Task 10).
- **Type consistency:** `load_client`, `command_output`, `emit_batch`, `project`, `parse_date`, `parse_range`, `load_plan`, `translate`, `summarize` names are used identically across producing and consuming tasks.
