import json

import pytest
import requests

from zoho.base_client import BaseZohoClient
from zoho.exceptions import ZohoBooksError, ZohoError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ZOHO_DISABLE_FILE_LOGGING", "true")
    with BaseZohoClient("token", "in", "https://example.invalid", "books") as client:
        yield client


@pytest.mark.parametrize(("payload", "code", "message"), [
    ({"code": 0, "error_code": 123, "message": "Primary"}, 0, "Primary"),
    ({"error_code": 123, "description": "Description"}, 123, "Description"),
    ({"code": None, "error_code": 123, "error_message": "Alternate"}, 123, "Alternate"),
    ({"message": "No code"}, None, "No code"),
    (["Unexpected shape"], None, "Unexpected shape"),
])
def test_error_details(client, payload, code, message):
    response = requests.Response()
    response.status_code = 400
    response._content = json.dumps(payload).encode()
    response.headers["Retry-After"] = "12"

    with pytest.raises(ZohoBooksError) as caught:
        client._raise_for_status(response, endpoint="invoices")

    error = caught.value
    assert error.error_code == code
    assert error.response_data == payload
    assert error.status_code == 400
    assert error.endpoint == "invoices"
    assert error.retry_after == "12"
    assert message in str(error)
    assert str(error).startswith("HTTP Error:" if code is None else "API Error")


def test_invalid_json_uses_text_and_generic_service_error(client):
    client.service_name = "unknown"
    response = requests.Response()
    response.status_code = 502
    response._content = b"Upstream unavailable"
    with pytest.raises(ZohoError) as caught:
        client._raise_for_status(response)
    assert type(caught.value) is ZohoError
    assert caught.value.response_data is None
    assert "Upstream unavailable" in str(caught.value)


def test_success_does_not_parse_body(client, monkeypatch):
    response = requests.Response()
    response.status_code = 204

    def unexpected_parse():
        pytest.fail("Successful response should not be parsed for errors")

    monkeypatch.setattr(response, "json", unexpected_parse)
    assert client._raise_for_status(response) is None


@pytest.mark.parametrize(("status", "body", "expected"), [
    (429, b"invalid json", True),
    (200, b'{"code": 44}', False),
    (400, b'{"code": 44}', True),
    (403, b'{"code": 429}', True),
    (400, b'{"message": "Maximum Number Of Requests reached"}', True),
    (400, b'{"code": 12}', False),
    (500, b"invalid json", False),
    (400, b"[]", False),
    (400, b"null", False),
])
def test_rate_limit_detection(client, status, body, expected):
    response = requests.Response()
    response.status_code = status
    response._content = body
    assert client._is_rate_limited(response) is expected


def test_rate_limit_detection_propagates_unexpected_error(client, monkeypatch):
    response = requests.Response()
    response.status_code = 400

    def broken_decoder():
        raise RuntimeError("Unexpected decoder failure")

    monkeypatch.setattr(response, "json", broken_decoder)
    with pytest.raises(RuntimeError, match="Unexpected decoder failure"):
        client._is_rate_limited(response)
