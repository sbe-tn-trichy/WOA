from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from zoho.core_sdk.auth import HttpTokenProvider
from zoho.core_sdk.base_client import BaseZohoClient
from zoho.core_sdk.identifiers import OrganizationId

from .custom import Metadata, Queries, Views
from .openapi import AnalyticsResources


class ZohoAnalyticsAPI(BaseZohoClient):
    """Client for Zoho Analytics v2 and its export and metadata helpers."""

    organization_id: OrganizationId

    def __init__(
        self,
        access_token: str,
        organization_id: OrganizationId | str,
        domain: str = "in",
        token_refresh_callback: Callable[[BaseZohoClient], None] | Callable[[], str] | None = None,
    ):
        if not organization_id:
            raise ValueError("organization_id is required.")
        super().__init__(
            access_token=access_token,
            domain=domain,
            base_url=f"https://analyticsapi.zoho.{domain}/restapi/v2",
            service_name="analytics",
            token_refresh_callback=token_refresh_callback,
            default_timeout=60,
        )
        self.organization_id = OrganizationId(organization_id)
        self.views = Views(self)
        self.metadata = Metadata(self)
        self.queries = Queries(self)
        self.openapi = AnalyticsResources(self)

    @classmethod
    def from_token_provider(
        cls,
        token_url: str = "http://localhost:3000/server/new/tokens",
        organization_id: OrganizationId | str | None = None,
        domain: str = "in",
        token_service_key: str = "zoho_analytics_conn",
        token_refresh_callback: Callable[[BaseZohoClient], None] | Callable[[], str] | None = None,
    ) -> "ZohoAnalyticsAPI":
        """Create a client using an access token from an HTTP token broker."""
        token = HttpTokenProvider(
            token_url,
            fallback_services={"zoho_analytics_conn": "analytics"},
        ).get_token(token_service_key)
        return cls(
            access_token=token,
            organization_id=organization_id or "",
            domain=domain,
            token_refresh_callback=token_refresh_callback,
        )

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
        request_headers: dict[str, str] = {"ZANALYTICS-ORGID": str(self.organization_id)}
        if headers:
            request_headers.update(headers)
        return super().request(
            method=method,
            endpoint=endpoint,
            json=json,
            data=data,
            params=params,
            headers=request_headers,
            files=files,
            stream=stream,
            override_url=override_url,
            is_mutation=is_mutation,
            timeout=timeout,
        )
