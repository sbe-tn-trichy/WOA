"""Fetch, caching, and normalization flow for the online-payment review queue."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from helpers import (
    build_batched_like_queries,
    fetch_uncategorized_bank_transactions,
    query_or_export_analytics_rows,
)
from utils.file_utils import json
from workflows.collection_payments.allocator import attach_invoice_preview
from workflows.collection_payments.cheques import attach_presented_dates
from workflows.collection_payments.transaction_index import OrderedBankCandidateIndex
from workflows.core.matching import to_text as _text
from workflows.runtime.exceptions import ReconciliationError
from .bank_statement import (
    CustomerFinderIndex,
    display_bank_transaction,
    extract_remitter_tokens,
    suggest_names_for_tokens,
)
from .preview_cache import PreviewCache


@dataclass(frozen=True)
class OnlinePaymentReviewConfig:
    creator_app_link_name: str
    bank_account_id: str = ""
    bank_accounts: tuple[tuple[str, str], ...] = ()
    payment_report_link_name: str = "Online_Payments"
    payment_reports: tuple[tuple[str, str], ...] = ()
    cheque_detail_report_link_name: str = "All_Cheque_Details"
    cheque_detail_form_link_name: str = "Cheque_Details"
    customer_report_link_name: str = "All_Customers1"
    creator_checkpoint_report_link_name: str = "All_Payments"
    creator_books_id_field: str = "Books_Transaction_Id"
    creator_payment_number_field: str = "PaymentNo"
    date_tolerance_days: int = 0
    cheque_date_tolerance_days: int = 7
    amount_tolerance: Decimal = Decimal("0")
    analytics_workspace_id: str = ""
    customer_finder_view_id: str = ""
    travel_expense_account_name: str = "Employee Travel Expense"
    travel_expense_account_id: str = ""
    salary_expense_account_id: str = ""
    cash_account_id: str = ""
    cash_account_name: str = "Cash-SBE"
    vendor_advance_vendor_name: str = "Polycab"
    vendor_advance_location_name: str = "Sri Bharath Electricals"
    analytics_preview_ttl_seconds: float = 300
    customer_mapping_ttl_seconds: float = 300
    travel_account_ttl_seconds: float = 300
    lazy_invoice_previews: bool = True
    analytics_batch_tokens: int = 35
    analytics_max_sql_bytes: int = 6000
    state_path: Path = Path(
        "output/collection_reconciliation/online_payments_review.json"
    )

    def __post_init__(self) -> None:
        for ttl in (
            self.analytics_preview_ttl_seconds,
            self.customer_mapping_ttl_seconds,
            self.travel_account_ttl_seconds,
        ):
            if not 0 <= ttl < float("inf"):
                raise ValueError("Cache expiry must be finite and non-negative.")
        if self.analytics_batch_tokens < 1 or self.analytics_max_sql_bytes < 256:
            raise ValueError("Analytics batch limits must be positive and SQL budget at least 256 bytes.")

    def configured_banks(self) -> tuple[tuple[str, str], ...]:
        if self.bank_accounts:
            return tuple(
                (str(name).strip(), str(account_id).strip())
                for name, account_id in self.bank_accounts
                if str(name).strip() and str(account_id).strip()
            )
        if self.bank_account_id:
            return (("Bank", str(self.bank_account_id)),)
        raise ValueError("At least one bank account is required.")

    def configured_reports(self) -> tuple[tuple[str, str], ...]:
        if self.payment_reports:
            return tuple(
                (str(payment_type).strip(), str(report_name).strip())
                for payment_type, report_name in self.payment_reports
                if str(payment_type).strip() and str(report_name).strip()
            )
        return (("Online", self.payment_report_link_name),)


def fetch_all_creator_payments(
    creator: Any,
    config: OnlinePaymentReviewConfig,
) -> list[dict[str, Any]]:
    """Fetch unlinked Creator payment records and join cheque presented dates."""
    rows: list[dict[str, Any]] = []
    has_cheques = False
    for payment_type, report_name in config.configured_reports():
        payments = creator.get_all_records(
            config.creator_app_link_name,
            report_name,
            criteria=f'({config.creator_books_id_field} == null || {config.creator_books_id_field} == "")',
        )
        for payment in payments:
            if _text(payment.get(config.creator_books_id_field)):
                continue
            annotated = dict(payment)
            annotated["_review_payment_type"] = payment_type
            annotated["_review_report_link_name"] = report_name
            rows.append(annotated)
        has_cheques = has_cheques or (
            payment_type.casefold() == "cheque"
            and any(not _text(payment.get(config.creator_books_id_field)) for payment in payments)
        )
    if has_cheques:
        cheque_details = creator.get_all_records(
            config.creator_app_link_name,
            config.cheque_detail_report_link_name,
        )
        attach_presented_dates(rows, cheque_details)
    return rows


def fetch_all_uncategorized_bank_transactions(
    books: Any,
    config: OnlinePaymentReviewConfig,
) -> list[dict[str, Any]]:
    """Fetch uncategorized Books bank lines annotated with configured bank identity."""
    return fetch_uncategorized_bank_transactions(
        books,
        config.configured_banks(),
        name_key="_review_bank_name",
        account_key="_review_bank_account_id",
    )


def fetch_review_sources(
    creator_reader: Callable[[], list[dict[str, Any]]],
    bank_reader: Callable[[], list[dict[str, Any]]],
    creator: Any,
    config: OnlinePaymentReviewConfig,
    customer_cache: PreviewCache[list[Mapping[str, Any]]],
    cache_hits: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    """Concurrently read Creator payments & Books bank lines, plus cached customer IDs."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        ctx_payment = copy_context()
        ctx_bank = copy_context()
        payment_read = executor.submit(lambda: ctx_payment.run(creator_reader))
        bank_read = executor.submit(lambda: ctx_bank.run(bank_reader))
        payments = payment_read.result()
        bank_transactions = bank_read.result()

    customer_key = (id(creator), config.creator_app_link_name, config.customer_report_link_name)
    customers = customer_cache.get(customer_key)
    if customers is None:
        customers = creator.get_all_records(
            config.creator_app_link_name,
            config.customer_report_link_name,
        )
        customer_cache.put(customer_key, customers, config.customer_mapping_ttl_seconds)
    else:
        cache_hits["customer_mapping"] += 1
    customer_ids = {
        _text(row.get("ID")): _text(row.get("Customer_Id"))
        for row in customers
        if _text(row.get("ID"))
    }
    return payments, bank_transactions, customer_ids


