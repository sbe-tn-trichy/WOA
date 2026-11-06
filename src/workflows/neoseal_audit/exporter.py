"""Compatibility exports retaining the historical Neoseal output filenames."""
from pathlib import Path

from zoho.inventory import ZohoInventoryAPI
from workflows.item_catalog import FIELDS, ItemExportRow, export_row, write_export_rows
from workflows.item_catalog import export_inventory_items as _export_inventory_items


def export_inventory_items(
    inventory_client: ZohoInventoryAPI,
    purchase_account_id: str,
    *,
    status: str = "active",
    output_path: Path | str = Path("output/neoseal_items.csv"),
    missing_output_path: Path | str = Path("output/neoseal_items_missing_alias.csv"),
) -> tuple[list[ItemExportRow], list[ItemExportRow]]:
    """Delegate to the generic catalog export with legacy destination defaults."""
    return _export_inventory_items(inventory_client, purchase_account_id, status=status,
        output_path=output_path, missing_output_path=missing_output_path)


__all__ = ["FIELDS", "export_inventory_items", "export_row", "write_export_rows"]
