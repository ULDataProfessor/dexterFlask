"""API response cache — mirror src/utils/cache.ts (subset)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dexter_flask.paths import dexter_path


def _clean_endpoint(endpoint: str) -> str:
    return re.sub(r"^/+|/+$", "", endpoint).replace("/", "_") or "root"


def _cache_rel_path(endpoint: str, params: dict[str, Any]) -> Path:
    sorted_params = sorted(
        ((k, v) for k, v in params.items() if v is not None),
        key=lambda x: x[0],
    )
    raw = f"{endpoint}?{'&'.join(f'{k}={v}' for k, v in sorted_params)}"
    h = hashlib.md5(raw.encode()).hexdigest()[:12]
    ticker = params.get("ticker")
    prefix = f"{str(ticker).upper()}_" if isinstance(ticker, str) else ""
    sub = dexter_path("cache") / _clean_endpoint(endpoint)
    sub.mkdir(parents=True, exist_ok=True)
    return sub / f"{prefix}{h}.json"


def read_cache(endpoint: str, params: dict[str, Any]) -> dict[str, Any] | None:
    """Return full cache entry dict with keys data, url, or None."""
    p = _cache_rel_path(endpoint, params)
    if not p.is_file():
        return None
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or "data" not in obj or "url" not in obj:
            p.unlink(missing_ok=True)
            return None
        return obj
    except (json.JSONDecodeError, OSError):
        p.unlink(missing_ok=True)
        return None


def write_cache(endpoint: str, params: dict[str, Any], data: Any, url: str) -> None:
    p = _cache_rel_path(endpoint, params)
    entry = {
        "endpoint": endpoint,
        "params": params,
        "data": data,
        "url": url,
        "cachedAt": datetime.now(timezone.utc).isoformat(),
    }
    try:
        p.write_text(json.dumps(entry, default=str), encoding="utf-8")
    except OSError:
        pass
