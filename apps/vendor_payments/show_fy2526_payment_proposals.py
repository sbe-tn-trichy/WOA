"""Create a focused FY 2025-26 review from the saved inter-location proposals."""

from __future__ import annotations
import importlib

from utils.file_utils import json
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, date
from pathlib import Path

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.runtime.auth import get_books_client
from workflows.runtime.config import Config
from workflows.inter_location.payment_updates import plan_customer_payment_moves


SOURCE = Path("output/inter_location_payment_proposals.json")
DESTINATION = Path("output/inter_location_payment_proposals_fy2526.md")


def main() -> int:
    raw_report = json.loads(SOURCE.read_text(encoding="utf-8"))
    report = raw_report if isinstance(raw_report, Mapping) else {}
    if report.get("view_id") != Config.INTER_LOCATION_CONTRA_VIEW_ID:
        raise ValueError("Unexpected proposal source")
    raw_proposals = report.get("proposals")
    payments = [p for p in raw_proposals
                if isinstance(p, Mapping)
                and date(2025, 4, 1) <= datetime.strptime(str(p.get("date", "")), "%d/%m/%Y").date()
                <= date(2026, 3, 31)] if isinstance(raw_proposals, Sequence) else []
    payments.sort(key=lambda p: (str(p.get("date", "")), str(p.get("payment_id", ""))))
    counts = Counter(p.get("status") for p in payments)
    prefix = str(payments[0].get("expected_number_prefix") or "") if payments else ""
    if not prefix:
        raise ValueError("No prefix found in proposals; ensure proposals include expected_number_prefix")
    limit = 15
    batch_moves = plan_customer_payment_moves(
        get_books_client(), payments, prefix=prefix, limit=limit,
        excluded_payment_ids=frozenset(Config.INTER_LOCATION_EXCLUDED_PAYMENT_IDS))
    if not batch_moves:
        raise ValueError("No live Books-verified candidates found")
    by_id = {str(p.get("payment_id")): p for p in payments}
    proposed_numbers = {move["payment_id"]: move["new_number"] for move in batch_moves}
    lines = ["# FY 2025–26 inter-location payment proposals", "",
             f"Source: Zoho Analytics Query Table {report.get('view_id')}. "
             f"{len(payments)} payments: {counts['proposed']} proposed, "
             f"{counts['manual_review']} manual review.", "",
             f"## Next {len(batch_moves)} customer-payment candidates", "",
             "These destination numbers are planned from current Books data; they are not reserved.", "",
             "| Payment ID | Date | Amount | Bank | From | To | Invoice | Destination number |",
             "| --- | --- | ---: | --- | --- | --- | --- | --- |"]
    for move in batch_moves:
        p = by_id[move["payment_id"]]
        lines.append("| " + " | ".join(str(v).replace("|", "\\|") for v in (
            p["payment_id"], p["date"], p["amount"], p["bank_account_name"],
            p["from_location"], p["to_location"], ", ".join(p["document_numbers"]),
            move["new_number"])) + " |")
    lines += ["", "## All FY 2025–26 payments", "",
              "| Status | Type | Payment ID | Date | Amount | Bank | From | To | Documents | Destination number | Reason |",
              "| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |"]
    for p in payments:
        lines.append("| " + " | ".join(str(v).replace("|", "\\|") for v in (
            p["status"], p["payment_type"], p["payment_id"], p["date"], p["amount"],
            p["bank_account_name"], p["from_location"], p["to_location"],
            ", ".join(p["document_numbers"]), proposed_numbers.get(p["payment_id"], "Pending"),
            p["reason"])) + " |")
    lines += ["", "No Books changes are made by this report.", ""]
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    DESTINATION.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {DESTINATION}: {len(payments)} payments; {len(batch_moves)} numbered batch candidates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
