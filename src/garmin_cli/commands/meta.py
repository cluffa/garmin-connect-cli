from __future__ import annotations

import typer
from typer.core import TyperGroup

from garmin_cli.output import command_output
from garmin_cli.workouts.schema import spec_json_schema


def _walk(command, prefix: str, out: list) -> None:
    if isinstance(command, TyperGroup):
        for name, sub in command.commands.items():
            child_prefix = f"{prefix} {name}".strip()
            _walk(sub, child_prefix, out)
    else:
        out.append({"name": prefix, "help": (command.help or "").strip()})


def register(app: typer.Typer) -> None:
    @app.command()
    @command_output
    def capabilities():
        """Emit all commands and the workout schema for one-call discovery."""
        cli_command = typer.main.get_command(app)
        commands: list[dict] = []
        _walk(cli_command, "", commands)
        commands = [c for c in commands if c["name"] and c["name"] != "capabilities"]
        return {
            "commands": sorted(commands, key=lambda c: c["name"]),
            "workoutSchema": spec_json_schema(),
        }
