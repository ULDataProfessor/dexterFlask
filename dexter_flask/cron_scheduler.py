"""Background APScheduler tick for cron jobs."""
from __future__ import annotations

import time

from apscheduler.schedulers.background import BackgroundScheduler

from dexter_flask.cron_pkg.executor import execute_cron_job
from dexter_flask.cron_pkg.store import load_cron_store

_scheduler: BackgroundScheduler | None = None


def _tick() -> None:
    for _ in range(50):
        store = load_cron_store()
        now = int(time.time() * 1000)
        due = next(
            (
                j
                for j in store.get("jobs", [])
                if j.get("enabled")
                and (j.get("state") or {}).get("nextRunAtMs") is not None
                and int((j.get("state") or {})["nextRunAtMs"]) <= now
            ),
            None,
        )
        if due is None:
            break
        execute_cron_job(due, store)


def start_cron_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_tick, "interval", seconds=30, id="dexter_cron", replace_existing=True)
    _scheduler.start()
