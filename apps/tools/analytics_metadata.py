"""Analyze cached Analytics metadata; use --sync to refresh it manually."""

import argparse
from utils.file_utils import json
from pathlib import Path

from workflows.analytics_catalog import AnalyticsCatalog
from workflows.runtime.auth import get_analytics_client
from workflows.runtime.config import Config
from workflows.core.checkpoint import write_atomic_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", default=Config.ANALYTICS_WORKSPACE_ID)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--view-id", help="Limit analysis and include transitive workflow impact")
    parser.add_argument("--sync", action="store_true", help="Manually refresh metadata before analysis")
    args = parser.parse_args()
    catalog = AnalyticsCatalog(get_analytics_client() if args.sync else None, args.workspace_id, args.output)
    if args.sync:
        catalog.sync()
    result = catalog.analyze(args.view_id)
    write_atomic_json(catalog.output_dir / "analysis.json", result)
    lines = ["# Analytics metadata analysis", "",
             f"Last successful metadata sync (UTC): {result['last_successful_sync_at']}", "",
             "Source: cached SQLite. Refresh manually with `apps/analytics_metadata.py --sync`.", "",
             "| View | Type | Workflows |", "|---|---|---|"]
    views = result.get("views", [])
    lines.extend("| " + " | ".join(str(v.get(k, "")).replace("|", "\\|").replace("\n", " ")
                 for k in ("name", "view_type", "used_by_workflows")) + " |" for v in views)
    (catalog.output_dir / "analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sync_info = result.get("sync", {})
    print(json.dumps({"database": str(catalog.output_dir / "metadata.sqlite"),
                      "counts": sync_info.get("counts", {}),
                      "last_successful_sync_at": result.get("last_successful_sync_at"),
                      "source": result.get("source")}, indent=2))


if __name__ == "__main__":
    main()
