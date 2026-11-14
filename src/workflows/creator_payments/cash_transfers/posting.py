"""Checkpointed payment creation, associated deposit and Creator read-back."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from utils.file_utils import json
from workflows.collection_payments.payments import customer_payment_payload
from workflows.core.checkpoint import write_atomic_json
from .planning import (
    CashTransferError, CashTransferPlan, PaymentPlan, creator_record, links, money,
    numeric, plan_cash_transfer, record,
)
from .allocations import (
    application_totals, nonnegative, plan_invoice_allocations,
    verify_allocations, verify_invoice_balances,
)


@dataclass(frozen=True)
class CashTransferResult:
    status: str
    checkpoint: str
    payment_ids: tuple[str, ...]
    deposit_id: str
    unused_amounts: dict[str, str] = field(default_factory=dict)


@contextmanager
def _lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write("Cash posting in progress; reconcile before removing a stale lock.\n")
    except FileExistsError as exc:
        raise CashTransferError(f"Cash posting lock exists: {path}; reconcile before retry") from exc
    try:
        yield
    finally:
        path.unlink()


def _verify_payment(books: Any, payment_id: str, expected: PaymentPlan, plan: CashTransferPlan) -> dict[str, Any]:
    payment = record(books.customer_payments.get(numeric(payment_id)), "payment", 0)
    wanted = {
        "payment_id": payment_id, "customer_id": expected.customer_id,
        "date": expected.date, "account_id": plan.source_account_id,
        "location_id": plan.location_id,
    }
    if any(str(payment.get(k) or "") != v for k, v in wanted.items()) or money(payment.get("amount")) != expected.amount:
        raise CashTransferError(f"Books payment {payment_id} differs from the approved plan")
    values = links(payment)
    if values.get("cf_receipt_number", "") != expected.reference:
        raise CashTransferError(f"Books payment {payment_id} Receipt Number differs from Creator cash receipt {expected.reference!r}")
    if (values.get("cf_creator_record_id", expected.creator_id) != expected.creator_id
            or values.get("cf_creator_payment_id", expected.creator_number) != expected.creator_number):
        raise CashTransferError(f"Books payment {payment_id} is linked to another Creator payment")
    if not payment.get("payment_number"):
        raise CashTransferError(f"Books payment {payment_id} has no payment number")
    return payment


def _deposit_header(books: Any, deposit_id: str, plan: CashTransferPlan) -> dict[str, Any]:
    deposit = record(books.bank_transactions.get(numeric(deposit_id)), "banktransaction", 0)
    expected = {
        "transaction_id": deposit_id, "transaction_type": "deposit", "date": plan.date,
        "from_account_id": plan.source_account_id, "to_account_id": plan.destination_account_id,
        "location_id": plan.location_id,
    }
    if any(str(deposit.get(k) or "") != v for k, v in expected.items()) or money(deposit.get("amount")) != plan.amount:
        raise CashTransferError(f"Deposit {deposit_id} differs from the approved accounts/date/amount/location")
    return deposit


def _verify_deposit(books: Any, deposit_id: str, plan: CashTransferPlan, payments: dict[str, str]) -> None:
    deposit = _deposit_header(books, deposit_id, plan)
    rows = deposit.get("line_items")
    amounts = {payments[p.creator_id]: p.amount for p in plan.payments}
    if not isinstance(rows, list) or len(rows) != len(amounts):
        raise CashTransferError("Deposit does not contain exactly the selected payment associations")
    seen = set()
    for row in rows:
        key = str(row.get("transaction_id") or "")
        if key in seen or key not in amounts or money(row.get("total")) != amounts[key]:
            raise CashTransferError("Deposit payment association/amount mismatch")
        seen.add(key)


def _unassociated_deposit(books: Any, deposit_id: str, plan: CashTransferPlan) -> None:
    """Only resume our checkpointed, exact-amount deposit before association."""
    deposit = _deposit_header(books, deposit_id, plan)
    rows = deposit.get("line_items")
    if (deposit.get("reference_number") != f"Creator-CT-{plan.transfer_id}"
            or not isinstance(rows, list) or len(rows) != 1
            or rows[0].get("transaction_id")
            or str(rows[0].get("from_account_id")) != plan.source_account_id
            or money(rows[0].get("total")) != plan.amount):
        raise CashTransferError("Staged deposit changed; reconcile before associating payments")


def _creator_update(creator: Any, plan: CashTransferPlan, report: str, rid: str, fields: dict[str, Any]) -> None:
    if report == "Pending_Cash_Transfers" and plan.snapshot.get("Status") == "Verified":
        report = "Verified"
    response = creator.update_records(plan.app, report, record_id=rid,
                                     payload={"data": fields, "skip_workflow": ["all"]})
    if not isinstance(response, dict) or response.get("code") != 3000:
        raise CashTransferError(f"Creator did not confirm update of {rid}: {response}")
    for result in response.get("result", []):
        if result.get("code") != 3000:
            raise CashTransferError(f"Creator rejected update of {rid}: {response}")
    fresh = creator_record(creator, plan.app, report, rid)
    for key, value in fields.items():
        if key == "Cash_Balance":
            if Decimal(str(fresh.get(key))) != Decimal(str(value)):
                raise CashTransferError(f"Creator {rid} read-back differs for {key}")
        elif str(fresh.get(key) or "") != str(value):
            raise CashTransferError(f"Creator {rid} read-back differs for {key}")


def post_cash_transfer(
    books: Any, creator: Any, *, transfer_id: str, app: str, location_id: str,
    checkpoint_dir: Path = Path("output/cash_transfer"), apply: bool = False,
) -> CashTransferResult:
    """Preview by default; uncertain writes require live reconciliation before retry.

    Payments use oldest-invoice-date-first allocation. A deposit is posted
    only after both Books payments have been read back successfully. Existing
    native IDs/evidence are validated before reuse. No rollback or blind replay.
    """
    checkpoint_dir = checkpoint_dir.resolve()
    numeric(transfer_id)
    with _lock(checkpoint_dir / "cash_posting.lock"):
        path = checkpoint_dir / f"transfer_{transfer_id}.json"
        previous: dict[str, Any] = {}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise CashTransferError(f"Invalid checkpoint: {path}")
            previous = raw
        recovery = None
        if previous.get("operations", {}).get("deposit", {}).get("id"):
            identity = {"org": str(books.organization_id), "owner": creator.account_owner_name,
                        "app": app, "location": location_id, "transfer": transfer_id}
            if any(previous.get("signature", {}).get(k) != v for k, v in identity.items()):
                raise CashTransferError(f"Checkpoint scope/plan changed: inspect {path}")
            recovery = previous.get("snapshot", {}).get("snapshot")
        plan = plan_cash_transfer(books, creator, transfer_id=transfer_id, app=app, location_id=location_id,
                                  recovery_transfer=recovery)
        signature = {
            "org": plan.organization_id, "owner": plan.owner, "app": plan.app,
            "location": plan.location_id, "transfer": plan.transfer_id, "date": plan.date,
            "amount": str(plan.amount), "source": plan.source_account_id,
            "destination": plan.destination_account_id,
            "payments": [{"creator_id": p.creator_id, "customer": p.customer_id, "date": p.date,
                          "amount": str(p.amount), "reference": p.reference} for p in plan.payments],
        }
        old: dict[str, Any] = {}
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("signature") != signature:
                raise CashTransferError(f"Checkpoint scope/plan changed: inspect {path}")
            old = raw
        snapshot = asdict(plan)
        snapshot["payments"] = [asdict(p) for p in plan.payments]
        state = old or {"signature": signature, "snapshot": snapshot, "operations": {}}
        if state.get("status") == "PREVIEW":
            state["snapshot"] = snapshot
        operations = state["operations"]
        payment_ids: dict[str, str] = {}
        payment_records: dict[str, dict[str, Any]] = {}
        for p in plan.payments:
            operation = operations.get(p.creator_id, {})
            pid = p.existing_id or operation.get("id", "")
            if pid:
                payment_records[p.creator_id] = _verify_payment(books, pid, p, plan)
                payment_ids[p.creator_id] = pid
                operations.setdefault(p.creator_id, {}).update(id=pid, status="VERIFIED")
            elif operation.get("status") == "UNKNOWN":
                raise CashTransferError(f"Uncertain payment create for {p.creator_id}; reconcile Books before retry: {path}")
        if len(set(payment_ids.values())) != len(payment_ids):
            raise CashTransferError("Multiple Creator payments resolve to the same Books payment")
        deposit_op = operations.get("deposit", {})
        deposit_id = plan.existing_deposit_id or deposit_op.get("id", "")
        deposit_needs_links = False
        if deposit_id:
            if len(payment_ids) != len(plan.payments):
                raise CashTransferError("Existing deposit found but payment links are incomplete; reconcile before creating payments")
            try:
                _verify_deposit(books, deposit_id, plan, payment_ids)
            except CashTransferError:
                if not deposit_op.get("association_required"):
                    raise
                _unassociated_deposit(books, deposit_id, plan)
                deposit_needs_links = True
            if deposit_op:
                deposit_op.update(id=deposit_id, status="CREATED" if deposit_needs_links else "VERIFIED")
        elif deposit_op.get("status") == "UNKNOWN":
            raise CashTransferError(f"Uncertain deposit create; reconcile Books before retry: {path}")
        for p in plan.payments:
            op = operations.get(f"allocation:{p.creator_id}", {})
            if op.get("status") == "UNKNOWN":
                current = payment_records.get(p.creator_id)
                if (current is None or application_totals(current.get("invoices", [])) != application_totals(op["payload"]["invoices"])
                        or nonnegative(current.get("unused_amount"), "unused amount") != Decimal(op["unused_after"])):
                    raise CashTransferError(f"Uncertain invoice allocation for {p.creator_id}; reconcile before retry: {path}")
                op["status"] = "VERIFIED"
        allocations = plan_invoice_allocations(books, plan, payment_records)
        state["allocation_preview"] = {key: asdict(value) for key, value in allocations.items()}
        unused_amounts = {key: str(value.unused_after) for key, value in allocations.items()}
        if not apply:
            if not old or state.get("status") == "PREVIEW":
                state["status"] = "PREVIEW"
            write_atomic_json(path, state)
            return CashTransferResult("PREVIEW", str(path), tuple(payment_ids.values()), deposit_id, unused_amounts)

        def save() -> None:
            write_atomic_json(path, state)

        def start(key: str, payload: dict[str, Any]) -> None:
            operations[key] = {"status": "UNKNOWN", "payload": payload}
            save()

        state["status"] = "RUNNING"
        save()
        try:
            # Resolve and verify every payment before attempting the deposit.
            for p in plan.payments:
                if p.creator_id not in payment_ids:
                    from datetime import date
                    verify_invoice_balances(books, allocations[p.creator_id], customer_id=p.customer_id,
                                            location_id=plan.location_id, after=False)
                    payload = customer_payment_payload(
                        customer_id=p.customer_id, payment_mode="cash", payment_date=date.fromisoformat(p.date),
                        amount=p.amount, reference_number="",
                        description=f"Creator cash payment {p.creator_number}; cash transfer {plan.transfer_id}",
                        account_id=plan.source_account_id, creator_record_id=p.creator_id,
                        creator_payment_id=p.creator_number, invoices=allocations[p.creator_id].payload()["invoices"],
                    )
                    payload["location_id"] = plan.location_id
                    if p.reference:
                        custom_fields = payload["custom_fields"]
                        if not isinstance(custom_fields, list):
                            raise CashTransferError("Customer payment payload has invalid custom fields")
                        custom_fields.append({"label": "Receipt Number", "value": p.reference})
                    start(p.creator_id, payload)
                    payment = record(books.customer_payments.create(payload), "payment", 0)
                    pid = numeric(payment.get("payment_id"))
                    operations[p.creator_id].update(id=pid, status="CREATED")
                    save()
                    payment_records[p.creator_id] = _verify_payment(books, pid, p, plan)
                    verify_allocations(payment_records[p.creator_id], allocations[p.creator_id])
                    verify_invoice_balances(books, allocations[p.creator_id], customer_id=p.customer_id,
                                            location_id=plan.location_id, after=True)
                    payment_ids[p.creator_id] = pid
                    operations[p.creator_id]["status"] = "VERIFIED"
                    save()
                else:
                    allocation = allocations[p.creator_id]
                    if allocation.before != allocation.after:
                        pid = payment_ids[p.creator_id]
                        current = _verify_payment(books, pid, p, plan)
                        if (application_totals(current.get("invoices", [])) != allocation.before
                                or nonnegative(current.get("unused_amount"), "unused amount") != allocation.unused_before):
                            raise CashTransferError("Payment applications changed after planning; no allocation update attempted")
                        verify_invoice_balances(books, allocation, customer_id=p.customer_id,
                                                location_id=plan.location_id, after=False)
                        key = f"allocation:{p.creator_id}"
                        operations[key] = {"status": "UNKNOWN", "id": pid, "payload": allocation.payload(),
                                           "before": current, "unused_after": str(allocation.unused_after)}
                        save()
                        response = books.customer_payments.update(pid, allocation.payload())
                        if not isinstance(response, dict) or response.get("code") != 0:
                            raise CashTransferError(f"Books rejected invoice allocation for {pid}")
                        payment_records[p.creator_id] = _verify_payment(books, pid, p, plan)
                        if payment_records[p.creator_id]["payment_number"] != current["payment_number"]:
                            raise CashTransferError("Payment number changed during invoice allocation")
                        verify_allocations(payment_records[p.creator_id], allocation)
                        verify_invoice_balances(books, allocation, customer_id=p.customer_id,
                                                location_id=plan.location_id, after=True)
                        operations[key]["status"] = "VERIFIED"
                        save()
                _creator_update(creator, plan, "All_Payments", p.creator_id, {
                    "Books_Transaction_Id": payment_ids[p.creator_id],
                    "PaymentNo": payment_records[p.creator_id]["payment_number"],
                })
            if not deposit_id:
                payload = {
                    "transaction_type": "deposit", "date": plan.date,
                    "from_account_id": plan.source_account_id, "amount": float(plan.amount),
                    "to_account_id": plan.destination_account_id,
                    "location_id": plan.location_id, "payment_mode": "cash",
                    "reference_number": f"Creator-CT-{plan.transfer_id}",
                    "description": f"Creator cash transfer {plan.transfer_id}",
                }
                # Create the correct total first: Books requires a positive
                # header amount and otherwise adds it to associated lines.
                start("deposit", payload)
                operations["deposit"]["association_required"] = True
                save()
                deposit = record(books.bank_transactions.create(payload), "banktransaction", 0)
                deposit_id = numeric(deposit.get("transaction_id"))
                operations["deposit"].update(id=deposit_id, status="CREATED")
                save()
                _unassociated_deposit(books, deposit_id, plan)
                deposit_needs_links = True
            if deposit_needs_links:
                _unassociated_deposit(books, deposit_id, plan)
                payload = {
                    "transaction_type": "deposit", "date": plan.date,
                    "to_account_id": plan.destination_account_id,
                    "location_id": plan.location_id, "payment_mode": "cash",
                    "reference_number": f"Creator-CT-{plan.transfer_id}",
                    "description": f"Creator cash transfer {plan.transfer_id}",
                    "line_items": [{"transaction_id": payment_ids[p.creator_id], "transaction_type": "invoice_payment",
                                    "from_account_id": plan.source_account_id, "customer_id": p.customer_id,
                                    "payment_mode": "cash", "amount": float(p.amount), "total": float(p.amount)}
                                   for p in plan.payments],
                }
                operations["deposit"].update(status="LINKING", association_payload=payload)
                save()
                response = books.bank_transactions.update(deposit_id, payload)
                if not isinstance(response, dict) or response.get("code") != 0:
                    raise CashTransferError("Books rejected deposit payment associations")
                _verify_deposit(books, deposit_id, plan, payment_ids)
                operations["deposit"]["status"] = "VERIFIED"
                save()
            _verify_deposit(books, deposit_id, plan, payment_ids)
            for p in plan.payments:
                _creator_update(creator, plan, "All_Payments", p.creator_id,
                                {"Cash_Status": "Settled", "Cash_Balance": 0})
            _creator_update(creator, plan, "Pending_Cash_Transfers", plan.transfer_id,
                            {"Books_Transaction_Id": deposit_id, "Status": "Verified"})
            state["status"] = "COMPLETE"
            state.pop("error", None)
            save()
        except Exception as exc:
            state.update(status="FAILED", error=str(exc))
            save()
            raise
        return CashTransferResult("COMPLETE", str(path), tuple(payment_ids.values()), deposit_id, unused_amounts)
