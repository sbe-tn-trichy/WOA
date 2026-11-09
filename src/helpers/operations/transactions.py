"""Higher-level helper functions for Zoho Books transaction lookups and response unwrapping."""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from collections.abc import Mapping, Sequence
from typing import Protocol

from zoho.core_sdk.validation import require_records
from .records import SearchResource, unique_record

logger = logging.getLogger("helpers.operations.transactions")

CLOSED_DOCUMENT_STATUSES = {
    "void",
    "draft",
    "paid",
    "rejected",
    "pending_approval",
    "approval_overdue",
}


class BooksInvoicesClient(Protocol):
    @property
    def invoices(self) -> SearchResource: ...


class BooksBillsSearchClient(Protocol):
    @property
    def bills(self) -> SearchResource: ...


class BooksBillsLookupResource(SearchResource, Protocol):
    def list(
        self, params: dict[str, object] | None = None,
    ) -> object: ...


class BooksBillsClient(BooksBillsSearchClient, Protocol):
    @property
    def bills(self) -> BooksBillsLookupResource: ...


def _to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, AttributeError, ValueError):
        return None


def _to_text(value: object) -> str:
    return "" if value is None else str(value).strip()


def resolve_bill_by_number(
    resource: SearchResource, vendor_id: str, bill_number: str,
) -> dict[str, object] | None:
    """Resolve one exact Books bill number within the selected vendor."""
    vendor = vendor_id.strip()
    number = bill_number.strip()
    if not vendor or not number:
        raise ValueError("Vendor ID and bill number are required")
    rows = require_records(
        resource.list_all(params={"vendor_id": vendor, "bill_number": number}, resource_key="bills"),
        "Books bill search",
    )
    numbered = [row for row in rows if _to_text(row.get("bill_number")).casefold() == number.casefold()]
    if any(not _to_text(row.get("vendor_id")) for row in numbered):
        raise ValueError("Matching Books bill has no vendor_id")
    return unique_record(
        (row for row in numbered if _to_text(row.get("vendor_id")) == vendor), "bill_id",
    )


def resolve_transaction_by_number(
    resource: SearchResource,
    number: str,
    *,
    number_fields: Sequence[str],
    resource_key: str,
    id_key: str,
) -> dict[str, object] | None:
    """Resolve one Books transaction using its supported number filters."""
    target = number.strip()
    if not target or not number_fields:
        raise ValueError("Transaction number and at least one number field are required")
    candidates: list[dict[str, object]] = []
    for field in dict.fromkeys(number_fields):
        rows = require_records(
            resource.list_all(params={field: target}, resource_key=resource_key),
            f"Books {resource_key} search",
        )
        candidates.extend(
            row for row in rows if any(_to_text(row.get(key)) == target for key in number_fields)
        )
    return unique_record(candidates, id_key)


def normalize_cheque_number(value: object) -> str:
    """Normalize a cheque reference number by stripping non-alphanumerics and leading zeros."""
    normalized = "".join(
        character for character in _to_text(value).casefold() if character.isalnum()
    )
    return normalized.lstrip("0") or ("0" if normalized else "")


def fetch_open_invoices(
    books_client: BooksInvoicesClient,
    customer_id: str,
) -> list[dict[str, object]]:
    """Fetch open, non-zero balance invoices for a customer from Zoho Books."""
    customer_id_str = _to_text(customer_id)
    if not customer_id_str:
        return []
    rows = books_client.invoices.list_all(params={"customer_id": customer_id_str})
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and _to_text(row.get("status")).casefold() not in CLOSED_DOCUMENT_STATUSES
        and (_to_decimal(row.get("balance")) or Decimal("0")) > 0
        and _to_text(row.get("invoice_id"))
    ]


def fetch_open_bills(
    books_client: BooksBillsSearchClient,
    vendor_id: str,
) -> list[dict[str, object]]:
    """Fetch open, non-zero balance bills for a vendor from Zoho Books."""
    vendor_id_str = _to_text(vendor_id)
    if not vendor_id_str:
        return []
    rows = books_client.bills.list_all(params={"vendor_id": vendor_id_str})
    if not isinstance(rows, list):
        return []
    return [
        row
        for row in rows
        if isinstance(row, dict)
        and _to_text(row.get("status")).casefold() not in CLOSED_DOCUMENT_STATUSES
        and (_to_decimal(row.get("balance")) or Decimal("0")) > 0
        and _to_text(row.get("bill_id"))
    ]


def find_bill_by_number(
    books_client: BooksBillsClient,
    vendor_id: str,
    bill_number: str,
) -> dict[str, object] | None:
    """Find a bill under a specific vendor by bill number."""
    vendor_id_str = _to_text(vendor_id)
    bill_no_str = _to_text(bill_number)
    if not vendor_id_str or not bill_no_str:
        return None

    try:
        res = books_client.bills.list(params={"vendor_id": vendor_id_str, "bill_number": bill_no_str})
        bills = res.get("bills", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])
        for bill in bills:
            if isinstance(bill, dict) and _to_text(bill.get("bill_number")).casefold() == bill_no_str.casefold():
                return bill
        if bills and isinstance(bills[0], dict):
            return bills[0]
    except Exception as exc:
        logger.warning(f"Error finding bill '{bill_no_str}' for vendor '{vendor_id_str}': {exc}")

    return None


