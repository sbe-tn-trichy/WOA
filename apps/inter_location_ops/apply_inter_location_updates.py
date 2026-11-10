"""Apply reviewed inter-location customer payment moves after a full Books preflight."""

from __future__ import annotations
import importlib

import argparse
from collections.abc import Mapping, Sequence
from utils.file_utils import json
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.inter_location.apply_updates import apply_verified_move, verify_proposed_pair
from workflows.runtime.auth import get_books_client
from workflows.runtime.config import Config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", default=Config.INTER_LOCATION_CLEARING_ACCOUNT_ID,
                        help="Clearing account ID")
    parser.add_argument("--proposal", type=Path, default=Path("output/inter_location_location_proposals.json"))
    parser.add_argument("--audit", type=Path, default=Path("output/inter_location_location_apply_audit.json"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    raw_report = json.loads(args.proposal.read_text(encoding="utf-8"))
    report = raw_report if isinstance(raw_report, Mapping) else {}
    if (
        report.get("view_id") != Config.INTER_LOCATION_CONTRA_VIEW_ID
        or report.get("workspace_id") != Config.ANALYTICS_WORKSPACE_ID
    ):
        raise ValueError("Proposal is not from the reviewed Query Table")
    raw_proposals = report.get("proposals")
    proposals = [item for item in raw_proposals if isinstance(item, Mapping) and item.get("status") == "proposed"] if isinstance(raw_proposals, Sequence) else []
    if len(proposals) != 15 or report.get("manual_review_pairs") != 3:
        raise ValueError("Proposal counts differ from the reviewed 15 moves and 3 holds")
    books = get_books_client()
    verified = []
    preflight_errors = []
    for index, proposal in enumerate(proposals, 1):
        try:
            item = verify_proposed_pair(books, proposal, clearing_account_id=args.account_id)
            verified.append(item)
            print(f"Preflight {index}/{len(proposals)}: {item['payment_id']} -> {item['to_location_id']}", flush=True)
        except Exception as exc:
            preflight_errors.append({"payment_id": proposal.get("customer_payment_id"), "error": str(exc)})
            print(f"Preflight {index}/{len(proposals)} failed: {proposal.get('customer_payment_id')}: {exc}", flush=True)
    if not args.apply:
        print(f"Dry run complete: {len(verified)} verified, {len(preflight_errors)} held. No Books locations changed.")
        return 0
    audit = {"started_at": datetime.now(timezone.utc).isoformat(), "source_view_id": report.get("view_id"),
             "preflight_count": len(verified), "preflight_errors": preflight_errors, "results": []}
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    if preflight_errors:
        args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
        raise ValueError(f"Preflight failed for {len(preflight_errors)} of {len(proposals)} proposed moves; no updates applied")
    for index, item in enumerate(verified, 1):
        try:
            result = apply_verified_move(books, item, clearing_account_id=args.account_id)
            audit["results"].append(result)
            print(f"Applied {index}/{len(verified)}: {result['payment_id']} ({result['status']})", flush=True)
        except Exception as exc:
            audit["error"] = f"{item['payment_id']}: {exc}"
            args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
            raise
        args.audit.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(audit['results'])} customer payment moves; audit: {args.audit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
