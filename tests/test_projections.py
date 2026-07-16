from __future__ import annotations

import pytest

from garmin_cli import state
from garmin_cli.projections import (
    project,
    project_activity,
    project_activity_list,
    project_health,
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


# ── project_health ─────────────────────────────────────────────


HEALTH_RAW = {
    "bodyBattery": {"chargedByActivity": 80},
    "stress": {"overallStressLevel": 25},
    "restingHeartRate": 48,
    "stepCount": 8500,
    "floorsAscendedInMeters": 10.0,
    "respiratoryData": {"averageWearableRespiration": 14.5},
    "spo2DailySummary": {"averageSpo2": 97},
}


def test_project_health_steps():
    out = project_health(HEALTH_RAW, "steps")
    assert out["steps"] == 8500


def test_project_health_stress():
    out = project_health(HEALTH_RAW, "stress")
    assert out["stress"] == 25


def test_project_health_respiration():
    out = project_health(HEALTH_RAW, "respiration")
    assert out["respiration"] == 14.5


def test_project_health_spo2():
    out = project_health(HEALTH_RAW, "spo2")
    assert out["spo2"] == 97


def test_project_health_floors():
    out = project_health(HEALTH_RAW, "floors")
    assert out["floors"] == 10.0


def test_project_health_default():
    out = project_health(HEALTH_RAW, "steps")
    assert out["steps"] == 8500
    assert "stress" not in out


def test_project_health_unknown_metric():
    out = project_health(HEALTH_RAW, "unknown")
    assert out == {}


def test_project_health_empty():
    assert project_health({}, "steps") == {}


# ── project_summary ────────────────────────────────────────────


SUMMARY_RAW = {
    "totalSteps": 12000,
    "stepGoal": 10000,
    "totalDistanceMeters": 8500,
    "activeSeconds": 3600,
    "highlyActiveSeconds": 1800,
    "restingHeartRate": 48,
    "minHeartRate": 42,
    "maxHeartRate": 165,
    "floorsAscended": 15,
    "caloriesOut": 2100,
    "totalKilocalories": 2600,
    "averageSpo2": 96,
    "avgWakingRespirationValue": 14.0,
}


def test_project_summary():
    out = project_summary(SUMMARY_RAW)
    assert out["steps"] == 12000
    assert out["step_goal_pct"] == pytest.approx(120.0)
    assert out["distance_km"] == 8.5
    assert out["active_minutes"] == 60
    assert out["highly_active_minutes"] == 30
    assert out["resting_hr"] == 48
    assert out["hr_range"] == "42-165"
    assert out["floors"] == 15
    assert out["calories"] == 2100
    assert out["avg_spo2"] == 96
    assert out["avg_respiration"] == 14.0


def test_project_summary_empty():
    assert project_summary({}) == {}


def test_project_summary_omits_missing_spo2_and_respiration():
    out = project_summary({"totalSteps": 100})
    assert "avg_spo2" not in out
    assert "avg_respiration" not in out


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


def test_project_health_unexpected_keys_fallback():
    """Non-empty health payload with no known metric keys returns raw payload."""
    raw = {"unexpectedKey": "value"}
    out = project_health(raw, "steps")
    assert out == raw


def test_project_health_unexpected_keys_empty_input_still_empty():
    assert project_health({}, "steps") == {}


def test_project_health_unknown_metric_still_empty():
    """Unknown metric still returns {} even with non-empty payload."""
    assert project_health({"foo": "bar"}, "unknown") == {}
