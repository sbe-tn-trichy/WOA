"""Synchronous pyqwest transport for the project's HTTP request conventions."""
from __future__ import annotations

import atexit
import os
import threading
from collections.abc import Iterator, Mapping
from email.message import Message
from http import HTTPStatus
from pathlib import Path
from typing import Protocol, TypedDict, Unpack, runtime_checkable
from urllib.parse import urlencode, urlsplit, urlunsplit

import certifi
import pyqwest

from ..file_utils import json as json_module


class TransportError(Exception):
    """An HTTP connection, timeout, protocol or body-transfer failure."""


class HTTPError(TransportError):
    """An unsuccessful HTTP response."""


_NETWORK_ERRORS = (ConnectionError, TimeoutError, pyqwest.ReadError,
                   pyqwest.WriteError, pyqwest.RemoteProtocolError, pyqwest.TooManyRedirects)


class RequestOptions(TypedDict, total=False):
    headers: Mapping[str, str] | None
    params: object
    json: object
    data: object
    files: Mapping[str, object] | None
    stream: bool
    timeout: float | tuple[float | None, float | None] | None


class _Headers(Mapping[str, str]):
    def __init__(self, headers: pyqwest.Headers):
        self._headers = headers

    def __getitem__(self, key: str) -> str:
        return self._headers[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._headers)

    def __len__(self) -> int:
        return len(self._headers)


class Response:
    """Own a native response while exposing buffered and incremental reads."""

    def __init__(self, response: pyqwest.SyncResponse):
        self._response = response
        self._content: bytes | None = None
        self.status_code = response.status
        self.headers: Mapping[str, str] = _Headers(response.headers)
        self.reason = HTTPStatus(response.status).phrase if response.status in HTTPStatus else ""

    @property
    def content(self) -> bytes:
        if self._content is None:
            self._content = b"".join(self.iter_content())
        return self._content

    @property
    def text(self) -> str:
        message = Message()
        message["Content-Type"] = self.headers.get("Content-Type", "")
        encoding = message.get_content_charset() or "utf-8"
        try:
            return self.content.decode(encoding, errors="replace")
        except LookupError:
            return self.content.decode("utf-8", errors="replace")

    def json(self) -> object:
        return json_module.loads(self.content)

    def iter_content(self, chunk_size: int = 8192) -> Iterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        try:
            chunks = (self._content,) if self._content is not None else self._response.content
            for chunk in chunks:
                raw = bytes(chunk)
                for offset in range(0, len(raw), chunk_size):
                    yield raw[offset:offset + chunk_size]
        except _NETWORK_ERRORS as exc:
            raise TransportError("HTTP response body transfer failed") from exc
        finally:
            self.close()

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"HTTP {self.status_code}: {self.reason}")

    def close(self) -> None:
        self._response.close()


@runtime_checkable
class _Readable(Protocol):
    def read(self, size: int = ...) -> bytes: ...


def _body(value: object) -> bytes | Iterator[bytes]:
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, _Readable):
        return iter(lambda: value.read(65536), b"")
    raise TypeError("HTTP body must be bytes, text or a readable binary stream")


def _form_pairs(value: object) -> list[tuple[str, str | bytes]]:
    if not isinstance(value, Mapping):
        raise TypeError("HTTP parameters and form data must be mappings")
    pairs = []
    for key, values in value.items():
        for item in values if isinstance(values, (list, tuple)) else (values,):
            if item is not None:
                pairs.append((str(key), item if isinstance(item, bytes) else str(item)))
    return pairs


def _multipart(files: Mapping[str, object], data: object) -> pyqwest.SyncMultipart:
    parts: list[tuple[str, pyqwest.SyncPart | bytes | str]] = []
    if data:
        parts.extend(_form_pairs(data))
    for key, value in files.items():
        if value is None:
            continue
        filename = os.path.basename(str(getattr(value, "name", key)))
        headers: dict[str, str] = {}
        if isinstance(value, (tuple, list)):
            if not 2 <= len(value) <= 4:
                raise ValueError("File tuples require filename, body, optional content type and headers")
            filename, body = value[:2]
            if len(value) >= 3 and value[2]:
                headers["Content-Type"] = str(value[2])
            if len(value) == 4:
                if not isinstance(value[3], Mapping):
                    raise TypeError("File headers must be a mapping")
                headers.update({str(k): str(v) for k, v in value[3].items()})
        else:
            body = value
        parts.append((key, pyqwest.SyncPart(
            _body(body), filename=None if filename is None else str(filename), headers=headers.items(),
        )))
    return pyqwest.SyncMultipart(parts)


