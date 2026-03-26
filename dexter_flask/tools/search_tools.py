"""Web search — Exa / Tavily."""

from __future__ import annotations

import json

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from dexter_flask.config import get_settings
from dexter_flask.tools.cache_util import read_cache, write_cache
from dexter_flask.tools.format_util import format_tool_result

try:
    from langchain_community.tools.tavily_search import TavilySearchResults
except ImportError:
    TavilySearchResults = None  # type: ignore[misc, assignment]


class SearchIn(BaseModel):
    query: str


def _tavily(q: str) -> str:
    key = get_settings().tavily_api_key
    if not key or TavilySearchResults is None:
        raise RuntimeError("Tavily unavailable")
    tool = TavilySearchResults(api_key=key, max_results=5)
    raw = tool.invoke({"query": q})
    urls: list[str] = []
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return format_tool_result({"results": raw}, urls)
    else:
        data = raw
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("url"):
                urls.append(str(item["url"]))
        return format_tool_result({"results": data}, urls)
    return format_tool_result({"results": data}, urls)


def _exa(q: str) -> str:
    key = get_settings().exasearch_api_key
    if not key:
        raise RuntimeError("Exa key missing")
    with httpx.Client(timeout=60.0) as client:
        r = client.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": key, "Content-Type": "application/json"},
            json={"query": q, "numResults": 5, "useAutoprompt": True},
        )
        r.raise_for_status()
        data = r.json()
    urls = [h.get("url", "") for h in data.get("results", []) if isinstance(h, dict)]
    return format_tool_result(data, [u for u in urls if u])


def _web_search(inp: SearchIn) -> str:
    s = get_settings()
    if s.exasearch_api_key:
        provider = "exa"
    elif s.tavily_api_key and TavilySearchResults:
        provider = "tavily"
    else:
        provider = None

    if provider:
        cache_params = {"query": inp.query, "provider": provider}
        cached = read_cache("web_search", cache_params)
        if cached and isinstance(cached.get("data"), str):
            return cached["data"]

        try:
            out = _exa(inp.query) if provider == "exa" else _tavily(inp.query)
        except Exception as e:
            return format_tool_result({"error": str(e)}, [])

        write_cache("web_search", cache_params, out, url=f"{provider}:search")
        return out

    return format_tool_result({"error": "No search API key configured"}, [])


WEB_SEARCH_DESCRIPTION = "Search the web for current information (Exa or Tavily)."


def web_search_tool() -> StructuredTool | None:
    s = get_settings()
    if not s.exasearch_api_key and not s.tavily_api_key:
        return None
    return StructuredTool.from_function(
        name="web_search",
        description=WEB_SEARCH_DESCRIPTION,
        func=_web_search,
        args_schema=SearchIn,
    )
