from __future__ import annotations

import pytest

from garmin_cli import state
from garmin_cli.projections import (
    project,
    project_activity,
    project_activity_list,
    project_sleep,
    project_summary,
    project_training_status,
    slim_activity,
)

RAW = {
    "activityId": 1,
    "activityName": "Run",
    "startTimeLocal": "2026-07-15 06:00",
    "activityType": {"typeKey": "running"},
    "distance": 5000.0,
    "duration": 1500.0,
    "averageHR": 150,
    "maxHR": 172,
    "averageSpeed": 3.3,
    "calories": 320,
    "ownerId": 999,
    "deviceId": 888,
}



# ── slim_activity ──────────────────────────────────────────────


def test_slim_activity_drops_noise():
    slim = slim_activity(RAW)
    assert "ownerId" not in slim
    assert "deviceId" not in slim
    assert slim["activityId"] == 1
    assert slim["averageHR"] == 150
    assert slim["calories"] == 320


def test_slim_activity_omits_missing_keys():
    slim = slim_activity({"activityId": 1, "activityName": "Test"})
    assert slim == {"activityId": 1, "activityName": "Test"}


# ── project dispatcher ─────────────────────────────────────────


def test_project_full_passthrough():
    state.full = True
    assert project("activity", RAW) == RAW


def test_project_full_activity_list():
    state.full = True
    out = project("activity_list", [RAW, RAW])
    assert out == [RAW, RAW]


def test_project_activity_list():
    state.full = False
    out = project("activity_list", [RAW, RAW])
    assert len(out) == 2
    assert "ownerId" not in out[0]
    assert out[0]["activityId"] == 1


def test_unknown_kind_passthrough():
    state.full = False
    assert project("mystery", {"x": 1}) == {"x": 1}


def test_project_non_dict_passthrough():
    state.full = False
    assert project("activity", None) is None
    assert project("activity", [1, 2, 3]) == [1, 2, 3]


# ── project_activity ───────────────────────────────────────────


def test_project_activity():
    out = project_activity(RAW)
    assert "ownerId" not in out
    assert out["activityId"] == 1
    assert out["averageSpeed"] == 3.3


def test_project_activity_empty():
    assert project_activity({}) == {}


# ── project_activity_list ──────────────────────────────────────


def test_project_activity_list_function():
    out = project_activity_list([RAW, RAW])
    assert len(out) == 2
    assert "deviceId" not in out[0]


def test_project_activity_list_empty():
    assert project_activity_list([]) == []


# ── project_sleep ──────────────────────────────────────────────


SLEEP_RAW = {
    "dailySleepDTO": {
        "sleepTimeFromLocal": "2026-07-15T22:00:00",
        "sleepTimeToLocal": "2026-07-16T06:30:00",
        "sleepScores": {"overall": {"value": {"qualifierValue": 85}}},
        "sleepTimeSeconds": 28800,
        "deepSleepSeconds": 5400,
        "lightSleepSeconds": 14400,
        "remSleepSeconds": 5400,
        "awakeSleepSeconds": 3600,
    },
    "restingHeartRate": 48,
    "hRVSummary": {"weeklyAverage": 45},
    "overallSleepScore": {"value": 85},
}


def test_project_sleep():
    out = project_sleep(SLEEP_RAW)
    assert out["duration_hours"] == 8.0
    assert out["deep_pct"] == pytest.approx(18.75)
    assert out["light_pct"] == pytest.approx(50.0)
    assert out["rem_pct"] == pytest.approx(18.75)
    assert out["awake_pct"] == pytest.approx(12.5)
    assert out["sleep_score"] == 85
    assert out["resting_hr"] == 48


def test_project_sleep_minimal():
    assert project_sleep({}) == {}


# ── project_summary ────────────────────────────────────────────


# Field names mirror a real get_user_summary payload.
SUMMARY_RAW = {
    "totalSteps": 12000,
    "dailyStepGoal": 10000,
    "totalDistanceMeters": 8500,
    "activeSeconds": 3600,
    "highlyActiveSeconds": 1800,
    "restingHeartRate": 48,
    "minHeartRate": 42,
    "maxHeartRate": 165,
    "floorsAscended": 15,
    "totalKilocalories": 2600.0,
    "moderateIntensityMinutes": 20,
    "vigorousIntensityMinutes": 10,
    "averageSpo2": 96,
    "avgWakingRespirationValue": 14.0,
    "averageStressLevel": 19,
    "maxStressLevel": 67,
    "bodyBatteryMostRecentValue": 73,
    "bodyBatteryHighestValue": 84,
    "bodyBatteryLowestValue": 47,
}


