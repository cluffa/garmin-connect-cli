# Garmin Connect Agent-First CLI — Design

**Date:** 2026-07-15
**Status:** Approved for planning

## 1. Purpose & Philosophy

A command-line tool that wraps [`python-garminconnect`](https://github.com/cyberjunky/python-garminconnect)
so an **external AI agent** (Claude Code, a custom coach, etc.) can program workouts and
retrieve Garmin data by calling the CLI as a set of tools.

The app contains **no LLM**. It is a clean, deterministic tool surface designed for
machine consumption first: structured output, machine-readable errors, meaningful exit
codes, one-call discovery, inline JSON input, and token-efficient responses. Humans can
use it too, but every design tradeoff favors the agent.

Distribution: a `uv`-managed Python app exposing a single `garmin` command.

## 2. Stack & Layout

- **Language/tooling:** Python, packaged and run via `uv`.
- **CLI framework:** [Typer](https://typer.tiangolo.com/) (Click-based) for nested
  subcommands and generated help.
- **Garmin access:** `python-garminconnect`, including its typed workout builders in
  `garminconnect.workout` (pydantic models + `create_*` step helpers).
- **Output format:** `python-toon` (imports as `toon`, provides `encode()`) for optional
  TOON encoding (see §8). Note: the `toon-format` package is only a namespace reservation
  with no working encoder, so `python-toon` is used instead.

```
garmin-connect-cli/
  pyproject.toml            # uv project, entry point: garmin = garmin_cli.cli:app
  src/garmin_cli/
    __init__.py
    cli.py                  # Typer app; wires command groups; global --format/--full
    client.py               # session/auth: build Garmin client, token cache, load-or-fail
    output.py               # envelope, error mapping, exit codes, json/toon rendering
    dates.py                # date shorthand parsing (C)
    commands/
      auth.py               # login, status, logout
      workout.py            # create, validate, list, get, delete, schedule, unschedule, scheduled, schema
      activity.py           # list, get, download
      health.py             # steps, heart-rate, sleep, body-battery, hrv, stress, weight
      stats.py              # summary, training-status, readiness, records, progress
      meta.py               # capabilities (B)
    workouts/
      schema.py             # simplified spec pydantic model + JSON-schema export
      translate.py          # simplified spec -> garminconnect.workout builders
      units.py              # "10min","1km","400m","1mi","4:00/km" -> secs/meters/mps
    projections.py          # slim views for big read endpoints (A)
  tests/
```

## 3. Authentication (`garmin auth`)

Token-based via Garth, with an on-disk cache so normal commands never prompt.

- **`auth login`** — reads `GARMIN_EMAIL` / `GARMIN_PASSWORD` from the environment, logs in,
  and caches the OAuth token to `~/.garmin-cli/` (override via `GARMINTOKENS` env var).
  MFA is handled **interactively** (prompts for the code) — this is the one command a human
  is expected to run.
- **`auth status`** — reports whether a valid cached token exists.
- **`auth logout`** — clears the cached token.

All other commands call a shared `load_client()` that silently loads the cached token.
If it is missing or expired, they return a structured auth error (§4) with exit code `3`
and **never** drop into an interactive prompt — an agent gets a clean, actionable failure.

## 4. Output & Error Contract

Every command prints a JSON envelope to **stdout** on success:

```json
{ "ok": true, "data": { } }
```

Errors print an envelope to **stderr** with a nonzero exit code:

```json
{ "ok": false, "error": { "type": "auth", "message": "No valid token; run `garmin auth login`." } }
```

**Error types:** `usage`, `auth`, `api`, `internal`.

**Exit codes:**

| code | meaning |
|------|---------|
| 0 | success |
| 2 | bad usage / invalid input or workout schema |
| 3 | auth (no/expired token) |
| 4 | Garmin API error (incl. batch with any failed item) |
| 1 | other/internal |

Output is compact JSON (not pretty-printed) by default. Errors carry a short message only —
no stack traces on stdout.

## 5. Workouts (`garmin workout`)

### 5.1 Input sources

Commands that take a spec accept **exactly one** of:

- `--json '<inline string>'` — the agent's primary path, no temp files
- `--file <path>`
- stdin (piped)

### 5.2 Simplified workout spec (running + cycling)

Authored against a stable, documented schema that `translate.py` maps onto the library's
typed builders. A single workout **or** a batch ("plan") is accepted; a bare single-workout
object is normalized to a batch of one.

```json
{
  "workouts": [
    { "name": "Tue Intervals", "sport": "running", "date": "2026-07-21",
      "steps": [
        { "type": "warmup", "duration": { "time": "10min" } },
        { "repeat": 5, "steps": [
          { "type": "interval", "duration": { "distance": "1km" }, "target": { "pace": ["4:00/km", "3:50/km"] } },
          { "type": "recovery", "duration": { "time": "2min" } }
        ]},
        { "type": "cooldown", "duration": { "time": "10min" } }
      ]
    },
    { "name": "Sat Long Ride", "sport": "cycling", "date": "2026-07-25",
      "steps": [
        { "type": "warmup", "duration": { "time": "15min" } },
        { "type": "interval", "duration": { "time": "60min" }, "target": { "power": [180, 210] } },
        { "type": "cooldown", "duration": { "time": "10min" } }
      ]
    }
  ]
}
```

**Fields**

- **`name`** (required), **`sport`** (`running` | `cycling`).
- **`date`** (optional, `YYYY-MM-DD` or a date shorthand from §7): present → create then
  `schedule_workout` onto that date; absent → create only. This is what merges create +
  schedule so a whole week is one JSON, one command.
- **`steps`**: ordered list. Step `type` ∈ `warmup | interval | recovery | cooldown`. A
  repeat block is `{ "repeat": <n>, "steps": [ ... ] }` (nestable).
- **`duration`**: exactly one of `time` (`"10min"`, `"90s"`) or `distance`
  (`"1km"`, `"400m"`, `"1mi"`).
- **`target`** (optional; omit = no target), `[min, max]`:
  - running: `pace` (e.g. `"4:00/km"`) or `hr` (bpm)
  - cycling: `power` (watts), `speed`, or `hr` (bpm)
  - `translate.py` converts to Garmin's units (pace → m/s, etc.) and builds the
    `targetType` + `targetValueOne/Two` fields.
- `estimatedDurationInSecs` is computed: exact for time steps, estimated from pace/speed
  target for distance steps.

Translation targets `garminconnect.workout`: `RunningWorkout`/`CyclingWorkout`,
`WorkoutSegment`, `create_warmup_step`, `create_interval_step`,
`create_distance_interval_step`, `create_recovery_step`, `create_cooldown_step`,
`create_repeat_group`, then `upload_workout(model.to_dict())`.

### 5.3 Commands

- **`create`** — validate → translate → upload each workout; if `date` present, schedule it.
  Single or batch. Continue-on-error with per-item results (§5.4).
- **`validate`** (D, dry-run) — validate + translate + compute the step breakdown and
  estimated duration, returning the same per-item shape as `create` **without uploading**.
  Side-effect-free verification of agent-generated JSON.
- **`list`** — `get_workouts` (slim by default).
- **`get <id>`** — `get_workout_by_id`.
- **`delete <id>`** — `delete_workout`.
- **`schedule <id> <date>`** — `schedule_workout` an existing workout.
- **`unschedule <scheduled_id>`** — `unschedule_workout`.
- **`scheduled <date|range>`** (E) — `get_scheduled_workouts`; what's already on the
  calendar, so a coach avoids double-booking.
- **`schema`** — emits the simplified-spec JSON schema (incl. the batch/`date` format) so an
  agent can self-discover it.

### 5.4 Batch result & failure semantics

Continue-on-error; report per item. Successful items are **not** rolled back.

```json
{ "ok": false,
  "data": { "results": [
    { "index": 0, "name": "Tue Intervals",  "ok": true,  "workoutId": 123, "scheduledId": 456 },
    { "index": 1, "name": "Sat Long Ride",  "ok": false, "error": { "type": "api", "message": "..." } }
  ], "created": 1, "failed": 1 } }
```

Top-level `ok` is `true` only if every item succeeded; otherwise exit code `4`. The agent
sees exactly which workouts landed and which to retry.

## 6. Data Commands

Thin wrappers returning the library's data inside the envelope, with slim projections (§9).

- **`activity list [--limit] [--start] [--type]`** — `get_activities`.
- **`activity get <id>`** — activity details.
- **`activity download <id> --format tcx|gpx|fit`** — writes the file, returns its path.
- **`health steps <date|range>`** — `get_daily_steps` / `get_weekly_steps`.
- **`health heart-rate <date>`** — `get_heart_rates`.
- **`health sleep <date>`** — `get_sleep_data`.
- **`health body-battery <date|range>`** — `get_body_battery`.
- **`health hrv <date>`** — `get_hrv_data`.
- **`health stress <date>`** — `get_stress_data`.
- **`health weight <date|range>`** — `get_weigh_ins` / `get_daily_weigh_ins`.
- **`stats summary <date>`** — `get_user_summary` / `get_stats`.
- **`stats training-status <date>`** — `get_training_status`.
- **`stats readiness <date>`** — `get_training_readiness`.
- **`stats records`** — `get_personal_record`.
- **`stats progress <start> <end>`** — `get_progress_summary_between_dates`.

## 7. Date Handling (C)

All date/range arguments accept, in addition to `YYYY-MM-DD`:

- `today`, `yesterday`
- relative offsets, past or future: `-7d` (7 days ago), `-1w`, `+7d` (7 days ahead)
- ranges: `start:end` (e.g. `2026-07-01:2026-07-07`, `-7d:today`, or `-7d:+7d`)

Parsed centrally in `dates.py` so the agent never computes calendar math. "Today" resolves
to the local date on the invoking machine.

## 8. Discovery (B) — `garmin capabilities`

`garmin capabilities` emits a single machine-readable payload describing every command, its
arguments/options, and the workout JSON schema. This lets an agent load the entire tool
surface in one call on its first turn instead of walking `--help` per command.

## 9. Token Efficiency

### 9.1 Slim projections + `--full` (A)

Big read endpoints (`activity get`, `activity list`, `health sleep`, `stats summary`, …)
return a **curated summary** by default (e.g. activity → date, type, distance, duration,
avg/max HR, pace, training effect). `--full` returns the raw library payload. Projections
live in `projections.py`, keyed by endpoint.

### 9.2 TOON output — global `--format json|toon`

- Default `json`, the stable guaranteed contract. `--format toon` encodes the **full
  envelope** as TOON (via `python-toon`'s `toon.encode()`) on stdout. Inputs remain JSON
  (encode-only).
- Biggest win on uniform arrays of objects: `activity list`, `health steps`, weekly steps,
  `stats progress`, `workout list`/`scheduled`, and batch `results`. Marginal on single
  nested blobs — hence per-call.
- `python-toon` is 0.1.x; keeping JSON as the default and TOON strictly opt-in ensures the
  early format never threatens the core contract.

Minimal-token path: slim + TOON. Everything path: `--full --format json`.

## 10. Coaching Loop (motivating use case)

The features compose into an AI-coach cycle:

1. **Read state (slim):** `stats readiness`, `stats training-status`, recent `activity list`,
   `health sleep` / `health hrv`.
2. **Check the calendar (E):** `workout scheduled -7d:+7d` to see what's already programmed.
3. **Generate a plan:** the agent produces one batch JSON for the week.
4. **Dry-run (D):** `workout validate --json '...'` to confirm structure + durations, no
   side effects.
5. **Commit:** `workout create --json '...'` create-and-schedules the whole week in one call.

## 11. Testing

- **pytest.** No live Garmin API calls in CI.
- **High-value pure logic** gets thorough unit tests: `units.py` (parsing durations, paces,
  distances) and `translate.py` (simplified spec → builder payloads, incl. repeats, targets,
  estimated duration).
- **`dates.py`** shorthand parsing unit-tested.
- **Command tests** mock the Garmin client and assert envelope shape, exit codes, batch
  continue-on-error behavior, and slim-vs-`--full` projections.

## 12. Out of Scope (v1)

- Sports beyond running and cycling (swim/strength/multi-sport) — schema is extensible later.
- Raw Garmin workout payload passthrough (`--raw`).
- Any embedded LLM / chat mode / MCP server.
- Decoding TOON input.
