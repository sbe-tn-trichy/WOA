"""Settle linked customer and vendor balances through a clearing bank account."""

from __future__ import annotations

import re
from utils.file_utils import json
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from math import isfinite
from collections.abc import Iterable, Mapping, Sequence

from helpers import (
    GSTIN_PATTERN,
    allocate_documents_fifo,
    fetch_open_bills,
    fetch_open_invoices,
    AmbiguousMatchError,
    resolve_bank_account_by_name,
    is_valid_gstin,
    normalize_gstin,
)
from ..core.checkpoint import write_atomic_json
from ..core.matching import to_decimal
from zoho.core_sdk.validation import require_record, require_records, require_text
from .contracts import (
    AmbiguousPair, BillAllocation, InvoiceAllocation, OffsetBooksClient,
    OffsetReport, OffsetTranche, PairSummary, SkippedOffset, FailedOffset,
)



class VendorCustomerOffsetError(RuntimeError):
    """Raised when a safe two-sided offset cannot be completed."""


@dataclass(frozen=True)
class VendorCustomerOffsetConfig:
    """Policy and posting settings for customer/vendor balance offsets."""

    bank_account_name: str = "Vendor To Customer"
    bank_account_id: str | None = None
    payment_mode: str = "banktransfer"
    reference_prefix: str = "Vendor-Customer Offset"
    dry_run: bool = True
    ensure_linked: bool = True
    vendor_id: str | None = None
    checkpoint_path: Path | None = None

    def __post_init__(self) -> None:
        if not self.bank_account_id and not self.bank_account_name.strip():
            raise ValueError("bank_account_id or bank_account_name is required.")
        if not self.payment_mode.strip():
            raise ValueError("payment_mode is required.")


def _decimal(value: object) -> Decimal:
    return to_decimal(value) or Decimal("0")


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _allocated_amount(value: object) -> float:
    """Narrow the shared allocator's existing wire amount without re-rounding it."""
    if not isinstance(value, float) or not isfinite(value):
        raise VendorCustomerOffsetError("Document allocation amount is invalid.")
    return value


def _contact_type(contact: Mapping[str, object]) -> str:
    return str(contact.get("contact_type") or "").strip().lower()


def _unique_gstin_pairs(
    contacts: Iterable[Mapping[str, object]],
) -> tuple[
    list[tuple[str, Mapping[str, object], Mapping[str, object]]],
    list[AmbiguousPair],
]:
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for contact in contacts:
        gstin = normalize_gstin(contact.get("gst_no"))
        if gstin:
            grouped[gstin].append(contact)

    pairs: list[tuple[str, Mapping[str, object], Mapping[str, object]]] = []
    skipped: list[AmbiguousPair] = []
    for gstin, matches in grouped.items():
        customers = [item for item in matches if _contact_type(item) == "customer"]
        vendors = [item for item in matches if _contact_type(item) == "vendor"]
        if not customers or not vendors:
            continue
        if (
            not is_valid_gstin(gstin)
            or len(matches) != 2
            or len(customers) != 1
            or len(vendors) != 1
        ):
            skipped.append(
                {
                    "gstin": gstin,
                    "reason": "ambiguous_gstin",
                    "customer_count": len(customers),
                    "vendor_count": len(vendors),
                }
            )
            continue
        pairs.append((gstin, customers[0], vendors[0]))
    return pairs, skipped


def _resolve_bank_account_id(books_client: OffsetBooksClient, config: VendorCustomerOffsetConfig) -> str:
    if config.bank_account_id:
        return config.bank_account_id

    try:
        account = resolve_bank_account_by_name(books_client.bank_accounts, config.bank_account_name)
    except AmbiguousMatchError as exc:
        raise VendorCustomerOffsetError(f"Ambiguous clearing bank account {config.bank_account_name!r}: {exc}") from exc
    if not account:
        raise VendorCustomerOffsetError(
            f"Expected exactly one bank account named {config.bank_account_name!r}; found 0."
        )
    account_id = str(account.get("account_id") or "")
    if not account_id:
        raise VendorCustomerOffsetError("The clearing bank account has no account_id.")
    return account_id


def _document_sort_key(document: Mapping[str, object]) -> tuple[str, str, str]:
    return (
        str(document.get("due_date") or "9999-12-31"),
        str(document.get("date") or "9999-12-31"),
        str(document.get("invoice_id") or document.get("bill_id") or ""),
    )


