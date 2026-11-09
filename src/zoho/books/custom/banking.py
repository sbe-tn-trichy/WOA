from __future__ import annotations

from collections.abc import Mapping, Sequence

from zoho.core_sdk.base_client import BaseZohoClient
from ..base import BaseResource
from .mixins import ActiveInactiveMixin


class BankAccounts(BaseResource, ActiveInactiveMixin):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "bankaccounts")


class BankTransactions(BaseResource):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "banktransactions")

    def get_matches(self, transaction_id: str) -> object:
        return self._action("GET", f"uncategorized/{transaction_id}", "match")

    def match(
        self,
        transaction_id: str,
        data: Mapping[str, object] | Sequence[Mapping[str, object]],
    ) -> object:
        payload: dict[str, object] = (
            dict(data)
            if isinstance(data, Mapping)
            else {"transactions_to_be_matched": list(data)}
        )
        return self._action(
            "POST", f"uncategorized/{transaction_id}", "match", data=payload
        )

    def categorize_as_expense(
        self, transaction_id: str, data: Mapping[str, object]
    ) -> object:
        return self._action(
            "POST",
            f"uncategorized/{transaction_id}",
            "categorize/expenses",
            data=dict(data),
        )

    def categorize(
        self, transaction_id: str, data: Mapping[str, object]
    ) -> object:
        """Categorize a bank line, including a transfer_fund transaction."""
        return self._action(
            "POST",
            f"uncategorized/{transaction_id}",
            "categorize",
            data=dict(data),
        )

    def categorize_as_vendor_payment(
        self, transaction_id: str, data: Mapping[str, object]
    ) -> object:
        """Categorize a vendor payment; no bill allocations records an advance."""
        return self._action(
            "POST",
            f"uncategorized/{transaction_id}",
            "categorize/vendorpayments",
            data=dict(data),
        )

    def categorize_as_customer_payment(
        self,
        transaction_id: str,
        data: Mapping[str, object],
    ) -> object:
        return self._action(
            "POST",
            f"uncategorized/{transaction_id}",
            "categorize/customerpayments",
            data=dict(data),
        )

    def unmatch(self, transaction_id: str, account_id: str) -> object:
        if not account_id:
            raise ValueError("account_id is required.")
        return self._action(
            "POST",
            transaction_id,
            "unmatch",
            params={"account_id": account_id},
        )


class Journals(BaseResource):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "journals")

    def publish(self, journal_id: str) -> object:
        return self._action("POST", journal_id, "status/publish")
