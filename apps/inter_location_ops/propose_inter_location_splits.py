"""Propose location-based payment splits for FY 2025-26 manual-review rows."""

from __future__ import annotations
import importlib

from utils.file_utils import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.runtime.auth import get_books_client
from workflows.runtime.config import Config
from helpers.operations.transactions import unwrap_record
from workflows.inter_location.split_proposals import propose_split


SOURCE = Path("output/inter_location_payment_proposals.json")
JSON_REPORT = Path("output/inter_location_split_proposals_fy2526.json")
MARKDOWN_REPORT = Path("output/inter_location_split_proposals_fy2526.md")
ALREADY_HANDLED = set(Config.INTER_LOCATION_HANDLED_SPLIT_PAYMENT_IDS)


def _get_entity(res: object, key: str) -> dict[str, Any]:
    raw = res if isinstance(res, Mapping) else {}
    return unwrap_record(raw, key)


def main() -> int:
    raw_source = json.loads(SOURCE.read_text(encoding="utf-8"))
    source = raw_source if isinstance(raw_source, Mapping) else {}
    if (source.get("view_id"), source.get("financial_year")) != (
        Config.INTER_LOCATION_CONTRA_VIEW_ID, "FY 2025-26"
    ):
        raise ValueError("Unexpected source proposal")
    books = get_books_client()
    results = []
    raw_proposals = source.get("proposals")
    proposals = raw_proposals if isinstance(raw_proposals, Sequence) else []
    for proposal in proposals:
        if not isinstance(proposal, Mapping):
            continue
        payment_id = str(proposal["payment_id"])
        if payment_id in ALREADY_HANDLED:
            continue
        kind = proposal["payment_type"]
        if kind == "Customer Payment":
            payment = _get_entity(books.customer_payments.get(payment_id), "payment")
            raw_allocations = payment.get("invoices") or []
            allocations = raw_allocations if isinstance(raw_allocations, Sequence) else []
            documents = [_get_entity(books.invoices.get(str(a["invoice_id"])), "invoice") for a in allocations if isinstance(a, Mapping)]
        elif kind == "Vendor Payment":
            payment = _get_entity(books.vendor_payments.get(payment_id), "vendorpayment")
            raw_allocations = payment.get("bills") or []
            allocations = raw_allocations if isinstance(raw_allocations, Sequence) else []
            documents = [_get_entity(books.bills.get(str(a["bill_id"])), "bill") for a in allocations if isinstance(a, Mapping)]
        else:
            raise ValueError(f"Unsupported payment type: {kind}")
        results.append(propose_split(dict(proposal), payment, documents))
    counts = Counter(result["status"] for result in results)
    report = {"source_view_id": source.get("view_id"), "financial_year": source.get("financial_year"),
              "excluded_handled_payment_ids": sorted(ALREADY_HANDLED),
              "checked_count": len(results), "status_counts": dict(counts), "proposals": results}
    JSON_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = ["# FY 2025–26 location split proposals", "",
             f"Checked {len(results)} current Books payments; {counts['split_proposed']} splits proposed; "
             f"{counts['manual_review']} other manual reviews.", "",
             "These are proposals only. No Books payments were changed.", "",
             "| Type | Payment | Current number | Date | Existing amount | Keep at current location | Create in other location(s) | Reason |",
             "| --- | --- | --- | --- | ---: | --- | --- | --- |"]
    for item in results:
        retain = item["retain"]
        keep = (f"{retain['location']}: {retain['amount']} " +
                ", ".join(d["number"] for d in retain["documents"])) if retain else ""
        create = "; ".join(
            f"{part['location']}: {part['amount']} " +
            ", ".join(d["number"] for d in part["documents"])
            for part in item["create"])
        values = (item["payment_type"], item["payment_id"], item["payment_number"],
                  item["date"], item["amount"], keep, create, item["reason"])
        lines.append("| " + " | ".join(str(v).replace("|", "\\|") for v in values) + " |")
    lines.append("")
    MARKDOWN_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Checked {len(results)}: {counts['split_proposed']} split proposals, "
          f"{counts['manual_review']} other manual reviews. Reports: {MARKDOWN_REPORT}, {JSON_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
