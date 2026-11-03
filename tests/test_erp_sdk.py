"""ERP definition coverage, routing, validation and shared transport contracts."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from zoho import ZohoERPAPI, ZohoERPError
from zoho.erp.generated import RESOURCE_TYPES

MANIFEST = json.loads((Path(__file__).parents[1] / "src/zoho/erp/manifest.json").read_text(encoding="utf-8"))
OPERATIONS = [(resource, operation) for resource, definition in MANIFEST.items()
              for operation in definition["operations"]]


@pytest.fixture
def api():
    with ZohoERPAPI("test-token", "org", domain="in") as client:
        yield client


@pytest.mark.parametrize("resource,operation", OPERATIONS,
                         ids=[f"{r}.{o['name']}" for r, o in OPERATIONS])
def test_every_generated_operation_routes_to_documented_endpoint(api, resource, operation):
    args = ["id /?#" for _ in operation["path_parameters"]]
    params = {name: "value" for name in operation["required_query"]}
    headers = {name: "value" for name in operation["required_headers"]}
    body = {} if operation["body_required"] else None
    with patch("zoho.base_client.BaseZohoClient.request", return_value={"code": 0}) as request:
        assert getattr(getattr(api, resource), operation["name"])(
            *args, params=params, headers=headers, body=body) == {"code": 0}
    expected_path = operation["path"]
    for name in operation["path_parameters"]:
        expected_path = expected_path.replace("{" + name + "}", "id%20%2F%3F%23")
    call = request.call_args.kwargs
    assert call["method"] == operation["method"]
    assert call["override_url"] == "https://www.zohoapis.in/erp/" + operation["version"] + expected_path
    assert call["params"] == {**params, "organization_id": "org"}
    assert params == {name: "value" for name in operation["required_query"]}


def response(code=200, payload=None):
    result = requests.Response()
    result.status_code = code
    result.headers["Content-Type"] = "application/json"
    result._content = json.dumps(payload or {"code": 0}).encode()
    result._content_consumed = True
    return result


def test_http_transport_and_error_type(api):
    api.session.request = Mock(return_value=response())
    api.departments.list_departments(params={"page": 2}, timeout=12)
    call = api.session.request.call_args.kwargs
    assert call["url"] == "https://www.zohoapis.in/erp/v1/departments"
    assert call["params"] == {"page": 2, "organization_id": "org"}
    assert call["headers"]["Authorization"] == "Zoho-oauthtoken test-token"
    assert call["timeout"] == 12
    api.session.request.return_value = response(400, {"code": 1001, "message": "Invalid department"})
    with pytest.raises(ZohoERPError, match="Invalid department") as caught:
        api.departments.list_departments()
    assert caught.value.error_code == 1001


def test_mutation_intent_and_refresh():
    token = Mock()
    token.get_token_for_request.return_value = "old"
    refresh = Mock(return_value="new")
    with ZohoERPAPI(token, "org", token_refresh_callback=refresh) as api:
        api.session.request = Mock(side_effect=[response(401), response(), response()])
        api.departments.create_department(body={"department_name": "Accounts"})
        token.get_token_for_request.assert_called_with(True)
        refresh.assert_called_once()
        assert api.session.request.call_args.kwargs["headers"]["Authorization"].endswith("new")
        api.departments.list_departments()


@pytest.mark.parametrize("identifier", ["", " ", ".", "..", None, 123])
def test_invalid_path_does_not_send_request(api, identifier):
    with patch.object(api, "request") as request:
        with pytest.raises(ValueError, match="department_id"):
            api.departments.get_department_details(identifier)
        request.assert_not_called()


def test_organization_override_and_inputs(api):
    with patch("zoho.base_client.BaseZohoClient.request") as request:
        with pytest.raises(ValueError, match="organization"):
            api.departments.list_departments(params={"organization_id": "other"})
        request.assert_not_called()
    with pytest.raises(ValueError, match="organization"):
        ZohoERPAPI("token", " ")
    with pytest.raises(ValueError, match="domain"):
        ZohoERPAPI("token", "org", domain="in/evil")


def test_required_query_and_multipart(api):
    required = next((r, o) for r, o in OPERATIONS if o["required_query"])
    r, o = required
    with pytest.raises(ValueError, match="required query"):
        getattr(getattr(api, r), o["name"])(*["id"] * len(o["path_parameters"]))
    r, o = next((r, o) for r, o in OPERATIONS if "multipart/form-data" in o["media"])
    upload = {"attachment": ("sample.txt", b"sample")}
    with patch("zoho.base_client.BaseZohoClient.request") as request:
        getattr(getattr(api, r), o["name"])(*["id"] * len(o["path_parameters"]),
            params={n: "value" for n in o["required_query"]},
            headers={n: "value" for n in o["required_headers"]}, body={"description": "sample"}, files=upload)
    assert request.call_args.kwargs["files"] is upload
    assert request.call_args.kwargs["data"] == {"description": "sample"}
    assert request.call_args.kwargs["json"] is None
    with pytest.raises(ValueError, match="multipart"):
        api.departments.list_departments(files=upload)
    with pytest.raises(ValueError, match="request body"):
        api.departments.list_departments(body={})


def test_resource_and_operation_coverage():
    assert len(RESOURCE_TYPES) == len(MANIFEST) == 81
    assert len(OPERATIONS) == 899
    assert {o["version"] for _, o in OPERATIONS} == {"v1", "v3"}
    for name, resource in RESOURCE_TYPES.items():
        assert {n for n in vars(resource) if not n.startswith("_")} == {
            o["name"] for o in MANIFEST[name]["operations"]}


def test_factory_uses_erp_token():
    from workflows.core.auth import get_erp_client
    with patch("workflows.core.auth.get_token_for", return_value="erp-token") as token:
        with get_erp_client(org_id="org", domain="in") as api:
            assert api.access_token == "erp-token"
            assert api.token_refresh_callback() == "erp-token"
    assert all(c.args[:2] == ("erp", "zoho_erp_conn") for c in token.call_args_list)


def test_generation_is_deterministic_and_rejects_invalid_specs(tmp_path):
    location = Path(__file__).parents[1] / "apps/generate_erp_sdk.py"
    spec = importlib.util.spec_from_file_location("generate_erp_sdk", location)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path / "specs"
    source.mkdir()
    definition = source / "example.yml"
    definition.write_text('''openapi: 3.0.0
servers:
  - url: https://www.zohoapis.in/erp/v3
paths:
  /example/{id}:
    get:
      operationId: get_example
''', encoding="utf-8")
    target = tmp_path / "generated"
    module.generate(source, target)
    first = (target / "generated.py").read_bytes()
    module.generate(source, target)
    assert (target / "generated.py").read_bytes() == first
    definition.write_text(definition.read_text().replace("https://www.zohoapis.in", "https://example.com"))
    with pytest.raises(ValueError, match="server"):
        module.generate(source, target)
    assert (target / "generated.py").read_bytes() == first
