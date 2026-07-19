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
    "trainingEffect",
    "anaerobicTrainingEffect",
    "trainingEffectLabel",
]

_METERS_PER_MILE = 1609.34


def slim_activity(a: dict) -> dict:
    """Return only the well-known keys present in *a*."""
    return {k: a[k] for k in _ACTIVITY_KEYS if k in a}


# ── Public per-kind projection helpers ─────────────────────────


def project_activity(activity: dict) -> dict:
    """Slim an activity dict to essential fields."""
    return slim_activity(activity)


def project_activity_list(activities: list[dict], miles: bool = False) -> list[dict]:
    """Slim every activity in a list.

    When *miles* is ``True``, each activity dict gains two computed
    fields: ``distance_mi`` (float, rounded to 2 dp) and
    ``pace_per_mi`` (``"mm:ss"`` string or ``None`` when there is no
    distance or duration).
    """
    result: list[dict] = []
    for a in activities:
        slim = slim_activity(a)
        if miles:
            dist_m = a.get("distance")
            dur_s = a.get("duration")
            if dist_m is not None and dist_m > 0:
                slim["distance_mi"] = round(dist_m / _METERS_PER_MILE, 2)
                if dur_s is not None and dur_s > 0:
                    pace_sec = dur_s / (dist_m / _METERS_PER_MILE)
                    mins = int(pace_sec // 60)
                    secs = int(pace_sec % 60)
                    slim["pace_per_mi"] = f"{mins}:{secs:02d}"
                else:
                    slim["pace_per_mi"] = None
            else:
                slim["distance_mi"] = 0.0
                slim["pace_per_mi"] = None
        result.append(slim)
    return result


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


def project_summary(stats: dict) -> dict:
    """Project a daily stats summary to a curated view.

    Keys produced (when source data is available):
        steps, step_goal_pct, distance_km, active_minutes,
        highly_active_minutes, moderate_intensity_minutes,
        vigorous_intensity_minutes, resting_hr, hr_range, floors, calories,
        avg_spo2, avg_respiration, avg_stress, max_stress, body_battery,
        body_battery_high, body_battery_low.

    Falls back to the raw payload when the input is non-empty but
    no known keys matched (e.g. API contract drift).
    """
    result: dict[str, Any] = {}

    steps = stats.get("totalSteps")
    if steps is not None:
        result["steps"] = steps
        goal = stats.get("dailyStepGoal") or stats.get("stepGoal")
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

    moderate = stats.get("moderateIntensityMinutes")
    if moderate is not None:
        result["moderate_intensity_minutes"] = moderate

    vigorous = stats.get("vigorousIntensityMinutes")
    if vigorous is not None:
        result["vigorous_intensity_minutes"] = vigorous

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

    cals = stats.get("totalKilocalories")
    if cals is None:
        cals = stats.get("caloriesOut")
    if cals is not None:
        result["calories"] = round(cals)

    spo2 = stats.get("averageSpo2")
    if spo2 is not None:
        result["avg_spo2"] = spo2

    resp = stats.get("avgWakingRespirationValue")
    if resp is not None:
        result["avg_respiration"] = resp

    avg_stress = stats.get("averageStressLevel")
    if avg_stress is not None:
        result["avg_stress"] = avg_stress

    max_stress = stats.get("maxStressLevel")
    if max_stress is not None:
        result["max_stress"] = max_stress

    bb_recent = stats.get("bodyBatteryMostRecentValue")
    if bb_recent is not None:
        result["body_battery"] = bb_recent

    bb_high = stats.get("bodyBatteryHighestValue")
    if bb_high is not None:
        result["body_battery_high"] = bb_high

    bb_low = stats.get("bodyBatteryLowestValue")
    if bb_low is not None:
        result["body_battery_low"] = bb_low

    # Fall back to raw payload to prevent silent data loss
    if not result and stats:
        return stats
    return result


_SPLIT_TYPE_LABELS: dict[str, str] = {
    "INTERVAL_WARMUP": "Warmup",
    "INTERVAL_ACTIVE": "Interval",
    "INTERVAL_COOLDOWN": "Cooldown",
    "INTERVAL_REST": "Rest",
    "RWD_RUN": "Run",
    "RWD_WALK": "Walk",
    "RWD_STAND": "Pause",
    "RWD_OTHER": "Other",
}


def _format_pace(duration_min: float, distance_mi: float) -> str:
    """Return pace as mm:ss per mile, or '--' when not meaningful."""
    if distance_mi <= 0 or duration_min <= 0:
        return "--"
    pace = duration_min / distance_mi
    mins = int(pace)
    secs = round((pace - mins) * 60)
    return f"{mins}:{secs:02d}"


def _lap_intensity_label(raw: str) -> str:
    """Map lap intensityType to a human label."""
    labels = {
        "INTERVAL": "Interval",
        "ACTIVE": "Active",
        "REST": "Rest",
        "WARMUP": "Warmup",
        "COOLDOWN": "Cooldown",
        "RECOVERY": "Recovery",
    }
    return labels.get(raw, raw)


def project_splits(activity: dict) -> dict:
    """Project per-lap data from ``get_activity_splits()`` to curated fields.

    Expects the ``lapDTOs`` payload returned by the Garmin Connect
    ``/splits`` endpoint (rich per-lap data with cadence, power,
    stride, ground contact time, etc.).
    """
    laps_raw: list[dict] = activity.get("lapDTOs") or []

    laps = []
    total_mi = 0.0
    total_dur_s = 0.0
    for s in laps_raw:
        distance_m = s.get("distance") or 0
        distance_mi = round(distance_m / 1609.34, 2)
        duration_sec = s.get("duration") or 0
        duration_min = round(duration_sec / 60, 1)
        pace_str = _format_pace(duration_min, distance_mi)

        total_mi += distance_mi
        total_dur_s += duration_sec

        intensity = _lap_intensity_label(s.get("intensityType", ""))

        entry: dict[str, Any] = {
            "distance_mi": distance_mi,
            "duration_min": duration_min,
            "pace_per_mi": pace_str,
            "lap_type": intensity,
        }

        # Remap Garmin API field names to stable output keys
        for src, dest in [
            ("averageHR", "avg_hr"),
            ("maxHR", "max_hr"),
            ("averageRunCadence", "cadence"),
            ("strideLength", "stride_length"),
            ("verticalOscillation", "vertical_oscillation"),
            ("averagePower", "avg_power"),
            ("normalizedPower", "normalized_power"),
            ("groundContactTime", "ground_contact_ms"),
            ("calories", "calories"),
            ("movingDuration", "moving_duration_s"),
        ]:
            val = s.get(src)
            if val is not None:
                entry[dest] = val if dest != "cadence" else round(val)
            else:
                entry[dest] = None

        laps.append(entry)

    # Date comes from the first lap's startTimeGMT if available
    date = laps_raw[0].get("startTimeGMT") if laps_raw else None

    return {
        "date": date,
        "total_distance_mi": round(total_mi, 2),
        "total_duration_sec": round(total_dur_s, 1),
        "lap_count": len(laps),
        "splits": laps,
    }


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


def project_weekly_volume(data: dict) -> dict:
    """Project a weekly running volume summary dict.

    Keys produced (when source data is available):
        week_total_mi, previous_week_mi, four_week_avg_mi,
        run_count, longest_run_mi, total_duration_hours, avg_daily_mi.
    """
    return data


# ── Generic dispatcher (used by command infrastructure) ────────


def project(kind: str, payload: Any, miles: bool = False) -> Any:
    """Dispatch *payload* through the appropriate projection.

    When ``state.full`` is ``True`` the raw payload is returned unchanged.

    Supported *kind* values:
        activity, activity_list, sleep, summary, training_status,
        weekly_volume.
    All other kinds pass through unchanged (but still respect the
    ``--full`` flag).
    """
    if state.full:
        return payload

    if kind == "activity" and isinstance(payload, dict):
        return project_activity(payload)
    if kind == "activity_list" and isinstance(payload, list):
        return project_activity_list(payload, miles=miles)
    if kind == "sleep" and isinstance(payload, dict):
        return project_sleep(payload)
    if kind == "summary" and isinstance(payload, dict):
        return project_summary(payload)
    if kind == "training_status" and isinstance(payload, dict):
        return project_training_status(payload)
    if kind == "splits" and isinstance(payload, dict):
        return project_splits(payload)
    if kind == "weekly_volume" and isinstance(payload, dict):
        return project_weekly_volume(payload)
    # Remaining kinds (heart_rate, steps, body_battery, hrv, stress,
    # weight, readiness, records, progress) pass through raw so
    # projection functions can be added later without touching callers.
    return payload
