"""Tests for the auth command group."""

import json

from typer.testing import CliRunner

from garmin_cli import client, state
from garmin_cli.cli import app

runner = CliRunner()


def setup_function():
    state.fmt = "json"
    state.full = False


# ── login ─────────────────────────────────────────────────────────────────


def test_login_success(monkeypatch):
    called = False

    def fake_login(prompt_mfa=None):
        nonlocal called
        called = True

    monkeypatch.setattr(client, "do_login", fake_login)
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert out["data"]["loggedIn"] is True
    assert called is True


def test_login_auth_error(monkeypatch):
    from garmin_cli.output import AuthError

    def raise_error(prompt_mfa=None):
        raise AuthError("bad password")

    monkeypatch.setattr(client, "do_login", raise_error)
    result = runner.invoke(app, ["auth", "login"])
    assert result.exit_code == 3
    err = json.loads(result.stderr)
    assert err == {"ok": False, "error": {"type": "auth", "message": "bad password"}}


# ── status ────────────────────────────────────────────────────────────────


def test_status_authenticated(monkeypatch):
    monkeypatch.setattr(client, "token_status", lambda: True)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out == {"ok": True, "data": {"authenticated": True}}


def test_status_unauthenticated(monkeypatch):
    monkeypatch.setattr(client, "token_status", lambda: False)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out == {"ok": True, "data": {"authenticated": False}}


# ── logout ────────────────────────────────────────────────────────────────


def test_logout_success(monkeypatch):
    called = False

    def fake_logout():
        nonlocal called
        called = True

    monkeypatch.setattr(client, "logout", fake_logout)
    result = runner.invoke(app, ["auth", "logout"])
    assert result.exit_code == 0
    out = json.loads(result.stdout)
    assert out == {"ok": True, "data": {"loggedOut": True}}
    assert called is True


# ── no_args_is_help ───────────────────────────────────────────────────────


def test_auth_group_help_shows_commands():
    result = runner.invoke(app, ["auth", "--help"])
    assert result.exit_code == 0
    assert "login" in result.stdout
    assert "status" in result.stdout
    assert "logout" in result.stdout
