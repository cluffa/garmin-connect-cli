"""Auth sub-commands: login, status, logout."""

import typer

from garmin_cli import client
from garmin_cli.output import command_output

auth_app = typer.Typer(help="Authenticate to Garmin Connect.", no_args_is_help=True)


@auth_app.command()
@command_output
def login():
    """Log in using GARMIN_EMAIL/GARMIN_PASSWORD; prompts for MFA if required."""
    client.do_login(prompt_mfa=lambda: typer.prompt("MFA code"))
    return {"loggedIn": True, "tokenDir": client.token_dir()}


@auth_app.command()
@command_output
def status():
    """Report whether a valid cached token exists."""
    return {"authenticated": client.token_status()}


@auth_app.command()
@command_output
def logout():
    """Delete the cached token."""
    client.logout()
    return {"loggedOut": True}
