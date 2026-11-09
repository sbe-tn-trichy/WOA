"""Targeted customer-number backfill for existing Books-linked Creator records."""
from dataclasses import dataclass
from typing import Any

from zoho.books import ZohoBooksAPI
from zoho.creator import ZohoCreatorAPI
from workflows.runtime.exceptions import ReconciliationError


def _as_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass(frozen=True)
class CustomerNumberChange:
    books_contact_id: str
    creator_record_id: str
    customer_name: str
    current_number: str
    books_number: str


@dataclass(frozen=True)
class CustomerNumberSyncResult:
    dry_run: bool
    changes: list[CustomerNumberChange]
    unchanged: int
    updated: int


def sync_customer_numbers(
    books_client: ZohoBooksAPI,
    creator_client: ZohoCreatorAPI,
    books_contact_ids: list[str],
    *,
    app_link_name: str = "order-management-new",
    report_link_name: str = "All_Customers1",
    dry_run: bool = True,
) -> CustomerNumberSyncResult:
    """Fill blank Customer_no values for explicit IDs, with no creates/deletes.

    Conflicting existing numbers, duplicate links or number collisions abort
    before writes. Applied updates are reread. A failure stops subsequent writes;
    earlier successful updates are not rolled back.
    """
    ids = [str(value).strip() for value in books_contact_ids]
    if not ids or any(not value.isdigit() for value in ids) or len(set(ids)) != len(ids):
        raise ValueError("Provide unique numeric Books contact IDs.")
    if not app_link_name.strip() or not report_link_name.strip():
        raise ValueError("Creator app and report link names are required.")
    rows = creator_client.get_all_records(app_link_name, report_link_name)
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ReconciliationError("Invalid Creator customer response.")
    changes: list[CustomerNumberChange] = []
    unchanged = 0
    planned_numbers: set[str] = set()
    for contact_id in ids:
        matches = [row for row in rows if str(row.get("Customer_Id", "")).strip() == contact_id]
        if len(matches) != 1 or not str(matches[0].get("ID", "")).isdigit():
            raise ReconciliationError(f"Books customer {contact_id} needs exactly one linked Creator record.")
        row = matches[0]
        if "Customer_no" not in row:
            raise ReconciliationError("Creator report must expose Customer_no.")
        raw_resp = books_client.contacts.get(contact_id)
        response = _as_dict(raw_resp)
        contact = _as_dict(response.get("contact"))
        if response.get("code") != 0 or str(contact.get("contact_id")) != contact_id or contact.get("contact_type") != "customer":
            raise ReconciliationError(f"Books customer {contact_id} could not be verified.")
        number = contact.get("contact_number")
        if not isinstance(number, str) or not number.strip():
            raise ReconciliationError(f"Books customer {contact_id} has no contact_number.")
        number = number.strip()
        current = str(row.get("Customer_no") or "").strip()
        if number in planned_numbers or any(str(other.get("Customer_no") or "").strip() == number and str(other.get("ID")) != str(row["ID"]) for other in rows):
            raise ReconciliationError(f"Books customer {contact_id} number conflicts with another Creator record.")
        planned_numbers.add(number)
        if current == number:
            unchanged += 1
            continue
        if current:
            raise ReconciliationError(f"Creator record {row['ID']} already has a different Customer_no.")
        changes.append(CustomerNumberChange(contact_id, str(row["ID"]),
                                            str(contact.get("contact_name") or ""), current, number))
    updated = 0
    if not dry_run:
        for change in changes:
            raw_upd = creator_client.update_records(
                app_link_name, report_link_name, record_id=change.creator_record_id,
                payload={"data": {"Customer_no": change.books_number}, "skip_workflow": ["all"]},
            )
            response = _as_dict(raw_upd)
            raw_res = response.get("result", [])
            results = raw_res if isinstance(raw_res, list) else []
            if response.get("code") != 3000 or any(_as_dict(result).get("code", 3000) != 3000 for result in results):
                raise ReconciliationError(f"Creator update was not confirmed for {change.creator_record_id}.")
            raw_saved = creator_client.get_records(
                app_link_name, report_link_name,
                params={"criteria": "ID == " + change.creator_record_id, "field_config": "all"},
            )
            saved = _as_dict(raw_saved)
            raw_recs = saved.get("data", [])
            records = raw_recs if isinstance(raw_recs, list) else []
            if saved.get("code") != 3000 or len(records) != 1:
                raise ReconciliationError(f"Creator number read-back failed for {change.creator_record_id}.")
            first_rec = _as_dict(records[0])
            if str(first_rec.get("Customer_Id")) != change.books_contact_id or first_rec.get("Customer_no") != change.books_number:
                raise ReconciliationError(f"Creator number read-back failed for {change.creator_record_id}.")
            updated += 1
    return CustomerNumberSyncResult(dry_run, changes, unchanged, updated)
