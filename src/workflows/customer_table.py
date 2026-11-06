"""Compatibility redirect for workflows.customer_management.table."""
from __future__ import annotations

import sys
from .customer_management import table as _target

sys.modules[__name__] = _target
