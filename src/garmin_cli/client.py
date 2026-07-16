"""Garmin Connect client wrapper — auth/session and token caching."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from garminconnect import Garmin

from garmin_cli.output import AuthError

# Token store used by the Garmin Workout Pipeline MCP server
# (https://github.com/cluffa/Garmin-Workout-Pipeline). Sharing this directory
# lets the CLI reuse the session authenticated by the MCP server — and vice
# versa — so a single `garmin auth login` (or MCP login) works for both.
MCP_TOKEN_DIR = Path.home() / ".garmin-workout-pipeline" / "tokens"

# Location used by earlier CLI-only versions, kept for backward compatibility.
LEGACY_TOKEN_DIR = Path.home() / ".garmin-cli"

# File written by garminconnect inside a token-store directory.
_TOKEN_FILE = "garmin_tokens.json"


def _has_tokens(path: Path) -> bool:
    """Return ``True`` when *path* holds a cached Garmin token file."""
    return (path / _TOKEN_FILE).exists()


def token_dir() -> str:
    """Return the directory used for cached token files.

    Precedence:

    1. The ``GARMINTOKENS`` environment variable, when set — explicit override.
    2. The Garmin Workout Pipeline MCP server's token store, so the CLI reuses
       the session authenticated through the MCP server (and writes new logins
       where the MCP server will find them).
    3. The legacy ``~/.garmin-cli`` directory, but only when it already holds a
       token and the MCP store does not — backward compatibility for existing
       CLI-only installs.
    """
    env = os.getenv("GARMINTOKENS")
    if env:
        return env
    if not _has_tokens(MCP_TOKEN_DIR) and _has_tokens(LEGACY_TOKEN_DIR):
        return str(LEGACY_TOKEN_DIR)
    return str(MCP_TOKEN_DIR)


def load_client(factory=Garmin):
    """Build and return an authenticated Garmin client from cached tokens.

    The *factory* parameter is injected during tests to avoid live API
    calls.  Raises :class:`AuthError` when no valid cached token exists.
    """
    store = token_dir()
    garmin = factory()
    try:
        garmin.login(store)
    except Exception as e:  # noqa: BLE001
        raise AuthError(
            f"no valid token; run `garmin auth login` ({e})"
        ) from None
    return garmin


def do_login(prompt_mfa, factory=Garmin) -> None:
    """Authenticate with ``GARMIN_EMAIL`` / ``GARMIN_PASSWORD`` and cache
    the session token.

    *prompt_mfa* is a ``() -> str`` callback that returns the MFA code when
    the account requires two-factor authentication.  Raises
    :class:`AuthError` if the credentials are missing or the login fails.
    """
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        raise AuthError("GARMIN_EMAIL and GARMIN_PASSWORD must be set")

    store = token_dir()
    Path(store).mkdir(parents=True, exist_ok=True)
    garmin = factory(email=email, password=password, prompt_mfa=prompt_mfa)
    try:
        garmin.login(store)
    except Exception as e:  # noqa: BLE001
        raise AuthError(f"login failed: {e}") from None


def logout() -> None:
    """Remove the cached token directory."""
    store = Path(token_dir())
    if store.exists():
        shutil.rmtree(store, ignore_errors=True)


def token_status() -> bool:
    """Return ``True`` when a valid cached token exists."""
    try:
        load_client()
        return True
    except AuthError:
        return False
