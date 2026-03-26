from dataclasses import dataclass
from typing import Any, Generator


def test_api_agent_run_returns_answer(monkeypatch) -> None:
    from dexter_flask.app import create_app
    from dexter_flask.routes import agent_api

    monkeypatch.setattr(agent_api, "run_agent_for_message", lambda body: "ANSWER")

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


def test_api_agent_run_prunes_heartbeat_turn(monkeypatch) -> None:
    from dexter_flask.app import create_app
    from dexter_flask.gateway.heartbeat_prompt import HEARTBEAT_OK_TOKEN
    import dexter_flask.services.agent_runner as agent_runner

    hist = FakeHistory(user_queries=[], saved_answers=[])

    def fake_get_chat_history(session_key: str, model: str) -> FakeHistory:
        return hist

    class FakeHeartbeatAgent:
        def run(
            self, query: str, history: Any
        ) -> Generator[dict[str, Any], None, None]:
            yield {
                "type": "done",
                "answer": f"Some text {HEARTBEAT_OK_TOKEN}",
                "toolCalls": [],
                "iterations": 1,
                "totalTime": 1,
                "tokenUsage": None,
                "tokensPerSecond": 0.0,
            }

    monkeypatch.setattr(agent_runner, "get_chat_history", fake_get_chat_history)
    monkeypatch.setattr(
        agent_runner.Agent,
        "create",
        classmethod(lambda cls, cfg: FakeHeartbeatAgent()),
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
        "isHeartbeat": True,
    }
    r = c.post("/api/agent/run", json=payload)
    assert r.status_code == 200
    assert r.get_json() == {"answer": f"Some text {HEARTBEAT_OK_TOKEN}"}
    assert hist.pruned_count == 1


@dataclass
class FakeHistory:
    user_queries: list[str]
    saved_answers: list[str]
    pruned_count: int = 0

    def save_user_query(self, query: str) -> None:
        self.user_queries.append(query)

    def save_answer(self, answer: str) -> None:
        self.saved_answers.append(answer)

    def prune_last_turn(self) -> None:
        self.pruned_count += 1


class FakeAgent:
    def run(self, query: str, history: Any) -> Generator[dict[str, Any], None, None]:
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


def test_api_agent_stream_prunes_heartbeat_turn(monkeypatch) -> None:
    from dexter_flask.app import create_app
    from dexter_flask.routes import agent_api
    from dexter_flask.gateway.heartbeat_prompt import HEARTBEAT_OK_TOKEN

    hist = FakeHistory(user_queries=[], saved_answers=[])

    def fake_get_chat_history(session_key: str, model: str) -> FakeHistory:
        return hist

    class FakeHeartbeatAgent:
        def run(
            self, query: str, history: Any
        ) -> Generator[dict[str, Any], None, None]:
            yield {
                "type": "done",
                "answer": f"Some text {HEARTBEAT_OK_TOKEN}",
                "toolCalls": [],
                "iterations": 1,
                "totalTime": 1,
                "tokenUsage": None,
                "tokensPerSecond": 0.0,
            }

    monkeypatch.setattr(agent_api, "get_chat_history", fake_get_chat_history)
    monkeypatch.setattr(
        agent_api.Agent,
        "create",
        classmethod(lambda cls, cfg: FakeHeartbeatAgent()),
    )

    app = create_app()
    c = app.test_client()
    payload = {
        "sessionKey": "s1",
        "query": "hello",
        "model": "gpt-5.4",
        "modelProvider": "openai",
        "isolatedSession": False,
        "isHeartbeat": True,
    }
    r = c.post("/api/agent/stream", json=payload)
    assert r.status_code == 200
    _ = r.data.decode("utf-8")
    assert hist.user_queries == ["hello"]
    assert hist.saved_answers == [f"Some text {HEARTBEAT_OK_TOKEN}"]
    assert hist.pruned_count == 1


def test_api_agent_stream_forwards_memory_recalled(monkeypatch) -> None:
    from dexter_flask.app import create_app
    from dexter_flask.routes import agent_api

    hist = FakeHistory(user_queries=[], saved_answers=[])

    def fake_get_chat_history(session_key: str, model: str) -> FakeHistory:
        return hist

    class FakeMemoryRecalledAgent:
        def run(
            self, query: str, history: Any
        ) -> Generator[dict[str, Any], None, None]:
            yield {
                "type": "memory_recalled",
                "filesLoaded": ["daily"],
                "tokenCount": 42,
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

    monkeypatch.setattr(agent_api, "get_chat_history", fake_get_chat_history)
    monkeypatch.setattr(
        agent_api.Agent,
        "create",
        classmethod(lambda cls, cfg: FakeMemoryRecalledAgent()),
    )

    app = create_app()
    c = app.test_client()
    payload = {
        "sessionKey": "s1",
        "query": "hello",
        "model": "gpt-5.4",
        "modelProvider": "openai",
        "isolatedSession": False,
    }
    r = c.post("/api/agent/stream", json=payload)
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert '"type": "memory_recalled"' in body
    assert '"tokenCount": 42' in body
    assert hist.saved_answers == ["FINAL"]
