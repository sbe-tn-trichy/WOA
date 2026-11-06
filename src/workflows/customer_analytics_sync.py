"""Compatibility redirect for workflows.customer_management.analytics_sync."""
from __future__ import annotations

import sys
from .customer_management import analytics_sync as _target

sys.modules[__name__] = _target
