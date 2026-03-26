"""Tool execution — mirror src/agent/tool-executor.ts."""
from __future__ import annotations

import inspect
import json
import time
from collections.abc import Callable, Generator
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from dexter_flask.agent.run_context import RunContext
from dexter_flask.agent.types import ApprovalDecision
from dexter_flask.tools.context import emit_tool_progress

TOOLS_REQUIRING_APPROVAL = frozenset({"write_file", "edit_file"})


class AgentToolExecutor:
    def __init__(
        self,
        tool_map: dict[str, BaseTool],
        request_tool_approval: Callable[..., Any] | None = None,
        session_approved_tools: set[str] | None = None,
    ) -> None:
        self._tool_map = tool_map
        self._request_tool_approval = request_tool_approval
        self._session_approved = session_approved_tools or set()

    def execute_all(
        self, response: AIMessage, ctx: RunContext
    ) -> Generator[dict[str, Any], None, None]:
        for tc in response.tool_calls or []:
            if isinstance(tc, dict):
                name, args = tc.get("name") or "", tc.get("args") or {}
            else:
                name, args = getattr(tc, "name", "") or "", getattr(tc, "args", None) or {}
            if not isinstance(args, dict):
                args = {}
            yield from self._execute_single(name, args, ctx)

    def _extract_query(self, args: dict[str, Any]) -> str | None:
        for key in ("query", "search", "question", "q", "text", "input"):
            v = args.get(key)
            if isinstance(v, str):
                return v
        return None

    def _resolve_approval(self, tool_name: str, tool_args: dict[str, Any]) -> ApprovalDecision:
        if tool_name not in TOOLS_REQUIRING_APPROVAL or tool_name in self._session_approved:
            return "allow-once"
        if self._request_tool_approval is None:
            return "allow-once"
        fn = self._request_tool_approval
        if inspect.iscoroutinefunction(fn):
            return "deny"
        out = fn({"tool": tool_name, "args": tool_args})
        return out if out in ("allow-once", "allow-session", "deny") else "deny"

    def _execute_single(
        self, tool_name: str, tool_args: dict[str, Any], ctx: RunContext
    ) -> Generator[dict[str, Any], None, None]:
        tool_query = self._extract_query(tool_args)
        if tool_name in TOOLS_REQUIRING_APPROVAL:
            # HTTP-driven approval flow:
            # - emit a `tool_approval` *request* event first (no `approved` field)
            # - then block in `request_tool_approval` until the operator decision arrives
            # - finally emit the `tool_approval` decision event (with `approved`)
            if self._request_tool_approval is not None and tool_name not in self._session_approved:
                yield {"type": "tool_approval", "tool": tool_name, "args": tool_args}

            decision = self._resolve_approval(tool_name, tool_args)
            yield {"type": "tool_approval", "tool": tool_name, "args": tool_args, "approved": decision}
            if decision == "deny":
                yield {"type": "tool_denied", "tool": tool_name, "args": tool_args}
                return
            if decision == "allow-session":
                self._session_approved.update(TOOLS_REQUIRING_APPROVAL)

        allowed, warning = ctx.scratchpad.can_call_tool(tool_name, tool_query)
        if warning:
            yield {"type": "tool_limit", "tool": tool_name, "warning": warning, "blocked": False}

        yield {"type": "tool_start", "tool": tool_name, "args": tool_args}
        t0 = time.time() * 1000
        tool = self._tool_map.get(tool_name)
        if not tool:
            err = f"Tool '{tool_name}' not found"
            yield {"type": "tool_error", "tool": tool_name, "error": err}
            ctx.scratchpad.record_tool_call(tool_name, tool_query)
            ctx.scratchpad.add_tool_result(tool_name, tool_args, f"Error: {err}")
            return

        try:
            emit_tool_progress(f"Running {tool_name}...")
            raw = tool.invoke(tool_args)
            result = raw if isinstance(raw, str) else json.dumps(raw, default=str)
            dur = int(time.time() * 1000 - t0)
            yield {"type": "tool_end", "tool": tool_name, "args": tool_args, "result": result, "duration": dur}
            ctx.scratchpad.record_tool_call(tool_name, tool_query)
            ctx.scratchpad.add_tool_result(tool_name, tool_args, result)
        except Exception as e:
            msg = str(e)
            yield {"type": "tool_error", "tool": tool_name, "error": msg}
            ctx.scratchpad.record_tool_call(tool_name, tool_query)
            ctx.scratchpad.add_tool_result(tool_name, tool_args, f"Error: {msg}")
