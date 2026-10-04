"""Reject local and non-web navigation before starting a browser."""

import pytest

from dexter_flask.tools.browser_tool import BrowserIn, _browser


@pytest.mark.parametrize("url", ["file:///etc/passwd", "FILE:///tmp/secret", "data:text/plain,secret", "ftp://example.com/file", "/etc/passwd", "javascript:alert(1)", "https://[", "https:"])
def test_browser_rejects_non_http_schemes(url):
    result = _browser(BrowserIn(action="navigate", url=url))
    assert "Only http/https URLs" in result


def test_browser_public_tool_rejects_file_url():
    from dexter_flask.tools.browser_tool import browser_tool_fn
    assert "Only http/https URLs" in browser_tool_fn().invoke({"action": "navigate", "url": "file:///etc/passwd"})


@pytest.mark.parametrize("url", ["https://example.com/report", "http://example.com/report"])
def test_browser_preserves_web_navigation(monkeypatch, url):
    from contextlib import nullcontext
    import sys
    from types import SimpleNamespace
    from dexter_flask.tools.browser_tool import browser_tool_fn

    navigated = []
    page = SimpleNamespace(
        goto=lambda target, **kwargs: navigated.append(target),
        title=lambda: "Research", inner_text=lambda selector: "Public report",
    )
    browser = SimpleNamespace(new_page=lambda: page, close=lambda: None)
    playwright = SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs: browser))
    monkeypatch.setitem(sys.modules, "playwright", SimpleNamespace())
    monkeypatch.setitem(sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=lambda: nullcontext(playwright)))
    result = browser_tool_fn().invoke({"action": "navigate", "url": url})
    assert navigated == [url]
    assert "Public report" in result