def _allocate_documents(
    documents: Sequence[Mapping[str, object]],
    amount: Decimal,
    id_key: str,
) -> tuple[list[dict[str, object]], Decimal]:
    if amount <= 0:
        return [], Decimal("0")
    allocations, remaining = allocate_documents_fifo(amount, documents, id_key=id_key)
    return require_records(allocations, "Document allocations"), remaining


def _build_bill_payment_tranches(
    invoices: Sequence[Mapping[str, object]],
    bills: Sequence[Mapping[str, object]],
    amount: Decimal,
) -> tuple[list[OffsetTranche], Decimal, str]:
    """Split an offset into one same-dated payment pair per vendor bill."""
    invoice_allocations, invoice_remaining = _allocate_documents(
        invoices, amount, "invoice_id"
    )
    bill_allocations, bill_remaining = _allocate_documents(bills, amount, "bill_id")
    if invoice_remaining or bill_remaining:
        return [], max(invoice_remaining, bill_remaining), "insufficient_open_documents"

    typed_bills = [BillAllocation(
        bill_id=require_text(row.get("bill_id"), "Allocated bill ID"),
        amount_applied=_allocated_amount(row.get("amount_applied")),
    ) for row in bill_allocations]
    typed_invoices = [InvoiceAllocation(
        invoice_id=require_text(row.get("invoice_id"), "Allocated invoice ID"),
        amount_applied=_allocated_amount(row.get("amount_applied")),
    ) for row in invoice_allocations]
    bill_by_id = {str(item.get("bill_id") or ""): item for item in bills}
    invoice_index = 0
    invoice_available = (
        _money(_decimal(typed_invoices[0]["amount_applied"]))
        if typed_invoices
        else Decimal("0")
    )
    tranches: list[OffsetTranche] = []
    for bill_allocation in typed_bills:
        bill_id = str(bill_allocation["bill_id"])
        bill = bill_by_id[bill_id]
        try:
            payment_date = date.fromisoformat(str(bill.get("date") or ""))
        except ValueError:
            return [], amount, "missing_vendor_invoice_date"

        tranche_amount = _money(_decimal(bill_allocation["amount_applied"]))
        tranche_remaining = tranche_amount
        tranche_invoices: list[InvoiceAllocation] = []
        while tranche_remaining > 0 and invoice_index < len(typed_invoices):
            applied = min(invoice_available, tranche_remaining)
            tranche_invoices.append(
                {
                    "invoice_id": typed_invoices[invoice_index]["invoice_id"],
                    "amount_applied": float(applied),
                }
            )
            tranche_remaining = _money(tranche_remaining - applied)
            invoice_available = _money(invoice_available - applied)
            if invoice_available == 0:
                invoice_index += 1
                if invoice_index < len(typed_invoices):
                    invoice_available = _money(
                        _decimal(typed_invoices[invoice_index]["amount_applied"])
                    )

        if tranche_remaining:
            return [], tranche_remaining, "insufficient_open_documents"
        tranches.append(
            {
                "amount": tranche_amount,
                "payment_date": payment_date,
                "invoice_allocations": tranche_invoices,
                "bill_allocations": [bill_allocation],
            }
        )
    return tranches, Decimal("0"), ""


def _open_documents(books_client: OffsetBooksClient, customer_id: str, vendor_id: str) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    return (
        require_records(fetch_open_invoices(books_client, customer_id), "Open invoices"),
        require_records(fetch_open_bills(books_client, vendor_id), "Open bills"),
    )


def _ensure_linked(books_client: OffsetBooksClient, customer_id: str, vendor_id: str) -> str:
    """Ensure the pair is linked using the Books web-client endpoint.

    Zoho's public OpenAPI does not publish this operation. The live Books client
    uses POST /customers/{customer_id}/link with form-encoded vendor_id. Code
    3051 is the idempotent "already linked" response.
    """
    try:
        response = books_client.request(
            "POST",
            f"customers/{customer_id}/link",
            data={"vendor_id": vendor_id},
        )
    except Exception as exc:
        message = str(exc)
        if '"code":3051' in message or "already linked" in message.lower():
            return "already_linked"
        raise VendorCustomerOffsetError(
            f"Could not verify the customer/vendor link: {message}"
        ) from exc
    response = require_record(response, "Customer/vendor link response")
    if response.get("code") == 0:
        return "linked"
    raise VendorCustomerOffsetError(
        f"Could not link customer/vendor pair: {response.get('message', 'unknown error')}"
    )


