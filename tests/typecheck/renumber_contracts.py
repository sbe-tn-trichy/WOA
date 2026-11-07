"""Compile-only compatibility examples; no clients or network calls are made."""

from typing import assert_type
from dataclasses import dataclass

from zoho.books import ZohoBooksAPI
from zoho.analytics import ZohoAnalyticsAPI
from workflows.payment_renumbering import (
    RenumberAnalyticsClient, RenumberBooksClient, PaymentId, CustomerId,
    RenumberResult,
)
from workflows.vendor_customer_offset.contracts import OffsetBooksClient


class FakePayments:
    def get(self, resource_id: str) -> object:
        return {"payment": {"payment_id": resource_id}}

    def list_all(self) -> object:
        return []

    def update_with_number_series(self, payment_id: str, data: dict[str, str]) -> object:
        return {"code": 0}


@dataclass
class FakeBooks:
    customer_payments: FakePayments


fake_books: RenumberBooksClient = FakeBooks(FakePayments())


def sdk_contracts(books: ZohoBooksAPI, analytics: ZohoAnalyticsAPI) -> None:
    checked_books: RenumberBooksClient = books
    offset_books: OffsetBooksClient = books
    checked_analytics: RenumberAnalyticsClient = analytics
    assert_type(checked_books.customer_payments.get("payment"), object)
    assert_type(offset_books.vendor_payments.create({"vendor_id": "vendor"}), object)
    analytics_contract(checked_analytics)


def analytics_contract(client: RenumberAnalyticsClient) -> None:
    assert_type(client.queries.execute(
        "workspace", "SELECT 1", max_attempts=1, poll_interval=2.0,
    ), object)


def identity_contracts(result: RenumberResult, customer_id: CustomerId) -> None:
    assert_type(result["payment_id"], PaymentId)
    assert_type(customer_id, CustomerId)
