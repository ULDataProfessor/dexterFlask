"""Agent HTTP API — mirror gateway AgentRunRequest."""
from __future__ import annotations

import json

from flask import Blueprint, Response, request, stream_with_context

from dexter_flask.agent.loop import Agent
from dexter_flask.agent.types import AgentConfig
from dexter_flask.services.agent_runner import run_agent_for_message
from dexter_flask.services.sessions import get_chat_history

agent_bp = Blueprint("agent", __name__)


def _payload():
    return request.get_json(force=True, silent=False) or {}


@agent_bp.post("/api/agent/run")
def api_agent_run():
    body = _payload()
    answer = run_agent_for_message(body)
    return {"answer": answer}


@agent_bp.post("/api/agent/stream")
def api_agent_stream():
    body = _payload()
    isolated = bool(body.get("isolatedSession"))
    session_key = str(body.get("sessionKey") or "default")
    model = str(body.get("model") or "gpt-5.4")
    query = str(body.get("query") or "")
    max_iter = int(body.get("maxIterations") or 10)

    history = None
    if not isolated:
        history = get_chat_history(session_key, model)
        history.save_user_query(query)

    cfg = AgentConfig(
        model=model,
        model_provider=body.get("modelProvider"),
        max_iterations=max_iter,
        channel=body.get("channel"),
        group_context=body.get("groupContext"),
        memory_enabled=not isolated,
    )
    agent = Agent.create(cfg)

    def gen():
        final = ""
        for ev in agent.run(query, history):
            yield f"data: {json.dumps(ev, default=str)}\n\n"
            if ev.get("type") == "done":
                final = str(ev.get("answer") or "")
        if history and final:
            history.save_answer(final)

    return Response(stream_with_context(gen()), mimetype="text/event-stream")
