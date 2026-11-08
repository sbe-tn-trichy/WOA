"""Compatibility entry point for apps.tools.analyze_project."""
from __future__ import annotations

import importlib
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
for _path in (_ROOT, _ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

_implementation = importlib.import_module("apps.tools.analyze_project")
if __name__ == "__main__":
    raise SystemExit(_implementation.main())
sys.modules[__name__] = _implementation


def __getattr__(name: str):
    return getattr(_implementation, name)