def _payment_id(response: object, container: str) -> str:
    envelope = require_record(response, "Payment response")
    payment = require_record(envelope.get(container) or envelope.get("payment") or {}, "Created payment")
    return str(payment.get("payment_id") or payment.get("vendorpayment_id") or "")


def _reference_number(prefix: str, bill_id: str) -> str:
    """Build a bill-specific reference within Books' live 50-character limit."""
    return f"{prefix.strip()} {bill_id}"[:50]


def _allocation_signature(value: object, id_key: str) -> list[tuple[str, Decimal]]:
    return sorted((require_text(row.get(id_key), "Recovery allocation ID"),
                   _money(_decimal(row.get("amount_applied"))))
                  for row in require_records(value, "Recovery allocations"))


def _reconcile_operation(books_client: OffsetBooksClient, operation: dict[str, object]) -> None:
    """Read both sides of saved intent; absence is never proof of rejection."""
    for side, resource, container, contact, account, allocations in (
        ("customer", books_client.customer_payments, "payment", "customer_id", "account_id", "invoices"),
        ("vendor", books_client.vendor_payments, "vendorpayment", "vendor_id", "paid_through_account_id", "bills"),
    ):
        payload = require_record(operation.get(f"{side}_payload"), "Saved payment intent")
        known_id = operation.get(f"{side}_payment_id")
        if isinstance(known_id, str) and known_id:
            ids = [known_id]
        else:
            candidates = require_records(resource.list_all(params={
                contact: payload[contact], "reference_number": payload["reference_number"],
            }), "Recovery payment candidates")
            ids = [require_text(row.get("payment_id") or row.get("vendorpayment_id"), "Recovery payment ID")
                   for row in candidates if row.get("reference_number") == payload["reference_number"]
                   and row.get(contact) == payload[contact]]
        matches: list[str] = []
        for payment_id in ids:
            response = require_record(resource.get(payment_id), "Recovery payment response")
            record = require_record(response.get(container) or response.get("payment"), "Recovery payment")
            id_key = "invoice_id" if side == "customer" else "bill_id"
            if (str(record.get("payment_id") or record.get("vendorpayment_id") or "") == payment_id
                and str(record.get("status") or "").lower() not in {"void", "voided", "deleted", "refunded"}
                and all(str(record.get(key) or "") == str(payload[key]) for key in
                    (contact, account, "reference_number", "date"))
                and _decimal(record.get("amount")) == _decimal(payload["amount"])
                and _allocation_signature(record.get(allocations), id_key)
                == _allocation_signature(payload[allocations], id_key)):
                matches.append(payment_id)
        if len(matches) != 1:
            raise VendorCustomerOffsetError(
                f"Existing offset intent: cannot uniquely verify {side} payment; "
                "live reconciliation required. No automatic retry or rollback is safe."
            )
        operation[f"{side}_payment_id"] = matches[0]
    operation["state"] = "paired"


