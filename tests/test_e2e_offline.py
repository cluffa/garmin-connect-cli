"""End-to-end offline tests — exercise the full pipeline without a live
Garmin API."""

import json

from typer.testing import CliRunner

from garmin_cli import state
from garmin_cli.cli import app

runner = CliRunner()

PLAN = json.dumps(
    {
        "workouts": [
            {
                "name": "Wk1 Tue",
                "sport": "running",
                "date": "2026-07-21",
                "steps": [
                    {"type": "warmup", "duration": {"time": "10min"}},
                    {
                        "repeat": 5,
                        "steps": [
                            {
                                "type": "interval",
                                "duration": {"distance": "1km"},
                                "target": {"pace": ["4:00/km", "3:50/km"]},
                            },
                            {"type": "recovery", "duration": {"time": "2min"}},
                        ],
                    },
                    {"type": "cooldown", "duration": {"time": "10min"}},
                ],
            },
        ]
    }
)


def setup_function():
    state.fmt = "json"


def test_validate_full_week():
    """Validate a full workout week plan (dry-run, no API call)."""
    result = runner.invoke(app, ["workout", "validate", "--json", PLAN])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert out["data"]["results"][0]["name"] == "Wk1 Tue"


def test_validate_toon_output():
    """Validate with TOON format produces YAML-like output, not JSON."""
    result = runner.invoke(
        app,
        ["--format", "toon", "workout", "validate", "--json", PLAN],
    )
    assert result.exit_code == 0
    assert "results" in result.stdout  # TOON still names the array


def test_schema_roundtrip():
    """The schema endpoint returns a valid JSON schema with workouts."""
    result = runner.invoke(app, ["workout", "schema"])
    schema = json.loads(result.stdout)["data"]
    assert schema["properties"]["workouts"]
