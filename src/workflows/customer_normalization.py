"""Compatibility redirect for workflows.customer_management.normalization."""
from __future__ import annotations

import sys
from .customer_management import normalization as _target

sys.modules[__name__] = _target
