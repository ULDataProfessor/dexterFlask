"""Leaf Financial Datasets tools — mirror src/tools/finance/*.ts."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.tools.finance.api_client import get_api, strip_fields_deep
from dexter_flask.tools.format_util import format_tool_result

RF = ("accession_number", "currency", "period")
RI = ("issuer",)


def _strip(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


# --- Fundamentals ---
class StmtIn(BaseModel):
    ticker: str = Field(description="Stock ticker e.g. AAPL")
    period: Literal["annual", "quarterly", "ttm"] = "annual"
    limit: int = 4
    report_period_gt: str | None = None
    report_period_gte: str | None = None
    report_period_lt: str | None = None
    report_period_lte: str | None = None


def _stmt_params(i: StmtIn) -> dict[str, Any]:
    return _strip(
        {
            "ticker": i.ticker.upper(),
            "period": i.period,
            "limit": i.limit,
            "report_period_gt": i.report_period_gt,
            "report_period_gte": i.report_period_gte,
            "report_period_lt": i.report_period_lt,
            "report_period_lte": i.report_period_lte,
        }
    )


def _income(i: StmtIn) -> str:
    api = get_api()
    data, url = api.get("/financials/income-statements/", _stmt_params(i))
    return format_tool_result(
        strip_fields_deep(data.get("income_statements") or {}, RF), [url]
    )


def _balance(i: StmtIn) -> str:
    api = get_api()
    data, url = api.get("/financials/balance-sheets/", _stmt_params(i))
    return format_tool_result(strip_fields_deep(data.get("balance_sheets") or {}, RF), [url])


def _cashflow(i: StmtIn) -> str:
    api = get_api()
    data, url = api.get("/financials/cash-flow-statements/", _stmt_params(i))
    return format_tool_result(
        strip_fields_deep(data.get("cash_flow_statements") or {}, RF), [url]
    )


def _all_fin(i: StmtIn) -> str:
    api = get_api()
    data, url = api.get("/financials/", _stmt_params(i))
    return format_tool_result(strip_fields_deep(data.get("financials") or {}, RF), [url])


class EarnIn(BaseModel):
    ticker: str


def _earnings_fix(i: EarnIn) -> str:
    api = get_api()
    data, url = api.get("/earnings", {"ticker": i.ticker.upper()})
    return format_tool_result(data.get("earnings") or {}, [url])


class KeyIn(BaseModel):
    ticker: str


def _key_ratios(i: KeyIn) -> str:
    api = get_api()
    data, url = api.get("/financial-metrics/snapshot/", {"ticker": i.ticker.upper()})
    return format_tool_result(data.get("snapshot") or {}, [url])


class HistKeyIn(BaseModel):
    ticker: str
    period: Literal["annual", "quarterly", "ttm"] = "ttm"
    limit: int = 4
    report_period: str | None = None
    report_period_gt: str | None = None
    report_period_gte: str | None = None
    report_period_lt: str | None = None
    report_period_lte: str | None = None


def _hist_key(i: HistKeyIn) -> str:
    api = get_api()
    params = _strip(
        {
            "ticker": i.ticker.upper(),
            "period": i.period,
            "limit": i.limit,
            "report_period": i.report_period,
            "report_period_gt": i.report_period_gt,
            "report_period_gte": i.report_period_gte,
            "report_period_lt": i.report_period_lt,
            "report_period_lte": i.report_period_lte,
        }
    )
    data, url = api.get("/financial-metrics/", params)
    return format_tool_result(
        strip_fields_deep(data.get("financial_metrics") or [], RF), [url]
    )


class EstIn(BaseModel):
    ticker: str
    period: Literal["annual", "quarterly"] = "annual"


def _estimates(i: EstIn) -> str:
    api = get_api()
    data, url = api.get("/analyst-estimates/", {"ticker": i.ticker.upper(), "period": i.period})
    return format_tool_result(data.get("analyst_estimates") or [], [url])


class SegIn(BaseModel):
    ticker: str
    period: Literal["annual", "quarterly"]
    limit: int = 4


def _segments(i: SegIn) -> str:
    api = get_api()
    data, url = api.get(
        "/financials/segmented-revenues/",
        {"ticker": i.ticker.upper(), "period": i.period, "limit": i.limit},
    )
    return format_tool_result(
        strip_fields_deep(data.get("segmented_revenues") or {}, RF), [url]
    )


# --- Market ---
class SnapIn(BaseModel):
    ticker: str


def _stock_snap(i: SnapIn) -> str:
    api = get_api()
    data, url = api.get("/prices/snapshot/", {"ticker": i.ticker.upper()})
    return format_tool_result(data.get("snapshot") or {}, [url])


class PricesIn(BaseModel):
    ticker: str
    interval: Literal["day", "week", "month", "year"] = "day"
    start_date: str
    end_date: str


def _stock_prices(i: PricesIn) -> str:
    api = get_api()
    params = {
        "ticker": i.ticker.upper(),
        "interval": i.interval,
        "start_date": i.start_date,
        "end_date": i.end_date,
    }
    end = datetime.strptime(i.end_date, "%Y-%m-%d").date()
    today = datetime.now().date()
    cacheable = end < today
    data, url = api.get("/prices/", params, cacheable=cacheable)
    return format_tool_result(data.get("prices") or [], [url])


def _stock_tickers(_: dict) -> str:
    api = get_api()
    data, url = api.get("/prices/snapshot/tickers/", {})
    return format_tool_result(data.get("tickers") or [], [url])


class CryptoSnapIn(BaseModel):
    ticker: str


def _crypto_snap(i: CryptoSnapIn) -> str:
    api = get_api()
    data, url = api.get("/crypto/prices/snapshot/", {"ticker": i.ticker})
    return format_tool_result(data.get("snapshot") or {}, [url])


class CryptoPricesIn(BaseModel):
    ticker: str
    interval: Literal["minute", "day", "week", "month", "year"] = "day"
    interval_multiplier: int = 1
    start_date: str
    end_date: str


def _crypto_prices(i: CryptoPricesIn) -> str:
    api = get_api()
    params = {
        "ticker": i.ticker,
        "interval": i.interval,
        "interval_multiplier": i.interval_multiplier,
        "start_date": i.start_date,
        "end_date": i.end_date,
    }
    end = datetime.strptime(i.end_date, "%Y-%m-%d").date()
    cacheable = end < datetime.now().date()
    data, url = api.get("/crypto/prices/", params, cacheable=cacheable)
    return format_tool_result(data.get("prices") or [], [url])


def _crypto_tickers(_: dict) -> str:
    api = get_api()
    data, url = api.get("/crypto/prices/tickers/", {})
    return format_tool_result(data.get("tickers") or [], [url])


class NewsIn(BaseModel):
    ticker: str
    limit: int = 5


def _news(i: NewsIn) -> str:
    api = get_api()
    data, url = api.get(
        "/news", {"ticker": i.ticker.upper(), "limit": min(i.limit, 10)}
    )
    return format_tool_result(data.get("news") or [], [url])


class InsiderIn(BaseModel):
    ticker: str
    limit: int = 10
    filing_date: str | None = None
    filing_date_gte: str | None = None
    filing_date_lte: str | None = None
    filing_date_gt: str | None = None
    filing_date_lt: str | None = None


def _insider(i: InsiderIn) -> str:
    api = get_api()
    params = _strip(
        {
            "ticker": i.ticker.upper(),
            "limit": i.limit,
            "filing_date": i.filing_date,
            "filing_date_gte": i.filing_date_gte,
            "filing_date_lte": i.filing_date_lte,
            "filing_date_gt": i.filing_date_gt,
            "filing_date_lt": i.filing_date_lt,
        }
    )
    data, url = api.get("/insider-trades/", params)
    return format_tool_result(strip_fields_deep(data.get("insider_trades") or [], RI), [url])


class Empty(BaseModel):
    model_config = {"extra": "forbid"}


def finance_router_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(name="get_income_statements", description="Income statements.", func=_income, args_schema=StmtIn),
        StructuredTool.from_function(name="get_balance_sheets", description="Balance sheets.", func=_balance, args_schema=StmtIn),
        StructuredTool.from_function(name="get_cash_flow_statements", description="Cash flow statements.", func=_cashflow, args_schema=StmtIn),
        StructuredTool.from_function(name="get_all_financial_statements", description="All financial statements.", func=_all_fin, args_schema=StmtIn),
        StructuredTool.from_function(name="get_earnings", description="Latest earnings snapshot.", func=_earnings_fix, args_schema=EarnIn),
        StructuredTool.from_function(name="get_key_ratios", description="Financial metrics snapshot.", func=_key_ratios, args_schema=KeyIn),
        StructuredTool.from_function(name="get_historical_key_ratios", description="Historical key ratios.", func=_hist_key, args_schema=HistKeyIn),
        StructuredTool.from_function(name="get_analyst_estimates", description="Analyst estimates.", func=_estimates, args_schema=EstIn),
        StructuredTool.from_function(name="get_segmented_revenues", description="Segmented revenues.", func=_segments, args_schema=SegIn),
    ]


def market_router_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(name="get_stock_price", description="Stock price snapshot.", func=_stock_snap, args_schema=SnapIn),
        StructuredTool.from_function(name="get_stock_prices", description="Historical stock prices.", func=_stock_prices, args_schema=PricesIn),
        StructuredTool.from_function(
            name="get_available_stock_tickers",
            description="List stock tickers.",
            func=lambda **kw: _stock_tickers(kw),
            args_schema=Empty,
        ),
        StructuredTool.from_function(name="get_crypto_price_snapshot", description="Crypto snapshot.", func=_crypto_snap, args_schema=CryptoSnapIn),
        StructuredTool.from_function(name="get_crypto_prices", description="Historical crypto.", func=_crypto_prices, args_schema=CryptoPricesIn),
        StructuredTool.from_function(
            name="get_available_crypto_tickers",
            description="List crypto tickers.",
            func=lambda **kw: _crypto_tickers(kw),
            args_schema=Empty,
        ),
        StructuredTool.from_function(name="get_company_news", description="Company news.", func=_news, args_schema=NewsIn),
        StructuredTool.from_function(name="get_insider_trades", description="Insider trades.", func=_insider, args_schema=InsiderIn),
    ]
