"""Conservative renumber-only workflow; Analytics discovery never authorizes writes."""

from copy import deepcopy
from datetime import date, datetime
from typing import Callable, Mapping, Sequence

from workflows.core.matching import parse_date
from .contracts import RenumberAnalyticsClient, RenumberBooksClient
from .models import (
    DiscoveryRecord, PaymentId, RenumberPlan, RenumberResult, RenumberingError,
    identifier, parse_renumber_plan, parse_renumber_results, record, records,
    snapshot as _snapshot, text,
)


def get_target_payments(analytics: RenumberAnalyticsClient, workspace_id: str) -> list[DiscoveryRecord]:
    """Fetch discovery records; the planner rechecks every selected Books payment."""
    response = analytics.queries.execute(workspace_id=workspace_id, sql_query='''
        SELECT "Payment ID", "Payment Number", "Payment Date"
        FROM "Customer Payments (Zoho Books)"
    ''', max_attempts=30, poll_interval=2.0)

    result: list[DiscoveryRecord] = []
    for row in records(response, "Analytics discovery"):
        result.append(DiscoveryRecord({
            "Payment ID": PaymentId(identifier(row.get("Payment ID"), "Discovery payment ID")),
            "Payment Number": text(row.get("Payment Number"), "Discovery payment number"),
            "Payment Date": text(row.get("Payment Date"), "Discovery payment date"),
        }))
    return result


def _get(books: RenumberBooksClient, payment_id: str) -> dict[str, object]:
    response = record(books.customer_payments.get(payment_id), "Books payment response")
    payment = record(response.get("payment"), "Books payment")
    code = response.get("code", 0)
    if type(code) is not int or code != 0 or identifier(payment.get("payment_id"), "Books payment ID") != payment_id:
        raise RenumberingError(f"Books did not return the requested payment: {payment_id}")
    text(payment.get("payment_number"), "Books payment number")
    return payment


def _occupied(books: RenumberBooksClient, prefix: str) -> dict[str, str]:
    # Read all pages; validate prefixes locally rather than trusting search filters.
    payments = records(books.customer_payments.list_all(), "Books payment list")
    occupied = {}
    for row in payments:
        number = text(row.get("payment_number"), "Listed payment number").strip()
        if not number.startswith(prefix):
            continue
        if not number[len(prefix):].isdigit() or not row.get("payment_id"):
            raise RenumberingError(f"Malformed destination series entry: {number}")
        if number in occupied:
            raise RenumberingError(f"Duplicate destination number: {number}")
        occupied[number] = identifier(row["payment_id"], "Listed payment ID")
    return occupied


def build_renumber_plan(
    books: RenumberBooksClient, records: Sequence[Mapping[str, object]], *, source_prefix: str,
    destination_prefix: str, start_date: date, end_date: date,
    width: int = 5, starting_sequence: int | None = None,
) -> list[RenumberPlan]:
    """Create a deterministic plan from live records and the actual Books maximum."""
    if (not source_prefix or not destination_prefix or source_prefix == destination_prefix
            or width < 1 or start_date > end_date
            or starting_sequence is not None and starting_sequence < 1):
        raise RenumberingError("Invalid prefixes, date range, width or starting sequence")
    selected = []
    seen = set()
    for row in records:
        number = text(row.get("Payment Number"), "Discovery payment number").strip()
        if not number.startswith(source_prefix):
            continue
        day = parse_date(row.get("Payment Date"))
        if day is None:
            raise RenumberingError(f"Invalid discovery date for {number}")
        if not start_date <= day <= end_date:
            continue
        payment_id = PaymentId(identifier(row.get("Payment ID"), "Discovery payment ID").strip())
        suffix = number[len(source_prefix):]
        if not payment_id or payment_id in seen or not suffix.isdigit():
            raise RenumberingError("Missing/duplicate payment identity or invalid source number")
        seen.add(payment_id)
        payment = _get(books, payment_id)
        if str(payment.get("payment_number")) != number or parse_date(payment.get("date")) != day:
            raise RenumberingError(f"Books differs from Analytics: {payment_id}")
        selected.append((day, int(suffix), payment_id, number, _snapshot(payment)))
    if not selected:
        return []
    occupied = _occupied(books, destination_prefix)
    maximum = max((int(n[len(destination_prefix):]) for n in occupied), default=0)
    sequence = maximum + 1 if starting_sequence is None else starting_sequence
    if sequence <= maximum:
        raise RenumberingError("Starting sequence is stale or already occupied")
    plan = []
    for offset, (_, _, payment_id, number, expected) in enumerate(sorted(selected)):
        suffix = f"{sequence + offset:0{width}d}"
        if len(suffix) > width:
            raise RenumberingError("Destination sequence exceeds the configured width")
        plan.append(RenumberPlan(payment_id=payment_id, current_payment_number=number,
                                new_payment_number=destination_prefix + suffix,
                                prefix=destination_prefix, suffix=suffix, expected=expected))
    return plan


