from __future__ import annotations

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.inventory.base import BaseResource


class InventoryAdjustments(BaseResource):
    """Resource class for Zoho Inventory Adjustments operations."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "inventoryadjustments")
