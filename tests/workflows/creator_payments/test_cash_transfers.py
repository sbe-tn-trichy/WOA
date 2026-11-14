"""Offline financial and recovery contracts for explicitly selected cash transfers."""
from copy import deepcopy
from types import SimpleNamespace
from pathlib import Path

import pytest

from utils.file_utils import json
from workflows.creator_payments import CashTransferError, post_cash_transfer
from zoho.creator.exceptions import ZohoCreatorError


class Environment:
    def __init__(self):
        self.creator_rows = {
            "1": {"ID": "1", "Date_field": "14-Oct-2026", "Transfer_Amount": "2500", "Total_Amount": "2500",
                  "From_Account": {"ID": "2"}, "Transfer_Details": [{"To_Account": {"ID": "3"}}],
                  "Payment_Ids": [{"ID": "4"}, {"ID": "5"}], "Books_Transaction_Id": ""},
            "2": {"ID": "2", "Account_ID": "20"}, "3": {"ID": "3", "Account_ID": "30"},
            "6": {"ID": "6", "Customer_Id": "60"}, "7": {"ID": "7", "Customer_Id": "70"},
        }
        for rid, customer, amount, ref in [("4", "6", "1000", "1142"), ("5", "7", "1500", "1143")]:
            self.creator_rows[rid] = {
                "ID": rid, "Payment_ID": rid, "Payment_Amount": amount, "Payment_Date": "14-Oct-2026",
                "Payment_Method": "Cash", "Account": {"ID": "2"}, "Customer_Name": {"ID": customer},
                "Reference": ref, "Cash_Transfer": [{"ID": "1"}], "Cash_Status": "In Hand", "Cash_Balance": amount,
            }
        self.payments = {}
        self.deposits = {}
        self.invoices = {}
        self.writes = []
        self.fail_payment = 0
        self.uncertain_payment = False
        self.fail_creator = False
        self.bad_deposit = False
        self.uncertain_allocation = False
        self.uncertain_deposit_create = False
        self.uncertain_deposit_links = False
        self.books = SimpleNamespace(
            organization_id="99", request=self.books_request,
            contacts=SimpleNamespace(get=lambda cid: {"code": 0, "contact": {"contact_id": cid, "contact_type": "customer"}}),
            bank_accounts=SimpleNamespace(get=lambda aid: {"code": 0, "bankaccount": {
                "account_id": aid, "is_active": True, "currency_code": "INR", "is_undeposited_funds": aid == "20"}}),
            customer_payments=SimpleNamespace(list_all=self.list_payments, get=lambda pid: {"code": 0, "payment": deepcopy(self.payments[pid])}, create=self.create_payment, update=self.update_payment),
            invoices=SimpleNamespace(list_all=lambda **kw: deepcopy([r for r in self.invoices.values() if r["customer_id"] == kw["params"]["customer_id"]]),
                                     get=lambda iid: {"code": 0, "invoice": deepcopy(self.invoices[iid])}),
            bank_transactions=SimpleNamespace(list_all=lambda **kw: [{**deepcopy(d), "account_id": d["to_account_id"]} for d in self.deposits.values()],
                                             get=lambda did: {"code": 0, "banktransaction": deepcopy(self.deposits[did])}, create=self.create_deposit, update=self.update_deposit),
        )
        self.creator = SimpleNamespace(account_owner_name="owner", request=self.creator_request, update_records=self.update_creator)

    def books_request(self, method, endpoint):
        return {"code": 0, "locations": [{"location_id": "90", "is_location_active": True}]}

    def creator_request(self, method, endpoint, **kwargs):
        rid = endpoint.split("/")[-1]
        row = deepcopy(self.creator_rows[rid])
        if rid == "1" and row.get("Status") == "Verified":
            if "/Pending_Cash_Transfers/" in endpoint:
                raise ZohoCreatorError("Not in Pending", error_code=9290)
            row.pop("Transfer_Details", None)
        return {"code": 3000, "data": row}

    def list_payments(self, *, params, resource_key):
        return deepcopy([p for p in self.payments.values() if p["customer_id"] == params["customer_id"]])

    def create_payment(self, payload):
        self.writes.append(("payment", deepcopy(payload)))
        if len(self.payments) + 1 == self.fail_payment:
            raise RuntimeError("payment timeout")
        pid = str(100 + len(self.payments))
        self.payments[pid] = {**deepcopy(payload), "payment_id": pid, "payment_number": f"CP-{pid}",
                              "unused_amount": payload["amount"] - sum(x["amount_applied"] for x in payload["invoices"])}
        for row in payload["invoices"]:
            self.invoices[row["invoice_id"]]["balance"] -= row["amount_applied"]
        if self.uncertain_payment:
            raise RuntimeError("response lost after commit")
        return {"code": 0, "payment": deepcopy(self.payments[pid])}

    def update_payment(self, pid, payload):
        self.writes.append(("allocation", pid))
        for row in self.payments[pid]["invoices"]:
            self.invoices[row["invoice_id"]]["balance"] += row["amount_applied"]
        for row in payload["invoices"]:
            self.invoices[row["invoice_id"]]["balance"] -= row["amount_applied"]
        self.payments[pid]["invoices"] = deepcopy(payload["invoices"])
        self.payments[pid]["unused_amount"] = self.payments[pid]["amount"] - sum(x["amount_applied"] for x in payload["invoices"])
        if self.uncertain_allocation:
            raise RuntimeError("allocation response lost")
        return {"code": 0, "payment": deepcopy(self.payments[pid])}

    def invoice(self, iid, customer, day, balance, due="2026-12-01"):
        self.invoices[iid] = {"invoice_id": iid, "invoice_number": "INV-" + iid, "customer_id": customer,
                              "date": day, "due_date": due, "balance": balance, "status": "sent", "location_id": "90"}

    def create_deposit(self, payload):
        self.writes.append(("deposit", deepcopy(payload)))
        if payload.get("from_account_id") != "20":
            raise RuntimeError("Involved account types are not applicable")
        if payload.get("amount", -1) <= 0:
            raise RuntimeError("Amount value cannot be less than zero")
        # Books adds a header amount to the associated payment lines; supplying
        # both silently double-counts the deposit rather than failing validation.
        amount = sum(r["total"] for r in payload.get("line_items", [])) + payload.get("amount", 0)
        self.deposits["200"] = {**deepcopy(payload), "transaction_id": "200", "amount": amount,
                                "line_items": deepcopy(payload.get("line_items", [])) + [
                                    {"from_account_id": payload["from_account_id"], "total": payload["amount"]}]}
        if self.uncertain_deposit_create:
            raise RuntimeError("deposit create response lost")
        return {"code": 0, "banktransaction": deepcopy(self.deposits["200"])}

    def update_deposit(self, did, payload):
        self.writes.append(("deposit_links", deepcopy(payload)))
        assert "amount" not in payload
        if any(row.get("amount", -1) <= 0 for row in payload["line_items"]):
            raise RuntimeError("Amount value cannot be less than zero")
        self.deposits[did].update(deepcopy(payload))
        self.deposits[did]["amount"] = sum(r["total"] for r in payload["line_items"])
        if self.bad_deposit:
            self.deposits[did]["line_items"][0]["transaction_id"] = "999"
        if self.uncertain_deposit_links:
            raise RuntimeError("deposit association response lost")
        return {"code": 0, "banktransaction": deepcopy(self.deposits[did])}

    def update_creator(self, app, report, *, record_id, payload):
        self.writes.append(("creator", record_id))
        if self.fail_creator:
            return {"code": 3000, "result": [{"code": 3002}]}
        if record_id == "1" and self.creator_rows["1"].get("Status") == "Verified":
            assert report == "Verified"
        self.creator_rows[record_id].update(payload["data"])
        return {"code": 3000}

    def run(self, tmp_path, apply=False):
        return post_cash_transfer(self.books, self.creator, transfer_id="1", app="app", location_id="90",
                                  checkpoint_dir=tmp_path, apply=apply)


