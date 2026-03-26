"""Cron job execution (agent only; WhatsApp delivery stays in Node gateway)."""

from __future__ import annotations

import time
from typing import Any

from dexter_flask.cron_pkg.schedule import compute_next_run_at_ms
from dexter_flask.cron_pkg.store import load_cron_store, save_cron_store


def schedule_next_run(job: dict[str, Any], store: dict[str, Any]) -> None:
    now = int(time.time() * 1000)
    st = job.setdefault("state", {})
    try:
        nxt = compute_next_run_at_ms(job["schedule"], now)
        if nxt is None and job["schedule"].get("kind") == "at":
            job["enabled"] = False
            st["nextRunAtMs"] = None
        elif nxt is None:
            st["nextRunAtMs"] = st.get("nextRunAtMs")
        else:
            st["nextRunAtMs"] = nxt
        st["scheduleErrorCount"] = 0
    except Exception:
        st["scheduleErrorCount"] = int(st.get("scheduleErrorCount") or 0) + 1
        if st["scheduleErrorCount"] >= 3:
            job["enabled"] = False
            st["nextRunAtMs"] = None


def execute_cron_job(job: dict[str, Any], store: dict[str, Any] | None = None) -> None:
    """Run one cron job through the Python agent; update store."""
    if store is None:
        store = load_cron_store()
    started = int(time.time() * 1000)
    payload = job.get("payload") or {}
    model = payload.get("model") or "gpt-5.4"
    prov = payload.get("modelProvider") or "openai"
    msg = payload.get("message") or ""
    q = f"[CRON JOB: {job.get('name')}]\n\n{msg}"

    from dexter_flask.services.agent_runner import run_agent_for_message

    try:
        run_agent_for_message(
            {
                "sessionKey": f"cron:{job['id']}",
                "query": q,
                "model": model,
                "modelProvider": prov,
                "maxIterations": int(payload.get("maxIterations") or 6),
                "isolatedSession": True,
                "channel": "whatsapp",
            }
        )
        job.setdefault("state", {})["lastRunStatus"] = "ok"
        job["state"]["consecutiveErrors"] = 0
    except Exception as e:
        job.setdefault("state", {})["lastRunStatus"] = "error"
        job["state"]["lastError"] = str(e)
        job["state"]["consecutiveErrors"] = (
            int(job["state"].get("consecutiveErrors") or 0) + 1
        )

    job["state"]["lastRunAtMs"] = started
    job["state"]["lastDurationMs"] = int(time.time() * 1000) - started
    job["updatedAtMs"] = int(time.time() * 1000)
    if job.get("fulfillment") == "once":
        job["enabled"] = False
        job["state"]["nextRunAtMs"] = None
    else:
        schedule_next_run(job, store)
    save_cron_store(store)
