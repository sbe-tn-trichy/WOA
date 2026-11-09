"""Update the three reviewed FY 2025-26 IDFC vendor payments."""

from __future__ import annotations
import importlib

import argparse
from collections.abc import Mapping, Sequence
from utils.file_utils import json
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


SOURCE = Path("output/inter_location_vendor_payment_proposals_fy2526.json")
AUDIT = Path("output/inter_location_vendor_payment_selected_apply_audit.json")
SELECTED = Config.SELECTED_VENDOR_PAYMENT_MOVES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw_report = json.loads(SOURCE.read_text(encoding="utf-8"))
    report = raw_report if isinstance(raw_report, Mapping) else {}
    if report.get("source_view_id") != Config.INTER_LOCATION_CONTRA_VIEW_ID:
        raise ValueError("Unexpected vendor proposal source")
    raw_moves = report.get("moves")
    moves: list[VendorPaymentMove] = sorted(
        (cast(VendorPaymentMove, m) for m in raw_moves if isinstance(m, dict) and m.get("payment_id") in SELECTED),
        key=lambda m: m["destination_number"]
    ) if isinstance(raw_moves, Sequence) else []
    if len(moves) != 3 or any(m["destination_number"] != SELECTED[m["payment_id"]] for m in moves):
        raise ValueError("Selected vendor proposal differs from the reviewed three moves")
    books = get_books_client()
    preflight_vendor_moves(books, moves)
    for move in moves:
        print(f"{move['payment_id']}: {move['old_number']} -> {move['destination_number']}")
    if not args.apply:
        print("Dry run: 3 verified; no vendor payments updated.")
        return 0
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    audit: dict[str, object] = {"planned": moves, "submitted_payment_ids": [], "results": []}
    for move in moves:
        try:
            submit_vendor_move(books, move)
            audit["submitted_payment_ids"].append(move["payment_id"])  # type: ignore[union-attr]
        except Exception as exc:
            audit["error"] = f"{move['payment_id']}: {exc}"
            AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
            raise
        AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    try:
        audit["results"] = verify_vendor_batch(books, moves)
    except Exception as exc:
        audit["error"] = f"Batch read-back: {exc}"
        AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        raise
    AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"Verified 3 vendor payments. Audit: {AUDIT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
