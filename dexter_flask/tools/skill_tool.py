"""Skill loader tool — mirror skill.ts."""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from dexter_flask.skills.registry import discover_skills, get_skill


class SkillIn(BaseModel):
    skill: str = Field(description="Skill name")
    args: str | None = Field(default=None, description="Optional arguments")


def _skill(inp: SkillIn) -> str:
    loaded = get_skill(inp.skill)
    if not loaded:
        names = ", ".join(s.name for s in discover_skills()) or "none"
        return f'Error: Skill "{inp.skill}" not found. Available: {names}'
    desc, body, skill_path = loaded

    # Resolve markdown links like `[label](sector-wacc.md)` to absolute
    # repo-root paths so the agent can read the referenced file via the
    # `read_file` tool.
    skill_dir = Path(skill_path).parent
    md_link_re = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")

    def _repl(match: re.Match[str]) -> str:
        label = match.group(1)
        rel_path = match.group(2)
        if rel_path.startswith("/") or rel_path.startswith("http"):
            return match.group(0)
        abs_path = (skill_dir / rel_path).resolve()
        return f"[{label}]({abs_path})"

    resolved_body = md_link_re.sub(_repl, body)
    hdr = f"## Skill: {inp.skill}\n\n"
    if inp.args:
        hdr += f"**Arguments:** {inp.args}\n\n"
    return hdr + resolved_body


SKILL_TOOL_DESCRIPTION = "Load specialized skill instructions (see Available Skills)."


def skill_tool_fn() -> StructuredTool | None:
    if not discover_skills():
        return None
    return StructuredTool.from_function(
        name="skill",
        description=SKILL_TOOL_DESCRIPTION,
        func=_skill,
        args_schema=SkillIn,
    )
