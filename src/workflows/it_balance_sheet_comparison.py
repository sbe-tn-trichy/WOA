"""Compatibility redirect for workflows.books_statements.it_balance_sheet_comparison."""
from __future__ import annotations

import sys
from .books_statements import it_balance_sheet_comparison as _target

sys.modules[__name__] = _target
