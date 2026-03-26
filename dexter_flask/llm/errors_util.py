"""Error classification — mirror src/utils/errors.ts (subset)."""
from __future__ import annotations

import re

CONTEXT_PATTERNS = [
    re.compile(r"context length exceeded", re.I),
    re.compile(r"maximum context length", re.I),
    re.compile(r"prompt is too long", re.I),
    re.compile(r"context overflow", re.I),
    re.compile(r"maximum context", re.I),
    re.compile(r"token limit", re.I),
]


def is_context_overflow_error(message: str) -> bool:
    if not message:
        return False
    lower = message.lower()
    if "tpm" in lower or "tokens per minute" in lower:
        return False
    return any(p.search(message) for p in CONTEXT_PATTERNS)


def is_non_retryable_error(message: str) -> bool:
    return is_context_overflow_error(message)


def format_user_facing_error(raw: str, provider: str | None = None) -> str:
    label = f"{provider} " if provider else ""
    if is_context_overflow_error(raw):
        return (
            "Context overflow: the conversation is too large for the model. "
            "Try starting a new conversation or use a model with a larger context window."
        )
    if not raw.strip():
        return "LLM request failed with an unknown error."
    if len(raw) > 300:
        return raw[:300] + "..."
    return f"{label}{raw}".strip()
