"""Global test fixtures — reset process-level state before every test."""

import pytest
import garmin_cli.state as state


@pytest.fixture(autouse=True)
def reset_state():
    state.fmt = "json"
    state.full = False
