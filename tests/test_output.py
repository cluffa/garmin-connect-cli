import json

import pytest

from garmin_cli import state
from garmin_cli.output import (
    AuthError,
    UsageError,
    command_output,
    emit_batch,
    render,
)


def setup_function():
    state.fmt = "json"
    state.full = False


def test_render_json_compact():
    out = render({"ok": True, "data": {"a": 1}})
    assert out == '{"ok":true,"data":{"a":1}}'


def test_render_toon_uses_toon(monkeypatch):
    state.fmt = "toon"
    out = render({"ok": True, "data": {"rows": [{"x": 1}, {"x": 2}]}})
    # TOON renders compact tabular output, not JSON
    # TOON renders compact YAML-like output, not JSON
    assert "rows[2," in out
    assert not out.startswith("{")


def test_command_output_success(capsys):
    @command_output
    def cmd():
        return {"hello": "world"}

    with pytest.raises(SystemExit) as exc:
        cmd()
    assert exc.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert out == {"ok": True, "data": {"hello": "world"}}


def test_command_output_cli_error(capsys):
    @command_output
    def cmd():
        raise AuthError("no token")

    with pytest.raises(SystemExit) as exc:
        cmd()
    assert exc.value.code == 3
    err = json.loads(capsys.readouterr().err)
    assert err == {"ok": False, "error": {"type": "auth", "message": "no token"}}


def test_command_output_unexpected_error(capsys):
    @command_output
    def cmd():
        raise ValueError("boom")

    with pytest.raises(SystemExit) as exc:
        cmd()
    assert exc.value.code == 1
    err = json.loads(capsys.readouterr().err)
    assert err["error"]["type"] == "internal"


def test_emit_batch_all_ok(capsys):
    with pytest.raises(SystemExit) as exc:
        emit_batch([{"index": 0, "ok": True}])
    assert exc.value.code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["data"]["created"] == 1
    assert out["data"]["failed"] == 0


def test_emit_batch_partial_failure(capsys):
    with pytest.raises(SystemExit) as exc:
        emit_batch([{"index": 0, "ok": True}, {"index": 1, "ok": False}])
    assert exc.value.code == 4
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False
    assert out["data"] == {
        "results": [{"index": 0, "ok": True}, {"index": 1, "ok": False}],
        "created": 1,
        "failed": 1,
    }
