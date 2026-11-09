"""Apply reviewed invoice payment date updates to Zoho Books."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Protocol

from helpers import unwrap_record

from workflows.core.checkpoint import write_atomic_json

logger = logging.getLogger(__name__)


class _CustomerPaymentsUpdateResource(Protocol):
    def get(self, resource_id: str, params: dict[str, object] | None = None) -> object: ...
    def update(self, resource_id: str, data: dict[str, object], params: dict[str, object] | None = None) -> object: ...


class BooksCustomerPaymentUpdaterClient(Protocol):
    @property
    def customer_payments(self) -> _CustomerPaymentsUpdateResource: ...


@dataclass
class PaymentUpdateResult:
    payment_id: str
    payment_number: str
    status: str  # "updated", "skipped", "failed", "planned"
    total_allocations: int
    updated_allocations: int
    error: str | None = None


class CustomerPaymentDateUpdater:
    """Updates customer payment invoice application dates in Zoho Books."""

    def __init__(self, books_client: BooksCustomerPaymentUpdaterClient):
        self.books = books_client

    def prepare_payment_payload(
        self,
        payment_detail: Mapping[str, object],
        target_allocations_by_inv: Mapping[str, str],  # invoice_id -> target_date (YYYY-MM-DD)
    ) -> dict[str, object]:
        """Construct the update payload for a customer payment preserving existing amounts and other fields."""
        invoices_payload: list[dict[str, object]] = []
        raw_invoices = payment_detail.get("invoices")
        invoices_list = raw_invoices if isinstance(raw_invoices, Sequence) else []
        for inv in invoices_list:
            if not isinstance(inv, Mapping):
                continue
            inv_id = str(inv.get("invoice_id") or "").strip()
            amt = float(str(inv.get("amount_applied") or inv.get("amount") or 0.0))
            if not inv_id or amt <= 0:
                continue

            inv_entry: dict[str, object] = {
                "invoice_id": inv_id,
                "amount_applied": amt,
            }
            if inv.get("invoice_payment_id"):
                inv_entry["invoice_payment_id"] = inv["invoice_payment_id"]
            if inv.get("tax_amount_withheld") is not None:
                inv_entry["tax_amount_withheld"] = float(str(inv.get("tax_amount_withheld") or 0.0))

            if inv_id in target_allocations_by_inv:
                target_dt = target_allocations_by_inv[inv_id]
                inv_entry["date"] = target_dt
                inv_entry["apply_date"] = target_dt
            elif inv.get("apply_date"):
                inv_entry["date"] = inv.get("apply_date")
                inv_entry["apply_date"] = inv.get("apply_date")
            elif inv.get("date"):
                inv_entry["date"] = inv.get("date")
                inv_entry["apply_date"] = inv.get("date")

            invoices_payload.append(inv_entry)

        payload: dict[str, object] = {"invoices": invoices_payload}
        for field in ("customer_id", "payment_mode", "date", "account_id", "reference_number", "description", "exchange_rate", "bank_charges"):
            val = payment_detail.get(field)
            if val is not None:
                payload[field] = val
        if payment_detail.get("amount") is not None:
            payload["amount"] = float(str(payment_detail["amount"]))

        return payload

    def execute_plan(
        self,
        plan: Mapping[str, object],
        *,
        execute: bool = False,
        checkpoint_path: Path | None = None,
    ) -> dict[str, object]:
        """Execute the date update plan across all affected customer payments."""
        raw_by_pmt = plan.get("by_payment")
        by_payment: Mapping[str, object] = raw_by_pmt if isinstance(raw_by_pmt, Mapping) else {}
        results: list[dict[str, object]] = []
        success_count = 0
        failed_count = 0
        skipped_count = 0

        for pmt_num, raw_allocs in by_payment.items():
            if not isinstance(raw_allocs, list) or not raw_allocs:
                continue
            allocations = [a for a in raw_allocs if isinstance(a, Mapping)]
            if not allocations:
                continue

            pmt_id = str(allocations[0].get("payment_id") or "")
            cust_name = str(allocations[0].get("customer_name") or "")

            # Map invoice_id -> target_applied_date
            targets_by_inv = {
                str(item["invoice_id"]): str(item["target_applied_date"])
                for item in allocations
                if item.get("invoice_id") and item.get("target_applied_date")
            }

            if not execute:
                results.append({
                    "payment_id": pmt_id,
                    "payment_number": pmt_num,
                    "customer_name": cust_name,
                    "status": "planned",
                    "allocations_count": len(allocations),
                    "target_dates": targets_by_inv,
                })
                continue

            try:
                # Fetch fresh payment from Books
                raw = self.books.customer_payments.get(pmt_id)
                current_pmt = unwrap_record(raw if isinstance(raw, Mapping) else {}, ("payment", "customerpayment"))
                
                payload = self.prepare_payment_payload(current_pmt, targets_by_inv)
                self.books.customer_payments.update(pmt_id, payload)

                results.append({
                    "payment_id": pmt_id,
                    "payment_number": pmt_num,
                    "customer_name": cust_name,
                    "status": "updated",
                    "allocations_count": len(allocations),
                    "target_dates": targets_by_inv,
                })
                success_count += 1
            except Exception as exc:
                logger.exception("Failed to update payment %s (%s)", pmt_num, pmt_id)
                results.append({
                    "payment_id": pmt_id,
                    "payment_number": pmt_num,
                    "customer_name": cust_name,
                    "status": "failed",
                    "allocations_count": len(allocations),
                    "error": str(exc),
                })
                failed_count += 1

        summary = {
            "total_payments": len(by_payment),
            "planned": len(results) if not execute else 0,
            "updated": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "dry_run": not execute,
        }

        output_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "results": results,
        }

        if checkpoint_path:
            write_atomic_json(checkpoint_path, output_payload, default=None)

        return output_payload
