"""Runtime boundaries and compiler contracts for the strict migration slice."""

from datetime import date
from importlib.util import find_spec
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest

from workflows.payment_renumbering import (
    RenumberingError, build_renumber_plan, execute_renumbering,
    get_target_payments, parse_renumber_plan, parse_renumber_results,
)
from workflows.collection_reconciliation.allocator import allocate_invoices_oldest_due_first
from workflows.core.exceptions import ReconciliationError
from zoho.validation import require_record, require_records, require_text


def setup_payment():
    payment = {
        "payment_id": "p", "payment_number": "OLD-001", "date": "2025-04-01",
        "amount": "100.00", "account_id": "bank", "customer_id": "customer",
        "location_id": "location", "invoices": [{"invoice_id": "i", "amount_applied": 100}],
    }
    books = Mock()
    books.customer_payments.get.return_value = {"payment": payment}
    books.customer_payments.list_all.return_value = []
    discovery = [{"Payment ID": "p", "Payment Number": "OLD-001", "Payment Date": "2025-04-01"}]
    return books, payment, discovery


def plan_for(books, discovery):
    return build_renumber_plan(
        books, discovery, source_prefix="OLD-", destination_prefix="NEW-",
        start_date=date(2025, 4, 1), end_date=date(2026, 3, 31),
    )


@pytest.mark.parametrize("field,value", [
    ("customer_id", None), ("location_id", []), ("account_id", True),
    ("payment_id", {"id": "p"}), ("payment_number", 12),
    ("date", "not-a-date"), ("amount", "NaN"), ("amount", "Infinity"),
    ("amount", True), ("invoices", {}), ("invoices", [None]),
    ("invoices", [{"invoice_id": "i", "amount_applied": "NaN"}]),
    ("invoices", [{"invoice_id": [], "amount_applied": 100}]),
    ("invoices", [{"invoice_id": "i", "amount_applied": 100, "date": "bad"}]),
])
def test_invalid_live_financial_records_fail_before_writes(field, value):
    books, payment, discovery = setup_payment()
    payment[field] = value
    with pytest.raises(RenumberingError):
        plan_for(books, discovery)
    books.customer_payments.update_with_number_series.assert_not_called()


@pytest.mark.parametrize("response", [None, [], {"payment": []}, {"code": False, "payment": {"payment_id": "p"}}])
def test_invalid_payment_envelope(response):
    books, _, discovery = setup_payment()
    books.customer_payments.get.return_value = response
    with pytest.raises(RenumberingError):
        plan_for(books, discovery)


@pytest.mark.parametrize("response", [None, {}, [None], [{"Payment ID": "p"}]])
def test_discovery_boundary_rejects_malformed_rows(response):
    analytics = Mock()
    analytics.queries.execute.return_value = response
    with pytest.raises(RenumberingError):
        get_target_payments(analytics, "workspace")


def test_discovery_boundary_accepts_empty_and_extra_vendor_fields():
    analytics = Mock()
    analytics.queries.execute.return_value = []
    assert get_target_payments(analytics, "workspace") == []
    _, _, discovery = setup_payment()
    analytics.queries.execute.return_value = [{**discovery[0], "unused": {}}]
    assert get_target_payments(analytics, "workspace") == discovery


def test_schema_one_plan_and_results_roundtrip():
    books, _, discovery = setup_payment()
    plan = plan_for(books, discovery)
    assert parse_renumber_plan(json.loads(json.dumps(plan))) == plan
    results = execute_renumbering(books, plan)
    assert parse_renumber_results(json.loads(json.dumps(results))) == results


@pytest.mark.parametrize("field,value", [("payment_id", []), ("prefix", None), ("expected", {}), ("suffix", 1)])
def test_invalid_saved_plan_is_rejected_before_remote_calls(field, value):
    books, _, discovery = setup_payment()
    plan = plan_for(books, discovery)
    plan[0][field] = value
    books.reset_mock()
    with pytest.raises(RenumberingError):
        execute_renumbering(books, plan, execute=True, checkpoint=Mock())
    assert not books.mock_calls


