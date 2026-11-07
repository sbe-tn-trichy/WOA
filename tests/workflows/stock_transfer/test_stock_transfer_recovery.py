"""Recovery works from recorded IDs and stops on uncertain writes."""
from copy import deepcopy
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from workflows.stock_transfer import TransferRecoveryPolicy, recover_stock_transfer


@pytest.fixture
def recovery(tmp_path):
    policy = TransferRecoveryPolicy("REF", 2, Decimal("100"), "source", "destination", "c", "v", ("purchase",))
    invoices, bills = {}, {}
    rows = []
    for n in (1, 2):
        common = dict(reference_number=f"REF-{n:03d}", date="2026-11-01", total=50, status="draft")
        invoice = dict(common, invoice_id=f"i{n}", invoice_number=f"INV-{n}", customer_id="c", location_id="source",
                       line_items=[dict(item_id="1", quantity=2, rate=25, tax_id="", location_id="source")])
        bill = dict(common, bill_id=f"b{n}", bill_number=f"INV-{n}", vendor_id="v", location_id="destination",
                    line_items=[dict(item_id="1", quantity=2, rate=25, tax_id="", location_id="destination")])
        invoices[f"i{n}"] = invoice
        bills[f"b{n}"] = bill
        rows.append(dict(invoice_id=f"i{n}", bill_id=f"b{n}", invoice_number=f"INV-{n}", total=50, date="2026-11-01"))
    state = dict(reference="REF", stage="bill_aligned", completed=[rows[0]], invoice=invoices["i2"], bill=bills["b2"])
    journal = tmp_path / "execution.json"
    journal.write_text(json.dumps(state))
    books = SimpleNamespace(invoices=MagicMock(), bills=MagicMock())
    books.invoices.get.side_effect = lambda key: {"invoice": deepcopy(invoices[key])}
    books.bills.get.side_effect = lambda key: {"bill": deepcopy(bills[key])}
    def post_invoice(key):
        assert json.loads(journal.read_text())["stage"] == "recovery_posting_invoice"
        invoices[key]["status"] = "sent"
    def post_bill(key):
        assert json.loads(journal.read_text())["stage"] == "recovery_posting_bill"
        bills[key]["status"] = "open"
    books.invoices.mark_as_sent.side_effect = post_invoice
    books.bills.mark_as_open.side_effect = post_bill
    stock = dict(location_stock_on_hand=20, location_available_stock=20, location_actual_available_stock=20,
                 location_available_for_sale_stock=20, location_actual_available_for_sale_stock=20)
    item = dict(item_id="1", purchase_account_id="purchase", locations=[dict(stock, location_id="source"), dict(stock, location_id="destination")])
    inventory = SimpleNamespace(items=MagicMock())
    inventory.items.get_details.side_effect = lambda ids: [deepcopy(item)]
    return books, inventory, journal, policy, invoices, bills, item


def test_preview_reads_but_never_changes_journal_or_remote(recovery):
    books, inventory, journal, policy, *_ = recovery
    before = journal.read_bytes()
    result = recover_stock_transfer(books, inventory, journal=journal, policy=policy)
    assert result.pairs == 2 and not result.applied
    assert journal.read_bytes() == before
    books.invoices.mark_as_sent.assert_not_called()
    books.bills.mark_as_open.assert_not_called()


def test_apply_posts_existing_pairs_and_verifies(recovery):
    books, inventory, journal, policy, *_ = recovery
    result = recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    assert result.applied and result.pairs == 2
    assert books.invoices.mark_as_sent.call_count == 2
    assert books.bills.mark_as_open.call_count == 2
    books.invoices.create.assert_not_called()
    books.bills.create.assert_not_called()
    assert json.loads(journal.read_text())["stage"] == "complete"
    with pytest.raises(ValueError, match="bill_aligned"):
        recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)


def test_existing_open_bills_not_reposted(recovery):
    books, inventory, journal, policy, _, bills, _ = recovery
    bills["b1"]["status"] = "open"
    recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    books.bills.mark_as_open.assert_called_once_with("b2")


@pytest.mark.parametrize("problem", ["scope", "reference", "amount", "nan", "quantity", "tax", "number", "identity", "status", "line_location", "purchase", "stock", "incomplete", "duplicate", "stage", "count"])
def test_preflight_refuses_changed_or_invalid_records(recovery, problem):
    books, inventory, journal, policy, invoices, bills, item = recovery
    if problem == "scope": invoices["i1"]["customer_id"] = "wrong"
    elif problem == "reference": bills["b1"]["reference_number"] = "wrong"
    elif problem == "amount": bills["b1"]["total"] = 49
    elif problem == "nan": invoices["i1"]["total"] = "NaN"
    elif problem == "quantity": bills["b1"]["line_items"][0]["quantity"] = 1
    elif problem == "tax": bills["b1"]["line_items"][0]["tax_id"] = "wrong"
    elif problem == "number": invoices["i1"]["invoice_number"] = "wrong"
    elif problem == "identity": invoices["i1"]["invoice_id"] = "wrong"
    elif problem == "status": invoices["i1"]["status"] = "sent"
    elif problem == "line_location": bills["b1"]["line_items"][0]["location_id"] = "wrong"
    elif problem == "purchase": item["purchase_account_id"] = "wrong"
    elif problem == "stock": item["locations"][0]["location_available_for_sale_stock"] = 3
    elif problem == "incomplete": inventory.items.get_details.side_effect = lambda ids: []
    else:
        state = json.loads(journal.read_text())
        if problem == "duplicate": state["completed"][0]["invoice_id"] = "i2"
        elif problem == "stage": state["stage"] = "posting"
        else: state["completed"] = []
        journal.write_text(json.dumps(state))
    before = journal.read_bytes()
    with pytest.raises((ValueError, KeyError)):
        recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    assert journal.read_bytes() == before
    books.invoices.mark_as_sent.assert_not_called()
    books.bills.mark_as_open.assert_not_called()


