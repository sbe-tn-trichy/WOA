from utils.file_utils import json
from typing import Any
from utils.http_utils.http import write_response_to_file
from zoho.core_sdk.security import resolve_output_path

from ..base import BaseResource
from .mixins import ActiveInactiveMixin

class Contacts(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: Any):
        super().__init__(client, 'contacts')

    def list_customers(self, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all active customer contacts, with optional filter overrides."""
        params = {"filter_by": "Status.Active", **(filters or {})}
        params["contact_type"] = "customer"
        contacts = self.list_all(params=params, resource_key="contacts")
        return [
            contact
            for contact in contacts
            if str(contact.get("contact_type", "")).lower() == "customer"
        ]

    def bulk_update(
        self,
        contacts: list[dict[str, Any]],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Update multiple contacts in one form-encoded API request."""
        return self.client.request(
            'PUT',
            self.endpoint,
            data={'JSONString': json.dumps(contacts)},
            params=params,
        )

    def enable_portal(self, contact_id: str, data: dict[str, Any]) -> dict[str, Any]:
        return self._action('POST', contact_id, 'portal/enable', data=data)

    def email_statement(self, contact_id: str, data: dict[str, Any], params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._action('POST', contact_id, 'statements/email', data=data, params=params)

    def get_statement(self, contact_id: str, params: dict[str, Any] | None = None, *, stream: bool = False) -> Any:
        """
        Retrieve a statement for a contact.
        Returns binary content (e.g. XLS or PDF) depending on the parameters (e.g. accept='xls').
        """
        if stream:
            return self.client.request('GET', f'{self.endpoint}/{contact_id}/statements', params=params, stream=True)
        return self._action('GET', contact_id, 'statements', params=params)

    def download_statement(self, contact_id: str, save_path: str, params: dict[str, Any] | None = None) -> str:
        """
        Download a contact statement and save it to the specified path.
        """
        if not params:
            params = {}
        if 'accept' not in params:
            params['accept'] = 'xls'

        save_path = resolve_output_path(save_path)
        response = self.get_statement(contact_id, params=params, stream=True)
        return write_response_to_file(response, save_path)


class Organizations(BaseResource):
    def __init__(self, client: Any):
        super().__init__(client, 'organizations')

class ChartOfAccounts(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: Any):
        super().__init__(client, 'chartofaccounts')

    def list_transactions(
        self,
        account_id: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return one page of transactions involving a financial account."""
        if not account_id:
            raise ValueError("account_id is required.")
        query = {**(params or {}), "account_id": account_id}
        return self.client.request(
            'GET',
            f'{self.endpoint}/accounttransactions',
            params=query,
        )

    def list_all_transactions(
        self,
        account_id: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return every page of transactions involving a financial account."""
        transactions: list[dict[str, Any]] = []
        page = 1
        filters = dict(params or {})

        while True:
            response = self.list_transactions(
                account_id,
                params={**filters, "page": page, "per_page": 200},
            )
            transactions.extend(response.get("transactions", []))
            if not response.get("page_context", {}).get("has_more_page", False):
                return transactions
            page += 1


class Vendors(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: Any):
        super().__init__(client, 'vendors')

    def get_statement(self, vendor_id: str, params: dict[str, Any] | None = None, *, stream: bool = False) -> Any:
        """
        Retrieve a statement for a vendor. 
        Returns binary content (e.g. XLS or PDF) depending on the parameters (e.g. accept='xls').
        """
        if stream:
            return self.client.request('GET', f'{self.endpoint}/{vendor_id}/statements', params=params, stream=True)
        return self._action('GET', vendor_id, 'statements', params=params)

    def download_statement(self, vendor_id: str, save_path: str, params: dict[str, Any] | None = None) -> str:
        """
        Download a vendor statement and save it to the specified path.
        """
        if not params:
            params = {}
        if 'accept' not in params:
            params['accept'] = 'xls'

        save_path = resolve_output_path(save_path)
        response = self.get_statement(vendor_id, params=params, stream=True)
        return write_response_to_file(response, save_path)


class Locations(BaseResource):
    """Organization locations and their India tax-registration settings."""

    def __init__(self, client: Any):
        super().__init__(client, "locations")

class CustomFields:
    """Zoho Books custom-field settings endpoints."""

    def __init__(self, client: Any):
        self.client = client

    def list_for_entity(
        self,
        entity: str,
        params: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if not entity:
            raise ValueError("entity is required.")
        query = {"entity": entity, "filter_custom_fields": True}
        if params:
            query.update(params)
        response = self.client.request("GET", "settings/fields", params=query)
        fields = response.get("fields", []) if isinstance(response, dict) else []
        return fields if isinstance(fields, list) else []

    def create(self, data: dict[str, Any]) -> dict[str, Any]:
        required = ("label", "data_type", "entity", "show_on_pdf")
        missing = [name for name in required if name not in data]
        if missing:
            raise ValueError(
                f"Missing required custom-field values: {', '.join(missing)}"
            )
        return self.client.request("POST", "settings/fields", json=dict(data))
