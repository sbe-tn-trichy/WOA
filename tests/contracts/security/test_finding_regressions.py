"""Regression coverage for the shared transport and local HTTP boundary findings."""
import io
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock

import pytest
import requests

from apps import dashboard, payment_review
from workflows.runtime.auth import get_analytics_client
from zoho.core_sdk.base_client import BaseZohoClient


@pytest.mark.parametrize("status", [401, 429])
@pytest.mark.parametrize("wrapped", [False, True])
def test_upload_retry_preserves_multipart_content(monkeypatch, status, wrapped):
    client = BaseZohoClient("old", "in", "https://www.zohoapis.in", "books",
                            token_refresh_callback=lambda: "new")
    source = io.BytesIO(b"ignored:actual attachment bytes")
    source.seek(8)
    bodies = []

    def send(**kwargs):
        prepared = requests.Request(kwargs["method"], kwargs["url"], files=kwargs["files"]).prepare()
        # Multipart boundaries are random; compare the actual part bytes.
        bodies.append(prepared.body.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n--", 1)[0])
        response = requests.Response()
        response.status_code = status if len(bodies) == 1 else 200
        response._content = b'{}'
        response._content_consumed = True
        response.headers = {"Content-Type": "application/json", "Retry-After": "0"}
        return response

    monkeypatch.setattr(client.session, "request", send)
    monkeypatch.setattr("zoho.core_sdk.base_client.time.sleep", lambda _: None)
    client.request("POST", "upload", files={"file": ("x.bin", source) if wrapped else source})
    assert bodies == [b"actual attachment bytes"] * 2
    assert not source.closed
    client.close()


def test_nonseekable_upload_fails_before_network():
    class Stream:
        def read(self):
            return b"payload"
    client = BaseZohoClient("token", "in", "https://www.zohoapis.in", "books")
    client.session.request = MagicMock()
    with pytest.raises(ValueError, match="seekable"):
        client.request("POST", "upload", files={"file": Stream()})
    client.session.request.assert_not_called()
    client.close()


@pytest.mark.parametrize("module", [dashboard, payment_review])
@pytest.mark.parametrize("method,path", [("GET", "/"), ("GET", "/api/state"), ("POST", "/api/refresh")])
def test_servers_reject_foreign_host_before_service_access(module, method, path):
    service = MagicMock()
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.make_handler(service, "secret"))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = HTTPConnection(*server.server_address)
        conn.request(method, path, headers={"Host": "attacker.example", "X-Review-Token": "secret", "X-Launcher-Token": "secret"})
        response = conn.getresponse()
        assert response.status == 403
        assert b"secret" not in response.read()
        assert not service.mock_calls
        conn.close()
        conn = HTTPConnection(*server.server_address)
        conn.request("GET", "/", headers={"Host": f"localhost:{server.server_port}"})
        response = conn.getresponse()
        assert response.status == 200
        assert b"secret" in response.read()
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_analytics_org_required_before_token_request(monkeypatch):
    token = MagicMock()
    monkeypatch.setattr("workflows.runtime.auth.get_token_for", token)
    with pytest.raises(ValueError, match="ANALYTICS_ORG_ID"):
        get_analytics_client(org_id="")
    token.assert_not_called()


