"""Higher-level helper functions for Zoho Books bank account operations."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Protocol

from zoho.core_sdk.validation import require_records
from ..operations.records import SearchResource, unique_record

logger = logging.getLogger("helpers.reports.accounts")


class BooksBankAccountsResource(Protocol):
    def list(self) -> object: ...
    def list_all(self, *, resource_key: str | None = None) -> object: ...


class BooksBankAccountsClient(Protocol):
    bank_accounts: BooksBankAccountsResource


def resolve_bank_account_by_name(
    resource: SearchResource, account_name: str,
) -> dict[str, object] | None:
    """Resolve a unique Books bank account from all pages."""
    target = account_name.strip().casefold()
    if not target:
        raise ValueError("Bank account name is required")
    rows = require_records(resource.list_all(resource_key="bankaccounts"), "Books bank account search")
    return unique_record(
        (row for row in rows if str(row.get("account_name") or "").strip().casefold() == target),
        "account_id",
    )


def _get_accounts_iterable(accounts_resource: object) -> object:
    """Safely obtain iterable over bank accounts."""
    if hasattr(accounts_resource, "list_all") and callable(getattr(accounts_resource, "list_all")):
        res = getattr(accounts_resource, "list_all")(resource_key="bankaccounts")
        if isinstance(res, list):
            return res
    if hasattr(accounts_resource, "list_iter") and callable(getattr(accounts_resource, "list_iter")):
        res = getattr(accounts_resource, "list_iter")(resource_key="bankaccounts")
        if isinstance(res, (list, tuple)) or hasattr(res, "__iter__"):
            return res
    if hasattr(accounts_resource, "list") and callable(getattr(accounts_resource, "list")):
        res = getattr(accounts_resource, "list")()
        if isinstance(res, dict):
            return res.get("bankaccounts", res.get("bank_accounts", []))
        if isinstance(res, list):
            return res
    return []


def find_bank_account_by_name(
    books_client: BooksBankAccountsClient,
    account_name: str,
) -> dict[str, object] | None:
    """Look up a bank account by case-insensitive account_name."""
    expected = str(account_name or "").strip().casefold()
    if not expected:
        return None

    try:
        accounts = _get_accounts_iterable(books_client.bank_accounts)
        if isinstance(accounts, (list, tuple)):
            for account in accounts:
                if not isinstance(account, Mapping):
                    continue
                name = str(account.get("account_name") or "").strip().casefold()
                if name == expected:
                    return dict(account)
    except Exception as exc:
        logger.warning(f"Error querying bank accounts for '{account_name}': {exc}")
        return None

    return None


def fetch_bank_accounts_map(
    books_client: BooksBankAccountsClient,
) -> dict[str, dict[str, object]]:
    """Fetch all bank accounts and index them by case-folded account_name."""
    lookup: dict[str, dict[str, object]] = {}
    try:
        accounts = _get_accounts_iterable(books_client.bank_accounts)
        if isinstance(accounts, (list, tuple)):
            for account in accounts:
                if not isinstance(account, Mapping):
                    continue
                name = str(account.get("account_name") or "").strip()
                if name:
                    lookup[name.casefold()] = dict(account)
    except Exception as exc:
        logger.error(f"Error fetching bank accounts map: {exc}")
        raise

    return lookup


def extract_bank_withdrawals(
    transactions: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Filter a list of bank transactions down to outflows (withdrawals / debits)."""
    withdrawals: list[dict[str, object]] = []
    for tx in transactions:
        amount_val = 0.0
        try:
            amount_val = float(str(tx.get("amount", 0.0)))
        except (ValueError, TypeError):
            pass

        doc_type = str(tx.get("transaction_type") or tx.get("type") or "").lower()
        doc_dc = str(tx.get("debit_or_credit") or "").lower()

        is_withdrawal = (
            amount_val < 0
            or doc_dc == "debit"
            or doc_type in ("expense", "withdrawal", "payment")
        )
        if is_withdrawal:
            withdrawals.append(dict(tx))
    return withdrawals


def extract_bank_deposits(
    transactions: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Filter a list of bank transactions down to inflows (deposits / credits / receipts)."""
    deposits: list[dict[str, object]] = []
    for tx in transactions:
        amount_val = 0.0
        try:
            amount_val = float(str(tx.get("amount", 0.0)))
        except (ValueError, TypeError):
            pass

        doc_type = str(tx.get("transaction_type") or tx.get("type") or "").lower()
        doc_dc = str(tx.get("debit_or_credit") or "").lower()

        if doc_dc == "debit" or doc_type in ("expense", "withdrawal", "payment") or amount_val < 0:
            continue

        is_deposit = (
            amount_val > 0
            or doc_dc == "credit"
            or doc_type in ("deposit", "refund", "receipt", "income")
        )
        if is_deposit:
            deposits.append(dict(tx))
    return deposits


