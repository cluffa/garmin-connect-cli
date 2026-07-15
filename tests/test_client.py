"""Tests for garmin_cli.client — auth/session management."""

import pytest

from garmin_cli import client
from garmin_cli.output import AuthError


class FakeGarmin:
    """Minimal stand-in for garminconnect.Garmin."""

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.logged_in = False
        self.tokenstore = None

    def login(self, tokenstore=None):
        if getattr(FakeGarmin, "fail", False):
            raise RuntimeError("no tokens")
        self.tokenstore = tokenstore
        self.logged_in = True
        return (None, None)


# ── token_dir ─────────────────────────────────────────────────────────────


def test_token_dir_env(monkeypatch, tmp_path):
    monkeypatch.setenv("GARMINTOKENS", str(tmp_path))
    assert client.token_dir() == str(tmp_path)


def test_token_dir_default(monkeypatch):
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    result = client.token_dir()
    assert result.endswith(".garmin-cli")


# ── load_client ───────────────────────────────────────────────────────────


def test_load_client_success(monkeypatch):
    FakeGarmin.fail = False
    g = client.load_client(factory=FakeGarmin)
    assert g.logged_in is True


def test_load_client_no_token(monkeypatch):
    FakeGarmin.fail = True
    with pytest.raises(AuthError):
        client.load_client(factory=FakeGarmin)
    FakeGarmin.fail = False  # reset


# ── do_login ──────────────────────────────────────────────────────────────


def test_do_login_missing_creds(monkeypatch):
    monkeypatch.delenv("GARMIN_EMAIL", raising=False)
    monkeypatch.delenv("GARMIN_PASSWORD", raising=False)
    with pytest.raises(AuthError):
        client.do_login(prompt_mfa=lambda: "000000", factory=FakeGarmin)


def test_do_login_success(monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    FakeGarmin.fail = False
    # Should not raise
    client.do_login(prompt_mfa=lambda: "000000", factory=FakeGarmin)


def test_do_login_failure(monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    FakeGarmin.fail = True
    with pytest.raises(AuthError):
        client.do_login(prompt_mfa=lambda: "000000", factory=FakeGarmin)
    FakeGarmin.fail = False
