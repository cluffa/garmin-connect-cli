from __future__ import annotations

from typing import Any

from garmin_cli import state

# ── Keys for each projection kind ──────────────────────────────

_ACTIVITY_KEYS = [
    "activityId",
    "activityName",
    "startTimeLocal",
    "activityType",
    "distance",
    "duration",
    "averageHR",
    "maxHR",
    "averageSpeed",
    "calories",
]


def slim_activity(a: dict) -> dict:
    """Return only the well-known keys present in *a*."""
    return {k: a[k] for k in _ACTIVITY_KEYS if k in a}


# ── Public per-kind projection helpers ─────────────────────────


def project_activity(activity: dict) -> dict:
    """Slim an activity dict to essential fields."""
    return slim_activity(activity)


def project_activity_list(activities: list[dict]) -> list[dict]:
    """Slim every activity in a list."""
    return [slim_activity(a) for a in activities]


def project_sleep(sleep: dict) -> dict:
    """Project sleep data to a curated summary.

    Keys produced (when source data is available):
        duration_hours, deep_pct, light_pct, rem_pct, awake_pct,
        sleep_score, resting_hr.

    Falls back to the raw payload when the input is non-empty but
    no known keys matched (e.g. API contract drift).
    """
    dto = sleep.get("dailySleepDTO") or {}
    total_sec = dto.get("sleepTimeSeconds")
    if not total_sec:
        result: dict[str, Any] = {}
    else:
        result = {
            "duration_hours": round(total_sec / 3600, 2),
        }

        stages: list[tuple[str, str]] = [
            ("deep_pct", "deepSleepSeconds"),
            ("light_pct", "lightSleepSeconds"),
            ("rem_pct", "remSleepSeconds"),
            ("awake_pct", "awakeSleepSeconds"),
        ]
        for key, src in stages:
            sec = dto.get(src)
            if sec is not None:
                result[key] = round(sec / total_sec * 100, 2)

        sleep_score_val = (
            dto.get("sleepScores", {})
            .get("overall", {})
            .get("value", {})
            .get("qualifierValue")
        )
        if sleep_score_val is not None:
            result["sleep_score"] = sleep_score_val
        else:
            overall = sleep.get("overallSleepScore")
            if isinstance(overall, dict):
                result["sleep_score"] = overall.get("value")

        rr = sleep.get("restingHeartRate")
        if rr is not None:
            result["resting_hr"] = rr

    # Fall back to raw payload to prevent silent data loss
    if not result and sleep:
        return sleep
    return result


def project_health(data: dict, metric: str) -> dict:
    """Extract a single health metric from a daily health snapshot.

    Supported *metric* values:
        steps, stress, respiration, spo2, floors.

    Falls back to the raw payload when the input is non-empty but
    no known keys matched (e.g. API contract drift).
    """
    field_map: dict[str, tuple[str, Any]] = {
        "steps": ("stepCount", None),
        "stress": ("stress", lambda d: d.get("overallStressLevel")),
        "respiration": (
            "respiratoryData",
            lambda d: d.get("averageWearableRespiration"),
        ),
        "spo2": ("spo2DailySummary", lambda d: d.get("averageSpo2")),
        "floors": ("floorsAscendedInMeters", None),
    }

    if metric not in field_map:
        return {}

    key, extractor = field_map[metric]
    val = data.get(key)
    if val is None:
        result: dict[str, Any] = {}
    elif extractor:
        v = extractor(val)
        result = {metric: v} if v is not None else {}
    else:
        result = {metric: val}

    # Fall back to raw payload to prevent silent data loss
    if not result and data:
        return data
    return result


