#!/usr/bin/env python3
"""Unified CLI for Inter-location contra reviews, proposals, and updates."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")


SUBCOMMANDS = {
    "contra": ("apps.inter_location_ops.review_inter_location_contra", "Review contra pairs and location consistency in Books"),
    "propose-location": ("apps.inter_location_ops.propose_inter_location_updates", "Propose location updates across allocated documents"),
    "propose-split": ("apps.inter_location_ops.propose_inter_location_splits", "Propose payment splits across conflicting locations"),
    "propose-customer": ("apps.vendor_payments.propose_inter_location_payment_updates", "Propose customer payment moves by fiscal year"),
    "propose-vendor": ("apps.vendor_payments.propose_fy2526_vendor_payment_updates", "Propose vendor payment moves for reviewed FY"),
    "recheck": ("apps.vendor_payments.recheck_inter_location_payment_proposals", "Recheck payment proposals against current Books state"),
    "show-proposals": ("apps.vendor_payments.show_fy2526_payment_proposals", "Display customer payment proposals and target numbers"),
    "apply-location": ("apps.inter_location_ops.apply_inter_location_updates", "Apply reviewed location proposals to Books documents"),
    "apply-vendor": ("apps.vendor_payments.apply_remaining_vendor_payment_proposals", "Apply proposed vendor payment location updates"),
    "update-vendor": ("apps.vendor_payments.update_selected_vendor_payments", "Update selected vendor payments with dry-run protection"),
    "move-customer": ("apps.inter_location_ops.move_inter_location_customer_payments", "Move customer payments to matching locations"),
    "query-table": ("apps.inter_location_ops.manage_inter_location_contra_query_table", "Create or update Analytics contra Query Table"),
}


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0] in {"-h", "--help"}:
        print("usage: inter_location.py <command> [options]\n\nUnified CLI for Inter-location operations.\n\nCommands:")
        for name, (_, desc) in sorted(SUBCOMMANDS.items()):
            print(f"  {name:<18} {desc}")
        print("\nRun 'inter_location.py <command> --help' for details on a specific command.")
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
