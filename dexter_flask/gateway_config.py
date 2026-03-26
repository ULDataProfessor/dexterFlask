"""Gateway config — mirror src/gateway/config.ts (subset)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from dexter_flask.paths import dexter_path

DEFAULT_CONFIG: dict[str, Any] = {
    "gateway": {
        "heartbeat": {
            "enabled": False,
            "intervalMinutes": 10,
            "maxIterations": 6,
        }
    }
}


def gateway_path() -> Path:
    return dexter_path("gateway.json")


def load_gateway_config() -> dict[str, Any]:
    p = gateway_path()
    if not p.is_file():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return json.loads(json.dumps(DEFAULT_CONFIG))


def save_gateway_config(cfg: dict[str, Any]) -> None:
    p = gateway_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def ensure_heartbeat_enabled() -> None:
    cfg = load_gateway_config()
    gw = cfg.setdefault("gateway", {})
    hb = gw.setdefault("heartbeat", {})
    if hb.get("enabled"):
        return
    hb["enabled"] = True
    hb.setdefault("intervalMinutes", 10)
    hb.setdefault("maxIterations", 6)
    save_gateway_config(cfg)
