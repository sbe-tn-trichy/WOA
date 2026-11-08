from __future__ import annotations

import builtins
import logging
from collections.abc import Iterator

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.core_sdk.exceptions import ZohoError
from zoho.core_sdk.validation import require_record, require_records


class BaseResource:
    """Shared base class for Zoho API modules providing standard CRUD and pagination."""

    required_fields: builtins.list[str] = []
    defaults: dict[str, object] = {}
    line_item_required_fields: builtins.list[str] = []
    line_item_defaults: dict[str, object] = {}
    error_class: type[ZohoError] = ZohoError
    logger_name: str = "zoho.api"

    def __init__(self, client: BaseZohoClient, endpoint: str) -> None:
        self.client = client
        self.endpoint = endpoint

    def _prepare_payload(self, data: dict[str, object], check_required: bool = True) -> dict[str, object]:
        """Merge defaults (if creating) and check if all required fields are present."""
        payload = {**self.defaults, **data} if check_required else data.copy()

        logger = logging.getLogger(self.logger_name)

        if check_required:
            missing = [field for field in self.required_fields if field not in payload]
            if missing:
                logger.error(f"Validation failed. Payload keys: {list(payload.keys())}. Missing: {missing}")
                raise self.error_class(f"Missing required fields: {', '.join(missing)}")

        if "line_items" in payload and isinstance(payload["line_items"], list):
            processed_items = []
            for index, item in enumerate(require_records(payload["line_items"], "Payload line_items")):
                if check_required:
                    full_item = {**self.line_item_defaults, **item}
                else:
                    full_item = item.copy()

                if check_required:
                    missing_item_fields = [f for f in self.line_item_required_fields if f not in full_item]
                    if missing_item_fields:
                        raise self.error_class(
                            f"Line item {index} missing required fields: {', '.join(missing_item_fields)}"
                        )
                processed_items.append(full_item)

            payload["line_items"] = processed_items

        return payload

    def list(self, params: dict[str, object] | None = None) -> object:
        response: object = self.client.request("GET", self.endpoint, params=params)
        return response

    def list_iter(
        self,
        params: dict[str, object] | None = None,
        resource_key: str | None = None,
        per_page: int = 200,
    ) -> Iterator[dict[str, object]]:
        """Generator yielding records item-by-item across pages without buffering all in memory."""
        if type(per_page) is not int or per_page <= 0:
            raise ValueError("per_page must be a positive integer")
        page = 1
        params = params or {}
        key = resource_key or self.endpoint.split("/")[-1]

        while True:
            current_params = {**params, "page": page, "per_page": per_page}
            response = self.list(params=current_params)
            context = f"{self.endpoint} page {page}"
            try:
                res = require_record(response, context)
                if key not in res:
                    raise ValueError(f"Missing resource key {key!r}")
                rows = require_records(res[key], f"{context} records")
                pagination = require_record(res.get("page_context", {}), f"{context} pagination")
                more = pagination.get("has_more_page", False)
                if type(more) is not bool:
                    raise ValueError("has_more_page must be boolean")
                if "page" in pagination and (type(pagination["page"]) is not int or pagination["page"] != page):
                    raise ValueError("Response page does not match requested page")
                if not rows and more:
                    raise ValueError("Empty page claims more results")
            except ValueError as exc:
                raise self.error_class(f"Invalid pagination for {context}: {exc}", endpoint=self.endpoint) from exc
            yield from rows
            if not more:
                break
            page += 1

    def list_all(
        self,
        params: dict[str, object] | None = None,
        resource_key: str | None = None,
    ) -> builtins.list[dict[str, object]]:
        """Helper to fetch all records across all pages."""
        return list(self.list_iter(params=params, resource_key=resource_key))

    def get(self, resource_id: str, params: dict[str, object] | None = None) -> object:
        response: object = self.client.request("GET", f"{self.endpoint}/{resource_id}", params=params)
        return response

    def create(
        self,
        data: dict[str, object],
        params: dict[str, object] | None = None,
        files: dict[str, object] | None = None,
    ) -> object:
        payload = self._prepare_payload(data, check_required=True)
        response: object = self.client.request("POST", self.endpoint, json=payload, params=params, files=files)
        return response

    def update(
        self,
        resource_id: str,
        data: dict[str, object],
        params: dict[str, object] | None = None,
        files: dict[str, object] | None = None,
    ) -> object:
        payload = self._prepare_payload(data, check_required=False)
        response: object = self.client.request("PUT", f"{self.endpoint}/{resource_id}", json=payload, params=params, files=files)
        return response

    def delete(self, resource_id: str, params: dict[str, object] | None = None) -> object:
        response: object = self.client.request("DELETE", f"{self.endpoint}/{resource_id}", params=params)
        return response

    def _action(
        self,
        method: str,
        resource_id: str | None,
        action: str,
        data: dict[str, object] | None = None,
        params: dict[str, object] | None = None,
    ) -> object:
        """Helper for action endpoints like /invoices/{id}/status/sent."""
        url = f"{self.endpoint}/{resource_id}/{action}" if resource_id else f"{self.endpoint}/{action}"
        response: object = self.client.request(method, url, json=data, params=params)
        return response
