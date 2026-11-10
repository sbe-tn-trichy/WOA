from unittest.mock import Mock

import pytest

from zoho.books import ZohoBooksAPI
from zoho.books.custom import Imports


@pytest.mark.parametrize("duplicate_handling", ["overwrite", "skip", "create_new"])
def test_upload_sends_actual_csv_and_closes_handle(tmp_path, duplicate_handling):
    path = tmp_path / "customers.csv"
    content = b"Customer Number,Display Name,Branch\nC1,Shop,Electricals\n"
    path.write_bytes(content)
    client = Mock(organization_id="org1")
    response = {"code": 0, "file_id": "staged"}
    handles = []

    def request(method, endpoint, **kwargs):
        assert (method, endpoint) == ("POST", "import/uploadfile")
        assert kwargs["params"] == {"is_new_flow": "false"}
        assert kwargs["data"] == {
            "charencoding": "UTF-8", "entity": "contact",
            "duplicate_handling": duplicate_handling, "delimiter": ",",
            "organization_id": "org1",
        }
        name, handle, mime = kwargs["files"]["importfile"]
        assert (name, mime) == ("customers.csv", "text/csv")
        assert handle.read() == content
        assert "headers" not in kwargs
        handles.append(handle)
        return response

    client.request.side_effect = request
    assert Imports(client).upload_file(path, entity="contact", duplicate_handling=duplicate_handling) is response
    assert handles[0].closed
    client.request.assert_called_once()


@pytest.mark.parametrize("overrides", [
    {"entity": ""}, {"duplicate_handling": "replace"},
    {"charencoding": ""}, {"delimiter": "::"}, {"delimiter": "\n"},
    {"is_new_flow": "false"},
])
def test_invalid_options_fail_before_network(tmp_path, overrides):
    path = tmp_path / "customers.csv"
    path.write_text("a\nb\n")
    client = Mock(organization_id="org1")
    with pytest.raises(ValueError):
        Imports(client).upload_file(path, **({"entity": "contact", "duplicate_handling": "skip"} | overrides))
    client.request.assert_not_called()


@pytest.mark.parametrize("kind", ["missing", "empty", "wrong_extension", "directory"])
def test_invalid_files_fail_before_network(tmp_path, kind):
    path = tmp_path / ("customers.txt" if kind == "wrong_extension" else "customers.csv")
    if kind == "directory":
        path.mkdir()
    elif kind != "missing":
        path.write_bytes(b"" if kind == "empty" else b"a\nb\n")
    client = Mock(organization_id="org1")
    with pytest.raises((ValueError, FileNotFoundError)):
        Imports(client).upload_file(path, entity="contact", duplicate_handling="skip")
    client.request.assert_not_called()


def test_failed_request_closes_file_and_propagates(tmp_path):
    path = tmp_path / "customers.csv"
    path.write_text("a\nb\n")
    client = Mock(organization_id="org1")
    handles = []

    def fail(*args, **kwargs):
        handles.append(kwargs["files"]["importfile"][1])
        raise RuntimeError("upload failed")

    client.request.side_effect = fail
    with pytest.raises(RuntimeError, match="upload failed"):
        Imports(client).upload_file(path, entity="contact", duplicate_handling="overwrite")
    assert handles[0].closed


def test_client_exposes_imports_and_pins_organization(tmp_path):
    path = tmp_path / "customers.csv"
    path.write_text("a\nb\n")
    api = ZohoBooksAPI("fake", "org1")
    assert isinstance(api.imports, Imports)
    api.organization_id = ""
    with pytest.raises(ValueError, match="organization_id"):
        api.imports.upload_file(path, entity="contact", duplicate_handling="skip")