def test_preview_then_post_and_rerun_preserves_associations(tmp_path):
    env = Environment()
    assert env.run(tmp_path).status == "PREVIEW"
    assert not env.writes
    result = env.run(tmp_path, apply=True)
    assert result.status == "COMPLETE"
    assert result.payment_ids == ("100", "101")
    assert result.deposit_id == "200"
    assert env.creator_rows["1"]["Status"] == "Verified"
    assert env.creator_rows["4"]["Cash_Balance"] == 0
    assert env.creator_rows["5"]["Books_Transaction_Id"] == "101"
    deposit = env.deposits["200"]
    deposit_payload = next(payload for kind, payload in env.writes if kind == "deposit")
    assert deposit_payload["amount"] == 2500 and deposit_payload["from_account_id"] == "20"
    assert "line_items" not in deposit_payload
    assert all(p["reference_number"] == "" for p in env.payments.values())
    assert [next(f["value"] for f in p["custom_fields"] if f["label"] == "Receipt Number")
            for p in env.payments.values()] == ["1142", "1143"]
    assert deposit["amount"] == 2500
    assert {r["transaction_id"] for r in deposit["line_items"]} == {"100", "101"}
    assert all(p["account_id"] == "20" and p["location_id"] == "90" for p in env.payments.values())
    assert env.run(tmp_path, apply=True).status == "COMPLETE"
    assert len(env.payments) == 2 and len(env.deposits) == 1


