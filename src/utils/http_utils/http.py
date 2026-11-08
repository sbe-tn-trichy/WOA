"""Reusable HTTP transport, session, retry, and streaming download utilities."""
from __future__ import annotations

import collections.abc
import os
from collections.abc import Iterator, Mapping, Sequence
from typing import Protocol, cast, runtime_checkable
from urllib.parse import urlsplit

from . import http_transport
from ..file_utils import json

DEFAULT_TIMEOUT: float = 30.0
DEFAULT_RETRY_AFTER: int = 12
MAX_RETRY_AFTER: int = 60


@runtime_checkable
class SeekableStream(Protocol):
    """Protocol for upload streams supporting tell/seek replay across retries."""

    def read(self, size: int = ...) -> bytes: ...
    def tell(self) -> int: ...
    def seek(self, offset: int) -> int: ...


class _HttpMethodCallable(Protocol):
    def __call__(self, url: str, **kwargs: object) -> http_transport.Response: ...


class _HttpRequestCallable(Protocol):
    def __call__(
        self, method: str, url: str, **kwargs: object
    ) -> http_transport.Response: ...


class _ChunkIterable(Protocol):
    def __call__(self, *, chunk_size: int = ...) -> Iterator[bytes]: ...


def is_json_content_type(content_type: str) -> bool:
    """Return True if ``content_type`` indicates a JSON media type."""
    media_type = content_type.split(";", 1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def is_html_body(text: str) -> bool:
    """Return True if ``text`` looks like an HTML document/error page."""
    lowered = text.strip().lower()
    return "<html" in lowered or "<!doctype" in lowered


def sanitize_error_text(
    text: str | None,
    status_code: int,
    reason: str | None = None,
) -> str:
    """Format a safe fallback error message without leaking raw HTML pages."""
    raw_text = (text or "").strip()
    if is_html_body(raw_text):
        return f"HTTP {status_code} ({reason or 'Server Error'})"
    return raw_text or f"HTTP {status_code}"


def extract_retry_after(headers: object) -> str | None:
    """Return the raw ``Retry-After`` header value when ``headers`` is a mapping."""
    if isinstance(headers, collections.abc.Mapping):
        value = headers.get("Retry-After")
        return str(value) if value is not None else None
    return None


def parse_retry_after(
    headers: object,
    default: int = DEFAULT_RETRY_AFTER,
    maximum: int = MAX_RETRY_AFTER,
) -> int:
    """Parse ``Retry-After`` into a bounded delay in ``[0, maximum]`` seconds."""
    header_val = extract_retry_after(headers)
    if header_val:
        try:
            return max(0, min(int(header_val), maximum))
        except Exception:
            pass
    return default


def validate_https_override_url(
    override_url: str,
    allowed_hosts: collections.abc.Set[str | None] | Sequence[str | None],
    *,
    error_message: str = "Override URL must use an approved HTTPS Zoho host.",
) -> None:
    """Ensure ``override_url`` uses HTTPS on port 443 without credentials on an allowed host."""
    target = urlsplit(override_url)
    if (
        target.scheme != "https"
        or target.hostname not in allowed_hosts
        or target.port not in (None, 443)
        or target.username is not None
        or target.password is not None
    ):
        raise ValueError(error_message)


def capture_upload_positions(
    files: Mapping[str, object] | None,
) -> list[tuple[SeekableStream, int]]:
    """Record current seek positions of upload streams; reject non-seekable streams."""
    positions: list[tuple[SeekableStream, int]] = []
    for value in (files or {}).values():
        body: object = (
            value[1]
            if isinstance(value, (tuple, list)) and len(value) > 1
            else value
        )
        if hasattr(body, "read"):
            tell_fn = getattr(body, "tell", None)
            seek_fn = getattr(body, "seek", None)
            if not callable(tell_fn) or not callable(seek_fn):
                raise ValueError(
                    "Upload streams must be seekable for safe retries."
                )
            try:
                position = int(tell_fn())
                seek_fn(position)
            except (AttributeError, OSError, TypeError, ValueError) as exc:
                raise ValueError(
                    "Upload streams must be seekable for safe retries."
                ) from exc
            if not isinstance(body, SeekableStream):
                raise ValueError("Upload streams must be seekable for safe retries.")
            positions.append((body, position))
    return positions


def rewind_uploads(positions: Sequence[tuple[SeekableStream, int]]) -> None:
    """Restore recorded seek positions before retrying an upload request."""
    for body, position in positions:
        body.seek(position)


def filter_request_kwargs(
    kwargs: Mapping[str, object],
    *,
    keep_none_keys: collections.abc.Set[str] = frozenset(),
) -> dict[str, object]:
    """Copy request kwargs, dropping ``url``/``method`` and unrequested ``None`` entries."""
    filtered = dict(kwargs)
    filtered.pop("url", None)
    filtered.pop("method", None)
    for key in list(filtered.keys()):
        if filtered[key] is None and key not in keep_none_keys:
            filtered.pop(key)
    return filtered


def send_http_request(
    method: str,
    url: str,
    *,
    session: http_transport.Session | None = None,
    **kwargs: object,
) -> http_transport.Response:
    """Execute through an explicit session or the shared pyqwest transport."""
    dispatcher = session.request if session is not None else http_transport.request
    return cast(_HttpRequestCallable, dispatcher)(method=method, url=url, **kwargs)


def unwrap_json_body(payload: object) -> object:
    """Unwrap a payload dictionary or stringified JSON body from a gateway envelope."""
    if isinstance(payload, collections.abc.Mapping):
        body = payload.get("body", payload)
        if isinstance(body, str):
            body = json.loads(body)
        return body
    return payload


def get_json_value(
    payload: object,
    *keys: str | int,
    default: object = None,
    required: bool = False,
    unwrap_body: bool = True,
) -> object:
    """Extract a specific nested value by key or path from a JSON object.

    If ``unwrap_body`` is True and ``payload`` contains a wrapped ``body`` (common
    in serverless/gateway responses), it unwraps the inner JSON payload first.
    """
    current = unwrap_json_body(payload) if unwrap_body else payload
    for key in keys:
        if isinstance(current, collections.abc.Mapping):
            if key in current:
                current = current[key]
            elif required:
                raise KeyError(f"Key {key!r} not found in JSON payload")
            else:
                return default
        elif isinstance(current, (list, tuple)) and isinstance(key, int):
            if -len(current) <= key < len(current):
                current = current[key]
            elif required:
                raise IndexError(f"Index {key} out of range for JSON array")
            else:
                return default
        else:
            if required:
                raise TypeError(
                    f"Cannot traverse key {key!r} on non-container {type(current).__name__}"
                )
            return default
    return current


def request_json(
    method: str,
    url: str,
    *,
    session: object = http_transport,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, object] | None = None,
    json: object = None,
    data: object = None,
    timeout: float = DEFAULT_TIMEOUT,
    key: str | int | None = None,
    unwrap_body: bool = False,
) -> object:
    """Send an HTTP request using ``session``, raise for HTTP status, and decode JSON."""
    method_upper = method.upper()
    call_kwargs: dict[str, object] = {"timeout": timeout}
    if headers is not None:
        call_kwargs["headers"] = headers
    if params is not None:
        call_kwargs["params"] = params
    if json is not None:
        call_kwargs["json"] = json
    if data is not None:
        call_kwargs["data"] = data

    dispatcher: _HttpMethodCallable | None = getattr(
        session, method_upper.lower(), None
    )
    if callable(dispatcher):
        response = dispatcher(url, **call_kwargs)
    else:
        request_fn: _HttpRequestCallable | None = getattr(session, "request", None)
        if not callable(request_fn):
            raise TypeError(f"Session {session!r} has no request method")
        response = request_fn(method_upper, url, **call_kwargs)
    response.raise_for_status()
    result: object = response.json()
    if key is not None:
        return get_json_value(result, key, unwrap_body=unwrap_body)
    return unwrap_json_body(result) if unwrap_body else result


