"""read_filings meta-tool — mirror src/tools/finance/read-filings.ts."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.agent.prompts import get_current_date
from dexter_flask.llm.client import call_llm, call_llm_structured
from dexter_flask.tools.context import emit_tool_progress
from dexter_flask.tools.finance.filings_leaves import (
    create_get_filings_tool,
    filing_item_tools,
    get_filing_item_types,
)
from dexter_flask.tools.format_util import format_tool_result


class FilingPlan(BaseModel):
    ticker: str
    filing_types: list[str] = Field(description="10-K, 10-Q, 8-K")
    limit: int = 10


class ReadFilingsQuery(BaseModel):
    query: str


def _plan_prompt() -> str:
    return f"""You are a SEC filings planning assistant.
Current date: {get_current_date()}

Return ticker, filing_types, limit for the user query.
Resolve company names to tickers. Choose filing types appropriately. Default limit 10."""


def _step2_prompt(user_query: str, filings_data: list, item_types: dict[str, Any]) -> str:
    q = user_query.replace("{", "{{").replace("}", "}}")
    fd = json.dumps(filings_data, indent=2).replace("{", "{{").replace("}", "}}")
    it = json.dumps(item_types, indent=2).replace("{", "{{").replace("}", "}}")
    return f"""You are a SEC filings content retrieval assistant.
Current date: {get_current_date()}

Original user query: "{q}"

Available filings:
{fd}

Item type reference:
{it}

Select filings and call get_10K_filing_items, get_10Q_filing_items, or get_8K_filing_items.
Maximum 3 filing reads. Always specify items for 10-K and 10-Q when possible.
Call the appropriate tool(s) now."""


def _tc_parts(tc) -> tuple[str, dict]:
    if isinstance(tc, dict):
        return tc.get("name") or "", tc.get("args") or {}
    return getattr(tc, "name", "") or "", getattr(tc, "args", None) or {}


def create_read_filings_tool(model: str) -> StructuredTool:
    get_filings = create_get_filings_tool()
    step2_tools = filing_item_tools()
    step2_map = {t.name: t for t in step2_tools}

    def _fn(query: str) -> str:
        emit_tool_progress("Planning filing search...")
        try:
            plan_raw = call_llm_structured(
                query,
                model=model,
                system_prompt=_plan_prompt(),
                schema=FilingPlan,
            )
            plan = plan_raw if isinstance(plan_raw, FilingPlan) else FilingPlan.model_validate(plan_raw)
        except Exception as e:
            return format_tool_result({"error": "Failed to plan filing search", "details": str(e)}, [])

        emit_tool_progress(f"Fetching filings for {plan.ticker}...")
        try:
            filings_raw = get_filings.invoke(
                {
                    "ticker": plan.ticker,
                    "filing_type": plan.filing_types,
                    "limit": plan.limit,
                }
            )
            item_types = get_filing_item_types()
        except Exception as e:
            return format_tool_result({"error": "Failed to fetch filings metadata", "details": str(e)}, [])

        parsed = json.loads(filings_raw) if isinstance(filings_raw, str) else filings_raw
        filings_list = parsed.get("data") if isinstance(parsed, dict) else []
        source_urls = parsed.get("sourceUrls") if isinstance(parsed, dict) else []
        if not isinstance(filings_list, list):
            filings_list = []
        if not isinstance(source_urls, list):
            source_urls = []

        if len(filings_list) == 0:
            return format_tool_result(
                {"error": "No filings found", "params": plan.model_dump()}, source_urls
            )

        emit_tool_progress("Selecting content to read...")
        resp, _ = call_llm(
            "Select and call the appropriate filing item tools.",
            model=model,
            system_prompt=_step2_prompt(query, filings_list, item_types),
            tools=step2_tools,
        )
        if not isinstance(resp, AIMessage) or not resp.tool_calls:
            return format_tool_result(
                {"error": "Failed to select filings to read", "availableFilings": filings_list},
                source_urls,
            )

        limited = (resp.tool_calls or [])[:3]
        emit_tool_progress(f"Reading {len(limited)} filing(s)...")

        def exec_one(tc):
            name, args = _tc_parts(tc)
            tool = step2_map.get(name)
            if not tool:
                return name, args, None, [], f"Tool '{name}' not found"
            try:
                raw = tool.invoke(args)
                pr = json.loads(raw) if isinstance(raw, str) else raw
                if isinstance(pr, dict):
                    return name, args, pr.get("data"), pr.get("sourceUrls") or [], None
                return name, args, pr, [], None
            except Exception as e:
                return name, args, None, [], str(e)

        combined: dict = {}
        all_urls = list(source_urls)
        errors: list[dict] = []
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = [ex.submit(exec_one, tc) for tc in limited]
            for f in as_completed(futures):
                name, args, data, urls, err = f.result()
                all_urls.extend(urls or [])
                if err:
                    errors.append({"tool": name, "args": args, "error": err})
                else:
                    acc = args.get("accession_number") if isinstance(args, dict) else None
                    key = acc or f"{name}_{len(combined)}"
                    combined[key] = data
        if errors:
            combined["_errors"] = errors
        return format_tool_result(combined, all_urls)

    return StructuredTool.from_function(
        name="read_filings",
        description="Read SEC 10-K / 10-Q / 8-K content from natural language.",
        func=_fn,
        args_schema=ReadFilingsQuery,
    )
