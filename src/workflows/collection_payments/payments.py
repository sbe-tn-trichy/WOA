"""Shared Books customer-payment payload fields for Creator collections."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from collections.abc import Mapping, Sequence
from typing import Any

from helpers import find_bank_match_candidate, match_bank_transaction
from workflows.collection_payments.identifiers import identifier, identifiers
from workflows.core.matching import parse_date, to_decimal, to_text
from workflows.runtime.exceptions import ReconciliationError


def customer_payment_payload(
    *,
    customer_id: str,
    payment_mode: str,
    payment_date: date | None,
    amount: Decimal | None,
    reference_number: str,
    description: str,
    account_id: str,
    creator_record_id: str,
    creator_payment_id: object = None,
    invoices: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    if not payment_date or amount is None:
        raise ReconciliationError("A valid payment date and amount are required.")
    custom_fields: list[dict[str, object]] = [{"label": "Creator Record ID", "value": creator_record_id}]
    if creator_payment_id not in (None, ""):
        custom_fields.append({"label": "Creator Payment ID", "value": creator_payment_id})
    payload: dict[str, object] = {
        "customer_id": customer_id,
        "payment_mode": payment_mode,
        "date": payment_date.isoformat(),
        "amount": float(abs(amount)),
        "reference_number": reference_number,
        "description": description,
        "account_id": account_id,
        "custom_fields": custom_fields,
    }
    if invoices is not None:
        payload["invoices"] = [
            {"invoice_id": row["invoice_id"], "amount_applied": row["amount_applied"]}
            for row in invoices
        ]
    return payload


def review_customer_payment_payload(
    entry: Mapping[str, Any],
    allocations: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a Books customer-payment payload from a human-review queue entry."""
    creator = entry["creator"]
    is_cheque = to_text(entry.get("payment_type")).casefold() == "cheque"
    payment_date = parse_date(entry["bank"].get("date") if is_cheque else creator.get("date"))
    return customer_payment_payload(
        customer_id=creator["books_customer_id"],
        payment_mode="check" if is_cheque else "banktransfer",
        payment_date=payment_date,
        amount=to_decimal(creator.get("amount")),
        reference_number=creator["reference"],
        description=entry["bank"].get("description") or "Creator reconciliation",
        account_id=entry["bank_account_id"],
        creator_record_id=entry["id"],
        creator_payment_id=creator.get("payment_id") or None,
        invoices=allocations,
    )


def create_customer_payment_and_resolve(
    books_client: Any,
    payload: Mapping[str, Any],
) -> tuple[str, str]:
    """Create a Books customer payment and return ``(payment_id, payment_number)``."""
    response = books_client.customer_payments.create(dict(payload))
    books_payment_id = identifier(
        response,
        ("payment_id", "customer_payment_id", "transaction_id"),
    ) or ""
    if not books_payment_id:
        raise ReconciliationError(
            "Books created a customer payment but returned no payment ID."
        )
    books_payment_number = identifier(response, ("payment_number",)) or ""
    return books_payment_id, books_payment_number


def match_books_payment_to_bank(
    books_client: Any,
    bank_id: str,
    books_payment_id: str,
    *,
    check_invoice_applications: bool = True,
) -> None:
    """Resolve a created Books payment (or its invoice application) and match the bank line."""
    candidate = find_bank_match_candidate(books_client, bank_id, books_payment_id)
    if not candidate and check_invoice_applications:
        application_ids = identifiers(
            books_client.customer_payments.get(books_payment_id),
            ("invoice_payment_id",),
        )
        candidate = find_bank_match_candidate(
            books_client,
            bank_id,
            books_payment_id,
            fallback_ids=sorted(application_ids),
        )
    if not candidate:
        raise ReconciliationError("The created Books customer payment is not a bank match candidate.")
    if not to_text(candidate.get("transaction_type")):
        raise ReconciliationError("The Books match candidate has no transaction_type.")
    try:
        match_bank_transaction(books_client, bank_id, candidate)
    except ValueError as exc:
        raise ReconciliationError(str(exc)) from exc
