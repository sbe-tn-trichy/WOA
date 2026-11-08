#!/usr/bin/env python3
"""Sync stable line IDs, Mapping addresses, and StockCount formulas via Zoho Sheet API."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401

from workflows.runtime.auth import get_sheet_client
from workflows.runtime.config import Config
from workflows.neoseal_stock_count import (
    read_stable_sync_plan, apply_stable_sync_plan, verify_stockcount_formulas,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-id", default=Config.NEOSEAL_STOCK_COUNT_SHEET_ID)
    parser.add_argument("--apply", action="store_true", help="Write plan via Zoho Sheet API")
    parser.add_argument("--verify-only", action="store_true",
                        help="Verify expressions only; requires --apply because a temporary L1 probe is written")
    args = parser.parse_args(argv)
    if args.verify_only and not args.apply:
        parser.error("--verify-only requires --apply to authorize the temporary StockCount L1 probe")
    try:
        sheet = get_sheet_client()
        plan = read_stable_sync_plan(sheet, args.sheet_id)
        print(f"Product lines: {len(plan.formulas)//2}; new IDs: {plan.new_line_ids}; "
              f"unplaced Flat SKUs: {len(plan.unplaced_skus)}; "
              f"stale unmapped Mapping SKUs: {len(plan.stale_mapping_skus)}", flush=True)
        for sku in plan.unplaced_skus:
            print(f"Unplaced: {sku}", flush=True)
        for sku in plan.stale_mapping_skus:
            print(f"Stale unmapped Mapping row: {sku}", flush=True)
        if args.apply:
            if args.verify_only:
                count = verify_stockcount_formulas(sheet, args.sheet_id, plan.formulas)
                print(f"Verified {count} stored formulas", flush=True)
            else:
                count = apply_stable_sync_plan(sheet, args.sheet_id, plan,
                    progress=lambda message: print(message, flush=True))
                print(f"Updated {count} formulas and verified all planned expressions", flush=True)
    except Exception as exc:
        print(f"Stable sync failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
