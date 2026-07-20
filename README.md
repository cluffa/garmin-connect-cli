# garmin-cli

**Agent-first CLI for Garmin Connect.** Every command emits a consistent JSON
envelope designed to be consumed programmatically — by AI agents, shell
pipelines, or other tools — without screen-scraping or fragile text parsing.

- JSON envelope: `{"ok":true,"data":...}` or `{"ok":false,"error":{...}}`
- Meaningful exit codes (0 = success, 1 = internal error, 2 = usage, 3 = auth,
  4 = API/failure)
- TOON output available with `--format toon` for human-friendly tables; `--format json-pretty` for indented JSON
- Unified date-spec across all commands (`today`, `yesterday`, `-7d`, `+7d`,
  `start:end`, `YYYY-MM-DD`, `YYYY-MM-DD:YYYY-MM-DD`)
- Optional `--full` flag to return raw Garmin API payloads instead of slim
  projections

## Setup

```bash
uv sync
export GARMIN_EMAIL=you@example.com
export GARMIN_PASSWORD=your-password
uv run garmin auth login        # prompts for MFA if enabled; caches token
```

Credentials are sourced from the `GARMIN_EMAIL` and `GARMIN_PASSWORD`
environment variables. The authenticated session token is cached and reused on
subsequent calls.

### Token store

