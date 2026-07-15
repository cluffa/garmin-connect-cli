from datetime import date

import pytest

from garmin_cli.dates import parse_date, parse_range
from garmin_cli.output import UsageError

REF = date(2026, 7, 15)


def test_iso():
    assert parse_date("2026-07-01", today=REF) == date(2026, 7, 1)


def test_today():
    assert parse_date("today", today=REF) == REF


def test_yesterday():
    assert parse_date("yesterday", today=REF) == date(2026, 7, 14)


def test_offset_days_back():
    assert parse_date("-7d", today=REF) == date(2026, 7, 8)


def test_offset_days_forward():
    assert parse_date("+7d", today=REF) == date(2026, 7, 22)


def test_offset_weeks():
    assert parse_date("-1w", today=REF) == date(2026, 7, 8)


def test_bad_date():
    with pytest.raises(UsageError):
        parse_date("someday", today=REF)


def test_range_explicit():
    assert parse_range("2026-07-01:2026-07-07", today=REF) == (
        date(2026, 7, 1),
        date(2026, 7, 7),
    )


def test_range_relative():
    assert parse_range("-7d:today", today=REF) == (date(2026, 7, 8), REF)


def test_range_single_date():
    assert parse_range("today", today=REF) == (REF, REF)
