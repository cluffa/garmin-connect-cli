---
name: garmin-connect
version: 0.3.0
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

**Repo:** `github.com/cluffa/garmin-connect-cli` — this skill ships inside
the CLI repo at `skills/garmin-connect/`, so it is versioned alongside the
interface it documents.

## Install

The CLI is not on PyPI — install it from GitHub with `uv`:

```bash
uv tool install git+https://github.com/cluffa/garmin-connect-cli
```

This exposes a `garmin` executable on your PATH (via `~/.local/bin`), so you
can run it from any directory. Pin a branch or tag by appending `@ref`, e.g.
`...garmin-connect-cli@main`.

Upgrade or reinstall later:

```bash
uv tool upgrade garmin-cli                                    # pull latest
uv tool install --reinstall git+https://github.com/cluffa/garmin-connect-cli
```

If `garmin` isn't found after install, ensure uv's bin dir is on PATH with
`uv tool update-shell` (then restart the shell).

### Installing this skill

The skill lives in the CLI repo. Clone it and link the skill directory into
your Claude Code skills path so the two stay in lockstep:

```bash
git clone https://github.com/cluffa/garmin-connect-cli
ln -s "$PWD/garmin-connect-cli/skills/garmin-connect" ~/.claude/skills/garmin-connect
```

Copying instead of symlinking works too, but then `git pull` no longer keeps
the skill current with the CLI.

## Setup

```bash
export GARMIN_EMAIL=you@example.com
export GARMIN_PASSWORD=your-password
garmin auth login  # prompts for MFA if enabled; caches token
```

