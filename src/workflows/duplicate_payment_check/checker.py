"""Find exact duplicate customer payments in Zoho Books."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from collections.abc import Iterable, Mapping
from typing import Protocol

from helpers import parse_date, unwrap_record
from workflows.core.matching import to_finite_decimal


DuplicateKey = tuple[str, date, Decimal]


class _CustomerPaymentsResource(Protocol):
    def list_all(
        self,
        params: dict[str, object] | None = None,
        resource_key: str | None = None,
    ) -> list[dict[str, object]]: ...
    def get(self, resource_id: str, params: dict[str, object] | None = None) -> object: ...


class BooksCustomerPaymentsClient(Protocol):
    @property
    def customer_payments(self) -> _CustomerPaymentsResource: ...


def _date(value: object) -> date | None:
    return parse_date(value)


def _payment_id(payment: Mapping[str, object]) -> str:
    return str(payment.get("payment_id") or payment.get("customer_payment_id") or "").strip()


def _summary(payment: Mapping[str, object]) -> dict[str, object]:
    return {
        "payment_id": _payment_id(payment),
        "payment_number": payment.get("payment_number"),
        "reference_number": payment.get("reference_number"),
        "date": payment.get("date"),
        "amount": payment.get("amount"),
        "customer_id": payment.get("customer_id"),
        "customer_name": payment.get("customer_name"),
        "payment_mode": payment.get("payment_mode"),
        "status": payment.get("status"),
    }


class DuplicatePaymentChecker:
    """Check Books customer payments without mutating any Books data."""

    def __init__(self, books_client: BooksCustomerPaymentsClient):
        self.books = books_client

    def run(
        self,
        *,
        customer_id: str | None = None,
        from_date: str | None = None,
        to_date: str | None = None,
    ) -> dict[str, object]:
        start = _date(from_date) if from_date else None
        end = _date(to_date) if to_date else None
        if from_date and not start:
            raise ValueError("from_date must use YYYY-MM-DD format.")
        if to_date and not end:
            raise ValueError("to_date must use YYYY-MM-DD format.")
        if start and end and start > end:
            raise ValueError("from_date cannot be later than to_date.")

        params: dict[str, object] = {}
        if customer_id:
            params["customer_id"] = customer_id
        if from_date:
            params["date_start"] = from_date
        if to_date:
            params["date_end"] = to_date

        # The live Books response uses the endpoint-shaped `customerpayments`
        # key (without an underscore), which is also BaseResource's default.
        payments = self.books.customer_payments.list_all(params=params or None)
        return self.check(payments, from_date=start, to_date=end)


    def check(
        self,
        payments: Iterable[Mapping[str, object]],
        *,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> dict[str, object]:
        payment_list = list(payments)
        grouped: dict[DuplicateKey, list[Mapping[str, object]]] = defaultdict(list)
        skipped: list[dict[str, str]] = []
        considered = 0

        for original in payment_list:
            payment = dict(original)
            paid_on = _date(payment.get("date"))
            amount = to_finite_decimal(payment.get("amount"))

            if not paid_on or amount is None:
                skipped.append({
                    "payment_id": _payment_id(payment),
                    "reason": "missing or invalid date/amount",
                })
                continue
            if (from_date and paid_on < from_date) or (to_date and paid_on > to_date):
                continue

            customer_id = str(payment.get("customer_id") or "").strip()
            payment_id = _payment_id(payment)
            if not customer_id and payment_id:
                try:
                    response = self.books.customer_payments.get(payment_id)
                    detail = unwrap_record(response if isinstance(response, Mapping) else {}, ("payment", "customerpayment"))
                    payment.update(detail)
                    customer_id = str(payment.get("customer_id") or "").strip()
                except Exception as exc:
                    skipped.append({
                        "payment_id": payment_id,
                        "reason": f"could not retrieve customer ID: {exc}",
                    })
                    continue

            if not customer_id:
                skipped.append({
                    "payment_id": payment_id,
                    "reason": "missing customer ID",
                })
                continue

            considered += 1
            grouped[(customer_id, paid_on, amount)].append(payment)

        duplicate_groups: list[dict[str, object]] = []
        for (customer_id, paid_on, amount), matches in grouped.items():
            if len(matches) < 2:
                continue
            ordered = sorted(matches, key=lambda item: (_payment_id(item), str(item.get("payment_number") or "")))
            duplicate_groups.append({
                "customer_id": customer_id,
                "customer_name": next((item.get("customer_name") for item in ordered if item.get("customer_name")), None),
                "date": paid_on.isoformat(),
                "amount": format(amount, "f"),
                "payment_count": len(ordered),
                "payments": [_summary(item) for item in ordered],
            })

        duplicate_groups.sort(key=lambda item: (str(item.get("date")), str(item.get("customer_id")), Decimal(str(item.get("amount")))))
        return {
            "payments_scanned": len(payment_list),
            "payments_considered": considered,
            "duplicate_group_count": len(duplicate_groups),
            "duplicate_payment_count": sum(int(str(item.get("payment_count") or 0)) for item in duplicate_groups),
            "duplicate_groups": duplicate_groups,
            "skipped": skipped,
        }


def check_duplicate_payments(
    books_client: BooksCustomerPaymentsClient,
    *,
    customer_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, object]:
    """Convenience entry point for exact customer/date/amount duplicate checks."""
    return DuplicatePaymentChecker(books_client).run(
        customer_id=customer_id,
        from_date=from_date,
        to_date=to_date,
    )
