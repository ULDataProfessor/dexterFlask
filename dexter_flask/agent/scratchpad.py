"""Scratchpad — mirror src/agent/scratchpad.ts."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dexter_flask.paths import dexter_path


@dataclass
class ToolCallRecord:
    tool: str
    args: dict[str, Any]
    result: str


class Scratchpad:
    DEFAULT_LIMIT = {"max_calls_per_tool": 3, "similarity_threshold": 0.7}

    def __init__(self, query: str, limit_config: dict | None = None) -> None:
        cfg = {**self.DEFAULT_LIMIT, **(limit_config or {})}
        self._max_calls = cfg["max_calls_per_tool"]
        self._sim_threshold = cfg["similarity_threshold"]
        self._scratchpad_dir = dexter_path("scratchpad")
        self._scratchpad_dir.mkdir(parents=True, exist_ok=True)
        h = hashlib.md5(query.encode()).hexdigest()[:12]
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%d-%H%M%S").replace(":", "")
        self.filepath = self._scratchpad_dir / f"{ts}_{h}.jsonl"
        self._tool_counts: dict[str, int] = {}
        self._tool_queries: dict[str, list[str]] = {}
        self._cleared_indices: set[int] = set()
        self._append({"type": "init", "content": query, "timestamp": now.isoformat()})

    def _append(self, entry: dict) -> None:
        with self.filepath.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def add_tool_result(self, tool_name: str, args: dict, result: str) -> None:
        self._append(
            {
                "type": "tool_result",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "toolName": tool_name,
                "args": args,
                "result": self._parse_result_safely(result),
            }
        )

    def add_thinking(self, thought: str) -> None:
        self._append(
            {"type": "thinking", "content": thought, "timestamp": datetime.now(timezone.utc).isoformat()}
        )

    def _parse_result_safely(self, result: str) -> Any:
        try:
            return json.loads(result)
        except (json.JSONDecodeError, TypeError):
            return result

    def _read_entries(self) -> list[dict]:
        if not self.filepath.is_file():
            return []
        out: list[dict] = []
        for line in self.filepath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
                if isinstance(o, dict) and "type" in o and "timestamp" in o:
                    out.append(o)
            except json.JSONDecodeError:
                continue
        return out

    def _tokenize(self, q: str) -> set[str]:
        q = re.sub(r"[^\w\s]", " ", q.lower())
        return {w for w in q.split() if len(w) > 2}

    def _similarity(self, a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union else 0.0

    def _find_similar(self, new_q: str, previous: list[str]) -> str | None:
        nw = self._tokenize(new_q)
        for pq in previous:
            if self._similarity(nw, self._tokenize(pq)) >= self._sim_threshold:
                return pq
        return None

    def can_call_tool(self, tool_name: str, query: str | None = None) -> tuple[bool, str | None]:
        c = self._tool_counts.get(tool_name, 0)
        if c >= self._max_calls:
            return (
                True,
                f"Tool '{tool_name}' has been called {c} times (suggested limit: {self._max_calls}).",
            )
        if query:
            prev = self._tool_queries.get(tool_name, [])
            if self._find_similar(query, prev):
                return (
                    True,
                    f"This query is very similar to a previous '{tool_name}' call.",
                )
        if c == self._max_calls - 1:
            return (
                True,
                f"You are approaching the suggested limit for '{tool_name}'.",
            )
        return True, None

    def record_tool_call(self, tool_name: str, query: str | None = None) -> None:
        self._tool_counts[tool_name] = self._tool_counts.get(tool_name, 0) + 1
        if query:
            self._tool_queries.setdefault(tool_name, []).append(query)

    def get_tool_usage_status_lines(self) -> str | None:
        if not self._tool_counts:
            return None
        lines = []
        for name, cnt in self._tool_counts.items():
            mx = self._max_calls
            status = f"{cnt} calls (over suggested limit)" if cnt >= mx else f"{cnt}/{mx} calls"
            lines.append(f"- {name}: {status}")
        return "## Tool Usage This Query\n\n" + "\n".join(lines) + "\n\n"

    def format_tool_usage_for_prompt(self) -> str | None:
        return self.get_tool_usage_status_lines()

    def _stringify_result(self, result: Any) -> str:
        if isinstance(result, str):
            return result
        return json.dumps(result)

    def get_tool_results(self) -> str:
        entries = self._read_entries()
        formatted: list[str] = []
        tool_idx = 0
        for entry in entries:
            if entry.get("type") != "tool_result" or not entry.get("toolName"):
                continue
            if tool_idx in self._cleared_indices:
                formatted.append(f"[Tool result #{tool_idx + 1} cleared from context]")
                tool_idx += 1
                continue
            args = entry.get("args") or {}
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            result_str = self._stringify_result(entry.get("result"))
            formatted.append(f"### {entry['toolName']}({args_str})\n{result_str}")
            tool_idx += 1
        return "\n\n".join(formatted)

    def clear_oldest_tool_results(self, keep_count: int) -> int:
        entries = self._read_entries()
        tool_indices: list[int] = []
        idx = 0
        for entry in entries:
            if entry.get("type") == "tool_result":
                if idx not in self._cleared_indices:
                    tool_indices.append(idx)
                idx += 1
        to_clear = max(0, len(tool_indices) - keep_count)
        if to_clear == 0:
            return 0
        for i in range(to_clear):
            self._cleared_indices.add(tool_indices[i])
        return to_clear

    def get_tool_call_records(self) -> list[ToolCallRecord]:
        recs: list[ToolCallRecord] = []
        for e in self._read_entries():
            if e.get("type") == "tool_result" and e.get("toolName"):
                recs.append(
                    ToolCallRecord(
                        tool=e["toolName"],
                        args=e.get("args") or {},
                        result=self._stringify_result(e.get("result")),
                    )
                )
        return recs

    def has_executed_skill(self, skill_name: str) -> bool:
        for e in self._read_entries():
            if e.get("type") == "tool_result" and e.get("toolName") == "skill":
                args = e.get("args") or {}
                if args.get("skill") == skill_name:
                    return True
        return False
