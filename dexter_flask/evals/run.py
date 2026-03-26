from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from dexter_flask.agent.loop import Agent
from dexter_flask.agent.types import AgentConfig
from dexter_flask.llm.client import call_llm_structured


@dataclass(frozen=True)
class Example:
    question: str
    expected_answer: str


class JudgeOut(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    comment: str


def _dataset_path() -> Path:
    # Temporary location: keep the existing TS dataset until we decide to move it.
    return (
        Path(__file__).resolve().parents[2]
        / "src"
        / "evals"
        / "dataset"
        / "finance_agent.csv"
    )


def load_examples(csv_path: Path) -> list[Example]:
    out: list[Example] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            q = (row.get("Question") or "").strip()
            a = (row.get("Answer") or "").strip()
            if q and a:
                out.append(Example(question=q, expected_answer=a))
    return out


def judge_correctness(
    *,
    model: str,
    expected: str,
    actual: str,
    system_prompt: str,
) -> JudgeOut:
    prompt = (
        "You are evaluating the correctness of an AI assistant's answer "
        "to a financial question.\n\n"
        "Compare the actual answer to the expected answer. The actual "
        "answer is considered correct if it conveys the same key "
        "information as the expected answer.\n\n"
        "Expected Answer:\n"
        f"{expected}\n\n"
        "Actual Answer:\n"
        f"{actual}\n\n"
        "Evaluate and provide:\n"
        "- score: 1 if the answer is correct (contains the key information), "
        "0 if incorrect\n"
        "- comment: brief explanation of why the answer is correct or incorrect"
    )

    res = call_llm_structured(
        prompt,
        model=model,
        system_prompt=system_prompt,
        schema=JudgeOut,
    )
    assert isinstance(res, JudgeOut)
    return res


def run_eval(
    *,
    sample_size: int,
    model: str,
    model_provider: str,
    max_iterations: int,
    judge: bool,
) -> None:
    examples = load_examples(_dataset_path())
    if not examples:
        raise RuntimeError(f"No examples loaded from {_dataset_path()}")

    n = min(sample_size, len(examples))
    sampled = random.sample(examples, k=n)

    agent = Agent.create(
        AgentConfig(
            model=model,
            model_provider=model_provider,
            max_iterations=max_iterations,
            memory_enabled=False,
        )
    )

    system_prompt = "You are a careful financial QA evaluator. Provide only the required JSON fields."

    correct = 0
    results: list[dict[str, Any]] = []

    for idx, ex in enumerate(sampled, start=1):
        # Run agent to completion (non-streaming).
        answer = ""
        for ev in agent.run(ex.question, None):
            if ev.get("type") == "done":
                answer = str(ev.get("answer") or "")
                break

        entry: dict[str, Any] = {
            "index": idx,
            "question": ex.question,
            "expected_answer": ex.expected_answer,
            "actual_answer": answer,
        }

        if judge:
            try:
                j = judge_correctness(
                    model=model,
                    expected=ex.expected_answer,
                    actual=answer,
                    system_prompt=system_prompt,
                )
                entry["judge"] = {"score": j.score, "comment": j.comment}
                if j.score >= 1.0:
                    correct += 1
            except Exception as e:
                entry["judge_error"] = str(e)
        results.append(entry)

        print(f"[{idx}/{n}] done")

    accuracy = correct / n if n else 0.0
    summary = {"sampleSize": n, "correct": correct, "accuracy": accuracy}
    print(json.dumps(summary, indent=2))
    # Persist detailed results for later inspection.
    out_path = Path(".dexter") / "eval_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"summary": summary, "results": results}, default=str),
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="dexter-eval", description="Dexter evaluation runner (Python)")
    p.add_argument("--sample", type=int, default=5)
    p.add_argument("--model", default="gpt-5.4")
    p.add_argument("--provider", default="openai")
    p.add_argument("--max-iterations", type=int, default=10)
    p.add_argument("--no-judge", action="store_true")
    args = p.parse_args(argv)

    run_eval(
        sample_size=args.sample,
        model=args.model,
        model_provider=args.provider,
        max_iterations=args.max_iterations,
        judge=not args.no_judge,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
