"""Build update plans for customer payment invoice application dates."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from collections.abc import Mapping

from helpers import parse_date


def parse_any_date(val: object) -> date | None:
    if not val:
        return None
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return parse_date(val)


def build_update_plan(audit_result_or_rows: object) -> dict[str, object]:
    """Build update plan to align application date to max(payment_date, invoice_date)."""
    plan_rows: list[dict[str, object]] = []
    by_payment: dict[str, list[dict[str, object]]] = {}

    # Case 1: Structured audit result payload
    if isinstance(audit_result_or_rows, dict):
        res = audit_result_or_rows.get("result") or audit_result_or_rows
        mismatches = res.get("mismatches") or []
        for pmt in mismatches:
            pmt_id = str(pmt.get("payment_id") or "").strip()
            pmt_num = str(pmt.get("payment_number") or "").strip()
            cust_name = str(pmt.get("customer_name") or "").strip()
            pmt_date_str = str(pmt.get("payment_date") or "").strip()
            pmt_d = parse_any_date(pmt_date_str)

            for app in pmt.get("mismatched_applications") or []:
                inv_id = str(app.get("invoice_id") or "").strip()
                inv_num = str(app.get("invoice_number") or "").strip()
                inv_date_str = str(app.get("invoice_date") or "").strip()
                app_date_str = str(app.get("applied_date") or "").strip()
                amt_str = str(app.get("amount_applied") or "0").replace("INR", "").replace(",", "").strip()

                inv_d = parse_any_date(inv_date_str)
                app_d = parse_any_date(app_date_str)

                if not pmt_d or not inv_d or not app_d:
                    continue

                target_d = max(pmt_d, inv_d)
                target_rule = "Payment Date" if target_d == pmt_d else "Invoice Date"
                days_shift = (target_d - app_d).days

                item: dict[str, object] = {
                    "payment_id": pmt_id,
                    "payment_number": pmt_num,
                    "customer_name": cust_name,
                    "payment_date": pmt_d.isoformat(),
                    "invoice_id": inv_id,
                    "invoice_number": inv_num,
                    "invoice_date": inv_d.isoformat(),
                    "current_applied_date": app_d.isoformat(),
                    "target_applied_date": target_d.isoformat(),
                    "target_date_source": target_rule,
                    "days_shift": days_shift,
                    "amount_applied": amt_str,
                }
                plan_rows.append(item)
                if pmt_num not in by_payment:
                    by_payment[pmt_num] = []
                by_payment[pmt_num].append(item)

        return {
            "total_discrepancies": len(plan_rows),
            "distinct_payments_count": len(by_payment),
            "allocations": plan_rows,
            "by_payment": by_payment,
        }

    # Case 2: List of flat rows
    if isinstance(audit_result_or_rows, list):
        for row in audit_result_or_rows:
            if not isinstance(row, Mapping):
                continue

            def _get_val(*keys: str) -> object:
                for k in keys:
                    if k in row and row[k] is not None:
                        return row[k]
                    for rk, rv in row.items():
                        if rk.lower() == k.lower() or rk.lower().endswith("." + k.lower()):
                            if rv is not None:
                                return rv
                return None

            pmt_num = str(_get_val("Payment Number", "cp.Payment Number") or "").strip()
            pmt_id = str(_get_val("Payment ID", "cp.Payment ID") or pmt_num).strip()
            cust_name = str(_get_val("Customer Name", "c.Customer Name") or "").strip()
            inv_num = str(_get_val("Invoice Number", "inv.Invoice Number") or "").strip()
            inv_id = str(_get_val("Invoice ID", "ip.Invoice ID", "inv.Invoice ID") or inv_num).strip()

            raw_pmt_date = _get_val("Payment Date", "cp.Payment Date")
            raw_inv_date = _get_val("Invoice Date", "inv.Invoice Date")
            raw_app_date = _get_val("Invoice Payment Applied Date", "ip.Invoice Payment Applied Date")
            amt_str = str(_get_val("Amount Applied", "Amount (BCY)") or "0").replace("INR", "").replace(",", "").strip()

            pmt_d = parse_any_date(raw_pmt_date)
            inv_d = parse_any_date(raw_inv_date)
            app_d = parse_any_date(raw_app_date)

            if not pmt_d or not inv_d or not app_d:
                continue

            target_d = max(pmt_d, inv_d)
            target_rule = "Payment Date" if target_d == pmt_d else "Invoice Date"
            days_shift = (target_d - app_d).days

            item: dict[str, object] = {
                "payment_id": pmt_id,
                "payment_number": pmt_num,
                "customer_name": cust_name,
                "payment_date": pmt_d.isoformat(),
                "invoice_id": inv_id,
                "invoice_number": inv_num,
                "invoice_date": inv_d.isoformat(),
                "current_applied_date": app_d.isoformat(),
                "target_applied_date": target_d.isoformat(),
                "target_date_source": target_rule,
                "days_shift": days_shift,
                "amount_applied": amt_str,
            }
            plan_rows.append(item)
            if pmt_num not in by_payment:
                by_payment[pmt_num] = []
            by_payment[pmt_num].append(item)

    return {
        "total_discrepancies": len(plan_rows),
        "distinct_payments_count": len(by_payment),
        "allocations": plan_rows,
        "by_payment": by_payment,
    }


def render_plan_markdown(plan: Mapping[str, object]) -> str:
    allocations = plan.get("allocations")
    alloc_list = allocations if isinstance(allocations, list) else []
    lines = [
        "# Invoice Payment Date Update Plan",
        "",
        "> **Formula Applied**: `Target Applied Date = MAX(Payment Date, Invoice Date)`",
        f"> **Total Allocations to Update**: {plan.get('total_discrepancies', 0)}",
        f"> **Distinct Payments**: {plan.get('distinct_payments_count', 0)}",
        "",
        "| # | Payment # | Payment Date | Customer | Invoice # | Invoice Date | Current Applied Date | **Target Applied Date** | Basis | Shift | Amount Applied |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for idx, raw_item in enumerate(alloc_list, 1):
        if not isinstance(raw_item, Mapping):
            continue
        item = raw_item
        shift = item.get("days_shift")
        shift_str = f"{shift}d" if str(shift).startswith("-") else f"+{shift}d"
        lines.append(
            f"| {idx} | {item.get('payment_number')} | {item.get('payment_date')} | {item.get('customer_name')} | "
            f"{item.get('invoice_number')} | {item.get('invoice_date')} | {item.get('current_applied_date')} | "
            f"**{item.get('target_applied_date')}** | {item.get('target_date_source')} | {shift_str} | ₹{item.get('amount_applied')} |"
        )

    lines.append("")
    return "\n".join(lines) + "\n"
