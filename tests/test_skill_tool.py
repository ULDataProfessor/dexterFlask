from __future__ import annotations

from pathlib import Path

import pytest

from dexter_flask.tools import skill_tool


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    root = tmp_path / "skills" / "sample"
    root.mkdir(parents=True)
    return root


def load_skill(skill_dir: Path, body: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(skill_tool, "discover_skills", lambda: [object()])
    monkeypatch.setattr(
        skill_tool,
        "get_skill",
        lambda name: ("Sample skill", body, str(skill_dir / "SKILL.md")),
    )
    tool = skill_tool.skill_tool_fn()
    assert tool is not None
    return tool.invoke({"skill": "sample"})


def test_skill_includes_local_references_once(
    skill_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (skill_dir / "reference.md").write_text("Reference data", encoding="utf-8")

    result = load_skill(
        skill_dir,
        "Use [reference](reference.md), then [reference](./reference.md).",
        monkeypatch,
    )

    assert result.count("Reference data") == 1
    assert "## Reference: reference.md" in result
    assert str(skill_dir) not in result


def test_skill_includes_nested_references(
    skill_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (skill_dir / "references").mkdir()
    (skill_dir / "references" / "reference.md").write_text(
        "Reference data", encoding="utf-8"
    )

    result = load_skill(skill_dir, "[reference](references/reference.md)", monkeypatch)

    assert "Reference data" in result
    assert "## Reference: references/reference.md" in result


@pytest.mark.parametrize("link_type", ["traversal", "absolute", "symlink"])
def test_skill_does_not_include_references_outside_skill_directory(
    skill_dir: Path, monkeypatch: pytest.MonkeyPatch, link_type: str
) -> None:
    private = skill_dir.parent / "private.md"
    private.write_text("private data", encoding="utf-8")
    if link_type == "symlink":
        (skill_dir / "reference.md").symlink_to(private)
        target = "reference.md"
    elif link_type == "absolute":
        target = str(private)
    else:
        target = "../private.md"

    result = load_skill(skill_dir, f"[reference]({target})", monkeypatch)

    assert "private data" not in result
    assert "## Reference:" not in result


@pytest.mark.parametrize(
    "target",
    [
        "missing.md",
        "https://example.com/reference.md",
        "//example.com/reference.md",
        "http://[malformed].md",
    ],
)
def test_skill_preserves_unavailable_or_external_links(
    skill_dir: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    body = f"[reference]({target})"

    result = load_skill(skill_dir, body, monkeypatch)

    assert body in result
    assert "## Reference:" not in result


def test_builtin_dcf_includes_sector_wacc_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from dexter_flask.skills import registry

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(registry, "_skill_cache", None)
    tool = skill_tool.skill_tool_fn()
    assert tool is not None

    result = tool.invoke({"skill": "dcf-valuation"})

    assert result.count("# Sector WACC Adjustments") == 1
    assert "## Reference: sector-wacc.md" in result
    assert "Information Technology | 8-12%" in result


def test_skill_does_not_follow_markdown_symlink_to_non_markdown_file(
    skill_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private = skill_dir / ".env"
    private.write_text("private data", encoding="utf-8")
    (skill_dir / "reference.md").symlink_to(private)

    result = load_skill(skill_dir, "[reference](reference.md)", monkeypatch)

    assert "private data" not in result
    assert "## Reference:" not in result


def test_skill_tool_accepts_optional_arguments(
    skill_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    load_skill(skill_dir, "Instructions", monkeypatch)
    tool = skill_tool.skill_tool_fn()
    assert tool is not None

    result = tool.invoke({"skill": "sample", "args": "Analyze ACME"})

    assert "**Arguments:** Analyze ACME" in result
    assert "Instructions" in result
