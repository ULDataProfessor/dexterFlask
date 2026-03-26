"""Token usage aggregation — mirror src/agent/token-counter.ts."""
from __future__ import annotations

from dexter_flask.agent.types import TokenUsage


class TokenCounter:
    def __init__(self) -> None:
        self._input = 0
        self._output = 0
        self._total = 0

    def add(self, usage: dict | None) -> None:
        if not usage:
            return
        self._input += int(usage.get("inputTokens", 0))
        self._output += int(usage.get("outputTokens", 0))
        self._total += int(usage.get("totalTokens", 0))

    def get_usage(self) -> TokenUsage  | None:
        if self._total == 0 and self._input == 0 and self._output == 0:
            return None
        return TokenUsage(
            inputTokens=self._input,
            outputTokens=self._output,
            totalTokens=self._total or self._input + self._output,
        )

    def get_tokens_per_second(self, total_time_ms: int) -> float:
        u = self.get_usage()
        if not u or total_time_ms <= 0:
            return 0.0
        sec = total_time_ms / 1000.0
        return u["totalTokens"] / sec if sec > 0 else 0.0
