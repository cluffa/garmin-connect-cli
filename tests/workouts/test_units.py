import pytest

from garmin_cli.output import UsageError
from garmin_cli.workouts import units


def test_parse_duration_seconds():
    assert units.parse_duration("90s") == 90


def test_parse_duration_minutes():
    assert units.parse_duration("10min") == 600


def test_parse_duration_compound():
    assert units.parse_duration("1h30min") == 5400


def test_parse_duration_colon_mmss():
    assert units.parse_duration("1:30") == 90


def test_parse_duration_colon_hhmmss():
    assert units.parse_duration("1:30:00") == 5400


def test_parse_duration_bad():
    with pytest.raises(UsageError):
        units.parse_duration("banana")


def test_parse_distance_meters():
    assert units.parse_distance("400m") == 400


def test_parse_distance_km():
    assert units.parse_distance("1.5km") == 1500


def test_parse_distance_miles():
    assert round(units.parse_distance("1mi"), 1) == 1609.3


def test_parse_pace_per_km():
    # 4:00/km -> 240 s per 1000 m -> 4.1667 m/s
    assert round(units.parse_pace("4:00/km"), 3) == 4.167


def test_parse_pace_per_mile():
    # 8:00/mi -> 480 s per 1609.34 m -> 3.353 m/s
    assert round(units.parse_pace("8:00/mi"), 3) == 3.353


def test_parse_pace_bad():
    with pytest.raises(UsageError):
        units.parse_pace("fast")
