"""Apply the current FY 2025-26 vendor-payment proposals after full preflight."""

from __future__ import annotations
import importlib

import argparse
from utils.file_utils import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.runtime.auth import get_books_client
from workflows.runtime.config import Config
from workflows.inter_location.vendor_payment_proposals import VendorPaymentMove
from workflows.inter_location.vendor_payment_updates import preflight_vendor_moves, submit_vendor_move, verify_vendor_batch


SOURCE = Path("output/inter_location_payment_proposals.json")
NUMBERED = Path("output/inter_location_vendor_payment_proposals_fy2526.json")
AUDIT = Path("output/inter_location_vendor_payment_remaining_apply_audit.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw_proposal = json.loads(SOURCE.read_text(encoding="utf-8"))
    proposal = raw_proposal if isinstance(raw_proposal, Mapping) else {}
    raw_numbered = json.loads(NUMBERED.read_text(encoding="utf-8"))
    numbered = raw_numbered if isinstance(raw_numbered, Mapping) else {}
    if (proposal.get("view_id"), proposal.get("financial_year"),
            numbered.get("source_view_id")) != (
            Config.INTER_LOCATION_CONTRA_VIEW_ID, "FY 2025-26", Config.INTER_LOCATION_CONTRA_VIEW_ID):
        raise ValueError("Unexpected proposal source")
    raw_proposals = proposal.get("proposals")
    candidates = {str(row["payment_id"]): row for row in raw_proposals
                  if isinstance(row, Mapping) and row.get("status") == "proposed" and row.get("payment_type") == "Vendor Payment"} if isinstance(raw_proposals, Sequence) else {}
    raw_moves = numbered.get("moves")
    moves: list[VendorPaymentMove] = [cast(VendorPaymentMove, m) for m in raw_moves if isinstance(m, dict)] if isinstance(raw_moves, Sequence) else []
    if (not candidates or len(candidates) != len(moves)
            or {str(move["payment_id"]) for move in moves} != set(candidates)
            or numbered.get("held_count") != 0):
        raise ValueError("Numbered moves do not exactly match current proposed vendor payments")
    for move in moves:
        row = candidates[move["payment_id"]]
        if (move["from_location_id"] != row["from_location_id"]
                or move["to_location_id"] != row["to_location_id"]
                or move["bank_account_id"] != row["bank_account_id"]
                or move["bill_numbers"] != row["document_numbers"]
                or not move["destination_number"].startswith(str(row["expected_number_prefix"]))):
            raise ValueError(f"Numbered move differs from current proposal: {move['payment_id']}")
    groups: dict[str, list[VendorPaymentMove]] = defaultdict(list)
    for move in moves:
        groups[move["destination_number"].rsplit("-", 1)[0]].append(move)
    books = get_books_client()
    for prefix in sorted(groups):
        preflight_vendor_moves(books, groups[prefix])
    print(f"Preflight passed: {len(moves)} vendor payments in {len(groups)} destination series.")
    if not args.apply:
        print("Dry run: no Books changes.")
        return 0
    audit: dict[str, object] = {"planned": moves, "submitted_payment_ids": [], "results": []}
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    for prefix in sorted(groups):
        group = sorted(groups[prefix], key=lambda move: move["destination_number"])
        for move in group:
            try:
                submit_vendor_move(books, move)
                audit["submitted_payment_ids"].append(move["payment_id"])
            except Exception as exc:
                audit["error"] = f"Submit {move['payment_id']}: {exc}"
                AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
                raise
            AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        try:
            audit["results"].extend(verify_vendor_batch(books, group))
        except Exception as exc:
            audit["error"] = f"Verify {prefix}: {exc}"
            AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
            raise
        AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(audit['results'])} vendor payments. Audit: {AUDIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
