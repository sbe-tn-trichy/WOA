"""Review FY 2025-26 inter-location vendor-payment moves and destination numbers."""

from __future__ import annotations
import importlib

from utils.file_utils import json
from collections.abc import Mapping, Sequence
from pathlib import Path

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.runtime.auth import get_books_client
from workflows.runtime.config import Config
from workflows.inter_location.vendor_payment_proposals import propose_vendor_payment_moves


SOURCE = Path("output/inter_location_payment_proposals.json")
JSON_REPORT = Path("output/inter_location_vendor_payment_proposals_fy2526.json")
MARKDOWN_REPORT = Path("output/inter_location_vendor_payment_proposals_fy2526.md")


def main() -> int:
    raw_report = json.loads(SOURCE.read_text(encoding="utf-8"))
    report = raw_report if isinstance(raw_report, Mapping) else {}
    if (report.get("workspace_id"), report.get("view_id")) != (
            Config.ANALYTICS_WORKSPACE_ID, Config.INTER_LOCATION_CONTRA_VIEW_ID):
        raise ValueError("Proposal is not from the reviewed Query Table")
    raw_proposals = report.get("proposals")
    proposals = [p for p in raw_proposals if isinstance(p, Mapping)] if isinstance(raw_proposals, Sequence) else []
    moves, held = propose_vendor_payment_moves(get_books_client(), proposals)
    result = {"source_view_id": report.get("view_id"), "proposed_count": len(moves),
              "held_count": len(held), "moves": moves, "held": held}
    JSON_REPORT.parent.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = ["# FY 2025–26 vendor-payment number and location proposals", "",
             f"{len(moves)} Books-verified moves; {len(held)} held for review.", "",
             "Payments already using the destination number series are excluded from this report.", "",
             "Destination numbers are proposed from current Books series maxima and are not reserved.", "",
             "| Payment ID | Date | Amount | Bank account ID | Current number | Destination number | From location ID | To location ID | Bills |",
             "| --- | --- | ---: | --- | --- | --- | --- | --- | --- |"]
    for move in moves:
        lines.append("| " + " | ".join(str(v).replace("|", "\\|") for v in (
            move["payment_id"], move["date"], move["amount"], move["bank_account_id"],
            move["old_number"], move["destination_number"], move["from_location_id"],
            move["to_location_id"], ", ".join(move["bill_numbers"]))) + " |")
    lines += ["", "## Held", "",
              "| Payment ID | Reason |", "| --- | --- |"]
    for item in held:
        lines.append(f"| {item['payment_id']} | {item['reason'].replace('|', '\\|')} |")
    lines += ["", "No vendor payments were updated.", ""]
    MARKDOWN_REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(moves)} vendor payments proposed; {len(held)} held. Report: {MARKDOWN_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
