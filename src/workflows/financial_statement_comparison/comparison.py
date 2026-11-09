"""Exact-cell comparisons with explicit Books account or section mappings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from collections.abc import Iterator, Mapping, Sequence
from typing import Protocol
from utils.file_utils import json
import re

from utils.http_utils import http_transport

from utils.http_utils.http import request_json
from workflows.core.matching import to_finite_decimal

KEYS = {"profitandloss": "schedule_profit_and_loss", "balancesheet": "schedule_balance_sheet"}


class ScheduleReportsResource(Protocol):
    def profit_and_loss_schedule_format(
        self, *, from_date: str, to_date: str, rule: str,
        cash_based: bool = False,
    ) -> Mapping[str, object]: ...
    def balance_sheet_schedule_format(
        self, *, from_date: str, to_date: str, rule: str,
        cash_based: bool = False,
    ) -> Mapping[str, object]: ...


class BooksScheduleClient(Protocol):
    @property
    def reports(self) -> ScheduleReportsResource: ...


@dataclass(frozen=True)
class ComparisonLine:
    label: str
    cell: str
    sheet_amount: Decimal
    books_amount: Decimal | None
    difference: Decimal | None
    status: str
    source: str


def fetch_schedule_reports(books: BooksScheduleClient, *, from_date: str, to_date: str,
                           excluded_location_id: str,
                           include_opening_balance_sheet: bool = False) -> dict[str, Mapping[str, object]]:
    """Read each schedule once with a verified branch exclusion and explicit FY."""
    if date.fromisoformat(from_date) > date.fromisoformat(to_date):
        raise ValueError("Invalid date range")
    if not excluded_location_id.strip():
        raise ValueError("An excluded location ID is required")
    rule = json.dumps({"columns": [{"index": 1, "field": "location_name",
        "value": [excluded_location_id], "comparator": "not_in", "group": "branch"}],
        "criteria_string": "1"})
    reports: dict[str, Mapping[str, object]] = {
        "profitandloss": books.reports.profit_and_loss_schedule_format(from_date=from_date, to_date=to_date, rule=rule),
        "balancesheet": books.reports.balance_sheet_schedule_format(from_date=from_date, to_date=to_date, rule=rule),
    }
    if include_opening_balance_sheet:
        opening_date = (date.fromisoformat(from_date) - timedelta(days=1)).isoformat()
        reports["balancesheet-opening"] = books.reports.balance_sheet_schedule_format(
            from_date=opening_date, to_date=opening_date, rule=rule)
    return reports


def read_sheet_cells(spreadsheet_id: str, cells: Sequence[str], *, access_token: str,
                     session: object = http_transport) -> dict[str, object]:
    """Read exact qualified A1 cells using the caller's Google OAuth token."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", spreadsheet_id) or not access_token:
        raise ValueError("A spreadsheet ID and Google OAuth token are required")
    payload = request_json(
        "GET",
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchGet",
        session=session,
        headers={"Authorization": f"Bearer {access_token}"},
        params={"ranges": list(cells), "valueRenderOption": "UNFORMATTED_VALUE"},
        timeout=30,
    )
    if not isinstance(payload, Mapping):
        raise ValueError("Invalid response payload from Google Sheets")
    ranges_val = payload.get("valueRanges")
    ranges = ranges_val if isinstance(ranges_val, list) else []
    if len(ranges) != len(cells):
        raise ValueError("Google Sheets did not return every requested cell")
    result: dict[str, object] = {}
    for cell, entry in zip(cells, ranges):
        if not isinstance(entry, Mapping):
            raise ValueError(f"Missing or invalid entry for cell: {cell}")
        values = entry.get("values")
        if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], list) or len(values[0]) != 1:
            raise ValueError(f"Missing or non-scalar sheet cell: {cell}")
        result[cell] = values[0][0]
    return result


def _amount(value: object) -> Decimal:
    amount = to_finite_decimal(value, allow_commas=True)
    if amount is None:
        raise ValueError(f"Invalid financial amount: {value!r}")
    return amount


def _nodes(nodes: Sequence[Mapping[str, object]], path: tuple[str, ...] = ()) -> Iterator[tuple[Mapping[str, object], tuple[str, ...]]]:
    for node in nodes:
        current = path + (str(node.get("name", "")),)
        if not node.get("section"):
            yield node, current
        txs = node.get("account_transactions", [])
        if isinstance(txs, Sequence):
            seq = [t for t in txs if isinstance(t, Mapping)]
            yield from _nodes(seq, current)


