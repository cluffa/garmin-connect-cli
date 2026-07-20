# Pretty-Print JSON Format Option Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `--format json-pretty` option that emits the standard JSON envelope with indentation and newlines for human readability. Remove the `--format human` option (superseded by `json-pretty`).

**Architecture:** A new format string `"json-pretty"` is accepted by the CLI callback and stored in `state.fmt`. The `render()` function in `output.py` dispatches it to `json.dumps()` with `indent=2`. The `human` format and all its helper functions (`_human_dict`, `_human_list`, `_human_splits`, `_hv`) are removed. The existing compact `json` format is unchanged.

**Tech Stack:** Python, Typer, stdlib `json`

## Global Constraints

- `--format json` must remain the default and continue to emit compact JSON (no breaking change)
- `--format human` must be removed entirely (CLI validation, rendering, helpers, tests, docs)
- The new format uses the same envelope structure (`{"ok": true, "data": ...}`)
- Exit codes and error handling are unchanged
- Format name: `json-pretty` (hyphenated, consistent with CLI convention)

---

### Task 1: Accept `json-pretty` in the CLI callback ✅ (COMPLETED)

**Files:**
- Modify: `src/garmin_cli/cli.py:25`

**Status:** Done. Commit `f9a03b2`. Added `"json-pretty"` to help text, validation tuple, and error message. `"human"` still present.

---

### Task 1b: Remove `--format human` from the CLI callback

**Files:**
- Modify: `src/garmin_cli/cli.py:21-27`

**Interfaces:**
- Produces: `state.fmt` valid values are now `"json"`, `"json-pretty"`, `"toon"` only

- [ ] **Step 1: Remove "human" from the CLI callback**

The current code (after Task 1) is:

```python
@app.callback()
def main(
    fmt: str = typer.Option("json", "--format", help="Output format: json, json-pretty, toon, or human."),
    full: bool = typer.Option(False, "--full", help="Return full raw payloads."),
) -> None:
    """Global options applied to every command."""
    if fmt not in ("json", "json-pretty", "toon", "human"):
        raise typer.BadParameter("format must be 'json', 'json-pretty', 'toon', or 'human'")
    state.fmt = fmt
    state.full = full
```

Remove `"human"` from the help text, the validation tuple, and the error message:

```python
@app.callback()
def main(
    fmt: str = typer.Option("json", "--format", help="Output format: json, json-pretty, or toon."),
    full: bool = typer.Option(False, "--full", help="Return full raw payloads."),
) -> None:
    """Global options applied to every command."""
    if fmt not in ("json", "json-pretty", "toon"):
        raise typer.BadParameter("format must be 'json', 'json-pretty', or 'toon'")
    state.fmt = fmt
    state.full = full
```

- [ ] **Step 2: Verify human is rejected**

Run: `uv run garmin --format human activity list`
Expected: `Error: Invalid value for '--format': 'human' is not one of 'json', 'json-pretty', 'toon'.` (BadParameter error)

- [ ] **Step 3: Verify json-pretty is still accepted**

Run: `uv run garmin --format json-pretty activity list`
Expected: Auth error (no token), NOT a BadParameter error

- [ ] **Step 4: Commit**

```bash
git add src/garmin_cli/cli.py
git commit -m "feat: remove --format human from CLI callback"
```

---

### Task 2: Add json-pretty rendering, remove human rendering from output.py

**Files:**
- Modify: `src/garmin_cli/output.py`

**Interfaces:**
- Consumes: `state.fmt` may be `"json-pretty"`; `"human"` is no longer valid
- Produces: `render()` returns indented JSON for `json-pretty`; human helpers and branch removed
- Removes: `_human_dict()`, `_human_list()`, `_human_splits()`, `_hv()`, and the `human` branch in `render()`

- [ ] **Step 1: Remove the `_hv` helper function**

Delete `_hv()` (lines 216-224 in current output.py):

```python
def _hv(val):
    """Format a value or return '--' for None."""
    if val is None:
        return "--"
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return f"{val:.1f}"
    return str(val)
```

- [ ] **Step 2: Remove the `_human_dict` helper function**

Delete `_human_dict()` (lines 40-52).

