"""Token estimation — mirror src/utils/tokens.ts."""
from __future__ import annotations

CONTEXT_THRESHOLD = 100_000
KEEP_TOOL_USES = 5


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)  # ~4 chars per token conservative
