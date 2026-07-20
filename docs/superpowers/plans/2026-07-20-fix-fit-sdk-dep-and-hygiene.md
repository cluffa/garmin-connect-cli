# Plan: Fix missing FIT SDK dependency + repo hygiene

Date: 2026-07-20
Repos: `garmin-connect-cli` (primary), `garmin-connect-skill` (version sync)

## Motivation

Review of the CLI and companion skill surfaced one release-blocking bug and
some publishing hygiene gaps.

### Findings

1. **Critical — missing runtime dependency.** `src/garmin_cli/commands/activity.py`
   imports `from garmin_fit_sdk import Decoder, Stream`. `cli.py` imports
   `activity_app` at module load, so this import runs for *every* command.
   `garmin-fit-sdk` was never added to `pyproject.toml` / `uv.lock`. Effect:
   a clean `uv sync` clone cannot run any command, and the full test suite
   (162 tests) fails at collection with `ModuleNotFoundError`. Introduced with
   the `--format-file json` FIT-to-JSON feature.

2. **Publishing hygiene.** Untracked working artifacts sit in the tree:
   `.DS_Store`, `tests/.DS_Store`, and two multi-MB downloaded activity files
   (`activity_23654666491.json`, `activity_23654666491.tcx`) containing personal
   Garmin data. `.gitignore` covers none of these. Per the repo owner's global
   publishing rules, these must never be committed.

3. **Untracked plan doc.** `docs/superpowers/plans/2026-07-20-pretty-print-json.md`
   is untracked, though the repo tracks its sibling superpowers plans/specs.

Non-findings (verified, no action): skill command coverage matches the live CLI
`capabilities` output; `uv run pytest` failing locally is a stale venv shebang
from a moved checkout, not a repo defect.

## Changes

### `garmin-connect-cli`

1. Add `garmin-fit-sdk>=21.208.0` to `pyproject.toml` `dependencies`; regenerate
   `uv.lock` (via `uv add garmin-fit-sdk`).
2. Append ignore rules to `.gitignore`:
   - `.DS_Store` (anywhere)
   - downloaded activity artifacts: `activity_*.json`, `activity_*.tcx`,
     `activity_*.gpx`, `activity_*.fit`
3. Delete the stray local artifacts (`activity_23654666491.{json,tcx}`, the two
   `.DS_Store` files). They are just downloaded test data.
4. Track this plan doc and `2026-07-20-pretty-print-json.md`.
5. Bump `project.version` `0.1.0` → `0.1.1` (release-blocking install fix).

### `garmin-connect-skill`

6. Bump `SKILL.md` frontmatter `version` `0.1.0` → `0.1.1` to keep the CLI and
   skill versions in sync per both repos' CLAUDE.md.

## Verification

- `uv sync --dev && uv run python -m pytest -q` → all tests pass.
- `git status` shows no `.DS_Store` or `activity_*` files.
- Pushed remotes contain no artifacts or personal data.
- CLI `pyproject.toml` version == skill `SKILL.md` version == `0.1.1`.

## Execution / commits

Two commits, one per repo, pushed to `origin/main`:

- cli: `fix: declare garmin-fit-sdk dependency; ignore local artifacts; v0.1.1`
- skill: `chore: bump version to 0.1.1 to match CLI`
