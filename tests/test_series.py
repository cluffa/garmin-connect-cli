"""Tests for the per-day range fetch helper."""

import pytest

from garmin_cli.output import ApiError, UsageError
from garmin_cli.series import day_series


def _fetch(day):
    return {"cdate": day, "value": 1}


def test_single_date_returns_payload_unchanged():
    # Single-date specs keep the pre-range shape: a bare payload, not a list.
    assert day_series("hrv", _fetch, "2026-07-15") == {
        "cdate": "2026-07-15",
        "value": 1,
    }


def test_range_returns_one_entry_per_day_ascending():
    result = day_series("hrv", _fetch, "2026-07-13:2026-07-15")
    assert [e["date"] for e in result] == ["2026-07-13", "2026-07-14", "2026-07-15"]
    assert result[0]["data"] == {"cdate": "2026-07-13", "value": 1}


def test_range_is_inclusive_of_both_ends():
    assert len(day_series("hrv", _fetch, "2026-07-01:2026-07-31")) == 31


def test_explicit_single_day_range_still_returns_a_list():
    # "2026-07-15:2026-07-15" is a range spec, so it gets the series shape
    # even though it covers one day.
    result = day_series("hrv", _fetch, "2026-07-15:2026-07-15")
    assert result == [{"date": "2026-07-15", "data": {"cdate": "2026-07-15", "value": 1}}]


def test_missing_day_yields_null_data():
    # get_hrv_data returns None for days with no recording.
    result = day_series("hrv", lambda d: None, "2026-07-14:2026-07-15")
    assert [e["data"] for e in result] == [None, None]
    assert all("error" not in e for e in result)


def test_one_failing_day_does_not_discard_the_rest():
    def flaky(day):
        if day == "2026-07-14":
            raise RuntimeError("boom")
        return {"cdate": day}

    result = day_series("hrv", flaky, "2026-07-13:2026-07-15")
    assert result[1] == {"date": "2026-07-14", "data": None, "error": "boom"}
    assert result[0]["data"] == {"cdate": "2026-07-13"}
    assert result[2]["data"] == {"cdate": "2026-07-15"}


def test_all_days_failing_raises_api_error():
    def broken(day):
        raise RuntimeError("upstream down")

    with pytest.raises(ApiError, match="all 3 days failed"):
        day_series("hrv", broken, "2026-07-13:2026-07-15")


def test_range_over_max_days_is_a_usage_error():
    with pytest.raises(UsageError, match="over the 5-day limit"):
        day_series("hrv", _fetch, "2026-07-01:2026-07-31", max_days=5)


def test_max_days_can_be_raised_deliberately():
    assert len(day_series("hrv", _fetch, "2026-07-01:2026-07-31", max_days=400)) == 31


def test_backwards_range_is_a_usage_error():
    with pytest.raises(UsageError, match="ends before it starts"):
        day_series("hrv", _fetch, "2026-07-15:2026-07-01")


def test_projection_is_applied_per_day():
    # Each day's payload goes through the same projection a single-date
    # fetch would use — here, sleep seconds to hours.
    def sleep_fetch(day):
        return {"dailySleepDTO": {"sleepTimeSeconds": 28800}}

    result = day_series("sleep", sleep_fetch, "2026-07-14:2026-07-15")
    assert result[0]["data"]["duration_hours"] == 8.0


def test_full_flag_bypasses_projection_per_day(monkeypatch):
    import garmin_cli.state as state

    monkeypatch.setattr(state, "full", True)

    def sleep_fetch(day):
        return {"dailySleepDTO": {"sleepTimeSeconds": 28800}}

    result = day_series("sleep", sleep_fetch, "2026-07-14:2026-07-15")
    assert result[0]["data"] == {"dailySleepDTO": {"sleepTimeSeconds": 28800}}
