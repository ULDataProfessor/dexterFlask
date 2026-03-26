from __future__ import annotations

from typing import Any, Generator


def test_agent_run_no_tools_yields_done() -> None:
    from dexter_flask.agent.loop import Agent
    from dexter_flask.agent.types import AgentConfig

    agent = Agent(
        config=AgentConfig(model="gpt-5.4"),
        tools=[],
        system_prompt="SYS",
    )
    events = list(agent.run("query", None))
    assert events
    assert events[-1]["type"] == "done"
    assert "No tools available" in events[-1]["answer"]


def test_agent_run_tool_path_emits_thinking_and_done(monkeypatch) -> None:
    from langchain_core.messages import AIMessage

    from dexter_flask.agent.loop import Agent, AgentToolExecutor
    from dexter_flask.agent.types import AgentConfig
    import dexter_flask.agent.loop as agent_loop

    ai_with_tools = AIMessage(
        content="Thinking...",
        tool_calls=[{"name": "dummy", "args": {"query": "query"}, "id": "1"}],
    )

    call_results: list[Any] = [ai_with_tools, "FINAL"]

    def fake_call_llm(*_: Any, **__: Any) -> tuple[Any, dict[str, int] | None]:
        return call_results.pop(0), None

    def fake_execute_all(
        self: Any, response: Any, ctx: Any
    ) -> Generator[dict[str, Any], None, None]:
        # Minimal tool output so the loop can proceed to the final LLM call.
        yield {
            "type": "tool_end",
            "tool": "dummy",
            "args": {},
            "result": "R",
            "duration": 0,
        }

    monkeypatch.setattr(agent_loop, "call_llm", fake_call_llm)
    monkeypatch.setattr(AgentToolExecutor, "execute_all", fake_execute_all)

    agent = Agent(
        config=AgentConfig(model="gpt-5.4", max_iterations=2),
        tools=[type("T", (), {"name": "dummy"})()],
        system_prompt="SYS",
    )

    events = list(agent.run("query", None))
    assert any(e["type"] == "thinking" for e in events)
    assert any(e["type"] == "tool_end" for e in events)
    done = [e for e in events if e["type"] == "done"][-1]
    assert done["answer"] == "FINAL"