def compare_statement_cells(cells: Mapping[str, object], reports: Mapping[str, Mapping[str, object]],
                            mappings: Sequence[Mapping[str, object]], *,
                            tolerance: Decimal = Decimal("1")) -> list[ComparisonLine]:
    """Compare every mapped cell; unknown sources remain visible as UNMAPPED.

    Account terms use their own total. Set include_children explicitly for a
    schedule parent subtotal. Repeated section closing rows are never summed.
    Section terms use an exact name path; multipliers allow reviewed netting.
    """
    tolerance = _amount(tolerance)
    if tolerance < 0:
        raise ValueError("Tolerance must be non-negative")
    rows: list[ComparisonLine] = []
    seen: set[str] = set()
    for mapping in mappings:
        cell = str(mapping["cell"])
        if cell in seen:
            raise ValueError(f"Duplicate source cell: {cell}")
        seen.add(cell)
        filed = _amount(cells[cell])
        raw_terms = mapping.get("terms")
        terms: list[Mapping[str, object]] = [t for t in raw_terms if isinstance(t, Mapping)] if isinstance(raw_terms, Sequence) else []
        if mapping.get("remaining_expense_path"):
            if terms:
                raise ValueError("Remaining expense mapping cannot also specify terms")
            rem_path = mapping.get("remaining_expense_path")
            scope = tuple(str(x) for x in rem_path) if isinstance(rem_path, Sequence) else ()
            pnl_report = reports["profitandloss"]
            pnl_tree = pnl_report.get(KEYS["profitandloss"], [])
            pnl_seq = [n for n in pnl_tree if isinstance(n, Mapping)] if isinstance(pnl_tree, Sequence) else []
            candidates = list(_nodes(pnl_seq))
            if sum(path == scope for _, path in candidates) != 1:
                raise ValueError("Remaining expense scope must identify one schedule section")
            assigned: list[Mapping[str, object]] = []
            for other in mappings:
                if other is mapping:
                    continue
                o_terms = other.get("terms")
                if isinstance(o_terms, Sequence):
                    assigned.extend(t for t in o_terms if isinstance(t, Mapping) and t.get("report") == "profitandloss")
            terms = []
            account_ids: set[str] = set()
            for node, path in candidates:
                if path[:len(scope)] != scope or not node.get("account_id"):
                    continue
                if any(("name" in term and node.get("name") == term["name"]) or
                       ("account_id" in term and str(node.get("account_id")) == str(term["account_id"])) or
                       ("path" in term and isinstance(term["path"], Sequence) and path[:len(term["path"])] == tuple(str(x) for x in term["path"]))
                       for term in assigned):
                    continue
                account_id = str(node["account_id"])
                if account_id in account_ids:
                    raise ValueError(f"Duplicate remaining expense account: {account_id}")
                account_ids.add(account_id)
                terms.append({"report": "profitandloss", "account_id": account_id})
        total = Decimal()
        sources: list[str] = []
        missing: list[str] = []
        for term in terms:
            if not isinstance(term, Mapping):
                continue
            if sum(key in term for key in ("path", "account_id", "name")) != 1:
                raise ValueError("A Books term needs exactly one path, account_id or name")
            period = str(term.get("period", "current"))
            if period not in ("current", "opening") or (period == "opening" and term.get("report") != "balancesheet"):
                raise ValueError("Opening-period terms require a balance-sheet source")
            report_key = str(term["report"]) + ("-opening" if period == "opening" else "")
            report = reports[report_key]
            rep_tree = report.get(KEYS[str(term["report"])], [])
            rep_seq = [n for n in rep_tree if isinstance(n, Mapping)] if isinstance(rep_tree, Sequence) else []
            candidates = list(_nodes(rep_seq))
            matches = [node for node, path in candidates if
                (path == tuple(str(x) for x in term["path"]) if "path" in term and isinstance(term["path"], Sequence) else
                 str(node.get("account_id", "")) == str(term["account_id"]) if "account_id" in term else
                 node.get("name") == term["name"])]
            term_path = term.get("path")
            path_str = " / ".join(str(x) for x in term_path) if isinstance(term_path, Sequence) else ""
            source = str(term.get("account_id") or term.get("name") or path_str)
            if mapping.get("remaining_expense_path") and len(matches) == 1:
                source = str(matches[0].get("name", "")) + " (" + f"{_amount(matches[0].get('total')):,.2f}" + ")"
            page_ctx = report.get("page_context")
            if term.get("report") == "balancesheet" and isinstance(page_ctx, Mapping) and page_ctx.get("to_date"):
                source += " (as of " + str(page_ctx["to_date"]) + ")"
            if not matches:
                missing.append(source)
                continue
            if len(matches) != 1:
                raise ValueError(f"Ambiguous Books source: {source}")
            node = matches[0]
            field = "total_sub_account" if term.get("include_children") and node.get("is_child_present") else "total"
            total += _amount(node.get(field)) * _amount(term.get("multiplier", 1))
            sources.append(source)
        mapped = bool(terms) and not missing
        if mapping.get("note"):
            sources.append(str(mapping["note"]))
        difference = total - filed if mapped else None
        status = "MATCH" if mapped and difference is not None and abs(difference) <= tolerance else "DIFFERENCE" if mapped else "UNMAPPED"
        label_val = str(mapping.get("label", ""))
        note_fallback = str(mapping.get("note", "Needs reviewed ledger mapping"))
        source_val = "; ".join(sources + ["Missing: " + x for x in missing]) or note_fallback
        rows.append(ComparisonLine(label_val, cell, filed, total if mapped else None,
            difference, status, source_val))
    return rows


