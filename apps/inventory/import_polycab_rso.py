#!/usr/bin/env python3
"""Import one Polycab RSO PDF into Zoho Books as a sales order."""

import importlib
import argparse
from utils.file_utils import json
import sys
from pathlib import Path

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows import get_books_client, import_polycab_rso_pdf
from workflows.runtime.config import Config
from workflows.runtime.auth import get_inventory_client


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf_path", help="Path to a machine-readable Polycab RSO PDF")
    parser.add_argument("--customer-id", default=Config.RSO_CUSTOMER_ID)
    parser.add_argument("--location-id", default=Config.EXPECTED_LOCATION_ID)
    parser.add_argument("--purchase-account-id", default=Config.FAN_PURCHASE_ACCOUNT_ID)
    args = parser.parse_args()

    result = import_polycab_rso_pdf(
        get_books_client(),
        args.pdf_path,
        customer_id=args.customer_id,
        location_id=args.location_id,
        inventory_client=get_inventory_client(),
        purchase_account_id=args.purchase_account_id,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
