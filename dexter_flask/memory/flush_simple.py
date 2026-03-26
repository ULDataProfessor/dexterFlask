"""Pre-compaction memory flush — mirror src/memory/flush.ts."""

from __future__ import annotations

from typing import Any

from dexter_flask.agent.tokens_util import CONTEXT_THRESHOLD
from dexter_flask.llm.client import call_llm
from langchain_core.messages import AIMessage

MEMORY_FLUSH_TOKEN = "NO_MEMORY_TO_FLUSH"

PROMPT_SUFFIX = f"""
Session context is close to compaction. Summarize durable facts worth remembering.
Output concise markdown bullets. If nothing to store, reply exactly: {MEMORY_FLUSH_TOKEN}.
Do not include temporary market data.
""".strip()


def should_memory_flush(estimated_tokens: int, already_flushed: bool) -> bool:
    if already_flushed:
        return False
    return estimated_tokens >= CONTEXT_THRESHOLD


def _text(resp: AIMessage | str) -> str:
    if isinstance(resp, str):
        return resp
    c = resp.content
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c)
    return str(c)


def maybe_memory_flush(
    *,
    model: str,
    system_prompt: str,
    query: str,
    tool_results: str,
    already_flushed: bool,
):
    est = max(1, len(system_prompt + query + tool_results) // 4)
    if not should_memory_flush(est, already_flushed):
        return
    yield {"type": "memory_flush", "phase": "start"}
    prompt = f"Original user query:\n{query}\n\nRelevant context:\n{tool_results}\n\n{PROMPT_SUFFIX}"
    try:
        resp, _ = call_llm(prompt, model=model, system_prompt=system_prompt)
        text = _text(resp).strip()
    except Exception:
        text = MEMORY_FLUSH_TOKEN
    written: list[str] = []
    if text and text != MEMORY_FLUSH_TOKEN:
        try:
            from datetime import datetime

            from dexter_flask.memory.manager import MemoryManager

            MemoryManager.get().append_daily_memory(
                f"## Pre-compaction memory flush\n{text}"
            )
            written = [datetime.now().strftime("%Y-%m-%d") + ".md"]
        except Exception:
            pass
    yield {"type": "memory_flush", "phase": "end", "filesWritten": written}
