"""Per-session chat history for API/gateway."""
from __future__ import annotations

from dexter_flask.agent.chat_history import InMemoryChatHistory

_sessions: dict[str, InMemoryChatHistory] = {}


def get_chat_history(session_key: str, model: str) -> InMemoryChatHistory:
    s = _sessions.get(session_key)
    if s is None:
        s = InMemoryChatHistory(model=model)
        _sessions[session_key] = s
    else:
        s.set_model(model)
    return s
