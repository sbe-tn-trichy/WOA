"""Vendor-independent exports retain account scope and legacy entry points."""
import csv
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from apps.inventory import export_items
from apps.neoseal_items import export_neoseal_items
from workflows.item_catalog import FIELDS, export_inventory_items
from workflows.neoseal_audit.exporter import export_inventory_items as legacy_export


def client():
    inventory = MagicMock()
    inventory.items.list_by_purchase_account.return_value = [
        dict(item_id="1", name="Cable", sku="CAB-1", alias_name=" Vendor cable ", manufacturer="Other brand", purchase_account_id="purchase"),
        dict(item_id="2", name="Switch", sku="SW-2", alias_name="  ", manufacturer="Another brand", purchase_account_id="purchase"),
    ]
    return inventory


@pytest.mark.parametrize("status", ["active", "inactive", "all"])
def test_generic_cli_exports_multiple_brands_and_forwards_status(tmp_path, monkeypatch, status):
    inventory = client()
    monkeypatch.setattr(export_items, "get_inventory_client", lambda: inventory)
    output, missing = tmp_path / "items.csv", tmp_path / "missing.csv"
    assert export_items.main(["--purchase-account-id", "purchase", "--status", status,
        "--output", str(output), "--missing-output", str(missing)]) == 0
    inventory.items.list_by_purchase_account.assert_called_once_with("purchase", status=status)
    with output.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames) == FIELDS
        rows = list(reader)
    assert [row["manufacturer"] for row in rows] == ["Other brand", "Another brand"]
    assert rows[0]["alias_name"] == "Vendor cable"
    with missing.open(encoding="utf-8", newline="") as handle:
        assert [row["item_id"] for row in csv.DictReader(handle)] == ["2"]
    inventory.items.update.assert_not_called()


def test_generic_and_legacy_defaults(tmp_path, monkeypatch):
    generic = export_items.build_parser().parse_args(["--purchase-account-id", "purchase"])
    legacy = export_neoseal_items.build_parser().parse_args(["--purchase-account-id", "purchase"])
    assert generic.output == Path("output/items.csv")
    assert generic.missing_output == Path("output/items_missing_alias.csv")
    assert legacy.output == Path("output/neoseal_items.csv")
    assert legacy.missing_output == Path("output/neoseal_items_missing_alias.csv")
    assert generic.status == legacy.status == "active"
    monkeypatch.chdir(tmp_path)
    legacy_export(client(), "purchase")
    assert Path("output/neoseal_items.csv").exists()
    assert not Path("output/items.csv").exists()


def test_library_generic_default_destinations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rows, missing = export_inventory_items(client(), "purchase")
    assert len(rows) == 2 and len(missing) == 1
    assert Path("output/items.csv").exists()
    assert Path("output/items_missing_alias.csv").exists()


@pytest.mark.parametrize("problem", ["blank_account", "bad_status", "same_output", "wrong_account", "missing_account", "api_error"])
def test_invalid_export_never_writes_files(tmp_path, problem):
    inventory = client()
    account, status = "purchase", "active"
    output, missing = tmp_path / "items.csv", tmp_path / "missing.csv"
    if problem == "blank_account": account = " "
    elif problem == "bad_status": status = "unknown"
    elif problem == "same_output": missing = output
    elif problem == "wrong_account": inventory.items.list_by_purchase_account.return_value[1]["purchase_account_id"] = "other"
    elif problem == "missing_account": del inventory.items.list_by_purchase_account.return_value[0]["purchase_account_id"]
    elif problem == "api_error": inventory.items.list_by_purchase_account.side_effect = RuntimeError("API unavailable")
    with pytest.raises((ValueError, RuntimeError)):
        export_inventory_items(inventory, account, status=status, output_path=output, missing_output_path=missing)
    assert not output.exists() and not missing.exists()


def test_generic_cli_rejects_invalid_status():
    with pytest.raises(SystemExit) as exc:
        export_items.build_parser().parse_args(["--purchase-account-id", "purchase", "--status", "unknown"])
    assert exc.value.code == 2
