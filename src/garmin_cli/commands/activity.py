from __future__ import annotations

import io
import json
import re
import sys
import zipfile

import typer
from garmin_fit_sdk import Decoder, Stream
from garminconnect import Garmin

from garmin_cli import client
from garmin_cli.output import UsageError, command_output
from garmin_cli.projections import project

activity_app = typer.Typer(help="Retrieve activities.", no_args_is_help=True)

_FORMATS = {
    "tcx": Garmin.ActivityDownloadFormat.TCX,
    "gpx": Garmin.ActivityDownloadFormat.GPX,
    "fit": Garmin.ActivityDownloadFormat.ORIGINAL,
    "json": None,  # sentinel — handled locally, not a Garmin API format
}

# Community-reverse-engineered names for undocumented Garmin FIT message types.
# Primary source: fit4ruby GlobalFitMessages.rb (Chris Schlaeger, GPLv2).
# Supplemented by: Intervals.icu forum, HarryOnline FIT File Viewer, Runalyze.
_FIT_MESSAGE_NAMES: dict[int, str] = {
    22: "data_sources",
    79: "user_data",
    104: "battery",
    113: "personal_records",
    140: "physiological_metrics",
    141: "epo_data",
    147: "sensor_settings",
    233: "sensor_data",
    288: "segment_info",
    325: "developer_data_1",
    326: "developer_data_2",
    327: "developer_data_3",
    329: "gps_summary",
    394: "training_meta",
    432: "event_extra",
    499: "device_settings_extra",
    517: "calibration",
    534: "extended_record",
    545: "training_effect_raw",
}

# Known field name overrides for undocumented message types.
# Key: (mesg_num, field_num), Value: human-readable field name.
# Sources: fit4ruby GlobalFitMessages.rb, Intervals.icu community.
_FIT_FIELD_NAMES: dict[tuple[int, int], str] = {
    # user_data (79) — pre-activity physiological profile
    (79, 0): "metmax",  # scale:1024, unit:MET → VO₂max = value × 3.5 ÷ 1024
    (79, 1): "age",
    (79, 2): "height",  # scale:100, m
    (79, 3): "weight",  # scale:10, kg
    (79, 4): "gender",
    (79, 5): "activity_class",  # scale:10
    (79, 6): "max_hr",
    (79, 8): "recovery_time",  # scale:60, hours
    (79, 10): "avg_resting_heart_rate",
    (79, 11): "running_lactate_threshold_heart_rate",
    (79, 12): "functional_threshold_power",
    (79, 13): "functional_threshold_speed",  # scale:36, m/s
    # battery (104) — per-device battery readings
    (104, 0): "unit_voltage",  # scale:1000, V
    (104, 2): "percent",  # %
    (104, 3): "current",  # mA (guessed)
    # personal_records (113) — best-effort records
    (113, 0): "longest_distance",
    (113, 1): "sport",
    (113, 2): "distance",  # scale:100, m
    (113, 3): "duration",  # scale:1000, ms
    (113, 4): "start_time",  # date_time
    (113, 5): "new_record",
    # physiological_metrics (140) — post-activity Firstbeat metrics
    (140, 0): "min_heart_rate",
    (140, 1): "max_heart_rate",
    (140, 4): "aerobic_training_effect",  # scale:10
    (140, 7): "metmax",  # scale:65536, unit:MET → VO₂max = value × 3.5 ÷ 65536
    (140, 9): "recovery_time",  # scale:60, hours
    (140, 14): "running_lactate_threshold_heart_rate",
    (140, 16): "running_lactate_threshold_speed",  # scale:36, m/s
    (140, 17): "performance_condition",
    (140, 20): "anaerobic_training_effect",  # scale:10
    (140, 29): "metmax_running",  # scale:65536, unit:MET — alternative VO₂max
    # sensor_settings (147) — connected sensor configuration
    (147, 0): "ant_id",
    (147, 2): "name",
    (147, 11): "calibration_factor",  # scale:10
    (147, 21): "wheel_size",  # mm
}


