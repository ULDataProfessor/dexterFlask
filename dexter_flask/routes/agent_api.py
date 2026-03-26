"""Agent HTTP API — mirror gateway AgentRunRequest."""

from __future__ import annotations

from collections import deque
import json
import re
import threading
import uuid
import time
from typing import Any

from flask import Blueprint, Response, request, stream_with_context
from pydantic import BaseModel, ConfigDict, ValidationError

from dexter_flask.agent.loop import Agent
from dexter_flask.agent.types import AgentConfig
from dexter_flask.services.agent_runner import run_agent_for_message
from dexter_flask.services.sessions import get_chat_history
from dexter_flask.tools.context import set_tool_progress
from dexter_flask.gateway.heartbeat_prompt import HEARTBEAT_OK_TOKEN

agent_bp = Blueprint("agent", __name__)

_DEFAULT_MODEL = "gpt-5.4"

_approval_states: dict[str, "ApprovalState"] = {}


class ApprovalState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._decision: str | None = None
        self._cancelled = False

    def wait_for_decision(self, *, timeout_s: int = 300) -> str:
        with self._cond:
            start = time.time()
            while self._decision is None and not self._cancelled:
                remaining = timeout_s - (time.time() - start)
                if remaining <= 0:
                    break
                self._cond.wait(timeout=remaining)

            if self._cancelled:
                return "deny"
            if self._decision is None:
                # Fail-safe: if no decision arrives, deny to avoid unsafe tool execution.
                return "deny"
            d = self._decision
            self._decision = None
            return str(d)

    def set_decision(self, decision: str) -> None:
        with self._cond:
            self._decision = decision
            self._cond.notify_all()

    def cancel(self) -> None:
        with self._cond:
            self._cancelled = True
            self._cond.notify_all()

    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled


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
    runId: str | None = None


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
    run_id = parsed.runId or uuid.uuid4().hex
    session_key = str(parsed.sessionKey)
    model = str(parsed.model)
    query = str(parsed.query)
    max_iter = int(parsed.maxIterations)
    approval_state = _approval_states.setdefault(run_id, ApprovalState())

    history = None
    if not isolated:
        history = get_chat_history(session_key, model)
        history.save_user_query(query)

    def request_tool_approval(info: dict[str, Any]) -> str:
        # The tool executor yields a `tool_approval` request event, then blocks on this callback.
        return approval_state.wait_for_decision()

    cfg = AgentConfig(
        model=model,
        model_provider=parsed.modelProvider,
        max_iterations=max_iter,
        channel=parsed.channel,
        group_context=parsed.groupContext,
        memory_enabled=not isolated,
        request_tool_approval=request_tool_approval,
        cancel_requested=lambda: approval_state.is_cancelled(),
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
                if (
                    parsed.isHeartbeat
                    and final.strip().upper().find(HEARTBEAT_OK_TOKEN) >= 0
                ):
                    history.prune_last_turn()
            yield from _drain_progress()
        finally:
            set_tool_progress(None)
            approval_state.cancel()
            _approval_states.pop(run_id, None)

    return Response(stream_with_context(gen()), mimetype="text/event-stream")


@agent_bp.post("/api/agent/approval")
def api_agent_approval():
    class ApprovalBody(BaseModel):
        model_config = ConfigDict(extra="ignore")
        runId: str
        decision: str

    body = request.get_json(force=True, silent=True) or {}
    try:
        parsed = ApprovalBody.model_validate(body)
    except Exception:
        return {
            "error": "invalid_request",
            "details": "Invalid approval request body",
        }, 400

    run_id = parsed.runId
    decision = str(parsed.decision)
    st = _approval_states.get(run_id)
    if not st:
        return {"error": "invalid_run_id", "details": "Unknown or expired runId"}, 404

    if decision not in ("allow-once", "allow-session", "deny"):
        return {
            "error": "invalid_decision",
            "details": "Decision must be allow-once, allow-session, or deny",
        }, 400

    st.set_decision(decision)
    return {"ok": True}


@agent_bp.post("/api/agent/cancel")
def api_agent_cancel():
    class CancelBody(BaseModel):
        model_config = ConfigDict(extra="ignore")
        runId: str

    body = request.get_json(force=True, silent=True) or {}
    try:
        parsed = CancelBody.model_validate(body)
    except Exception:
        return {
            "error": "invalid_request",
            "details": "Invalid cancel request body",
        }, 400

    run_id = parsed.runId
    st = _approval_states.get(run_id)
    if not st:
        return {"error": "invalid_run_id", "details": "Unknown or expired runId"}, 404

    st.cancel()
    return {"ok": True}
