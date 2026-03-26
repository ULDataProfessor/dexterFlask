"""Heartbeat query builder — mirror src/gateway/heartbeat/prompt.ts."""

from __future__ import annotations

import re

from dexter_flask.paths import dexter_path

HEARTBEAT_OK_TOKEN = "HEARTBEAT_OK"  # must match TS gateway heartbeat/suppression.ts
DEFAULT_CHECKLIST = """- Major index moves (S&P 500, NASDAQ, Dow) — alert if any move more than 2% in a session
- Breaking financial news — major earnings surprises, Fed announcements, significant market events"""


def _heartbeat_path():
    return dexter_path("HEARTBEAT.md")


def load_heartbeat_document() -> str | None:
    p = _heartbeat_path()
    if not p.is_file():
        return None
    return p.read_text(encoding="utf-8")


def is_heartbeat_empty(content: str) -> bool:
    for line in content.split("\n"):
        t = line.strip()
        if not t:
            continue
        if re.match(r"^#+\s*", t):
            continue
        if re.match(r"^[-*]\s*$", t):
            continue
        return False
    return True


def build_heartbeat_query() -> str | None:
    raw = load_heartbeat_document()
    if raw is not None:
        if is_heartbeat_empty(raw):
            return None
        checklist = raw
    else:
        checklist = DEFAULT_CHECKLIST
    return f"""[HEARTBEAT CHECK]

{checklist}

If there is nothing actionable, respond with only: {HEARTBEAT_OK_TOKEN}
"""
