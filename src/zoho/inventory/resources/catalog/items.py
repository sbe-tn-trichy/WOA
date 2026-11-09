from __future__ import annotations

from collections.abc import Mapping, Sequence

from utils.file_utils import json
from zoho.core_sdk.base_client import BaseZohoClient
from zoho.core_sdk.validation import require_record, require_records
from zoho.inventory.base import BaseResource


class Items(BaseResource):
    """Resource class for Zoho Inventory Items operations."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "items")

    def mark_as_active(self, item_id: str) -> object:
        """Activate an Inventory item."""
        return self._action("POST", item_id, "active")

    def mark_as_inactive(self, item_id: str) -> object:
        """Deactivate an Inventory item."""
        return self._action("POST", item_id, "inactive")

    def get_details(
        self, item_ids: Sequence[str], batch_size: int = 50
    ) -> list[dict[str, object]]:
        """Bulk-fetch complete items through GET /itemdetails; require every ID."""
        if not 1 <= batch_size <= 50:
            raise ValueError("batch_size must be between 1 and 50")
        if any(not isinstance(value, str) or not value.isdigit() for value in item_ids):
            raise ValueError("item_ids must be non-empty numeric strings")
        ids = list(dict.fromkeys(item_ids))
        result: list[dict[str, object]] = []
        for start in range(0, len(ids), batch_size):
            batch = ids[start : start + batch_size]
            response = require_record(
                self.client.request(
                    "GET", "itemdetails", params={"item_ids": ",".join(batch)}
                ),
                "itemdetails",
            )
            raw_items = response.get("items", [])
            items = (
                require_records(raw_items, "items")
                if isinstance(raw_items, list)
                else []
            )
            returned = [str(item["item_id"]) for item in items]
            if (
                response.get("code", 0) != 0
                or len(returned) != len(batch)
                or set(returned) != set(batch)
            ):
                raise ValueError("Incomplete or unexpected itemdetails response")
            by_id = {str(item["item_id"]): item for item in items}
            result.extend(by_id[item_id] for item_id in batch)
        return result

    def list_bins(self, item_id: str, location_id: str) -> list[dict[str, object]]:
        """Read item-specific bin balances at one location."""
        if not item_id or not location_id:
            raise ValueError("item_id and location_id required")
        return BaseResource(self.client, "storagelocations").list_all(
            params={"item_id": item_id, "location_id": location_id},
            resource_key="storage_locations",
        )

    def group_items(self, data: Mapping[str, object]) -> object:
        """
        Group existing items under a new item group.
        """
        payload = {"JSONString": json.dumps(dict(data))}
        return self.client.request(
            "POST",
            "items/grouping",
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
            },
            data=payload,
        )

    def list_by_status(self, status: str = "active") -> list[dict[str, object]]:
        params: dict[str, object] = {}
        if status:
            params["filter_by"] = f"Status.{status.title()}"
        return self.list_all(params=params)

    def list_by_purchase_account(
        self,
        account_id: str,
        status: str = "all",
    ) -> list[dict[str, object]]:
        account_id = str(account_id or "").strip()
        if not account_id:
            raise ValueError("purchase_account_id is required.")
        params: dict[str, object] = {"purchase_account_id": account_id}
        if status:
            params["filter_by"] = f"Status.{status.title()}"
        return self.list_all(params=params)

    def mark_inactive_bulk(
        self,
        item_ids: Sequence[str],
        batch_size: int = 200,
    ) -> list[dict[str, object]]:
        if batch_size < 1 or batch_size > 200:
            raise ValueError("batch_size must be between 1 and 200")
        clean_ids = [
            str(item_id).strip() for item_id in item_ids if str(item_id).strip()
        ]
        responses: list[dict[str, object]] = []
        for start in range(0, len(clean_ids), batch_size):
            batch_ids = clean_ids[start : start + batch_size]
            response = self.client.request(
                "POST",
                "items/inactive",
                params={"item_ids": ",".join(batch_ids)},
            )
            responses.append({"item_ids": batch_ids, "response": response})
        return responses
