from __future__ import annotations

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.inventory.base import BaseResource


class MoveOrders(BaseResource):
    """Resource class for Zoho Inventory Move Orders operations."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "moveorders")

    def mark_as_confirmed(self, move_order_id: str) -> object:
        """Mark a move order status as confirmed."""
        return self._action("POST", move_order_id, "status/confirmed")

    def mark_as_in_progress(self, move_order_id: str) -> object:
        """Mark a move order status as in progress."""
        return self._action("POST", move_order_id, "status/inprogress")

    def mark_as_completed(self, move_order_id: str) -> object:
        """Mark a move order status as completed."""
        return self._action("POST", move_order_id, "status/completed")