@pytest.mark.parametrize("change", [
    {"status": "success"}, {"payment_id": []}, {"updated_at": "yesterday"}, {"error": {}},
])
def test_invalid_saved_results_rejected_before_remote_calls(change):
    books, _, discovery = setup_payment()
    plan = plan_for(books, discovery)
    previous = [{"payment_id": "p", "status": "submitted", "updated_at": None, "error": None, **change}]
    books.reset_mock()
    with pytest.raises(RenumberingError):
        execute_renumbering(books, plan, previous_results=previous, execute=True, checkpoint=Mock())
    assert not books.mock_calls


def test_cli_invalid_resume_preserves_existing_recovery_file(monkeypatch, tmp_path):
    from apps import renumber_sbe2627_payments as app
    audit_file = tmp_path / "audit.json"
    original = json.dumps({"schema_version": 1, "plan": [{}], "results": []})
    audit_file.write_text(original, encoding="utf-8")
    factory = Mock()
    monkeypatch.setattr(app, "get_books_client", factory)
    with pytest.raises(RenumberingError):
        app.main(["--resume", str(audit_file), "--execute"])
    assert audit_file.read_text(encoding="utf-8") == original
    factory.assert_not_called()


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-Infinity", None, 0])
def test_collection_allocator_rejects_invalid_payment_amounts(amount):
    with pytest.raises(ReconciliationError):
        allocate_invoices_oldest_due_first(amount, [])


@pytest.mark.parametrize("balance", ["NaN", "Infinity", None, "broken"])
def test_collection_allocator_rejects_invalid_balance_instead_of_skipping(balance):
    with pytest.raises(ReconciliationError, match="balance"):
        allocate_invoices_oldest_due_first(100, [{"invoice_id": "i", "balance": balance}])


def test_collection_allocator_preserves_existing_wire_metadata():
    allocations, remaining = allocate_invoices_oldest_due_first(100, [
        {"invoice_id": "i", "balance": "120", "invoice_number": "INV-1", "date": "2026-01-01", "due_date": "2026-01-10"},
    ])
    assert remaining == 0
    assert allocations == [{"invoice_id": "i", "amount_applied": 100.0, "balance": 120.0,
                            "invoice_number": "INV-1", "date": "2026-01-01", "due_date": "2026-01-10"}]


@pytest.mark.parametrize("value", [None, [], "text", {1: "nonstring key"}])
def test_record_validation_rejects_invalid_shapes(value):
    with pytest.raises(ValueError):
        require_record(value, "Test record")


def test_record_validation_preserves_extra_fields_and_empty_lists():
    assert require_records([], "Rows") == []
    assert require_record({"unused": [1, 2]}, "Record") == {"unused": [1, 2]}
    assert require_text("", "Optional text", allow_empty=True) == ""
    with pytest.raises(ValueError):
        require_text("", "Required text")


@pytest.mark.parametrize("field,value", [("locations", {}), ("locations", [None]), ("item_tax_preferences", [None])])
def test_stock_transfer_rejects_malformed_nested_records(field, value):
    from workflows.stock_transfer import build_plan
    from tests.test_stock_transfer import item
    data = item()
    data[field] = value
    with pytest.raises(ValueError):
        build_plan([data], "source", "destination", ["p"])


def test_checker_accepts_real_sdk_and_rejects_wrong_domain_types(tmp_path):
    if find_spec("mypy") is None:
        pytest.skip("Install the authorized typing extra to run checker contracts")
    from mypy import api
    root = Path(__file__).resolve().parents[1]
    cache_arg = f"--cache-dir={tmp_path / 'mypy'}"
    out, err, code = api.run([cache_arg, "tests/typecheck/renumber_contracts.py"])
    assert code == 0, out + err
    rejected_file = tmp_path / "rejected_contract.py"
    rejected_file.write_text((root / "tests/typecheck/renumber_rejected.txt").read_text(encoding="utf-8"), encoding="utf-8")
    out, err, code = api.run([cache_arg, str(rejected_file)])
    assert code == 1, out + err
    assert out.count("[arg-type]") == 1, out
    assert out.count("[typeddict-item]") == 1, out
    assert out.count("[assignment]") == 1, out
    assert out.count("error:") == 3, out