def build_historical_finder_queries(
    config: OnlinePaymentReviewConfig,
    tokens: Sequence[str],
) -> list[str]:
    """Build SQL-budgeted ``LIKE`` queries against ``Payment Customer Finder``."""
    try:
        return build_batched_like_queries(
            "Payment Customer Finder",
            ("Customer Name", "Description"),
            "Description",
            tokens,
            where_prefix='"Customer Name" IS NOT NULL AND "Customer Name" != \'\'',
            max_tokens_per_query=config.analytics_batch_tokens,
            max_sql_bytes=config.analytics_max_sql_bytes,
        )
    except ValueError as exc:
        raise ReconciliationError(str(exc)) from exc


def query_historical_customer_finder(
    analytics: Any,
    config: OnlinePaymentReviewConfig,
    tokens: Sequence[str],
) -> tuple[list[dict[str, object]], bool]:
    """Query Analytics Payment Customer Finder rows with SQL batching or export fallback."""
    if not config.customer_finder_view_id or not tokens:
        return [], False
    if not analytics or not config.analytics_workspace_id:
        raise ReconciliationError("Analytics customer-name validation is not configured.")
    unique_tokens = sorted({t.strip() for t in tokens if t and len(t.strip()) >= 3})
    if not unique_tokens:
        return [], False
    queries = build_historical_finder_queries(config, unique_tokens)
    try:
        return query_or_export_analytics_rows(
            analytics,
            config.analytics_workspace_id,
            queries=queries,
            fallback_view_id=config.customer_finder_view_id,
            max_export_attempts=60,
        )
    except ValueError as exc:
        raise ReconciliationError(str(exc)) from exc


