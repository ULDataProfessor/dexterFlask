from __future__ import annotations

from pathlib import Path

import pytest

from dexter_flask.tools.fs_tools import ReadIn, read_file_tool


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    root = tmp_path / ".dexter" / "workspace"
    root.mkdir(parents=True)
    return root


@pytest.mark.parametrize("absolute", [False, True])
def test_read_file_reads_workspace_files(workspace: Path, absolute: bool) -> None:
    path = workspace / "reports" / "results.txt"
    path.parent.mkdir()
    path.write_text("Research results", encoding="utf-8")

    file_path = str(path) if absolute else "reports/results.txt"
    assert read_file_tool().invoke({"filePath": file_path}) == "Research results"


@pytest.mark.parametrize(
    "relative_path",
    ["../../.env", "../settings.json", "../workspace-other/secret.txt"],
)
def test_read_file_rejects_traversal(workspace: Path, relative_path: str) -> None:
    target = (workspace / relative_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("private data", encoding="utf-8")

    with pytest.raises(ValueError, match="Path escapes sandbox"):
        read_file_tool().invoke({"filePath": relative_path})


@pytest.mark.parametrize(
    "target_path", [".env", ".dexter/settings.json", ".dexter/workspace-other/secret.txt"]
)
def test_read_file_rejects_absolute_paths_elsewhere_in_repo(
    workspace: Path, target_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = workspace.parent.parent
    monkeypatch.setenv("DEXTER_REPO_ROOT", str(repo))
    target = repo / target_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("private data", encoding="utf-8")

    with pytest.raises(ValueError, match="Path escapes sandbox"):
        read_file_tool().invoke({"filePath": str(target)})


@pytest.mark.parametrize("absolute", [False, True])
@pytest.mark.parametrize("directory_link", [False, True])
def test_read_file_rejects_symlink_escape(
    workspace: Path, absolute: bool, directory_link: bool
) -> None:
    outside = workspace.parent / "private"
    outside.mkdir()
    (outside / "secret.txt").write_text("private data", encoding="utf-8")
    link = workspace / "linked"
    if directory_link:
        link.symlink_to(outside, target_is_directory=True)
        path = link / "secret.txt"
    else:
        link.symlink_to(outside / "secret.txt")
        path = link
    file_path = str(path) if absolute else str(path.relative_to(workspace))

    with pytest.raises(ValueError, match="Path escapes sandbox"):
        read_file_tool().invoke({"filePath": file_path})


def test_read_file_allows_symlink_within_workspace(workspace: Path) -> None:
    target = workspace / "results.txt"
    target.write_text("Research results", encoding="utf-8")
    (workspace / "linked.txt").symlink_to(target)

    assert read_file_tool().invoke({"filePath": "linked.txt"}) == "Research results"


def test_read_file_normalizes_paths_within_workspace(workspace: Path) -> None:
    (workspace / "reports").mkdir()
    (workspace / "results.txt").write_text("Research results", encoding="utf-8")

    result = read_file_tool().invoke({"filePath": "reports/../results.txt"})
    assert result == "Research results"


def test_read_file_reports_missing_files(workspace: Path) -> None:
    result = read_file_tool().invoke({"filePath": "missing.txt"})
    assert result == "Error: file not found: missing.txt"


def test_read_file_schema_advertises_workspace_boundary() -> None:
    description = ReadIn.model_fields["filePath"].description
    assert description is not None
    assert "absolute paths must also be inside .dexter/workspace" in description
