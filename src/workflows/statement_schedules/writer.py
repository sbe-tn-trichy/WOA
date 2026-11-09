"""Google Sheets schedule cell formatting, batching and verified writes."""
from __future__ import annotations

from __future__ import annotations

from utils.file_utils import json
from pathlib import Path
import re
from collections.abc import Mapping, Sequence

from utils.http_utils import http_transport

from utils.http_utils.http import request_json
from .checkbox import checkbox_formula_updates


def grid_address(address: str) -> tuple[str, int, int, int, int]:
    match = re.fullmatch(r"'((?:[^']|'')+)'!([A-Z]+)([1-9]\d*)(?::([A-Z]+)([1-9]\d*))?", address)
    if match is None:
        raise ValueError(f"Invalid qualified A1 range: {address}")
    def column(text: str) -> int:
        value = 0
        for char in text:
            value = value * 26 + ord(char) - ord("A") + 1
        return value - 1
    name, first_col, first_row, last_col, last_row = match.groups()
    return name.replace("''", "'"), int(first_row) - 1, column(first_col), int(last_row or first_row), column(last_col or first_col) + 1


def cell_data(value: object, *, literal: bool) -> dict[str, object]:
    if value == "":
        return {}
    if isinstance(value, (float, int)):
        return {"userEnteredValue": {"numberValue": value}}
    field = "formulaValue" if isinstance(value, str) and value.startswith("=") and not literal else "stringValue"
    return {"userEnteredValue": {field: value}}


