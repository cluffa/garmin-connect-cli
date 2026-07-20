---
name: garmin-connect
description: >
  Use this skill whenever the user asks about Garmin Connect data — retrieving
  activities, health metrics, sleep, steps, heart rate, body battery, HRV,
  stress, training status, readiness, personal records, badges, workouts,
  or any fitness data from Garmin. Also trigger when the user mentions
  "garmin", "garmin connect", "garmin-cli", "my run today", "how did I sleep",
  "what's my vo2max", "create a workout", "schedule a run", "download my
  activity", or similar fitness-tracking queries. This skill should be
  consulted BEFORE running any garmin CLI commands so the agent knows the
  available commands, output formats, and error-handling patterns.
---

# Garmin Connect CLI

Agent-first CLI for Garmin Connect. Every command emits a consistent JSON
envelope `{"ok":true,"data":...}` or `{"ok":false,"error":{...}}` — no
screen-scraping needed.

**Repo:** `github.com/cluffa/garmin-connect-cli`
**Skill repo:** `github.com/cluffa/garmin-connect-skill`

## Setup

```bash
export GARMIN_EMAIL=you@example.com
export GARMIN_PASSWORD=your-password
uv run garmin auth login  # prompts for MFA if enabled; caches token
```

The CLI shares its token store with the
[Garmin Workout Pipeline MCP server](https://github.com/cluffa/Garmin-Workout-Pipeline),
so a single `auth login` works for both tools.

If the user hasn't authenticated yet, walk them through `auth login` first
before running data commands. Check auth status with `auth status`.

## Invocation

All commands are run from the CLI repo root:

```bash
cd /path/to/garmin-connect-cli
uv run garmin [global options] <command> [args]
```

## Global Options

| Option | Default | Description |
|--------|---------|-------------|
| `--format json` | yes | Compact JSON (default) |
| `--format json-pretty` | — | Indented, human-readable JSON |
| `--format toon` | — | Compact tabular output |
| `--full` | — | Return raw Garmin API payloads instead of slim projections |

Global options go **before** the sub-command:

```bash
uv run garmin --format json-pretty activity list
uv run garmin --full stats summary today
```

## Agent-First Patterns

### Always check the envelope

```bash
result=$(uv run garmin activity list 2>&1)
exit_code=$?
```

- **exit_code 0**: `result.stdout` is `{"ok":true,"data":...}` — parse with `jq`
- **exit_code ≠ 0**: `result.stderr` is `{"ok":false,"error":{"type":"...","message":"..."}}` — check `error.type` to decide what to do

### Error type guide

| Type | Meaning | Agent should |
|------|---------|-------------|
| `auth` | No valid token | Tell user to run `auth login` |
| `usage` | Bad arguments | Fix the command and retry |
| `api` | Garmin API error | Report the message, maybe retry |
| `internal` | Unexpected bug | Report the error |

### Pipe to jq

Every command returns JSON on stdout (or stderr for errors). Use `jq` to
extract what you need:

```bash
uv run garmin activity list | jq '.data[:3] | .[] | {name: .activityName, date: .startTimeLocal}'
```

### Use json-pretty for human display

When showing data to the user, prefer `--format json-pretty`:

```bash
uv run garmin --format json-pretty activity get 12345
```

### Streaming binary/JSON to stdout

For `activity download`, use `--out -` to stream raw data to stdout:

```bash
# Stream TCX to a pipe
uv run garmin activity download 123 --format-file tcx --out - | gzip > activity.tcx.gz

# Stream parsed JSON to jq
uv run garmin activity download 123 --format-file json --out - | jq '.record_mesgs[:10]'
```

## Date Specifications

All date parameters accept these formats:

| Format | Example | Description |
|--------|---------|-------------|
| `YYYY-MM-DD` | `2026-07-21` | Absolute date |
| `today` | — | Current date |
| `yesterday` | — | Current date minus 1 day |
| `-Nd` | `-7d` | N days ago |
| `+Nd` | `+7d` | N days from now |
| `start:end` | `-7d:today` | Date range |
| `YYYY-MM-DD:YYYY-MM-DD` | `2026-07-01:2026-07-31` | Absolute range |

## Commands

### `auth` — Authentication

```bash
uv run garmin auth login      # Authenticate (prompts for MFA)
uv run garmin auth status     # Check if token is valid
uv run garmin auth logout     # Delete cached token
```

### `activity` — Retrieve Activities

```bash
# List recent activities (slim projection by default)
uv run garmin activity list
uv run garmin activity list --limit 10
uv run garmin activity list --type running
uv run garmin activity list --miles          # distances in miles, pace/mi
uv run garmin --full activity list           # raw API payload

# Get one activity's details
uv run garmin activity get <activity_id>
uv run garmin --full activity get <activity_id>

# Lap/split data with mile paces, HR, cadence, stride, power
uv run garmin activity splits <activity_id>

# Download activity file (binary formats)
uv run garmin activity download <id> --format-file tcx
uv run garmin activity download <id> --format-file gpx --out run.gpx
uv run garmin activity download <id> --format-file fit

# Download and parse FIT to structured JSON (uses official Garmin FIT SDK)
uv run garmin activity download <id> --format-file json
uv run garmin activity download <id> --format-file json --out - | jq '.record_mesgs[0]'

# Stream any format to stdout
uv run garmin activity download <id> --format-file tcx --out - | head
```

**JSON format details:** `--format-file json` downloads the raw FIT file,
extracts it from the zip, and parses it with the official Garmin FIT SDK.
Output includes `record_mesgs` (GPS track points with HR, cadence, altitude,
speed, power), `lap_mesgs`, `session_mesgs`, `physiological_metrics_mesgs`
(VO₂ max, training load, recovery time, lactate threshold), and 30+ other
message types. Numeric-only message types are community-mapped to readable
names where known (fit4ruby/Intervals.icu sources).

### `health` — Health & Wellness

```bash
uv run garmin health steps today
uv run garmin health steps -7d:today
uv run garmin health heart-rate today
uv run garmin health sleep yesterday
uv run garmin health body-battery today
uv run garmin health body-battery -7d:today
uv run garmin health hrv today
uv run garmin health stress today
uv run garmin health weight -30d:today
```

### `stats` — Summaries & Training Status

```bash
uv run garmin stats summary today       # steps, distance, HR, floors, calories, SpO₂
uv run garmin stats training-status today
uv run garmin stats readiness today
uv run garmin stats records             # personal records
uv run garmin stats progress -30d today # progress between two dates
uv run garmin stats weekly              # weekly running volume breakdown
```

### `workout` — Create & Manage Workouts

```bash
# Validate a workout spec (dry-run)
uv run garmin workout validate --json '{"workouts":[{"name":"Easy 5k","sport":"running","steps":[{"type":"warmup","duration":{"time":"10min"}},{"type":"interval","duration":{"distance":"5km"},"target":{"pace":["5:30/km","5:00/km"]}},{"type":"cooldown","duration":{"time":"5min"}}]}]}'

# Validate from file
uv run garmin workout validate --file workout.json

# Create and schedule a workout
uv run garmin workout create --json '{"workouts":[{"name":"Track","sport":"running","date":"2026-07-22","steps":[...]}]}'

# List saved workouts
uv run garmin workout list

# Get/delete a workout
uv run garmin workout get <id>
uv run garmin workout delete <id>

# Schedule/unschedule
uv run garmin workout schedule <id> <date>
uv run garmin workout unschedule <id>

# List scheduled workouts for a date range
uv run garmin workout scheduled today:+7d

# Get the workout JSON schema
uv run garmin workout schema
```

**Workout step types:** `warmup`, `interval`, `recovery`, `cooldown`
**Duration:** `{"time": "10min"}` or `{"distance": "5km"}`
**Target (optional):** `{"pace": ["5:30/km", "5:00/km"]}`, `{"hr": [140, 155]}`, `{"power": [200, 250]}`
**Repeat groups:** `{"repeat": 5, "steps": [...]}`
**Notes:** optional `"note"` per step, `"notes"` per workout

### `badge` — Badges & Challenges

```bash
uv run garmin badge earned --limit 10
uv run garmin badge in-progress
uv run garmin badge available --start 0 --limit 20
uv run garmin badge adhoc --start 0 --limit 20
uv run garmin badge challenges
```

### `capabilities` — Agent Discovery

```bash
uv run garmin capabilities
```

Returns the full command tree plus workout JSON schema in one call. Use this
to discover the interface if you're unsure what commands are available.

## Common Recipes

### "How was my run today?"

```bash
uv run garmin activity list --type running --limit 1 | jq '.data[0] | {name, distance, duration, pace: .averageSpeed, hr: .averageHR}'
```

### "What's my weekly mileage?"

```bash
uv run garmin stats weekly | jq '.data'
```

### "How did I sleep last night?"

```bash
uv run garmin --format json-pretty health sleep yesterday
```

### "Show me my HRV trend this week"

```bash
for i in $(seq 6 -1 0); do
  uv run garmin health hrv -${i}d | jq '.data'
done
```

### "What's my VO₂ max?"

```bash
# Download the FIT file for a recent run and extract physiological metrics
uv run garmin activity download <recent_run_id> --format-file json --out - | \
  jq '.physiological_metrics_mesgs[0] | {vo2max_ml_kg_min: (.metmax * 3.5 / 65536), performance_condition}'
```

### "Create a workout for me"

Write the spec as JSON (see workout schema above), validate with `workout validate`,
then create with `workout create`. Ask the user for: sport, duration/distance,
intensity, and any interval structure they want.

### "I got a new personal record — show me"

```bash
uv run garmin stats records | jq '.data'
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Internal error |
| 2 | Usage error |
| 3 | Auth error |
| 4 | API error / partial failure |

## Keeping This Skill Current

This skill documents the garmin-connect-cli interface. The source of truth
for commands, flags, and behavior is the CLI repo at
`github.com/cluffa/garmin-connect-cli`. When the CLI gains new commands,
changes flags, or alters output format, this SKILL.md must be updated to
match. See the CLAUDE.md in this repo for cross-repo update instructions.
