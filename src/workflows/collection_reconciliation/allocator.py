"""Oldest-due-first invoice balance allocation for customer payments."""

from __future__ import annotations

from decimal import Decimal
from collections.abc import Mapping, Sequence

from zoho.validation import require_records, require_text
from .types import InvoiceAllocation

from zoho.helpers import (
    CLOSED_DOCUMENT_STATUSES as CLOSED_INVOICE_STATUSES,
    allocate_documents_fifo,
    fetch_open_invoices,
)
from ..core.exceptions import ReconciliationError
from ..core.matching import to_decimal as _decimal, to_text as _text


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
