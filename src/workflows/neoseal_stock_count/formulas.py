"""Stored StockCount formula inspection and stable-plan execution.

Formula inspection temporarily writes StockCount L1; callers must explicitly
request this live operation, even when they only want verification.
"""
from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence

from zoho.sheet import ZohoSheetAPI
from .processor import format_cell_address, parse_cell_address
from .stable_sync import StableSyncPlan


def audit_stockcount_formulas(
    sheet: ZohoSheetAPI, workbook: str, cells: Sequence[str], *, delay_seconds: float = 1.25,
) -> dict[str, str]:
    """Read expressions using a checked empty probe, removing the probe on failure."""
    _validate_delay(delay_seconds)
    if len(set(cells)) != len(cells):
        raise ValueError("Formula addresses must be unique")
    for cell in cells:
        row, column = parse_cell_address(cell)
        if cell != format_cell_address(row, column) or cell == "L1":
            raise ValueError(f"Invalid or reserved formula address: {cell}")
    if not cells:
        return {}
    probe = sheet.request("GET", workbook, params={
        "method": "worksheet.content.get", "worksheet_name": "StockCount", "range": "L1",
    })
    if "range_details" not in probe or not isinstance(probe["range_details"], list):
        raise ValueError("Cannot confirm StockCount L1 is empty")
    if probe["range_details"]:
        raise ValueError("StockCount L1 must be empty for formula introspection")
    found: dict[str, str] = {}
    try:
        for start in range(0, len(cells), 12):
            batch = cells[start:start + 12]
            expression = "=" + '&"♦"&'.join(f'IFERROR(FORMULA({cell});"")' for cell in batch)
            response = sheet.set_cell(workbook, "StockCount", 1, 12, expression)
            res = response if isinstance(response, dict) else {}
            cell_raw = res.get("cell")
            cell_data = cell_raw if isinstance(cell_raw, dict) else {}
            value = cell_data.get("cell_value")
            if not isinstance(value, str):
                raise ValueError(f"Formula audit missing text at {batch[0]}")
            parts = value.split("♦")
            if len(parts) != len(batch):
                raise ValueError(f"Formula audit response count differs at {batch[0]}")
            found.update(zip(batch, parts))
            time.sleep(delay_seconds)
    finally:
        sheet.clear_range(workbook, "StockCount", 1, 12, 1, 12)
    return found


def verify_stockcount_formulas(
    sheet: ZohoSheetAPI, workbook: str, expected: Mapping[str, str], *, delay_seconds: float = 1.25,
) -> int:
    """Verify all expected expressions, using the temporary live L1 probe."""
    actual = audit_stockcount_formulas(sheet, workbook, list(expected), delay_seconds=delay_seconds)
    bad = [cell for cell, formula in expected.items() if actual[cell] != formula]
    if bad:
        raise ValueError(f"Stored formulas differ: {bad[:10]}")
    return len(expected)


def apply_stable_sync_plan(
    sheet: ZohoSheetAPI, workbook: str, plan: StableSyncPlan, *, delay_seconds: float = 1.25,
    progress: Callable[[str], None] | None = None,
) -> int:
    """Apply changed helpers/expressions and verify every stored formula afterward."""
    _validate_delay(delay_seconds)
    before = audit_stockcount_formulas(sheet, workbook, list(plan.formulas), delay_seconds=delay_seconds)
    formula_changes = {cell: value for cell, value in plan.formulas.items() if before[cell] != value}
    if progress:
        progress(f"Helper/address writes: {len(plan.changes)}; formula writes: {len(formula_changes)}")
    for index, change in enumerate(plan.changes, 1):
        sheet.set_cell(workbook, change.sheet, change.row, change.column, change.content)
        if progress and index % 25 == 0:
            progress(f"Applied {index}/{len(plan.changes)} helper/address writes")
        time.sleep(delay_seconds)
    for index, (address, formula) in enumerate(formula_changes.items(), 1):
        row, column = parse_cell_address(address)
        sheet.set_cell(workbook, "StockCount", row, column, formula)
        if progress and index % 25 == 0:
            progress(f"Applied {index}/{len(formula_changes)} formula writes")
        time.sleep(delay_seconds)
    verify_stockcount_formulas(sheet, workbook, plan.formulas, delay_seconds=delay_seconds)
    return len(formula_changes)


def _validate_delay(value: float) -> None:
    if not math.isfinite(value) or value < 0:
        raise ValueError("Request delay must be finite and nonnegative")
