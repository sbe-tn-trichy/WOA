"""Human review queue for the live Creator ``Online_Payments`` report."""

from __future__ import annotations

import threading
from collections.abc import Mapping, Sequence
from typing import Any

from helpers import (
    AmbiguousMatchError,
    categorize_bank_transaction,
    fetch_open_invoices,
    get_uncategorized_bank_transaction,
    resolve_chart_of_account,
    resolve_location_by_name,
    resolve_vendor_by_name,
    update_and_verify_creator_record,
)
from utils import utc_now_iso
from utils.file_utils import json
from workflows.collection_payments.allocator import allocate_invoices_oldest_due_first, attach_invoice_preview
from workflows.collection_payments.cheques import checkpoint_cheque_presentation
from workflows.collection_payments.identifiers import identifier as _identifier
from workflows.collection_payments.payments import (
    create_customer_payment_and_resolve,
    match_books_payment_to_bank,
    review_customer_payment_payload,
)
from workflows.collection_payments.transaction_index import (
    OrderedBankCandidateIndex as _BankCandidateIndex,
    find_review_bank_transaction_details,
    require_matching_date_amount,
)
from workflows.collection_payments.types import BankTransferProposal
from workflows.core.checkpoint import write_atomic_json
from workflows.core.matching import to_text as _text
from workflows.runtime.exceptions import ReconciliationError
from .bank_statement import (
    CustomerFinderIndex,
    bank_line_kind,
    build_bank_statement_views,
    check_customer_name,
    collect_review_remitter_tokens,
    extract_remitter_tokens,
    validate_live_bank_line_for_categorization,
)
from .bank_transfers import bank_line_identity, merge_transfer_proposals, post_transfer
from .preview_cache import PreviewCache
from .review_fetch import (
    OnlinePaymentReviewConfig,
    apply_manual_reference_override,
    build_historical_finder_queries,
    build_proposal_entry,
    fetch_all_creator_payments,
    fetch_all_uncategorized_bank_transactions,
    fetch_review_sources,
    merge_review_entries,
    preview_customer_finder,
    query_historical_customer_finder,
)


