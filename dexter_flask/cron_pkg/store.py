"""Cron persistence — mirror src/cron/store.ts."""
from __future__ import annotations

import json
import secrets
from pathlib import Path

from dexter_flask.cron_pkg.types import CronStore
from dexter_flask.paths import dexter_path


def cron_store_path() -> Path:
    return dexter_path("cron", "jobs.json")


def load_cron_store() -> CronStore:
    p = cron_store_path()
    if not p.is_file():
        return {"version": 1, "jobs": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data.get("jobs"), list):
            return {"version": 1, "jobs": []}
        return data  # type: ignore[return-value]
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "jobs": []}


def save_cron_store(store: CronStore) -> None:
    p = cron_store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{secrets.token_hex(4)}.tmp")
    tmp.write_text(json.dumps(store, indent=2), encoding="utf-8")
    tmp.replace(p)
