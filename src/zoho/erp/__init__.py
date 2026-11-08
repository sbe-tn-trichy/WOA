"""Zoho ERP SDK, generated from ERP OpenAPI YAML definitions."""

from utils.general_utils.module_aliases import register_module_aliases

register_module_aliases({"zoho.erp.generated": "zoho.erp.openapi.generated"})

from .client import ZohoERPAPI
from zoho.core_sdk.exceptions import ZohoERPError

__all__ = ["ZohoERPAPI", "ZohoERPError"]

