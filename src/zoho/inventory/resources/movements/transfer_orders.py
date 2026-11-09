from __future__ import annotations

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.inventory.base import BaseResource


class TransferOrders(BaseResource):
    """Resource class for Zoho Inventory Transfer Orders operations."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "transferorders")

    def mark_as_in_transit(self, transfer_order_id: str) -> object:
        """Mark a transfer order as in-transit."""
        return self._action("POST", transfer_order_id, "status/intransit")

    def mark_as_received(self, transfer_order_id: str) -> object:
        """Mark a transfer order as received."""
        return self._action("POST", transfer_order_id, "status/received")

    def submit_for_approval(self, transfer_order_id: str) -> object:
        """Submit a transfer order for approval."""
        return self._action("POST", transfer_order_id, "submit")

    def approve(self, transfer_order_id: str) -> object:
        """Approve a transfer order."""
        return self._action("POST", transfer_order_id, "approve")

    def reject(self, transfer_order_id: str) -> object:
        """Reject a transfer order."""
        return self._action("POST", transfer_order_id, "reject")
