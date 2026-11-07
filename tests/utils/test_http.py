"""Unit tests for the shared HTTP utility layer in ``utils.http``."""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests

import utils
from utils.http import (
    DEFAULT_RETRY_AFTER,
    MAX_RETRY_AFTER,
    capture_upload_positions,
    decode_response,
    extract_retry_after,
    filter_request_kwargs,
    get_json_value,
    is_html_body,
    is_json_content_type,
    parse_retry_after,
    request_json,
    rewind_uploads,
    sanitize_error_text,
    send_http_request,
    unwrap_json_body,
    validate_https_override_url,
    write_response_to_file,
)


def test_public_exports_match_package_root() -> None:
    for symbol in utils.http.__all__:
        assert hasattr(utils, symbol)
        assert getattr(utils, symbol) is getattr(utils.http, symbol)


@pytest.mark.parametrize(
    "content_type,expected",
    [
        ("application/json", True),
        ("application/json; charset=utf-8", True),
        ("application/vnd.api+json", True),
        ("text/html; charset=utf-8", False),
        ("application/octet-stream", False),
        ("", False),
    ],
)
def test_is_json_content_type(content_type: str, expected: bool) -> None:
    assert is_json_content_type(content_type) is expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("<html><body>Error</body></html>", True),
        ("<!DOCTYPE html><html></html>", True),
        ('{"code": 400, "message": "Bad Request"}', False),
        ("", False),
    ],
)
def test_is_html_body_and_sanitize_error_text(text: str, expected: bool) -> None:
    assert is_html_body(text) is expected
    sanitized = sanitize_error_text(text, 502, "Bad Gateway")
    if expected:
        assert sanitized == "HTTP 502 (Bad Gateway)"
    elif text:
        assert sanitized == text
    else:
        assert sanitized == "HTTP 502"


@pytest.mark.parametrize(
    "headers,raw_expected,bounded_expected",
    [
        ({"Retry-After": "15"}, "15", 15),
        ({"Retry-After": "-5"}, "-5", 0),
        ({"Retry-After": "999"}, "999", MAX_RETRY_AFTER),
        ({"Retry-After": "invalid"}, "invalid", DEFAULT_RETRY_AFTER),
        ({}, None, DEFAULT_RETRY_AFTER),
        (None, None, DEFAULT_RETRY_AFTER),
    ],
)
def test_extract_and_parse_retry_after(
    headers: object, raw_expected: str | None, bounded_expected: int
) -> None:
    assert extract_retry_after(headers) == raw_expected
    assert parse_retry_after(headers) == bounded_expected


@pytest.mark.parametrize(
    "url,valid",
    [
        ("https://www.zohoapis.in/books/v3/invoices", True),
        ("https://download.zoho.in/v1/workdrive/download/1", True),
        ("http://www.zohoapis.in/books/v3/invoices", False),
        ("https://evil.example/books", False),
        ("https://www.zohoapis.in:8443/books", False),
        ("https://user:pass@www.zohoapis.in/books", False),
    ],
)
def test_validate_https_override_url(url: str, valid: bool) -> None:
    allowed = {"www.zohoapis.in", "download.zoho.in"}
    if valid:
        validate_https_override_url(url, allowed)
    else:
        with pytest.raises(ValueError, match="approved HTTPS Zoho host"):
            validate_https_override_url(url, allowed)


def test_capture_and_rewind_upload_positions() -> None:
    stream = io.BytesIO(b"prefix:payload")
    stream.seek(7)
    positions = capture_upload_positions(
        {"file": ("doc.txt", stream), "raw": b"bytes"}
    )
    assert len(positions) == 1
    assert stream.read() == b"payload"
    rewind_uploads(positions)
    assert stream.tell() == 7
    assert stream.read() == b"payload"


def test_capture_upload_positions_rejects_nonseekable_stream() -> None:
    class Unseekable:
        def read(self, size: int = -1) -> bytes:
            return b"data"

    with pytest.raises(ValueError, match="seekable"):
        capture_upload_positions({"file": Unseekable()})


def test_filter_request_kwargs_respects_keep_none_keys() -> None:
    raw = {
        "method": "GET",
        "url": "https://example.com",
        "params": None,
        "json": None,
        "data": None,
        "timeout": 10,
    }
    filtered = filter_request_kwargs(
        raw, keep_none_keys=frozenset({"json"})
    )
    assert filtered == {"json": None, "timeout": 10}


