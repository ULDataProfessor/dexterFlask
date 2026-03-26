from __future__ import annotations

import types
import time


def test_web_fetch_caches_by_url_params(monkeypatch) -> None:
    from dexter_flask.tools import web_fetch as wf

    calls = {"n": 0}
    html = "<html><head><title>Example</title></head><body><p>Hello Cache</p></body></html>"

    class FakeResp:
        def __init__(self) -> None:
            self.text = html
            self.url = "https://example.com/final"

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *_: object, **__: object) -> None:
            return None

        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get(self, *_: object, **__: object) -> FakeResp:
            calls["n"] += 1
            return FakeResp()

    monkeypatch.setattr(wf.httpx, "Client", FakeClient)

    token = str(time.time_ns())
    inp = wf.WebFetchIn(
        url=f"https://example.com/page-cache-test-{token}",
        extractMode="markdown",
        maxChars=1000,
    )
    out1 = wf._fetch(inp)
    out2 = wf._fetch(inp)

    assert out1 == out2
    assert calls["n"] == 1

