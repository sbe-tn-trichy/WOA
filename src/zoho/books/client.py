import logging
import os
from collections.abc import Callable, Mapping, Sequence

from zoho.core_sdk.base_client import BaseZohoClient
from .custom.contacts import Vendors
from .custom.sales import SalesReturns
from .custom.gst import GST
from .custom.contacts import CustomFields
from .custom.reports import Reports
from .openapi import BooksResources, RESOURCE_TYPES

class ZohoBooksAPI(BaseZohoClient, BooksResources):
    """
    Main Zoho Books API Client linking all modules together.
    """
    def __init__(
        self,
        access_token: str,
        organization_id: str,
        domain: str = "in",
        on_request_completed: Callable[..., None] | None = None,
        token_refresh_callback: Callable[..., str] | None = None,
    ):
        """
        Initialize the Zoho Books API client.
        """
        if not organization_id:
            raise ValueError("organization_id is required.")
            
        base_url = f"https://www.zohoapis.{domain}/books/v3"
        super().__init__(
            access_token=access_token,
            domain=domain,
            base_url=base_url,
            service_name="books",
            token_refresh_callback=token_refresh_callback,
            on_request_completed=on_request_completed,
            default_timeout=30
        )
        self.organization_id = organization_id
        
        # Initialize modules
        self.vendors = Vendors(self)
        self.sales_returns = SalesReturns(self)
        self.reports = Reports(self)
        self.gst = GST(self)
        self.custom_fields = CustomFields(self)
        for name, resource_type in RESOURCE_TYPES.items():
            setattr(self, name, resource_type(self))

    def request(
        self,
        method: str,
        endpoint: str,
        json: Mapping[str, object] | Sequence[object] | None = None,
        data: Mapping[str, object] | str | bytes | None = None,
        params: Mapping[str, object] | None = None,
        headers: Mapping[str, str] | None = None,
        files: Mapping[str, object] | None = None,
        stream: bool = False,
        override_url: str | None = None,
        is_mutation: bool | None = None,
        timeout: int | None = None,
    ) -> object:
        """
        Internal HTTP request handler with logging.
        """
        params_dict: dict[str, object] = dict(params or {})
        if 'organization_id' not in params_dict:
            params_dict['organization_id'] = self.organization_id
            
        return super().request(
            method=method,
            endpoint=endpoint,
            json=json,
            data=data,
            params=params_dict,
            headers=headers,
            files=files,
            stream=stream,
            override_url=override_url,
            is_mutation=is_mutation,
            timeout=timeout,
        )