def test_deployment_defaults_are_empty_and_explicit_values_migrate(monkeypatch):
    from workflows.runtime import config
    source = __import__('pathlib').Path(config.__file__).read_text()
    class_source = source[source.index('class Config:'):]
    keys = [
        'ANALYTICS_ORG_ID',
        'ANALYTICS_WORKSPACE_ID',
        'ANALYTICS_DATE_MISMATCH_VIEW_ID',
        'ANALYTICS_BANK_STATEMENT_VIEW_ID',
        'ANALYTICS_CUSTOMER_FINDER_VIEW_ID',
        'INTER_LOCATION_CONTRA_VIEW_ID',
        'INTER_LOCATION_DIFF_VIEW_ID',
        'PAYMENT_TRAVEL_EXPENSE_ACCOUNT_ID',
        'PAYMENT_SALARY_EXPENSE_ACCOUNT_ID',
        'PAYMENT_CASH_ACCOUNT_ID',
        'NEOSEAL_STOCK_COUNT_SHEET_ID',
        'POLYCAB_RMA_ITEM_ID',
        'SALES_ACCOUNT_ID',
        'UNEARNED_REVENUE_ACCOUNT_ID',
        'INTER_BRANCH_ACCOUNT_ID',
        'INTER_LOCATION_CLEARING_ACCOUNT_ID',
        'EXCLUDED_LOCATION_ID',
    ]
    monkeypatch.setattr(config, '_FILE_CONFIG', {})
    for key in keys + ['ZOHO_ANALYTICS_WORKSPACE_ID']:
        monkeypatch.delenv(key, raising=False)
    namespace = dict(vars(config))
    exec(class_source, namespace)
    assert all(getattr(namespace['Config'], key) == '' for key in keys)
    monkeypatch.setattr(config, '_FILE_CONFIG', {key.lower(): 'explicit-id' for key in keys})
    exec(class_source, namespace)
    assert all(getattr(namespace['Config'], key) == 'explicit-id' for key in keys)
    monkeypatch.setenv('ANALYTICS_ORG_ID', 'environment-id')
    exec(class_source, namespace)
    assert namespace['Config'].ANALYTICS_ORG_ID == 'environment-id'


@pytest.mark.parametrize('module', [dashboard, payment_review])
@pytest.mark.parametrize('hosts', [[], ['localhost:1'], ['evil.example:8765'],
                                   ['localhost:8765', 'localhost:8765'],
                                   ['localhost:8765.evil.example']])
def test_host_guard_rejects_missing_duplicate_and_malformed_authorities(module, hosts):
    from email.message import Message
    service = MagicMock()
    cls = module.make_handler(service, 'secret')
    handler = cls.__new__(cls)
    handler.server = MagicMock(server_address=('127.0.0.1', 8765))
    handler.headers = Message()
    for host in hosts:
        handler.headers['Host'] = host
    handler._json = MagicMock()
    handler.path = '/'
    handler.do_GET()
    handler._json.assert_called_once_with({'error': 'Invalid Host header'}, 403)
    assert not service.mock_calls


@pytest.mark.parametrize("override", [False, True])
def test_request_log_redacts_url_without_changing_transport(monkeypatch, caplog, override):
    import logging

    base_url = "https://www.zohoapis.in"
    client = BaseZohoClient("token", "in", base_url, "analytics")
    query = "page=2&%61ccess_token=FIRST_SENTINEL&access_token=SECOND_SENTINEL&sig=SIGNED_SENTINEL"
    endpoint = f"files?{query}"
    override_url = f"https://download.zoho.in/{endpoint}" if override else None
    response = requests.Response()
    response.status_code = 204
    response._content = b""
    transport = MagicMock(return_value=response)
    monkeypatch.setattr(client.session, "request", transport)

    with caplog.at_level(logging.INFO, logger="zoho.analytics"):
        client.request("GET", endpoint, override_url=override_url)

    assert "page=2" in caplog.text
    assert "SENTINEL" not in caplog.text
    assert transport.call_args.kwargs["url"] == (override_url or f"{base_url}/{endpoint}")


def test_workdrive_list_log_redacts_params_without_changing_request(caplog):
    import logging

    from zoho.wd.resources.files import Files

    client = MagicMock()
    params = {"limit": 50, "token": "LIST_SECRET_1234"}
    with caplog.at_level(logging.INFO, logger="zoho_wd.app"):
        Files(client).list_files("folder", params)

    assert "50" in caplog.text
    assert "LIST_SECRET" not in caplog.text
    client.request.assert_called_once_with("GET", "files/folder/files", params=params)
