"""Stable count-page references survive Mapping reorder and product row moves."""

from unittest.mock import MagicMock

import pytest

from workflows.neoseal_stock_count import (
    audit_stockcount_formulas, verify_stockcount_formulas, apply_stable_sync_plan,
)
from workflows.neoseal_stock_count.stable_sync import build_stable_sync_plan


FLAT = {
    1: {1: "item_id", 2: "sku", 5: "available_quantity", 12: "packing"},
    2: {1: "101", 2: "SKU-A", 5: "3", 12: "24"},
    3: {1: "102", 2: "SKU-B", 5: "4", 12: "24"},
}
MAPPING = {
    1: {1: "sku", 2: "cell", 3: "name", 4: "item_id", 5: "stock_on_hand_cell", 6: "line_id"},
    2: {1: "SKU-A", 2: "C3", 3: "Product", 4: "101", 6: "SC-1"},
    3: {1: "SKU-B", 2: "C3", 3: "Product", 4: "102", 6: "SC-1"},
}
COUNT = {
    1: {1: "PRODUCT", 2: "PACK", 3: "QTY", 6: "PRODUCT", 7: "PACK", 8: "QTY",
        10: "left_line_id", 11: "right_line_id"},
    3: {1: "Product", 2: "24", 3: "7", 10: "SC-1"},
}


def test_reordered_mapping_keeps_sku_formulas_and_aggregates_duplicates():
    first = build_stable_sync_plan(FLAT, MAPPING, COUNT)
    reordered = {1: MAPPING[1], 2: MAPPING[3], 3: MAPPING[2]}
    second = build_stable_sync_plan(FLAT, reordered, COUNT)
    assert '"SKU-A"' in first.formulas["C3"]
    assert '"SKU-B"' in first.formulas["C3"]
    assert set(first.formulas) == set(second.formulas)
    assert first.new_line_ids == 0
    assert not first.changes


def test_moved_product_row_updates_mapping_address_by_line_id():
    moved = {1: COUNT[1], 5: COUNT[3]}
    plan = build_stable_sync_plan(FLAT, MAPPING, moved)
    assert {"B5", "C5"} == set(plan.formulas)
    assert {(c.sheet, c.row, c.column, c.content) for c in plan.changes} == {
        ("Mapping", 2, 2, "C5"), ("Mapping", 3, 2, "C5")
    }


def test_new_flat_item_is_reported_without_automatic_placement():
    extra = dict(FLAT)
    extra[4] = {1: "103", 2: "SKU-C", 5: "8", 12: "12"}
    plan = build_stable_sync_plan(extra, MAPPING, COUNT)
    assert plan.unplaced_skus == ("SKU-C",)


def sheet_client():
    sheet = MagicMock()
    sheet.request.return_value = {"range_details": []}
    return sheet


def test_formula_audit_batches_and_clears_probe():
    sheet = sheet_client()
    cells = [f"C{n}" for n in range(1, 14)]
    sheet.set_cell.side_effect = [{"cell": {"cell_value": "♦".join(["=0"] * 12)}}, {"cell": {"cell_value": "=1"}}]
    assert audit_stockcount_formulas(sheet, "book", cells, delay_seconds=0) == dict(zip(cells, ["=0"] * 12 + ["=1"]))
    sheet.clear_range.assert_called_once_with("book", "StockCount", 1, 12, 1, 12)


@pytest.mark.parametrize("response", [{}, {"range_details": [{}]}, {"range_details": "invalid"}])
def test_formula_probe_must_be_confirmed_empty(response):
    sheet = sheet_client()
    sheet.request.return_value = response
    with pytest.raises(ValueError):
        audit_stockcount_formulas(sheet, "book", ["C3"], delay_seconds=0)
    sheet.set_cell.assert_not_called()
    sheet.clear_range.assert_not_called()


@pytest.mark.parametrize("cells", [["L1"], ["C0"], ["C1", "C1"], ['C1);HYPERLINK("x")'], ["c3"]])
def test_formula_addresses_validated_before_probe(cells):
    sheet = sheet_client()
    with pytest.raises(ValueError):
        audit_stockcount_formulas(sheet, "book", cells, delay_seconds=0)
    sheet.request.assert_not_called()


@pytest.mark.parametrize("failure", [RuntimeError("lost response"), {"cell": {"cell_value": "one♦two"}}, {}])
def test_formula_audit_failure_cleans_probe(failure):
    sheet = sheet_client()
    sheet.set_cell.side_effect = [failure]
    with pytest.raises((ValueError, RuntimeError)):
        audit_stockcount_formulas(sheet, "book", ["C3"], delay_seconds=0)
    sheet.clear_range.assert_called_once()


def test_verify_formulas_reports_mismatch():
    sheet = sheet_client()
    sheet.set_cell.return_value = {"cell": {"cell_value": "=wrong"}}
    with pytest.raises(ValueError, match="Stored formulas differ"):
        verify_stockcount_formulas(sheet, "book", {"C3": "=right"}, delay_seconds=0)


def test_apply_stable_formulas_only_changes_differences_and_verifies():
    sheet = sheet_client()
    plan = build_stable_sync_plan(FLAT, MAPPING, COUNT)
    expected = list(plan.formulas.values())
    sheet.set_cell.side_effect = [
        {"cell": {"cell_value": "♦".join(["=old", expected[1]])}},
        {"cell": {}}, {"cell": {"cell_value": "♦".join(expected)}},
    ]
    progress = []
    assert apply_stable_sync_plan(sheet, "book", plan, delay_seconds=0, progress=progress.append) == 1
    assert progress == ["Helper/address writes: 0; formula writes: 1"]
    assert sheet.set_cell.call_count == 3


def test_formula_verification_cli_requires_probe_authorization():
    from apps.sync_neoseal_stockcount import main
    with pytest.raises(SystemExit) as exc:
        main(["--verify-only"])
    assert exc.value.code == 2
