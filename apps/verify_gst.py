#!/usr/bin/env python3
"""Unified CLI for GST verification, returns reconciliation, and cash-ledger audits."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Sequence

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")


SUBCOMMANDS = {
    "gstr1": ("apps.gst.verify_gstr1", "Verify GSTR-1 readiness using Analytics or live Books"),
    "gstr2": ("apps.gst.verify_gstr2", "Cross-check GSTR-2/2B returns against Books purchases"),
    "gstr3b-pnl": ("apps.gst.compare_gstr3b_pnl", "Compare full-year GSTR-3B JSON with Books Sales & COGS"),
    "cash-ledger": ("apps.gst.check_gst_cash_ledger", "Check GST cash-ledger balances against net tax"),
    "monthly": ("apps.gst.check_monthly_gst", "Audit monthly GST movements and balance differences"),
    "monthly-analytics": ("apps.gst.check_monthly_gst_analytics", "Audit monthly GST movements via Analytics"),
}


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0] in {"-h", "--help"}:
        print("usage: verify_gst.py <command> [options]\n\nUnified CLI for GST audits and returns.\n\nCommands:")
        for name, (_, desc) in sorted(SUBCOMMANDS.items()):
            print(f"  {name:<18} {desc}")
        print("\nRun 'verify_gst.py <command> --help' for details on a specific command.")
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
