from __future__ import annotations


from zoho.core_sdk.base_resource import BaseResource as _BaseResource
from .exceptions import ZohoBooksError


class BaseResource(_BaseResource):
    """Base class for Zoho Books modules providing standard CRUD operations."""

    error_class: type[ZohoBooksError] = ZohoBooksError
    logger_name: str = "zoho.books.api"
