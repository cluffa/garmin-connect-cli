import functools
import json
import sys
from datetime import datetime

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


class InternalError(CliError):
    type = "internal"
    exit_code = 1


def _human_dict(data: dict) -> str:
    """Render a flat dict as labeled key: value pairs."""
    lines: list[str] = []
    for k, v in data.items():
        if isinstance(v, dict):
            continue  # skip nested, let toon handle those
        if isinstance(v, list):
            continue
        label = k.replace("_", " ").replace("  ", " ").title()
        if isinstance(v, float):
            v = f"{v:.1f}" if v != int(v) else int(v)
        lines.append(f"  {label}: {v}")
    return "\n".join(lines)


def _human_list(items: list) -> str:
    """Render a list of dicts as an aligned table."""
    if not items:
        return "  (empty)"

    first = items[0]
    if not isinstance(first, dict):
        return "\n".join(f"  {i+1}. {v}" for i, v in enumerate(items))

    # Fields to exclude
    skip = {"activityType", "activityId", "userProfileId"}

    # Pick columns — use the first item's keys (after filtering)
    cols = [k for k in first if k not in skip and not isinstance(first[k], (dict, list))]

    # Prettify column headers
    label_overrides = {
        "activityName": "Activity",
        "startTimeLocal": "Start",
        "pace_per_mi": "Pace",
        "distance_mi": "Dist",
        "averageHR": "HR",
        "maxHR": "MaxHR",
        "averageSpeed": "Speed",
        "trainingEffectLabel": "TE",
        "anaerobicTrainingEffect": "Anaerobic",
        "duration": "Duration (s)",
    }

    def col_label(c: str) -> str:
        return label_overrides.get(c, c.replace("_", " ").title())

    # Measure columns using labels
    col_widths = {c: len(col_label(c)) for c in cols}

    def fmt(v):
        if v is None:
            return "--"
        if isinstance(v, bool):
            return "✓" if v else ""
        if isinstance(v, float):
            return f"{v:.1f}" if abs(v - round(v, 1)) > 0.0001 else str(int(v))
        return str(v)

    # Widen columns to fit data
    for item in items:
        for c in cols:
            w = len(fmt(item.get(c)))
            if w > col_widths.get(c, 0):
                col_widths[c] = w

    # Cap width so tables don't get absurdly wide
    col_widths = {c: min(w, 30) for c, w in col_widths.items()}

    sep = "  "
    hdr = sep.join(f"{col_label(c):>{col_widths[c]}}" for c in cols)
    ruler = "─" * len(hdr)
    rows = []
    for item in items:
        row = sep.join(f"{fmt(item.get(c)):>{col_widths[c]}}" for c in cols)
        rows.append(row)

    return "\n".join([hdr, ruler] + rows)


