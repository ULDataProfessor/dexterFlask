"""Memory tools — mirror src/tools/memory/*.ts."""

from __future__ import annotations

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field

from dexter_flask.memory.manager import MemoryManager
from dexter_flask.tools.format_util import format_tool_result


class MemSearchIn(BaseModel):
    query: str


def _mem_search(inp: MemSearchIn) -> str:
    m = MemoryManager.get()
    if not m.is_available():
        return format_tool_result(
            {"results": [], "disabled": True, "error": m.get_unavailable_reason()}, []
        )
    return format_tool_result({"results": m.search(inp.query)})


class MemGetIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    path: str
    from_: int | None = Field(default=None, alias="from")
    lines: int | None = None


def _mem_get(inp: MemGetIn) -> str:
    m = MemoryManager.get()
    d = m.read_lines_segment(path=inp.path, from_=inp.from_, lines=inp.lines)
    return format_tool_result(d)


class MemUpdIn(BaseModel):
    content: str | None = None
    action: str = "append"
    file: str = "long_term"
    old_text: str | None = None
    new_text: str | None = None


def _mem_upd(inp: MemUpdIn) -> str:
    m = MemoryManager.get()
    if inp.action == "append":
        if not inp.content:
            return format_tool_result({"success": False, "error": "content required"})
        m.append_memory(inp.file, inp.content)
        return format_tool_result({"success": True, "file": inp.file})
    if inp.action == "edit":
        if not inp.old_text or inp.new_text is None:
            return format_tool_result(
                {"success": False, "error": "old_text and new_text required"}
            )
        ok = m.edit_memory(inp.file, inp.old_text, inp.new_text)
        return format_tool_result({"success": ok})
    if inp.action == "delete":
        if not inp.old_text:
            return format_tool_result({"success": False, "error": "old_text required"})
        ok = m.delete_memory(inp.file, inp.old_text)
        return format_tool_result({"success": ok})
    return format_tool_result({"success": False, "error": "unknown action"})


MEMORY_SEARCH_DESCRIPTION = "Semantic/keyword search over memory files."
MEMORY_GET_DESCRIPTION = "Read a segment of a memory file."
MEMORY_UPDATE_DESCRIPTION = "Append, edit, or delete memory content."


def memory_search_tool() -> StructuredTool:
    return StructuredTool.from_function(
        name="memory_search",
        description=MEMORY_SEARCH_DESCRIPTION,
        func=_mem_search,
        args_schema=MemSearchIn,
    )


def memory_get_tool() -> StructuredTool:
    return StructuredTool.from_function(
        name="memory_get",
        description=MEMORY_GET_DESCRIPTION,
        func=_mem_get,
        args_schema=MemGetIn,
    )


def memory_update_tool() -> StructuredTool:
    return StructuredTool.from_function(
        name="memory_update",
        description=MEMORY_UPDATE_DESCRIPTION,
        func=_mem_upd,
        args_schema=MemUpdIn,
    )
