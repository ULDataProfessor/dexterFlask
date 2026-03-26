"""Agent iteration loop — mirror src/agent/agent.ts."""

from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any

from langchain_core.messages import AIMessage

from dexter_flask.agent.chat_history import InMemoryChatHistory
from dexter_flask.agent.history_context import build_history_context
from dexter_flask.agent.prompts import (
    build_iteration_prompt,
    build_system_prompt,
    load_soul_document,
)
from dexter_flask.agent.run_context import RunContext, create_run_context
from dexter_flask.agent.token_counter import TokenCounter
from dexter_flask.agent.tool_executor import AgentToolExecutor
from dexter_flask.agent.tokens_util import (
    CONTEXT_THRESHOLD,
    KEEP_TOOL_USES,
    estimate_tokens,
)
from dexter_flask.agent.types import AgentConfig
from dexter_flask.llm.client import DEFAULT_MODEL, call_llm
from dexter_flask.llm.errors_util import (
    format_user_facing_error,
    is_context_overflow_error,
)
from dexter_flask.memory.flush_simple import maybe_memory_flush
from dexter_flask.providers import resolve_provider
from dexter_flask.tools.registry import get_tools


def _has_tool_calls(response: AIMessage | str) -> bool:
    if isinstance(response, str):
        return False
    return bool(response.tool_calls)


def _text_content(response: AIMessage | str) -> str:
    if isinstance(response, str):
        return response
    c = response.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(c)


