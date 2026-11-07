"""SDK-002: malformed pagination cannot look like a complete dataset."""

from unittest.mock import Mock

import pytest

from zoho.base_resource import BaseResource
from zoho.exceptions import ZohoError


@pytest.mark.parametrize("response", [
    None, [], {}, {"items": {}}, {"items": [None]},
    {"items": [], "page_context": None},
    {"items": [], "page_context": []},
    {"items": [], "page_context": {"has_more_page": "false"}},
    {"items": [], "page_context": {"has_more_page": 0}},
    {"items": [], "page_context": {"has_more_page": True}},
    {"items": [{"id": "x"}], "page_context": {"page": 2}},
    {"items": [{"id": "x"}], "page_context": {"page": True}},
])
def test_invalid_response_fails_with_endpoint_and_page(response):
    client = Mock()
    client.request.return_value = response
    with pytest.raises(ZohoError, match="items page 1") as failure:
        BaseResource(client, "items").list_all()
    assert failure.value.endpoint == "items"
    assert client.request.call_count == 1


def test_second_page_failure_does_not_return_partial_success():
    client = Mock()
    client.request.side_effect = [
        {"items": [{"id": "first"}], "page_context": {"has_more_page": True}},
        {"items": [], "page_context": {"has_more_page": True}},
    ]
    with pytest.raises(ZohoError, match="items page 2"):
        BaseResource(client, "items").list_all()
    assert client.request.call_count == 2


@pytest.mark.parametrize("response", [
    {"items": []}, {"items": [], "page_context": {"has_more_page": False}},
])
def test_valid_empty_results(response):
    client = Mock()
    client.request.return_value = response
    assert BaseResource(client, "items").list_all() == []


def test_custom_key_and_multiple_pages_preserve_records_and_query():
    client = Mock()
    client.request.side_effect = [
        {"records": [{"id": "a"}], "page_context": {"page": 1, "has_more_page": True}},
        {"records": [{"id": "b"}], "page_context": {"page": 2, "has_more_page": False}},
    ]
    query = {"purchase_account_id": "vendor-account"}
    assert BaseResource(client, "items").list_all(query, resource_key="records") == [{"id": "a"}, {"id": "b"}]
    assert query == {"purchase_account_id": "vendor-account"}
    assert client.request.call_args.kwargs["params"] == {**query, "page": 2, "per_page": 200}


def test_streaming_checks_current_page_before_yielding_records():
    client = Mock()
    client.request.return_value = {"items": [{"id": "a"}], "page_context": {"has_more_page": "yes"}}
    iterator = BaseResource(client, "items").list_iter()
    with pytest.raises(ZohoError):
        next(iterator)


@pytest.mark.parametrize("per_page", [0, -1, True, "200"])
def test_invalid_page_size_fails_before_request(per_page):
    client = Mock()
    with pytest.raises(ValueError, match="per_page"):
        list(BaseResource(client, "items").list_iter(per_page=per_page))
    client.request.assert_not_called()


def test_raw_resource_responses_remain_opaque_until_consumed():
    client = Mock()
    client.request.return_value = b"statement"
    resource = BaseResource(client, "contacts")
    assert resource.get("contact/statements") == b"statement"