def allocate_documents_fifo(
    amount: object,
    documents: Sequence[Mapping[str, object]],
    id_key: str = "invoice_id",
    include_metadata: bool = False,
) -> tuple[list[dict[str, object]], Decimal]:
    """Allocate a payment/credit amount across open documents sorted by due date and date.

    Returns a tuple of (allocations, unallocated_remaining_amount).
    """
    dec_amount = _to_decimal(amount)
    if dec_amount is None or dec_amount <= 0:
        raise ValueError("A positive amount is required for allocation.")

    remaining = dec_amount
    sorted_docs = list(documents)
    sorted_docs.sort(
        key=lambda row: (
            _to_text(row.get("due_date")) or "9999-12-31",
            _to_text(row.get("date")) or "9999-12-31",
            _to_text(row.get(id_key) or row.get("invoice_id") or row.get("bill_id")),
        )
    )

    allocations: list[dict[str, object]] = []
    for doc in sorted_docs:
        balance = _to_decimal(doc.get("balance")) or Decimal("0")
        doc_id = _to_text(doc.get(id_key) or doc.get("invoice_id") or doc.get("bill_id"))
        if not doc_id or balance <= 0 or remaining <= 0:
            continue
        applied = min(balance, remaining)
        allocation: dict[str, object] = {
            id_key: doc_id,
            "amount_applied": float(applied),
        }
        if include_metadata:
            if "invoice_number" in doc:
                allocation["invoice_number"] = _to_text(doc.get("invoice_number"))
            if "bill_number" in doc:
                allocation["bill_number"] = _to_text(doc.get("bill_number"))
            if "date" in doc:
                allocation["date"] = _to_text(doc.get("date"))
            if "due_date" in doc:
                allocation["due_date"] = _to_text(doc.get("due_date"))
            if "balance" in doc:
                allocation["balance"] = float(balance)

        allocations.append(allocation)
        remaining -= applied

    return allocations, remaining




def unwrap_record(
    response: object,
    candidate_keys: str | Sequence[str] = (),
) -> dict[str, object]:
    """Extract the primary record dictionary from a Zoho API response payload.

    Handles single-entity keys (e.g. 'salesorder', 'sales_order', 'payment', 'customerpayment',
    'invoice', 'creditnote', 'credit_note', 'bill', 'contact', 'item').
    """
    if not isinstance(response, Mapping):
        return {}

    keys = (candidate_keys,) if isinstance(candidate_keys, str) else candidate_keys
    # Check caller-provided candidate keys first
    for key in keys:
        val = response.get(key)
        if isinstance(val, dict):
            return dict(val)

    # Common Zoho Books single record entity keys
    common_keys = (
        "salesorder",
        "sales_order",
        "payment",
        "customerpayment",
        "customer_payment",
        "invoice",
        "creditnote",
        "credit_note",
        "bill",
        "vendorpayment",
        "vendor_payment",
        "contact",
        "customer",
        "vendor",
        "item",
        "bankaccount",
        "bank_account",
        "data",
    )
    for key in common_keys:
        val = response.get(key)
        if isinstance(val, dict):
            return val

    # Return copy of response dict if no wrapper key found
    return dict(response)


def find_transaction_by_number(
    resource: object,
    number: str,
    number_keys: Sequence[str] = (
        "reference_number",
        "salesorder_number",
        "invoice_number",
        "payment_number",
        "creditnote_number",
        "bill_number",
    ),
    resource_key: str | None = None,
) -> dict[str, object] | None:
    """Look up a transaction in a Books resource (sales_orders, invoices, customer_payments, etc.) by reference or number."""
    target = str(number or "").strip()
    if not target:
        return None

    # Try querying via reference_number parameter
    try:
        if hasattr(resource, "list_all"):
            records = getattr(resource, "list_all")(params={"reference_number": target}, resource_key=resource_key)
        elif hasattr(resource, "list_iter"):
            records = list(getattr(resource, "list_iter")(params={"reference_number": target}, resource_key=resource_key))
        elif hasattr(resource, "list"):
            res = getattr(resource, "list")(params={"reference_number": target})
            records = res.get(resource_key or "data", []) if isinstance(res, dict) else []
        else:
            records = []

        if isinstance(records, (list, tuple)):
            for record in records:
                if isinstance(record, Mapping):
                    for key in number_keys:
                        if str(record.get(key) or "").strip() == target:
                            return dict(record)
    except Exception as exc:
        logger.warning(f"Error querying transaction by number '{target}': {exc}")

    return None
