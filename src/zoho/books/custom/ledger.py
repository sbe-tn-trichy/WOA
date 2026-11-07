"""Read Zoho Books account registers as detailed general-ledger entries."""

from __future__ import annotations

from datetime import date
from collections.abc import Iterator, Mapping, Sequence
from typing import Any
from zoho.base_resource import BaseResource


class Registers:
    """Read the documented account-register report for one ledger account."""

    def __init__(self, client: Any) -> None:
        self.client = client

    def list_transactions(
        self,
        account_id: str,
        *,
        from_date: str,
        to_date: str,
        page: int = 1,
        per_page: int = 200,
        cash_based: bool = False,
    ) -> Mapping[str, Any]:
        """Return one raw page from ``GET /registers/{account_id}/transactions``."""
        return self.list_transactions_for_accounts(
            [account_id], from_date=from_date, to_date=to_date, page=page,
            per_page=per_page, cash_based=cash_based,
        )

    def list_transactions_for_accounts(
        self,
        account_ids: Sequence[str],
        *,
        from_date: str,
        to_date: str,
        page: int = 1,
        per_page: int = 200,
        cash_based: bool = False,
    ) -> Mapping[str, Any]:
        """Return one register page filtered to up to 50 account IDs."""
        if isinstance(account_ids, (str, bytes)):
            raise ValueError("account_ids must be a sequence of IDs")
        ids = [str(account_id).strip() for account_id in account_ids]
        if not ids or any(not account_id for account_id in ids):
            raise ValueError("account_id is required")
        if len(ids) > 50 or len(set(ids)) != len(ids):
            raise ValueError("account_ids must be unique and contain at most 50 IDs")
        try:
            start, end = date.fromisoformat(from_date), date.fromisoformat(to_date)
        except (TypeError, ValueError) as exc:
            raise ValueError("from_date and to_date must be ISO dates") from exc
        if start > end:
            raise ValueError("from_date must not be after to_date")
        if page < 1 or per_page < 1:
            raise ValueError("page and per_page must be positive")
        response = self.client.request(
            "GET",
            f"registers/{ids[0]}/transactions",
            params={
                "account_id": ",".join(ids),
                "filter_by": "TransactionDate.CustomDate",
                "from_date": from_date,
                "to_date": to_date,
                "cash_based": str(cash_based).lower(),
                "page": page,
                "per_page": per_page,
            },
        )
        if not isinstance(response, Mapping) or response.get("code") != 0:
            raise ValueError("Books account register request failed")
        if not isinstance(response.get("register_transactions"), Mapping):
            raise ValueError("Books account register response is missing register_transactions")
        return response

    def iter_transactions(
        self,
        account_id: str,
        *,
        from_date: str,
        to_date: str,
        per_page: int = 200,
        cash_based: bool = False,
    ) -> Iterator[Mapping[str, Any]]:
        """Yield detailed transaction rows across all account-register pages."""
        yield from self.iter_transactions_for_accounts(
            [account_id], from_date=from_date, to_date=to_date,
            per_page=per_page, cash_based=cash_based,
        )

    def iter_transactions_for_accounts(
        self,
        account_ids: Sequence[str],
        *,
        from_date: str,
        to_date: str,
        per_page: int = 200,
        cash_based: bool = False,
    ) -> Iterator[Mapping[str, Any]]:
        """Yield detailed rows from one filtered register query across pages."""
        page = 1
        while True:
            response = self.list_transactions_for_accounts(
                account_ids,
                from_date=from_date,
                to_date=to_date,
                page=page,
                per_page=per_page,
                cash_based=cash_based,
            )
            register = response["register_transactions"]

            def walk(nodes: Any) -> Iterator[Mapping[str, Any]]:
                if not isinstance(nodes, list):
                    raise ValueError("Books account register has invalid account_transactions")
                for node in nodes:
                    if not isinstance(node, Mapping):
                        raise ValueError("Books account register has an invalid row")
                    if "account_transactions" in node:
                        yield from walk(node["account_transactions"])
                    elif "transaction_id" in node:
                        yield node

            yield from walk(register.get("account_transactions", []))
            context = response.get("page_context")
            if not isinstance(context, Mapping):
                raise ValueError("Books account register response is missing page_context")
            if not context.get("has_more_page"):
                return
            page += 1


class FixedAssets(BaseResource):
    def __init__(self, client: Any):
        super().__init__(client, "fixedassets")

    def list(self, params: dict[str, Any] | None = None) -> dict[str, Any]:
        result = super().list(params)
        if result.get("code") != 0 or not isinstance(result.get("fixedassets"), list):
            raise ValueError("Invalid fixed asset list response")
        if not result["fixedassets"] and result.get("page_context", {}).get("has_more_page"):
            raise ValueError("Empty fixed asset list page claims more pages")
        return result

    def history(self, fixed_asset_id: str) -> list[dict[str, Any]]:
        """Return every history page; reject incomplete or duplicated valuations."""
        if not fixed_asset_id or "/" in fixed_asset_id:
            raise ValueError("A fixed asset ID is required")
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        page = 1
        while True:
            response = self.client.request("GET", f"fixedassets/{fixed_asset_id}/history",
                                           params={"page": page, "per_page": 200})
            if response.get("code") != 0 or not isinstance(response.get("asset_history"), list):
                raise ValueError("Invalid fixed asset history response")
            entries = response["asset_history"]
            for entry in entries:
                identity = str(entry.get("valuation_id") or "")
                if not identity or identity in seen:
                    raise ValueError("Missing or repeated fixed asset valuation ID")
                seen.add(identity)
                rows.append(entry)
            if not response.get("page_context", {}).get("has_more_page", False):
                return rows
            if not entries:
                raise ValueError("Empty fixed asset history page claims more pages")
            page += 1
