from typing import Any


class ZohoError(Exception):
    """Base exception class for all Zoho SDK errors."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | int | None = None,
        response_data: Any | None = None,
        endpoint: str | None = None,
        retry_after: str | int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.response_data = response_data
        self.endpoint = endpoint
        self.retry_after = retry_after


class ZohoERPError(ZohoError):
    """Zoho ERP API failure."""


class ZohoAuthError(ZohoError):
    """Authentication or token-provider failure."""


class ZohoAnalyticsError(ZohoError):
    """Zoho Analytics API failure."""


class ZohoBooksError(ZohoError):
    """Custom exception for Zoho Books API errors."""


class ZohoInventoryError(ZohoError):
    """Custom exception for Zoho Inventory API errors."""


class ZohoWorkdriveError(ZohoError):
    """Custom exception for Zoho WorkDrive API errors."""


class ZohoMailError(ZohoError):
    """Custom exception for Zoho Mail API errors."""


class ZohoCreatorError(ZohoError):
    """Custom exception for Zoho Creator API errors."""


class ZohoCliqError(ZohoError):
    """Custom exception for Zoho Cliq API errors."""


class ZohoSheetError(ZohoError):
    """Custom exception for Zoho Sheet API errors."""
