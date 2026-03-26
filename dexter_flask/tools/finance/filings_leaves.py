"""SEC filings leaf tools — mirror src/tools/finance/filings.ts."""

from __future__ import annotations

from typing import Any

import httpx
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.tools.finance.api_client import get_api
from dexter_flask.tools.format_util import format_tool_result

_cached_item_types: dict[str, Any] | None = None


def get_filing_item_types() -> dict[str, Any]:
    global _cached_item_types
    if _cached_item_types:
        return _cached_item_types
    r = httpx.get("https://api.financialdatasets.ai/filings/items/types/", timeout=60.0)
    r.raise_for_status()
    _cached_item_types = r.json()
    return _cached_item_types


class FilingsIn(BaseModel):
    ticker: str
    filing_type: list[str] | None = Field(default=None)
    limit: int = 10


def _get_filings(i: FilingsIn) -> str:
    api = get_api()
    params: dict[str, Any] = {"ticker": i.ticker.upper(), "limit": i.limit}
    if i.filing_type:
        params["filing_type"] = i.filing_type
    data, url = api.get("/filings/", params)
    return format_tool_result(data.get("filings") or [], [url])


class F10KIn(BaseModel):
    ticker: str
    accession_number: str
    items: list[str] | None = None


def _10k(i: F10KIn) -> str:
    api = get_api()
    params: dict[str, Any] = {
        "ticker": i.ticker.upper(),
        "filing_type": "10-K",
        "accession_number": i.accession_number,
    }
    if i.items:
        params["item"] = i.items
    data, url = api.get("/filings/items/", params, cacheable=True)
    return format_tool_result(data, [url])


class F10QIn(BaseModel):
    ticker: str
    accession_number: str
    items: list[str] | None = None


def _10q(i: F10QIn) -> str:
    api = get_api()
    params: dict[str, Any] = {
        "ticker": i.ticker.upper(),
        "filing_type": "10-Q",
        "accession_number": i.accession_number,
    }
    if i.items:
        params["item"] = i.items
    data, url = api.get("/filings/items/", params, cacheable=True)
    return format_tool_result(data, [url])


class F8KIn(BaseModel):
    ticker: str
    accession_number: str


def _8k(i: F8KIn) -> str:
    api = get_api()
    params = {
        "ticker": i.ticker.upper(),
        "filing_type": "8-K",
        "accession_number": i.accession_number,
    }
    data, url = api.get("/filings/items/", params, cacheable=True)
    return format_tool_result(data, [url])


def create_get_filings_tool() -> StructuredTool:
    return StructuredTool.from_function(
        name="get_filings",
        description="SEC filings metadata for a ticker.",
        func=_get_filings,
        args_schema=FilingsIn,
    )


def filing_item_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            name="get_10K_filing_items",
            description="10-K filing items.",
            func=_10k,
            args_schema=F10KIn,
        ),
        StructuredTool.from_function(
            name="get_10Q_filing_items",
            description="10-Q filing items.",
            func=_10q,
            args_schema=F10QIn,
        ),
        StructuredTool.from_function(
            name="get_8K_filing_items",
            description="8-K filing items.",
            func=_8k,
            args_schema=F8KIn,
        ),
    ]
