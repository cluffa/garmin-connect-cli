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