def test_send_http_request_uses_explicit_or_default_session() -> None:
    session = MagicMock(spec=requests.Session)
    session_resp = MagicMock(spec=requests.Response)
    session.request.return_value = session_resp

    assert (
        send_http_request("GET", "https://example.com", session=session, timeout=5)
        is session_resp
    )
    session.request.assert_called_once_with(
        method="GET", url="https://example.com", timeout=5
    )

    with patch("utils.http_transport.Session.request") as mock_req:
        mock_resp = MagicMock(spec=requests.Response)
        mock_req.return_value = mock_resp
        assert (
            send_http_request("POST", "https://example.com", timeout=5)
            is mock_resp
        )
        mock_req.assert_called_once_with(
            method="POST", url="https://example.com", timeout=5
        )


def test_request_json_dispatches_method_and_fallback_request() -> None:
    session = Mock()
    session.get.return_value.json.return_value = {"ok": True}
    assert request_json(
        "GET",
        "https://example.com/api",
        session=session,
        headers={"Authorization": "Bearer tok"},
        params={"q": "1"},
        timeout=15,
    ) == {"ok": True}
    session.get.assert_called_once_with(
        "https://example.com/api",
        headers={"Authorization": "Bearer tok"},
        params={"q": "1"},
        timeout=15,
    )
    session.get.return_value.raise_for_status.assert_called_once_with()

    class RequestOnlySession:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, dict[str, object]]] = []

        def request(self, method: str, url: str, **kwargs: object) -> Mock:
            self.calls.append((method, url, kwargs))
            resp = Mock()
            resp.json.return_value = {"custom": True}
            return resp

    req_only = RequestOnlySession()
    assert request_json("PATCH", "https://example.com/item", session=req_only, json={"a": 1}) == {
        "custom": True
    }
    assert req_only.calls == [
        ("PATCH", "https://example.com/item", {"timeout": 30.0, "json": {"a": 1}})
    ]

    # Test key extraction and unwrap_body
    envelope_session = Mock()
    envelope_session.get.return_value.json.return_value = {
        "body": '{"data": {"token": "secret123"}}'
    }
    extracted = request_json(
        "GET",
        "https://example.com/wrapped",
        session=envelope_session,
        key="data",
        unwrap_body=True,
    )
    assert extracted == {"token": "secret123"}


def test_unwrap_json_body() -> None:
    assert unwrap_json_body({"body": '{"key": "val"}'}) == {"key": "val"}
    assert unwrap_json_body({"body": {"key": "val"}}) == {"key": "val"}
    assert unwrap_json_body({"direct": 123}) == {"direct": 123}
    assert unwrap_json_body([1, 2, 3]) == [1, 2, 3]


def test_get_json_value_nested_and_indexing() -> None:
    payload = {
        "body": {
            "users": [
                {"id": 101, "name": "Alice"},
                {"id": 102, "name": "Bob"},
            ],
            "meta": {"total": 2},
        }
    }
    assert get_json_value(payload, "users", 1, "name") == "Bob"
    assert get_json_value(payload, "meta", "total") == 2
    assert get_json_value(payload, "missing", default="fallback") == "fallback"
    assert get_json_value(payload, "users", 99, default=None) is None

    with pytest.raises(KeyError, match="missing"):
        get_json_value(payload, "missing", required=True)

    with pytest.raises(IndexError, match="5"):
        get_json_value(payload, "users", 5, required=True)

    with pytest.raises(TypeError, match="Cannot traverse key"):
        get_json_value(payload, "meta", "total", "leaf", required=True)


def test_decode_response_variants() -> None:
    empty = MagicMock(status_code=204, text="", headers={})
    assert decode_response(empty) == {}

    json_resp = MagicMock(
        status_code=200,
        text='{"a": 1}',
        headers={"Content-Type": "application/json"},
    )
    json_resp.json.return_value = {"a": 1}
    assert decode_response(json_resp) == {"a": 1}

    binary_resp = MagicMock(
        status_code=200,
        text="binary",
        content=b"\x00\x01",
        headers={"Content-Type": "application/pdf"},
    )
    assert decode_response(binary_resp) == b"\x00\x01"


def test_write_response_to_file_bytes_and_chunks(tmp_path: Path) -> None:
    dest_bytes = tmp_path / "sub" / "raw.bin"
    assert write_response_to_file(b"hello", str(dest_bytes)) == str(dest_bytes)
    assert dest_bytes.read_bytes() == b"hello"

    stream_resp = MagicMock()
    stream_resp.iter_content.return_value = [b"part1-", b"", b"part2"]
    dest_stream = tmp_path / "stream.bin"
    assert write_response_to_file(stream_resp, str(dest_stream), chunk_size=4) == str(
        dest_stream
    )
    assert dest_stream.read_bytes() == b"part1-part2"
    stream_resp.close.assert_called_once_with()
