from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, overload

from utils.file_utils import json
from utils.http_utils import http_transport
from utils.http_utils.http import write_response_to_file
from zoho.core_sdk.base_client import BaseZohoClient
from zoho.core_sdk.security import resolve_output_path
from zoho.core_sdk.validation import require_records
from ..base import BaseResource
from .mixins import ActiveInactiveMixin


class Contacts(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "contacts")

    def list_customers(
        self, filters: Mapping[str, object] | None = None
    ) -> list[dict[str, object]]:
        """Fetch all active customer contacts, with optional filter overrides."""
        params: dict[str, object] = {"filter_by": "Status.Active", **(filters or {})}
        params["contact_type"] = "customer"
        contacts = self.list_all(params=params, resource_key="contacts")
        return [
            contact
            for contact in contacts
            if str(contact.get("contact_type", "")).lower() == "customer"
        ]

    def bulk_update(
        self,
        contacts: Sequence[Mapping[str, object]],
        params: Mapping[str, object] | None = None,
    ) -> object:
        """Update multiple contacts in one form-encoded API request."""
        return self.client.request(
            "PUT",
            self.endpoint,
            data={"JSONString": json.dumps(list(contacts))},
            params=dict(params) if params else None,
        )

    def enable_portal(
        self, contact_id: str, data: Mapping[str, object]
    ) -> object:
        return self._action("POST", contact_id, "portal/enable", data=dict(data))

    def email_statement(
        self,
        contact_id: str,
        data: Mapping[str, object],
        params: Mapping[str, object] | None = None,
    ) -> object:
        return self._action(
            "POST",
            contact_id,
            "statements/email",
            data=dict(data),
            params=dict(params) if params else None,
        )

    @overload
    def get_statement(
        self,
        contact_id: str,
        params: Mapping[str, object] | None = None,
        *,
        stream: Literal[True],
    ) -> http_transport.Response: ...

    @overload
    def get_statement(
        self,
        contact_id: str,
        params: Mapping[str, object] | None = None,
        *,
        stream: Literal[False] = False,
    ) -> object: ...

    @overload
    def get_statement(
        self,
        contact_id: str,
        params: Mapping[str, object] | None = None,
        *,
        stream: bool = False,
    ) -> object: ...

    def get_statement(
        self,
        contact_id: str,
        params: Mapping[str, object] | None = None,
        *,
        stream: bool = False,
    ) -> object:
        """
        Retrieve a statement for a contact.
        Returns binary content (e.g. XLS or PDF) depending on the parameters (e.g. accept='xls').
        """
        if stream:
            return self.client.request(
                "GET",
                f"{self.endpoint}/{contact_id}/statements",
                params=dict(params) if params else None,
                stream=True,
            )
        return self._action(
            "GET", contact_id, "statements", params=dict(params) if params else None
        )

    def download_statement(
        self,
        contact_id: str,
        save_path: str,
        params: Mapping[str, object] | None = None,
    ) -> str:
        """
        Download a contact statement and save it to the specified path.
        """
        params_dict: dict[str, object] = dict(params or {})
        if "accept" not in params_dict:
            params_dict["accept"] = "xls"

        resolved_path = resolve_output_path(save_path)
        response = self.get_statement(contact_id, params=params_dict, stream=True)
        return write_response_to_file(response, resolved_path)


class Organizations(BaseResource):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "organizations")


class ChartOfAccounts(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "chartofaccounts")

    def list_transactions(
        self,
        account_id: str,
        params: Mapping[str, object] | None = None,
    ) -> object:
        """Return one page of transactions involving a financial account."""
        if not account_id:
            raise ValueError("account_id is required.")
        query: dict[str, object] = {**(params or {}), "account_id": account_id}
        return self.client.request(
            "GET",
            f"{self.endpoint}/accounttransactions",
            params=query,
        )

    def list_all_transactions(
        self,
        account_id: str,
        params: Mapping[str, object] | None = None,
    ) -> list[dict[str, object]]:
        """Return every page of transactions involving a financial account."""
        transactions: list[dict[str, object]] = []
        page = 1
        filters = dict(params or {})

        while True:
            response = self.list_transactions(
                account_id,
                params={**filters, "page": page, "per_page": 200},
            )
            raw_txs = response.get("transactions") if isinstance(response, Mapping) else None
            if isinstance(raw_txs, list):
                transactions.extend(require_records(raw_txs, "transactions"))
            page_ctx = response.get("page_context") if isinstance(response, Mapping) else None
            has_more = isinstance(page_ctx, Mapping) and bool(
                page_ctx.get("has_more_page", False)
            )
            if not has_more:
                return transactions
            page += 1


class Vendors(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "vendors")

    @overload
    def get_statement(
        self,
        vendor_id: str,
        params: Mapping[str, object] | None = None,
        *,
        stream: Literal[True],
    ) -> http_transport.Response: ...

    @overload
    def get_statement(
        self,
        vendor_id: str,
        params: Mapping[str, object] | None = None,
        *,
        stream: Literal[False] = False,
    ) -> object: ...

    @overload
    def get_statement(
        self,
        vendor_id: str,
        params: Mapping[str, object] | None = None,
        *,
        stream: bool = False,
    ) -> object: ...

    def get_statement(
        self,
        vendor_id: str,
        params: Mapping[str, object] | None = None,
        *,
        stream: bool = False,
    ) -> object:
        """
        Retrieve a statement for a vendor.
        Returns binary content (e.g. XLS or PDF) depending on the parameters (e.g. accept='xls').
        """
        if stream:
            return self.client.request(
                "GET",
                f"{self.endpoint}/{vendor_id}/statements",
                params=dict(params) if params else None,
                stream=True,
            )
        return self._action(
            "GET", vendor_id, "statements", params=dict(params) if params else None
        )

    def download_statement(
        self,
        vendor_id: str,
        save_path: str,
        params: Mapping[str, object] | None = None,
    ) -> str:
        """
        Download a vendor statement and save it to the specified path.
        """
        params_dict: dict[str, object] = dict(params or {})
        if "accept" not in params_dict:
            params_dict["accept"] = "xls"

        resolved_path = resolve_output_path(save_path)
        response = self.get_statement(vendor_id, params=params_dict, stream=True)
        return write_response_to_file(response, resolved_path)


class Locations(BaseResource):
    """Organization locations and their India tax-registration settings."""

    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "locations")


class CustomFields:
    """Zoho Books custom-field settings endpoints."""

    def __init__(self, client: BaseZohoClient) -> None:
        self.client = client

    def list_for_entity(
        self,
        entity: str,
        params: Mapping[str, object] | None = None,
    ) -> list[dict[str, object]]:
        if not entity:
            raise ValueError("entity is required.")
        query: dict[str, object] = {"entity": entity, "filter_custom_fields": True}
        if params:
            query.update(params)
        response = self.client.request("GET", "settings/fields", params=query)
        if isinstance(response, Mapping):
            fields = response.get("fields", [])
            if isinstance(fields, list):
                return require_records(fields, "settings/fields")
        return []

    def create(self, data: Mapping[str, object]) -> object:
        required = ("label", "data_type", "entity", "show_on_pdf")
        missing = [name for name in required if name not in data]
        if missing:
            raise ValueError(
                f"Missing required custom-field values: {', '.join(missing)}"
            )
        return self.client.request("POST", "settings/fields", json=dict(data))
