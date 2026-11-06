"""Compatibility redirect for workflows.books_statements.pnl_notes."""
from __future__ import annotations

import sys
from .books_statements import pnl_notes as _target

sys.modules[__name__] = _target
