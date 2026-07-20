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
# Sources: Intervals.icu forum, HarryOnline FIT File Viewer, Runalyze.
_FIT_MESSAGE_NAMES: dict[int, str] = {
    22: "sensor_config",
    79: "alt_vo2max",
    104: "device_aux_info",
    113: "device_aux_info_2",
    140: "firstbeat_metrics",
    141: "activity_meta",
    147: "hrm_device_info",
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
_FIT_FIELD_NAMES: dict[tuple[int, int], str] = {
    # firstbeat_metrics (140) — https://forum.intervals.icu/t/all-fields-from-garmin-activity/28097
    (140, 1): "new_hr_max",
    (140, 4): "aerobic_training_load",
    (140, 7): "vo2max_metmax",  # × 3.5 ÷ 65536 for ml/kg/min
    (140, 9): "recovery_time_min",
    (140, 14): "lactate_threshold_hr",
    (140, 15): "lactate_threshold_pace_ms",
    (140, 17): "performance_condition",
    (140, 20): "anaerobic_training_load",
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
