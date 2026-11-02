"""Wire-compatible records and validation for renumbering recovery evidence."""

from datetime import datetime
from typing import Literal, TypedDict

from workflows.core.matching import parse_date, to_finite_decimal
from zoho.validation import require_record, require_records, require_text
from zoho.identifiers import (
    PaymentId as PaymentId, InvoiceId as InvoiceId, CustomerId as CustomerId,
    AccountId as AccountId, LocationId as LocationId,
)
RenumberStatus = Literal["planned", "submitted", "verified", "failed"]


class RenumberingError(ValueError):
    """A plan, live payment, or destination series is unsafe to apply."""


class AllocationSnapshot(TypedDict):
    invoice_id: InvoiceId
    amount_applied: str
    date: str


class PaymentSnapshot(TypedDict):
    date: str
    amount: str
    account_id: AccountId
    location_id: LocationId
    customer_id: CustomerId
    invoices: list[AllocationSnapshot]


class RenumberPlan(TypedDict):
    payment_id: PaymentId
    current_payment_number: str
    new_payment_number: str
    prefix: str
    suffix: str
    expected: PaymentSnapshot


class RenumberResult(TypedDict):
    payment_id: PaymentId
    status: RenumberStatus
    updated_at: str | None
    error: str | None


DiscoveryRecord = TypedDict("DiscoveryRecord", {
    "Payment ID": PaymentId, "Payment Number": str, "Payment Date": str,
})


def record(value: object, context: str) -> dict[str, object]:
    try:
        return require_record(value, context)
    except ValueError as exc:
        raise RenumberingError(str(exc)) from exc


def records(value: object, context: str) -> list[dict[str, object]]:
    try:
        return require_records(value, context)
    except ValueError as exc:
        raise RenumberingError(str(exc)) from exc


def text(value: object, context: str, *, allow_empty: bool = False) -> str:
    try:
        return require_text(value, context, allow_empty=allow_empty)
    except ValueError as exc:
        raise RenumberingError(str(exc)) from exc


def identifier(value: object, context: str) -> str:
    # Zoho sometimes represents IDs as JSON integers. Never stringify containers,
    # booleans or floats into apparently valid identities.
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise RenumberingError(f"{context} must be a string or integer ID")
    return text(str(value), context)


def snapshot(value: object) -> PaymentSnapshot:
    payment = record(value, "Payment")
    day = text(payment.get("date"), "Payment date")
    if parse_date(day) is None:
        raise RenumberingError("Payment date is invalid")
    raw_amount = payment.get("amount")
    if isinstance(raw_amount, bool):
        raise RenumberingError("Payment amount is invalid")
    amount = to_finite_decimal(raw_amount, allow_commas=True)
    if amount is None:
        raise RenumberingError("Payment amount is invalid")
    allocations: list[AllocationSnapshot] = []
    for row in records(payment.get("invoices"), "Payment invoice allocations"):
        raw_applied = row.get("amount_applied")
        applied = None if isinstance(raw_applied, bool) else to_finite_decimal(raw_applied, allow_commas=True)
        if applied is None:
            raise RenumberingError("Invoice allocation amount is invalid")
        allocation_date = row.get("date")
        allocation_day = "" if allocation_date is None else text(allocation_date, "Allocation date", allow_empty=True)
        if allocation_day and parse_date(allocation_day) is None:
            raise RenumberingError("Invoice allocation date is invalid")
        allocations.append(AllocationSnapshot(
            invoice_id=InvoiceId(identifier(row.get("invoice_id"), "Invoice allocation identity")),
            amount_applied=str(applied.normalize()), date=allocation_day,
        ))
    return PaymentSnapshot(
        date=day, amount=str(amount.normalize()),
        account_id=AccountId(identifier(payment.get("account_id"), "Payment account_id")),
        location_id=LocationId(identifier(payment.get("location_id"), "Payment location_id")),
        customer_id=CustomerId(identifier(payment.get("customer_id"), "Payment customer_id")),
        invoices=sorted(allocations, key=lambda row: (row["invoice_id"], row["date"], row["amount_applied"])),
    )


def parse_renumber_plan(value: object) -> list[RenumberPlan]:
    """Validate loaded plans before reading or mutating remote records."""
    result: list[RenumberPlan] = []
    for row in records(value, "Renumber plan"):
        result.append(RenumberPlan(
            payment_id=PaymentId(text(row.get("payment_id"), "Plan payment_id")),
            current_payment_number=text(row.get("current_payment_number"), "Current number"),
            new_payment_number=text(row.get("new_payment_number"), "New number"),
            prefix=text(row.get("prefix"), "Destination prefix"),
            suffix=text(row.get("suffix"), "Destination suffix"),
            expected=snapshot(row.get("expected")),
        ))
    return result


def parse_renumber_results(value: object) -> list[RenumberResult]:
    result: list[RenumberResult] = []
    for row in records(value, "Renumber results"):
        status = row.get("status")
        if status not in ("planned", "submitted", "verified", "failed"):
            raise RenumberingError("Unknown renumber result status")
        # Explicit branches narrow the external string to the public Literal.
        state: RenumberStatus
        if status == "planned":
            state = "planned"
        elif status == "submitted":
            state = "submitted"
        elif status == "verified":
            state = "verified"
        else:
            state = "failed"
        error = row.get("error")
        updated_at = row.get("updated_at")
        if updated_at is not None:
            updated_at = text(updated_at, "Result updated_at")
            try:
                datetime.fromisoformat(updated_at)
            except ValueError as exc:
                raise RenumberingError("Invalid result updated_at") from exc
        result.append(RenumberResult(
            payment_id=PaymentId(text(row.get("payment_id"), "Result payment_id")),
            status=state, updated_at=updated_at,
            error=None if error is None else text(error, "Result error", allow_empty=True),
        ))
    return result