The CLI shares its token store with the
[Garmin Workout Pipeline MCP server](https://github.com/cluffa/Garmin-Workout-Pipeline),
so a single login works for both tools. The store is resolved in this order:

1. `$GARMINTOKENS`, when set — explicit override.
2. `~/.garmin-workout-pipeline/tokens` — the MCP server's token store (default).
   Authenticate through either tool and the other reuses the same session.
3. `~/.garmin-cli/` — legacy CLI-only location, used only when it already holds
   a token and the MCP store does not.

## Global Options

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `json` | Output format: `json` (compact), `json-pretty` (indented), or `toon` (tabular) |
| `--full` | — | Return raw Garmin API payloads instead of slim projections |

Place global options **before** the sub-command:

```bash
uv run garmin --format toon activity list
uv run garmin --full stats summary today
```

## One-Call Discovery

```bash
uv run garmin capabilities
```

Lists every registered command (name + help text) alongside the workout JSON
schema — everything an agent needs to discover the interface in a single call.

## Commands

### `auth` — Authentication

| Command | Description |
|---------|-------------|
| `auth login` | Authenticate with `GARMIN_EMAIL`/`GARMIN_PASSWORD`; prompts for MFA |
| `auth status` | Check whether a valid cached token exists |
| `auth logout` | Delete the cached token |

### `workout` — Create and manage workouts

| Command | Description |
|---------|-------------|
| `workout validate --json '<spec>'` | Dry-run: validate and translate a spec without uploading |
| `workout validate --file spec.json` | Same, from a JSON file |
| `workout validate` | Same, read JSON from stdin |
| `workout create --json '<spec>'` | Validate, upload, and (if `date` set) schedule workouts |
| `workout list` | List saved workouts |
| `workout get <id>` | Get one workout by ID |
| `workout delete <id>` | Delete a workout |
| `workout schedule <id> <date>` | Schedule an existing workout to a date |
| `workout unschedule <id>` | Remove a scheduled workout |
| `workout scheduled <range>` | List scheduled workouts for a date or range |
| `workout schema` | Print the workout JSON schema |

**Workout spec format** (JSON):

```json
{
  "workouts": [
    {
      "name": "Wk1 Tue",
      "sport": "running",
      "date": "2026-07-21",
      "notes": "cruise intervals at one-hour effort",
      "steps": [
        {"type": "warmup", "duration": {"time": "10min"}, "note": "easy Z1–Z2"},
        {
          "repeat": 5,
          "steps": [
            {"type": "interval", "duration": {"distance": "1km"}, "target": {"pace": ["4:00/km", "3:50/km"]}, "note": "one-hour effort"},
            {"type": "recovery", "duration": {"time": "2min"}}
          ]
        },
        {"type": "cooldown", "duration": {"time": "10min"}}
      ]
    }
  ]
}
```

- **Step types:** `warmup`, `interval`, `recovery`, `cooldown`
- **Duration:** `time` (`"10min"`, `"45s"`) or `distance` (`"1km"`, `"400m"`, `"1mi"`)
- **Target:** optional `pace` (running), `speed`, `power` (cycling), or `hr`
- **Note:** optional per-step `note` — free text shown as the step's note on the watch
- **Notes:** optional per-workout `notes` — free text set as the workout description
- **Repeat groups:** `{"repeat": N, "steps": [...]}` for intervals
- **Date:** optional; when present, `create` also schedules the workout
- **Batch:** a single spec can include multiple workouts; partial failures report
  individually

**Input sources** (for `validate` and `create`):

| Source | Example |
|--------|---------|
| `--json '<spec>'` | Inline JSON string |
| `--file spec.json` | Path to JSON file |
| stdin | Pipe or heredoc |

Provide exactly one source; `UsageError` is raised otherwise.

### `activity` — Retrieve activities

| Command | Description |
|---------|-------------|
| `activity list` | Recent activities (slim; use `--full` for raw) |
| `activity list --limit 50 --type running` | Filtered list |
| `activity list --miles` | List activities with distances in miles and pace per mile |
| `activity get <id>` | One activity's details (slim) |
| `activity download <id> --format-file tcx` | Download TCX, GPX, or FIT file |
| `activity download <id> --format-file gpx --out race.gpx` | Download with custom output path |
| `activity splits <id>` | Display lap/split data with mile paces, HR, and split type labels |

Note: `activity download` uses `--format-file` (values: `tcx`, `gpx`, `fit`) instead of `--format` because
`--format` is the reserved global `json`/`json-pretty`/`toon` option. Use `--out <path>` to specify the output file
(defaults to `<id>.<format>` in the working directory).

### `health` — Health/wellness data

| Command | Description |
|---------|-------------|
| `health steps [range]` | Daily steps over a date or range |
| `health heart-rate [date]` | Heart-rate data for a date |
| `health sleep [date]` | Sleep data for a date |
| `health body-battery [range]` | Body Battery over a date or range |
| `health hrv [date]` | HRV data for a date |
| `health stress [date]` | Stress data for a date |
| `health weight [range]` | Weigh-ins over a date or range |

### `stats` — Summaries and training status

| Command | Description |
|---------|-------------|
| `stats summary [date]` | Daily user summary (steps, distance, HR, floors, calories, intensity minutes, avg SpO₂, avg respiration, stress, Body Battery) |
| `stats training-status [date]` | Training status (load, load ratio, HRV, focus) |
| `stats readiness [date]` | Training readiness score |
| `stats records` | Personal records |
| `stats progress <start> <end>` | Progress summary between two dates |
| `stats weekly` | Weekly running volume: total miles, previous week, 4-week avg, longest run, run count |

### `badge` — Badges and challenges

| Command | Description |
|---------|-------------|
| `badge earned [--limit N]` | Recently earned badges (newest first) |
| `badge in-progress` | Badges currently in progress |
| `badge available [--start N] [--limit N]` | Available badge challenges |
| `badge adhoc [--start N] [--limit N]` | Ad-hoc challenges |
| `badge challenges [--start N] [--limit N]` | All badge challenges |

### `capabilities` — Agent discovery

```bash
uv run garmin capabilities
```

Returns the full command tree + workout JSON schema in a single call. Designed
for agents to discover the available interface without prior knowledge.

## Date Specifications

All date parameters accept:

| Format | Example | Description |
|--------|---------|-------------|
| `YYYY-MM-DD` | `2026-07-21` | Absolute date |
| `today` | — | Current date |
| `yesterday` | — | Current date minus 1 day |
| `-7d` | — | N days ago |
| `+7d` | — | N days from now |
| `start:end` | `-7d:today` | Date range (two date specs separated by `:`) |
| `YYYY-MM-DD:YYYY-MM-DD` | `2026-07-01:2026-07-31` | Absolute range |

## Output Format

### JSON (default)

Compact JSON with no extra whitespace:

```json
{"ok":true,"data":{"results":[{"index":0,"name":"Wk1 Tue"}]}}
```

Error envelopes use stderr and non-zero exit codes:

```json
{"ok":false,"error":{"type":"auth","message":"no cached token"}}
```

### JSON-Pretty

Pass `--format json-pretty` for indented, human-readable JSON:

```bash
uv run garmin --format json-pretty activity list
```

```json
{
  "ok": true,
  "data": [
    {
      "activityName": "Morning Run",
      "startTimeLocal": "2026-07-20 07:30:00",
      "duration": 1800.0
    }
  ]
}
```

### TOON

Pass `--format toon` for compact tabular output (uses `python-toon`):

```bash
uv run garmin --format toon workout validate --json '...'
```

### Slim Projections

By default, commands return slim projections of the data (key fields only).
Pass `--full` to return the complete Garmin API payload:

```bash
uv run garmin --full stats summary today
```

## Exit Codes

| Code | Meaning | JSON envelope |
|------|---------|---------------|
| 0 | Success | `{"ok":true,"data":...}` |
| 1 | Internal error | `{"ok":false,"error":{"type":"internal",...}}` |
| 2 | Usage error | `{"ok":false,"error":{"type":"usage",...}}` |
| 3 | Auth error | `{"ok":false,"error":{"type":"auth",...}}` |
| 4 | API error / partial failure | `{"ok":false,"error":{"type":"api",...}}` |

## Design Philosophy

This CLI was designed from the ground up for **agent-driven consumption**:

1. **Structured envelopes** — every command outputs `{"ok":true,"data":...}` or
   `{"ok":false,"error":{...}}` — no human-formatted text that needs parsing.
2. **Exit codes** — 0 (success), 1 (internal), 2 (usage), 3 (auth), 4 (API).
   Agents check code + envelope to determine next action.
3. **Error types** — errors carry a `type` field (`auth`, `usage`, `api`,
   `internal`) so agents can branch on the class of failure.
4. **Discovery** — `capabilities` returns the full command tree + JSON schema in
   one call. An agent can bootstrap without reading a manual.
5. **Batch semantics** — `workout create` accepts multiple workouts in a single
   call. Individual results surface `ok`/`error` per entry; the top-level
   envelope reflects overall success.
6. **No hidden state** — auth state is filesystem-cached; every command sends
   explicit HTTP requests to Garmin. No daemons, no databases, no surprise
   state.
7. **Single binary** — `uv sync` + environment variables + `uv run garmin`.
   Nothing to install globally.

## Development

```bash
uv sync --dev
uv run pytest -v
```