def preview_customer_finder(
    analytics: Any,
    config: OnlinePaymentReviewConfig,
    tokens: Sequence[str],
    history_cache: PreviewCache[list[Mapping[str, Any]]],
    full_history_cache: PreviewCache[list[Mapping[str, Any]]],
    cache_hits: dict[str, int],
    query_fn: Callable[[Sequence[str]], list[Mapping[str, Any]]],
    was_full_export: Callable[[], bool],
) -> list[Mapping[str, Any]]:
    """Fetch or return cached historical Analytics remitter rows for ``tokens``."""
    scope = (id(analytics), config.analytics_workspace_id, config.customer_finder_view_id)
    unique_tokens = sorted({t.strip() for t in tokens if t and len(t.strip()) >= 3})
    if not unique_tokens:
        return []
    full_rows = full_history_cache.get(scope)
    if full_rows is not None:
        cache_hits["analytics_tokens"] += len(unique_tokens)
        return full_rows
    rows: list[Mapping[str, Any]] = []
    missing = []
    for token in unique_tokens:
        cached = history_cache.get((*scope, token))
        if cached is None:
            missing.append(token)
        else:
            cache_hits["analytics_tokens"] += 1
            rows.extend(cached)
    if missing:
        fresh = query_fn(missing)
        if was_full_export():
            full_history_cache.put(scope, fresh, config.analytics_preview_ttl_seconds)
            return fresh
        rows.extend(fresh)
        for token in missing:
            matched = [
                row for row in fresh
                if token.casefold() in _text(row.get("Description")).casefold()
            ]
            history_cache.put((*scope, token), matched, config.analytics_preview_ttl_seconds)
    unique_rows: dict[tuple[str, str], Mapping[str, Any]] = {}
    for row in rows:
        unique_rows[(_text(row.get("Customer Name")), _text(row.get("Description")))] = row
    return list(unique_rows.values())


def migrate_bank_identity(
    entry: dict[str, Any],
    previous_batch: Mapping[str, Any],
    config: OnlinePaymentReviewConfig,
) -> None:
    """Backfill legacy review entries missing ``payment_type`` or ``bank_account_id``."""
    entry.setdefault("payment_type", "Online")
    entry.setdefault("source_report", config.payment_report_link_name)
    if entry.get("bank_account_id"):
        return
    previous_account_id = _text(previous_batch.get("bank_account_id"))
    if not previous_account_id:
        return
    name = next(
        (bank_name for bank_name, account_id in config.configured_banks() if account_id == previous_account_id),
        "Bank",
    )
    entry["bank_account_id"] = previous_account_id
    entry["bank_name"] = name


def merge_review_entries(
    raw_entries: list[dict[str, Any]],
    previous: Mapping[str, Any],
    customer_finder: CustomerFinderIndex,
    customer_finder_rows: Sequence[Mapping[str, Any]],
    books: Any,
    config: OnlinePaymentReviewConfig,
    check_name_fn: Callable[[dict[str, Any], Sequence[Mapping[str, Any]]], None],
) -> list[dict[str, Any]]:
    """Attach customer checks, invoice previews, prior decisions, and archived entries."""
    previous_entries = {str(entry.get("id")): entry for entry in previous.get("entries", [])}
    invoice_cache: dict[str, list[dict[str, object]]] = {}
    entries: list[dict[str, Any]] = []
    for entry in raw_entries:
        for candidate in entry["ambiguous_candidates"]:
            cand_tokens = extract_remitter_tokens(candidate.get("description"))
            candidate["suggested_customer_names"] = (
                suggest_names_for_tokens(cand_tokens, customer_finder_rows)
                or customer_finder.suggest(candidate)
            )
        check_name_fn(entry, customer_finder_rows)
        old = previous_entries.get(entry["id"])
        if old and old.get("push_status") == "pushed":
            terminal = dict(old)
            terminal["archived"] = False
            migrate_bank_identity(terminal, previous, config)
            entries.append(terminal)
            continue
        if config.lazy_invoice_previews and entry.get("reviewable"):
            entry.update(allocation_status="pending_preview", invoice_allocations=[], allocation_error="")
        else:
            attach_invoice_preview(books, entry, invoice_cache)
        if entry.get("customer_name_valid") is False:
            entry["reason"] += " " + entry["customer_name_reason"]
        if old and old.get("fingerprint") == entry["fingerprint"]:
            for key in (
                "decision", "push_status", "retry_stage", "books_payment_id",
                "books_payment_number", "decision_at", "pushed_at", "error",
            ):
                if key in old:
                    entry[key] = old[key]
            if old.get("manual_reference_override"):
                for key in (
                    "bank", "bank_name", "bank_account_id",
                    "manual_reference_override", "reviewable", "reason",
                ):
                    if key in old:
                        entry[key] = old[key]
        entries.append(entry)

    current_ids = {entry["id"] for entry in entries}
    for old in previous.get("entries", []):
        if _text(old.get("id")) not in current_ids and old.get("push_status") == "pushed":
            archived = dict(old)
            archived["archived"] = True
            migrate_bank_identity(archived, previous, config)
            entries.append(archived)
    return entries


