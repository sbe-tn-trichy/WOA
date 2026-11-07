"""Exercise the Rust HTTP transport against a local server, without external APIs."""
import io
import json
import threading
import time
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import pytest

from utils import http_transport
from utils.http import write_response_to_file
from zoho.base_client import BaseZohoClient


@pytest.fixture
def server():
    records = []
    replies = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = bytearray()
            if self.headers.get("Transfer-Encoding") == "chunked":
                while size := int(self.rfile.readline().split(b";", 1)[0], 16):
                    body.extend(self.rfile.read(size))
                    self.rfile.read(2)
                self.rfile.readline()
            else:
                body.extend(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            records.append((self.path, dict(self.headers), bytes(body)))
            status, headers, content = replies.pop(0) if replies else (200, {}, b'{}')
            if self.path.startswith("/slow"):
                time.sleep(0.1)
            self.send_response(status)
            for key, value in {"Content-Length": str(len(content)), **headers}.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError):
                return

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", records, replies
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


@pytest.fixture
def session():
    client = http_transport.Session()
    try:
        yield client
    finally:
        client.close()


def test_form_query_and_json_encoding(server, session):
    base, records, replies = server
    replies.append((200, {"content-type": "application/json", "retry-after": "3"}, b'{"ok":true}'))
    response = session.request("POST", base + "/?existing=1#fragment",
                               params={"key": ["a b", "c"], "skip": None},
                               data={"flag": True, "skip": None, "key": [1, 2]})
    path, headers, body = records[0]
    assert parse_qs(urlsplit(path).query) == {"existing": ["1"], "key": ["a b", "c"]}
    assert parse_qs(body.decode()) == {"flag": ["True"], "key": ["1", "2"]}
    assert headers["content-type"] == "application/x-www-form-urlencoded"
    assert response.json() == {"ok": True}
    assert response.headers.get("Retry-After") == "3"
    session.request("POST", base, json={"values": [None, "தமிழ்"]}, data={})
    assert json.loads(records[1][2]) == {"values": [None, "தமிழ்"]}


@pytest.mark.parametrize("status", [401, 429])
@pytest.mark.parametrize("wrapped", [False, True])
def test_native_multipart_retry_replays_nonzero_stream(server, monkeypatch, status, wrapped):
    base, records, replies = server
    replies.extend([(status, {"Retry-After": "0"}, b'{}'), (200, {}, b'{}')])
    source = io.BytesIO(b"prefix:actual attachment bytes")
    source.seek(7)
    monkeypatch.setenv("ZOHO_DISABLE_FILE_LOGGING", "true")
    with BaseZohoClient("old", "in", base, "books", token_refresh_callback=lambda: "new") as client:
        client.request("POST", "upload", data={"field": "value"},
                       files={"file": ("x.bin", source, "application/octet-stream") if wrapped else source})
    assert len(records) == 2
    for _, headers, body in records:
        assert int(headers["content-length"]) == len(body)
        assert "transfer-encoding" not in headers
        parsed = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: " + headers["content-type"].encode() + b"\r\n\r\n" + body)
        assert [part.get_payload(decode=True) for part in parsed.iter_parts()] == [b"value", b"actual attachment bytes"]
    assert records[-1][1]["authorization"] == "Zoho-oauthtoken " + ("new" if status == 401 else "old")
    assert not source.closed


def test_binary_stream_download_does_not_buffer(server, session, tmp_path):
    base, _, replies = server
    payload = bytes(range(256)) * 4096
    replies.append((200, {"Content-Type": "application/octet-stream"}, payload))
    response = session.request("GET", base, stream=True)
    assert response._content is None
    destination = tmp_path / "download.bin"
    write_response_to_file(response, str(destination), chunk_size=4096)
    assert destination.read_bytes() == payload
    assert response._content is None


def test_http_error_invalid_json_and_native_timeout(server, session):
    base, _, replies = server
    replies.append((403, {}, b"not json"))
    response = session.request("GET", base)
    with pytest.raises(http_transport.HTTPError, match="403"):
        response.raise_for_status()
    with pytest.raises(ValueError):
        response.json()
    with pytest.raises(http_transport.TransportError):
        session.request("GET", base + "/slow", timeout=(1, 0.01))


def test_closed_session_fails_before_network(session):
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        session.request("GET", "http://invalid.test")


def test_redirect_drops_authorization_for_different_host(server, session):
    base, records, replies = server
    target = base.replace("127.0.0.1", "localhost") + "/target"
    replies.append((302, {"Location": target}, b""))
    assert session.request("GET", base, headers={"Authorization": "Bearer secret"}).status_code == 200
    assert len(records) == 2
    assert records[0][1]["authorization"] == "Bearer secret"
    assert "authorization" not in records[1][1]


def test_interrupted_stream_fails_instead_of_reporting_success(server, session, tmp_path, monkeypatch):
    base, _, replies = server
    replies.append((200, {"Content-Length": "9999"}, b"truncated"))
    response = session.request("GET", base, stream=True)
    from unittest.mock import Mock
    close = Mock(wraps=response.close)
    monkeypatch.setattr(response, "close", close)
    with pytest.raises(http_transport.TransportError):
        write_response_to_file(response, str(tmp_path / "download.bin"))
    close.assert_called()


def test_json_nan_and_invalid_timeouts_fail_before_network(session):
    with pytest.raises(ValueError):
        session.request("POST", "http://invalid.test", json={"amount": float("nan")})
    with pytest.raises(ValueError, match="timeout"):
        session.request("GET", "http://invalid.test", timeout=0)


def test_default_helpers_do_not_persist_cookies(server):
    base, records, replies = server
    replies.append((200, {"Set-Cookie": "session=secret; Path=/"}, b'{}'))
    http_transport.get(base)
    http_transport.get(base)
    assert "cookie" not in records[-1][1]


def test_explicit_session_persists_cookies(server, session):
    base, records, replies = server
    replies.append((200, {"Set-Cookie": "session=value; Path=/"}, b'{}'))
    session.request("GET", base)
    session.request("GET", base)
    assert records[-1][1]["cookie"] == "session=value"
