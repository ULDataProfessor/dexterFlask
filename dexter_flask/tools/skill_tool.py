"""Skill loader tool — mirror skill.ts."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

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

    # Include local Markdown references without granting read_file access
    # outside its workspace. Resolve symlinks before checking the skill boundary.
    skill_dir = Path(skill_path).resolve().parent
    md_link_re = re.compile(r"\[([^\]]+)\]\(([^)]+\.md)\)")
    references: dict[Path, str] = {}

    def _repl(match: re.Match[str]) -> str:
        label = match.group(1)
        rel_path = match.group(2)
        try:
            if urlsplit(rel_path).scheme or rel_path.startswith("//"):
                return match.group(0)
            path = (skill_dir / rel_path).resolve()
            if (
                not path.is_relative_to(skill_dir)
                or path.suffix != ".md"
                or not path.is_file()
            ):
                return match.group(0)
            if path not in references:
                with path.open(encoding="utf-8", errors="replace") as reference:
                    references[path] = reference.read(200_000)
        except (OSError, RuntimeError, ValueError):
            return match.group(0)
        return f"{label} (reference included below)"

    resolved_body = md_link_re.sub(_repl, body)
    hdr = f"## Skill: {inp.skill}\n\n"
    if inp.args:
        hdr += f"**Arguments:** {inp.args}\n\n"
    reference_text = "".join(
        f"\n\n## Reference: {path.relative_to(skill_dir)}\n\n{content}"
        for path, content in references.items()
    )
    return hdr + resolved_body + reference_text


SKILL_TOOL_DESCRIPTION = "Load specialized skill instructions (see Available Skills)."


def skill_tool_fn() -> StructuredTool | None:
    if not discover_skills():
        return None
    return StructuredTool.from_function(
        name="skill",
        description=SKILL_TOOL_DESCRIPTION,
        func=lambda skill, args=None: _skill(SkillIn(skill=skill, args=args)),
        args_schema=SkillIn,
    )
