import typer

from garmin_cli import state
from garmin_cli.commands.activity import activity_app
from garmin_cli.commands.auth import auth_app
from garmin_cli.commands.badge import badge_app
from garmin_cli.commands.health import health_app
from garmin_cli.commands.meta import register as register_meta
from garmin_cli.commands.stats import stats_app
from garmin_cli.commands.workout import workout_app

app = typer.Typer(
    add_completion=False,
    help="Agent-first CLI for Garmin Connect.",
    no_args_is_help=True,
)


@app.callback()
def main(
    fmt: str = typer.Option("json", "--format", help="Output format: json, json-pretty, or toon."),
    full: bool = typer.Option(False, "--full", help="Return full raw payloads."),
) -> None:
    """Global options applied to every command."""
    if fmt not in ("json", "json-pretty", "toon"):
        raise typer.BadParameter("format must be 'json', 'json-pretty', or 'toon'")
    state.fmt = fmt
    state.full = full


app.add_typer(activity_app, name="activity")
app.add_typer(auth_app, name="auth")
app.add_typer(badge_app, name="badge")
app.add_typer(health_app, name="health")
app.add_typer(stats_app, name="stats")
app.add_typer(workout_app, name="workout")

register_meta(app)
