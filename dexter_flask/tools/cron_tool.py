"""Cron management tool — mirror cron-tool.ts."""

from __future__ import annotations

import secrets
import time
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.cron_pkg.executor import execute_cron_job
from dexter_flask.cron_pkg.schedule import compute_next_run_at_ms
from dexter_flask.cron_pkg.store import load_cron_store, save_cron_store

CRON_TOOL_DESCRIPTION = (
    "Create, list, update, remove, or run scheduled jobs (see cron-tool.ts)."
)


class CronIn(BaseModel):
    action: str
    name: str | None = None
    description: str | None = None
    schedule: dict[str, Any] | None = None
    message: str | None = None
    model: str | None = None
    modelProvider: str | None = None
    fulfillment: str | None = None
    jobId: str | None = None
    enabled: bool | None = None


def _fmt_sched(s: dict[str, Any]) -> str:
    k = s.get("kind")
    if k == "at":
        return f"one-shot at {s.get('at')}"
    if k == "every":
        ms = int(s.get("everyMs") or 0)
        return f"every {ms // 1000}s"
    if k == "cron":
        return f"cron {s.get('expr')} {s.get('tz') or ''}"
    return str(s)


def _fmt_job(job: dict[str, Any]) -> str:
    st = job.get("state") or {}
    n = st.get("nextRunAtMs")
    lr = st.get("lastRunAtMs")
    lines = [
        f"**{job.get('name')}** ({job.get('id')}) [{'enabled' if job.get('enabled') else 'DISABLED'}]",
        f"  Schedule: {_fmt_sched(job.get('schedule') or {})}",
        f"  Fulfillment: {job.get('fulfillment', 'keep')}",
        f"  Next run: {__import__('datetime').datetime.utcfromtimestamp(n / 1000).isoformat() if n else 'none'}",
        f"  Last run: {__import__('datetime').datetime.utcfromtimestamp(lr / 1000).isoformat() if lr else 'never'}",
    ]
    return "\n".join(lines)


def _cron(inp: CronIn) -> str:
    if inp.action == "list":
        store = load_cron_store()
        jobs = store.get("jobs") or []
        if not jobs:
            return "No scheduled jobs."
        return "\n\n".join(_fmt_job(j) for j in jobs)

    if inp.action == "add":
        if not inp.name or not inp.schedule or not inp.message:
            return "Error: name, schedule, and message are required for add."
        store = load_cron_store()
        now = int(time.time() * 1000)
        jid = secrets.token_hex(8)
        sched = inp.schedule
        nxt = compute_next_run_at_ms(sched, now)
        if nxt is None and sched.get("kind") == "at":
            return "Error: the specified time is in the past."
        job = {
            "id": jid,
            "name": inp.name,
            "description": inp.description,
            "enabled": True,
            "createdAtMs": now,
            "updatedAtMs": now,
            "schedule": sched,
            "payload": {
                "message": inp.message,
                "model": inp.model,
                "modelProvider": inp.modelProvider,
            },
            "fulfillment": inp.fulfillment or "keep",
            "state": {
                "nextRunAtMs": nxt,
                "consecutiveErrors": 0,
                "scheduleErrorCount": 0,
            },
        }
        store.setdefault("jobs", []).append(job)
        save_cron_store(store)
        return f'Created job "{inp.name}" (id: {jid}). Next: {nxt}'

    if inp.action == "update":
        if not inp.jobId:
            return "Error: jobId required."
        store = load_cron_store()
        job = next((j for j in store["jobs"] if j.get("id") == inp.jobId), None)
        if not job:
            return f"Error: job {inp.jobId} not found."
        if inp.name is not None:
            job["name"] = inp.name
        if inp.description is not None:
            job["description"] = inp.description
        if inp.schedule is not None:
            job["schedule"] = inp.schedule
            job.setdefault("state", {})["nextRunAtMs"] = compute_next_run_at_ms(
                inp.schedule, int(time.time() * 1000)
            )
            job["state"]["scheduleErrorCount"] = 0
        pl = job.setdefault("payload", {})
        if inp.message is not None:
            pl["message"] = inp.message
        if inp.model is not None:
            pl["model"] = inp.model
        if inp.modelProvider is not None:
            pl["modelProvider"] = inp.modelProvider
        if inp.fulfillment is not None:
            job["fulfillment"] = inp.fulfillment
        if inp.enabled is not None:
            job["enabled"] = inp.enabled
            if inp.enabled and not job.get("state", {}).get("nextRunAtMs"):
                job["state"]["nextRunAtMs"] = compute_next_run_at_ms(
                    job["schedule"], int(time.time() * 1000)
                )
        job["updatedAtMs"] = int(time.time() * 1000)
        save_cron_store(store)
        return f"Updated job {inp.jobId}."

    if inp.action == "remove":
        if not inp.jobId:
            return "Error: jobId required."
        store = load_cron_store()
        jobs = store.get("jobs", [])
        idx = next((i for i, j in enumerate(jobs) if j.get("id") == inp.jobId), -1)
        if idx < 0:
            return f"Error: job {inp.jobId} not found."
        jobs.pop(idx)
        save_cron_store(store)
        return "Removed job."

    if inp.action == "run":
        if not inp.jobId:
            return "Error: jobId required."
        store = load_cron_store()
        job = next((j for j in store["jobs"] if j.get("id") == inp.jobId), None)
        if not job:
            return f"Error: job {inp.jobId} not found."
        execute_cron_job(job, store)
        return f"Executed job. Status: {job.get('state', {}).get('lastRunStatus')}"

    return "Unknown action."


def cron_tool_fn() -> StructuredTool:
    return StructuredTool.from_function(
        name="cron", description=CRON_TOOL_DESCRIPTION, func=_cron, args_schema=CronIn
    )
