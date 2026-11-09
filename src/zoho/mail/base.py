from __future__ import annotations

import builtins
from collections.abc import Mapping
from typing import TYPE_CHECKING, ClassVar

from .exceptions import ZohoMailError

if TYPE_CHECKING:
    from zoho.core_sdk.base_client import BaseZohoClient


class BaseResource:
    """Base class for Zoho Mail modules providing standard CRUD operations."""

    required_fields: ClassVar[builtins.list[str]] = []
    defaults: ClassVar[dict[str, object]] = {}

    def __init__(self, client: BaseZohoClient, endpoint: str):
        self.client = client
        self.endpoint = endpoint

    def _prepare_payload(self, data: Mapping[str, object], check_required: bool = True) -> dict[str, object]:
        """Merge defaults (if creating) and check if all required fields are present."""
        if check_required:
            payload: dict[str, object] = {**self.defaults, **data}
        else:
            payload = dict(data)

        if check_required:
            missing = [field for field in self.required_fields if field not in payload]
            if missing:
                raise ZohoMailError(f"Missing required fields: {', '.join(missing)}")

        return payload

    def list(self, params: Mapping[str, object] | None = None) -> object:
        return self.client.request('GET', self.endpoint, params=params)

    def get(self, resource_id: str, params: Mapping[str, object] | None = None) -> object:
        return self.client.request('GET', f"{self.endpoint}/{resource_id}", params=params)

    def create(
        self,
        data: Mapping[str, object],
        params: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
    ) -> object:
        payload = self._prepare_payload(data, check_required=True)
        return self.client.request('POST', self.endpoint, json=payload, params=params, files=files)

    def update(
        self,
        resource_id: str,
        data: Mapping[str, object],
        params: Mapping[str, object] | None = None,
        files: Mapping[str, object] | None = None,
    ) -> object:
        payload = self._prepare_payload(data, check_required=False)
        return self.client.request('PUT', f"{self.endpoint}/{resource_id}", json=payload, params=params, files=files)

    def delete(self, resource_id: str, params: Mapping[str, object] | None = None) -> object:
        return self.client.request('DELETE', f"{self.endpoint}/{resource_id}", params=params)

    def _action(
        self,
        method: str,
        resource_id: str | None,
        action: str,
        data: Mapping[str, object] | None = None,
        params: Mapping[str, object] | None = None,
    ) -> object:
        """Helper for action endpoints."""
        url = f"{self.endpoint}/{resource_id}/{action}" if resource_id else f"{self.endpoint}/{action}"
        return self.client.request(method, url, json=data, params=params)
