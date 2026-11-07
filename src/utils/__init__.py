"""Shared cross-service utility modules."""
from __future__ import annotations

from .encoding import detect_encoding
from .http import (
    DEFAULT_RETRY_AFTER,
    DEFAULT_TIMEOUT,
    MAX_RETRY_AFTER,
    SeekableStream,
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
from .http_transport import HTTPError, RequestOptions, Response, Session, TransportError
from .json import JSONDecodeError, dump, dumps, load, loads
from .yaml import YAMLError, safe_dump, safe_load

__all__ = [
    "JSONDecodeError",
    "dump",
    "dumps",
    "load",
    "loads",
    "HTTPError",
    "RequestOptions",
    "Response",
    "Session",
    "TransportError",
    "YAMLError",
    "detect_encoding",
    "safe_dump",
    "safe_load",
    "read_pdf_pages",
    "DEFAULT_RETRY_AFTER",
    "DEFAULT_TIMEOUT",
    "MAX_RETRY_AFTER",
    "SeekableStream",
    "capture_upload_positions",
    "decode_response",
    "extract_retry_after",
    "filter_request_kwargs",
    "get_json_value",
    "is_html_body",
    "is_json_content_type",
    "parse_retry_after",
    "request_json",
    "rewind_uploads",
    "sanitize_error_text",
    "send_http_request",
    "unwrap_json_body",
    "validate_https_override_url",
    "write_response_to_file",
]


def __getattr__(name: str):
    if name == "read_pdf_pages":
        # PDF support belongs to the optional workflows extra.
        from .pdf import read_pdf_pages
        return read_pdf_pages
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
