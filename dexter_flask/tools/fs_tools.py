"""Sandboxed filesystem tools — mirror src/tools/filesystem/*.ts."""
from __future__ import annotations

from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.paths import dexter_path, repo_root


def _sandbox_root() -> Path:
    w = dexter_path("workspace")
    w.mkdir(parents=True, exist_ok=True)
    return w.resolve()


def _resolve_safe(rel: str) -> Path:
    root = _sandbox_root()
    p = (root / rel).resolve()
    root_r = root
    if root_r not in p.parents and p != root_r:
        raise ValueError("Path escapes sandbox")
    return p


def _resolve_read_safe(file_path: str) -> Path:
    """
    Read tool is allowed to read:
    - Relative paths under `.dexter/workspace`
    - Absolute paths within the repo root
    """
    p = Path(file_path)
    if p.is_absolute():
        rr = repo_root().resolve()
        rp = p.resolve()
        if rr != rp and rr not in rp.parents:
            raise ValueError("Absolute read path must be inside repo root")
        return rp
    return _resolve_safe(file_path)


class ReadIn(BaseModel):
    filePath: str = Field(
        description=(
            "Path to read. Relative paths are relative to .dexter/workspace; "
            "absolute paths must be inside the repo root."
        )
    )


def _read_file(inp: ReadIn) -> str:
    p = _resolve_read_safe(inp.filePath)
    if not p.is_file():
        return f"Error: file not found: {inp.filePath}"
    return p.read_text(encoding="utf-8", errors="replace")[:200_000]


class WriteIn(BaseModel):
    filePath: str
    content: str


def _write_file(inp: WriteIn) -> str:
    p = _resolve_safe(inp.filePath)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(inp.content, encoding="utf-8")
    return f"Wrote {len(inp.content)} bytes to {inp.filePath}"


class EditIn(BaseModel):
    filePath: str
    oldText: str
    newText: str


def _edit_file(inp: EditIn) -> str:
    p = _resolve_safe(inp.filePath)
    if not p.is_file():
        return "Error: file not found"
    c = p.read_text(encoding="utf-8")
    if inp.oldText not in c:
        return "Error: oldText not found"
    p.write_text(c.replace(inp.oldText, inp.newText, 1), encoding="utf-8")
    return "Edit applied"


READ_FILE_DESCRIPTION = "Read a file under .dexter/workspace."
WRITE_FILE_DESCRIPTION = "Write a file under .dexter/workspace."
EDIT_FILE_DESCRIPTION = "Find-and-replace edit in .dexter/workspace."


def read_file_tool() -> StructuredTool:
    return StructuredTool.from_function(
        name="read_file",
        description=READ_FILE_DESCRIPTION,
        func=_read_file,
        args_schema=ReadIn,
    )


def write_file_tool() -> StructuredTool:
    return StructuredTool.from_function(
        name="write_file",
        description=WRITE_FILE_DESCRIPTION,
        func=_write_file,
        args_schema=WriteIn,
    )


def edit_file_tool() -> StructuredTool:
    return StructuredTool.from_function(
        name="edit_file",
        description=EDIT_FILE_DESCRIPTION,
        func=_edit_file,
        args_schema=EditIn,
    )
