"""Path helpers — mirror src/utils/paths.ts."""

from __future__ import annotations

import os
from pathlib import Path

DEXTER_DIR = ".dexter"


def get_dexter_dir() -> str:
    return DEXTER_DIR


def dexter_path(*segments: str) -> Path:
    return Path(get_dexter_dir()).joinpath(*segments)


def repo_root() -> Path:
    """Project root (cwd or env DEXTER_REPO_ROOT)."""
    env = os.environ.get("DEXTER_REPO_ROOT")
    if env:
        return Path(env).resolve()
    return Path.cwd()


def soul_md_path() -> Path:
    p = repo_root() / "SOUL.md"
    if p.is_file():
        return p
    return Path(__file__).resolve().parent.parent / "SOUL.md"
