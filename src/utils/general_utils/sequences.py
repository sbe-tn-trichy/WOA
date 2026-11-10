"""Generic document-number and numeric-run parsing shared across layers."""

from __future__ import annotations

import re


def parse_doc_number(doc_no: str) -> tuple[str, int, int]:
    """Return prefix, trailing integer and observed width; width zero means no suffix."""
    value = str(doc_no or "").strip()
    match = re.fullmatch(r"(.*?)(\d+)", value)
    if not match:
        return value, 0, 0
    prefix, suffix = match.groups()
    return prefix, int(suffix), len(suffix)


def numeric_affixes(
    value: object,
    length: int = 4,
    is_prefix: bool = False,
) -> set[str]:
    """Return the first or last ``length`` digits of each numeric run in ``value``."""
    if length < 1:
        raise ValueError("Affix length must be at least 1.")
    text = "" if value is None else str(value).strip()
    if not text:
        return set()
    return {
        digits[:length] if is_prefix else digits[-length:]
        for digits in re.findall(r"\d+", text)
        if len(digits) >= length
    }


__all__ = ["numeric_affixes", "parse_doc_number"]
