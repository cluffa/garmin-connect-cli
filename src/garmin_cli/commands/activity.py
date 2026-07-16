from __future__ import annotations

import re

import typer
from garminconnect import Garmin

from garmin_cli import client
from garmin_cli.output import UsageError, command_output
from garmin_cli.projections import project

activity_app = typer.Typer(help="Retrieve activities.", no_args_is_help=True)

_FORMATS = {
    "tcx": Garmin.ActivityDownloadFormat.TCX,
    "gpx": Garmin.ActivityDownloadFormat.GPX,
    "fit": Garmin.ActivityDownloadFormat.ORIGINAL,
}


@activity_app.command(name="list")
@command_output
def list_(
    limit: int = typer.Option(20, "--limit"),
    start: int = typer.Option(0, "--start"),
    activity_type: str = typer.Option(None, "--type"),
):
    """List recent activities (slim by default)."""
    data = client.load_client().get_activities(start, limit, activity_type)
    return project("activity_list", data)


@activity_app.command()
@command_output
def get(activity_id: str = typer.Argument(...)):
    """Get one activity's details (slim by default)."""
    data = client.load_client().get_activity(activity_id)
    return project("activity", data)


@activity_app.command()
@command_output
def download(
    activity_id: str = typer.Argument(...),
    fmt: str = typer.Option("tcx", "--format-file", help="tcx | gpx | fit"),
    out: str = typer.Option(None, "--out", help="Output file path."),
):
    """Download an activity file."""
    if fmt not in _FORMATS:
        raise UsageError("format must be tcx, gpx, or fit")
    if out is None and not re.fullmatch(r"[A-Za-z0-9_-]+", activity_id):
        raise UsageError(
            "activity_id must be alphanumeric to derive a filename; "
            "pass --out to choose an explicit path"
        )
    data = client.load_client().download_activity(activity_id, _FORMATS[fmt])
    path = out or f"activity_{activity_id}.{fmt}"
    with open(path, "wb") as fh:
        fh.write(data)
    return {"path": path, "bytes": len(data)}