def execute_renumbering(
    books: RenumberBooksClient, plan: Sequence[RenumberPlan], *, execute: bool = False,
    previous_results: Sequence[RenumberResult] = (),
    checkpoint: Callable[[list[RenumberResult]], None] | None = None,
) -> list[RenumberResult]:
    """Preflight every row, persist uncertain state before writes, and verify read-back.

    A submitted/failed prior row is reconciled through live reads on resume; it is
    never blindly replayed. External writers can still race the preflight.
    """
    if execute and checkpoint is None:
        raise RenumberingError("Execution requires a durable checkpoint callback")
    plan = parse_renumber_plan(list(plan))
    previous_results = parse_renumber_results(list(previous_results))
    ids = [row["payment_id"] for row in plan]
    numbers = [row["new_payment_number"] for row in plan]
    if len(ids) != len(set(ids)) or len(numbers) != len(set(numbers)):
        raise RenumberingError("Duplicate payment IDs or destination numbers in plan")
    previous = {row["payment_id"]: row for row in previous_results}
    if len(previous) != len(previous_results) or set(previous) - set(ids):
        raise RenumberingError("Prior results do not match this plan")
    if not plan:
        return []
    prefixes = {row["prefix"] for row in plan}
    if len(prefixes) != 1:
        raise RenumberingError("Plan must use exactly one destination prefix")
    prefix = next(iter(prefixes))
    suffixes = [row["suffix"] for row in plan]
    if any(not suffix.isdigit() for suffix in suffixes) or len({int(suffix) for suffix in suffixes}) != len(suffixes):
        raise RenumberingError("Invalid or duplicate destination suffixes")
    occupied = _occupied(books, prefix)
    completed = set()
    for row in plan:
        if (not row["payment_id"] or not prefix or not row["suffix"].isdigit()
                or row["new_payment_number"] != prefix + row["suffix"]
                or row["current_payment_number"] == row["new_payment_number"]):
            raise RenumberingError("Malformed plan record")
        payment_id = row["payment_id"]
        payment = _get(books, payment_id)
        if _snapshot(payment) != row["expected"]:
            raise RenumberingError(f"Financial state changed: {payment_id}")
        current = str(payment.get("payment_number") or "")
        if current == row["new_payment_number"] and payment_id in previous:
            completed.add(payment_id)
        elif payment_id in previous and previous[payment_id]["status"] == "verified":
            raise RenumberingError(f"Previously verified payment changed: {payment_id}")
        elif current != row["current_payment_number"]:
            raise RenumberingError(f"Payment number changed after planning: {payment_id}")
        owner = occupied.get(row["new_payment_number"])
        if owner is not None and owner != payment_id:
            raise RenumberingError(f"Destination occupied: {row['new_payment_number']}")
        # Different padding must not hide a numeric collision.
        target = int(row["suffix"])
        if any(int(number[len(prefix):]) == target and owner_id != payment_id
               for number, owner_id in occupied.items()):
            raise RenumberingError(f"Destination suffix occupied: {target}")
    results = [RenumberResult(payment_id=row["payment_id"],
                              status="verified" if row["payment_id"] in completed else "planned",
                              updated_at=None, error=None) for row in plan]
    for row, result in zip(plan, results):
        payment_id = row["payment_id"]
        if not execute or payment_id in completed:
            if checkpoint:
                checkpoint(deepcopy(results))
            continue
        assert checkpoint is not None  # Narrowed after dry-run/completed rows above.
        try:
            before = _get(books, payment_id)
            if _snapshot(before) != row["expected"] or str(before.get("payment_number")) != row["current_payment_number"]:
                raise RenumberingError(f"Payment changed before submission: {payment_id}")
            result["status"] = "submitted"
            checkpoint(deepcopy(results))
            response = record(books.customer_payments.update_with_number_series(payment_id, {
                "location_id": row["expected"]["location_id"],
                "payment_number_prefix": prefix, "payment_number_suffix": row["suffix"],
            }), "Books update response")
            if type(response.get("code")) is not int or response.get("code") != 0:
                raise RenumberingError(f"Books rejected payment update: {response.get('message')}")
            after = _get(books, payment_id)
            if str(after.get("payment_number")) != row["new_payment_number"] or _snapshot(after) != row["expected"]:
                raise RenumberingError(f"Read-back mismatch: {payment_id}; inspect Books before resuming")
            result["status"] = "verified"
            result["updated_at"] = datetime.now().isoformat()
        except Exception as exc:
            result["status"] = "failed"
            result["error"] = str(exc)
            checkpoint(deepcopy(results))
            break
        checkpoint(deepcopy(results))
    return results