def apply_manual_reference_override(
    entry: dict[str, Any],
    selected_bank_transaction_id: str,
    allow_reference_override: bool,
) -> None:
    """Attach a user-confirmed reference-mismatch bank candidate onto ``entry``."""
    if not allow_reference_override:
        raise ReconciliationError("Explicit confirmation of the reference mismatch is required.")
    possible = next(
        (
            row
            for row in entry.get("possible_candidates", [])
            if _text(row.get("transaction_id")) == _text(selected_bank_transaction_id)
        ),
        None,
    )
    if not possible:
        raise ReconciliationError("The selected bank transaction is not a possible match for this payment.")
    if not _text(entry.get("creator", {}).get("books_customer_id")):
        raise ReconciliationError("The Creator customer has no Zoho Books Customer_Id.")
    entry.update(
        {
            "bank": {k: v for k, v in possible.items() if k not in {"bank_name", "bank_account_id"}},
            "bank_name": _text(possible.get("bank_name")),
            "bank_account_id": _text(possible.get("bank_account_id")),
            "manual_reference_override": True,
            "reviewable": True,
            "reason": "Manually selected date-and-amount match; reference differs",
        }
    )


def build_proposal_entry(
    payment: Mapping[str, Any],
    customer_ids: Mapping[str, str],
    bank_transactions: Sequence[Mapping[str, Any]] | OrderedBankCandidateIndex,
    used_transaction_ids: set[str],
    config: OnlinePaymentReviewConfig,
    find_details: Callable[
        [Mapping[str, Any], Sequence[Mapping[str, Any]] | OrderedBankCandidateIndex, set[str]],
        tuple[Mapping[str, Any] | None, str, list[Mapping[str, Any]], list[Mapping[str, Any]]],
    ],
) -> dict[str, Any]:
    """Normalize a Creator payment and build a fingerprinted review-queue entry."""
    creator_id = _text(payment.get("ID"))
    raw_cust = payment.get("Customer_Name")
    lookup: Mapping[str, Any] = raw_cust if isinstance(raw_cust, Mapping) else {}
    creator_customer_id = _text(lookup.get("ID"))
    is_cheque = _text(payment.get("_review_payment_type")).casefold() == "cheque"
    normalized = {
        "date": _text(payment.get("_review_presented_date") if is_cheque else payment.get("Payment_Date")),
        "date_source": _text(payment.get("_review_date_source")) or "payment_date",
        "amount": _text(payment.get("Payment_Amount")),
        "reference": _text(payment.get("Reference")),
        "payment_id": _text(payment.get("Payment_ID")),
        "customer_name": _text(lookup.get("zc_display_value") or lookup.get("Name")),
        "creator_customer_id": creator_customer_id,
        "books_customer_id": customer_ids.get(creator_customer_id, ""),
        "payment_type": _text(payment.get("_review_payment_type")) or "Online",
        "date_tolerance_days": config.cheque_date_tolerance_days if is_cheque else config.date_tolerance_days,
    }
    date_error = _text(payment.get("_review_presented_date_error"))
    if date_error:
        candidate, reason, candidates, possible_candidates = None, date_error, [], []
    else:
        candidate, reason, candidates, possible_candidates = find_details(
            normalized, bank_transactions, used_transaction_ids,
        )
    bank = display_bank_transaction(candidate) if candidate else None

    def display_candidates(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                **display_bank_transaction(row),
                "bank_name": _text(row.get("_review_bank_name")),
                "bank_account_id": _text(row.get("_review_bank_account_id")),
            }
            for row in rows
        ]

    ambiguous_candidates = display_candidates(candidates) if len(candidates) > 1 else []
    displayed_possible = display_candidates(possible_candidates)
    if bank:
        used_transaction_ids.add(bank["transaction_id"])
    fingerprint_payload = {
        "creator": normalized,
        "bank_transaction_id": bank.get("transaction_id") if bank else None,
        "ambiguous_transaction_ids": [row["transaction_id"] for row in ambiguous_candidates],
        "possible_transaction_ids": [row["transaction_id"] for row in displayed_possible],
        "reason": reason,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "id": creator_id,
        "fingerprint": fingerprint,
        "creator": normalized,
        "payment_type": normalized["payment_type"],
        "source_report": _text(payment.get("_review_report_link_name")) or config.payment_report_link_name,
        "bank": bank,
        "bank_name": _text((candidate or {}).get("_review_bank_name")),
        "bank_account_id": _text((candidate or {}).get("_review_bank_account_id")),
        "ambiguous_candidates": ambiguous_candidates,
        "possible_candidates": displayed_possible,
        "reason": reason,
        "reviewable": bool(bank and normalized["books_customer_id"]),
        "decision": "pending",
        "push_status": "not_started",
        "books_payment_id": "",
        "books_payment_number": "",
        "error": "",
    }
