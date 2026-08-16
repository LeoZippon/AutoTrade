"""Shared script bootstrap for direct repo execution."""

from __future__ import annotations

import sys
from pathlib import Path


def add_repo_src(file: str) -> Path:
    """Pin THIS repo's `src/` at the FRONT of sys.path.

    Presence is not precedence: a sibling checkout installed editable into the
    shared environment sorts its .pth before ours, so merely finding our src
    somewhere in sys.path let production scripts silently import the sibling's
    `autotrade` (observed 2026-08-13: a foreign cron_update mutated this lake).
    """
    root = _repo_root(Path(file).resolve())
    src = str(root / "src")
    while src in sys.path:
        sys.path.remove(src)
    sys.path.insert(0, src)
    return root


def _repo_root(path: Path) -> Path:
    for parent in (path.parent, *path.parents):
        if (parent / "src" / "autotrade").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError(f"cannot locate repo root from {path}")
