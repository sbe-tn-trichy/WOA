"""General utilities including character encoding, timestamps, and sequence parsing."""

from __future__ import annotations

from . import dates, encoding, module_aliases, sequences
from .dates import utc_now_iso
from .encoding import detect_encoding
from .module_aliases import register_module_aliases
from .sequences import numeric_affixes, parse_doc_number

__all__ = [
    "dates",
    "detect_encoding",
    "encoding",
    "module_aliases",
    "numeric_affixes",
    "parse_doc_number",
    "register_module_aliases",
    "sequences",
    "utc_now_iso",
]
