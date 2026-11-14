"""Read and validate a single transfer before any financial write."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from zoho.creator.exceptions import ZohoCreatorError

from workflows.core.matching import parse_date, to_decimal


class CashTransferError(RuntimeError):
    """Invalid scope, ambiguous posting or failed live verification."""


def record(response: Any, key: str, code: int) -> dict[str, Any]:
    if not isinstance(response, dict) or response.get("code") != code:
        raise CashTransferError(f"Unsuccessful {key} response: {response}")
    value = response.get(key)
    if not isinstance(value, dict):
        raise CashTransferError(f"Missing {key} response record")
    return value


def numeric(value: Any) -> str:
    text = str(value or "").strip()
    if not text.isascii() or not text.isdigit():
        raise CashTransferError(f"Expected a numeric record ID, got {text!r}")
    return text


def money(value: Any) -> Decimal:
    amount = to_decimal(value)
    if amount is None or not amount.is_finite() or amount <= 0 or amount != amount.quantize(Decimal("0.01")):
        raise CashTransferError(f"Expected a positive two-decimal amount, got {value!r}")
    return amount


def creator_record(creator: Any, app: str, report: str, record_id: str) -> dict[str, Any]:
    numeric(record_id)
    try:
        response = creator.request(
            "GET", f"data/{creator.account_owner_name}/{app}/report/{report}/{record_id}",
            params={"field_config": "all"},
        )
    except ZohoCreatorError as exc:
        if report != "Pending_Cash_Transfers" or str(exc.error_code) not in {"9280", "9290"}:
            raise
        response = creator.request(
            "GET", f"data/{creator.account_owner_name}/{app}/report/Verified/{record_id}",
            params={"field_config": "all"},
        )
    value = record(response, "data", 3000)
    if str(value.get("ID")) != record_id:
        raise CashTransferError(f"Creator identity mismatch for {record_id}")
    return value


@dataclass(frozen=True)
class PaymentPlan:
    creator_id: str
    creator_number: str
    customer_id: str
    date: str
    amount: Decimal
    reference: str
    existing_id: str
    snapshot: dict[str, Any]


@dataclass(frozen=True)
class CashTransferPlan:
    transfer_id: str
    app: str
    owner: str
    organization_id: str
    location_id: str
    date: str
    amount: Decimal
    source_account_id: str
    destination_account_id: str
    payments: tuple[PaymentPlan, ...]
    existing_deposit_id: str
    snapshot: dict[str, Any]


def links(payment: dict[str, Any]) -> dict[str, str]:
    names = ("cf_creator_record_id", "cf_creator_payment_id", "cf_receipt_number")
    values = {k: str(v) for k, v in payment.get("custom_field_hash", {}).items() if k in names and v not in (None, "")}
    values.update({k: str(payment[k]) for k in names if payment.get(k) not in (None, "")})
    for field in payment.get("custom_fields", []):
        name = field.get("api_name") or {
            "Creator Record ID": "cf_creator_record_id", "Creator Payment ID": "cf_creator_payment_id",
            "Receipt Number": "cf_receipt_number",
        }.get(field.get("label"))
        if name and field.get("value") not in (None, ""):
            values[name] = str(field["value"])
    return values


def plan_cash_transfer(
    books: Any, creator: Any, *, transfer_id: str, app: str, location_id: str,
    recovery_transfer: dict[str, Any] | None = None,
) -> CashTransferPlan:
    """Reject mismatched amounts, scopes, split deposits and duplicate candidates."""
    numeric(transfer_id); numeric(location_id)
    locations = books.request("GET", "locations")
    if not isinstance(locations, dict) or locations.get("code") != 0:
        raise CashTransferError("Could not verify Books locations")
    if not any(str(x.get("location_id")) == location_id and x.get("is_location_active") is True
               for x in locations.get("locations", [])):
        raise CashTransferError("Selected Books location is missing or inactive")
    transfer = creator_record(creator, app, "Pending_Cash_Transfers", transfer_id)
    details = transfer.get("Transfer_Details")
    if not details and transfer.get("Status") == "Verified" and recovery_transfer:
        # The Verified report hides the destination subform. Recover only the
        # approved destination; revalidate all visible scope and Books evidence.
        for key in ("ID", "Date_field", "From_Account", "Payment_Ids"):
            if transfer.get(key) != recovery_transfer.get(key):
                raise CashTransferError(f"Verified transfer differs from checkpoint for {key}")
        for key in ("Total_Amount", "Transfer_Amount"):
            if money(transfer.get(key)) != money(recovery_transfer.get(key)):
                raise CashTransferError("Verified transfer amount differs from checkpoint")
        details = recovery_transfer.get("Transfer_Details")
    if not isinstance(details, list) or len(details) != 1:
        raise CashTransferError("Exactly one destination account is supported; split transfers need separate review")
    source = creator_record(creator, app, "All_Account_Details", numeric(transfer["From_Account"]["ID"]))
    destination = creator_record(creator, app, "All_Account_Details", numeric(details[0]["To_Account"]["ID"]))
    source_id, destination_id = numeric(source.get("Account_ID")), numeric(destination.get("Account_ID"))
    if source_id == destination_id:
        raise CashTransferError("Source and destination accounts must differ")
    accounts = [record(books.bank_accounts.get(aid), "bankaccount", 0) for aid in (source_id, destination_id)]
    if any(str(a.get("account_id")) != aid or a.get("is_active") is not True
           or a.get("currency_code") != "INR" for a, aid in zip(accounts, (source_id, destination_id))):
        raise CashTransferError("Account identity, active status or INR currency mismatch")
    if accounts[0].get("is_undeposited_funds") is not True:
        raise CashTransferError("Source account is not Books Undeposited Funds")
    day = parse_date(transfer.get("Date_field"))
    if day is None:
        raise CashTransferError("Transfer date is missing or invalid")
    amount = money(transfer.get("Transfer_Amount"))
    if money(transfer.get("Total_Amount")) != amount:
        raise CashTransferError("Transfer amount and total differ")
    if details[0].get("Transfer_Amount") not in (None, "") and money(details[0]["Transfer_Amount"]) != amount:
        raise CashTransferError("Destination row amount differs from the transfer")
    references = transfer.get("Payment_Ids")
    if not isinstance(references, list) or not references:
        raise CashTransferError("Transfer has no linked payments")
    plans = []
    seen = set()
    for reference in references:
        rid = numeric(reference.get("ID"))
        if rid in seen:
            raise CashTransferError("Duplicate Creator payment in transfer")
        seen.add(rid)
        payment = creator_record(creator, app, "All_Payments", rid)
        if payment.get("Payment_Method") != "Cash" or str(payment.get("Account", {}).get("ID")) != str(source["ID"]):
            raise CashTransferError(f"Payment {rid} is not cash into the selected Undeposited Funds account")
        if payment.get("InvoiceDet") or payment.get("Is_Discount_Applicable") in (True, "true", ["Yes"]):
            raise CashTransferError(f"Payment {rid} has invoice/discount instructions requiring separate review")
        if not any(str(t.get("ID")) == transfer_id for t in payment.get("Cash_Transfer", [])):
            raise CashTransferError(f"Payment {rid} is not linked back to this transfer")
        payment_day = parse_date(payment.get("Payment_Date"))
        if payment_day is None or payment_day > day:
            raise CashTransferError(f"Payment {rid} has an invalid or later date")
        customer = creator_record(creator, app, "All_Customers1", numeric(payment["Customer_Name"]["ID"]))
        customer_id = numeric(customer.get("Customer_Id"))
        contact = record(books.contacts.get(customer_id), "contact", 0)
        if str(contact.get("contact_id")) != customer_id or contact.get("contact_type") != "customer":
            raise CashTransferError("Books customer identity/type mismatch")
        existing_id = str(payment.get("Books_Transaction_Id") or "")
        candidates = books.customer_payments.list_all(params={"customer_id": customer_id}, resource_key="customerpayments")
        if not isinstance(candidates, list) or any(str(r.get("customer_id")) != customer_id for r in candidates):
            raise CashTransferError("Books payment query returned invalid or out-of-scope records")
        matching = []
        for candidate in candidates:
            if links(candidate).get("cf_creator_record_id") == rid:
                matching.append(candidate)
            elif (candidate.get("date") == payment_day.isoformat()
                  and money(candidate.get("amount")) == money(payment["Payment_Amount"])):
                # List responses may omit custom fields. Read detail before
                # deciding that a same-date/amount receipt is missing.
                detail = record(books.customer_payments.get(numeric(candidate.get("payment_id"))), "payment", 0)
                receipt = str(payment.get("Reference") or "")
                if (links(detail).get("cf_receipt_number", "") == receipt
                        or str(detail.get("reference_number") or "") == receipt):
                    matching.append(detail)
        if len(matching) > 1 or (matching and existing_id and str(matching[0].get("payment_id")) != existing_id):
            raise CashTransferError(f"Ambiguous existing Books payment for {rid}")
        if matching:
            existing_id = numeric(matching[0].get("payment_id"))
        plans.append(PaymentPlan(rid, str(payment.get("Payment_ID") or ""), customer_id,
                                 payment_day.isoformat(), money(payment["Payment_Amount"]),
                                 str(payment.get("Reference") or ""), existing_id, payment))
    if sum((p.amount for p in plans), Decimal(0)) != amount:
        raise CashTransferError("Linked payment amounts do not equal the transfer; no writes made")
    deposit_id = str(transfer.get("Books_Transaction_Id") or "")
    deposits = books.bank_transactions.list_all(
        params={"account_id": destination_id, "date_start": day.isoformat(), "date_end": day.isoformat()},
        resource_key="banktransactions",
    )
    if not isinstance(deposits, list):
        raise CashTransferError("Invalid Books deposit query")
    for row in deposits:
        if str(row.get("account_id")) != destination_id or row.get("date") != day.isoformat():
            raise CashTransferError("Books deposit query returned out-of-scope records")
        if row.get("transaction_type") != "deposit":
            continue
        if str(row.get("reference_number") or "") == f"Creator-CT-{transfer_id}" or to_decimal(row.get("amount")) == amount:
            candidate = numeric(row.get("transaction_id"))
            if deposit_id and deposit_id != candidate:
                raise CashTransferError("Multiple/conflicting deposit candidates; inspect Books before retry")
            deposit_id = candidate
    if not deposit_id:
        for p in plans:
            balance = to_decimal(p.snapshot.get("Cash_Balance"))
            if balance != p.amount or p.snapshot.get("Cash_Status") not in ("In Hand", "Transfer Initiated"):
                raise CashTransferError(f"Payment {p.creator_id} is already settled or partially transferred; reconcile first")
    return CashTransferPlan(transfer_id, app, creator.account_owner_name, str(books.organization_id), location_id,
                            day.isoformat(), amount, source_id, destination_id, tuple(plans), deposit_id, transfer)
