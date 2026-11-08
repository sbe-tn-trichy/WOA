import logging
import os
from typing import Any
from zoho.core_sdk.base_client import BaseZohoClient
from zoho.inventory.resources.catalog.items import Items
from zoho.inventory.resources.movements.move_orders import MoveOrders
from zoho.inventory.resources.movements.transfer_orders import TransferOrders
from zoho.inventory.resources.movements.inventory_adjustments import InventoryAdjustments
from zoho.inventory.resources.fulfillment.packages import Packages
from zoho.inventory.resources.fulfillment.shipments import Shipments
from zoho.inventory.resources.fulfillment.picklists import Picklists
from zoho.inventory.resources.catalog.bins import Bins
from zoho.inventory.resources.catalog.batches import Batches
from zoho.inventory.resources.catalog.item_groups import ItemGroups

class ZohoInventoryAPI(BaseZohoClient):
    """
    Main Zoho Inventory API Client linking all modules together.
    """
    def __init__(
        self,
        access_token: str,
        organization_id: str,
        domain: str = "in",
        on_request_completed: Any | None = None,
        token_refresh_callback: Any | None = None
    ):
        if not organization_id:
            raise ValueError("organization_id is required.")
            
        base_url = f"https://www.zohoapis.{domain}/inventory/v1"
        super().__init__(
            access_token=access_token,
            domain=domain,
            base_url=base_url,
            service_name="inventory",
            token_refresh_callback=token_refresh_callback,
            on_request_completed=on_request_completed,
            default_timeout=30
        )
        self.organization_id = organization_id

        # Initialize sub-resources
        self.items = Items(self)
        self.move_orders = MoveOrders(self)
        self.transfer_orders = TransferOrders(self)
        self.inventory_adjustments = InventoryAdjustments(self)
        self.packages = Packages(self)
        self.shipments = Shipments(self)
        self.picklists = Picklists(self)
        self.bins = Bins(self)
        self.batches = Batches(self)
        self.item_groups = ItemGroups(self)

    def request(
        self,
        method: str,
        endpoint: str,
        json: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
        stream: bool = False,
        override_url: str | None = None,
        is_mutation: bool | None = None,
        timeout: int | None = None,
    ) -> Any:
        """
        Internal HTTP request handler with logging.
        """
        params = dict(params or {})
        if 'organization_id' not in params:
            params['organization_id'] = self.organization_id
            
        return super().request(
            method=method,
            endpoint=endpoint,
            json=json,
            data=data,
            params=params,
            headers=headers,
            files=files,
            stream=stream,
            override_url=override_url,
            is_mutation=is_mutation,
            timeout=timeout,
        )
