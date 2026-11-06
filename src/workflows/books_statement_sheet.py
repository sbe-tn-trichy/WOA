"""Compatibility redirect for workflows.books_statements.statement_sheet."""
from __future__ import annotations

import sys
from .books_statements import statement_sheet as _target

sys.modules[__name__] = _target
