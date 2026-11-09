from __future__ import annotations

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.inventory.base import BaseResource


class ItemGroups(BaseResource):
    """Resource class for Zoho Inventory Item Groups operations."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "itemgroups")

    def mark_as_active(self, itemgroup_id: str) -> object:
        """Mark an item group status as active."""
        return self._action("POST", itemgroup_id, "active")

    def mark_as_inactive(self, itemgroup_id: str) -> object:
        """Mark an item group status as inactive."""
        return self._action("POST", itemgroup_id, "inactive")
