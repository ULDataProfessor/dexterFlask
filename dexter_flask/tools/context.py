"""Per-invocation tool context (progress callbacks)."""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar
from contextlib import contextmanager
from typing import Any

OnProgress = Callable[..., Any]

_tool_progress: ContextVar[OnProgress | None] = ContextVar(
    "tool_progress", default=None
)

_current_tool_name: ContextVar[str | None] = ContextVar("current_tool_name", default=None)


def set_tool_progress(cb: OnProgress | None) -> None:
    _tool_progress.set(cb)


@contextmanager
def tool_progress_tool(tool_name: str | None) -> Any:
    token = _current_tool_name.set(tool_name)
    try:
        yield
    finally:
        _current_tool_name.reset(token)


def get_current_tool_name() -> str | None:
    return _current_tool_name.get()


def emit_tool_progress(message: str, *, tool: str | None = None) -> None:
    cb = _tool_progress.get()
    if cb:
        tool_name = tool or _current_tool_name.get() or ""
        try:
            cb(tool_name, message)
        except TypeError:
            cb(message)
