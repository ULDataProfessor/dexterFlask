"""Memory file store — mirror src/memory/store.ts."""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path

from dexter_flask.paths import dexter_path

LONG_TERM = "MEMORY.md"
DAILY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")


def format_daily_name(dt: datetime | None = None) -> str:
    d = dt or datetime.now()
    return f"{d.year:04d}-{d.month:02d}-{d.day:02d}.md"


class MemoryStore:
    def __init__(self) -> None:
        self._mem = dexter_path("memory")

    def ensure_dir(self) -> None:
        self._mem.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str) -> Path:
        p = Path(path)
        if p.is_absolute():
            raise ValueError("Memory paths must be relative")
        rp = (self._mem / path).resolve()
        mem_r = self._mem.resolve()
        try:
            rp.relative_to(mem_r)
        except ValueError as e:
            raise ValueError("Path outside memory dir") from e
        return rp

    def read_file(self, path: str) -> str:
        rp = self.resolve(path)
        try:
            return rp.read_text(encoding="utf-8")
        except OSError:
            return ""

    def write_file(self, path: str, content: str) -> None:
        self.ensure_dir()
        rp = self.resolve(path)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(content, encoding="utf-8")

    def append_file(self, path: str, content: str) -> None:
        prev = self.read_file(path)
        sep = "" if prev.endswith("\n") or not prev else "\n"
        self.write_file(path, f"{prev}{sep}{content}")

    def edit_file(self, path: str, old: str, new: str) -> bool:
        c = self.read_file(path)
        if old not in c:
            return False
        self.write_file(path, c.replace(old, new, 1))
        return True

    def delete_snippet(self, path: str, text: str) -> bool:
        c = self.read_file(path)
        if text not in c:
            return False
        self.write_file(path, c.replace(text, "").replace("\n\n\n", "\n\n"))
        return True

    def list_files(self) -> list[str]:
        self.ensure_dir()
        out: list[str] = []
        for p in self._mem.iterdir():
            if p.is_file() and (p.name == LONG_TERM or DAILY_RE.match(p.name)):
                out.append(p.name)
        return sorted(out)

    def read_lines(self, path: str, from_line: int | None, max_lines: int | None) -> dict:
        text = self.read_file(path)
        if not text:
            return {"path": path, "text": ""}
        lines = text.split("\n")
        start = max(1, from_line or 1) - 1
        end = len(lines) if not max_lines else min(start + max_lines, len(lines))
        return {"path": path, "text": "\n".join(lines[start:end])}

    def load_session_context(self, max_tokens: int = 2000) -> dict:
        files_loaded: list[str] = []
        sections: list[str] = []
        est = 0
        yesterday = datetime.now() - timedelta(days=1)
        for fn in [LONG_TERM, format_daily_name(), format_daily_name(yesterday)]:
            c = self.read_file(fn).strip()
            if not c:
                continue
            t = len(c) // 4
            if est + t > max_tokens:
                break
            est += t
            files_loaded.append(fn)
            sections.append(f"### {fn}\n{c}")
        text = "\n\n".join(sections)
        return {"filesLoaded": files_loaded, "text": text, "tokenCount": est}
