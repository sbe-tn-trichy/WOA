"""Read Zoho Books account registers as detailed general-ledger entries."""

from __future__ import annotations

import builtins
from collections.abc import Iterator, Mapping, Sequence
from datetime import date

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.core_sdk.base_resource import BaseResource
from zoho.core_sdk.validation import require_record, require_records


class Registers:
    """Read the documented account-register report for one ledger account."""

    def __init__(self, client: BaseZohoClient) -> None:
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
    ) -> Mapping[str, object]:
        """Return one raw page from ``GET /registers/{account_id}/transactions``."""
        return self.list_transactions_for_accounts(
            [account_id],
            from_date=from_date,
            to_date=to_date,
            page=page,
            per_page=per_page,
            cash_based=cash_based,
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
    ) -> Mapping[str, object]:
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
            raise ValueError(
                "Books account register response is missing register_transactions"
            )
        return response

    def iter_transactions(
        self,
        account_id: str,
        *,
        from_date: str,
        to_date: str,
        per_page: int = 200,
        cash_based: bool = False,
    ) -> Iterator[Mapping[str, object]]:
        """Yield detailed transaction rows across all account-register pages."""
        yield from self.iter_transactions_for_accounts(
            [account_id],
            from_date=from_date,
            to_date=to_date,
            per_page=per_page,
            cash_based=cash_based,
        )

    def iter_transactions_for_accounts(
        self,
        account_ids: Sequence[str],
        *,
        from_date: str,
        to_date: str,
        per_page: int = 200,
        cash_based: bool = False,
    ) -> Iterator[Mapping[str, object]]:
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
            raw_reg = response["register_transactions"]
            register = raw_reg if isinstance(raw_reg, Mapping) else {}

            def walk(nodes: object) -> Iterator[Mapping[str, object]]:
                if not isinstance(nodes, list):
                    raise ValueError(
                        "Books account register has invalid account_transactions"
                    )
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
                raise ValueError(
                    "Books account register response is missing page_context"
                )
            if not context.get("has_more_page"):
                return
            page += 1


class FixedAssets(BaseResource):
    def __init__(self, client: BaseZohoClient) -> None:
        super().__init__(client, "fixedassets")

    def list(
        self, params: Mapping[str, object] | None = None
    ) -> dict[str, object]:
        result = require_record(
            super().list(dict(params) if params else None), "FixedAssets.list"
        )
        if result.get("code") != 0 or not isinstance(result.get("fixedassets"), list):
            raise ValueError("Invalid fixed asset list response")
        page_ctx = result.get("page_context")
        has_more = isinstance(page_ctx, Mapping) and bool(
            page_ctx.get("has_more_page", False)
        )
        if not result["fixedassets"] and has_more:
            raise ValueError("Empty fixed asset list page claims more pages")
        return result

    def history(self, fixed_asset_id: str) -> builtins.list[dict[str, object]]:
        """Return every history page; reject incomplete or duplicated valuations."""
        if not fixed_asset_id or "/" in fixed_asset_id:
            raise ValueError("A fixed asset ID is required")
        rows: builtins.list[dict[str, object]] = []
        seen: set[str] = set()
        page = 1
        while True:
            response = require_record(
                self.client.request(
                    "GET",
                    f"fixedassets/{fixed_asset_id}/history",
                    params={"page": page, "per_page": 200},
                ),
                "fixedassets/history",
            )
            raw_entries = response.get("asset_history")
            if response.get("code") != 0 or not isinstance(raw_entries, list):
                raise ValueError("Invalid fixed asset history response")
            entries = require_records(raw_entries, "asset_history")
            for entry in entries:
                identity = str(entry.get("valuation_id") or "")
                if not identity or identity in seen:
                    raise ValueError("Missing or repeated fixed asset valuation ID")
                seen.add(identity)
                rows.append(entry)
            page_ctx = response.get("page_context")
            has_more = isinstance(page_ctx, Mapping) and bool(
                page_ctx.get("has_more_page", False)
            )
            if not has_more:
                return rows
            if not entries:
                raise ValueError("Empty fixed asset history page claims more pages")
            page += 1
