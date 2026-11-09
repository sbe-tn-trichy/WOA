#!/usr/bin/env python3
"""Repair unused credits on previously pushed payment-review Books payments."""

from __future__ import annotations
import importlib

import argparse
from utils.file_utils import json
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.collection_reconciliation.repair import (
    _payment_payload,
    _update_payload,
    _write_checkpoint,
    repair_payment_allocations,
)
from workflows.runtime.auth import get_books_client

# Backward compatibility alias
run = repair_payment_allocations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "state",
        type=Path,
        nargs="?",
        default=Path("output/collection_reconciliation/online_payments_review.json"),
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--checkpoint", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    state_raw = json.loads(args.state.read_text(encoding="utf-8"))
    if not isinstance(state_raw, Mapping):
        raise ValueError(f"State file {args.state} must be a JSON object")
    state: Mapping[str, Any] = state_raw
    checkpoint = args.checkpoint or Path(
        "output/collection_reconciliation/payment_allocation_repair.json"
    )
    result = repair_payment_allocations(
        get_books_client(), state, execute=args.execute, checkpoint_path=checkpoint
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