def test_lost_response_persists_intent_and_blocks_retry(recovery):
    books, inventory, journal, policy, invoices, *_ = recovery
    def uncertain(key):
        invoices[key]["status"] = "sent"
        raise TimeoutError("response lost")
    books.invoices.mark_as_sent.side_effect = uncertain
    with pytest.raises(TimeoutError):
        recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    assert json.loads(journal.read_text())["stage"] == "recovery_posting_invoice"
    books.bills.mark_as_open.assert_not_called()
    with pytest.raises(ValueError, match="bill_aligned"):
        recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    assert books.invoices.mark_as_sent.call_count == 1


def test_readback_failure_stops_before_bill_and_next_pair(recovery):
    books, inventory, journal, policy, *_ = recovery
    books.invoices.mark_as_sent.side_effect = None
    with pytest.raises(ValueError, match="invoice status"):
        recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    assert json.loads(journal.read_text())["stage"] == "recovery_posting_invoice"
    books.bills.mark_as_open.assert_not_called()
    assert books.invoices.mark_as_sent.call_count == 1


def test_bin_recovery_checks_aggregate_and_current_allocations(recovery, monkeypatch):
    books, inventory, journal, policy, invoices, _, item = recovery
    monkeypatch.setattr("workflows.stock_transfer.recovery.time.sleep", lambda seconds: None)
    for invoice in invoices.values():
        invoice["line_items"][0]["storages"] = [{"storage_id": "bin", "out_quantity": 2}]
    item["locations"][0]["is_storage_location_enabled"] = True
    inventory.items.list_bins.return_value = [{"storage_id": "bin", "location_id": "source", "status": 1, "balance_quantity": 10}]
    recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    assert inventory.items.list_bins.call_count == 3


def test_bin_recovery_rejects_insufficient_aggregate(recovery, monkeypatch):
    books, inventory, journal, policy, invoices, _, item = recovery
    monkeypatch.setattr("workflows.stock_transfer.recovery.time.sleep", lambda seconds: None)
    for invoice in invoices.values():
        invoice["line_items"][0]["storages"] = [{"storage_id": "bin", "out_quantity": 2}]
    item["locations"][0]["is_storage_location_enabled"] = True
    inventory.items.list_bins.return_value = [{"storage_id": "bin", "location_id": "source", "status": 1, "balance_quantity": 3}]
    with pytest.raises(ValueError, match="Bin stock changed"):
        recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    books.invoices.mark_as_sent.assert_not_called()


def test_final_stock_readback_failure_leaves_incomplete_journal(recovery):
    books, inventory, journal, policy, _, _, item = recovery
    calls = 0
    def details(ids):
        nonlocal calls
        calls += 1
        if calls == 4:
            item["locations"][0]["location_stock_on_hand"] = -1
        return [deepcopy(item)]
    inventory.items.get_details.side_effect = details
    with pytest.raises(ValueError, match="Negative source stock"):
        recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    assert json.loads(journal.read_text())["stage"] == "recovery_pair_verified"


def test_journal_changed_during_preflight_is_not_overwritten(recovery):
    books, inventory, journal, policy, _, _, item = recovery
    def change_journal(ids):
        journal.write_text('{"stage": "external change"}')
        return [deepcopy(item)]
    inventory.items.get_details.side_effect = change_journal
    with pytest.raises(ValueError, match="Journal changed"):
        recover_stock_transfer(books, inventory, journal=journal, policy=policy, apply=True)
    assert json.loads(journal.read_text())["stage"] == "external change"
    books.invoices.mark_as_sent.assert_not_called()


def recovery_args():
    return ["--journal", "unused.json", "--reference", "REF", "--expected-pairs", "2",
            "--maximum-invoice-total", "100", "--source", "source", "--destination", "destination",
            "--customer-id", "c", "--vendor-id", "v", "--purchase-account-id", "purchase"]


def test_recovery_cli_defaults_to_preview(monkeypatch):
    from apps import recover_stock_transfer as app
    from workflows.stock_transfer import TransferRecoveryResult
    monkeypatch.setattr(app, "get_books_client", MagicMock())
    monkeypatch.setattr(app, "get_inventory_client", MagicMock())
    recover = MagicMock(return_value=TransferRecoveryResult("REF", 2, False))
    monkeypatch.setattr(app, "recover_stock_transfer", recover)
    assert app.main(recovery_args()) == 0
    assert recover.call_args.kwargs["apply"] is False


def test_invalid_recovery_policy_stops_before_client_creation(monkeypatch):
    from apps import recover_stock_transfer as app
    factory = MagicMock(side_effect=AssertionError("Should not create client"))
    monkeypatch.setattr(app, "get_books_client", factory)
    args = recovery_args()
    args[args.index("--maximum-invoice-total") + 1] = "NaN"
    assert app.main(args) == 1
    factory.assert_not_called()
