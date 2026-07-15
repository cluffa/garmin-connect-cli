from typer.testing import CliRunner

from garmin_cli.cli import app

runner = CliRunner()


def test_help_runs():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Garmin Connect" in result.output
