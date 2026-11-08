from __future__ import annotations

import sys
from pathlib import Path


def _resolve_project_root(start: Path) -> Path:
    """Find the repository containing this application entry point."""
    for parent in start.resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError(f"Could not find pyproject.toml above {start}")


_ROOT = _resolve_project_root(Path(__file__))
_SRC = _ROOT / "src"
_APPS = _ROOT / "apps"
for _p in (str(_SRC), str(_ROOT), str(_APPS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
