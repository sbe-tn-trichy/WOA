"""Encode requests for the Analytics OpenAPI operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from utils.file_utils import json

if TYPE_CHECKING:
    from ..client import ZohoAnalyticsAPI


class AnalyticsOperationResource:
    def __init__(self, client: ZohoAnalyticsAPI) -> None:
        self.client = client

    def _request_operation(
        self,
        method: str,
        endpoint: str,
        *,
        path_values: dict[str, str],
        config: dict[str, Any] | None = None,
        config_location: str | None = None,
        upload: Any = None,
        inline_data: str | None = None,
        destination_org_id: str | None = None,
        is_mutation: bool | None = None,
        stream: bool = False,
        timeout: int | None = None,
    ) -> Any:
        for name, value in path_values.items():
            if not isinstance(value, str) or not value.strip() or value in {".", ".."}:
                raise ValueError(f"{name} must be a non-empty path identifier")
            endpoint = endpoint.replace("{" + name + "}", quote(value, safe=""))

        if config is not None and not isinstance(config, dict):
            raise ValueError("config must be a dictionary")
        encoded = {"CONFIG": json.dumps(config)} if config is not None else None
        files = None
        if config_location == "multipart":
            if (upload is None) == (inline_data is None):
                raise ValueError("Provide exactly one of upload or inline_data")
            # A filename-less part sends DATA as a multipart form field.
            files = {"FILE": upload} if upload is not None else {"DATA": (None, inline_data)}

        return self.client.request(
            method,
            endpoint,
            params=encoded if config_location == "query" else None,
            data=encoded if config_location in {"form", "multipart"} else None,
            files=files,
            headers={"ZANALYTICS-DEST-ORGID": destination_org_id} if destination_org_id else None,
            is_mutation=is_mutation,
            stream=stream,
            timeout=timeout,
        )
