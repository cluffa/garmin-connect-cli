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


def test_token_dir_default_is_mcp_store(monkeypatch, tmp_path):
    """With no override and no existing tokens, default to the MCP store."""
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    monkeypatch.setattr(client, "MCP_TOKEN_DIR", tmp_path / "mcp")
    monkeypatch.setattr(client, "LEGACY_TOKEN_DIR", tmp_path / "legacy")
    assert client.token_dir() == str(tmp_path / "mcp")


def test_token_dir_prefers_mcp_when_mcp_has_tokens(monkeypatch, tmp_path):
    """The MCP store wins even when the legacy dir also holds a token."""
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    mcp = tmp_path / "mcp"
    legacy = tmp_path / "legacy"
    for d in (mcp, legacy):
        d.mkdir()
        (d / "garmin_tokens.json").write_text("{}")
    monkeypatch.setattr(client, "MCP_TOKEN_DIR", mcp)
    monkeypatch.setattr(client, "LEGACY_TOKEN_DIR", legacy)
    assert client.token_dir() == str(mcp)


def test_token_dir_falls_back_to_legacy(monkeypatch, tmp_path):
    """Use the legacy dir only when it has a token and the MCP store does not."""
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    mcp = tmp_path / "mcp"
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "garmin_tokens.json").write_text("{}")
    monkeypatch.setattr(client, "MCP_TOKEN_DIR", mcp)
    monkeypatch.setattr(client, "LEGACY_TOKEN_DIR", legacy)
    assert client.token_dir() == str(legacy)


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


def test_do_login_creates_private_token_dir(monkeypatch, tmp_path):
    """The token store must be created 0o700 — tokens are account secrets."""
    store = tmp_path / "tokens"
    monkeypatch.setenv("GARMINTOKENS", str(store))
    monkeypatch.setenv("GARMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    FakeGarmin.fail = False
    client.do_login(prompt_mfa=lambda: "000000", factory=FakeGarmin)
    assert store.is_dir()
    assert (store.stat().st_mode & 0o777) == 0o700


def test_do_login_tightens_existing_loose_dir(monkeypatch, tmp_path):
    """A pre-existing world-readable store is tightened to 0o700 on login."""
    store = tmp_path / "tokens"
    store.mkdir(mode=0o755)
    monkeypatch.setenv("GARMINTOKENS", str(store))
    monkeypatch.setenv("GARMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    FakeGarmin.fail = False
    client.do_login(prompt_mfa=lambda: "000000", factory=FakeGarmin)
    assert (store.stat().st_mode & 0o777) == 0o700


def test_do_login_failure(monkeypatch):
    monkeypatch.setenv("GARMIN_EMAIL", "a@b.com")
    monkeypatch.setenv("GARMIN_PASSWORD", "pw")
    FakeGarmin.fail = True
    with pytest.raises(AuthError):
        client.do_login(prompt_mfa=lambda: "000000", factory=FakeGarmin)
    FakeGarmin.fail = False
