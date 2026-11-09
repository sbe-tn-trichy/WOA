from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from .exceptions import ZohoWorkdriveError

if TYPE_CHECKING:
    from zoho.core_sdk.base_client import BaseZohoClient


class BaseResource:
    """Base class for Zoho Workdrive resources providing standard operations."""

    def __init__(self, client: BaseZohoClient, endpoint: str):
        self.client = client
        self.endpoint = endpoint

    def _action(
        self,
        method: str,
        resource_id: str,
        action: str,
        data: Mapping[str, object] | None = None,
        params: Mapping[str, object] | None = None,
    ) -> object:
        """Perform a specific action on a resource."""
        endpoint = f"{self.endpoint}/{resource_id}/{action}" if action else f"{self.endpoint}/{resource_id}"
        return self.client.request(method, endpoint, json=data, params=params)
