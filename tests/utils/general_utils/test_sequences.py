"""Unit tests for sequence parsing and UTC timestamp utilities."""
from __future__ import annotations

from datetime import datetime, timezone
import pytest

from utils import numeric_affixes, utc_now_iso
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



def test_numeric_affixes_suffix_and_prefix() -> None:
    assert numeric_affixes("CHQ 00123456 / 20261108", 4) == {"3456", "1108"}
    assert numeric_affixes("CHQ 00123456 / 20261108", 4, is_prefix=True) == {"0012", "2026"}
    assert numeric_affixes("123 4567", 4) == {"4567"}
    assert numeric_affixes(None, 4) == set()
    assert numeric_affixes("no digits here", 4) == set()


def test_numeric_affixes_invalid_length() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        numeric_affixes("12345", 0)


def test_utc_now_iso_returns_utc_isoformat() -> None:
    parsed = datetime.fromisoformat(utc_now_iso())
    assert parsed.tzinfo == timezone.utc
