"""Tool registry — mirror src/tools/registry.ts."""
from __future__ import annotations

from langchain_core.tools import BaseTool

from dexter_flask.tools.browser_tool import BROWSER_DESCRIPTION, browser_tool_fn
from dexter_flask.tools.cron_tool import CRON_TOOL_DESCRIPTION, cron_tool_fn
from dexter_flask.tools.finance.meta import create_get_financials_tool, create_get_market_data_tool
from dexter_flask.tools.finance.read_filings_tool import create_read_filings_tool
from dexter_flask.tools.finance.screen_stocks_tool import create_screen_stocks_tool
from dexter_flask.tools.fs_tools import (
    EDIT_FILE_DESCRIPTION,
    READ_FILE_DESCRIPTION,
    WRITE_FILE_DESCRIPTION,
    edit_file_tool,
    read_file_tool,
    write_file_tool,
)
from dexter_flask.tools.heartbeat_tool import HEARTBEAT_TOOL_DESCRIPTION, heartbeat_tool_fn
from dexter_flask.tools.memory_tools import (
    MEMORY_GET_DESCRIPTION,
    MEMORY_SEARCH_DESCRIPTION,
    MEMORY_UPDATE_DESCRIPTION,
    memory_get_tool,
    memory_search_tool,
    memory_update_tool,
)
from dexter_flask.tools.skill_tool import SKILL_TOOL_DESCRIPTION, skill_tool_fn
from dexter_flask.tools.search_tools import WEB_SEARCH_DESCRIPTION, web_search_tool
from dexter_flask.tools.web_fetch import WEB_FETCH_DESCRIPTION, web_fetch_tool
from dexter_flask.tools.x_search_tool import X_SEARCH_DESCRIPTION, x_search_tool

# Rich descriptions for system prompt (abbreviated where tools are self-explanatory)
GET_FINANCIALS_DESC = "Intelligent meta-tool for company financials, statements, ratios, estimates, segments. Pass full NL query once."
GET_MARKET_DATA_DESC = "Intelligent meta-tool for stock/crypto prices, news, insider trades."
READ_FILINGS_DESC = "Read SEC 10-K/10-Q/8-K content from natural language."
SCREEN_STOCKS_DESC = "Screen stocks by financial criteria from natural language."


def get_tool_registry(model: str) -> list[tuple[str, BaseTool, str]]:
    items: list[tuple[str, BaseTool, str]] = [
        ("get_financials", create_get_financials_tool(model), GET_FINANCIALS_DESC),
        ("get_market_data", create_get_market_data_tool(model), GET_MARKET_DATA_DESC),
        ("read_filings", create_read_filings_tool(model), READ_FILINGS_DESC),
        ("stock_screener", create_screen_stocks_tool(model), SCREEN_STOCKS_DESC),
        ("web_fetch", web_fetch_tool(), WEB_FETCH_DESCRIPTION),
        ("browser", browser_tool_fn(), BROWSER_DESCRIPTION),
        ("read_file", read_file_tool(), READ_FILE_DESCRIPTION),
        ("write_file", write_file_tool(), WRITE_FILE_DESCRIPTION),
        ("edit_file", edit_file_tool(), EDIT_FILE_DESCRIPTION),
        ("heartbeat", heartbeat_tool_fn(), HEARTBEAT_TOOL_DESCRIPTION),
        ("cron", cron_tool_fn(), CRON_TOOL_DESCRIPTION),
        ("memory_search", memory_search_tool(), MEMORY_SEARCH_DESCRIPTION),
        ("memory_get", memory_get_tool(), MEMORY_GET_DESCRIPTION),
        ("memory_update", memory_update_tool(), MEMORY_UPDATE_DESCRIPTION),
    ]
    ws = web_search_tool()
    if ws:
        items.append(("web_search", ws, WEB_SEARCH_DESCRIPTION))
    xs = x_search_tool()
    if xs:
        items.append(("x_search", xs, X_SEARCH_DESCRIPTION))
    sk = skill_tool_fn()
    if sk:
        items.append(("skill", sk, SKILL_TOOL_DESCRIPTION))
    return items


def get_tools(model: str) -> list[BaseTool]:
    return [t for _, t, _ in get_tool_registry(model)]


def build_tool_descriptions(model: str) -> str:
    return "\n\n".join(f"### {name}\n\n{desc}" for name, _, desc in get_tool_registry(model))