def update_requests(values: Mapping[str, Sequence[Sequence[object]]], config: Mapping[str, object]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    asset_summary = config.get("asset_layout") == "reviewed_statement"
    sheets_cfg = config.get("sheets")
    if not isinstance(sheets_cfg, Mapping):
        raise ValueError("Missing sheets config")
    sheet_ids = config.get("sheet_ids")
    if not isinstance(sheet_ids, Mapping):
        raise ValueError("Missing sheet_ids config")
    for address, rows in values.items():
        title, first_row, first_col, end_row, end_col = grid_address(address)
        key = next(k for k, name in sheets_cfg.items() if name == title)
        if len(rows) != end_row - first_row:
            raise ValueError("Range height does not match rows")
        grid_rows: list[dict[str, object]] = []
        for row in rows:
            if len(row) > end_col - first_col:
                raise ValueError("Row is wider than target range")
            if key == "assets" and row and str(row[0]).startswith("Table 2:"):
                asset_summary = True
            padded = list(row) + [""] * (end_col - first_col - len(row))
            grid_rows.append({"values": [cell_data(value, literal=(
                (key == "notes" and c + first_col == 0) or
                (key == "assets" and (c + first_col == 0 or (not asset_summary and c + first_col == 1) or
                                       (asset_summary and c + first_col == 11 and isinstance(value, str))))))
                for c, value in enumerate(padded)]})
        result.append({"updateCells": {"range": {
            "sheetId": sheet_ids[key], "startRowIndex": first_row, "endRowIndex": end_row,
            "startColumnIndex": first_col, "endColumnIndex": end_col},
            "rows": grid_rows, "fields": "userEnteredValue"}})
    return result


def apply_plan(spreadsheet_id: str, values: Mapping[str, Sequence[Sequence[object]]], *,
               access_token: str, config: Mapping[str, object], session: object = http_transport) -> None:
    """Verify target layout, snapshot prior cells, batch write and read back formulas.

    Only configured note/asset rectangles and statement detail cells are managed.
    Only note headings are bold; other formatting and validation are preserved.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]+", spreadsheet_id) or not access_token:
        raise ValueError("A Google spreadsheet ID and edit token are required")
    sheets_cfg = config.get("sheets")
    if not isinstance(sheets_cfg, Mapping):
        raise ValueError("Missing sheets config")
    sheet_ids = config.get("sheet_ids")
    if not isinstance(sheet_ids, Mapping):
        raise ValueError("Missing sheet_ids config")
    base = f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}"
    headers = {"Authorization": f"Bearer {access_token}"}
    meta_obj = request_json("GET", base, session=session, headers=headers, params={"fields": "sheets.properties"}, timeout=30)
    meta_json = meta_obj if isinstance(meta_obj, Mapping) else {}
    raw_sheets = meta_json.get("sheets", [])
    sheets_list = [s for s in raw_sheets if isinstance(s, Mapping)] if isinstance(raw_sheets, Sequence) else []
    sheets: dict[str, Mapping[str, object]] = {
        str(s["properties"]["title"]): s["properties"]
        for s in sheets_list if isinstance(s.get("properties"), Mapping) and "title" in s["properties"]
    }
    for key, title in sheets_cfg.items():
        if title not in sheets or sheets[title].get("sheetId") != sheet_ids[key]:
            raise ValueError(f"Sheet identity changed: {title}")
    values_copy: dict[str, list[list[object]]] = {key: [list(row) for row in rows] for key, rows in values.items()}
    # Read the configured managed blocks to remove stale generated rows on rerun.
    managed = {}
    for key, last_column in (("notes", "C"), ("assets", "I" if config.get("asset_layout") == "reviewed_statement" else "O")):
        title = str(sheets_cfg[key])
        sheet_props = sheets[title]
        grid_props = sheet_props.get("gridProperties")
        row_count = int(str(grid_props.get("rowCount", 500))) if isinstance(grid_props, Mapping) else 500
        limit_val = int(str(config.get("managed_row_limit", 500)))
        row_limit = min(row_count, limit_val)
        managed[key] = "'" + title.replace("'", "''") + f"'!A1:{last_column}{row_limit}"
    prior_obj = request_json("GET", base + "/values:batchGet", session=session, headers=headers,
                              params={"ranges": list(managed.values()), "valueRenderOption": "FORMULA"}, timeout=30)
    prior_json = prior_obj if isinstance(prior_obj, Mapping) else {}
    prior_ranges_raw = prior_json.get("valueRanges")
    prior_ranges = [r for r in prior_ranges_raw if isinstance(r, Mapping)] if isinstance(prior_ranges_raw, Sequence) else []
    if len(prior_ranges) != 2:
        raise ValueError("Could not inspect managed note and asset blocks")
    for key, entry in zip(managed, prior_ranges):
        title = str(sheets_cfg[key])
        address = next(a for a in values_copy if grid_address(a)[0] == title)
        rows = values_copy.pop(address)
        entry_values = entry.get("values")
        entry_rows = entry_values if isinstance(entry_values, list) else []
        if len(entry_rows) >= grid_address(managed[key])[3]:
            raise ValueError("Managed rows reach the configured scan limit; increase managed_row_limit")
        height = max(len(rows), len(entry_rows))
        if height > grid_address(managed[key])[3]:
            raise ValueError("Plan exceeds managed row limit or existing grid")
        width = grid_address(managed[key])[4]
        values_copy["'" + title.replace("'", "''") + f"'!A1:{chr(ord('A') + width - 1)}{height}"] = rows + [[""] * width for _ in range(height - len(rows))]
    checkbox_before = None
    if 'checkbox' in sheets_cfg:
        title = str(sheets_cfg['checkbox'])
        chk_props = sheets[title]
        chk_grid = chk_props.get('gridProperties')
        chk_row_cnt = int(str(chk_grid.get('rowCount', 1000))) if isinstance(chk_grid, Mapping) else 1000
        limit = min(chk_row_cnt, int(str(config.get('checkbox_row_limit', 1000))))
        address = "'" + title.replace("'", "''") + f"'!A1:K{limit}"
        checkbox_obj = request_json("GET", base + '/values:batchGet', session=session, headers=headers,
            params={'ranges': [address], 'valueRenderOption': 'FORMULA'}, timeout=30)
        checkbox_json = checkbox_obj if isinstance(checkbox_obj, Mapping) else {}
        entries_raw = checkbox_json.get('valueRanges')
        entries = [r for r in entries_raw if isinstance(r, Mapping)] if isinstance(entries_raw, Sequence) else []
        if len(entries) != 1:
            raise ValueError('Could not inspect checkbox inputs')
        checkbox_before = checkbox_json
        raw_rows = entries[0].get('values')
        rows = [r if isinstance(r, Sequence) else [] for r in raw_rows] if isinstance(raw_rows, Sequence) else []
        if len(rows) >= limit:
            raise ValueError('Checkbox reaches scan limit; increase checkbox_row_limit')
        if len(rows) < 7 or list(rows[6][:4]) != ['Year', 'Evidence', 'Section', 'Line item']:
            raise ValueError('Checkbox A7:D7 headers changed; review layout before apply')
        periods_val = config.get('periods')
        periods_seq = periods_val if isinstance(periods_val, Sequence) else []
        mappings_val = config.get('checkbox_mappings')
        mappings_seq = mappings_val if isinstance(mappings_val, Sequence) else []
        values_copy.update(checkbox_formula_updates(rows, sheet=title, periods=periods_seq,
            sheets=sheets_cfg, mappings=mappings_seq))
    requests_body = update_requests(values_copy, config)
    for request in requests_body:
        up_cells = request["updateCells"]
        if not isinstance(up_cells, Mapping):
            continue
        target = up_cells["range"]
        if not isinstance(target, Mapping):
            continue
        sheet_target = next(s for s in sheets.values() if s.get("sheetId") == target.get("sheetId"))
        target_grid = sheet_target.get("gridProperties")
        if isinstance(target_grid, Mapping):
            if (int(target["endRowIndex"]) > int(target_grid["rowCount"]) or
                    int(target["endColumnIndex"]) > int(target_grid["columnCount"])):
                raise ValueError("Plan exceeds the existing sheet grid")
    # Check native validation and formulas before writing, including destinations
    # whose displayed plain values can conceal validation constraints.
    native_obj = request_json("GET", base, session=session, headers=headers, params={"ranges": list(values_copy), "includeGridData": "true",
        "fields": "sheets(properties(title),data(startRow,startColumn,rowData(values(userEnteredValue,dataValidation,userEnteredFormat(textFormat),effectiveFormat(textFormat)))))"}, timeout=30)
    native_json = native_obj if isinstance(native_obj, Mapping) else {}
    native_sheets_raw = native_json.get("sheets", [])
    native_sheets = [s for s in native_sheets_raw if isinstance(s, Mapping)] if isinstance(native_sheets_raw, Sequence) else []
    if {s.get("properties", {}).get("title") for s in native_sheets} != set(sheets_cfg.values()):
        raise ValueError("Native cell metadata read is incomplete")
    for sheet in native_sheets:
        data_raw = sheet.get("data", [])
        data_list = [g for g in data_raw if isinstance(g, Mapping)] if isinstance(data_raw, Sequence) else []
        for grid in data_list:
            row_data_raw = grid.get("rowData", [])
            row_data = [r for r in row_data_raw if isinstance(r, Mapping)] if isinstance(row_data_raw, Sequence) else []
            for row in row_data:
                cell_vals = row.get("values", [])
                if isinstance(cell_vals, Sequence) and any(isinstance(c, Mapping) and c.get("dataValidation") for c in cell_vals):
                    raise ValueError("Managed target contains data validation; review it before apply")
    requests_body = changed_update_requests(requests_body, native_json, config)
    requests_body += note_bold_requests(values_copy, native_json, config)
    read_obj = request_json("GET", base + "/values:batchGet", session=session, headers=headers,
                             params={"ranges": list(values_copy), "valueRenderOption": "FORMULA"}, timeout=30)
    read_json = read_obj if isinstance(read_obj, Mapping) else {}
    old_raw = read_json.get("valueRanges")
    old = [r for r in old_raw if isinstance(r, Mapping)] if isinstance(old_raw, Sequence) else []
    if len(old) != len(values_copy):
        raise ValueError("Google Sheets did not return every target range")
    for address, entry in zip(values_copy, old):
        if ":" not in address and address.split("!")[-1].startswith(("C", "D")):
            entry_vals = entry.get("values")
            existing = (entry_vals or [[None]])[0][0] if isinstance(entry_vals, Sequence) and len(entry_vals) > 0 and isinstance(entry_vals[0], Sequence) and len(entry_vals[0]) > 0 else None
            note_prefix = "='" + str(sheets_cfg["notes"]).replace("'", "''") + "'!"
            title, row, col, _, _ = grid_address(address)
            notes_cfg = config.get("notes")
            notes_list = [n for n in notes_cfg if isinstance(n, Mapping)] if isinstance(notes_cfg, Sequence) else []
            is_note_target = any(sheets_cfg.get(n.get("statement")) == title and n.get("statement_row") == row + 1
                                 for n in notes_list)
            source_col = "B" if col == 2 else "C"
            managed_note_link = is_note_target and isinstance(existing, str) and re.fullmatch(
                re.escape(note_prefix + source_col) + r"[1-9]\d*", existing)
            rollforward = config.get("inventory_rollforward")
            rf_map = rollforward if isinstance(rollforward, Mapping) else {}
            purchases = next((n for n in notes_list if rf_map and n.get("number") == rf_map.get("purchases_note")), None)
            direct_cfg = config.get("direct_inputs")
            direct_list = [d for d in direct_cfg if isinstance(d, Mapping)] if isinstance(direct_cfg, Sequence) else []
            is_movement_target = any(d.get("inventory_changes") and sheets_cfg.get(d.get("statement")) == title
                                     and d.get("row") == row + 1 for d in direct_list)
            statement_col = "C" if col == 2 else "D"
            managed_movement_link = bool(purchases and is_movement_target and isinstance(existing, str) and re.fullmatch(
                re.escape(note_prefix + source_col) + r"[1-9]\d*" + re.escape(f"-{statement_col}{purchases.get('statement_row')}"), existing))
            if isinstance(existing, str) and existing.startswith("=") and existing != values_copy[address][0][0] and not (managed_note_link or managed_movement_link):
                raise ValueError(f"Unexpected existing formula in {address}")
    # The runner supplies an output path checked before any network call.
    snapshot = Path(str(config["backup_path"]))
    snapshot.write_text(json.dumps({**read_json, "native_cells": native_json,
        "checkbox_before": checkbox_before}, indent=2), encoding="utf-8")
    if requests_body:
        request_json("POST", base + ":batchUpdate", session=session, headers=headers,
                     json={"requests": requests_body}, timeout=30)
    verify_obj = request_json("GET", base + "/values:batchGet", session=session, headers=headers,
                               params={"ranges": list(values_copy), "valueRenderOption": "FORMULA"}, timeout=30)
    verify_json = verify_obj if isinstance(verify_obj, Mapping) else {}
    ret_raw = verify_json.get("valueRanges")
    returned = [r for r in ret_raw if isinstance(r, Mapping)] if isinstance(ret_raw, Sequence) else []
    if len(returned) != len(values_copy):
        raise ValueError("Google Sheets read-back is incomplete after update")
    for (address, expected), entry in zip(values_copy.items(), returned):
        actual = entry.get("values", [])
        if not isinstance(actual, list):
            actual = []
        for r, row in enumerate(expected):
            for c, cell in enumerate(row):
                got = actual[r][c] if r < len(actual) and isinstance(actual[r], list) and c < len(actual[r]) else ""
                if got != cell:
                    raise ValueError(f"Google Sheets read-back differs in {address}, row {r + 1}, column {c + 1}")
    eff_obj = request_json("GET", base + "/values:batchGet", session=session, headers=headers,
                                  params={"ranges": list(values_copy), "valueRenderOption": "UNFORMATTED_VALUE"}, timeout=30)
    effective_json = eff_obj if isinstance(eff_obj, Mapping) else {}
    eff_ranges_raw = effective_json.get("valueRanges")
    eff_ranges = [r for r in eff_ranges_raw if isinstance(r, Mapping)] if isinstance(eff_ranges_raw, Sequence) else []
    for entry in eff_ranges:
        entry_vals = entry.get("values", [])
        entry_rows = [r for r in entry_vals if isinstance(r, Sequence)] if isinstance(entry_vals, Sequence) else []
        for row in entry_rows:
            if any(isinstance(value, str) and value.startswith(("#REF!", "#VALUE!", "#ERROR!", "#DIV/0!", "#NAME?", "#N/A")) for value in row):
                raise ValueError("Google Sheets contains a formula error after update")
    fmt_obj = request_json("GET", base, session=session, headers=headers, params={"ranges": [a for a in values_copy if grid_address(a)[0] == sheets_cfg["notes"]],
        "includeGridData": "true", "fields": "sheets(properties(title),data(startRow,startColumn,rowData(values(userEnteredFormat(textFormat),effectiveFormat(textFormat)))))"}, timeout=30)
    formatting_json = fmt_obj if isinstance(fmt_obj, Mapping) else {}
    fmt_sheets_raw = formatting_json.get("sheets", [])
    fmt_sheets = [s for s in fmt_sheets_raw if isinstance(s, Mapping)] if isinstance(fmt_sheets_raw, Sequence) else []
    if not any(s.get("properties", {}).get("title") == sheets_cfg["notes"] for s in fmt_sheets):
        raise ValueError("Google Sheets note formatting read-back is incomplete")
    if note_bold_requests(values_copy, formatting_json, config):
        raise ValueError("Google Sheets note bold formatting read-back differs")


def note_bold_requests(values: Mapping[str, Sequence[Sequence[object]]], native: Mapping[str, object],
                       config: Mapping[str, object]) -> list[dict[str, object]]:
    """Change only bold in managed notes A:C, using the new heading positions."""
    sheets_cfg = config["sheets"]
    if not isinstance(sheets_cfg, Mapping):
        return []
    sheet_ids = config["sheet_ids"]
    if not isinstance(sheet_ids, Mapping):
        return []
    title = sheets_cfg["notes"]
    existing: dict[tuple[int, int], bool] = {}
    native_sheets_raw = native.get("sheets", [])
    native_sheets = [s for s in native_sheets_raw if isinstance(s, Mapping)] if isinstance(native_sheets_raw, Sequence) else []
    for sheet in native_sheets:
        props = sheet.get("properties")
        if not isinstance(props, Mapping) or props.get("title") != title:
            continue
        data_raw = sheet.get("data", [])
        data_list = [g for g in data_raw if isinstance(g, Mapping)] if isinstance(data_raw, Sequence) else []
        for grid in data_list:
            start_row = int(grid.get("startRow", 0))
            start_col = int(grid.get("startColumn", 0))
            row_data_raw = grid.get("rowData", [])
            row_data = [r for r in row_data_raw if isinstance(r, Mapping)] if isinstance(row_data_raw, Sequence) else []
            for r, row in enumerate(row_data, start_row):
                cell_vals_raw = row.get("values", [])
                cell_vals = [c for c in cell_vals_raw if isinstance(c, Mapping)] if isinstance(cell_vals_raw, Sequence) else []
                for c, cell in enumerate(cell_vals, start_col):
                    eff_fmt = cell.get("effectiveFormat")
                    eff_txt = eff_fmt.get("textFormat") if isinstance(eff_fmt, Mapping) else {}
                    usr_fmt = cell.get("userEnteredFormat")
                    usr_txt = usr_fmt.get("textFormat") if isinstance(usr_fmt, Mapping) else {}
                    bold_val = eff_txt.get("bold") if isinstance(eff_txt, Mapping) and "bold" in eff_txt else (
                        usr_txt.get("bold", False) if isinstance(usr_txt, Mapping) else False
                    )
                    existing[r, c] = bool(bold_val)
    changes: list[dict[str, object]] = []
    for address, rows in values.items():
        name, sr, sc, _, _ = grid_address(address)
        if name != title:
            continue
        for offset, row in enumerate(rows):
            bold = bool(row and isinstance(row[0], str) and re.match(r"^Note \d+:", row[0]))
            for c in range(sc, sc + 3):
                r = sr + offset
                if existing.get((r, c), False) != bold:
                    changes.append({"updateCells": {"range": {"sheetId": sheet_ids["notes"],
                        "startRowIndex": r, "endRowIndex": r + 1, "startColumnIndex": c, "endColumnIndex": c + 1},
                        "rows": [{"values": [{"userEnteredFormat": {"textFormat": {"bold": bold}}}]}],
                        "fields": "userEnteredFormat.textFormat.bold"}})
    return changes


def changed_update_requests(requests_body: list[dict[str, object]], native: Mapping[str, object],
                            config: Mapping[str, object]) -> list[dict[str, object]]:
    """Keep only changed entered values, batching adjacent changes within a row."""
    sheets_cfg = config["sheets"]
    if not isinstance(sheets_cfg, Mapping):
        return []
    sheet_ids = config["sheet_ids"]
    if not isinstance(sheet_ids, Mapping):
        return []
    existing: dict[tuple[object, int, int], object] = {}
    native_sheets_raw = native.get("sheets", [])
    native_sheets = [s for s in native_sheets_raw if isinstance(s, Mapping)] if isinstance(native_sheets_raw, Sequence) else []
    for sheet in native_sheets:
        props = sheet.get("properties")
        if not isinstance(props, Mapping):
            continue
        title = props.get("title")
        key = next(k for k, name in sheets_cfg.items() if name == title)
        sheet_id = sheet_ids[key]
        data_raw = sheet.get("data", [])
        data_list = [g for g in data_raw if isinstance(g, Mapping)] if isinstance(data_raw, Sequence) else []
        for grid in data_list:
            start_row = int(grid.get("startRow", 0))
            start_col = int(grid.get("startColumn", 0))
            row_data_raw = grid.get("rowData", [])
            row_data = [r for r in row_data_raw if isinstance(r, Mapping)] if isinstance(row_data_raw, Sequence) else []
            for r, row in enumerate(row_data, start_row):
                cell_vals_raw = row.get("values", [])
                cell_vals = [c for c in cell_vals_raw if isinstance(c, Mapping)] if isinstance(cell_vals_raw, Sequence) else []
                for c, cell in enumerate(cell_vals, start_col):
                    existing[sheet_id, r, c] = cell.get("userEnteredValue", {})
    changed: list[dict[str, object]] = []
    for request in requests_body:
        update = request.get("updateCells")
        if not isinstance(update, Mapping):
            continue
        target = update.get("range")
        if not isinstance(target, Mapping):
            continue
        rows_val = update.get("rows", [])
        rows_list = [r for r in rows_val if isinstance(r, Mapping)] if isinstance(rows_val, Sequence) else []
        for offset, row in enumerate(rows_list):
            r = int(target["startRowIndex"]) + offset
            run: list[object] = []
            start = int(target["startColumnIndex"])
            def flush() -> None:
                if run:
                    changed.append({"updateCells": {"range": {
                        "sheetId": target["sheetId"], "startRowIndex": r, "endRowIndex": r + 1,
                        "startColumnIndex": start, "endColumnIndex": start + len(run)},
                        "rows": [{"values": list(run)}], "fields": "userEnteredValue"}})
                    run.clear()
            row_vals = row.get("values", [])
            cells_list = [c for c in row_vals if isinstance(c, Mapping)] if isinstance(row_vals, Sequence) else []
            for col_offset, cell in enumerate(cells_list):
                c = int(target["startColumnIndex"]) + col_offset
                if cell.get("userEnteredValue", {}) == existing.get((target["sheetId"], r, c), {}):
                    flush()
                else:
                    if not run:
                        start = c
                    run.append(cell)
            flush()
    return changed
    """Keep only changed entered values, batching adjacent changes within a row."""
    existing = {}
    for sheet in native["sheets"]:
        title = sheet["properties"]["title"]
        key = next(k for k, name in config["sheets"].items() if name == title)
        sheet_id = config["sheet_ids"][key]
        for grid in sheet.get("data", []):
            for r, row in enumerate(grid.get("rowData", []), grid.get("startRow", 0)):
                for c, cell in enumerate(row.get("values", []), grid.get("startColumn", 0)):
                    existing[sheet_id, r, c] = cell.get("userEnteredValue", {})
    changed = []
    for request in requests_body:
        update = request["updateCells"]
        target = update["range"]
        for offset, row in enumerate(update["rows"]):
            r = target["startRowIndex"] + offset
            run = []
            start = target["startColumnIndex"]
            def flush() -> None:
                if run:
                    changed.append({"updateCells": {"range": {
                        "sheetId": target["sheetId"], "startRowIndex": r, "endRowIndex": r + 1,
                        "startColumnIndex": start, "endColumnIndex": start + len(run)},
                        "rows": [{"values": list(run)}], "fields": "userEnteredValue"}})
                    run.clear()
            for col_offset, cell in enumerate(row["values"]):
                c = target["startColumnIndex"] + col_offset
                if cell.get("userEnteredValue", {}) == existing.get((target["sheetId"], r, c), {}):
                    flush()
                else:
                    if not run:
                        start = c
                    run.append(cell)
            flush()
    return changed
