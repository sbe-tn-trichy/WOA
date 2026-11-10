#!/usr/bin/env python3
"""Download Zoho Analytics Accounts and Items into one local SQLite file."""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.analytics_catalog import AnalyticsCatalog
from workflows.item_catalog import sync_analytics_items
from workflows.runtime.auth import get_analytics_client
from workflows.runtime.config import Config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/analytics/items.sqlite"))
    parser.add_argument("--catalog-dir", type=Path, default=Path("data/analytics"))
    parser.add_argument("--workspace-id", default=Config.ANALYTICS_WORKSPACE_ID)
    args = parser.parse_args()
    result = sync_analytics_items(
        get_analytics_client(), AnalyticsCatalog(None, args.workspace_id, args.catalog_dir), args.db,
    )
    print(f"Saved {result.database.resolve()}")
    for table, count in result.row_counts.items():
        print(f"{table}: {count:,} rows")
    print(f"Last successful Analytics metadata sync: {result.last_successful_metadata_sync_at}")


if __name__ == "__main__":
    main()
