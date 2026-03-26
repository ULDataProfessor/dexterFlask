"""Agent execution — mirror src/gateway/agent-runner.ts."""
from __future__ import annotations

from typing import Any, Callable

from dexter_flask.agent.loop import Agent
from dexter_flask.agent.types import AgentConfig
from dexter_flask.gateway.heartbeat_prompt import HEARTBEAT_OK_TOKEN
from dexter_flask.services.sessions import get_chat_history


def run_agent_for_message(
    req: dict[str, Any],
    *,
    on_event: Callable[[dict[str, Any]], Any] | None = None,
) -> str:
    isolated = bool(req.get("isolatedSession"))
    session_key = str(req.get("sessionKey") or "default")
    model = str(req.get("model") or "gpt-5.4")
    query = str(req.get("query") or "")
    max_iter = int(req.get("maxIterations") or 10)

    history = None
    if not isolated:
        history = get_chat_history(session_key, model)
        history.save_user_query(query)

    cfg = AgentConfig(
        model=model,
        model_provider=req.get("modelProvider"),
        max_iterations=max_iter,
        channel=req.get("channel"),
        group_context=req.get("groupContext"),
        memory_enabled=not isolated,
    )
    agent = Agent.create(cfg)
    final = ""
    for ev in agent.run(query, history):
        if on_event:
            on_event(ev)
        if ev.get("type") == "done":
            final = str(ev.get("answer") or "")

    if history and final:
        history.save_answer(final)
    if (
        history
        and req.get("isHeartbeat")
        and final.strip().upper().find(HEARTBEAT_OK_TOKEN) >= 0
    ):
        history.prune_last_turn()
    return final
