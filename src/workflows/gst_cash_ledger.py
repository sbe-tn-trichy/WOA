"""Compatibility redirect for workflows.gst.cash_ledger."""
from __future__ import annotations

import sys
from .gst import cash_ledger as _target

sys.modules[__name__] = _target
