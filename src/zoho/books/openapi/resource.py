"""Wire encoding and argument guards for generated Books operations."""
from __future__ import annotations

from utils.file_utils import json
from typing import Any
from urllib.parse import quote

from ..base import BaseResource


class BooksOperationResource(BaseResource):
    """Use the shared Books transport without changing existing CRUD semantics."""

    def _request_operation(
        self, method: str, path: str, *, path_values: dict[str, str],
        required_query: list[str], required_headers: list[str], media: list[str],
        body_required: bool, upload: bool, body: dict[str, Any] | list[dict[str, Any]] | None,
        params: dict[str, Any] | None, headers: dict[str, Any] | None,
        files: dict[str, Any] | None, stream: bool, timeout: int | None,
    ) -> object:
        for name, value in path_values.items():
            if not isinstance(value, str) or not value.strip() or value in {'.', '..'}:
                raise ValueError(f'{name} must be a non-empty path identifier')
            path = path.replace('{' + name + '}', quote(value, safe=''))
        query = dict(params or {})
        organization = getattr(self.client, 'organization_id', None)
        if query.get('organization_id', organization) != organization:
            raise ValueError('organization_id cannot override the Books client organization')
        for name in required_query:
            if name not in query or query[name] is None or query[name] == '':
                raise ValueError(f'{path}: required query parameter {name!r} is missing')
        normalized_headers = {k.lower(): v for k,v in (headers or {}).items()}
        for name in required_headers:
            if not normalized_headers.get(name.lower()):
                raise ValueError(f'{path}: required header {name!r} is missing')
        if files and not upload:
            raise ValueError(f'{path}: this operation does not accept multipart files')
        if body is not None and not media and not upload:
            raise ValueError(f'{path}: this operation does not define a request body')
        if body_required and body is None and not files:
            raise ValueError(f'{path}: a request body is required')
        multipart = bool(files) or 'multipart/form-data' in media
        # Books represents structured payloads alongside files as JSONString.
        data = None
        if multipart and body is not None:
            data = body if 'multipart/form-data' in media else {'JSONString': json.dumps(body)}
        return self.client.request(
            method, path.lstrip('/'), json=None if multipart else body,
            data=data, params=query, headers=headers, files=files,
            stream=stream, timeout=timeout,
        )