def validate_statement_totals(cells: Mapping[str, object], groups: Sequence[Mapping[str, object]]) -> None:
    """Verify source line sums, and require the two sides of each statement to balance."""
    totals: dict[str, list[Decimal]] = {}
    for group in groups:
        total_cell = str(group["total_cell"])
        actual = _amount(cells[total_cell])
        group_cells = group.get("cells")
        cell_seq = [str(c) for c in group_cells] if isinstance(group_cells, Sequence) else []
        if abs(sum((_amount(cells[c]) for c in cell_seq), Decimal()) - actual) > Decimal("0.01"):
            raise ValueError(f"Sheet line sum does not agree with {group['total_cell']}")
        statement = str(group["statement"])
        totals.setdefault(statement, []).append(actual)
    for statement, amounts in totals.items():
        if len(amounts) != 2 or abs(amounts[0] - amounts[1]) > Decimal("0.01"):
            raise ValueError(f"Sheet {statement} does not balance")


def render_comparison(rows: Sequence[ComparisonLine], *, source_url: str,
                      from_date: str, to_date: str, provenance: str) -> str:
    """Render amounts and qualifications without changing either source."""
    def escaped(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    def mismatch_group(row: ComparisonLine) -> str:
        # The source workbook has liabilities in B and assets in D.
        sheet, _, cell = row.cell.rpartition("!")
        if sheet.strip("'") == "Balance Sheet":
            if cell.startswith("B"):
                return "Liabilities and equities"
            if cell.startswith("D"):
                return "Assets"
        return "Profit and loss / other lines"

    def append_table(group: Sequence[ComparisonLine]) -> None:
        text.extend(["| Line | Sheet cell | Sheet | Books | Difference | Status | Books source / qualification |",
                     "|---|---|---:|---:|---:|---|---|"])
        for row in group:
            amounts = [f"{value:,.2f}" if value is not None else "—" for value in
                       (row.sheet_amount, row.books_amount, row.difference)]
            text.append("| " + " | ".join(map(escaped, [row.label, row.cell, *amounts, row.status, row.source])) + " |")
        text.append("")
    text = ["# Google Sheet versus Zoho Books schedules", "",
        f"Source: [{source_url}]({source_url})", f"Period: {from_date} to {to_date}; accrual; INR.",
        f"Data: {provenance}",
        "Endpoints: reports/scheduleprofitandloss and reports/schedulebalancesheet.",
        "Difference = Books minus sheet. Branch rule echo is verified; this alone does not prove transaction-level scope.",
        "Mappings reflect disclosed account classifications; differences require accounting review.", ""]
    for status, title in (("DIFFERENCE", "Mismatches"), ("UNMAPPED", "Unmapped lines"), ("MATCH", "Matches")):
        group = [row for row in rows if row.status == status]
        text.extend([f"## {title} ({len(group)})", ""])
        if not group:
            text.extend(["None.", ""])
            continue
        if status == "DIFFERENCE":
            for category in ("Liabilities and equities", "Assets", "Profit and loss / other lines"):
                subgroup = [row for row in group if mismatch_group(row) == category]
                if subgroup:
                    text.extend([f"### {category} ({len(subgroup)})", ""])
                    append_table(subgroup)
        else:
            append_table(group)
    return "\n".join(text) + "\n"
