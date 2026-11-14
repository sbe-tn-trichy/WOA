"""Oldest-invoice-date-first allocation with customer/location scope and reservations."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from helpers import CLOSED_DOCUMENT_STATUSES
from workflows.core.matching import parse_date, to_decimal
from .planning import CashTransferError, CashTransferPlan, numeric, record


def nonnegative(value: Any, label: str) -> Decimal:
    amount = to_decimal(value)
    if amount is None or not amount.is_finite() or amount < 0 or amount != amount.quantize(Decimal("0.01")):
        raise CashTransferError(f"Invalid {label}: {value!r}")
    return amount


def application_totals(rows: Any) -> dict[str, Decimal]:
    if not isinstance(rows, list):
        raise CashTransferError("Invalid payment invoice applications")
    totals = {}
    for row in rows:
        if not isinstance(row, dict):
            raise CashTransferError("Invalid invoice application record")
        key = numeric(row.get("invoice_id"))
        if key in totals:
            raise CashTransferError("Duplicate invoice application")
        if any(nonnegative(row.get(field, 0), field) for field in ("tax_amount_withheld", "discount_amount")):
            raise CashTransferError("Withholding/discount applications require separate review")
        totals[key] = nonnegative(row.get("amount_applied"), "invoice application")
    return totals


@dataclass(frozen=True)
class AllocationPlan:
    before: dict[str, Decimal]
    after: dict[str, Decimal]
    unused_before: Decimal
    unused_after: Decimal
    invoices: list[dict[str, Any]]

    def payload(self) -> dict[str, Any]:
        return {"invoices": [{"invoice_id": key, "amount_applied": float(amount)}
                             for key, amount in self.after.items()]}


def _open_invoices(books: Any, customer_id: str, location_id: str) -> list[dict[str, Any]]:
    rows = books.invoices.list_all(params={"customer_id": customer_id, "location_id": location_id})
    if not isinstance(rows, list):
        raise CashTransferError("Invalid Books invoice list")
    invoices = []
    seen = set()
    for raw in rows:
        if not isinstance(raw, dict):
            raise CashTransferError("Invalid Books invoice record")
        row = dict(raw)
        key = numeric(row.get("invoice_id"))
        if key in seen:
            raise CashTransferError("Duplicate invoice in Books response")
        seen.add(key)
        if not row.get("customer_id") or not row.get("location_id"):
            row = record(books.invoices.get(key), "invoice", 0)
        if str(row.get("invoice_id")) != key or str(row.get("customer_id")) != customer_id:
            raise CashTransferError(f"Invoice {key} is outside the selected customer")
        balance = nonnegative(row.get("balance"), "invoice balance")
        # Books can ignore the location filter on this list endpoint. Enforce
        # the selected location locally; another valid location is not a match.
        if numeric(row.get("location_id")) != location_id:
            continue
        if str(row.get("status", "")).casefold() in CLOSED_DOCUMENT_STATUSES or balance == 0:
            continue
        if not row.get("status"):
            raise CashTransferError(f"Invoice {key} has no status")
        day = parse_date(row.get("date"))
        if day is None:
            raise CashTransferError(f"Invoice {key} has an invalid invoice date")
        row.update(date=day.isoformat(), balance=balance)
        invoices.append(row)
    # This rule is invoice age, distinct from the collection review's due-date FIFO.
    return sorted(invoices, key=lambda r: (r["date"], str(r.get("due_date") or "9999-12-31"), int(r["invoice_id"])))


def plan_invoice_allocations(
    books: Any, plan: CashTransferPlan, payment_records: dict[str, dict[str, Any]],
) -> dict[str, AllocationPlan]:
    """Preserve prior applications and reserve shared balances across selected payments."""
    cache: dict[str, list[dict[str, Any]]] = {}
    result = {}
    for payment in sorted(plan.payments, key=lambda p: (p.date, int(p.creator_id))):
        native = payment_records.get(payment.creator_id)
        before = application_totals(native.get("invoices", [])) if native else {}
        unused = nonnegative(native.get("unused_amount"), "unused payment amount") if native else payment.amount
        refunded = nonnegative(native.get("amount_refunded", 0), "refunded payment amount") if native else Decimal(0)
        if sum(before.values(), Decimal(0)) + unused + refunded != payment.amount:
            raise CashTransferError(f"Payment {payment.creator_id} applications/unused/refund do not reconcile")
        remaining = unused
        after = dict(before)
        selected = []
        if remaining:
            if payment.customer_id not in cache:
                cache[payment.customer_id] = _open_invoices(books, payment.customer_id, plan.location_id)
            for invoice in cache[payment.customer_id]:
                if not remaining:
                    break
                allocated = min(remaining, invoice["balance"])
                if not allocated:
                    continue
                key = str(invoice["invoice_id"])
                after[key] = after.get(key, Decimal(0)) + allocated
                selected.append({"invoice_id": key, "invoice_number": invoice.get("invoice_number", ""),
                                 "date": invoice["date"], "amount_applied": str(allocated),
                                 "balance_before": str(invoice["balance"])})
                invoice["balance"] -= allocated
                remaining -= allocated
        result[payment.creator_id] = AllocationPlan(before, after, unused, remaining, selected)
    return result


def verify_allocations(payment: dict[str, Any], expected: AllocationPlan) -> None:
    if (application_totals(payment.get("invoices", [])) != expected.after
            or nonnegative(payment.get("unused_amount"), "unused payment amount") != expected.unused_after):
        raise CashTransferError("Books invoice allocation read-back differs from the approved plan")


def verify_invoice_balances(
    books: Any, allocation: AllocationPlan, *, customer_id: str, location_id: str, after: bool,
) -> None:
    """Detect changed balances before mutation and verify affected invoices afterward."""
    for planned in allocation.invoices:
        key = planned["invoice_id"]
        invoice = record(books.invoices.get(key), "invoice", 0)
        expected = Decimal(planned["balance_before"])
        if after:
            expected -= Decimal(planned["amount_applied"])
        if (str(invoice.get("invoice_id")) != key or str(invoice.get("customer_id")) != customer_id
                or str(invoice.get("location_id")) != location_id
                or nonnegative(invoice.get("balance"), "live invoice balance") != expected):
            raise CashTransferError(f"Invoice {key} scope/balance changed {'after' if after else 'before'} allocation")