class Session:
    """Reuse native pools, with Requests-style connect/read inactivity timeouts."""

    def __init__(self, *, persist_cookies: bool = True) -> None:
        self._transports: dict[tuple[float | None, float | None], pyqwest.SyncHTTPTransport] = {}
        self._lock = threading.Lock()
        self._closed = False
        self._persist_cookies = persist_cookies

    def request(
        self, method: str, url: str, *, headers: Mapping[str, str] | None = None,
        params: object = None, json: object = None, data: object = None,
        files: Mapping[str, object] | None = None, stream: bool = False,
        timeout: float | tuple[float | None, float | None] | None = 30,
    ) -> Response:
        connect, read = timeout if isinstance(timeout, tuple) else (timeout, timeout)
        for value in (connect, read):
            if value is not None and value <= 0:
                raise ValueError("HTTP timeout must be positive or None")
        request_headers = pyqwest.Headers(headers.items() if headers is not None else None)
        content: bytes | Iterator[bytes] | pyqwest.SyncMultipart | None = None
        if files:
            content = _multipart(files, data)
        elif json is not None and not data:
            content = json_module.dumps(json, allow_nan=False).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        elif data is not None:
            if isinstance(data, Mapping):
                content = urlencode(_form_pairs(data)).encode("utf-8")
                request_headers.setdefault("Content-Type", "application/x-www-form-urlencoded")
            else:
                content = _body(data)
        if params:
            query = urlencode(_form_pairs(params))
            # Let the standard URL parser keep query parameters before fragments.
            parsed = urlsplit(url)
            url = urlunsplit(parsed._replace(query="&".join(filter(None, (parsed.query, query)))))
        with self._lock:
            if self._closed:
                raise RuntimeError("HTTP session is closed")
            transport = self._transports.get((connect, read))
            if transport is None:
                ca_path = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("CURL_CA_BUNDLE") or certifi.where()
                transport = pyqwest.SyncHTTPTransport(
                    tls_ca_cert=Path(ca_path).read_bytes(), connect_timeout=connect,
                    read_timeout=read, enable_cookie_store=self._persist_cookies, use_system_dns=True,
                    max_redirects=30,
                )
                self._transports[(connect, read)] = transport
        try:
            native_request = pyqwest.SyncRequest(
                method.upper(), url, headers=request_headers, content=content,
            )
            if files:
                # Requests buffered multipart bodies and sent Content-Length.
                # Keep that wire behavior for upload endpoints rejecting chunked bodies.
                encoded = native_request.content
                native_request = pyqwest.SyncRequest(
                    method.upper(), url, headers=native_request.headers,
                    content=encoded if isinstance(encoded, bytes) else b"".join(encoded),
                )
            response = Response(transport.execute_sync(native_request))
            if not stream:
                # Reading also closes the native response, retaining buffered bytes.
                _ = response.content
            return response
        except _NETWORK_ERRORS as exc:
            raise TransportError("HTTP request failed") from exc

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for transport in self._transports.values():
                transport.close()
            self._transports.clear()


_default_session = Session(persist_cookies=False)
atexit.register(_default_session.close)


def request(method: str, url: str, **kwargs: Unpack[RequestOptions]) -> Response:
    return _default_session.request(method=method, url=url, **kwargs)


def get(url: str, **kwargs: Unpack[RequestOptions]) -> Response:
    return request("GET", url, **kwargs)


def post(url: str, **kwargs: Unpack[RequestOptions]) -> Response:
    return request("POST", url, **kwargs)


__all__ = ["HTTPError", "RequestOptions", "Response", "Session", "TransportError", "get", "post", "request"]
