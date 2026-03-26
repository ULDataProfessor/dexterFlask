"""History context formatting — mirror src/utils/history-context.ts."""

from __future__ import annotations

HISTORY_CONTEXT_MARKER = "[Chat history for context]"
CURRENT_MESSAGE_MARKER = "[Current message - respond to this]"
DEFAULT_HISTORY_LIMIT = 10
FULL_ANSWER_TURNS = 3


def build_history_context(
    *,
    entries: list[dict],  # role user|assistant, content
    current_message: str,
    line_break: str = "\n",
) -> str:
    if not entries:
        return current_message
    history_text = (line_break * 2).join(
        f"{'User' if e['role'] == 'user' else 'Assistant'}: {e['content']}"
        for e in entries
    )
    return line_break.join(
        [
            HISTORY_CONTEXT_MARKER,
            history_text,
            "",
            CURRENT_MESSAGE_MARKER,
            current_message,
        ]
    )