def project_summary(stats: dict) -> dict:
    """Project a daily stats summary to a curated view.

    Keys produced (when source data is available):
        steps, step_goal_pct, distance_km, active_minutes,
        highly_active_minutes, resting_hr, hr_range, floors, calories,
        avg_spo2, avg_respiration.

    Falls back to the raw payload when the input is non-empty but
    no known keys matched (e.g. API contract drift).
    """
    result: dict[str, Any] = {}

    steps = stats.get("totalSteps")
    if steps is not None:
        result["steps"] = steps
        goal = stats.get("stepGoal")
        if goal:
            result["step_goal_pct"] = round(steps / goal * 100, 1)

    dist = stats.get("totalDistanceMeters")
    if dist is not None:
        result["distance_km"] = round(dist / 1000, 2)

    active = stats.get("activeSeconds")
    if active is not None:
        result["active_minutes"] = round(active / 60)

    highly = stats.get("highlyActiveSeconds")
    if highly is not None:
        result["highly_active_minutes"] = round(highly / 60)

    rr = stats.get("restingHeartRate")
    if rr is not None:
        result["resting_hr"] = rr

    hr_min = stats.get("minHeartRate")
    hr_max = stats.get("maxHeartRate")
    if hr_min is not None and hr_max is not None:
        result["hr_range"] = f"{hr_min}-{hr_max}"

    floors = stats.get("floorsAscended")
    if floors is not None:
        result["floors"] = floors

    cals = stats.get("caloriesOut")
    if cals is not None:
        result["calories"] = cals

    spo2 = stats.get("averageSpo2")
    if spo2 is not None:
        result["avg_spo2"] = spo2

    resp = stats.get("avgWakingRespirationValue")
    if resp is not None:
        result["avg_respiration"] = resp

    # Fall back to raw payload to prevent silent data loss
    if not result and stats:
        return stats
    return result


def project_training_status(status: dict) -> dict:
    """Project training status data to a curated summary.

    Keys produced (when source data is available):
        status, load, load_ratio, hrv_status, hrv_avg,
        acute_load, chronic_load, focus.

    Falls back to the raw payload when the input is non-empty but
    no known keys matched (e.g. API contract drift).
    """
    result: dict[str, Any] = {}

    ts = status.get("trainingStatus")
    if ts:
        result["status"] = ts

    load = status.get("currentLoad")
    if load is not None:
        result["load"] = load

    lr = status.get("loadRatio")
    if lr is not None:
        result["load_ratio"] = lr

    hrv_s = status.get("hrvStatus")
    if hrv_s:
        result["hrv_status"] = hrv_s

    hrv = status.get("hrv7dAvg")
    if hrv is not None:
        result["hrv_avg"] = hrv

    al = status.get("acuteLoad")
    if al is not None:
        result["acute_load"] = al

    cl = status.get("chronicLoad")
    if cl is not None:
        result["chronic_load"] = cl

    focus = status.get("focus")
    if focus:
        result["focus"] = focus

    # Fall back to raw payload to prevent silent data loss
    if not result and status:
        return status
    return result


# ── Generic dispatcher (used by command infrastructure) ────────


def project(kind: str, payload: Any, metric: str | None = None) -> Any:
    """Dispatch *payload* through the appropriate projection.

    When ``state.full`` is ``True`` the raw payload is returned unchanged.

    Supported *kind* values:
        activity, activity_list, sleep, health (requires *metric*),
        summary, training_status.
    All other kinds pass through unchanged (but still respect the
    ``--full`` flag).
    """
    if state.full:
        return payload

    if kind == "activity" and isinstance(payload, dict):
        return project_activity(payload)
    if kind == "activity_list" and isinstance(payload, list):
        return project_activity_list(payload)
    if kind == "sleep" and isinstance(payload, dict):
        return project_sleep(payload)
    if kind == "health" and isinstance(payload, dict) and metric:
        return project_health(payload, metric)
    if kind == "summary" and isinstance(payload, dict):
        return project_summary(payload)
    if kind == "training_status" and isinstance(payload, dict):
        return project_training_status(payload)
    # Remaining kinds (heart_rate, steps, body_battery, hrv, stress,
    # weight, readiness, records, progress) pass through raw so
    # projection functions can be added later without touching callers.
    return payload
