"""Unit tests for sequence parsing utilities."""
from __future__ import annotations

from utils.general_utils.sequences import parse_doc_number


def test_parse_doc_number_with_prefix_and_numeric_suffix() -> None:
    prefix, num, width = parse_doc_number("INV-00123")
    assert prefix == "INV-"
    assert num == 123
    assert width == 5


def test_parse_doc_number_without_suffix() -> None:
    prefix, num, width = parse_doc_number("INV-PREFIX")
    assert prefix == "INV-PREFIX"
    assert num == 0
    assert width == 0


def test_parse_doc_number_empty_or_none() -> None:
    prefix, num, width = parse_doc_number("")
    assert prefix == ""
    assert num == 0
    assert width == 0

    prefix, num, width = parse_doc_number(None)  # type: ignore[arg-type]
    assert prefix == ""
    assert num == 0
    assert width == 0


def test_parse_doc_number_pure_digits() -> None:
    prefix, num, width = parse_doc_number("00042")
    assert prefix == ""
    assert num == 42
    assert width == 5
