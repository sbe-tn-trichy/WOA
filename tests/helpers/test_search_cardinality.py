from unittest.mock import Mock, call

import pytest

from helpers import (
    AmbiguousMatchError,
    ensure_books_custom_fields,
    resolve_bill_by_number,
    resolve_inventory_item_by_sku_or_name,
    resolve_inventory_sku,
    resolve_transaction_by_number,
    search_customers,
)
from zoho.books.custom.contacts import Contacts


def customer(identifier, **fields):
    return {"contact_id": identifier, "contact_type": "customer", **fields}


def page(number, rows, *, more=False):
    return {"contacts": rows, "page_context": {"page": number, "has_more_page": more}}


def test_name_search_follows_pages_and_deduplicates_distinct_customer_ids():
    client = Mock()
    contact = customer("one", contact_name="Acme Traders")
    company = customer("two", company_name="ACME Industries")
    client.request.side_effect = [
        page(1, [contact], more=True),
        page(2, [company]),
        page(1, [company, {**contact, "contact_type": "vendor"}]),
    ]
    result = search_customers(Mock(contacts=Contacts(client)), " acme ", exact=False)
    assert result.status == "ambiguous"
    assert result.candidates == (contact, company)
    assert client.request.call_args_list == [
        call("GET", "contacts", params={
            "contact_type": "customer", field: "acme", "page": number, "per_page": 200,
        })
        for field, number in [
            ("contact_name_contains", 1),
            ("contact_name_contains", 2),
            ("company_name_contains", 1),
        ]
    ]


@pytest.mark.parametrize(("by", "query", "fields"), [
    ("gstin", "33 aabcd1234e1z5", {"custom_fields": [
        {"api_name": "gstin", "value": "33AABCD1234E1Z5"},
    ]}),
    ("phone", "+91 12345 67890", {"mobile": "+91 (12345) 67890"}),
])
def test_customer_search_matches_normalized_fields(by, query, fields):
    books = Mock()
    books.contacts.list_all.return_value = [customer("one", **fields)]
    assert search_customers(books, query, by=by).status == "unique"
    books.contacts.list_all.assert_called_once_with(
        params={"contact_type": "customer"}, resource_key="contacts",
    )
    books.contacts.list_all.return_value = [customer("two", phone="1234567890")]
    assert search_customers(books, query, by=by).status == "no_match"


def test_search_propagates_later_page_failure():
    client = Mock()
    client.request.side_effect = [
        page(1, [customer("one", contact_name="Acme")], more=True),
        RuntimeError("request failed"),
    ]
    with pytest.raises(RuntimeError, match="request failed"):
        search_customers(Mock(contacts=Contacts(client)), "Acme")


def test_search_rejects_matching_customer_without_id():
    books = Mock()
    books.contacts.list_all.return_value = [customer("", contact_name="Acme")]
    with pytest.raises(ValueError, match="contact_id"):
        search_customers(books, "Acme")


def test_sku_ranking_rejects_distinct_tied_active_items():
    inventory = Mock()
    inactive = {"item_id": "old", "sku": "ABC", "status": "inactive"}
    active = {"item_id": "new", "sku": "ABC", "status": "active"}
    wrong_account = {**active, "item_id": "elsewhere", "purchase_account_id": "other"}
    inventory.items.list_all.return_value = [inactive, active, wrong_account]
    assert resolve_inventory_sku(inventory, "abc", purchase_account_id="account") == active
    inventory.items.list_all.return_value.append({**active, "item_id": "duplicate"})
    with pytest.raises(AmbiguousMatchError, match="found 2"):
        resolve_inventory_sku(inventory, "abc", purchase_account_id="account")


def test_item_name_search_prefers_exact_and_rejects_tied_partial_matches():
    inventory = Mock()
    exact = {"item_id": "sku", "sku": "Fan"}
    partial = [{"item_id": "one", "name": "Fan 1"}, {"item_id": "two", "name": "Fan 2"}]
    inventory.items.list_all.return_value = [*partial, exact]
    assert resolve_inventory_item_by_sku_or_name(inventory, "fan") == exact
    inventory.items.list_all.return_value = partial
    with pytest.raises(AmbiguousMatchError, match="item_id"):
        resolve_inventory_item_by_sku_or_name(inventory, "fan")


def test_bill_search_only_accepts_exact_number_within_vendor():
    bills = Mock()
    exact = {"bill_id": "a", "bill_number": "B-1", "vendor_id": "vendor"}
    bills.list_all.return_value = [
        {**exact, "bill_id": "b", "bill_number": "B-10"},
        {**exact, "bill_id": "c", "vendor_id": "other"},
    ]
    assert resolve_bill_by_number(bills, "vendor", "B-1") is None
    bills.list_all.return_value += [exact, {**exact, "bill_id": "d"}]
    with pytest.raises(AmbiguousMatchError, match="bill_id"):
        resolve_bill_by_number(bills, "vendor", "B-1")


def test_sales_order_search_checks_both_number_fields():
    orders = Mock()
    orders.list_all.side_effect = [
        [],
        [{"salesorder_id": "one", "salesorder_number": "RSO-1"}],
    ]
    match = resolve_transaction_by_number(
        orders, "RSO-1", number_fields=("reference_number", "salesorder_number"),
        resource_key="salesorders", id_key="salesorder_id",
    )
    assert match == {"salesorder_id": "one", "salesorder_number": "RSO-1"}
    assert orders.list_all.call_args_list == [
        call(params={field: "RSO-1"}, resource_key="salesorders")
        for field in ("reference_number", "salesorder_number")
    ]


def test_custom_field_collision_blocks_provisioning():
    books = Mock()
    books.custom_fields.list_for_entity.return_value = [
        {"customfield_id": "one", "label": "Payment Ref"},
        {"customfield_id": "two", "api_name": "cf_payment_ref"},
    ]
    result = ensure_books_custom_fields(
        books, "invoice", [{"label": "Payment Ref"}, {"label": "Missing"}], create_missing=True,
    )
    assert result["valid"] is False
    assert result["misconfigured"][0]["field"] == "Payment Ref"
    books.custom_fields.create.assert_not_called()