class OnlinePaymentReviewService:
    """Build and mutate a persistent, explicitly approved payment review queue."""

    def __init__(self, creator_client: Any, books_client: Any, config: OnlinePaymentReviewConfig, analytics_client: Any = None) -> None:
        self.creator, self.books, self.analytics, self.config = creator_client, books_client, analytics_client, config
        self._lock = threading.RLock()
        self._history_cache: PreviewCache[list[Mapping[str, Any]]] = PreviewCache()
        self._full_history_cache: PreviewCache[list[Mapping[str, Any]]] = PreviewCache()
        self._history_was_full_export = False
        self._customer_cache: PreviewCache[list[Mapping[str, Any]]] = PreviewCache()
        self._expense_cache: PreviewCache[str] = PreviewCache()
        self._cache_hits: dict[str, int] = {"analytics_tokens": 0, "customer_mapping": 0}

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.config.state_path.exists():
                return self._empty_batch()
            data = json.loads(self.config.state_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else self._empty_batch()

    def refresh(self, *, force_refresh: bool = False) -> dict[str, Any]:
        """Read live Creator/Books data and rebuild proposals without writing to Zoho."""
        with self._lock:
            self._cache_hits = {"analytics_tokens": 0, "customer_mapping": 0}
            if force_refresh:
                for cache in (self._history_cache, self._full_history_cache, self._customer_cache, self._expense_cache):
                    cache.clear()
            previous = self.load()
            payments, bank_transactions, customer_ids = fetch_review_sources(
                self._all_creator_payments, self._all_uncategorized_bank_transactions,
                self.creator, self.config, self._customer_cache, self._cache_hits,
            )
            bank_transfers, transfer_lines = merge_transfer_proposals(bank_transactions, previous.get("bank_transfers", []))
            used_ids: set[str] = set()
            excluded = {"cash_deposit", "electricity", "salary", "travel_allowance", "vendor_advance"}
            bank_index = _BankCandidateIndex([
                tx for tx in bank_transactions
                if bank_line_identity(tx) not in transfer_lines and bank_line_kind(tx) not in excluded
            ])
            bank_comparisons = [self._proposal(p, customer_ids, bank_index, set()) for p in payments]
            raw_entries = [self._proposal(p, customer_ids, bank_index, used_ids) for p in payments]
            tokens = collect_review_remitter_tokens(raw_entries, bank_transactions, transfer_lines)
            finder_rows = self._preview_customer_finder(tokens)
            finder = CustomerFinderIndex(finder_rows)
            entries = merge_review_entries(
                raw_entries, previous, finder, finder_rows, self.books, self.config, self._check_customer_name,
            )
            bank_suggestions, bank_records = build_bank_statement_views(
                bank_transactions, bank_comparisons, bank_transfers, transfer_lines,
                previous, finder, used_ids,
                travel_expense_account_name=self.config.travel_expense_account_name,
                cash_account_name=self.config.cash_account_name,
                vendor_advance_vendor_name=self.config.vendor_advance_vendor_name,
                vendor_advance_location_name=self.config.vendor_advance_location_name,
            )
            batch = {
                **self._empty_batch(),
                "refreshed_at": utc_now_iso(),
                "preview_cache_hits": dict(self._cache_hits),
                "entries": entries,
                "bank_suggestions": bank_suggestions,
                "bank_records": bank_records,
                "bank_transfers": bank_transfers,
            }
            self._save(batch)
            return batch

    def categorize_bank_transfer(self, transfer_proposal_id: str) -> BankTransferProposal:
        """Apply an explicitly confirmed pair as one Books transfer."""
        with self._lock:
            batch = self.load()
            proposal = next((pair for pair in batch.get("bank_transfers", []) if pair["id"] == transfer_proposal_id), None)
            if proposal is None:
                raise ReconciliationError("No bank transfer proposal exists. Refresh the queue.")
            if proposal["status"] == "completed":
                return proposal
            rows = self._all_uncategorized_bank_transactions()

            def checkpoint() -> None:
                for group in ("bank_records", "bank_suggestions"):
                    for row in batch.get(group, []):
                        if proposal["id"] in row.get("transfer_ids", []):
                            row["categorization_status"] = "categorized" if proposal["status"] == "completed" else "pending"
                self._save(batch)

            try:
                post_transfer(self.books, proposal, rows, checkpoint)
            except Exception as exc:
                proposal["error"] = str(exc)
                checkpoint()
                raise
            return proposal

    def preview_invoices(self, entry_id: str) -> dict[str, Any]:
        """Load an invoice preview without authorizing a payment mutation."""
        with self._lock:
            batch, entry = self._entry(entry_id)
            if entry.get("push_status") != "pushed":
                attach_invoice_preview(self.books, entry, {})
                self._save(batch)
            return entry

    def categorize_many(self, transaction_ids: Sequence[str]) -> dict[str, Any]:
        """Validate a fresh batch snapshot, then checkpoint sequential writes."""
        if isinstance(transaction_ids, (str, bytes)) or any(not isinstance(x, str) or not x for x in transaction_ids):
            raise ReconciliationError("transaction_ids must contain non-empty strings.")
        with self._lock:
            rows = self._all_uncategorized_bank_transactions()
            current = {(row["_review_bank_account_id"], _text(row.get("transaction_id") or row.get("id"))): row for row in rows}
            metadata: dict[str, Any] = {}
            succeeded, failed = [], []
            for transaction_id in dict.fromkeys(transaction_ids):
                try:
                    self.categorize_bank_line(transaction_id, _current_rows=current, _vendor_metadata=metadata)
                    succeeded.append(transaction_id)
                except Exception as exc:
                    metadata.clear()
                    failed.append({"transaction_id": transaction_id, "error": str(exc)})
            return {"succeeded": succeeded, "failed": failed}

    def categorize_travel_expense(self, transaction_id: str) -> dict[str, Any]:
        """Categorize one reviewed TA withdrawal after validating live Books state."""
        return self.categorize_bank_line(transaction_id, expected_kind="travel_allowance")

    def categorize_bank_line(
        self, transaction_id: str, *, expected_kind: str = "",
        _current_rows: Mapping[tuple[str, str], Mapping[str, Any]] | None = None,
        _vendor_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Apply a reviewed expense, cash transfer, or vendor advance classification."""
        with self._lock:
            batch = self.load()
            proposal = next((row for row in batch.get("bank_suggestions", []) if _text(row.get("transaction_id")) == transaction_id), None)
            if not proposal or proposal.get("kind") not in {"travel_allowance", "electricity", "salary", "cash_deposit", "vendor_advance"} or (expected_kind and proposal.get("kind") != expected_kind):
                raise ReconciliationError("No matching categorization proposal exists for this bank line.")
            kind = proposal["kind"]
            if proposal.get("categorization_status") == "categorized":
                return proposal
            account_id = _text(proposal.get("bank_account_id"))
            current = self._current_bank_transaction(transaction_id, account_id) if _current_rows is None else _current_rows.get((account_id, transaction_id))
            if current is None:
                raise ReconciliationError("The proposed bank transaction is no longer uncategorized. Refresh the queue.")
            base_payload = validate_live_bank_line_for_categorization(current, proposal, kind)
            if kind == "vendor_advance":
                return self._categorize_vendor_advance(batch, proposal, account_id, base_payload, _vendor_metadata)
            configured_id = ("" if kind == "electricity" else self.config.cash_account_id if kind == "cash_deposit"
                             else self.config.salary_expense_account_id if kind == "salary" else self.config.travel_expense_account_id)
            account_name = ("Electricity" if kind == "electricity" else self.config.cash_account_name if kind == "cash_deposit"
                            else "Salary" if kind == "salary" else self.config.travel_expense_account_name)
            if kind not in {"travel_allowance", "electricity"} and not configured_id:
                raise ReconciliationError(f"Configure the {account_name} account ID first.")
            target_account_id = self._resolve_categorize_account(kind, configured_id, account_name)
            if kind == "cash_deposit" and target_account_id == account_id:
                raise ReconciliationError("Cash source and destination bank must differ.")
            payload = (
                {**base_payload, "from_account_id": target_account_id, "to_account_id": account_id, "transaction_type": "transfer_fund"}
                if kind == "cash_deposit"
                else {**base_payload, "account_id": target_account_id, "paid_through_account_id": account_id}
            )
            try:
                categorize_bank_transaction(self.books, transaction_id, kind="transfer_fund" if kind == "cash_deposit" else "expense", payload=payload)
            except Exception as exc:
                self._expense_cache.clear()
                if isinstance(exc, ValueError):
                    raise ReconciliationError("Books rejected the categorization.") from exc
                raise
            proposal["categorization_status"] = "categorized"
            proposal["source_account_id" if kind == "cash_deposit" else "expense_account_id"] = target_account_id
            self._save(batch)
            return proposal

    def _resolve_categorize_account(self, kind: str, configured_id: str, account_name: str) -> str:
        expense_key = (id(self.books), configured_id, account_name)
        cached = self._expense_cache.get(expense_key)
        if cached is not None:
            return cached
        try:
            account = resolve_chart_of_account(
                self.books, account_id=configured_id, account_name="" if configured_id else account_name,
                account_types={"cash"} if kind == "cash_deposit" else {"expense", "other_expense"},
            )
        except AmbiguousMatchError as exc:
            raise ReconciliationError(f"A unique active {account_name} account was not found in Books.") from exc
        if not account:
            raise ReconciliationError(f"A unique active {account_name} account was not found in Books.")
        target_id = _text(account["account_id"])
        self._expense_cache.put(expense_key, target_id, self.config.travel_account_ttl_seconds)
        return target_id

    def _categorize_vendor_advance(
        self, batch: dict[str, Any], proposal: dict[str, Any], bank_account_id: str,
        base_payload: Mapping[str, object], metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metadata = metadata if metadata is not None else {}
        if not metadata:
            target_vendor = (self.config.vendor_advance_vendor_name or "Polycab").strip()
            target_location = (self.config.vendor_advance_location_name or "Sri Bharath Electricals").strip()
            try:
                vendor = resolve_vendor_by_name(self.books, target_vendor, aliases=(f"{target_vendor} india limited",), deduplicate=False)
            except AmbiguousMatchError:
                vendor = None
            if not vendor:
                raise ReconciliationError(f"A unique active {target_vendor} vendor was not found in Books.")
            try:
                location = resolve_location_by_name(self.books, target_location)
            except AmbiguousMatchError:
                location = None
            if not location:
                raise ReconciliationError(f"A unique active {target_location} branch was not found in Books.")
            metadata.update(vendor_id=_text(vendor["contact_id"]), location_id=_text(location["location_id"]))
        payload = {**base_payload, "vendor_id": metadata["vendor_id"], "location_id": metadata["location_id"],
                   "paid_through_account_id": bank_account_id, "payment_mode": "Bank Transfer", "bills": []}
        try:
            categorize_bank_transaction(self.books, proposal["transaction_id"], kind="vendor_payment", payload=payload)
        except ValueError as exc:
            raise ReconciliationError("Books rejected the vendor advance categorization.") from exc
        proposal.update(categorization_status="categorized", vendor_id=payload["vendor_id"], location_id=payload["location_id"])
        self._save(batch)
        return proposal

    def reject(self, entry_id: str) -> dict[str, Any]:
        with self._lock:
            batch, entry = self._entry(entry_id)
            if entry.get("push_status") == "pushed" or entry.get("books_payment_id"):
                raise ReconciliationError("An entry with a Books payment checkpoint cannot be rejected.")
            entry.update({"decision": "rejected", "decision_at": utc_now_iso(), "error": ""})
            self._save(batch)
            return entry

    def accept_and_push(
        self, entry_id: str, current_bank_by_id: Mapping[str, Mapping[str, Any]] | None = None,
        *, selected_bank_transaction_id: str = "", allow_reference_override: bool = False, allow_customer_name_override: bool = False,
    ) -> dict[str, Any]:
        """Push one approved proposal to Books, then checkpoint it in Creator."""
        with self._lock:
            batch, entry = self._entry(entry_id)
            if entry.get("push_status") == "pushed":
                return entry
            if not entry.get("bank") and selected_bank_transaction_id:
                apply_manual_reference_override(entry, selected_bank_transaction_id, allow_reference_override)
                self._save(batch)
            if not entry.get("bank"):
                raise ReconciliationError("This entry has no unique bank match to accept.")
            if not entry.get("reviewable"):
                raise ReconciliationError(entry.get("customer_name_reason") if entry.get("customer_name_valid") is False else entry.get("allocation_error") or "This entry has no invoice allocation to accept.")
            self._check_customer_name(entry, self._query_historical_customer_finder(extract_remitter_tokens(entry["bank"].get("description"))))
            if entry.get("customer_name_valid") is False:
                self._save(batch)
                if not allow_customer_name_override:
                    raise ReconciliationError(entry["customer_name_reason"] + " Explicit confirmation of the Creator customer is required.")
                entry["manual_customer_name_override"] = {"confirmed_at": utc_now_iso(), "customer_name": entry["creator"]["customer_name"], "historical_customer_names": entry["historical_customer_names"]}
            entry.update({"decision": "accepted", "decision_at": entry.get("decision_at") or utc_now_iso(), "error": ""})
            self._save(batch)
            try:
                self._push_entry(batch, entry, current_bank_by_id=current_bank_by_id)
            except Exception as exc:
                stage = _text(entry.get("push_status"))
                if stage in {"payment_created", "match_requested", "bank_matched", "creator_updated"}:
                    entry["retry_stage"] = stage
                entry.update({"push_status": "failed", "error": str(exc)})
                self._save(batch)
                raise
            return entry

    def accept_many(self, entry_ids: Sequence[str], selected_bank_transaction_ids: Mapping[str, str] | None = None, *, allow_reference_override: bool = False) -> dict[str, Any]:
        """Push selected entries sequentially using one current bank snapshot."""
        selected = list(dict.fromkeys(_text(entry_id) for entry_id in entry_ids if _text(entry_id)))
        if not selected:
            raise ReconciliationError("Select at least one payment to accept.")
        if len(selected) > 200:
            raise ReconciliationError("At most 200 payments can be accepted at once.")
        current_bank_by_id = {_text(r.get("transaction_id") or r.get("id")): r for r in self._all_uncategorized_bank_transactions() if _text(r.get("transaction_id") or r.get("id"))}
        pushed, failed = [], []
        selected_ids = selected_bank_transaction_ids or {}
        for entry_id in selected:
            try:
                entry = self.accept_and_push(entry_id, current_bank_by_id=current_bank_by_id, selected_bank_transaction_id=_text(selected_ids.get(entry_id)), allow_reference_override=allow_reference_override)
                pushed.append({"id": entry_id, "books_payment_id": entry.get("books_payment_id", ""), "push_status": entry.get("push_status", "")})
            except Exception as exc:
                failed.append({"id": entry_id, "error": str(exc)})
        return {"selected": len(selected), "pushed": pushed, "failed": failed}

    def _push_entry(self, batch: dict[str, Any], entry: dict[str, Any], current_bank_by_id: Mapping[str, Mapping[str, Any]] | None = None) -> None:
        stage = _text(entry.get("retry_stage") if entry.get("push_status") == "failed" else entry.get("push_status"))
        bank_id, bank_account_id = _text(entry["bank"].get("transaction_id")), _text(entry.get("bank_account_id"))
        if not bank_id:
            raise ReconciliationError("The proposed bank transaction has no ID.")
        if not bank_account_id:
            raise ReconciliationError("The proposed bank transaction has no bank account ID.")
        if not _text(entry["creator"].get("books_customer_id")):
            raise ReconciliationError("The Creator customer has no Zoho Books Customer_Id.")

        if stage not in ("bank_matched", "creator_updated"):
            current = self._current_bank_transaction(bank_id, bank_account_id) if current_bank_by_id is None else current_bank_by_id.get(bank_id)
            if not current:
                raise ReconciliationError("The proposed bank transaction is no longer uncategorized. Refresh the queue.")
            if entry.get("manual_reference_override"):
                self._require_same_date_amount(entry, current)
            else:
                matched, reason = self._find_transaction(entry["creator"], [current], set())
                if _text((matched or {}).get("transaction_id") or (matched or {}).get("id")) != bank_id:
                    raise ReconciliationError(f"The live bank transaction no longer matches this payment: {reason}.")

        books_payment_id, books_payment_number = _text(entry.get("books_payment_id")), _text(entry.get("books_payment_number"))
        if not books_payment_id:
            allocations, unallocated = allocate_invoices_oldest_due_first(
                entry["creator"]["amount"], fetch_open_invoices(self.books, entry["creator"]["books_customer_id"]),
            )
            if not allocations:
                raise ReconciliationError("No open customer invoices are available. Payment creation was blocked to prevent the full amount becoming unused credit.")
            entry.update({"invoice_allocations": allocations, "unallocated_amount": float(unallocated),
                          "allocation_status": "fully_allocated" if unallocated == 0 else "partially_allocated",
                          "allocation_error": "", "allocation_refreshed_at": utc_now_iso()})
            self._save(batch)
            books_payment_id, books_payment_number = create_customer_payment_and_resolve(self.books, self._customer_payment_payload(entry, allocations))
            entry.update({"books_payment_id": books_payment_id, "books_payment_number": books_payment_number, "push_status": "payment_created"})
            entry.pop("retry_stage", None)
            stage = "payment_created"
            self._save(batch)

        if not books_payment_number:
            books_payment_number = _identifier(self.books.customer_payments.get(books_payment_id), ("payment_number",)) or ""
            if not books_payment_number:
                raise ReconciliationError("Books returned no payment number for the created customer payment. The existing payment will be reused on retry.")
            entry["books_payment_number"] = books_payment_number
            self._save(batch)

        if stage not in ("bank_matched", "creator_updated"):
            entry["push_status"] = "match_requested"
            self._save(batch)
            match_books_payment_to_bank(self.books, bank_id, books_payment_id)
            entry["push_status"] = "bank_matched"
            entry.pop("retry_stage", None)
            stage = "bank_matched"
            self._save(batch)

        if stage != "creator_updated":
            self._checkpoint_creator(entry, books_payment_id, books_payment_number)
            entry["push_status"] = "creator_updated"
            entry.pop("retry_stage", None)
            self._save(batch)

        entry.update({"push_status": "pushed", "pushed_at": utc_now_iso(), "error": ""})
        entry.pop("retry_stage", None)
        self._save(batch)

    def _checkpoint_creator(self, entry: Mapping[str, Any], books_payment_id: str, books_payment_number: str) -> None:
        if _text(entry.get("payment_type")).casefold() == "cheque":
            self._checkpoint_cheque_presentation(entry)
        try:
            update_and_verify_creator_record(
                self.creator, self.config.creator_app_link_name, self.config.creator_checkpoint_report_link_name,
                _text(entry.get("id")), {self.config.creator_books_id_field: books_payment_id, self.config.creator_payment_number_field: books_payment_number},
            )
        except ValueError as exc:
            raise ReconciliationError(
                "Creator checkpoint verification failed: Books_Transaction_Id and Payment# were not both saved. The existing Books payment will be reused on retry."
                if "read-back" in str(exc) else str(exc)
            ) from exc

    def _checkpoint_cheque_presentation(self, entry: Mapping[str, Any]) -> None:
        checkpoint_cheque_presentation(
            self.creator, app_link_name=self.config.creator_app_link_name,
            detail_report_link_name=self.config.cheque_detail_report_link_name,
            detail_form_link_name=self.config.cheque_detail_form_link_name, entry=entry,
        )

    def _preview_customer_finder(self, tokens: Sequence[str]) -> list[Mapping[str, Any]]:
        return preview_customer_finder(
            self.analytics, self.config, tokens, self._history_cache, self._full_history_cache,
            self._cache_hits, self._query_historical_customer_finder, lambda: self._history_was_full_export,
        )

    def _historical_queries(self, tokens: Sequence[str]) -> list[str]:
        return build_historical_finder_queries(self.config, tokens)

    def _query_historical_customer_finder(self, tokens: Sequence[str]) -> list[Mapping[str, Any]]:
        rows, used_export = query_historical_customer_finder(self.analytics, self.config, tokens)
        self._history_was_full_export = used_export
        return list(rows)

    def _check_customer_name(self, entry: dict[str, Any], historical_rows: Sequence[Mapping[str, Any]]) -> None:
        check_customer_name(entry, historical_rows, customer_finder_view_id=self.config.customer_finder_view_id)

    def _proposal(self, payment: Mapping[str, Any], customer_ids: Mapping[str, str], bank_transactions: Sequence[Mapping[str, Any]] | _BankCandidateIndex, used_transaction_ids: set[str]) -> dict[str, Any]:
        return build_proposal_entry(payment, customer_ids, bank_transactions, used_transaction_ids, self.config, self._find_transaction_details)

    def _find_transaction(self, payment: Mapping[str, Any], transactions: Sequence[Mapping[str, Any]], used_transaction_ids: set[str]) -> tuple[Mapping[str, Any] | None, str]:
        candidate, reason, _, _ = self._find_transaction_details(payment, transactions, used_transaction_ids)
        return candidate, reason

    def _find_transaction_details(self, payment: Mapping[str, Any], transactions: Sequence[Mapping[str, Any]] | _BankCandidateIndex, used_transaction_ids: set[str]) -> tuple[Mapping[str, Any] | None, str, list[Mapping[str, Any]], list[Mapping[str, Any]]]:
        return find_review_bank_transaction_details(payment, transactions, used_transaction_ids, default_date_tolerance_days=self.config.date_tolerance_days, amount_tolerance=self.config.amount_tolerance)

    def _current_bank_transaction(self, bank_id: str, bank_account_id: str) -> Mapping[str, Any]:
        current = get_uncategorized_bank_transaction(self.books, bank_id, bank_account_id)
        if not current:
            raise ReconciliationError("The proposed bank transaction is no longer uncategorized. Refresh the queue.")
        bank_name = next((name for name, aid in self.config.configured_banks() if aid == bank_account_id), "Bank")
        return {**current, "_review_bank_account_id": bank_account_id, "_review_bank_name": bank_name}

    def _require_same_date_amount(self, entry: Mapping[str, Any], transaction: Mapping[str, Any]) -> None:
        require_matching_date_amount(entry, transaction, default_date_tolerance_days=self.config.date_tolerance_days, amount_tolerance=self.config.amount_tolerance)

    def _customer_payment_payload(self, entry: Mapping[str, Any], allocations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        return review_customer_payment_payload(entry, allocations)

    def _all_creator_payments(self) -> list[dict[str, Any]]:
        return fetch_all_creator_payments(self.creator, self.config)

    def _all_uncategorized_bank_transactions(self) -> list[dict[str, Any]]:
        return fetch_all_uncategorized_bank_transactions(self.books, self.config)

    def _entry(self, entry_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        batch = self.load()
        entry = next((row for row in batch.get("entries", []) if _text(row.get("id")) == _text(entry_id)), None)
        if not entry:
            raise ReconciliationError(f"Review entry {entry_id} was not found.")
        return batch, entry

    def _empty_batch(self) -> dict[str, Any]:
        return {"version": 2, "reports": [{"payment_type": pt, "report": r} for pt, r in self.config.configured_reports()],
                "bank_accounts": [{"name": n, "account_id": aid} for n, aid in self.config.configured_banks()], "refreshed_at": None, "entries": []}

    def _save(self, batch: Mapping[str, Any]) -> None:
        statuses = {row["transaction_id"]: row.get("categorization_status", "pending") for row in batch.get("bank_suggestions", [])}
        for row in batch.get("bank_records", []):
            if row["transaction_id"] in statuses:
                row["categorization_status"] = statuses[row["transaction_id"]]
        write_atomic_json(self.config.state_path, batch)
