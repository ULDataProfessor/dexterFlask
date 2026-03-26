from __future__ import annotations

import types
import time


def test_web_search_caches_provider_query(monkeypatch) -> None:
    from dexter_flask.tools import search_tools

    calls = {"n": 0}

    def fake_exa(q: str) -> str:
        calls["n"] += 1
        return f"EXA_RESULT::{q}"

    def fake_settings() -> types.SimpleNamespace:
        return types.SimpleNamespace(
            exasearch_api_key="k",
            tavily_api_key=None,
        )

    monkeypatch.setattr(search_tools, "_exa", fake_exa)
    monkeypatch.setattr(search_tools, "get_settings", fake_settings)

    token = str(time.time_ns())
    inp = search_tools.SearchIn(query=f"cache me {token}")
    out1 = search_tools._web_search(inp)
    out2 = search_tools._web_search(inp)

    assert out1 == out2
    assert calls["n"] == 1

