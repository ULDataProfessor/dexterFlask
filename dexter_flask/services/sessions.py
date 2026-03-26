"""Per-session chat history for API/gateway."""

from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

from dexter_flask.agent.chat_history import InMemoryChatHistory, _Message

_sessions: dict[str, InMemoryChatHistory] = {}
_db_lock = threading.Lock()
_sessions_lock = threading.Lock()


def _db_path() -> Path:
    raw = os.getenv("DEXTER_SESSIONS_DB_PATH")
    if raw:
        return Path(raw)
    return Path(".dexter") / "sessions.db"


def _ensure_db() -> Path:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_sessions (
                session_key TEXT NOT NULL,
                message_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                answer TEXT,
                summary TEXT,
                PRIMARY KEY (session_key, message_id)
            )
            """
        )
    return db


def _load_messages(session_key: str) -> list[_Message]:
    db = _ensure_db()
    with sqlite3.connect(db) as conn:
        rows = conn.execute(
            """
            SELECT message_id, query, answer, summary
            FROM chat_sessions
            WHERE session_key = ?
            ORDER BY message_id ASC
            """,
            (session_key,),
        ).fetchall()
    return [
        _Message(id=int(mid), query=str(q), answer=a, summary=s)
        for mid, q, a, s in rows
    ]


class SQLiteChatHistory(InMemoryChatHistory):
    def __init__(self, session_key: str, model: str) -> None:
        super().__init__(model=model)
        self._session_key = session_key
        self._messages = _load_messages(session_key)

    def save_user_query(self, query: str) -> None:
        super().save_user_query(query)
        last = self._messages[-1]
        with _db_lock:
            db = _ensure_db()
            with sqlite3.connect(db) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO chat_sessions
                    (session_key, message_id, query, answer, summary)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        self._session_key,
                        last.id,
                        last.query,
                        last.answer,
                        last.summary,
                    ),
                )

    def save_answer(self, answer: str) -> None:
        before = len(self._messages)
        super().save_answer(answer)
        if not self._messages or len(self._messages) != before:
            return
        last = self._messages[-1]
        with _db_lock:
            db = _ensure_db()
            with sqlite3.connect(db) as conn:
                conn.execute(
                    """
                    UPDATE chat_sessions
                    SET answer = ?, summary = ?
                    WHERE session_key = ? AND message_id = ?
                    """,
                    (last.answer, last.summary, self._session_key, last.id),
                )

    def prune_last_turn(self) -> None:
        if not self._messages:
            return
        last_id = self._messages[-1].id
        super().prune_last_turn()
        with _db_lock:
            db = _ensure_db()
            with sqlite3.connect(db) as conn:
                conn.execute(
                    """
                    DELETE FROM chat_sessions
                    WHERE session_key = ? AND message_id = ?
                    """,
                    (self._session_key, last_id),
                )


def get_chat_history(session_key: str, model: str) -> InMemoryChatHistory:
    with _sessions_lock:
        s = _sessions.get(session_key)
        if s is None:
            s = SQLiteChatHistory(session_key=session_key, model=model)
            _sessions[session_key] = s
        else:
            s.set_model(model)
    return s
