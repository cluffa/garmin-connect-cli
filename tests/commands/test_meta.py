"""Tests for the capabilities discovery command."""

import json

from typer.testing import CliRunner

from garmin_cli.cli import app

runner = CliRunner()


def test_capabilities_lists_groups_and_schema():
    result = runner.invoke(app, ["capabilities"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)["data"]
    names = {c["name"] for c in data["commands"]}
    assert {"workout create", "activity list", "stats summary"} <= names
    assert "workouts" in data["workoutSchema"]["properties"]
