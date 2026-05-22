"""Tests for Flask dev-server startup defaults (security hardening)."""

from __future__ import annotations

import os
import unittest.mock as mock


def _run_kwargs(env_overrides: dict, *, remove: list[str] | None = None) -> dict:
    """Call _get_run_kwargs with a controlled environment."""
    from dexter_flask.app import _get_run_kwargs

    env = dict(os.environ)
    env.update(env_overrides)
    for k in remove or []:
        env.pop(k, None)
    with mock.patch.dict(os.environ, env, clear=True):
        return _get_run_kwargs()


def test_default_host_is_localhost() -> None:
    """Dev server must bind to 127.0.0.1 when FLASK_HOST is not set."""
    kwargs = _run_kwargs({}, remove=["FLASK_HOST"])
    assert kwargs["host"] == "127.0.0.1", f"Expected 127.0.0.1 but got {kwargs['host']!r}"


def test_flask_host_override() -> None:
    """FLASK_HOST env var lets operators intentionally expose non-local binding."""
    kwargs = _run_kwargs({"FLASK_HOST": "0.0.0.0"})
    assert kwargs["host"] == "0.0.0.0"


def test_default_debug_is_off() -> None:
    """Debug mode must be disabled unless FLASK_DEBUG=1 is explicitly set."""
    kwargs = _run_kwargs({}, remove=["FLASK_DEBUG"])
    assert kwargs["debug"] is False


def test_flask_debug_enabled_by_env() -> None:
    """Setting FLASK_DEBUG=1 enables debug mode."""
    kwargs = _run_kwargs({"FLASK_DEBUG": "1"})
    assert kwargs["debug"] is True


def test_default_port() -> None:
    """Default port is 5050 when PORT env var is absent."""
    kwargs = _run_kwargs({}, remove=["PORT"])
    assert kwargs["port"] == 5050


def test_port_override() -> None:
    """PORT env var is respected."""
    kwargs = _run_kwargs({"PORT": "8080"})
    assert kwargs["port"] == 8080