def _human_splits(data: dict) -> str:
    """Render splits data as a human-readable table."""
    laps = data.get("splits") or []
    total_mi = data.get("total_distance_mi", 0)
    total_sec = data.get("total_duration_sec", 0)
    lap_count = data.get("lap_count", 0)

    # Header line
    date_str = ""
    raw_date = data.get("date", "")
    if raw_date:
        try:
            dt = datetime.fromisoformat(raw_date.replace("Z", ""))
            date_str = dt.strftime("%d %b %Y")
        except (ValueError, TypeError):
            date_str = raw_date[:10]

    total_pace = "--"
    if total_mi > 0 and total_sec > 0:
        pace_sec = total_sec / total_mi
        mins = int(pace_sec // 60)
        secs = int(pace_sec % 60)
        total_pace = f"{mins}:{secs:02d}/mi"

    total_time = f"{int(total_sec//60)}m" if total_sec < 3600 else f"{int(total_sec//3600)}h{int((total_sec%3600)//60):02d}m"

    lines: list[str] = []
    lines.append(f"  {total_mi:.2f} mi \u00b7 {total_pace} \u00b7 {total_time} \u00b7 {lap_count} laps")
    if date_str:
        lines.insert(0, f"  {date_str}")
    lines.append("")

    # Column widths
    col_lap = max(3, len(str(lap_count)))
    col_pace = 8
    col_hr = 4
    col_maxhr = 5
    col_cad = 4
    col_stride = 7
    col_gct = 5
    col_power = 5
    col_cal = 4

    # Header row
    hdr = (
        f"{'Lap':>{col_lap}}  {'Dist':>6}  {'Pace':>{col_pace}}  "
        f"{'HR':>{col_hr}}  {'MaxHR':>{col_maxhr}}  {'Cad':>{col_cad}}  "
        f"{'Stride':>{col_stride}}  {'GCT':>{col_gct}}  {'Power':>{col_power}}"
    )

    # Check if we have extra fields to show
    has_extra = any(l.get("avg_power") is not None for l in laps)
    if has_extra:
        hdr += f"  {'Cal':>{col_cal}}"
    lines.append(hdr)

    sep_len = len(hdr)
    lines.append("\u2500" * sep_len)

    for i, lap in enumerate(laps):
        d = lap.get("distance_mi", 0)
        p = lap.get("pace_per_mi", "--")
        hr = _hv(lap.get("avg_hr"))
        mhr = _hv(lap.get("max_hr"))
        cad = _hv(lap.get("cadence"))
        stride = _hv(lap.get("stride_length"))
        gct = _hv(lap.get("ground_contact_ms"))
        pwr = _hv(lap.get("avg_power"))

        row = (
            f"{i+1:>{col_lap}}  {d:>5.2f}mi  {p:>{col_pace}}  "
            f"{hr:>{col_hr}}  {mhr:>{col_maxhr}}  {cad:>{col_cad}}  "
            f"{stride:>{col_stride}}  {gct:>{col_gct}}  {pwr:>{col_power}}"
        )
        if has_extra:
            cal = _hv(lap.get("calories"))
            row += f"  {cal:>{col_cal}}"
        lines.append(row)

    lines.append("\u2500" * sep_len)

    # Totals row
    total_hr = "--"
    avg_hrs = [l.get("avg_hr") for l in laps if l.get("avg_hr") is not None]
    if avg_hrs:
        total_hr = str(round(sum(avg_hrs) / len(avg_hrs)))
    total_row = (
        f"{'':>{col_lap}}  {total_mi:>5.2f}mi  {total_pace:>{col_pace}}  "
        f"{total_hr:>{col_hr}}  {'':>{col_maxhr}}  {'':>{col_cad}}  "
        f"{'':>{col_stride}}  {'':>{col_gct}}  {'':>{col_power}}"
    )
    lines.append(total_row)

    return "\n".join(lines)


def _hv(val):
    """Format a value or return '--' for None."""
    if val is None:
        return "--"
    if isinstance(val, float):
        if val == int(val):
            return str(int(val))
        return f"{val:.1f}"
    return str(val)


def render(envelope: dict) -> str:
    if state.fmt == "toon":
        return toon.encode(envelope)
    if state.fmt == "human":
        data = envelope.get("data")
        if isinstance(data, dict) and "splits" in data and "lap_count" in data:
            return _human_splits(data)
        if isinstance(data, dict):
            return _human_dict(data)
        if isinstance(data, list):
            return _human_list(data)
        return toon.encode(envelope)
    return json.dumps(envelope, separators=(",", ":"), default=str)


def _emit(envelope: dict, stream, code: int) -> None:
    print(render(envelope), file=stream)
    raise SystemExit(code)


def emit_error(e: CliError) -> None:
    """Render a single ``CliError`` to stderr as the standard error envelope.

    Exit codes come from ``e.exit_code``.  Intended for commands that bypass
    the ``command_output`` decorator (e.g. batch-oriented commands).
    """
    _emit(
        {"ok": False, "error": {"type": e.type, "message": e.message}},
        sys.stderr,
        e.exit_code,
    )


def command_output(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            data = fn(*args, **kwargs)
        except CliError as e:
            emit_error(e)
        except Exception as e:  # noqa: BLE001 - top-level guard
            emit_error(InternalError(str(e)))
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
