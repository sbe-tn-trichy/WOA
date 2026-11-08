"""Shared argument validation and wire encoding for generated ERP operations."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

if TYPE_CHECKING:
    from ..client import ZohoERPAPI


class ERPResource:
    def __init__(self, client: ZohoERPAPI) -> None:
        self.client = client

    def _request(
        self, method: str, path: str, version: str, *,
        path_values: dict[str, str], required_query: list[str],
        required_headers: list[str], media: list[str], body_required: bool,
        body: dict[str, Any] | None, params: dict[str, Any] | None,
        headers: dict[str, Any] | None, files: dict[str, Any] | None,
        stream: bool, timeout: int | None,
    ) -> object:
        for name, value in path_values.items():
            if not isinstance(value, str) or not value.strip() or value in {".", ".."}:
                raise ValueError(f"{name} must be a non-empty path identifier")
            path = path.replace("{" + name + "}", quote(value, safe=""))
        query = dict(params or {})
        for name in required_query:
            if name not in query or query[name] is None or query[name] == "":
                raise ValueError(f"{path}: required query parameter {name!r} is missing")
        supplied_headers = {name.lower(): value for name, value in (headers or {}).items()}
        for name in required_headers:
            if not supplied_headers.get(name.lower()):
                raise ValueError(f"{path}: required header {name!r} is missing")
        multipart = "multipart/form-data" in media
        if files and not multipart:
            raise ValueError(f"{path}: this operation does not accept multipart files")
        if body is not None and not media:
            raise ValueError(f"{path}: this operation does not define a request body")
        if body_required and body is None and not files:
            raise ValueError(f"{path}: a request body is required")
        return self.client.request(
            method, path.lstrip("/"), json=None if multipart else body,
            data=body if multipart else None, params=query, headers=headers,
            files=files, stream=stream, timeout=timeout,
            override_url=f"https://www.zohoapis.{self.client.domain}/erp/{version}{path}",
        )
