#!/usr/bin/env python3
"""Export Inventory items for a purchase account and flag missing vendor aliases."""

from __future__ import annotations
import importlib

import argparse
from pathlib import Path
from collections.abc import Sequence

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.runtime.auth import get_inventory_client
from workflows.item_catalog import export_inventory_items


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--purchase-account-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/items.csv"),
    )
    parser.add_argument(
        "--missing-output",
        type=Path,
        default=Path("output/items_missing_alias.csv"),
    )
    parser.add_argument("--status", choices=["active", "inactive", "all"], default="active")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows, missing = export_inventory_items(
        get_inventory_client(),
        args.purchase_account_id,
        status=args.status,
        output_path=args.output,
        missing_output_path=args.missing_output,
    )
    print(f"Exported {len(rows)} items; {len(missing)} missing aliases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
