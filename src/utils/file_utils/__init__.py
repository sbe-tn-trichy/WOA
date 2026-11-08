"""File and document serialization utilities (JSON, YAML, PDF)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from . import json, yaml
from .json import JSONDecodeError, dump, dumps, load, loads
from .yaml import YAMLError, safe_dump, safe_load

if TYPE_CHECKING:
    from . import pdf
    from .pdf import read_pdf_pages

__all__ = [
    "JSONDecodeError",
    "dump",
    "dumps",
    "load",
    "loads",
    "YAMLError",
    "safe_dump",
    "safe_load",
    "read_pdf_pages",
    "json",
    "yaml",
    "pdf",
]


def __getattr__(name: str):
    if name in ("pdf", "read_pdf_pages"):
        import importlib
        pdf_module = importlib.import_module(".pdf", __package__)
        globals()["pdf"] = pdf_module
        if name == "read_pdf_pages":
            return pdf_module.read_pdf_pages
        return pdf_module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
