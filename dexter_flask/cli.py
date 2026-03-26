from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from dexter_flask.agent.loop import Agent
from dexter_flask.agent.types import AgentConfig


def _print_event(ev: dict[str, Any]) -> None:
    t = ev.get("type")
    if t == "tool_end":
        # Keep tool results compact for terminal usage.
        msg = {"type": t, "tool": ev.get("tool"), "duration": ev.get("duration")}
        print(json.dumps(msg, ensure_ascii=False))
        return
    if t == "done":
        print(ev.get("answer") or "")
        return

    # Default: emit minimal event.
    msg = {
        k: v
        for k, v in ev.items()
        if k in ("type", "message", "tool", "warning", "error", "toolCalls")
    }
    print(json.dumps(msg, ensure_ascii=False))


def _run_agent(
    query: str,
    *,
    model: str,
    model_provider: str,
    max_iterations: int,
    memory_enabled: bool,
    stream: bool,
) -> None:
    cfg = AgentConfig(
        model=model,
        model_provider=model_provider,
        max_iterations=max_iterations,
        memory_enabled=memory_enabled,
    )
    agent = Agent.create(cfg)
    final_answer = ""

    for ev in agent.run(query, None):
        if stream:
            _print_event(ev)  # events end with `done` which prints answer
        else:
            if ev.get("type") == "done":
                final_answer = str(ev.get("answer") or "")
    if not stream:
        print(final_answer)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dexter-flask", description="Dexter Python CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    run_p = sub.add_parser("run", help="Run agent to completion (non-streaming)")
    run_p.add_argument("--query", "-q", required=True, help="User question")
    run_p.add_argument("--model", default=os.environ.get("DEXTER_MODEL", "gpt-5.4"))
    run_p.add_argument("--provider", default=os.environ.get("DEXTER_PROVIDER", "openai"))
    run_p.add_argument("--max-iterations", type=int, default=10)
    run_p.add_argument(
        "--isolated",
        action="store_true",
        help="Disable memory integration for the run",
    )

    stream_p = sub.add_parser("stream", help="Run agent with event streaming")
    stream_p.add_argument("--query", "-q", required=True, help="User question")
    stream_p.add_argument("--model", default=os.environ.get("DEXTER_MODEL", "gpt-5.4"))
    stream_p.add_argument("--provider", default=os.environ.get("DEXTER_PROVIDER", "openai"))
    stream_p.add_argument("--max-iterations", type=int, default=10)
    stream_p.add_argument(
        "--isolated",
        action="store_true",
        help="Disable memory integration for the run",
    )

    # Simple eval runner (optional judge).
    eval_p = sub.add_parser("eval", help="Run a small evaluation over finance_agent.csv")
    eval_p.add_argument("--sample", type=int, default=5, help="Number of questions to run")
    eval_p.add_argument("--model", default=os.environ.get("DEXTER_MODEL", "gpt-5.4"))
    eval_p.add_argument("--provider", default=os.environ.get("DEXTER_PROVIDER", "openai"))
    eval_p.add_argument("--max-iterations", type=int, default=10)
    eval_p.add_argument("--no-judge", action="store_true", help="Skip LLM-as-judge scoring")

    args = p.parse_args(argv or sys.argv[1:])

    if args.cmd in ("run", "stream"):
        _run_agent(
            args.query,
            model=args.model,
            model_provider=args.provider,
            max_iterations=args.max_iterations,
            memory_enabled=not bool(args.isolated),
            stream=args.cmd == "stream",
        )
        return 0

    if args.cmd == "eval":
        from dexter_flask.evals.run import run_eval

        run_eval(
            sample_size=args.sample,
            model=args.model,
            model_provider=args.provider,
            max_iterations=args.max_iterations,
            judge=not args.no_judge,
        )
        return 0

    raise AssertionError(f"Unhandled cmd: {args.cmd}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