@pytest.mark.parametrize("phase", ["create", "links"])
def test_lost_deposit_response_reconciles_same_native_deposit(tmp_path, phase):
    env = Environment()
    setattr(env, "uncertain_deposit_" + phase, True)
    with pytest.raises(RuntimeError, match="response lost"):
        env.run(tmp_path, apply=True)
    assert env.creator_rows["4"]["Cash_Status"] == "In Hand"
    assert env.deposits["200"]["amount"] == 2500
    setattr(env, "uncertain_deposit_" + phase, False)
    assert env.run(tmp_path, apply=True).status == "COMPLETE"
    assert sum(kind == "deposit" for kind, *_ in env.writes) == 1
    assert sum(kind == "deposit_links" for kind, *_ in env.writes) == 1


def test_changed_staged_deposit_is_never_overwritten(tmp_path):
    env = Environment(); env.uncertain_deposit_create = True
    with pytest.raises(RuntimeError):
        env.run(tmp_path, apply=True)
    env.deposits["200"]["line_items"][0]["transaction_id"] = "999"
    before = len(env.writes)
    with pytest.raises(CashTransferError, match="Staged deposit changed"):
        env.run(tmp_path, apply=True)
    assert len(env.writes) == before


def test_existing_cash_receipt_reuses_custom_field_with_unrelated_reference(tmp_path):
    env = Environment()
    env.run(tmp_path, apply=True)
    env.payments["100"]["reference_number"] = "external-reference"
    # Neither Creator IDs nor receipt fields are exposed by this list response.
    env.books.customer_payments.list_all = lambda **kw: [
        {k: p[k] for k in ("customer_id", "payment_id", "amount", "date")}
        for p in env.payments.values() if p["customer_id"] == kw["params"]["customer_id"]]
    env.creator_rows["4"]["Books_Transaction_Id"] = ""
    assert env.run(tmp_path, apply=True).status == "COMPLETE"
    assert len(env.payments) == 2
    assert env.payments["100"]["reference_number"] == "external-reference"


def test_reference_does_not_substitute_for_cash_receipt_number(tmp_path):
    env = Environment()
    env.run(tmp_path, apply=True)
    payment = env.payments["100"]
    payment["custom_fields"] = [f for f in payment["custom_fields"] if f["label"] != "Receipt Number"]
    payment["reference_number"] = "1142"
    before = len(env.writes)
    with pytest.raises(CashTransferError, match="Receipt Number"):
        env.run(tmp_path, apply=True)
    assert len(env.writes) == before


