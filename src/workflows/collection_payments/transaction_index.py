"""Run-local bank candidates indexed without weakening amount/date tolerances."""

from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from collections.abc import Mapping, Sequence
from typing import Any

from utils import numeric_affixes
from workflows.runtime.exceptions import ReconciliationError
from workflows.core.matching import (
    get_bank_reference,
    parse_date,
    to_decimal,
    to_text as _text,
)
from workflows.collection_payments.identifiers import identifier


@dataclass(frozen=True)
class BankCandidate:
    row: Mapping[str, object]
    transaction_id: str
    amount: Decimal
    reference: str
    narration: str


class TransactionIndex:
    """Normalize once, then search occupied dates and sorted absolute amounts."""

    def __init__(self, transactions: Sequence[Mapping[str, object]], bank_account_id: str) -> None:
        by_day: dict[int, list[BankCandidate]] = defaultdict(list)
        for row in transactions:
            transaction_id = identifier(row, ("transaction_id", "id"))
            day = parse_date(row.get("date") or row.get("transaction_date"))
            amount = to_decimal(row.get("amount"))
            if not transaction_id or not day or amount is None:
                continue
            if not amount.is_finite():
                raise ReconciliationError(f"Bank transaction {transaction_id} has a non-finite amount.")
            by_day[day.toordinal()].append(BankCandidate(
                row, transaction_id, abs(amount),
                str(get_bank_reference(row, bank_account_id) or "").strip().casefold(),
                str(row.get("description") or row.get("narration") or "").strip().casefold(),
            ))
        self._days = sorted(by_day)
        self._by_day = {day: sorted(rows, key=lambda row: row.amount)
                        for day, rows in by_day.items()}

    def candidates(self, day: date, amount: Decimal, date_tolerance: int,
                   amount_tolerance: Decimal) -> list[BankCandidate]:
        ordinal = day.toordinal()
        first = bisect_left(self._days, ordinal - date_tolerance)
        last = bisect_right(self._days, ordinal + date_tolerance)
        result = []
        for bank_day in self._days[first:last]:
            rows = self._by_day[bank_day]
            low = bisect_left(rows, abs(amount) - amount_tolerance, key=lambda row: row.amount)
            high = bisect_right(rows, abs(amount) + amount_tolerance, key=lambda row: row.amount)
            result.extend(rows[low:high])
        return result


class OrderedBankCandidateIndex:
    """Normalize bank dates and amounts once; preserve original candidate order."""

    def __init__(self, rows: Sequence[Mapping[str, Any]]) -> None:
        self.by_date: dict[date, dict[Decimal, list[tuple[int, Mapping[str, Any]]]]] = {}
        for position, row in enumerate(rows):
            day = parse_date(row.get("date") or row.get("transaction_date"))
            amount = to_decimal(row.get("amount"))
            if day and amount is not None:
                self.by_date.setdefault(day, {}).setdefault(abs(amount), []).append((position, row))
        self.amounts = {day: sorted(values) for day, values in self.by_date.items()}

    def candidates(
        self,
        day: date,
        amount: Decimal,
        days: int,
        tolerance: Decimal,
    ) -> list[Mapping[str, Any]]:
        matches: list[tuple[int, Mapping[str, Any]]] = []
        for offset in range(-days, days + 1):
            candidate_day = day + timedelta(days=offset)
            amounts = self.amounts.get(candidate_day, [])
            lower = bisect_left(amounts, abs(amount) - tolerance)
            upper = bisect_right(amounts, abs(amount) + tolerance)
            for value in amounts[lower:upper]:
                matches.extend(self.by_date[candidate_day][value])
        return [row for _, row in sorted(matches, key=lambda item: item[0])]


def find_review_bank_transaction_details(
    payment: Mapping[str, Any],
    transactions: Sequence[Mapping[str, Any]] | OrderedBankCandidateIndex,
    used_transaction_ids: set[str],
    *,
    default_date_tolerance_days: int,
    amount_tolerance: Decimal,
) -> tuple[
    Mapping[str, Any] | None,
    str,
    list[Mapping[str, Any]],
    list[Mapping[str, Any]],
]:
    """Find a unique bank candidate and fallback candidates for a normalized payment."""
    payment_date = parse_date(payment.get("date"))
    amount = to_decimal(payment.get("amount"))
    reference = _text(payment.get("reference")).casefold()
    if not payment_date or amount is None:
        return None, "Invalid payment date or amount", [], []

    default_tol = int(payment.get("date_tolerance_days", default_date_tolerance_days))
    tol_amount = Decimal(str(amount_tolerance))
    rows: Sequence[Mapping[str, Any]] = (
        transactions.candidates(payment_date, amount, default_tol, tol_amount)
        if isinstance(transactions, OrderedBankCandidateIndex)
        else transactions
    )
    candidates: list[Mapping[str, Any]] = []
    date_amount_candidates: list[Mapping[str, Any]] = []
    for transaction in rows:
        transaction_id = _text(transaction.get("transaction_id") or transaction.get("id"))
        if not transaction_id or transaction_id in used_transaction_ids:
            continue
        transaction_date = parse_date(transaction.get("date") or transaction.get("transaction_date"))
        transaction_amount = to_decimal(transaction.get("amount"))
        if not transaction_date or transaction_amount is None:
            continue
        if payment.get("date_source") == "cheque_date" and transaction_date < payment_date:
            continue
        if abs((transaction_date - payment_date).days) > default_tol:
            continue
        if abs(abs(transaction_amount) - abs(amount)) > tol_amount:
            continue
        date_amount_candidates.append(transaction)
        if not reference:
            continue
        account_id = _text(transaction.get("_review_bank_account_id"))
        bank_reference = _text(get_bank_reference(transaction, account_id)).casefold()
        narration = _text(transaction.get("description") or transaction.get("narration")).casefold()
        if _text(payment.get("payment_type")).casefold() == "cheque":
            cheque_suffixes = numeric_affixes(reference, 4)
            bank_suffixes = numeric_affixes(bank_reference, 4) | numeric_affixes(narration, 4)
            matched = bool(cheque_suffixes & bank_suffixes)
        else:
            matched = reference == bank_reference or reference in narration
        if matched:
            candidates.append(transaction)

    if not reference:
        return None, "Missing reference number", [], date_amount_candidates
    if len(candidates) == 1:
        return candidates[0], "Unique date, amount, and reference match", candidates, []
    if len(candidates) > 1:
        return None, "Multiple bank transactions match", candidates, []
    return None, "No bank transaction matched", [], date_amount_candidates


def require_matching_date_amount(
    entry: Mapping[str, Any],
    transaction: Mapping[str, Any],
    *,
    default_date_tolerance_days: int,
    amount_tolerance: Decimal,
) -> None:
    """Revalidate a manually selected reference-mismatch candidate."""
    creator = entry["creator"]
    payment_date = parse_date(creator.get("date"))
    transaction_date = parse_date(transaction.get("date") or transaction.get("transaction_date"))
    payment_amount = to_decimal(creator.get("amount"))
    transaction_amount = to_decimal(transaction.get("amount"))
    tolerance_days = int(creator.get("date_tolerance_days", default_date_tolerance_days))
    if (
        not payment_date
        or not transaction_date
        or payment_amount is None
        or transaction_amount is None
        or (creator.get("date_source") == "cheque_date" and transaction_date < payment_date)
        or abs((transaction_date - payment_date).days) > tolerance_days
        or abs(abs(transaction_amount) - abs(payment_amount)) > Decimal(str(amount_tolerance))
    ):
        raise ReconciliationError(
            "The selected bank transaction no longer matches the payment date and amount."
        )