def _apply_fit_mappings(messages: dict) -> None:
    """Rename undocumented numeric message/field keys to human-readable names in place."""
    rename: list[tuple[str, str]] = []
    for key in messages:
        mesg_num = None
        if key.endswith("_mesgs"):
            # Already named — skip
            continue
        if key.isdigit():
            mesg_num = int(key)
        if mesg_num is not None and mesg_num in _FIT_MESSAGE_NAMES:
            rename.append((key, f"{_FIT_MESSAGE_NAMES[mesg_num]}_mesgs"))
            items = messages[key]
            if items:
                for item in items:
                    _rename_fields(item, mesg_num)

    for old_key, new_key in rename:
        messages[new_key] = messages.pop(old_key)


def _rename_fields(item: dict, mesg_num: int) -> None:
    """Rename known undocumented field numbers to names in a single record."""
    renames: dict[int, str] = {}
    for field_key in item:
        if isinstance(field_key, int):
            name = _FIT_FIELD_NAMES.get((mesg_num, field_key))
            if name:
                renames[field_key] = name
    for old, new in renames.items():
        item[new] = item.pop(old)


@activity_app.command(name="list")
@command_output
def list_(
    limit: int = typer.Option(20, "--limit"),
    start: int = typer.Option(0, "--start"),
    activity_type: str = typer.Option(None, "--type"),
    miles: bool = typer.Option(
        False, "--miles", "-m", help="Show distance in miles and pace per mile."
    ),
):
    """List recent activities (slim by default)."""
    data = client.load_client().get_activities(start, limit, activity_type)
    return project("activity_list", data, miles=miles)


@activity_app.command()
@command_output
def get(activity_id: str = typer.Argument(...)):
    """Get one activity's details (slim by default)."""
    data = client.load_client().get_activity(activity_id)
    return project("activity", data)


@activity_app.command()
@command_output
def splits(activity_id: str = typer.Argument(...)):
    """Display lap/split data for an activity. Uses the per-lap API endpoint for rich lap-level data (cadence, stride, power, HR)."""
    gc = client.load_client()
    data = gc.get_activity_splits(activity_id)
    return project("splits", data)


@activity_app.command()
@command_output
def download(
    activity_id: str = typer.Argument(...),
    fmt: str = typer.Option("tcx", "--format-file", help="tcx | gpx | fit | json"),
    out: str = typer.Option(None, "--out", help="Output file path. Use '-' for stdout."),
):
    """Download an activity file."""
    if fmt not in _FORMATS:
        raise UsageError("format must be tcx, gpx, fit, or json")
    if fmt == "json":
        # Download FIT, parse with official Garmin SDK, return structured JSON
        raw = client.load_client().download_activity(
            activity_id, Garmin.ActivityDownloadFormat.ORIGINAL
        )
        z = zipfile.ZipFile(io.BytesIO(raw))
        fit_bytes = z.read(z.namelist()[0])
        decoder = Decoder(Stream.from_bytes_io(io.BytesIO(fit_bytes)))
        messages, _errors = decoder.read()

        # Replace numeric message keys and field names with human-readable labels
        _apply_fit_mappings(messages)

        payload = json.dumps(messages, indent=2, default=str)

        if out == "-":
            sys.stdout.write(payload)
            raise SystemExit(0)

        path = out or f"activity_{activity_id}.json"
        with open(path, "w") as fh:
            fh.write(payload)
        return {"path": path, "bytes": len(payload)}
    if out is None and not re.fullmatch(r"[A-Za-z0-9_-]+", activity_id):
        raise UsageError(
            "activity_id must be alphanumeric to derive a filename; "
            "pass --out to choose an explicit path"
        )
    data = client.load_client().download_activity(activity_id, _FORMATS[fmt])

    if out == "-":
        sys.stdout.buffer.write(data)
        raise SystemExit(0)

    path = out or f"activity_{activity_id}.{fmt}"
    with open(path, "wb") as fh:
        fh.write(data)
    return {"path": path, "bytes": len(data)}
