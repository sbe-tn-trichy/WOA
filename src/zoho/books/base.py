from __future__ import annotations


from typing import ClassVar

from zoho.core_sdk.base_resource import BaseResource as _BaseResource
from .exceptions import ZohoBooksError


class BaseResource(_BaseResource):
    """Base class for Zoho Books modules providing standard CRUD operations."""

    logger_name: ClassVar[str] = "zoho.books.api"

    @property
    def error_class(self) -> type[ZohoBooksError]:
        return ZohoBooksError
