from __future__ import annotations

import sqlite3


def test_get_chat_history_persists_to_sqlite(monkeypatch, tmp_path) -> None:
    import dexter_flask.services.sessions as sessions

    db_path = tmp_path / "sessions.db"
    monkeypatch.setenv("DEXTER_SESSIONS_DB_PATH", str(db_path))
    sessions._sessions.clear()

    hist = sessions.get_chat_history("s1", "gpt-5.4")
    monkeypatch.setattr(hist, "_generate_summary", lambda q, a: "summary")

    hist.save_user_query("hello")
    hist.save_answer("world")

    sessions._sessions.clear()
    loaded = sessions.get_chat_history("s1", "gpt-5.4")
    turns = loaded.get_recent_turns()
    assert turns == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "world"},
    ]


def test_prune_last_turn_removes_row(monkeypatch, tmp_path) -> None:
    import dexter_flask.services.sessions as sessions

    db_path = tmp_path / "sessions.db"
    monkeypatch.setenv("DEXTER_SESSIONS_DB_PATH", str(db_path))
    sessions._sessions.clear()

    hist = sessions.get_chat_history("s2", "gpt-5.4")
    monkeypatch.setattr(hist, "_generate_summary", lambda q, a: "summary")
    hist.save_user_query("hello")
    hist.save_answer("world")
    hist.prune_last_turn()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM chat_sessions WHERE session_key = ?",
            ("s2",),
        ).fetchone()
    assert rows is not None
    assert int(rows[0]) == 0
