from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
_APPS = _ROOT / "apps"
for _p in (str(_SRC), str(_ROOT), str(_APPS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
