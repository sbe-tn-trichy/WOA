#!/usr/bin/env python3
"""Preview or post one explicitly selected Creator cash transfer to Books."""
from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from utils.file_utils import json
from workflows.creator_payments import post_cash_transfer
from workflows.runtime.auth import get_books_client, get_creator_client
from workflows.runtime.config import Config


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transfer-id", required=True, help="One Creator Cash_Transfer record ID")
    parser.add_argument("--location-id", required=True, help="Explicit active Books location ID")
    parser.add_argument("--app", default=Config.PAYMENT_CREATOR_APP_LINK_NAME)
    parser.add_argument("--checkpoint-dir", type=Path, default=Path("output/cash_transfer"))
    parser.add_argument("--apply", action="store_true", help="Create missing payments, record deposit and update Creator")
    args = parser.parse_args(argv)
    try:
        result = post_cash_transfer(
            get_books_client(), get_creator_client(), transfer_id=args.transfer_id, app=args.app,
            location_id=args.location_id, checkpoint_dir=args.checkpoint_dir, apply=args.apply,
        )
    except Exception as exc:
        print(f"Cash transfer {args.transfer_id} failed: {exc}. Inspect its checkpoint before retrying.", file=sys.stderr)
        return 1
    payload = asdict(result)
    payload["payment_ids"] = list(result.payment_ids)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
