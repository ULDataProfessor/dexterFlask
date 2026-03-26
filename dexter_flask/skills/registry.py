"""Skill discovery — mirror src/skills/registry.ts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from dexter_flask.paths import dexter_path, repo_root


@dataclass
class SkillMetadata:
    name: str
    description: str
    path: str
    source: str


_skill_cache: dict[str, SkillMetadata] | None = None


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    meta = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return meta if isinstance(meta, dict) else {}, body


def extract_metadata(skill_md_path: Path, source: str) -> SkillMetadata:
    raw = skill_md_path.read_text(encoding="utf-8")
    data, _ = _parse_frontmatter(raw)
    name = data.get("name")
    desc = data.get("description")
    if not name or not desc:
        raise ValueError(f"Invalid skill frontmatter: {skill_md_path}")
    return SkillMetadata(
        name=str(name),
        description=str(desc),
        path=str(skill_md_path.resolve()),
        source=source,
    )


def _scan_dir(dir_path: Path, source: str) -> list[SkillMetadata]:
    if not dir_path.is_dir():
        return []
    out: list[SkillMetadata] = []
    for child in dir_path.iterdir():
        if child.is_dir():
            sf = child / "SKILL.md"
            if sf.is_file():
                try:
                    out.append(extract_metadata(sf, source))
                except ValueError:
                    continue
    return out


def discover_skills() -> list[SkillMetadata]:
    global _skill_cache
    if _skill_cache is not None:
        return list(_skill_cache.values())
    root = repo_root()
    dirs = [
        (Path(__file__).resolve().parent / "builtin", "builtin"),
        (dexter_path("skills"), "project"),
    ]
    merged: dict[str, SkillMetadata] = {}
    for path, src in dirs:
        for s in _scan_dir(path, src):
            merged[s.name] = s
    _skill_cache = merged
    return list(merged.values())


def get_skill(name: str) -> tuple[str, str, str] | None:
    discover_skills()
    assert _skill_cache is not None
    m = _skill_cache.get(name)
    if not m:
        return None
    raw = Path(m.path).read_text(encoding="utf-8")
    _, body = _parse_frontmatter(raw)
    return m.description, body, m.path


def build_skill_metadata_section() -> str:
    skills = discover_skills()
    lines = [f"- **{s.name}**: {s.description}" for s in skills]
    return "\n".join(lines)


def clear_skill_cache() -> None:
    global _skill_cache
    _skill_cache = None
