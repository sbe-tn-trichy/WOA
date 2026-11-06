"""Recover existing journaled pairs without creating or replaying documents."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Protocol, Sequence
import json
import re
import time

from workflows.core.checkpoint import write_atomic_json
from zoho.validation import require_record, require_records, require_text
from .processor import number, stocks


class RecoveryInvoices(Protocol):
    def get(self, resource_id: str) -> object: ...
    def mark_as_sent(self, invoice_id: str) -> object: ...


class RecoveryBills(Protocol):
    def get(self, resource_id: str) -> object: ...
    def mark_as_open(self, bill_id: str) -> object: ...


class RecoveryBooks(Protocol):
    @property
    def invoices(self) -> RecoveryInvoices: ...
    @property
    def bills(self) -> RecoveryBills: ...


class RecoveryItems(Protocol):
    def get_details(self, item_ids: Sequence[str]) -> object: ...
    def list_bins(self, item_id: str, location_id: str) -> object: ...


class RecoveryInventory(Protocol):
    @property
    def items(self) -> RecoveryItems: ...


@dataclass(frozen=True)
class TransferRecoveryPolicy:
    reference: str
    expected_pairs: int
    maximum_invoice_total: Decimal
    source: str
    destination: str
    customer_id: str
    vendor_id: str
    purchase_account_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.reference):
            raise ValueError("Reference must use letters, digits, hyphens or underscores")
        if self.expected_pairs < 1 or not self.maximum_invoice_total.is_finite() or self.maximum_invoice_total <= 0:
            raise ValueError("Positive expected pair count and finite positive maximum total required")
        if (not all((self.source, self.destination, self.customer_id, self.vendor_id))
                or self.source == self.destination or not self.purchase_account_ids
                or any(not account for account in self.purchase_account_ids)):
            raise ValueError("Explicit different locations, contacts and purchase accounts required")


@dataclass(frozen=True)
class TransferRecoveryResult:
    reference: str
    pairs: int
    applied: bool


def _detail(resource: RecoveryInvoices | RecoveryBills, key: str, identifier: str) -> dict[str, object]:
    response = require_record(resource.get(identifier), key + " response")
    record = require_record(response.get(key), key)
    if str(record.get(key + "_id")) != identifier:
        raise ValueError(f"{key} identity mismatch for {identifier}")
    return record


def _lines(document: dict[str, object]) -> dict[str, dict[str, object]]:
    rows = require_records(document.get("line_items"), "Transfer lines")
    result = {require_text(row.get("item_id"), "Item ID"): row for row in rows}
    if not result or len(result) != len(rows):
        raise ValueError("Missing or duplicate transfer item lines")
    return result


def _verify_pair(books: RecoveryBooks, row: dict[str, object], index: int,
                 policy: TransferRecoveryPolicy, *, posted: bool = False,
                 invoice_posted: bool = False) -> tuple[dict[str, object], dict[str, object]]:
    invoice = _detail(books.invoices, "invoice", require_text(row.get("invoice_id"), "Invoice ID"))
    bill = _detail(books.bills, "bill", require_text(row.get("bill_id"), "Bill ID"))
    reference = f"{policy.reference}-{index:03d}"
    for kind, doc, location, contact in (
        ("invoice", invoice, policy.source, policy.customer_id),
        ("bill", bill, policy.destination, policy.vendor_id),
    ):
        if (doc.get("reference_number") != reference or doc.get("location_id") != location
                or doc.get("customer_id" if kind == "invoice" else "vendor_id") != contact
                or doc.get("date") != row.get("date")):
            raise ValueError(f"{kind} scope/reference/date mismatch for pair {index}")
    invoice_status = invoice.get("status")
    if invoice_status not in ({"sent", "overdue", "partially_paid", "paid"} if posted or invoice_posted else {"draft"}):
        raise ValueError(f"Unexpected invoice status for pair {index}: {invoice_status}")
    if bill.get("status") not in ({"open", "overdue"} if posted else {"draft", "open", "overdue"}):
        raise ValueError(f"Unexpected bill status for pair {index}: {bill.get('status')}")
    total = number(invoice.get("total"))
    if total <= 0 or total > policy.maximum_invoice_total or total != number(bill.get("total")) or total != number(row.get("total")):
        raise ValueError(f"Total mismatch or cap violation for pair {index}")
    expected_number = require_text(row.get("invoice_number"), "Recorded invoice number")
    if invoice.get("invoice_number") != expected_number or bill.get("bill_number") != expected_number:
        raise ValueError(f"Document number mismatch for pair {index}")
    left, right = _lines(invoice), _lines(bill)
    if set(left) != set(right):
        raise ValueError(f"Paired item IDs differ for pair {index}")
    for item_id, line in left.items():
        other = right[item_id]
        if (number(line.get("quantity")) <= 0 or number(line.get("rate")) < 0
                or any(number(line.get(key)) != number(other.get(key)) for key in ("quantity", "rate"))
                or line.get("tax_id") != other.get("tax_id")):
            raise ValueError(f"Paired quantity/rate/tax differs for {item_id}")
        if line.get("location_id") != policy.source or other.get("location_id") != policy.destination:
            raise ValueError(f"Line location differs for {item_id}")
    return invoice, bill


def _stock_check(inventory: RecoveryInventory, invoices: Sequence[dict[str, object]],
                 policy: TransferRecoveryPolicy, *, after: bool = False) -> None:
    quantities: dict[str, Decimal] = defaultdict(Decimal)
    allocations: dict[str, dict[str, Decimal]] = {}
    for invoice in invoices:
        for item_id, line in _lines(invoice).items():
            quantities[item_id] += number(line.get("quantity"))
            storages = require_records(line.get("storages", []), "Recorded bin allocations")
            for storage in storages:
                key = require_text(storage.get("storage_id"), "Storage ID")
                amount = number(storage.get("out_quantity"))
                if amount <= 0:
                    raise ValueError("Bin quantities must be positive")
                target = allocations.setdefault(item_id, {})
                target[key] = target.get(key, Decimal(0)) + amount
    details = require_records(inventory.items.get_details(list(quantities)), "Inventory details")
    by_id = {require_text(item.get("item_id"), "Inventory item ID"): item for item in details}
    if len(by_id) != len(details) or set(by_id) != set(quantities):
        raise ValueError("Incomplete or duplicate Inventory response")
    for item_id, item in by_id.items():
        if item.get("purchase_account_id") not in policy.purchase_account_ids:
            raise ValueError(f"Item outside purchase-account scope: {item_id}")
        if item.get("track_batch_number") or item.get("track_serial_number"):
            raise ValueError(f"Batch/serial recovery is unsupported for {item_id}")
        on_hand, _, cap = stocks(item, policy.source, policy.destination)
        if after:
            if on_hand < 0:
                raise ValueError(f"Negative source stock after recovery for {item_id}")
            continue
        if quantities[item_id] > cap:
            raise ValueError(f"Insufficient source stock for {item_id}")
        locations = require_records(item.get("locations"), "Item locations")
        source = next(loc for loc in locations if loc.get("location_id") == policy.source)
        if source.get("is_storage_location_enabled") or item_id in allocations:
            if sum(allocations.get(item_id, {}).values()) != quantities[item_id]:
                raise ValueError(f"Incomplete bin allocation for {item_id}")
            time.sleep(1.0)
            bins = require_records(inventory.items.list_bins(item_id, policy.source), "Live bins")
            index = {require_text(b.get("storage_id"), "Bin ID"): b for b in bins}
            if len(index) != len(bins):
                raise ValueError("Duplicate live bins")
            for bin_id, quantity in allocations[item_id].items():
                live = index.get(bin_id, {})
                if (live.get("location_id") != policy.source or live.get("status") != 1
                        or number(live.get("balance_quantity")) < quantity):
                    raise ValueError(f"Bin stock changed for {item_id}/{bin_id}")
    # Refresh location balances after any paced bin reads, before permitting posting.
    if not after and allocations:
        refreshed = require_records(inventory.items.get_details(list(quantities)), "Fresh Inventory details")
        fresh = {require_text(i.get("item_id"), "Fresh item ID"): i for i in refreshed}
        if len(fresh) != len(refreshed) or set(fresh) != set(quantities):
            raise ValueError("Incomplete fresh Inventory response")
        for item_id, item in fresh.items():
            if item.get("purchase_account_id") not in policy.purchase_account_ids or quantities[item_id] > stocks(item, policy.source, policy.destination)[2]:
                raise ValueError(f"Source stock/scope changed for {item_id}")


def recover_stock_transfer(
    books: RecoveryBooks, inventory: RecoveryInventory, *, journal: Path,
    policy: TransferRecoveryPolicy, apply: bool = False,
) -> TransferRecoveryResult:
    """Preview/post a bill_aligned journal; uncertain/attempted recovery cannot replay.

    All pairs must still have draft invoices. Existing open bills are preserved.
    No documents are created, deleted, renumbered or compensated. Use while idle;
    local checkpoints do not coordinate other machines or concurrent stock writers.
    """
    raw = journal.read_bytes()
    state = require_record(json.loads(raw), "Transfer journal")
    if state.get("reference") != policy.reference or state.get("stage") != "bill_aligned":
        raise ValueError("Recovery requires the matching bill_aligned journal; inspect live state before retrying")
    completed = require_records(state.get("completed", []), "Completed pairs")
    invoice = require_record(state.get("invoice"), "Current invoice")
    bill = require_record(state.get("bill"), "Current bill")
    completed.append({"invoice_id": invoice.get("invoice_id"), "invoice_number": invoice.get("invoice_number"),
                      "bill_id": bill.get("bill_id"), "total": invoice.get("total"), "date": invoice.get("date")})
    if len(completed) != policy.expected_pairs:
        raise ValueError(f"Expected {policy.expected_pairs} pairs, found {len(completed)}")
    for key in ("invoice_id", "bill_id"):
        ids = [require_text(row.get(key), key) for row in completed]
        if len(set(ids)) != len(ids):
            raise ValueError(f"Duplicate recorded {key}")
    for row in completed:
        date.fromisoformat(require_text(row.get("date"), "Recorded transaction date"))
    invoices = [_verify_pair(books, row, index, policy)[0] for index, row in enumerate(completed, 1)]
    _stock_check(inventory, invoices, policy)
    if not apply:
        return TransferRecoveryResult(policy.reference, len(completed), False)
    if journal.read_bytes() != raw:
        raise ValueError("Journal changed during preflight; rerun recovery")
    state["completed"] = completed

    def checkpoint(stage: str, pair: int | None) -> None:
        state.update(stage=stage, current_pair=pair)
        write_atomic_json(journal, state)

    # Persist the reviewed scope as well as intent before any remote write.
    state["recovery_policy"] = {
        "source": policy.source, "destination": policy.destination, "customer_id": policy.customer_id,
        "vendor_id": policy.vendor_id, "purchase_account_ids": policy.purchase_account_ids,
        "maximum_invoice_total": policy.maximum_invoice_total, "expected_pairs": policy.expected_pairs,
    }
    checkpoint("recovery_verified", None)
    for index, row in enumerate(completed, 1):
        current_invoice, _ = _verify_pair(books, row, index, policy)
        _stock_check(inventory, [current_invoice], policy)
        checkpoint("recovery_posting_invoice", index)
        books.invoices.mark_as_sent(require_text(row["invoice_id"], "Invoice ID"))
        _, current_bill = _verify_pair(books, row, index, policy, invoice_posted=True)
        if current_bill.get("status") == "draft":
            checkpoint("recovery_posting_bill", index)
            books.bills.mark_as_open(require_text(row["bill_id"], "Bill ID"))
        _verify_pair(books, row, index, policy, posted=True)
        checkpoint("recovery_pair_verified", index)
    _stock_check(inventory, invoices, policy, after=True)
    checkpoint("complete", None)
    return TransferRecoveryResult(policy.reference, len(completed), True)