- [ ] **Step 3: Remove the `_human_list` helper function**

Delete `_human_list()` (lines 55-117).

- [ ] **Step 4: Remove the `_human_splits` helper function**

Delete `_human_splits()` (lines 120-213).

- [ ] **Step 5: Replace the `render()` function**

Replace `render()` (lines 227-239) with:

```python
def render(envelope: dict) -> str:
    if state.fmt == "toon":
        return toon.encode(envelope)
    if state.fmt == "json-pretty":
        return json.dumps(envelope, indent=2, default=str)
    return json.dumps(envelope, separators=(",", ":"), default=str)
```

- [ ] **Step 6: Remove unused `datetime` import**

Since `_human_splits` is removed, the `from datetime import datetime` import (line 4) is now unused. Remove it.

The imports should become:

```python
import functools
import json
import sys

import toon

from garmin_cli import state
```

- [ ] **Step 7: Smoke test json-pretty**

Run: `uv run python -c "
from garmin_cli import state
from garmin_cli.output import render
state.fmt = 'json-pretty'
print(render({'ok': True, 'data': {'a': 1, 'b': [1,2,3]}}))
"`
Expected indented JSON output.

- [ ] **Step 8: Run tests to verify nothing breaks**

Run: `uv run pytest -v`
Expected: Some tests may fail if they reference the human format. Note which ones — they'll be fixed in Task 3.

- [ ] **Step 9: Commit**

```bash
git add src/garmin_cli/output.py
git commit -m "feat: add json-pretty rendering, remove human format and helpers"
```

---

### Task 3: Update tests

**Files:**
- Modify: `tests/test_output.py`
- Check for human references in: `tests/` (grep for "human" in test files)

**Interfaces:**
- Consumes: `render()` from `output.py` (Task 2)

- [ ] **Step 1: Find all test references to "human" format**

Run: `grep -r "human" tests/ --include="*.py"`
If nothing found, skip Step 2.

- [ ] **Step 2: Remove or update any human-format tests**

Remove any tests that exercise the human format, or update them to use `json-pretty` instead.

- [ ] **Step 3: Add a unit test for pretty-printed JSON rendering**

Add this test function to `tests/test_output.py` (after the existing `test_render_json_compact` test):

```python
def test_render_json_pretty():
    state.fmt = "json-pretty"
    out = render({"ok": True, "data": {"a": 1}})
    assert out == '{\n  "ok": true,\n  "data": {\n    "a": 1\n  }\n}'
```

- [ ] **Step 4: Run the new test**

Run: `uv run pytest tests/test_output.py::test_render_json_pretty -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add tests/test_output.py
git commit -m "test: add json-pretty test, remove human format tests"
```

---

### Task 4: Update README documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Remove all human format references**

Run: `grep -n "human" README.md` to find all references.

Update each one:
- Line 10-11: Remove `human` from the feature list
- Line 45 (Global Options table): Remove `human` from the format description
- Line 147-149: Remove `human` from the `--format` note
- Any other mentions of `human` in format context

- [ ] **Step 2: Update the Global Options table row**

```markdown
| `--format` | `json` | Output format: `json` (compact), `json-pretty` (indented), or `toon` (tabular) |
```

- [ ] **Step 3: Add json-pretty section to Output Format docs**

After the JSON section, add:

```markdown
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
```

- [ ] **Step 4: Update any other format references**

Make sure no stale `human` references remain in the README. The JSON envelope description (line 7-8) should stay as-is (it describes JSON output regardless of format).

- [ ] **Step 5: Verify**

Run: `grep -n "human" README.md` — should return no results (or only non-format uses like "human-readable").

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: replace human format with json-pretty in README"
```

---

## Self-Review

**1. Spec coverage:** 
- Add `json-pretty` format ✓ (Tasks 1, 2)
- Remove `human` format ✓ (Tasks 1b, 2, 3, 4)
- Tests ✓ (Task 3)
- Docs ✓ (Task 4)

**2. Placeholder scan:** No TBDs, TODOs, or vague instructions.

**3. Type consistency:** `state.fmt` values: `"json"`, `"json-pretty"`, `"toon"`. Consistent across CLI, render, tests, docs.
