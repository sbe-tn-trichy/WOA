from __future__ import annotations

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.inventory.base import BaseResource


class Bins(BaseResource):
    """Resource class for Zoho Inventory Bins operations."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "bins")
