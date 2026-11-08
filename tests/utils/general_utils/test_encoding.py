"""Unit tests for character encoding detection utilities."""
from __future__ import annotations

from utils.general_utils.encoding import detect_encoding


def test_detect_encoding_empty() -> None:
    assert detect_encoding(b"") == "utf-8"
    assert detect_encoding(b"", fallback="latin1") == "latin1"


def test_detect_encoding_utf8() -> None:
    data = "Hello, world! © 2026".encode("utf-8")
    result = detect_encoding(data)
    assert isinstance(result, str)
    assert result in ("utf-8", "windows-1252", "iso-8859-1")
