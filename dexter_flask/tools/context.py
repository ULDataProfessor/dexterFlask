"""Per-invocation tool context (progress callbacks)."""
from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar

OnProgress = Callable[[str], None]

_tool_progress: ContextVar[OnProgress | None] = ContextVar("tool_progress", default=None)


def set_tool_progress(cb: OnProgress | None) -> None:
    _tool_progress.set(cb)


def emit_tool_progress(message: str) -> None:
    cb = _tool_progress.get()
    if cb:
        cb(message)
