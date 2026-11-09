from __future__ import annotations


from typing import ClassVar

from zoho.core_sdk.base_resource import BaseResource as _BaseResource
from .exceptions import ZohoInventoryError


class BaseResource(_BaseResource):
    """Base class for Zoho Inventory modules providing standard CRUD operations."""

    logger_name: ClassVar[str] = "zoho.inventory.api"

    @property
    def error_class(self) -> type[ZohoInventoryError]:
        return ZohoInventoryError
