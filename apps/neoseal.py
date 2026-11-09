#!/usr/bin/env python3
"""Unified CLI for Neoseal inventory, audit, and stock count operations."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")


SUBCOMMANDS = {
    "count": ("apps.neoseal_items.neoseal_stock_count", "Upsert active Neoseal flat stock into Zoho Sheet"),
    "sync": ("apps.neoseal_items.sync_neoseal_stockcount", "Sync stable line IDs, mapping addresses, and formulas"),
    "audit": ("apps.neoseal_items.audit_neoseal_items", "Audit Neoseal inventory items and price-list rates"),
    "export": ("apps.neoseal_items.export_neoseal_items", "Export items and flag missing vendor aliases"),
    "apply-names": ("apps.neoseal_items.apply_neoseal_name_updates", "Apply approved naming conventions and SKU updates"),
    "format": ("apps.neoseal_items.format_stock_count", "Format cell merges and borders in stock count worksheet"),
}


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0] in {"-h", "--help"}:
        print("usage: neoseal.py <command> [options]\n\nUnified CLI for Neoseal operations.\n\nCommands:")
        for name, (_, desc) in sorted(SUBCOMMANDS.items()):
            print(f"  {name:<14} {desc}")
        print("\nRun 'neoseal.py <command> --help' for details on a specific command.")
        return 0

    cmd = args_list[0]
    if cmd not in SUBCOMMANDS:
        print(f"Unknown command: '{cmd}'. Choose from: {', '.join(sorted(SUBCOMMANDS))}", file=sys.stderr)
        return 2

    module_name = SUBCOMMANDS[cmd][0]
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        module = importlib.import_module(module_name.split(".")[-1])
    orig_argv = sys.argv
    try:
        sys.argv = [f"{orig_argv[0]} {cmd}", *args_list[1:]]
        try:
            return module.main(args_list[1:])
        except TypeError:
            return module.main()
    finally:
        sys.argv = orig_argv


if __name__ == "__main__":
    raise SystemExit(main())
