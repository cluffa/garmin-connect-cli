import functools
import json
import sys

import toon

from garmin_cli import state


class CliError(Exception):
    type = "internal"
    exit_code = 1

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class UsageError(CliError):
    type = "usage"
    exit_code = 2


class AuthError(CliError):
    type = "auth"
    exit_code = 3


class ApiError(CliError):
    type = "api"
    exit_code = 4


class InternalError(CliError):
    type = "internal"
    exit_code = 1


def render(envelope: dict) -> str:
    if state.fmt == "toon":
        return toon.encode(envelope)
    return json.dumps(envelope, separators=(",", ":"), default=str)


def _emit(envelope: dict, stream, code: int) -> None:
    print(render(envelope), file=stream)
    raise SystemExit(code)


def command_output(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            data = fn(*args, **kwargs)
        except CliError as e:
            _emit({"ok": False, "error": {"type": e.type, "message": e.message}}, sys.stderr, e.exit_code)
        except Exception as e:  # noqa: BLE001 - top-level guard
            _emit({"ok": False, "error": {"type": "internal", "message": str(e)}}, sys.stderr, 1)
        else:
            _emit({"ok": True, "data": data}, sys.stdout, 0)

    return wrapper


def emit_batch(results: list[dict]) -> None:
    created = sum(1 for r in results if r.get("ok"))
    failed = len(results) - created
    envelope = {
        "ok": failed == 0,
        "data": {"results": results, "created": created, "failed": failed},
    }
    _emit(envelope, sys.stdout, 0 if failed == 0 else 4)
