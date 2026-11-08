"""General utilities including character encoding and sequence parsing."""

from __future__ import annotations

from . import encoding, module_aliases, sequences
from .encoding import detect_encoding
from .module_aliases import register_module_aliases
from .sequences import parse_doc_number
from .module_aliases import register_module_aliases

__all__ = [
    "register_module_aliases",
    "detect_encoding",
    "parse_doc_number",
    "register_module_aliases",
    "encoding",
    "module_aliases",
    "sequences",
]
