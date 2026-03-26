"""Heartbeat checklist tool — mirror heartbeat-tool.ts."""

from __future__ import annotations

import time

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.gateway_config import ensure_heartbeat_enabled
from dexter_flask.paths import dexter_path


class HbIn(BaseModel):
    action: str = Field(description="view or update")
    content: str | None = None


def _sync_heartbeat_cron() -> None:
    from dexter_flask.cron_pkg.store import load_cron_store, save_cron_store
    from dexter_flask.gateway.heartbeat_prompt import build_heartbeat_query

    store = load_cron_store()
    for j in store.get("jobs", []):
        if j.get("name") == "Heartbeat":
            q = build_heartbeat_query()
            j.setdefault("payload", {})
            if q is None:
                j["enabled"] = False
            else:
                j["payload"]["message"] = q
            j["updatedAtMs"] = int(time.time() * 1000)
            break
    save_cron_store(store)


def _heartbeat(inp: HbIn) -> str:
    path = dexter_path("HEARTBEAT.md")
    if inp.action == "view":
        if not path.is_file():
            return (
                "No heartbeat checklist configured yet. "
                "The heartbeat will use a default checklist. Use update to customize."
            )
        return f"Current heartbeat checklist:\n\n{path.read_text(encoding='utf-8')}"
    if inp.action == "update":
        if not inp.content:
            return "Error: content is required for update."
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(inp.content, encoding="utf-8")
        lines = [l for l in inp.content.split("\n") if l.strip().startswith("-")]
        if lines:
            ensure_heartbeat_enabled()
        _sync_heartbeat_cron()
        return f"Updated heartbeat checklist ({len(lines)} items)."
    return 'Unknown action. Use "view" or "update".'


HEARTBEAT_TOOL_DESCRIPTION = (
    "View or update .dexter/HEARTBEAT.md periodic monitoring checklist."
)


def heartbeat_tool_fn() -> StructuredTool:
    return StructuredTool.from_function(
        name="heartbeat",
        description=HEARTBEAT_TOOL_DESCRIPTION,
        func=_heartbeat,
        args_schema=HbIn,
    )
