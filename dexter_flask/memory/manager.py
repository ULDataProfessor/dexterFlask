"""Memory manager — simplified hybrid: keyword ranking over memory files (SQLite vector optional later)."""
from __future__ import annotations

import re
from typing import Any

from dexter_flask.memory.store import LONG_TERM, MemoryStore, format_daily_name


class MemoryManager:
    _instance: MemoryManager | None = None

    def __init__(self) -> None:
        self._store = MemoryStore()
        self._init_error: str | None = None
        try:
            self._store.ensure_dir()
        except Exception as e:
            self._init_error = str(e)

    @classmethod
    def get(cls) -> MemoryManager:
        if cls._instance is None:
            cls._instance = MemoryManager()
        return cls._instance

    def is_available(self) -> bool:
        return self._init_error is None

    def get_unavailable_reason(self) -> str | None:
        return self._init_error

    def list_files(self) -> list[str]:
        return self._store.list_files()

    def load_session_context(self) -> dict[str, Any]:
        return self._store.load_session_context()

    def resolve_alias(self, file: str) -> str:
        if file == "long_term":
            return LONG_TERM
        if file == "daily":
            return format_daily_name()
        return file

    def get(self, *, path: str, from_: int | None = None, lines: int | None = None) -> dict:
        return self._store.read_lines(path, from_, lines)

    def append_memory(self, file: str, content: str) -> None:
        self._store.append_file(self.resolve_alias(file), content)

    def append_daily_memory(self, text: str) -> None:
        self._store.append_file(format_daily_name(), text)

    def edit_memory(self, file: str, old: str, new: str) -> bool:
        return self._store.edit_file(self.resolve_alias(file), old, new)

    def delete_memory(self, file: str, text: str) -> bool:
        return self._store.delete_snippet(self.resolve_alias(file), text)

    def search(self, query: str, max_results: int = 8) -> list[dict[str, Any]]:
        tokens = re.findall(r"[\w]+", query.lower())
        if not tokens:
            return []
        results: list[tuple[float, dict]] = []
        for name in self._store.list_files():
            text = self._store.read_file(name)
            if not text:
                continue
            lower = text.lower()
            score = sum(1 for t in tokens if t in lower)
            if score <= 0:
                continue
            snippet = text[:500] + ("…" if len(text) > 500 else "")
            results.append((score, {"file_path": name, "snippet": snippet, "score": score / len(tokens)}))
        results.sort(key=lambda x: -x[0])
        return [r[1] for r in results[:max_results]]
