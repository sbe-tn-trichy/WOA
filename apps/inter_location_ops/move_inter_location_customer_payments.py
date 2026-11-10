"""Move reviewed customer payments with destination location number series."""

from __future__ import annotations
import importlib

import argparse
from collections.abc import Mapping, Sequence
from utils.file_utils import json
from datetime import datetime, date
from pathlib import Path

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.runtime.auth import get_books_client
from workflows.runtime.config import Config
from workflows.inter_location.payment_updates import plan_customer_payment_moves, submit_customer_payment_move, verify_customer_payment_batch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, default=Path("output/inter_location_payment_proposals.json"))
    parser.add_argument("--prefix", default="",
                        help="Payment series prefix; defaults to expected_number_prefix from proposal")
    parser.add_argument("--financial-year", default="FY 2025-26", choices=["FY 2025-26"])
    parser.add_argument("--last-suffix", type=int, default=None,
                        help="Override the current highest Books suffix; default reads Books")
    parser.add_argument("--batch-size", type=int, default=15)
    parser.add_argument(
        "--exclude-payment-id",
        action="append",
        default=list(Config.INTER_LOCATION_EXCLUDED_PAYMENT_IDS),
    )
    parser.add_argument("--audit", type=Path, default=Path("output/inter_location_customer_payment_apply_audit.json"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw_report = json.loads(args.proposal.read_text(encoding="utf-8"))
    report = raw_report if isinstance(raw_report, Mapping) else {}
    if (report.get("workspace_id"), report.get("view_id")) != (
            Config.ANALYTICS_WORKSPACE_ID, Config.INTER_LOCATION_CONTRA_VIEW_ID):
        raise ValueError("Proposal is not from the reviewed Query Table")
    raw_proposals = report.get("proposals")
    proposals = [p for p in raw_proposals
                 if isinstance(p, Mapping)
                 and p.get("financial_year") == args.financial_year
                 and date(2025, 4, 1) <= datetime.strptime(str(p.get("date", "")), "%d/%m/%Y").date()
                 <= date(2026, 3, 31)] if isinstance(raw_proposals, Sequence) else []
    books = get_books_client()
    prefix = args.prefix or (str(proposals[0].get("expected_number_prefix") or "") if proposals else "")
    if not prefix:
        raise ValueError("Prefix is required: pass --prefix or provide proposals with expected_number_prefix")
    moves = plan_customer_payment_moves(books, proposals,
                                        prefix=prefix, last_suffix=args.last_suffix,
                                        limit=args.batch_size,
                                        excluded_payment_ids=frozenset(args.exclude_payment_id))
    if not moves:
        raise ValueError("No eligible payments remain in this series")
    if len(moves) != args.batch_size:
        raise ValueError(f"Only {len(moves)} eligible payments; batch size is {args.batch_size}")
    for move in moves:
        print(f"{move['payment_id']}: {move['old_number']} -> {move['new_number']} "
              f"at {move['target_location_id']}")
    if not args.apply:
        print(f"Dry run: {len(moves)} payment(s); no updates applied.")
        return 0
    if not args.audit.is_absolute() and (not args.audit.parts or args.audit.parts[0] != "output"):
        parser.error("Relative audit path must be under output/")
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    audit: dict[str, object] = {"planned": moves, "submitted_payment_ids": [], "results": []}
    for move in moves:
        try:
            submit_customer_payment_move(books, move)
            audit["submitted_payment_ids"].append(move["payment_id"])  # type: ignore[union-attr]
        except Exception as exc:
            audit["error"] = f"{move['payment_id']}: {exc}"
            args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
            raise
        args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    try:
        audit["results"] = verify_customer_payment_batch(books, moves)
    except Exception as exc:
        audit["error"] = f"Batch read-back: {exc}"
        args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        raise
    args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(moves)} payment(s). Audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
