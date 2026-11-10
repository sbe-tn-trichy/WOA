from unittest.mock import Mock

import pytest

from zoho.books.custom import Imports


@pytest.mark.parametrize("new_flow", [False, True])
def test_confirmation_sends_organization_once_in_query(new_flow):
    client = Mock(organization_id="org1")
    response = {"code": 0}
    client.request.return_value = response
    assert Imports(client).confirm("12345", is_new_flow=new_flow) is response
    client.request.assert_called_once_with(
        "PUT", "import/12345",
        params={"is_new_flow": str(new_flow).lower(), "organization_id": "org1"},
        is_mutation=True,
    )


@pytest.mark.parametrize("import_id", ["", " ", "12/34", "../123", "123?org=2", "１２３", 123, None])
def test_invalid_import_id_does_not_send_request(import_id):
    client = Mock(organization_id="org1")
    with pytest.raises(ValueError, match="import_id"):
        Imports(client).confirm(import_id)
    client.request.assert_not_called()


@pytest.mark.parametrize("organization_id", [None, "", " "])
def test_missing_organization_does_not_send_request(organization_id):
    client = Mock(organization_id=organization_id)
    with pytest.raises(ValueError, match="organization_id"):
        Imports(client).confirm("123")
    client.request.assert_not_called()


def test_invalid_flow_does_not_send_request():
    client = Mock(organization_id="org1")
    with pytest.raises(ValueError, match="is_new_flow"):
        Imports(client).confirm("123", is_new_flow="false")
    client.request.assert_not_called()


def test_failure_is_propagated_without_resource_retry():
    client = Mock(organization_id="org1")
    client.request.side_effect = RuntimeError("uncertain confirmation")
    with pytest.raises(RuntimeError, match="uncertain confirmation"):
        Imports(client).confirm("123")
    client.request.assert_called_once()
