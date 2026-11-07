from typing import Any
from .exceptions import ZohoMailError

class BaseResource:
    """Base class for Zoho Mail modules providing standard CRUD operations."""
    required_fields: list[str] = []
    defaults: dict[str, Any] = {}

    def __init__(self, client: Any, endpoint: str):
        self.client = client
        self.endpoint = endpoint

    def _prepare_payload(self, data: dict[str, Any], check_required: bool = True) -> dict[str, Any]:
        """Merge defaults (if creating) and check if all required fields are present."""
        if check_required:
            payload = {**self.defaults, **data}
        else:
            payload = data.copy()
        
        if check_required:
            missing = [field for field in self.required_fields if field not in payload]
            if missing:
                raise ZohoMailError(f"Missing required fields: {', '.join(missing)}")
            
        return payload

    def list(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.client.request('GET', self.endpoint, params=params)

    def get(self, resource_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.client.request('GET', f"{self.endpoint}/{resource_id}", params=params)

    def create(self, data: dict[str, Any], params: dict[str, Any] | None = None, files: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = self._prepare_payload(data, check_required=True)
        return self.client.request('POST', self.endpoint, json=payload, params=params, files=files)

    def update(self, resource_id: str, data: dict[str, Any], params: dict[str, Any] | None = None, files: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = self._prepare_payload(data, check_required=False)
        return self.client.request('PUT', f"{self.endpoint}/{resource_id}", json=payload, params=params, files=files)

    def delete(self, resource_id: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.client.request('DELETE', f"{self.endpoint}/{resource_id}", params=params)

    def _action(self, method: str, resource_id: str | None, action: str, data: dict[str, Any] | None = None, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Helper for action endpoints."""
        url = f"{self.endpoint}/{resource_id}/{action}" if resource_id else f"{self.endpoint}/{action}"
        return self.client.request(method, url, json=data, params=params)
