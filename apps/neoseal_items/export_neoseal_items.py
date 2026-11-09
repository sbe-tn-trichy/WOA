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
from workflows.neoseal_audit.exporter import (
    FIELDS,
    export_inventory_items,
    export_row,
    write_export_rows as _write_rows,
)


def build_parser() -> argparse.ArgumentParser:
    from apps.inventory.export_items import build_parser as generic_parser

    parser = generic_parser()
    parser.set_defaults(output=Path("output/neoseal_items.csv"),
                        missing_output=Path("output/neoseal_items_missing_alias.csv"))
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
