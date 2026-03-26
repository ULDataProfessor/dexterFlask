"""Stock screener — mirror src/tools/finance/screen-stocks.ts."""

from __future__ import annotations

import json

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.agent.prompts import get_current_date
from dexter_flask.llm.client import call_llm_structured
from dexter_flask.tools.context import emit_tool_progress
from dexter_flask.tools.finance.api_client import get_api
from dexter_flask.tools.format_util import format_tool_result


class FilterItem(BaseModel):
    field: str
    operator: str = Field(description="gt, gte, lt, lte, eq, between")
    value: float | str | list[float] | list[str]


class ScreenerPayload(BaseModel):
    filters: list[FilterItem]
    currency: str = "USD"
    limit: int = 5


class ScreenQuery(BaseModel):
    query: str = Field(description="Natural language screening criteria")


_cached_metrics: dict | None = None


def _get_screener_filters() -> dict:
    global _cached_metrics
    if _cached_metrics:
        return _cached_metrics
    api = get_api()
    data, _ = api.get("/financials/search/screener/filters/", {})
    _cached_metrics = data
    return data


def _prompt(metrics: dict) -> str:
    esc = json.dumps(metrics, indent=2).replace("{", "{{").replace("}", "}}")
    return f"""You are a stock screening assistant.
Current date: {get_current_date()}

Produce structured filters from the user query.

## Available Screener Metrics
{esc}

Map criteria to exact field names and operators. Default limit 25 unless specified.
Return filters, currency (USD), limit."""


def create_screen_stocks_tool(model: str) -> StructuredTool:
    def _fn(query: str) -> str:
        emit_tool_progress("Loading screener metrics...")
        try:
            metrics = _get_screener_filters()
        except Exception as e:
            return format_tool_result(
                {"error": "Failed to fetch screener metrics", "details": str(e)}, []
            )
        emit_tool_progress("Building screening criteria...")
        try:
            payload = call_llm_structured(
                query,
                model=model,
                system_prompt=_prompt(metrics),
                schema=ScreenerPayload,
            )
            pl = (
                payload
                if isinstance(payload, ScreenerPayload)
                else ScreenerPayload.model_validate(payload)
            )
        except Exception as e:
            return format_tool_result(
                {"error": "Failed to parse screening criteria", "details": str(e)}, []
            )
        emit_tool_progress("Screening stocks...")
        body = {
            "filters": [f.model_dump() for f in pl.filters],
            "currency": pl.currency,
            "limit": pl.limit,
        }
        try:
            api = get_api()
            data, url = api.post("/financials/search/screener/", body)
            return format_tool_result(data, [url])
        except Exception as e:
            return format_tool_result(
                {
                    "error": "Screener request failed",
                    "details": str(e),
                    "filters": body["filters"],
                },
                [],
            )

    return StructuredTool.from_function(
        name="stock_screener",
        description="Screen stocks by financial criteria from natural language.",
        func=_fn,
        args_schema=ScreenQuery,
    )
