"""Unit tests for COA, location, vendor resolvers and Analytics query helpers."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from helpers import (
    AmbiguousMatchError,
    build_batched_like_queries,
    query_or_export_analytics_rows,
    resolve_chart_of_account,
    resolve_location_by_name,
    resolve_vendor_by_name,
)


def test_resolve_chart_of_account_by_id_and_name() -> None:
    class CoaResource:
        def get(self, identifier):
            return {"chart_of_account": {"account_id": identifier, "account_name": "Cash-SBE", "account_type": "cash", "is_active": True}}

        def list_all(self):
            return [
                {"account_id": "e1", "account_name": "Electricity", "account_type": "expense", "is_active": True},
                {"account_id": "e2", "account_name": "Electricity", "account_type": "expense", "is_active": False},
            ]

    books = SimpleNamespace(chart_of_accounts=CoaResource(), locations=SimpleNamespace(list_all=lambda: []))
    by_id = resolve_chart_of_account(books, account_id="c1", account_types={"cash"})
    assert by_id is not None and by_id["account_id"] == "c1"

    by_name = resolve_chart_of_account(books, account_name="electricity", account_types={"expense", "other_expense"})
    assert by_name is not None and by_name["account_id"] == "e1"


def test_resolve_location_and_vendor_by_name() -> None:
    books = SimpleNamespace(
        chart_of_accounts=SimpleNamespace(get=lambda _: {}, list_all=lambda: []),
        locations=SimpleNamespace(list_all=lambda: [
            {"location_id": "loc1", "location_name": "Main Branch", "is_active": True, "status": "active"},
            {"location_id": "loc2", "location_name": "Main Branch", "is_active": False, "status": "inactive"},
        ]),
        contacts=SimpleNamespace(list_all=lambda params=None, resource_key=None: [
            {"contact_id": "v1", "contact_name": "Polycab India Limited", "contact_type": "vendor", "status": "active"},
            {"contact_id": "v2", "contact_name": "Polycab", "contact_type": "vendor", "status": "active"},
        ]),
    )
    loc = resolve_location_by_name(books, "main branch")
    assert loc is not None and loc["location_id"] == "loc1"

    with pytest.raises(AmbiguousMatchError):
        resolve_vendor_by_name(books, "Polycab", aliases=("Polycab India Limited",))


def test_batched_like_queries_and_export_fallback() -> None:
    sqls = build_batched_like_queries(
        "Payment Customer Finder",
        ("Customer Name", "Description"),
        "Description",
        ["TOK1", "TOK'2", "TOK3"],
        where_prefix='"Customer Name" IS NOT NULL',
        max_tokens_per_query=2,
    )
    assert len(sqls) == 2
    assert "TOK''2" in sqls[0]

    with pytest.raises(ValueError, match="SQL budget"):
        build_batched_like_queries("T", ("A",), "A", ["X" * 300], max_sql_bytes=256)

    analytics = SimpleNamespace(
        queries=SimpleNamespace(execute=lambda ws, sql: (_ for _ in ()).throw(RuntimeError("down"))),
        views=SimpleNamespace(export_all=lambda ws, vid, max_attempts=60: [{"Customer Name": "Acme"}]),
    )
    rows, exported = query_or_export_analytics_rows(
        analytics, "ws1", queries=sqls, fallback_view_id="v1",
    )
    assert exported is True and rows == [{"Customer Name": "Acme"}]