The CLI shares its token store with the
[Garmin Workout Pipeline MCP server](https://github.com/cluffa/Garmin-Workout-Pipeline),
so a single `auth login` works for both tools. The token is cached under the
home directory, so it persists across CLI upgrades and reinstalls.

If the user hasn't authenticated yet, walk them through `auth login` first
before running data commands. Check auth status with `auth status`.

## Invocation

Once installed, run `garmin` directly from any directory:

```bash
garmin [global options] <command> [args]
```

(If you're working from a source checkout instead of an installed tool, run the
same commands as `uv run garmin ...` from the CLI repo root.)

## Global Options

| Option | Default | Description |
|--------|---------|-------------|
| `--format json` | yes | Compact JSON (default) |
| `--format json-pretty` | — | Indented, human-readable JSON |
| `--format toon` | — | Compact tabular output |
| `--full` | — | Return raw Garmin API payloads instead of slim projections |

Global options go **before** the sub-command:

```bash
garmin --format json-pretty activity list
garmin --full stats summary today
```

## Agent-First Patterns

### Always check the envelope

```bash
result=$(garmin activity list 2>&1)
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
garmin activity list | jq '.data[:3] | .[] | {name: .activityName, date: .startTimeLocal}'
```

### Use json-pretty for human display

When showing data to the user, prefer `--format json-pretty`:

```bash
garmin --format json-pretty activity get 12345
```

### Streaming binary/JSON to stdout

For `activity download`, use `--out -` to stream raw data to stdout:

```bash
# Stream TCX to a pipe
garmin activity download 123 --format-file tcx --out - | gzip > activity.tcx.gz

# Stream parsed JSON to jq
garmin activity download 123 --format-file json --out - | jq '.record_mesgs[:10]'
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
garmin auth login      # Authenticate (prompts for MFA)
garmin auth status     # Check if token is valid
garmin auth logout     # Delete cached token
```

### `activity` — Retrieve Activities

```bash
# List recent activities (slim projection by default)
garmin activity list
garmin activity list --limit 10
garmin activity list --type running
garmin activity list --miles          # distances in miles, pace/mi
garmin --full activity list           # raw API payload

# Get one activity's details
garmin activity get <activity_id>
garmin --full activity get <activity_id>

# Lap/split data with mile paces, HR, cadence, stride, power
garmin activity splits <activity_id>

# Download activity file (binary formats)
garmin activity download <id> --format-file tcx
garmin activity download <id> --format-file gpx --out run.gpx
garmin activity download <id> --format-file fit

# Download and parse FIT to structured JSON (uses official Garmin FIT SDK)
garmin activity download <id> --format-file json
garmin activity download <id> --format-file json --out - | jq '.record_mesgs[0]'

# Stream any format to stdout
garmin activity download <id> --format-file tcx --out - | head
```

**JSON format details:** `--format-file json` downloads the raw FIT file,
extracts it from the zip, and parses it with the official Garmin FIT SDK.
Output includes `record_mesgs` (GPS track points with HR, cadence, altitude,
speed, power), `lap_mesgs`, `session_mesgs`, `physiological_metrics_mesgs`
(VO₂ max, training load, recovery time, lactate threshold), and 30+ other
message types. Numeric-only message types are community-mapped to readable
names where known (fit4ruby/Intervals.icu sources).

### `health` — Health & Wellness

Every command here takes a date **or a range**:

```bash
garmin health steps today
garmin health steps -7d:today
garmin health heart-rate -7d:today
garmin health sleep -30d:today
garmin health body-battery -7d:today
garmin health hrv -90d:today
garmin health stress -30d:today
garmin health weight -30d:today

# Weekly aggregates — 52 weeks in a single request
garmin health weekly-steps
garmin health weekly-stress --weeks 12
```

**Prefer a range over a loop.** Never shell-loop day by day; pass the range
and let the CLI do it. One command returns one array, instead of N tool
results filling your context.

#### Two response shapes

`steps`, `body-battery`, `weight`, `weekly-steps`, and `weekly-stress` hit
range-capable Garmin endpoints — one request, whatever the span, and the
payload comes back as the API returns it.

`heart-rate`, `sleep`, `hrv`, and `stress` have no upstream range endpoint,
so a range costs **one request per day**. For these:

- A **single date** returns that day's payload directly (a dict).
- A **range** returns an array of `{"date": "YYYY-MM-DD", "data": {...}}`,
  ascending, one entry per day inclusive.

```bash
garmin health hrv -7d:today | jq '.data[] | {date, avg: .data.weeklyAvg}'
```

Days with no recording come back as `"data": null`. A day whose request
fails gets `"data": null` plus an `"error"` string and the rest of the range
still returns — check for `error` keys rather than assuming every entry is
good. If *every* day fails, the command exits 4 with an `api` error.

Ranges are capped at **366 days** to avoid hammering an undocumented API;
past that you get a `usage` error. Raise it deliberately with `--max-days`
if you truly need more.

### `stats` — Summaries & Training Status

```bash
garmin stats summary today       # steps, distance, HR, floors, calories, SpO₂
garmin stats training-status today
garmin stats training-status -30d:today   # one entry per day
garmin stats readiness today
garmin stats readiness -14d:today         # one entry per day
garmin stats records             # personal records
garmin stats progress -30d today # progress between two dates
garmin stats weekly              # weekly running volume breakdown
```

`training-status` and `readiness` are single-date upstream, so they follow
the same two-shape rule as `health hrv` above: bare date → dict, range →
array of `{"date", "data"}` at one request per day, `--max-days` capped.

### `workout` — Create & Manage Workouts

```bash
# Validate a workout spec (dry-run)
garmin workout validate --json '{"workouts":[{"name":"Easy 5k","sport":"running","steps":[{"type":"warmup","duration":{"time":"10min"}},{"type":"interval","duration":{"distance":"5km"},"target":{"pace":["5:30/km","5:00/km"]}},{"type":"cooldown","duration":{"time":"5min"}}]}]}'

# Validate from file
garmin workout validate --file workout.json

# Create and schedule a workout
garmin workout create --json '{"workouts":[{"name":"Track","sport":"running","date":"2026-07-22","steps":[...]}]}'

# List saved workouts
garmin workout list

# Get/delete a workout
garmin workout get <id>
garmin workout delete <id>

# Schedule/unschedule
garmin workout schedule <id> <date>
garmin workout unschedule <id>

# List scheduled workouts for a date range
garmin workout scheduled today:+7d

# Get the workout JSON schema
garmin workout schema
```

**Workout step types:** `warmup`, `interval`, `recovery`, `cooldown`
**Duration:** `{"time": "10min"}` or `{"distance": "5km"}`
**Target (optional):** `{"pace": ["5:30/km", "5:00/km"]}`, `{"hr": [140, 155]}`, `{"power": [200, 250]}`
**Repeat groups:** `{"repeat": 5, "steps": [...]}`
**Notes:** optional `"note"` per step, `"notes"` per workout

### `badge` — Badges & Challenges

```bash
garmin badge earned --limit 10
garmin badge in-progress
garmin badge available --start 0 --limit 20
garmin badge adhoc --start 0 --limit 20
garmin badge challenges
```

### `capabilities` — Agent Discovery

```bash
garmin capabilities
```

Returns the full command tree plus workout JSON schema in one call. Use this
to discover the interface if you're unsure what commands are available.

## Common Recipes

### "How was my run today?"

```bash
garmin activity list --type running --limit 1 | jq '.data[0] | {name, distance, duration, pace: .averageSpeed, hr: .averageHR}'
```

### "What's my weekly mileage?"

```bash
garmin stats weekly | jq '.data'
```

### "How did I sleep last night?"

```bash
garmin --format json-pretty health sleep yesterday
```

### "Show me my HRV trend this week"

```bash
garmin health hrv -7d:today | jq '.data[] | {date, avg: .data.weeklyAvg}'
```

Do **not** loop a day at a time — one range call replaces seven, and keeps
seven tool results out of your context.

### "How has my training load trended this month?"

```bash
garmin stats training-status -30d:today | jq '.data[] | {date, load: .data.load, status: .data.status}'
```

### "Am I sleeping less than I was?"

```bash
garmin health sleep -60d:today | jq '[.data[] | select(.data != null) | .data.duration_hours] | add / length'
```

### "What's my step trend over the past year?"

```bash
# One request, 52 weekly aggregates — no per-day fetching.
garmin health weekly-steps | jq '.data[] | {week: .calendarDate, steps: .totalSteps}'
```

### "What's my VO₂ max?"

```bash
# Download the FIT file for a recent run and extract physiological metrics
garmin activity download <recent_run_id> --format-file json --out - | \
  jq '.physiological_metrics_mesgs[0] | {vo2max_ml_kg_min: (.metmax * 3.5 / 65536), performance_condition}'
```

### "Create a workout for me"

Write the spec as JSON (see workout schema above), validate with `workout validate`,
then create with `workout create`. Ask the user for: sport, duration/distance,
intensity, and any interval structure they want.

### "I got a new personal record — show me"

```bash
garmin stats records | jq '.data'
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

This skill documents the garmin-connect-cli interface and lives in the same
repo as that interface, at `skills/garmin-connect/SKILL.md`. Any change to a
command, flag, output format, or error type belongs in the same commit as the
update to this file — that is the reason the two are not separate repos. See
the repo's `CLAUDE.md` for the version-sync rule.
