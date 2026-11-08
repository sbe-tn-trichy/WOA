from utils.general_utils.module_aliases import register_module_aliases

_MODULE_ALIASES = {
    "zoho.analytics.metadata": "zoho.analytics.custom.metadata",
    "zoho.analytics.resources": "zoho.analytics.custom.resources",
    "zoho.analytics.snapshot": "zoho.analytics.custom.snapshot",
    "zoho.auth": "zoho.core_sdk.auth",
    "zoho.base_client": "zoho.core_sdk.base_client",
    "zoho.base_resource": "zoho.core_sdk.base_resource",
    "zoho.exceptions": "zoho.core_sdk.exceptions",
    "zoho.identifiers": "zoho.core_sdk.identifiers",
    "zoho.logging": "zoho.core_sdk.logging",
    "zoho.security": "zoho.core_sdk.security",
    "zoho.validation": "zoho.core_sdk.validation",
    "zoho.erp.generated": "zoho.erp.openapi.generated",
    "zoho.inventory.resources.items": "zoho.inventory.resources.catalog.items",
    "zoho.inventory.resources.item_groups": "zoho.inventory.resources.catalog.item_groups",
    "zoho.inventory.resources.bins": "zoho.inventory.resources.catalog.bins",
    "zoho.inventory.resources.batches": "zoho.inventory.resources.catalog.batches",
    "zoho.inventory.resources.packages": "zoho.inventory.resources.fulfillment.packages",
    "zoho.inventory.resources.shipments": "zoho.inventory.resources.fulfillment.shipments",
    "zoho.inventory.resources.picklists": "zoho.inventory.resources.fulfillment.picklists",
    "zoho.inventory.resources.inventory_adjustments": "zoho.inventory.resources.movements.inventory_adjustments",
    "zoho.inventory.resources.move_orders": "zoho.inventory.resources.movements.move_orders",
    "zoho.inventory.resources.transfer_orders": "zoho.inventory.resources.movements.transfer_orders",
}
register_module_aliases(_MODULE_ALIASES)

from .analytics import ZohoAnalyticsAPI, ZohoAnalyticsError
from zoho.core_sdk.auth import CatalystAuth, HttpTokenProvider, ZohoOAuth2Manager
from .books import ZohoBooksAPI, ZohoBooksError
from .cliq import ZohoCliqAPI
from .creator import ZohoCreatorAPI, ZohoCreatorError
from .erp import ZohoERPAPI, ZohoERPError
from zoho.core_sdk.exceptions import (
    ZohoAuthError,
    ZohoCliqError,
    ZohoConfigurationError,
    ZohoError,
    ZohoSheetError,
    ZohoTokenResponseError,
    ZohoTokenServiceError,
)
from zoho.core_sdk.identifiers import (
    AccountId,
    CustomerId,
    InvoiceId,
    LocationId,
    PaymentId,
)
from .inventory import ZohoInventoryAPI, ZohoInventoryError
from zoho.core_sdk.logging import configure_service_logger
from .mail import ZohoMailAPI, ZohoMailError
from zoho.core_sdk.security import (
    mask_sensitive_value,
    resolve_output_path,
    sanitize_filename,
    sanitize_log_params,
)
from .sheet import ZohoSheetAPI
from zoho.core_sdk.validation import require_record, require_records, require_text
from .wd import ZohoWorkdriveAPI

__all__ = [
    "ZohoConfigurationError",
    "ZohoTokenResponseError",
    "ZohoTokenServiceError",
    "configure_service_logger",
    "ZohoERPAPI",
    "ZohoERPError",
    "require_record",
    "require_records",
    "require_text",
    "PaymentId",
    "InvoiceId",
    "CustomerId",
    "AccountId",
    "LocationId",
    "ZohoBooksAPI",
    "ZohoBooksError",
    "ZohoCliqAPI",
    "ZohoMailAPI",
    "ZohoMailError",
    "ZohoSheetAPI",
    "ZohoWorkdriveAPI",
    "ZohoInventoryAPI",
    "ZohoInventoryError",
    "ZohoCreatorAPI",
    "ZohoCreatorError",
    "ZohoAnalyticsAPI",
    "ZohoAnalyticsError",
    "ZohoOAuth2Manager",
    "CatalystAuth",
    "HttpTokenProvider",
    "ZohoAuthError",
    "ZohoError",
    "ZohoCliqError",
    "ZohoSheetError",
    "sanitize_filename",
    "resolve_output_path",
    "mask_sensitive_value",
    "sanitize_log_params",
]
