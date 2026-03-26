"""Meta tools get_financials / get_market_data — mirror get-financials.ts / get-market-data.ts."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.agent.prompts import get_current_date
from dexter_flask.llm.client import call_llm
from dexter_flask.tools.context import emit_tool_progress
from dexter_flask.tools.finance.leaves import finance_router_tools, market_router_tools
from dexter_flask.tools.format_util import format_tool_result


def _subtool_label(name: str) -> str:
    return " ".join(w.capitalize() for w in name.split("_"))


def _fin_router_prompt() -> str:
    return f"""You are a financial data routing assistant.
Current date: {get_current_date()}

Given a user's natural language query about financial data, call the appropriate financial tool(s).

1. Ticker resolution: Apple → AAPL, etc.
2. Prefer specific tools; use get_all_financial_statements when multiple statements needed.
3. Use smallest limit that answers the question.

Call the appropriate tool(s) now."""


def _market_router_prompt() -> str:
    return f"""You are a market data routing assistant.
Current date: {get_current_date()}

Given a user's natural language query about market data, call the appropriate tool(s).

1. Ticker resolution for stocks and crypto (BTC-USD, etc.).
2. For current prices use snapshot tools; for historical use price history tools.
3. For news use get_company_news; insider activity use get_insider_trades.

Call the appropriate tool(s) now."""


def _tc_parts(tc) -> tuple[str, dict]:
    if isinstance(tc, dict):
        return tc.get("name") or "", tc.get("args") or {}
    name = getattr(tc, "name", "") or ""
    args = getattr(tc, "args", None) or {}
    return name, args if isinstance(args, dict) else {}


def _run_router(
    query: str, model: str, system_prompt: str, tools: list[StructuredTool]
) -> str:
    emit_tool_progress("Routing...")
    tool_map = {t.name: t for t in tools}
    resp, _ = call_llm(query, model=model, system_prompt=system_prompt, tools=tools)
    if not isinstance(resp, AIMessage):
        return format_tool_result({"error": "Unexpected LLM response"}, [])
    tcs = resp.tool_calls or []
    if not tcs:
        return format_tool_result({"error": "No tools selected for query"}, [])
    labels = list({_subtool_label(_tc_parts(tc)[0]) for tc in tcs})
    emit_tool_progress(f"Fetching from {', '.join(labels)}...")

    def exec_one(tc):
        name, args = _tc_parts(tc)
        tool = tool_map.get(name)
        if not tool:
            return name, args, None, [], f"Tool '{name}' not found"
        try:
            raw = tool.invoke(args)
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict):
                return (
                    name,
                    args,
                    parsed.get("data"),
                    parsed.get("sourceUrls") or [],
                    None,
                )
            return name, args, parsed, [], None
        except Exception as e:
            return name, args, None, [], str(e)

    combined: dict = {}
    all_urls: list[str] = []
    errors: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(8, len(tcs))) as ex:
        futs = [ex.submit(exec_one, tc) for tc in tcs]
        for f in as_completed(futs):
            name, args, data, urls, err = f.result()
            all_urls.extend(urls or [])
            if err:
                errors.append({"tool": name, "args": args, "error": err})
            else:
                ticker = args.get("ticker") if isinstance(args, dict) else None
                key = f"{name}_{ticker}" if ticker else name
                combined[key] = data
    if errors:
        combined["_errors"] = errors
    return format_tool_result(combined, all_urls)


class RouterQuery(BaseModel):
    query: str = Field(description="Natural language query")


def create_get_financials_tool(model: str) -> StructuredTool:
    tools = finance_router_tools()

    def _fn(query: str) -> str:
        return _run_router(query, model, _fin_router_prompt(), tools)

    return StructuredTool.from_function(
        name="get_financials",
        description="Intelligent meta-tool for company financials, metrics, estimates, segments.",
        func=_fn,
        args_schema=RouterQuery,
    )


def create_get_market_data_tool(model: str) -> StructuredTool:
    tools = market_router_tools()

    def _fn(query: str) -> str:
        return _run_router(query, model, _market_router_prompt(), tools)

    return StructuredTool.from_function(
        name="get_market_data",
        description="Intelligent meta-tool for prices, news, insider trades, crypto.",
        func=_fn,
        args_schema=RouterQuery,
    )
