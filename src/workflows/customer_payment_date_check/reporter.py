"""Format customer payment date mismatch reports as Markdown and CSV."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping


def render_markdown_report(payload: Mapping[str, object]) -> str:
    """Render a human-readable Markdown audit report."""
    raw_res = payload.get("result")
    result: Mapping[str, object] = raw_res if isinstance(raw_res, Mapping) else payload
    checked_at = str(payload.get("checked_at") or "")
    filters_val = payload.get("filters")
    filters = filters_val if isinstance(filters_val, Mapping) else {}

    lines: list[str] = [
        "# Customer Payment vs Applied Date Audit Report",
        "",
        f"- **Checked At (UTC)**: {checked_at}",
        f"- **Payments Scanned**: {result.get('payments_scanned', 0)}",
        f"- **Mismatched Payments**: {result.get('mismatched_payments_count', 0)}",
        f"- **Mismatched Invoice Applications**: {result.get('total_mismatched_applications', 0)}",
        f"- **Tolerance (Days)**: {result.get('tolerance_days', 0)}",
    ]

    if filters:
        filter_strs = [f"{k}: {v}" for k, v in filters.items() if v is not None]
        if filter_strs:
            lines.append(f"- **Filters Applied**: {', '.join(filter_strs)}")

    lines.append("")

    raw_mismatches = result.get("mismatches")
    mismatches: list[object] = raw_mismatches if isinstance(raw_mismatches, list) else []
    if not mismatches:
        lines.append("No customer payments with different applied dates were found.")
        return "\n".join(lines) + "\n"

    lines.extend([
        "## Mismatched Payment Allocations",
        "",
        "| Payment # | Payment Date | Customer | Invoice # | Invoice Date | Applied Date | Diff (Days) | Amount Applied | Reference |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for raw_pmt in mismatches:
        if not isinstance(raw_pmt, Mapping):
            continue
        pmt = raw_pmt
        pmt_num = pmt.get("payment_number") or pmt.get("payment_id")
        pmt_date = pmt.get("payment_date", "")
        cust_name = pmt.get("customer_name", "")
        ref = pmt.get("reference_number", "")

        apps = pmt.get("mismatched_applications")
        if isinstance(apps, list):
            for raw_app in apps:
                if not isinstance(raw_app, Mapping):
                    continue
                app = raw_app
                inv_num = app.get("invoice_number") or app.get("invoice_id", "")
                inv_date = app.get("invoice_date") or "-"
                applied_date = app.get("applied_date", "")
                days_diff = app.get("days_difference", 0)
                diff_str = f"+{days_diff}d" if isinstance(days_diff, (int, float)) and days_diff > 0 else f"{days_diff}d"
                amt = app.get("amount_applied", "0.00")

                lines.append(
                    f"| {pmt_num} | {pmt_date} | {cust_name} | {inv_num} | {inv_date} | {applied_date} | {diff_str} | ₹{amt} | {ref} |"
                )

    lines.append("")
    return "\n".join(lines) + "\n"


def render_csv_report(payload: Mapping[str, object]) -> str:
    """Render a CSV audit report."""
    raw_res = payload.get("result")
    result: Mapping[str, object] = raw_res if isinstance(raw_res, Mapping) else payload
    raw_mismatches = result.get("mismatches")
    mismatches: list[object] = raw_mismatches if isinstance(raw_mismatches, list) else []

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Payment ID",
        "Payment Number",
        "Payment Date",
        "Customer ID",
        "Customer Name",
        "Payment Amount",
        "Payment Mode",
        "Reference Number",
        "Invoice ID",
        "Invoice Number",
        "Invoice Date",
        "Applied Date",
        "Days Difference",
        "Mismatch Type",
        "Amount Applied",
    ])

    for raw_pmt in mismatches:
        if not isinstance(raw_pmt, Mapping):
            continue
        pmt = raw_pmt
        apps = pmt.get("mismatched_applications")
        if isinstance(apps, list):
            for raw_app in apps:
                if not isinstance(raw_app, Mapping):
                    continue
                app = raw_app
                writer.writerow([
                    pmt.get("payment_id"),
                    pmt.get("payment_number"),
                    pmt.get("payment_date"),
                    pmt.get("customer_id"),
                    pmt.get("customer_name"),
                    pmt.get("payment_amount"),
                    pmt.get("payment_mode"),
                    pmt.get("reference_number"),
                    app.get("invoice_id"),
                    app.get("invoice_number"),
                    app.get("invoice_date"),
                    app.get("applied_date"),
                    app.get("days_difference"),
                    app.get("mismatch_type"),
                    app.get("amount_applied"),
                ])

    return output.getvalue()
