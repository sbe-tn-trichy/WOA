"""Find and analyze unique transaction number series for customer payments in Zoho Books using Zoho Analytics with FY filtering."""

import importlib
import argparse
from utils.file_utils import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.runtime.auth import get_analytics_client
from workflows.runtime.config import Config
from workflows.core.dates import get_fy_date_range
from workflows.customer_payments.inspection import (
    PaymentSeriesSummary,
    extract_series_info,
    fetch_customer_payments,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]


def display_results(series_list: list[PaymentSeriesSummary], total_records: int, filter_title: str) -> None:
    """Print results formatted as a table."""
    print("=" * 115)
    print(f" ZOHO BOOKS CUSTOMER PAYMENTS - {filter_title.upper()}")
    print("=" * 115)
    print(f"Transactions in this Period : {total_records:,}")
    print(f"Unique Series in Period     : {len(series_list)}")
    print("-" * 115)
    print(
        f"{'#':<3} | {'Series Prefix':<16} | {'Count':>7} | {'Range':<15} | {'Date Range':<23} | {'Sample Transaction'}"
    )
    print("-" * 115)

    for idx, s in enumerate(series_list, 1):
        print(
            f"{idx:<3} | {s['series_prefix']:<16} | {s['count']:>7,d} | {s['number_range']:<15} | {s['date_range']:<23} | {s['sample_first']}"
        )

    print("=" * 115)


def main():
    parser = argparse.ArgumentParser(
        description="Filter and analyze unique transaction number series for customer payments in Zoho Books."
    )
    parser.add_argument(
        "--fy",
        default="last",
        help="Financial Year filter: 'last' (default), 'current', '25-26', '24-25', '23-24', etc.",
    )
    parser.add_argument(
        "--workspace-id",
        default=Config.ANALYTICS_WORKSPACE_ID,
        help="Zoho Analytics workspace ID",
    )
    parser.add_argument(
        "--output-dir",
        default=str(WORKSPACE_ROOT / "output"),
        help="Directory to save outputs",
    )
    args = parser.parse_args()

    start_date, end_date, fy_id = get_fy_date_range(args.fy)
    fy_label = f"FY {fy_id} ({start_date:%d/%m/%Y} to {end_date:%d/%m/%Y})"

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug_fy = fy_label.split()[1].replace("-", "_").lower()
    json_path = out_dir / f"customer_payment_series_{slug_fy}.json"

    print(f"Connecting to Zoho Analytics (Workspace ID: {args.workspace_id})...")
    print(f"Filtering for: {fy_label}")
    records = fetch_customer_payments(get_analytics_client(), workspace_id=args.workspace_id)
    series_info, matched_count = extract_series_info(records, start_date=start_date, end_date=end_date)

    display_results(series_info, matched_count, filter_title=f"Transaction Number Series for {fy_label}")

    # Save to JSON
    json_data = {
        "financial_year": fy_label,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "generated_at": datetime.now().isoformat(),
        "total_period_records": matched_count,
        "total_series": len(series_info),
        "series": series_info,
    }
    json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
    print(f"\n[OK] JSON exported to: {json_path}")


if __name__ == "__main__":
    main()
