"""Export Inventory items for a purchase account and flag missing vendor aliases."""

from __future__ import annotations

import csv
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import TypedDict

from zoho.inventory import ZohoInventoryAPI


class ItemExportRow(TypedDict):
    item_id: str
    name: str
    sku: str
    alias_name: str
    has_alias_name: str
    manufacturer: str
    purchase_account_id: str


FIELDS = (
    "item_id",
    "name",
    "sku",
    "alias_name",
    "has_alias_name",
    "manufacturer",
    "purchase_account_id",
)


def export_row(item: Mapping[str, object]) -> ItemExportRow:
    """Return the stable CSV representation of one Inventory item."""
    alias = str(item.get("alias_name") or "").strip()
    return {
        "item_id": str(item.get("item_id") or "").strip(),
        "name": str(item.get("name") or "").strip(),
        "sku": str(item.get("sku") or "").strip(),
        "alias_name": alias,
        "has_alias_name": "true" if alias else "false",
        "manufacturer": str(item.get("manufacturer") or "").strip(),
        "purchase_account_id": str(item.get("purchase_account_id") or "").strip(),
    }


def write_export_rows(path: Path | str, rows: Sequence[Mapping[str, object]]) -> None:
    """Write export rows to CSV."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def export_inventory_items(
    inventory_client: ZohoInventoryAPI,
    purchase_account_id: str,
    *,
    status: str = "active",
    output_path: Path | str = Path("output/items.csv"),
    missing_output_path: Path | str = Path("output/items_missing_alias.csv"),
) -> tuple[list[ItemExportRow], list[ItemExportRow]]:
    """Fetch items by purchase account, export CSV, and write missing aliases."""
    if not purchase_account_id.strip():
        raise ValueError("purchase_account_id must be nonempty")
    if status not in {"active", "inactive", "all"}:
        raise ValueError("status must be active, inactive, or all")
    if Path(output_path).resolve() == Path(missing_output_path).resolve():
        raise ValueError("Export and missing-alias outputs must use different paths")
    items = inventory_client.items.list_by_purchase_account(
        purchase_account_id,
        status=status,
    )
    for item in items:
        if str(item.get("purchase_account_id") or "").strip() != purchase_account_id.strip():
            raise ValueError(f"Inventory returned item {item.get('item_id')} outside purchase account {purchase_account_id}")
    rows = [export_row(item) for item in items]
    missing = [row for row in rows if row["has_alias_name"] == "false"]
    write_export_rows(output_path, rows)
    write_export_rows(missing_output_path, missing)
    return rows, missing
