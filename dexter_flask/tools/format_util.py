"""Tool result formatting — mirror src/tools/types.ts."""
from __future__ import annotations

import json
from typing import Any


def format_tool_result(data: Any, source_urls: list[str] | None = None) -> str:
    obj: dict[str, Any] = {"data": data}
    if source_urls:
        obj["sourceUrls"] = source_urls
    return json.dumps(obj, default=str)
