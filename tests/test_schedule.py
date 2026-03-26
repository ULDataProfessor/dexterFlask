"""Tests for cron schedule helper."""
from __future__ import annotations

import datetime as dt

from dexter_flask.cron_pkg.schedule import compute_next_run_at_ms


def test_every_ms_schedules_future():
    now = 1_000_000
    sched = {"kind": "every", "everyMs": 60_000, "anchorMs": now}
    nxt = compute_next_run_at_ms(sched, now + 1000)
    assert nxt is not None
    assert nxt > now


def test_at_past_returns_none():
    past = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)).isoformat().replace("+00:00", "Z")
    sched = {"kind": "at", "at": past}
    now = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
    assert compute_next_run_at_ms(sched, now) is None


def test_health_endpoint():
    from dexter_flask.app import create_app

    app = create_app()
    c = app.test_client()
    r = c.get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}
