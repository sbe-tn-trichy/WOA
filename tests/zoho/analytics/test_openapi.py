import importlib
import inspect
import json
import re
from importlib.resources import files
from unittest.mock import MagicMock

import pytest

from zoho.analytics import ZohoAnalyticsAPI
from zoho.analytics.openapi import RESOURCE_TYPES


MANIFEST = json.loads(files("zoho.analytics.openapi").joinpath("manifest.json").read_text())
OPERATIONS = [
    (domain, operation)
    for domain, entry in MANIFEST.items()
    for operation in entry["operations"]
]


@pytest.mark.parametrize(
    "domain,operation", OPERATIONS, ids=[operation["operation_id"] for _, operation in OPERATIONS]
)
def test_generated_routes(domain, operation, monkeypatch):
    client = ZohoAnalyticsAPI("token", "org", domain="in")
    transport = MagicMock(return_value=MagicMock(status_code=200))
    monkeypatch.setattr(client.session, "request", transport)
    resource = getattr(client.openapi, domain)
    assert type(resource) is RESOURCE_TYPES[domain]
    wrapper = getattr(resource, operation["name"])
    path = operation["path"]
    path_args = {key.replace("-", "_"): "a/b" for key in re.findall(r"{([\w-]+)}", path)}
    signature = inspect.signature(wrapper)
    kwargs = {"stream": True, "timeout": 9}
    if "config" in signature.parameters:
        kwargs["config"] = {"sample": True}
    if "upload" in signature.parameters:
        kwargs["upload"] = ("rows.csv", b"column\nvalue\n")
    if "destination_org_id" in signature.parameters:
        kwargs["destination_org_id"] = "destination"

    assert wrapper(**path_args, **kwargs) is transport.return_value
    wire = transport.call_args.kwargs
    method, url = wire["method"], wire["url"]
    assert method == operation["method"]
    assert url == "https://analyticsapi.zoho.in" + re.sub(r"{[^}]+}", "a%2Fb", path)
    assert wire["headers"]["ZANALYTICS-ORGID"] == "org"
    assert wire["headers"]["Authorization"] == "Zoho-oauthtoken token"
    assert wire["headers"].get("ZANALYTICS-DEST-ORGID") == kwargs.get("destination_org_id")
    assert wire["stream"] is True
    assert wire["timeout"] == 9
    if "config" in kwargs:
        wire_field = "params" if method == "GET" else "data"
        assert json.loads(wire[wire_field]["CONFIG"]) == kwargs["config"]
    if "upload" in kwargs:
        assert wire["files"] == {"FILE": kwargs["upload"]}


def test_manifest_covers_generated_resources():
    assert len(RESOURCE_TYPES) == 10
    assert len(OPERATIONS) == 203
    routes = {(op["method"], re.sub(r"{[^}]+}", "{}", op["path"])) for _, op in OPERATIONS}
    assert len(routes) == len(OPERATIONS)
    for domain, resource in RESOURCE_TYPES.items():
        methods = {name for name, _ in inspect.getmembers(resource, inspect.isfunction) if not name.startswith("_")}
        assert methods == {op["name"] for op in MANIFEST[domain]["operations"]}


@pytest.mark.parametrize("module", ["resources", "metadata", "snapshot"])
def test_legacy_modules_share_identity(module):
    assert importlib.import_module(f"zoho.analytics.{module}") is importlib.import_module(
        f"zoho.analytics.custom.{module}"
    )


def test_inline_data_and_validation(monkeypatch):
    client = ZohoAnalyticsAPI("token", "org")
    request = MagicMock()
    monkeypatch.setattr(client, "request", request)
    operations = client.openapi.data_operations
    with pytest.raises(ValueError, match="workspace-id"):
        operations.import_data_new_table("..", config={}, inline_data="a,b")
    with pytest.raises(ValueError, match="exactly one"):
        operations.import_data_new_table("w1", config={})
    with pytest.raises(ValueError, match="exactly one"):
        operations.import_data_new_table("w1", config={}, upload=b"file", inline_data="a,b")
    with pytest.raises(ValueError, match="config is required"):
        operations.create_import_job_new_table("w1", config=None, upload=b"file")
    assert not request.called

    operations.import_data_new_table("w1", config={}, inline_data="a,b")
    assert request.call_args.kwargs["files"] == {"DATA": (None, "a,b")}
    assert request.call_args.kwargs["data"] == {"CONFIG": "{}"}


def test_key_regeneration_marks_get_as_mutation(monkeypatch):
    client = ZohoAnalyticsAPI("token", "org")
    request = MagicMock()
    monkeypatch.setattr(client, "request", request)
    get_key = client.openapi.workspace_management.get_workspace_secret_key
    get_key("w1")
    assert request.call_args.kwargs["is_mutation"] is False
    get_key("w1", config={"regenerateKey": True})
    assert request.call_args.kwargs["is_mutation"] is True
    with pytest.raises(ValueError, match="must be a boolean"):
        get_key("w1", config={"regenerateKey": "false"})
    assert request.call_count == 2
