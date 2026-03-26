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
        # Cached BM25 index over memory files for faster repeated searches.
        self._bm25_index_key: tuple[tuple[str, int], ...] | None = None
        self._bm25_bm25: Any | None = None
        self._bm25_files: list[str] = []
        self._bm25_texts: list[str] = []
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
        query_tokens = re.findall(r"[\w]+", query.lower())
        if not query_tokens:
            return []

        try:
            from rank_bm25 import BM25Okapi  # type: ignore
        except ImportError:
            # Fallback to the previous simple token containment scoring.
            results: list[tuple[float, dict[str, Any]]] = []
            for name in self._store.list_files():
                text = self._store.read_file(name)
                if not text:
                    continue
                lower = text.lower()
                score = sum(1 for t in query_tokens if t in lower)
                if score <= 0:
                    continue
                snippet = text[:500] + ("…" if len(text) > 500 else "")
                results.append((float(score), {"file_path": name, "snippet": snippet, "score": score / len(query_tokens)}))
            results.sort(key=lambda x: -x[0])
            return [r[1] for r in results[:max_results]]

        try:
            from rapidfuzz import fuzz  # type: ignore
        except ImportError:  # pragma: no cover
            fuzz = None

        files = self._store.list_files()
        if not files:
            return []

        key_parts: list[tuple[str, int]] = []
        for fn in files:
            p = self._store.resolve(fn)
            key_parts.append((fn, int(p.stat().st_mtime_ns)))
        index_key = tuple(key_parts)

        if self._bm25_bm25 is None or self._bm25_index_key != index_key:
            doc_tokens: list[list[str]] = []
            doc_texts: list[str] = []
            doc_files: list[str] = []
            for name in files:
                text = self._store.read_file(name)
                if not text:
                    continue
                doc_files.append(name)
                doc_texts.append(text)
                doc_tokens.append(re.findall(r"[\w]+", text.lower()))

            self._bm25_files = doc_files
            self._bm25_texts = doc_texts
            self._bm25_bm25 = BM25Okapi(doc_tokens) if doc_tokens else None
            self._bm25_index_key = index_key

        if self._bm25_bm25 is None or not self._bm25_files:
            return []

        scores = self._bm25_bm25.get_scores(query_tokens)
        max_score = max(float(s) for s in scores) if scores else 0.0
        denom = max_score if max_score > 0 else 1.0

        bonus_weight = 0.25
        results: list[tuple[float, dict[str, Any]]] = []
        for i, name in enumerate(self._bm25_files):
            text = self._bm25_texts[i] if i < len(self._bm25_texts) else ""
            snippet = text[:500] + ("…" if len(text) > 500 else "")

            bm25_score = float(scores[i]) if i < len(scores) else 0.0
            norm_bm25 = bm25_score / denom if denom else 0.0

            fuzzy_bonus = 0.0
            if fuzz:
                # Token-set fuzzy matching on query vs snippet tends to work well for short "recall".
                fuzzy_bonus = fuzz.token_set_ratio(query, snippet) / 100.0

            combined = norm_bm25 + bonus_weight * fuzzy_bonus
            final_score = combined / (1.0 + bonus_weight)

            # If both components are effectively zero, drop it.
            if final_score <= 0.0:
                continue

            results.append(
                (
                    final_score,
                    {
                        "file_path": name,
                        "snippet": snippet,
                        "score": final_score,
                    },
                )
            )

        results.sort(key=lambda x: -x[0])
        return [r[1] for r in results[:max_results]]