def test_project_summary():
    out = project_summary(SUMMARY_RAW)
    assert out["steps"] == 12000
    assert out["step_goal_pct"] == pytest.approx(120.0)
    assert out["distance_km"] == 8.5
    assert out["active_minutes"] == 60
    assert out["highly_active_minutes"] == 30
    assert out["moderate_intensity_minutes"] == 20
    assert out["vigorous_intensity_minutes"] == 10
    assert out["resting_hr"] == 48
    assert out["hr_range"] == "42-165"
    assert out["floors"] == 15
    assert out["calories"] == 2600
    assert out["avg_spo2"] == 96
    assert out["avg_respiration"] == 14.0
    assert out["avg_stress"] == 19
    assert out["max_stress"] == 67
    assert out["body_battery"] == 73
    assert out["body_battery_high"] == 84
    assert out["body_battery_low"] == 47


def test_project_summary_zero_intensity_minutes_kept():
    """Zero intensity minutes are real data, not missing — must be included."""
    out = project_summary(
        {"totalSteps": 1, "moderateIntensityMinutes": 0, "vigorousIntensityMinutes": 0}
    )
    assert out["moderate_intensity_minutes"] == 0
    assert out["vigorous_intensity_minutes"] == 0


def test_project_summary_calories_falls_back_to_calories_out():
    """Older payloads without totalKilocalories still yield calories."""
    out = project_summary({"totalSteps": 1, "caloriesOut": 2100})
    assert out["calories"] == 2100


def test_project_summary_empty():
    assert project_summary({}) == {}


def test_project_summary_omits_missing_spo2_and_respiration():
    out = project_summary({"totalSteps": 100})
    assert "avg_spo2" not in out
    assert "avg_respiration" not in out


def test_project_summary_real_payload_keys():
    """Regression: real get_user_summary keys populate goal, calories, respiration."""
    raw = {
        "totalSteps": 487,
        "dailyStepGoal": 8000,
        "totalKilocalories": 1163.0,
        "floorsAscended": 4.0,
        "averageSpo2": None,  # device recorded no SpO2 today
        "avgWakingRespirationValue": 11.0,
    }
    out = project_summary(raw)
    assert out["step_goal_pct"] == pytest.approx(6.1)
    assert out["calories"] == 1163
    assert out["avg_respiration"] == 11.0
    assert "avg_spo2" not in out


# ── project_training_status ────────────────────────────────────


STATUS_RAW = {
    "trainingStatus": "PRODUCTIVE",
    "currentLoad": 450,
    "loadRatio": 1.2,
    "hrvStatus": "BALANCED",
    "hrv7dAvg": 45,
    "acuteLoad": 400,
    "chronicLoad": 350,
    "focus": "ENDURANCE",
}


def test_project_training_status():
    out = project_training_status(STATUS_RAW)
    assert out["status"] == "PRODUCTIVE"
    assert out["load"] == 450
    assert out["load_ratio"] == 1.2
    assert out["hrv_status"] == "BALANCED"
    assert out["hrv_avg"] == 45
    assert out["acute_load"] == 400
    assert out["chronic_load"] == 350
    assert out["focus"] == "ENDURANCE"


def test_project_training_status_minimal():
    out = project_training_status({"trainingStatus": "RECOVERY"})
    assert out["status"] == "RECOVERY"
    assert "load" not in out


def test_project_training_status_empty():
    assert project_training_status({}) == {}


# ── Fallback: unexpected keys → raw payload ────────────────────


def test_project_sleep_unexpected_keys_fallback():
    """Non-empty sleep payload with no known keys returns raw payload."""
    raw = {"unexpectedKey": "value"}
    out = project_sleep(raw)
    assert out == raw


def test_project_sleep_empty_input_still_empty():
    """Empty input still returns {} (no data to fall back to)."""
    assert project_sleep({}) == {}


def test_project_summary_unexpected_keys_fallback():
    """Non-empty stats payload with no known keys returns raw payload."""
    raw = {"unexpectedKey": "value"}
    out = project_summary(raw)
    assert out == raw


def test_project_summary_empty_input_still_empty():
    assert project_summary({}) == {}


def test_project_training_status_unexpected_keys_fallback():
    """Non-empty status payload with no known keys returns raw payload."""
    raw = {"unexpectedKey": "value"}
    out = project_training_status(raw)
    assert out == raw


def test_project_training_status_empty_input_still_empty():
    assert project_training_status({}) == {}
