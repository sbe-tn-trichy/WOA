#!/usr/bin/env python3
"""Preview or post existing stock-transfer pairs from a reviewed execution journal."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
from utils import json
from pathlib import Path
import sys

try:
    from . import _bootstrap  # noqa: F401
except ImportError:
    import _bootstrap  # noqa: F401

from workflows.core.auth import get_books_client, get_inventory_client
from workflows.stock_transfer import TransferRecoveryPolicy, recover_stock_transfer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--expected-pairs", type=int, required=True)
    parser.add_argument("--maximum-invoice-total", type=Decimal, required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--vendor-id", required=True)
    parser.add_argument("--purchase-account-id", action="append", required=True)
    parser.add_argument("--apply", action="store_true", help="Post verified existing pairs; no new documents are created")
    args = parser.parse_args(argv)
    try:
        policy = TransferRecoveryPolicy(
            args.reference, args.expected_pairs, args.maximum_invoice_total, args.source,
            args.destination, args.customer_id, args.vendor_id, tuple(args.purchase_account_id),
        )
        print(f"{'Apply' if args.apply else 'Preview'}: {args.expected_pairs} existing pairs; "
              f"source={args.source}, destination={args.destination}, journal={args.journal}", flush=True)
        result = recover_stock_transfer(get_books_client(), get_inventory_client(),
            journal=args.journal, policy=policy, apply=args.apply)
    except Exception as exc:
        print(f"Recovery stopped: {exc}. Inspect the journal and live state before retrying.", file=sys.stderr)
        return 1
    print(json.dumps(asdict(result)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
