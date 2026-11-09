"""Higher-level helper functions for Zoho Analytics and Inventory bin operations."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Protocol

logger = logging.getLogger("helpers.catalog.bins")

DEFAULT_WORKSPACE_ID = ""
DEFAULT_TABLE_NAME = "Item Stock by Bin"


class AnalyticsQueriesResource(Protocol):
    def execute(self, workspace_id: str, sql_query: str) -> object: ...


class AnalyticsBinClient(Protocol):
    queries: AnalyticsQueriesResource


def _escape_sql_literal(value: object) -> str:
    """Escape single quotes for SQL string literals."""
    return str(value or "").replace("'", "''")


def _to_clean_list(val: object) -> list[str]:
    """Convert a single value or sequence into a list of non-empty strings."""
    if val is None:
        return []
    if isinstance(val, (str, int, float)):
        cleaned = str(val).strip()
        return [cleaned] if cleaned else []
    result = []
    if isinstance(val, (list, tuple, set)):
        for item in val:
            cleaned = str(item).strip()
            if cleaned:
                result.append(cleaned)
    return result


def get_bins_for_items(
    analytics_client: AnalyticsBinClient,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    item_ids: Sequence[str | int] | str | int | None = None,
    skus: Sequence[str] | str | None = None,
    item_names: Sequence[str] | str | None = None,
    available_only: bool = True,
    table_name: str = DEFAULT_TABLE_NAME,
    order_by: str | None = 'ORDER BY "Item Name" ASC',
) -> list[dict[str, object]]:
    """Query item stock across warehouse bins using Zoho Analytics.

    Parameters:
        analytics_client: Authenticated ZohoAnalyticsAPI client instance.
        workspace_id: Zoho Analytics workspace ID containing the bin view.
        item_ids: Optional item ID or list of item IDs to filter.
        skus: Optional SKU or list of SKUs to filter.
        item_names: Optional item name or list of item names to filter.
        available_only: When True (default), filters for Available > 0.
        table_name: Query table name (defaults to 'Item Stock by Bin').
        order_by: Optional SQL ORDER BY clause.

    Returns:
        List of dicts representing each (item, bin) stock balance:
            - Product ID
            - Item Name
            - SKU
            - Bin Location ID
            - Bin Name
            - Warehouse ID
            - In
            - Out
            - Available
    """
    conditions: list[str] = []

    if available_only:
        conditions.append('"Available" > 0')

    id_list = _to_clean_list(item_ids)
    if id_list:
        clause = ", ".join(f"'{_escape_sql_literal(i)}'" for i in id_list)
        conditions.append(f'"Product ID" IN ({clause})')

    sku_list = _to_clean_list(skus)
    if sku_list:
        clause = ", ".join(f"'{_escape_sql_literal(s)}'" for s in sku_list)
        conditions.append(f'"SKU" IN ({clause})')

    name_list = _to_clean_list(item_names)
    if name_list:
        clause = ", ".join(f"'{_escape_sql_literal(n)}'" for n in name_list)
        conditions.append(f'"Item Name" IN ({clause})')

    where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    order_clause = f" {order_by.strip()}" if order_by and order_by.strip() else ""
    sql = f'SELECT * FROM "{table_name}"{where_clause}{order_clause}'

    if not workspace_id or not str(workspace_id).strip():
        raise ValueError("workspace_id is required to query bin stock.")

    logger.debug("Executing get_bins_for_items SQL: %s", sql)

    try:
        results = analytics_client.queries.execute(
            workspace_id=workspace_id,
            sql_query=sql,
        )
        return results if isinstance(results, list) else []
    except Exception as exc:
        logger.error("Failed to query bin stock for items: %s", exc)
        raise


def get_bins_by_item_map(
    analytics_client: AnalyticsBinClient,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    key_field: str = "SKU",
    item_ids: Sequence[str | int] | str | int | None = None,
    skus: Sequence[str] | str | None = None,
    available_only: bool = True,
    table_name: str = DEFAULT_TABLE_NAME,
) -> dict[str, list[dict[str, object]]]:
    """Fetch bin stock grouped by item key (e.g. SKU, Product ID, or Item Name).

    Returns a mapping of {key_value: [bin_record_1, bin_record_2, ...]}.
    """
    records = get_bins_for_items(
        analytics_client=analytics_client,
        workspace_id=workspace_id,
        item_ids=item_ids,
        skus=skus,
        available_only=available_only,
        table_name=table_name,
    )
    grouped: dict[str, list[dict[str, object]]] = {}
    for record in records:
        key_val = record.get(key_field)
        if key_val is not None:
            clean_key = str(key_val).strip()
            if clean_key:
                grouped.setdefault(clean_key, []).append(record)
    return grouped


__all__ = [
    "DEFAULT_TABLE_NAME",
    "DEFAULT_WORKSPACE_ID",
    "get_bins_by_item_map",
    "get_bins_for_items",
]
