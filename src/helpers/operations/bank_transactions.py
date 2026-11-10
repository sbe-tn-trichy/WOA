"""Composite operations for Zoho Books uncategorized bank transactions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol

from zoho.core_sdk.validation import require_records, require_text


class _BankTransactionsResource(Protocol):
    def list_all(self, params: dict[str, object] | None = None) -> object: ...
    def get_matches(self, transaction_id: str) -> object: ...
    def match(self, transaction_id: str, payload: list[dict[str, object]]) -> object: ...
    def categorize(self, transaction_id: str, payload: dict[str, object]) -> object: ...
    def categorize_as_expense(self, transaction_id: str, payload: dict[str, object]) -> object: ...
    def categorize_as_vendor_payment(self, transaction_id: str, payload: dict[str, object]) -> object: ...


class BooksBankTransactionsClient(Protocol):
    @property
    def bank_transactions(self) -> _BankTransactionsResource: ...


def fetch_uncategorized_bank_transactions(
    books_client: BooksBankTransactionsClient,
    bank_accounts: Sequence[tuple[str, str]],
    *,
    name_key: str = "bank_name",
    account_key: str = "bank_account_id",
) -> list[dict[str, object]]:
    """Fetch uncategorized bank transactions across configured ``(name, account_id)`` pairs."""
    rows: list[dict[str, object]] = []
    for bank_name, account_id in bank_accounts:
        transactions = require_records(
            books_client.bank_transactions.list_all(
                params={
                    "account_id": account_id,
                    "filter_by": "Status.Uncategorized",
                }
            ),
            "Books uncategorized bank transactions",
        )
        for transaction in transactions:
            annotated = dict(transaction)
            annotated[name_key] = bank_name
            annotated[account_key] = account_id
            rows.append(annotated)
    return rows


def get_uncategorized_bank_transaction(
    books_client: BooksBankTransactionsClient,
    bank_id: str,
    bank_account_id: str,
) -> dict[str, object] | None:
    """Return one currently uncategorized bank transaction or ``None`` if absent."""
    target_id = require_text(bank_id, "Bank transaction ID")
    account_id = require_text(bank_account_id, "Bank account ID")
    rows = require_records(
        books_client.bank_transactions.list_all(
            params={
                "account_id": account_id,
                "filter_by": "Status.Uncategorized",
            }
        ),
        "Books uncategorized bank transactions",
    )
    for row in rows:
        row_id = str(row.get("transaction_id") or row.get("id") or "").strip()
        if row_id == target_id:
            return dict(row)
    return None


def find_bank_match_candidate(
    books_client: BooksBankTransactionsClient,
    bank_id: str,
    primary_id: str,
    *,
    fallback_ids: Sequence[str] = (),
) -> dict[str, object] | None:
    """Look up a matching Books candidate for ``bank_id`` by primary or fallback IDs."""
    matches = books_client.bank_transactions.get_matches(bank_id)
    rows = matches.get("matching_transactions", []) if isinstance(matches, Mapping) else []
    for row in rows:
        if isinstance(row, Mapping) and str(row.get("transaction_id") or "").strip() == primary_id:
            return dict(row)
    fallback_set = {item.strip() for item in fallback_ids if item and item.strip()}
    if fallback_set:
        for row in rows:
            if isinstance(row, Mapping) and str(row.get("transaction_id") or "").strip() in fallback_set:
                return dict(row)
    return None


def match_bank_transaction(
    books_client: BooksBankTransactionsClient,
    bank_id: str,
    candidate: Mapping[str, object],
) -> None:
    """Match an uncategorized bank transaction to a validated Books match candidate."""
    match_transaction_id = require_text(candidate.get("transaction_id"), "Match candidate transaction_id")
    transaction_type = require_text(candidate.get("transaction_type"), "Match candidate transaction_type")
    books_client.bank_transactions.match(
        bank_id,
        [
            {
                "transaction_id": match_transaction_id,
                "transaction_type": transaction_type,
            }
        ],
    )


def categorize_bank_transaction(
    books_client: BooksBankTransactionsClient,
    transaction_id: str,
    *,
    kind: Literal["expense", "transfer_fund", "vendor_payment"],
    payload: Mapping[str, object],
) -> dict[str, object]:
    """Categorize an uncategorized bank line and verify Books ``code == '0'``."""
    body = dict(payload)
    if kind == "expense":
        response = books_client.bank_transactions.categorize_as_expense(transaction_id, body)
    elif kind == "transfer_fund":
        response = books_client.bank_transactions.categorize(transaction_id, body)
    elif kind == "vendor_payment":
        response = books_client.bank_transactions.categorize_as_vendor_payment(transaction_id, body)
    else:
        raise ValueError(f"Unsupported bank categorization kind: {kind}")
    if not isinstance(response, Mapping):
        raise ValueError(f"Books rejected the {kind} categorization.")
    code = response.get("code")
    if code is None or str(code).strip() != "0":
        raise ValueError(f"Books rejected the {kind} categorization.")
    return {str(key): value for key, value in response.items()}


__all__ = [
    "BooksBankTransactionsClient",
    "categorize_bank_transaction",
    "fetch_uncategorized_bank_transactions",
    "find_bank_match_candidate",
    "get_uncategorized_bank_transaction",
    "match_bank_transaction",
]
