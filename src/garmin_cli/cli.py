import typer

from garmin_cli import state
from garmin_cli.commands.auth import auth_app

app = typer.Typer(
    add_completion=False,
    help="Agent-first CLI for Garmin Connect.",
    no_args_is_help=True,
)


@app.callback()
def main(
    fmt: str = typer.Option("json", "--format", help="Output format: json or toon."),
    full: bool = typer.Option(False, "--full", help="Return full raw payloads."),
) -> None:
    """Global options applied to every command."""
    if fmt not in ("json", "toon"):
        raise typer.BadParameter("format must be 'json' or 'toon'")
    state.fmt = fmt
    state.full = full


app.add_typer(auth_app, name="auth")