@pytest.mark.parametrize("change", ["amount", "duplicate", "source", "date", "split", "customer", "discount"])
def test_invalid_plan_never_posts(tmp_path, change):
    env = Environment()
    if change == "amount": env.creator_rows["1"]["Transfer_Amount"] = "3650"
    if change == "duplicate": env.creator_rows["1"]["Payment_Ids"].append({"ID": "4"})
    if change == "source": env.creator_rows["4"]["Account"] = {"ID": "3"}
    if change == "date": env.creator_rows["4"]["Payment_Date"] = "15-Oct-2026"
    if change == "split": env.creator_rows["1"]["Transfer_Details"].append({"To_Account": {"ID": "3"}})
    if change == "customer": env.creator_rows["6"]["Customer_Id"] = ""
    if change == "discount": env.creator_rows["4"]["Is_Discount_Applicable"] = ["Yes"]
    with pytest.raises(CashTransferError): env.run(tmp_path, apply=True)
    assert not env.writes


def test_partial_payment_failure_persists_unknown_and_never_deposits(tmp_path):
    env = Environment(); env.fail_payment = 2
    with pytest.raises(RuntimeError, match="timeout"): env.run(tmp_path, apply=True)
    state = json.loads((tmp_path / "transfer_1.json").read_text())
    assert state["status"] == "FAILED"
    assert state["operations"]["4"]["id"] == "100"
    assert state["operations"]["5"]["status"] == "UNKNOWN"
    assert not env.deposits
    with pytest.raises(CashTransferError, match="Uncertain payment"): env.run(tmp_path, apply=True)
    assert len(env.payments) == 1


def test_lost_payment_response_reconciles_native_marker_without_duplicate(tmp_path):
    env = Environment(); env.uncertain_payment = True
    with pytest.raises(RuntimeError, match="lost"): env.run(tmp_path, apply=True)
    env.uncertain_payment = False
    assert env.run(tmp_path, apply=True).status == "COMPLETE"
    assert len(env.payments) == 2
    state = json.loads((tmp_path / "transfer_1.json").read_text())
    assert state["operations"]["4"]["status"] == "VERIFIED"
    assert state["operations"]["4"]["id"] == "100"


def test_partial_cash_balance_is_not_posted_as_a_full_transfer(tmp_path):
    env = Environment(); env.creator_rows["4"]["Cash_Balance"] = "500"
    with pytest.raises(CashTransferError, match="partially transferred"): env.run(tmp_path, apply=True)
    assert not env.writes


def test_verified_transfer_without_checkpoint_cannot_guess_hidden_destination(tmp_path):
    env = Environment(); env.run(tmp_path, apply=True)
    with pytest.raises(CashTransferError, match="destination"):
        env.run(tmp_path / "missing_checkpoint", apply=True)


def test_creator_rejection_stops_before_deposit(tmp_path):
    env = Environment(); env.fail_creator = True
    with pytest.raises(CashTransferError, match="Creator rejected"): env.run(tmp_path, apply=True)
    assert not env.deposits and len(env.payments) == 1


def test_deposit_readback_rejects_wrong_payment_association(tmp_path):
    env = Environment(); env.bad_deposit = True
    with pytest.raises(CashTransferError, match="association"): env.run(tmp_path, apply=True)
    assert env.creator_rows["1"]["Books_Transaction_Id"] == ""
    assert env.creator_rows["4"]["Cash_Status"] == "In Hand"


def test_scope_change_cannot_reuse_checkpoint(tmp_path):
    env = Environment(); env.run(tmp_path)
    env.books.organization_id = "98"
    with pytest.raises(CashTransferError, match="scope/plan changed"): env.run(tmp_path, apply=True)
    assert not env.writes


def test_existing_deposit_requires_complete_payment_links_before_writes(tmp_path):
    env = Environment(); env.creator_rows["1"]["Books_Transaction_Id"] = "200"
    with pytest.raises(CashTransferError, match="links are incomplete"): env.run(tmp_path, apply=True)
    assert not env.writes


def test_exclusive_lock_blocks_overlapping_financial_runs(tmp_path):
    (tmp_path / "cash_posting.lock").touch()
    with pytest.raises(CashTransferError, match="lock exists"): Environment().run(tmp_path, apply=True)


