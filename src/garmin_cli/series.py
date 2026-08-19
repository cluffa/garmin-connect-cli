"""Fetch a per-day metric across a date range.

Several Garmin endpoints (`sleep`, `hrv`, `stress`, `heart-rate`,
`readiness`, `training-status`) accept a single date only — there is no
range variant upstream, so N days means N HTTP requests. Looping in the
*agent* is the expensive way to do that: every day lands in the transcript
as its own tool result, and a 90-day trend exhausts the context window long
before Garmin objects. Looping here costs the same requests but returns one
JSON array.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable

from garmin_cli.dates import is_range, parse_range
from garmin_cli.output import ApiError, UsageError
from garmin_cli.projections import project

# Ceiling on days fetched in one command, since each day is a separate
# request to an undocumented API. Deliberately raisable via --max-days.
MAX_RANGE_DAYS = 366


def day_series(
    kind: str,
    fetch: Callable[[str], Any],
    date_spec: str,
    max_days: int = MAX_RANGE_DAYS,
) -> Any:
    """Return *kind* data for *date_spec*, one entry per day.

    A single-date spec (``today``, ``2026-07-15``) returns that day's
    projected payload unchanged — the shape callers got before ranges were
    supported. A range spec (``-7d:today``) returns a list of
    ``{"date": ..., "data": ...}`` entries, one per day inclusive, in
    ascending date order.

    Days the API has nothing for yield ``"data": null``; days whose request
    fails yield ``"data": null`` plus an ``"error"`` string, so one bad day
    does not discard the rest of a long fetch. When *every* day fails the
    cause is systemic rather than per-day, so :class:`ApiError` is raised.
    """
    start, end = parse_range(date_spec)

    if not is_range(date_spec):
        return project(kind, fetch(start.isoformat()))

    if end < start:
        raise UsageError(
            f"range ends before it starts: {start.isoformat()} > {end.isoformat()}"
        )

    span = (end - start).days + 1
    if span > max_days:
        raise UsageError(
            f"range spans {span} days, over the {max_days}-day limit; each day "
            f"is a separate request to Garmin. Narrow the range, or raise "
            f"--max-days deliberately."
        )

    entries: list[dict[str, Any]] = []
    failures = 0
    for offset in range(span):
        day = (start + timedelta(days=offset)).isoformat()
        try:
            payload = fetch(day)
        except Exception as e:  # noqa: BLE001 - one bad day must not sink the range
            entries.append({"date": day, "data": None, "error": str(e)})
            failures += 1
        else:
            entries.append({"date": day, "data": project(kind, payload)})

    if failures == span:
        raise ApiError(
            f"all {span} days failed; last error: {entries[-1]['error']}"
        )
    return entries
