from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Generator


def test_tool_executor_deny_approval_yields_tool_denied(monkeypatch) -> None:
    from dexter_flask.agent.run_context import create_run_context
    from dexter_flask.agent.tool_executor import AgentToolExecutor

    ctx = create_run_context("q")

    executor = AgentToolExecutor(
        tool_map={},
        request_tool_approval=lambda info: "deny",
        session_approved_tools=set(),
    )

    resp = SimpleNamespace(
        tool_calls=[
            {
                "name": "write_file",
                "args": {"query": "hello"},
            }
        ]
    )

    events = list(executor.execute_all(resp, ctx))
    assert any(e.get("type") == "tool_approval" and e.get("approved") == "deny" for e in events)
    assert any(e.get("type") == "tool_denied" for e in events)
    assert not any(e.get("type") == "tool_start" for e in events)


def test_tool_executor_tool_limit_approaching(monkeypatch) -> None:
    from dexter_flask.agent.run_context import create_run_context
    from dexter_flask.agent.tool_executor import AgentToolExecutor

    ctx = create_run_context("q")
    # Default limit config allows 3 calls per tool; on the 3rd attempt, the executor should warn.
    ctx.scratchpad.record_tool_call("dummy")
    ctx.scratchpad.record_tool_call("dummy")

    executor = AgentToolExecutor(tool_map={})
    resp = SimpleNamespace(tool_calls=[{"name": "dummy", "args": {"query": "hello"}}])

    events = list(executor.execute_all(resp, ctx))
    limit_events = [e for e in events if e.get("type") == "tool_limit"]
    assert limit_events, "expected tool_limit event"
    assert "approaching" in (limit_events[0].get("warning") or "").lower()


def test_tool_executor_tool_limit_similarity(monkeypatch) -> None:
    from dexter_flask.agent.run_context import create_run_context
    from dexter_flask.agent.tool_executor import AgentToolExecutor

    ctx = create_run_context("q")
    ctx.scratchpad.record_tool_call("dummy", "How to buy apple stock")

    executor = AgentToolExecutor(tool_map={})
    resp = SimpleNamespace(
        tool_calls=[
            {"name": "dummy", "args": {"query": "How to buy apple stock now"}},
        ]
    )

    events = list(executor.execute_all(resp, ctx))
    limit_events = [e for e in events if e.get("type") == "tool_limit"]
    assert limit_events, "expected tool_limit event"
    assert "very similar" in (limit_events[0].get("warning") or "")


def test_tool_executor_missing_tool_yields_tool_error_and_records_result() -> None:
    from dexter_flask.agent.run_context import create_run_context
    from dexter_flask.agent.tool_executor import AgentToolExecutor

    ctx = create_run_context("q")
    executor = AgentToolExecutor(tool_map={})
    resp = SimpleNamespace(
        tool_calls=[
            {"name": "missing_tool", "args": {"query": "x"}},
        ]
    )

    events = list(executor.execute_all(resp, ctx))
    assert any(e.get("type") == "tool_error" and e.get("tool") == "missing_tool" for e in events)

    recs = ctx.scratchpad.get_tool_call_records()
    assert len(recs) == 1
    assert recs[0].tool == "missing_tool"

