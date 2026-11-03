"""Zoho ERP client sharing the SDK OAuth and HTTP transport."""
from __future__ import annotations

import re
from typing import Any, Callable

from zoho.base_client import BaseZohoClient
from .generated import ERPResources, RESOURCE_TYPES


class ZohoERPAPI(BaseZohoClient, ERPResources):
    """ERP v1/v3 resources generated from the supplied OpenAPI definitions."""

    def __init__(
        self, access_token: Any, organization_id: str, domain: str = "in",
        on_request_completed: Callable[..., None] | None = None,
        token_refresh_callback: Callable[[], str] | None = None,
    ) -> None:
        if not isinstance(organization_id, str) or not organization_id.strip():
            raise ValueError("organization_id is required")
        if not re.fullmatch(r"[a-z]+(?:\.[a-z]+)*", domain):
            raise ValueError("domain must be a Zoho data-center suffix, e.g. 'in' or 'com'")
        super().__init__(access_token, domain, f"https://www.zohoapis.{domain}/erp/v1",
                         "erp", token_refresh_callback, on_request_completed)
        self.organization_id = organization_id
        for name, resource_type in RESOURCE_TYPES.items():
            setattr(self, name, resource_type(self))

    def request(
        self, method: str, endpoint: str,
        json: dict[str, Any] | None = None, data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None, headers: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None, stream: bool = False,
        override_url: str | None = None, is_mutation: bool | None = None,
        timeout: int | None = None,
    ) -> Any:
        query = dict(params or {})
        if query.get("organization_id", self.organization_id) != self.organization_id:
            raise ValueError("organization_id cannot override the ERP client's organization")
        query["organization_id"] = self.organization_id
        return super().request(
            method=method, endpoint=endpoint, json=json, data=data, params=query,
            headers=headers, files=files, stream=stream, override_url=override_url,
            is_mutation=is_mutation, timeout=timeout,
        )
