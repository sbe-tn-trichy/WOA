"""Compatibility redirect for workflows.books_statements.custom_module_store."""
from __future__ import annotations

import sys
from .books_statements import custom_module_store as _target

sys.modules[__name__] = _target