def decode_response(response: http_transport.Response) -> object:
    """Decode a non-streamed HTTP response into JSON, raw bytes, or ``{}`` for empty bodies."""
    if response.status_code == 204 or not response.text:
        return {}
    content_type = ""
    if hasattr(response, "headers") and isinstance(
        response.headers, collections.abc.Mapping
    ):
        raw_ct = response.headers.get("Content-Type", "")
        content_type = str(raw_ct) if raw_ct is not None else ""
    if content_type and not is_json_content_type(content_type):
        return response.content
    result: object = response.json()
    return result


def write_response_to_file(
    response: object,
    destination: str,
    chunk_size: int = 8192,
) -> str:
    """Write bytes or a streaming HTTP response to ``destination`` and close it."""
    close = getattr(response, "close", None)
    try:
        is_binary = isinstance(response, (bytes, bytearray))
        iter_content: _ChunkIterable | None = getattr(
            response, "iter_content", None
        )
        content = None if callable(iter_content) else getattr(response, "content", None)
        if (
            not is_binary
            and not callable(iter_content)
            and not isinstance(content, (bytes, bytearray))
        ):
            raise TypeError(
                "Download response must be bytes or provide binary content."
            )

        parent = os.path.dirname(destination)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(destination, "wb") as output:
            if isinstance(response, (bytes, bytearray)):
                output.write(response)
                return destination

            if callable(iter_content):
                for chunk in iter_content(chunk_size=chunk_size):
                    if chunk:
                        output.write(chunk)
                return destination

            if isinstance(content, (bytes, bytearray)):
                output.write(content)
            return destination
    finally:
        if callable(close):
            close()


__all__ = [
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
