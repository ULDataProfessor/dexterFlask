"""X/Twitter search — mirror x-search.ts (subset)."""
from __future__ import annotations

import time
from urllib.parse import quote

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.config import get_settings
from dexter_flask.tools.format_util import format_tool_result

X_API = "https://api.x.com/2"
FIELDS = "tweet.fields=created_at,public_metrics,author_id&expansions=author_id&user.fields=username,name"


class XSearchIn(BaseModel):
    query: str = Field(description="Search query for X posts")


def _x_search(inp: XSearchIn) -> str:
    token = get_settings().x_bearer_token
    if not token:
        return format_tool_result({"error": "X_BEARER_TOKEN not set"}, [])
    q = quote(inp.query, safe="")
    url = f"{X_API}/tweets/search/recent?query={q}&{FIELDS}&max_results=10"
    time.sleep(0.35)
    r = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=60.0)
    if r.status_code == 429:
        return format_tool_result({"error": "X API rate limited"}, [])
    r.raise_for_status()
    return format_tool_result(r.json(), [url])


X_SEARCH_DESCRIPTION = "Search recent public posts on X/Twitter."

def x_search_tool() -> StructuredTool | None:
    if not get_settings().x_bearer_token:
        return None
    return StructuredTool.from_function(
        name="x_search", description=X_SEARCH_DESCRIPTION, func=_x_search, args_schema=XSearchIn
    )