def _run_vendor_customer_offset(
    books_client: OffsetBooksClient,
    config: VendorCustomerOffsetConfig | None = None,
) -> OffsetReport:
    """Create paired, fully-applied payments for linked customer/vendor contacts.

    Contacts are paired only when a valid GSTIN occurs exactly once as a customer
    and exactly once as a vendor. Payments are applied oldest-due-first. A pair
    is skipped if either balance is non-positive, currencies differ, or open
    documents cannot absorb the calculated offset completely.
    """
    config = config or VendorCustomerOffsetConfig()
    journal: dict[str, object] = {}
    operations: list[dict[str, object]] = []
    if not config.dry_run:
        assert config.checkpoint_path is not None
        scope = {"organization_id": books_client.organization_id, "domain": books_client.domain}
        if not all(isinstance(value, str) and value.strip() for value in scope.values()):
            raise VendorCustomerOffsetError("Explicit Books organization and domain are required.")
        if config.checkpoint_path.exists():
            journal = require_record(json.loads(config.checkpoint_path.read_text(encoding="utf-8")), "Offset checkpoint")
            if journal.get("scope") != scope:
                raise VendorCustomerOffsetError("Offset checkpoint organization/domain does not match this client.")
            operations = require_records(journal.get("operations"), "Offset checkpoint operations")
            for saved_operation in operations:
                _reconcile_operation(books_client, saved_operation)
        else:
            journal = {"scope": scope, "operations": operations}
        write_atomic_json(config.checkpoint_path, journal)
    bank_account_id = _resolve_bank_account_id(books_client, config)
    contacts = require_records(books_client.contacts.list_all(params={"filter_by": "Status.Active"}), "Offset contacts")
    pairs, skipped = _unique_gstin_pairs(contacts)
    if config.vendor_id:
        pairs = [
            pair
            for pair in pairs
            if str(pair[2].get("contact_id") or "") == config.vendor_id
        ]
    results: OffsetReport = {
        "dry_run": config.dry_run,
        "bank_account_id": bank_account_id,
        "candidate_pairs": len(pairs),
        "planned": [],
        "posted": [],
        "skipped": list(skipped),
        "failed": [],
        "summary": {"planned": 0, "posted": 0, "planned_customer_payments": 0,
                    "planned_vendor_payments": 0, "posted_customer_payments": 0,
                    "posted_vendor_payments": 0, "skipped": 0, "failed": 0},
    }

    for gstin, customer, vendor in pairs:
        if results["failed"]:
            break
        customer_id = str(customer.get("contact_id") or "")
        vendor_id = str(vendor.get("contact_id") or "")
        customer_currency = str(customer.get("currency_code") or "")
        vendor_currency = str(vendor.get("currency_code") or "")
        receivable = _money(_decimal(customer.get("outstanding_receivable_amount")))
        payable = _money(_decimal(vendor.get("outstanding_payable_amount")))
        amount = min(receivable, payable)
        pair_summary: PairSummary = {
            "gstin": gstin,
            "customer_id": customer_id,
            "vendor_id": vendor_id,
            "amount": float(amount),
        }

        if not customer_id or not vendor_id:
            results["skipped"].append(SkippedOffset(gstin=gstin, customer_id=customer_id, vendor_id=vendor_id, amount=float(amount), reason="missing_contact_id"))
            continue
        if customer_currency != vendor_currency:
            results["skipped"].append(SkippedOffset(gstin=gstin, customer_id=customer_id, vendor_id=vendor_id, amount=float(amount), reason="currency_mismatch"))
            continue
        if amount <= 0:
            results["skipped"].append(SkippedOffset(gstin=gstin, customer_id=customer_id, vendor_id=vendor_id, amount=float(amount), reason="no_mutual_outstanding"))
            continue

        invoices, bills = _open_documents(books_client, customer_id, vendor_id)
        tranches, unallocated, tranche_error = _build_bill_payment_tranches(
            invoices, bills, amount
        )
        if tranche_error:
            results["skipped"].append(
                {
                    **pair_summary,
                    "reason": tranche_error,
                    "unallocated_amount": float(unallocated),
                }
            )
            continue

        if config.dry_run:
            for tranche in tranches:
                results["planned"].append(
                    {
                        **pair_summary,
                        "amount": float(tranche["amount"]),
                        "payment_date": tranche["payment_date"].isoformat(),
                        "invoice_allocations": tranche["invoice_allocations"],
                        "bill_allocations": tranche["bill_allocations"],
                        "link_status": "not_checked_in_dry_run",
                    }
                )
            continue

        try:
            link_status = (
                _ensure_linked(books_client, customer_id, vendor_id)
                if config.ensure_linked
                else "assumed_linked"
            )
        except Exception as exc:
            results["failed"].append(
                FailedOffset(gstin=gstin, customer_id=customer_id, vendor_id=vendor_id, amount=float(amount), error=str(exc), rollback="not_required")
            )
            continue

        for tranche in tranches:
            payment_date_text = tranche["payment_date"].isoformat()
            tranche_amount = tranche["amount"]
            bill_id = tranche["bill_allocations"][0]["bill_id"]
            if any(
                any(row.get("bill_id") == bill_id for row in require_records(
                    require_record(saved.get("vendor_payload"), "Saved vendor payload").get("bills"), "Saved bill allocations"))
                for saved in operations
            ):
                results["skipped"].append(SkippedOffset(
                    gstin=gstin, customer_id=customer_id, vendor_id=vendor_id,
                    amount=float(tranche_amount), reason="already_verified_in_checkpoint"
                ))
                continue
            reference = _reference_number(config.reference_prefix, bill_id)
            customer_payload: dict[str, object] = {
                "customer_id": customer_id,
                "payment_mode": config.payment_mode,
                "amount": float(tranche_amount),
                "date": payment_date_text,
                "account_id": bank_account_id,
                "reference_number": reference,
                "description": "Offset against linked vendor payable",
                "invoices": tranche["invoice_allocations"],
            }
            vendor_payload: dict[str, object] = {
                "vendor_id": vendor_id,
                "payment_mode": config.payment_mode,
                "amount": float(tranche_amount),
                "date": payment_date_text,
                "paid_through_account_id": bank_account_id,
                "reference_number": reference,
                "description": "Offset against linked customer receivable",
                "bills": tranche["bill_allocations"],
            }
            customer_payment_id = ""
            vendor_payment_id = ""
            operation: dict[str, object] = {
                "customer_payload": customer_payload, "vendor_payload": vendor_payload,
                "state": "customer_create_requested",
            }
            operations.append(operation)
            assert config.checkpoint_path is not None
            journal["operations"] = operations
            write_atomic_json(config.checkpoint_path, journal)
            try:
                customer_response = books_client.customer_payments.create(customer_payload)
                customer_payment_id = _payment_id(customer_response, "payment")
                if not customer_payment_id:
                    raise VendorCustomerOffsetError(
                        "Zoho did not return the created customer payment ID."
                    )
                operation.update(customer_payment_id=customer_payment_id, state="vendor_create_requested")
                write_atomic_json(config.checkpoint_path, journal)
                vendor_response = books_client.vendor_payments.create(vendor_payload)
                vendor_payment_id = _payment_id(vendor_response, "vendorpayment")
                if not vendor_payment_id:
                    raise VendorCustomerOffsetError(
                        "Zoho did not return the created vendor payment ID."
                    )
                operation.update(vendor_payment_id=vendor_payment_id, state="paired")
                write_atomic_json(config.checkpoint_path, journal)
                results["posted"].append(
                    {
                        **pair_summary,
                        "amount": float(tranche_amount),
                        "bill_id": bill_id,
                        "payment_date": payment_date_text,
                        "customer_payment_id": customer_payment_id,
                        "vendor_payment_id": vendor_payment_id,
                        "link_status": link_status,
                    }
                )
            except Exception as exc:
                operation.update(customer_payment_id=customer_payment_id,
                                 vendor_payment_id=vendor_payment_id, error=str(exc))
                write_atomic_json(config.checkpoint_path, journal)
                rollback = "withheld_pending_live_reconciliation"
                results["failed"].append(
                    {
                        **pair_summary,
                        "amount": float(tranche_amount),
                        "bill_id": bill_id,
                        "payment_date": payment_date_text,
                        "error": str(exc),
                        "rollback": rollback,
                        "customer_payment_id": customer_payment_id,
                        "vendor_payment_id": vendor_payment_id,
                    }
                )
                break

    results["summary"] = {
        "planned": len(results["planned"]),
        "posted": len(results["posted"]),
        "planned_customer_payments": len(results["planned"]),
        "planned_vendor_payments": len(results["planned"]),
        "posted_customer_payments": len(results["posted"]),
        "posted_vendor_payments": len(results["posted"]),
        "skipped": len(results["skipped"]),
        "failed": len(results["failed"]),
    }
    return results


def run_vendor_customer_offset(
    books_client: OffsetBooksClient,
    config: VendorCustomerOffsetConfig | None = None,
) -> OffsetReport:
    """Plan offsets or post with an exclusive, durable recovery checkpoint.

    Saved intent is reconciled with live detail reads before resuming. Missing or
    ambiguous payments require operator review, never automatic retry/rollback.
    """
    config = config or VendorCustomerOffsetConfig()
    if config.dry_run:
        return _run_vendor_customer_offset(books_client, config)
    if config.checkpoint_path is None:
        raise VendorCustomerOffsetError("Live offsets require an explicit checkpoint_path.")
    lock = config.checkpoint_path.with_suffix(config.checkpoint_path.suffix + ".lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise VendorCustomerOffsetError(
            f"Offset checkpoint is locked: {lock}. Reconcile interrupted work before removing the lock."
        ) from exc
    try:
        with handle:
            return _run_vendor_customer_offset(books_client, config)
    finally:
        lock.unlink()
