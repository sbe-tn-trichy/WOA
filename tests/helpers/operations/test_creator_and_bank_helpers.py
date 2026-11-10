"""Unit tests for Creator checkpoint and Books bank transaction helpers."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from helpers import (
    categorize_bank_transaction,
    fetch_uncategorized_bank_transactions,
    find_bank_match_candidate,
    get_uncategorized_bank_transaction,
    match_bank_transaction,
    require_creator_success,
    update_and_verify_creator_record,
)


def test_require_creator_success_accepts_zero_and_3000() -> None:
    require_creator_success({"code": 3000, "data": {"ID": "1"}})
    require_creator_success({"data": [{"code": "0"}]})


def test_require_creator_success_rejects_invalid_or_error_code() -> None:
    with pytest.raises(ValueError, match="invalid update response"):
        require_creator_success("bad")
    with pytest.raises(ValueError, match="code=2945"):
        require_creator_success({"data": {"code": 2945, "message": "Denied"}})


def test_update_and_verify_creator_record_reads_back_fields() -> None:
    calls: list[str] = []

    class CreatorStub:
        def update_records(self, app, report, payload, *, record_id=None):
            calls.append(f"update:{record_id}")
            return {"code": 3000, "data": {"ID": record_id}}

        def get_records(self, app, report, *, params=None):
            calls.append("get")
            return {"data": [{"ID": "r1", "Books_ID": "b1", "PaymentNo": "CP-1"}]}

    record = update_and_verify_creator_record(
        CreatorStub(),
        "app",
        "All_Payments",
        "r1",
        {"Books_ID": "b1", "PaymentNo": "CP-1"},
    )
    assert record["ID"] == "r1"
    assert calls == ["update:r1", "get"]


def test_update_and_verify_creator_record_fails_on_mismatch() -> None:
    class CreatorMismatch:
        def update_records(self, app, report, payload, *, record_id=None):
            return {"code": 3000}

        def get_records(self, app, report, *, params=None):
            return {"data": [{"ID": "r1", "Books_ID": "wrong"}]}

    with pytest.raises(ValueError, match="Books_ID"):
        update_and_verify_creator_record(CreatorMismatch(), "app", "rep", "r1", {"Books_ID": "b1"})


def test_bank_transaction_fetch_get_match_and_categorize() -> None:
    matched_calls: list[tuple[str, list[dict[str, object]]]] = []
    cat_calls: list[tuple[str, str, dict[str, object]]] = []

    class BankTxResource:
        def list_all(self, params=None):
            acc = (params or {}).get("account_id")
            if acc == "a1":
                return [{"transaction_id": "t1", "amount": "100"}]
            return [{"id": "t2", "amount": "200"}]

        def get_matches(self, bank_id):
            return {"matching_transactions": [{"transaction_id": "app1", "transaction_type": "customer_payment"}]}

        def match(self, bank_id, payload):
            matched_calls.append((bank_id, payload))
            return {"code": 0}

        def categorize_as_expense(self, tx_id, payload):
            cat_calls.append(("expense", tx_id, payload))
            return {"code": 0}

        def categorize(self, tx_id, payload):
            cat_calls.append(("transfer", tx_id, payload))
            return {"code": 1}

        def categorize_as_vendor_payment(self, tx_id, payload):
            cat_calls.append(("vendor", tx_id, payload))
            return {"code": 0}

    books = SimpleNamespace(bank_transactions=BankTxResource())

    rows = fetch_uncategorized_bank_transactions(
        books, [("HDFC", "a1"), ("ICICI", "a2")], name_key="_name", account_key="_acct",
    )
    assert len(rows) == 2
    assert rows[0]["_name"] == "HDFC" and rows[1]["_acct"] == "a2"

    assert get_uncategorized_bank_transaction(books, "t1", "a1") is not None
    assert get_uncategorized_bank_transaction(books, "missing", "a1") is None

    cand = find_bank_match_candidate(books, "t1", "p1", fallback_ids=["app1"])
    assert cand is not None
    match_bank_transaction(books, "t1", cand)
    assert matched_calls == [("t1", [{"transaction_id": "app1", "transaction_type": "customer_payment"}])]

    assert categorize_bank_transaction(books, "t1", kind="expense", payload={"amount": 100})["code"] == 0
    with pytest.raises(ValueError, match="rejected"):
        categorize_bank_transaction(books, "t1", kind="transfer_fund", payload={"amount": 100})
