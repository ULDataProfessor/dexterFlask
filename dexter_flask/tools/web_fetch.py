"""Fetch URL and extract readable text — mirror web-fetch.ts (subset)."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from readability import Document

from dexter_flask.tools.cache_util import read_cache, write_cache
from dexter_flask.tools.format_util import format_tool_result


class WebFetchIn(BaseModel):
    url: str = Field(description="HTTP(S) URL to fetch")
    extractMode: str = Field(
        default="markdown", description="markdown or text"
    )
    maxChars: int = Field(default=20_000)


def _fetch(inp: WebFetchIn) -> str:
    u = inp.url.strip()
    if urlparse(u).scheme not in ("http", "https"):
        return format_tool_result({"error": "Only http/https URLs"}, [])

    cache_params = {
        "url": u,
        "extractMode": inp.extractMode,
        "maxChars": inp.maxChars,
    }
    cached = read_cache("web_fetch", cache_params)
    if cached and isinstance(cached.get("data"), str):
        return cached["data"]

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        r = client.get(u, headers={"User-Agent": "DexterBot/1.0"})
        r.raise_for_status()
        html = r.text
        final = str(r.url)
    try:
        doc = Document(html)
        title = doc.title() or ""
        summary_html = doc.summary()
        soup = BeautifulSoup(summary_html, "lxml")
        text = soup.get_text("\n", strip=True)
    except Exception:
        soup = BeautifulSoup(html, "lxml")
        title = soup.title.string if soup.title else ""
        text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if inp.extractMode == "text":
        pass
    truncated = len(text) > inp.maxChars
    text = text[: inp.maxChars]

    out = format_tool_result(
        {
            "url": u,
            "finalUrl": final,
            "title": title,
            "text": text,
            "extractMode": inp.extractMode,
            "truncated": truncated,
        },
        [final],
    )
    # Cache only successful responses (when we have a final URL).
    write_cache("web_fetch", cache_params, out, final)
    return out


WEB_FETCH_DESCRIPTION = (
    "Fetch a web page URL and return extracted readable content."
)


def web_fetch_tool() -> StructuredTool:
    return StructuredTool.from_function(
        name="web_fetch",
        description=WEB_FETCH_DESCRIPTION,
        func=_fetch,
        args_schema=WebFetchIn,
    )
