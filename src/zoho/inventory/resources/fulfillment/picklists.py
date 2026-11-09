from __future__ import annotations

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.inventory.base import BaseResource


class Picklists(BaseResource):
    """Resource class for Zoho Inventory Picklists operations."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "picklists")

    def mark_status(self, picklist_id: str, status: str) -> object:
        """Update the status of a picklist."""
        payload = {"status": status}
        return self._action("POST", picklist_id, "status", data=payload)
