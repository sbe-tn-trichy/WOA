from __future__ import annotations

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.inventory.base import BaseResource


class Shipments(BaseResource):
    """Resource class for Zoho Inventory Shipment Orders operations."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "shipmentorders")

    def mark_as_delivered(self, shipment_id: str) -> object:
        """Mark a shipment order status as delivered."""
        return self._action("POST", shipment_id, "status/delivered")
