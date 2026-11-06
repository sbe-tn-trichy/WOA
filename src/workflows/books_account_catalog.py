"""Compatibility redirect for workflows.books_statements.account_catalog."""
from __future__ import annotations

import sys
from .books_statements import account_catalog as _target

sys.modules[__name__] = _target
