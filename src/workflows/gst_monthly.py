"""Compatibility redirect for workflows.gst.monthly."""
from __future__ import annotations

import sys
from .gst import monthly as _target

sys.modules[__name__] = _target
