"""Skill loader tool — mirror skill.ts."""
from __future__ import annotations

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
    desc, body = loaded
    hdr = f"## Skill: {inp.skill}\n\n"
    if inp.args:
        hdr += f"**Arguments:** {inp.args}\n\n"
    return hdr + body


SKILL_TOOL_DESCRIPTION = "Load specialized skill instructions (see Available Skills)."


def skill_tool_fn() -> StructuredTool | None:
    if not discover_skills():
        return None
    return StructuredTool.from_function(
        name="skill", description=SKILL_TOOL_DESCRIPTION, func=_skill, args_schema=SkillIn
    )
