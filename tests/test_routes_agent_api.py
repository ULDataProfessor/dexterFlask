from dataclasses import dataclass
from typing import Any, Generator


def test_api_agent_run_returns_answer(monkeypatch) -> None:
    from dexter_flask.app import create_app
    from dexter_flask.routes import agent_api

    monkeypatch.setattr(
        agent_api, "run_agent_for_message", lambda body: "ANSWER"
    )

    app = create_app()
    c = app.test_client()
    payload = {
        "sessionKey": "s1",
        "query": "hello",
        "model": "gpt-5.4",
        "modelProvider": "openai",
        "maxIterations": 2,
        "isolatedSession": False,
    }
    r = c.post("/api/agent/run", json=payload)
    assert r.status_code == 200
    assert r.get_json() == {"answer": "ANSWER"}


@dataclass
class FakeHistory:
    user_queries: list[str]
    saved_answers: list[str]

    def save_user_query(self, query: str) -> None:
        self.user_queries.append(query)

    def save_answer(self, answer: str) -> None:
        self.saved_answers.append(answer)


class FakeAgent:
    def run(
        self, query: str, history: Any
    ) -> Generator[dict[str, Any], None, None]:
        from dexter_flask.tools.context import emit_tool_progress

        yield {"type": "thinking", "message": "Thinking..."}
        emit_tool_progress("Running dummy...")
        yield {
            "type": "tool_end",
            "tool": "dummy",
            "args": {},
            "result": "R",
            "duration": 0,
        }
        yield {
            "type": "done",
            "answer": "FINAL",
            "toolCalls": [],
            "iterations": 1,
            "totalTime": 1,
            "tokenUsage": None,
            "tokensPerSecond": 0.0,
        }


def test_api_agent_stream_sse_saves_history(monkeypatch) -> None:
    from dexter_flask.app import create_app
    from dexter_flask.routes import agent_api

    hist = FakeHistory(user_queries=[], saved_answers=[])

    def fake_get_chat_history(session_key: str, model: str) -> FakeHistory:
        return hist

    monkeypatch.setattr(agent_api, "get_chat_history", fake_get_chat_history)
    monkeypatch.setattr(
        agent_api.Agent,
        "create",
        classmethod(lambda cls, cfg: FakeAgent()),
    )

    app = create_app()
    c = app.test_client()
    payload = {
        "sessionKey": "s1",
        "query": "hello",
        "model": "gpt-5.4",
        "modelProvider": "openai",
        "maxIterations": 2,
        "isolatedSession": False,
    }
    r = c.post("/api/agent/stream", json=payload)
    assert r.status_code == 200
    assert "text/event-stream" in (r.content_type or "")

    body = r.data.decode("utf-8")
    assert "data:" in body
    assert '"type": "tool_progress"' in body
    assert '"type": "done"' in body
    assert "FINAL" in body

    # Route saves the final answer once the generator emits the `done` event.
    assert hist.user_queries == ["hello"]
    assert hist.saved_answers == ["FINAL"]


def test_api_agent_stream_isolated_does_not_save_history(monkeypatch) -> None:
    from dexter_flask.app import create_app
    from dexter_flask.routes import agent_api

    def boom(*_: object, **__: object) -> None:
        raise AssertionError(
            "get_chat_history should not be called for isolated sessions"
        )

    monkeypatch.setattr(agent_api, "get_chat_history", boom)
    monkeypatch.setattr(
        agent_api.Agent,
        "create",
        classmethod(lambda cls, cfg: FakeAgent()),
    )

    app = create_app()
    c = app.test_client()
    payload = {
        "sessionKey": "s1",
        "query": "hello",
        "model": "gpt-5.4",
        "modelProvider": "openai",
        "isolatedSession": True,
    }
    r = c.post("/api/agent/stream", json=payload)
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert '"type": "done"' in body
