import re

from garmin_cli.output import UsageError

METERS_PER_MILE = 1609.34


def _mmss_to_seconds(text: str) -> int | None:
    parts = text.split(":")
    if not all(p.isdigit() for p in parts):
        return None
    if len(parts) == 2:
        m, s = int(parts[0]), int(parts[1])
        if m >= 60 or s >= 60:
            return None
        return m * 60 + s
    if len(parts) == 3:
        h, m, s = int(parts[0]), int(parts[1]), int(parts[2])
        if m >= 60 or s >= 60:
            return None
        return h * 3600 + m * 60 + s
    return None


_DUR_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(hours?|hr|h|minutes?|mins?|min|m|seconds?|secs?|sec|s)")
_DUR_FACTOR = {"h": 3600, "hr": 3600, "m": 60, "min": 60, "s": 1, "sec": 1}


def parse_duration(text: str) -> float:
    text = text.strip().lower()
    if ":" in text:
        secs = _mmss_to_seconds(text)
        if secs is not None:
            return float(secs)
        raise UsageError(f"invalid duration: {text!r}")
    matches = list(_DUR_UNIT.finditer(text))
    if not matches:
        raise UsageError(f"invalid duration: {text!r}")
    total = 0.0
    last_end = 0
    for m in matches:
        gap = text[last_end : m.start()]
        if gap.strip():
            raise UsageError(f"invalid duration: {text!r}")
        value, unit = m.group(1), m.group(2)
        key = unit[0] if unit[0] in "hms" else unit
        total += float(value) * _DUR_FACTOR[key]
        last_end = m.end()
    if text[last_end:].strip():
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
    if seconds >= 60:
        raise UsageError(f"invalid pace: {text!r}")
    per_unit_seconds = minutes * 60 + seconds
    distance = METERS_PER_MILE if unit == "mi" else 1000.0
    if per_unit_seconds <= 0:
        raise UsageError(f"invalid pace: {text!r}")
    return distance / per_unit_seconds
