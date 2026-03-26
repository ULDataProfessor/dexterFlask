"""Next-run scheduling — mirror src/cron/schedule.ts."""
from __future__ import annotations

import datetime as dt
from typing import Any

try:
    from croniter import croniter
except ImportError:
    croniter = None  # type: ignore[misc, assignment]

MIN_GAP_MS = 2000


def compute_next_run_at_ms(schedule: dict[str, Any], now_ms: int) -> int | None:
    kind = schedule.get("kind")
    if kind == "at":
        target = dt.datetime.fromisoformat(str(schedule["at"]).replace("Z", "+00:00"))
        t_ms = int(target.timestamp() * 1000)
        return t_ms if t_ms > now_ms else None
    if kind == "every":
        every = int(schedule.get("everyMs") or 0)
        if every <= 0:
            return None
        anchor = int(schedule.get("anchorMs") or now_ms)
        elapsed = now_ms - anchor
        periods = (elapsed + every - 1) // every
        nxt = anchor + periods * every
        if nxt <= now_ms:
            nxt += every
        return nxt
    if kind == "cron":
        if croniter is None:
            return None
        expr = str(schedule.get("expr") or "")
        tz = schedule.get("tz") or None
        base = dt.datetime.fromtimestamp(now_ms / 1000.0, tz=dt.timezone.utc)
        try:
            it = croniter(expr, base)
            nxt: dt.datetime | None = it.get_next(dt.datetime)
            if nxt is None:
                return None
            nxt_ms = int(nxt.timestamp() * 1000)
            if nxt_ms <= now_ms + MIN_GAP_MS:
                nxt_ms = now_ms + MIN_GAP_MS
            return nxt_ms
        except Exception:
            return None
    return None
