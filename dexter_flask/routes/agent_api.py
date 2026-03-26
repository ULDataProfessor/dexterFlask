"""Agent HTTP API — mirror gateway AgentRunRequest."""
from __future__ import annotations

from collections import deque
import json
import re
from typing import Any

from flask import Blueprint, Response, request, stream_with_context
from pydantic import BaseModel, ConfigDict, ValidationError

from dexter_flask.agent.loop import Agent
from dexter_flask.agent.types import AgentConfig
from dexter_flask.services.agent_runner import run_agent_for_message
from dexter_flask.services.sessions import get_chat_history
from dexter_flask.tools.context import set_tool_progress

agent_bp = Blueprint("agent", __name__)

_DEFAULT_MODEL = "gpt-5.4"


class AgentRunBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    sessionKey: str = "default"
    query: str = ""
    model: str = _DEFAULT_MODEL
    modelProvider: str | None = None
    maxIterations: int = 10
    isolatedSession: bool = False
    channel: str | None = None
    groupContext: dict[str, Any] | None = None
    isHeartbeat: bool = False


def _parse_body() -> tuple[AgentRunBody | None, tuple[Any, int] | None]:
    body = request.get_json(force=True, silent=True) or {}
    try:
        parsed = AgentRunBody.model_validate(body)
        return parsed, None
    except ValidationError as e:
        return None, ({"error": "invalid_request", "details": e.errors()}, 400)


@agent_bp.post("/api/agent/run")
def api_agent_run():
    parsed, err = _parse_body()
    if err is not None:
        payload, code = err
        return payload, code

    assert parsed is not None
    answer = run_agent_for_message(parsed.model_dump())
    return {"answer": answer}


@agent_bp.post("/api/agent/stream")
def api_agent_stream():
    parsed, err = _parse_body()
    if err is not None:
        payload, code = err
        return payload, code

    assert parsed is not None
    isolated = bool(parsed.isolatedSession)
    session_key = str(parsed.sessionKey)
    model = str(parsed.model)
    query = str(parsed.query)
    max_iter = int(parsed.maxIterations)

    history = None
    if not isolated:
        history = get_chat_history(session_key, model)
        history.save_user_query(query)

    cfg = AgentConfig(
        model=model,
        model_provider=parsed.modelProvider,
        max_iterations=max_iter,
        channel=parsed.channel,
        group_context=parsed.groupContext,
        memory_enabled=not isolated,
    )
    agent = Agent.create(cfg)

    def gen():
        tool_progress_queue: deque[str] = deque()

        def _cb(msg: str) -> None:
            tool_progress_queue.append(msg)

        def _drain_progress():
            while tool_progress_queue:
                msg = tool_progress_queue.popleft()
                tool = ""
                m = re.match(r"^Running (.+)\.\.\.$", msg)
                if m:
                    tool = m.group(1)
                ev = {"type": "tool_progress", "tool": tool, "message": msg}
                yield f"data: {json.dumps(ev, default=str)}\n\n"

        set_tool_progress(_cb)
        final = ""
        try:
            for ev in agent.run(query, history):
                yield f"data: {json.dumps(ev, default=str)}\n\n"
                if ev.get("type") == "done":
                    final = str(ev.get("answer") or "")
                yield from _drain_progress()
            if history and final:
                history.save_answer(final)
            yield from _drain_progress()
        finally:
            set_tool_progress(None)

    return Response(stream_with_context(gen()), mimetype="text/event-stream")
