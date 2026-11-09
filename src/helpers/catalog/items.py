"""Higher-level helper functions for Zoho Inventory item operations."""

from __future__ import annotations

import logging
from collections.abc import Mapping

from zoho.core_sdk.validation import require_records
from zoho.inventory import ZohoInventoryAPI
from ..operations.records import unique_record

logger = logging.getLogger("helpers.catalog.items")


def _get_items_iterable(items_resource: object, params: dict[str, object]) -> object:
    """Safely obtain iterable over items supporting list_all, list_iter, or list."""
    if hasattr(items_resource, "list_all") and callable(getattr(items_resource, "list_all")):
        res = getattr(items_resource, "list_all")(params=params, resource_key="items")
        if isinstance(res, list):
            return res
    if hasattr(items_resource, "list_iter") and callable(getattr(items_resource, "list_iter")):
        res = getattr(items_resource, "list_iter")(params=params, resource_key="items")
        if isinstance(res, (list, tuple)) or hasattr(res, "__iter__"):
            return res
    if hasattr(items_resource, "list") and callable(getattr(items_resource, "list")):
        res = getattr(items_resource, "list")(params=params)
        if isinstance(res, dict):
            return res.get("items", [])
        if isinstance(res, list):
            return res
    return []


def fetch_items_lookup(
    inventory_client: ZohoInventoryAPI,
    key_field: str = "name",
    status: str = "active",
    purchase_account_id: str | None = None,
) -> dict[str, dict[str, object]]:
    """Fetch all items from Zoho Inventory and index them by `key_field`.

    Supports `name`, `sku`, `item_id`, `item_name`, etc. Optional `purchase_account_id`
    scopes the query to a specific purchase account.
    """
    params: dict[str, object] = {"filter_by": f"Status.{status.title()}"}
    if purchase_account_id:
        params["purchase_account_id"] = str(purchase_account_id).strip()

    lookup: dict[str, dict[str, object]] = {}

    try:
        items = _get_items_iterable(inventory_client.items, params)
        if isinstance(items, (list, tuple)):
            for item in items:
                if not isinstance(item, Mapping):
                    continue
                key_val = item.get(key_field)
                if key_val is None and key_field == "name":
                    key_val = item.get("item_name")
                elif key_val is None and key_field == "item_name":
                    key_val = item.get("name")

                if key_val is not None:
                    clean_key = str(key_val).strip()
                    if clean_key:
                        lookup[clean_key] = dict(item)
    except Exception as exc:
        logger.error(f"Failed to fetch and index items by key '{key_field}': {exc}")
        raise

    return lookup


def fetch_items_by_purchase_account(
    inventory_client: ZohoInventoryAPI,
    purchase_account_id: str,
    key_field: str = "sku",
    status: str = "all",
) -> dict[str, dict[str, object]]:
    """Fetch items scoped to a specific purchase account and index them by `key_field`."""
    account_id = str(purchase_account_id or "").strip()
    if not account_id:
        raise ValueError("purchase_account_id is required.")

    return fetch_items_lookup(
        inventory_client,
        key_field=key_field,
        status=status,
        purchase_account_id=account_id,
    )


def find_item_by_sku_or_name(
    inventory_client: ZohoInventoryAPI,
    query: str,
    purchase_account_id: str | None = None,
) -> dict[str, object] | None:
    """Search for an item by matching SKU or name, optionally scoped by purchase_account_id."""
    cleaned = str(query or "").strip()
    if not cleaned:
        return None

    target = cleaned.lower()
    params: dict[str, object] = {"search_text": cleaned}
    if purchase_account_id:
        params["purchase_account_id"] = str(purchase_account_id).strip()

    try:
        res = inventory_client.items.list(params=params)
        items = res.get("items", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])
        for item in items:
            if not isinstance(item, Mapping):
                continue
            sku = str(item.get("sku") or "").strip().lower()
            name = str(item.get("item_name") or item.get("name") or "").strip().lower()
            if target in (sku, name):
                return dict(item)

        for item in items:
            if not isinstance(item, Mapping):
                continue
            name = str(item.get("item_name") or item.get("name") or "").strip().lower()
            if target in name:
                return dict(item)
    except Exception as exc:
        logger.warning(f"Error searching items for '{cleaned}': {exc}")

    return None


def find_item_by_exact_sku(
    inventory_client: ZohoInventoryAPI,
    sku: str,
    purchase_account_id: str,
) -> dict[str, object] | None:
    """Find an exact Inventory SKU in one purchase account, preferring active items."""
    account_id = str(purchase_account_id or "").strip()
    if not account_id:
        raise ValueError("purchase_account_id is required for item lookup.")
    candidate = str(sku or "").strip()
    if not candidate:
        return None
    response = inventory_client.items.list(
        params={"sku": candidate, "purchase_account_id": account_id}
    )
    items = response.get("items", []) if isinstance(response, dict) else []
    matches = [
        dict(item) for item in items
        if isinstance(item, Mapping) and str(item.get("sku") or "").upper() == candidate.upper()
    ]
    matches.sort(key=lambda item: item.get("status") != "active")
    return matches[0] if matches else None


def _inventory_candidates(
    inventory_client: ZohoInventoryAPI,
    params: dict[str, object],
    purchase_account_id: str | None,
) -> list[dict[str, object]]:
    if purchase_account_id is not None:
        account_id = purchase_account_id.strip()
        if not account_id:
            raise ValueError("purchase_account_id cannot be blank")
        params["purchase_account_id"] = account_id
    rows = require_records(
        inventory_client.items.list_all(params=params, resource_key="items"), "Inventory item search",
    )
    return [
        row for row in rows
        if purchase_account_id is None or row.get("purchase_account_id") is None
        or str(row["purchase_account_id"]) == params["purchase_account_id"]
    ]


def resolve_inventory_sku(
    inventory_client: ZohoInventoryAPI,
    sku: str,
    *,
    purchase_account_id: str | None = None,
) -> dict[str, object] | None:
    """Resolve one exact SKU, preferring active Inventory items."""
    target = sku.strip()
    if not target:
        raise ValueError("Inventory SKU is required")
    rows = _inventory_candidates(inventory_client, {"sku": target}, purchase_account_id)
    matches = [
        row for row in rows
        if str(row.get("sku") or "").strip().casefold() == target.casefold()
    ]
    active = [row for row in matches if row.get("status") == "active"]
    return unique_record(active or matches, "item_id")


def resolve_inventory_item_by_sku_or_name(
    inventory_client: ZohoInventoryAPI,
    query: str,
    *,
    purchase_account_id: str | None = None,
) -> dict[str, object] | None:
    """Resolve one Inventory item, preferring exact SKU or name to partial name."""
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Inventory search query is required")
    target = cleaned.casefold()
    rows = _inventory_candidates(inventory_client, {"search_text": cleaned}, purchase_account_id)
    exact: list[dict[str, object]] = []
    partial: list[dict[str, object]] = []
    for row in rows:
        name = str(row.get("item_name") or row.get("name") or "").strip().casefold()
        sku = str(row.get("sku") or "").strip().casefold()
        if target in (name, sku):
            exact.append(row)
        elif target in name:
            partial.append(row)
    return unique_record(exact or partial, "item_id")


from .bins import get_bins_by_item_map, get_bins_for_items

__all__ = [
    "fetch_items_lookup",
    "fetch_items_by_purchase_account",
    "find_item_by_sku_or_name",
    "resolve_inventory_item_by_sku_or_name",
    "resolve_inventory_sku",
    "get_bins_for_items",
    "get_bins_by_item_map",
]

