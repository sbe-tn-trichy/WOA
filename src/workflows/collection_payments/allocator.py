"""Oldest-due-first invoice balance allocation for customer payments."""

from __future__ import annotations

from decimal import Decimal
from collections.abc import Mapping, MutableMapping, Sequence
from typing import Any

from zoho.core_sdk.validation import require_records, require_text
from workflows.collection_payments.types import InvoiceAllocation

from helpers import (
    CLOSED_DOCUMENT_STATUSES as CLOSED_INVOICE_STATUSES,
    allocate_documents_fifo,
    fetch_open_invoices,
)
from helpers.operations.transactions import BooksInvoicesClient
from workflows.runtime.exceptions import ReconciliationError
from workflows.core.matching import to_decimal as _decimal, to_text as _text


def allocate_invoices_oldest_due_first(
    payment_amount: object,
    open_invoices: Sequence[Mapping[str, object]],
) -> tuple[list[InvoiceAllocation], Decimal]:
    """Allocate a payment amount across open invoices sorted by due date and invoice date."""
    amount = _decimal(payment_amount)
    if amount is None or not amount.is_finite() or amount == 0:
        raise ReconciliationError("A non-zero payment amount is required.")

    for row in open_invoices:
        require_text(row.get("invoice_id"), "Open invoice ID")
        balance = _decimal(row.get("balance"))
        if balance is None or not balance.is_finite():
            raise ReconciliationError("Open invoice has an invalid balance.")
    raw_allocations, remaining = allocate_documents_fifo(
        abs(amount),
        open_invoices,
        id_key="invoice_id",
        include_metadata=True,
    )

    allocations: list[InvoiceAllocation] = []
    for row in require_records(raw_allocations, "Invoice allocations"):
        raw_applied = row.get("amount_applied")
        applied = _decimal(raw_applied)
        if not isinstance(raw_applied, float) or applied is None or not applied.is_finite():
            raise ReconciliationError("Invoice allocation has an invalid amount.")
        allocation = InvoiceAllocation(
            invoice_id=require_text(row.get("invoice_id"), "Allocated invoice ID"),
            amount_applied=raw_applied,
        )
        for key in ("invoice_number", "date", "due_date"):
            if key in row:
                # Literal assignments preserve the precise wire keys.
                value = require_text(row[key], f"Allocation {key}", allow_empty=True)
                if key == "invoice_number":
                    allocation["invoice_number"] = value
                elif key == "date":
                    allocation["date"] = value
                else:
                    allocation["due_date"] = value
        if "balance" in row:
            raw_balance = row["balance"]
            balance = _decimal(raw_balance)
            if not isinstance(raw_balance, float) or balance is None or not balance.is_finite():
                raise ReconciliationError("Invoice allocation has an invalid balance.")
            allocation["balance"] = raw_balance
        allocations.append(allocation)
    return allocations, remaining


def attach_invoice_preview(
    books_client: BooksInvoicesClient,
    entry: MutableMapping[str, Any],
    invoice_cache: dict[str, list[dict[str, object]]],
) -> None:
    """Populate FIFO open-invoice allocation preview fields on a review queue entry."""
    creator_data = entry.get("creator")
    creator = creator_data if isinstance(creator_data, Mapping) else {}
    customer_id = _text(creator.get("books_customer_id"))
    if not entry.get("bank") or not customer_id:
        entry.update(
            {
                "invoice_allocations": [],
                "unallocated_amount": float(abs(_decimal(creator.get("amount")) or Decimal("0"))),
                "allocation_status": "unavailable",
                "allocation_error": (
                    "Creator customer has no Zoho Books Customer_Id."
                    if entry.get("bank") and not customer_id
                    else ""
                ),
            }
        )
        entry["reviewable"] = False
        return
    try:
        if customer_id not in invoice_cache:
            invoice_cache[customer_id] = fetch_open_invoices(books_client, customer_id)
        allocations, unallocated = allocate_invoices_oldest_due_first(
            creator.get("amount"),
            invoice_cache[customer_id],
        )
    except Exception as exc:
        entry.update(
            {
                "invoice_allocations": [],
                "unallocated_amount": 0,
                "allocation_status": "unavailable",
                "allocation_error": f"Could not load open invoices: {exc}",
                "reviewable": False,
            }
        )
        return
    entry.update(
        {
            "invoice_allocations": allocations,
            "unallocated_amount": float(unallocated),
            "allocation_status": (
                "fully_allocated"
                if unallocated == 0
                else "partially_allocated"
                if allocations
                else "no_open_invoices"
            ),
            "allocation_error": (
                "No open customer invoices are available; push is blocked to prevent "
                "unused credit."
                if not allocations
                else ""
            ),
            "reviewable": bool(allocations),
        }
    )
