"""Compare a reviewed Google financial statement sheet with Books schedules."""
from __future__ import annotations
import importlib

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from utils.file_utils import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from zoho.core_sdk.base_client import BaseZohoClient
from workflows.runtime.auth import get_books_client
from workflows.core.checkpoint import atomic_text_writer, write_atomic_json
from workflows.financial_statement_comparison import (
    compare_statement_cells, fetch_schedule_reports, read_sheet_cells, render_comparison,
    validate_statement_totals,
)

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, default=ROOT / "examples/financial_statement_fy2425.mapping.json")
    parser.add_argument("--sheet-snapshot", type=Path, help="Use a captured sheet instead of live Google OAuth")
    parser.add_argument("--saved", action="store_true", help="Use saved Books schedules; no Books network access")
    parser.add_argument("--output", type=Path, default=ROOT / "output/sheet-schedule-comparison")
    parser.add_argument("--tolerance", type=Decimal, default=Decimal("1"))
    args = parser.parse_args(argv)
    raw_config = json.loads(args.mapping.read_text(encoding="utf-8"))
    config: dict[str, Any] = raw_config if isinstance(raw_config, dict) else {}
    lines_list: list[dict[str, Any]] = [l for l in config.get("lines", []) if isinstance(l, dict)]
    include_opening = any(term.get("period") == "opening" for line in lines_list for term in line.get("terms", []))
    if args.saved and not args.sheet_snapshot:
        parser.error("--saved requires --sheet-snapshot for fully offline replay")
    targets = [args.output / name for name in ("report.md", "comparison.json", "sheet-cells.json",
               "scheduleprofitandloss.json", "schedulebalancesheet.json")]
    if include_opening:
        targets.append(args.output / "schedulebalancesheet-opening.json")
    protected = {args.mapping.resolve()}
    if args.sheet_snapshot:
        protected.add(args.sheet_snapshot.resolve())
    # A saved source may be the existing output snapshot, but never overwrite it.
    written = targets[:2] + ([] if args.saved else targets[3:]) + ([] if args.sheet_snapshot else [targets[2]])
    if any(path.resolve() in protected for path in written):
        parser.error("Report outputs must not overwrite input files")
    if args.sheet_snapshot:
        raw_snap = json.loads(args.sheet_snapshot.read_text(encoding="utf-8"))
        snapshot: dict[str, Any] = raw_snap if isinstance(raw_snap, dict) else {}
        for key in ("spreadsheet_id", "from_date", "to_date"):
            if snapshot.get(key) != config.get(key):
                raise ValueError(f"Sheet snapshot {key} does not match configuration")
        cells = snapshot.get("cells", {})
        provenance = "captured Google cells at " + str(snapshot.get("captured_at", ""))
    else:
        requested_cells = list(dict.fromkeys([line["cell"] for line in lines_list] +
            [cell for group in config.get("total_checks", []) for cell in [group["total_cell"], *group["cells"]]]))
        cells = read_sheet_cells(str(config["spreadsheet_id"]), requested_cells,
                                 access_token=os.environ.get("GOOGLE_SHEETS_ACCESS_TOKEN", ""))
        provenance = "live Google cells at " + datetime.now(timezone.utc).isoformat()
    validate_statement_totals(cells, config.get("total_checks", []))
    if args.saved:
        names = ["profitandloss", "balancesheet"] + (["balancesheet-opening"] if include_opening else [])
        saved_reports: dict[str, Mapping[str, object]] = {}
        for name in names:
            loaded = json.loads((args.output / f"schedule{name}.json").read_text(encoding="utf-8"))
            saved_reports[name] = loaded if isinstance(loaded, Mapping) else {}
        # Use SDK validation against saved responses, including period and scope.
        from zoho.books.custom.reports import Reports
        class SavedClient(BaseZohoClient):
            def __init__(self) -> None:
                super().__init__("dummy-token", domain="in")
            def request(
                self,
                method: str,
                endpoint: str,
                json: Mapping[str, object] | Sequence[object] | None = None,
                data: Mapping[str, object] | str | bytes | None = None,
                params: Mapping[str, object] | None = None,
                headers: Mapping[str, str] | None = None,
                files: Mapping[str, object] | None = None,
                stream: bool = False,
                override_url: str | None = None,
                is_mutation: bool | None = None,
                timeout: int | None = None,
                **kwargs: Any,
            ) -> Any:
                name = endpoint.removeprefix("reports/schedule")
                if name == "balancesheet" and isinstance(params, Mapping) and params.get("to_date") != config["to_date"]:
                    name += "-opening"
                return saved_reports[name]
        books = SimpleNamespace(reports=Reports(SavedClient()))
        reports = fetch_schedule_reports(cast(Any, books), from_date=str(config["from_date"]), to_date=str(config["to_date"]),
                                         excluded_location_id=str(config["excluded_location_id"]),
                                         include_opening_balance_sheet=include_opening)
        provenance += "; saved Books schedules (retrieval metadata retained in JSON)"
    else:
        reports = fetch_schedule_reports(get_books_client(), from_date=str(config["from_date"]),
            to_date=str(config["to_date"]), excluded_location_id=str(config["excluded_location_id"]),
            include_opening_balance_sheet=include_opening)
        provenance += "; Books retrieved at " + datetime.now(timezone.utc).isoformat()
    rows = compare_statement_cells(cells, reports, lines_list, tolerance=args.tolerance)
    if not args.saved:
        for name, report in reports.items():
            target = args.output / f"schedule{name}.json"
            if target.resolve() in protected:
                raise ValueError("Books snapshot output must not overwrite an input")
            write_atomic_json(target, report)
    if not args.sheet_snapshot:
        write_atomic_json(args.output / "sheet-cells.json", {**{key: config[key] for key in
            ("spreadsheet_id", "from_date", "to_date")}, "captured_at": datetime.now(timezone.utc).isoformat(), "cells": cells})
    write_atomic_json(args.output / "comparison.json", [
        {key: str(value) if isinstance(value, Decimal) else value for key, value in asdict(row).items()} for row in rows])
    with atomic_text_writer(args.output / "report.md") as handle:
        handle.write(render_comparison(rows, source_url=config["source_url"], from_date=config["from_date"],
                    to_date=config["to_date"], provenance=provenance))
    print(f"{len(rows)} lines: " + ", ".join(f"{status}={sum(r.status == status for r in rows)}" for status in
          ("MATCH", "DIFFERENCE", "UNMAPPED")))
    print((args.output / "report.md").resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