class Agent:
    DEFAULT_MAX_ITER = 10

    def __init__(
        self,
        config: AgentConfig,
        tools: list,
        system_prompt: str,
        *,
        memory_files_loaded: list[str] | None = None,
        memory_token_count: int = 0,
    ) -> None:
        self.model = config.model or DEFAULT_MODEL
        self.max_iterations = config.max_iterations or self.DEFAULT_MAX_ITER
        self.tools = tools
        self._tool_map = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self._request_approval = config.request_tool_approval
        self._session_approved = config.session_approved_tools or set()
        self.memory_enabled = config.memory_enabled
        self._cancel_requested = config.cancel_requested
        self._memory_files_loaded = memory_files_loaded or []
        self._memory_token_count = memory_token_count

    @classmethod
    def create(cls, config: AgentConfig | None = None) -> "Agent":
        cfg = config or AgentConfig()
        model = cfg.model or DEFAULT_MODEL
        tools = get_tools(model)
        soul = load_soul_document()
        memory_files: list[str] = []
        memory_context: str | None = None
        memory_files_loaded: list[str] = []
        memory_token_count = 0
        if cfg.memory_enabled is not False:
            try:
                from dexter_flask.memory.manager import MemoryManager

                mm = MemoryManager.get()
                memory_files = mm.list_files()
                ctx = mm.load_session_context()
                memory_context = ctx.get("text") or None
                memory_files_loaded = ctx.get("filesLoaded") or []
                memory_token_count = int(ctx.get("tokenCount") or 0)
            except Exception:
                pass
        sp = build_system_prompt(
            model,
            soul,
            channel=cfg.channel,
            group_context=cfg.group_context,
            memory_files=memory_files,
            memory_context=memory_context,
        )
        return cls(
            cfg,
            tools,
            sp,
            memory_files_loaded=memory_files_loaded,
            memory_token_count=memory_token_count,
        )

    def _initial_prompt(self, query: str, history: InMemoryChatHistory | None) -> str:
        if not history or not history.has_messages():
            return query
        turns = history.get_recent_turns()
        if not turns:
            return query
        return build_history_context(entries=turns, current_message=query)

    def run(
        self,
        query: str,
        history: InMemoryChatHistory | None = None,
    ) -> Any:
        """Yield event dicts (thinking, tool_*, done, context_cleared, memory_recalled, memory_flush)."""
        t0 = int(time.time() * 1000)

        def is_cancelled() -> bool:
            return bool(
                self._cancel_requested
                and callable(self._cancel_requested)
                and self._cancel_requested()
            )

        if not self.tools:
            yield {
                "type": "done",
                "answer": "No tools available. Please check your API key configuration.",
                "toolCalls": [],
                "iterations": 0,
                "totalTime": 0,
            }
            return

        ctx = create_run_context(query)
        if self.memory_enabled:
            yield {
                "type": "memory_recalled",
                "filesLoaded": self._memory_files_loaded,
                "tokenCount": self._memory_token_count,
            }
        if is_cancelled():
            total = int(time.time() * 1000) - ctx.start_time
            yield {
                "type": "done",
                "answer": "Cancelled",
                "toolCalls": [
                    {"tool": r.tool, "args": r.args, "result": r.result}
                    for r in ctx.scratchpad.get_tool_call_records()
                ],
                "iterations": ctx.iteration,
                "totalTime": total,
                "tokenUsage": ctx.token_counter.get_usage(),
                "tokensPerSecond": ctx.token_counter.get_tokens_per_second(total),
            }
            return
        executor = AgentToolExecutor(
            self._tool_map, self._request_approval, self._session_approved
        )
        current_prompt = self._initial_prompt(query, history)
        memory_flushed = False
        overflow_retries = 0
        max_overflow_retries = 2

        while ctx.iteration < self.max_iterations:
            ctx.iteration += 1
            if is_cancelled():
                total = int(time.time() * 1000) - ctx.start_time
                yield {
                    "type": "done",
                    "answer": "Cancelled",
                    "toolCalls": [
                        {"tool": r.tool, "args": r.args, "result": r.result}
                        for r in ctx.scratchpad.get_tool_call_records()
                    ],
                    "iterations": ctx.iteration,
                    "totalTime": total,
                    "tokenUsage": ctx.token_counter.get_usage(),
                    "tokensPerSecond": ctx.token_counter.get_tokens_per_second(total),
                }
                return
            while True:
                try:
                    resp, usage = call_llm(
                        current_prompt,
                        model=self.model,
                        system_prompt=self.system_prompt,
                        tools=self.tools,
                    )
                    ctx.token_counter.add(usage)
                    overflow_retries = 0
                    break
                except Exception as e:
                    msg = str(e)
                    if (
                        is_context_overflow_error(msg)
                        and overflow_retries < max_overflow_retries
                    ):
                        overflow_retries += 1
                        cleared = ctx.scratchpad.clear_oldest_tool_results(3)
                        if cleared > 0:
                            yield {
                                "type": "context_cleared",
                                "clearedCount": cleared,
                                "keptCount": 3,
                            }
                            current_prompt = build_iteration_prompt(
                                query,
                                ctx.scratchpad.get_tool_results(),
                                ctx.scratchpad.format_tool_usage_for_prompt(),
                            )
                            continue
                    provider = resolve_provider(self.model).display_name
                    total = int(time.time() * 1000) - ctx.start_time
                    yield {
                        "type": "done",
                        "answer": f"Error: {format_user_facing_error(msg, provider)}",
                        "toolCalls": [
                            asdict(r) for r in ctx.scratchpad.get_tool_call_records()
                        ],
                        "iterations": ctx.iteration,
                        "totalTime": total,
                        "tokenUsage": ctx.token_counter.get_usage(),
                        "tokensPerSecond": ctx.token_counter.get_tokens_per_second(
                            total
                        ),
                    }
                    return

            text = _text_content(resp)
            if text.strip() and isinstance(resp, AIMessage) and _has_tool_calls(resp):
                ctx.scratchpad.add_thinking(text.strip())
                yield {"type": "thinking", "message": text.strip()}

            if isinstance(resp, str) or not _has_tool_calls(resp):
                total = int(time.time() * 1000) - ctx.start_time
                yield {
                    "type": "done",
                    "answer": text,
                    "toolCalls": [
                        {"tool": r.tool, "args": r.args, "result": r.result}
                        for r in ctx.scratchpad.get_tool_call_records()
                    ],
                    "iterations": ctx.iteration,
                    "totalTime": total,
                    "tokenUsage": ctx.token_counter.get_usage(),
                    "tokensPerSecond": ctx.token_counter.get_tokens_per_second(total),
                }
                return

            assert isinstance(resp, AIMessage)
            for ev in executor.execute_all(resp, ctx):
                yield ev
                if is_cancelled():
                    total = int(time.time() * 1000) - ctx.start_time
                    yield {
                        "type": "done",
                        "answer": "Cancelled",
                        "toolCalls": [
                            {"tool": r.tool, "args": r.args, "result": r.result}
                            for r in ctx.scratchpad.get_tool_call_records()
                        ],
                        "iterations": ctx.iteration,
                        "totalTime": total,
                        "tokenUsage": ctx.token_counter.get_usage(),
                        "tokensPerSecond": ctx.token_counter.get_tokens_per_second(
                            total
                        ),
                    }
                    return
                if ev.get("type") == "tool_denied":
                    total = int(time.time() * 1000) - ctx.start_time
                    yield {
                        "type": "done",
                        "answer": "",
                        "toolCalls": [
                            {"tool": r.tool, "args": r.args, "result": r.result}
                            for r in ctx.scratchpad.get_tool_call_records()
                        ],
                        "iterations": ctx.iteration,
                        "totalTime": total,
                        "tokenUsage": ctx.token_counter.get_usage(),
                        "tokensPerSecond": ctx.token_counter.get_tokens_per_second(
                            total
                        ),
                    }
                    return

            full_results = ctx.scratchpad.get_tool_results()
            est_ctx = estimate_tokens(self.system_prompt + query + full_results)
            if est_ctx > CONTEXT_THRESHOLD and self.memory_enabled:
                for ev in maybe_memory_flush(
                    model=self.model,
                    system_prompt=self.system_prompt,
                    query=query,
                    tool_results=full_results,
                    already_flushed=memory_flushed,
                ):
                    yield ev
                memory_flushed = True
            cleared = ctx.scratchpad.clear_oldest_tool_results(KEEP_TOOL_USES)
            if cleared > 0:
                memory_flushed = False
                yield {
                    "type": "context_cleared",
                    "clearedCount": cleared,
                    "keptCount": KEEP_TOOL_USES,
                }

            current_prompt = build_iteration_prompt(
                query,
                ctx.scratchpad.get_tool_results(),
                ctx.scratchpad.format_tool_usage_for_prompt(),
            )

        total = int(time.time() * 1000) - ctx.start_time
        yield {
            "type": "done",
            "answer": (
                f"Reached maximum iterations ({self.max_iterations}). "
                "I was unable to complete the research in the allotted steps."
            ),
            "toolCalls": [
                {"tool": r.tool, "args": r.args, "result": r.result}
                for r in ctx.scratchpad.get_tool_call_records()
            ],
            "iterations": ctx.iteration,
            "totalTime": total,
            "tokenUsage": ctx.token_counter.get_usage(),
            "tokensPerSecond": ctx.token_counter.get_tokens_per_second(total),
        }
