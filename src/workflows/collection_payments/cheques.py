"""Cheque presented-date lookup, normalization, joining, and presentation checkpoint."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from helpers import normalize_cheque_number, require_creator_success
from workflows.core.matching import parse_date, to_text as _text
from workflows.runtime.exceptions import ReconciliationError


def attach_presented_dates(
    payments: Sequence[dict[str, object]],
    cheque_details: Sequence[Mapping[str, object]],
) -> None:
    """Join presented dates from Creator All_Cheque_Details onto payment records."""
    details_by_key: dict[tuple[str, str], list[Mapping[str, object]]] = {}
    for detail in cheque_details:
        raw_cust = detail.get("Payment_ID.Customer_Name")
        lookup: Mapping[str, object] = raw_cust if isinstance(raw_cust, Mapping) else {}
        key = (
            normalize_cheque_number(detail.get("Cheque_Number")),
            _text(lookup.get("ID")),
        )
        if all(key):
            details_by_key.setdefault(key, []).append(detail)

    for payment in payments:
        if _text(payment.get("_review_payment_type")).casefold() != "cheque":
            continue
        raw_cust = payment.get("Customer_Name")
        lookup = raw_cust if isinstance(raw_cust, Mapping) else {}
        key = (
            normalize_cheque_number(payment.get("Reference")),
            _text(lookup.get("ID")),
        )
        candidates = details_by_key.get(key, [])
        if len(candidates) > 1:
            payment["_review_presented_date"] = ""
            payment["_review_presented_date_error"] = "Multiple presented cheque details matched cheque number and customer"
            continue

        presented_date = _text(candidates[0].get("Presented_Date")) if candidates else ""
        cheque_date = _text(payment.get("Cheque_Date"))
        payment["_review_presented_date"] = presented_date or cheque_date
        payment["_review_date_source"] = "presented_date" if presented_date else "cheque_date"
        payment["_review_presented_date_error"] = "" if presented_date or cheque_date else "No Presented_Date or Cheque_Date is available"
        if candidates:
            payment["_review_cheque_detail_id"] = _text(candidates[0].get("ID"))


def checkpoint_cheque_presentation(
    creator_client: object,
    *,
    app_link_name: str,
    detail_report_link_name: str,
    detail_form_link_name: str,
    entry: Mapping[str, object],
) -> None:
    """Save the bank clearing date after matching, reusing a detail on retry."""
    record_id = _text(entry["id"])
    bank = entry.get("bank")
    bank_date = parse_date(bank.get("date") if isinstance(bank, Mapping) else None)
    if not bank_date:
        raise ReconciliationError("The cheque bank line has no valid clearing date.")
    creator_row = entry.get("creator")
    cheque_ref = _text(creator_row.get("reference") if isinstance(creator_row, Mapping) else "")

    def matching_details() -> list[Mapping[str, object]]:
        rows = getattr(creator_client, "get_all_records")(
            app_link_name, detail_report_link_name, field_config="all",
        )
        return [
            row
            for row in rows
            if isinstance(row, Mapping)
            and isinstance(row.get("Payment_ID"), Mapping)
            and _text(row["Payment_ID"].get("ID")) == record_id
        ]

    details = matching_details()
    if len(details) > 1:
        raise ReconciliationError(
            "Multiple Creator cheque details refer to this payment; presentation checkpoint is blocked."
        )
    payload = {
        "Payment_ID": record_id,
        "Cheque_Number": cheque_ref,
        "Presented_Date": bank_date.strftime("%d-%b-%Y"),
    }
    if details:
        detail = details[0]
        if normalize_cheque_number(detail.get("Cheque_Number")) != normalize_cheque_number(cheque_ref):
            raise ReconciliationError("Creator cheque detail number conflicts with this payment.")
        if parse_date(detail.get("Presented_Date")) == bank_date:
            return
        response = getattr(creator_client, "update_records")(
            app_link_name,
            detail_report_link_name,
            {"data": payload},
            record_id=_text(detail.get("ID")),
        )
    else:
        response = getattr(creator_client, "add_records")(
            app_link_name,
            detail_form_link_name,
            {"data": payload},
        )
    try:
        require_creator_success(response)
    except ValueError as exc:
        raise ReconciliationError(str(exc)) from exc
    verified = matching_details()
    if (
        len(verified) != 1
        or parse_date(verified[0].get("Presented_Date")) != bank_date
        or normalize_cheque_number(verified[0].get("Cheque_Number")) != normalize_cheque_number(cheque_ref)
    ):
        raise ReconciliationError(
            "Creator presented-date verification failed. The existing Books payment will be reused on retry."
        )
