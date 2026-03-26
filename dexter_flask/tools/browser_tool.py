"""Headless browser — Playwright subset for JS pages."""
from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.tools.format_util import format_tool_result


class BrowserIn(BaseModel):
    action: str = Field(description="navigate | snapshot | click (ref from snapshot)")
    url: str | None = None
    ref: str | None = None


def _browser(inp: BrowserIn) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return format_tool_result({"error": "playwright not installed; pip install playwright && playwright install chromium"}, [])
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            if inp.action == "navigate" and inp.url:
                page.goto(inp.url, wait_until="networkidle", timeout=60_000)
                title = page.title()
                text = page.inner_text("body")[:30_000]
                browser.close()
                return format_tool_result({"title": title, "text": text}, [inp.url])
            browser.close()
            return format_tool_result({"error": "Unsupported action or missing url"}, [])
    except Exception as e:
        return format_tool_result({"error": str(e)}, [])


BROWSER_DESCRIPTION = "Use headless browser for JS-heavy pages: navigate to url and return page text."


def browser_tool_fn() -> StructuredTool:
    return StructuredTool.from_function(name="browser", description=BROWSER_DESCRIPTION, func=_browser, args_schema=BrowserIn)
