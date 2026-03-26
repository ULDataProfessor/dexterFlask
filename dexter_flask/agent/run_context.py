"""Run context — mirror src/agent/run-context.ts."""
from __future__ import annotations

import time
from dataclasses import dataclass

from dexter_flask.agent.scratchpad import Scratchpad
from dexter_flask.agent.token_counter import TokenCounter


@dataclass
class RunContext:
    query: str
    scratchpad: Scratchpad
    token_counter: TokenCounter
    start_time: int
    iteration: int = 0


def create_run_context(query: str) -> RunContext:
    return RunContext(
        query=query,
        scratchpad=Scratchpad(query),
        token_counter=TokenCounter(),
        start_time=int(time.time() * 1000),
    )