def test_creation_allocates_by_invoice_date_before_due_date(tmp_path):
    env = Environment()
    env.invoice("801", "60", "2026-08-01", 400, due="2026-12-01")
    env.invoice("802", "60", "2026-09-01", 2000, due="2026-09-02")
    env.invoice("803", "70", "2026-07-01", 2000)
    result = env.run(tmp_path, apply=True)
    assert env.payments["100"]["invoices"] == [
        {"invoice_id": "801", "amount_applied": 400}, {"invoice_id": "802", "amount_applied": 600}]
    assert env.payments["101"]["invoices"] == [{"invoice_id": "803", "amount_applied": 1500}]
    assert all(float(value) == 0 for value in result.unused_amounts.values())


def test_existing_deposited_payments_gain_applications_without_reposting(tmp_path):
    env = Environment(); env.run(tmp_path, apply=True)
    original_deposit = deepcopy(env.deposits)
    env.invoice("801", "60", "2026-08-01", 2000)
    env.invoice("802", "70", "2026-07-01", 2000)
    result = env.run(tmp_path, apply=True)
    assert result.status == "COMPLETE" and env.deposits == original_deposit
    assert env.payments["100"]["unused_amount"] == 0
    assert env.payments["101"]["unused_amount"] == 0
    assert len(env.payments) == 2
    updates = len([x for x in env.writes if x[0] == "allocation"])
    env.run(tmp_path, apply=True)
    assert len([x for x in env.writes if x[0] == "allocation"]) == updates


def test_existing_applications_are_preserved_when_unused_credit_is_filled(tmp_path):
    env = Environment()
    env.invoice("801", "60", "2026-08-01", 300)
    env.run(tmp_path, apply=True)
    env.invoice("802", "60", "2026-09-01", 1000)
    env.run(tmp_path, apply=True)
    assert env.payments["100"]["invoices"] == [
        {"invoice_id": "801", "amount_applied": 300}, {"invoice_id": "802", "amount_applied": 700}]


def test_shared_customer_invoice_balance_is_reserved_across_payments(tmp_path):
    env = Environment(); env.creator_rows["7"]["Customer_Id"] = "60"
    env.invoice("801", "60", "2026-08-01", 1800)
    result = env.run(tmp_path, apply=True)
    assert env.payments["100"]["unused_amount"] == 0
    assert env.payments["101"]["unused_amount"] == 700
    assert env.invoices["801"]["balance"] == 0
    assert float(result.unused_amounts["5"]) == 700


@pytest.mark.parametrize("field,value", [("location_id", "bad"), ("balance", "bad"), ("date", "bad")])
def test_invalid_invoice_scope_or_financial_data_blocks_all_writes(tmp_path, field, value):
    env = Environment(); env.invoice("801", "60", "2026-08-01", 2000)
    env.invoices["801"][field] = value
    with pytest.raises(CashTransferError): env.run(tmp_path, apply=True)
    assert not env.writes


def test_other_books_location_is_excluded_even_when_list_filter_is_ignored(tmp_path):
    env = Environment(); env.invoice("801", "60", "2026-01-01", 1000)
    env.invoices["801"]["location_id"] = "91"
    env.invoice("802", "60", "2026-08-01", 2000)
    env.run(tmp_path, apply=True)
    assert env.payments["100"]["invoices"] == [{"invoice_id": "802", "amount_applied": 1000}]
    assert env.invoices["801"]["balance"] == 1000


def test_invoice_balance_change_before_posting_stops_financial_mutations(tmp_path):
    env = Environment(); env.invoice("801", "60", "2026-08-01", 2000)
    env.books.invoices.get = lambda iid: {"code": 0, "invoice": {**env.invoices[iid], "balance": 1999}}
    with pytest.raises(CashTransferError, match="before allocation"): env.run(tmp_path, apply=True)
    assert not env.writes


def test_lost_allocation_response_reconciles_exact_applications_before_retry(tmp_path):
    env = Environment(); env.run(tmp_path, apply=True)
    env.invoice("801", "60", "2026-08-01", 2000)
    env.uncertain_allocation = True
    with pytest.raises(RuntimeError, match="response lost"): env.run(tmp_path, apply=True)
    env.uncertain_allocation = False
    env.run(tmp_path, apply=True)
    assert len([x for x in env.writes if x[0] == "allocation"]) == 1
    state = json.loads((tmp_path / "transfer_1.json").read_text())
    assert state["operations"]["allocation:4"]["status"] == "VERIFIED"
