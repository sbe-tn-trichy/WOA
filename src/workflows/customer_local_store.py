"""Compatibility redirect for workflows.customer_management.local_store."""
from __future__ import annotations

import sys
from .customer_management import local_store as _target

sys.modules[__name__] = _target
