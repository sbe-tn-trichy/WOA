"""Compatibility redirect for workflows.customer_management.invoice_payment_review."""
from __future__ import annotations

import sys
from .customer_management import invoice_payment_review as _target

sys.modules[__name__] = _target
