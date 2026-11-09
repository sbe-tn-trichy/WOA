"""Find customer payments where payment date and applied dates differ using Zoho Analytics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from collections.abc import Iterable, Mapping
from typing import Protocol

from helpers import parse_date
from workflows.core.matching import to_finite_decimal
from workflows.runtime.config import Config


DEFAULT_WORKSPACE_ID = Config.ANALYTICS_WORKSPACE_ID
DEFAULT_DATE_MISMATCH_VIEW_ID = Config.ANALYTICS_DATE_MISMATCH_VIEW_ID


class _ViewsExportResource(Protocol):
    def export_all(self, workspace_id: str, view_id: str) -> list[dict[str, object]]: ...


class AnalyticsExportClient(Protocol):
    @property
    def views(self) -> _ViewsExportResource: ...


@dataclass(frozen=True)
class InvoiceApplicationMismatch:
    invoice_id: str
    invoice_number: str
    invoice_date: str | None
    applied_date: str
    amount_applied: Decimal
    days_difference: int  # applied_date - payment_date
    mismatch_type: str  # "Applied After Payment", "Applied Before Payment"

    def as_dict(self) -> dict[str, object]:
        return {
            "invoice_id": self.invoice_id,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "applied_date": self.applied_date,
            "amount_applied": format(self.amount_applied, "f"),
            "days_difference": self.days_difference,
            "mismatch_type": self.mismatch_type,
        }


@dataclass
class PaymentDateMismatchRecord:
    payment_id: str
    payment_number: str
    payment_date: str
    customer_id: str
    customer_name: str
    payment_amount: Decimal
    unused_amount: Decimal
    reference_number: str
    payment_mode: str
    mismatched_applications: list[InvoiceApplicationMismatch]

    def as_dict(self) -> dict[str, object]:
        return {
            "payment_id": self.payment_id,
            "payment_number": self.payment_number,
            "payment_date": self.payment_date,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "payment_amount": format(self.payment_amount, "f"),
            "unused_amount": format(self.unused_amount, "f"),
            "reference_number": self.reference_number,
            "payment_mode": self.payment_mode,
            "mismatch_count": len(self.mismatched_applications),
            "mismatched_applications": [app.as_dict() for app in self.mismatched_applications],
        }


class AnalyticsCustomerPaymentDateChecker:
    """Audit of payment date vs applied date using Zoho Analytics."""

    def __init__(
        self,
        analytics_client: AnalyticsExportClient,
        workspace_id: str = DEFAULT_WORKSPACE_ID,
        view_id: str = DEFAULT_DATE_MISMATCH_VIEW_ID,
    ):
        self.analytics = analytics_client
        self.workspace_id = workspace_id
        self.view_id = view_id

    def run(
        self,
        *,
        from_date: str | None = None,
        to_date: str | None = None,
        customer_id: str | None = None,
        tolerance_days: int = 0,
    ) -> dict[str, object]:
        start = parse_date(from_date) if from_date else None
        end = parse_date(to_date) if to_date else None
        if from_date and not start:
            raise ValueError("from_date must use YYYY-MM-DD format.")
        if to_date and not end:
            raise ValueError("to_date must use YYYY-MM-DD format.")
        if start and end and start > end:
            raise ValueError("from_date cannot be later than to_date.")
        if tolerance_days < 0:
            raise ValueError("tolerance_days cannot be negative.")

        rows = self.analytics.views.export_all(self.workspace_id, self.view_id)
        return self.process_rows(
            rows,
            tolerance_days=tolerance_days,
            from_date=start,
            to_date=end,
            customer_id=customer_id,
        )

    def process_rows(
        self,
        rows: Iterable[Mapping[str, object]],
        tolerance_days: int = 0,
        from_date: date | None = None,
        to_date: date | None = None,
        customer_id: str | None = None,
    ) -> dict[str, object]:
        from collections import defaultdict

        headers: dict[str, dict[str, object]] = {}
        applications: dict[str, list[InvoiceApplicationMismatch]] = defaultdict(list)

        def _get_val(row_dict: Mapping[str, object], *keys: str) -> object:
            for k in keys:
                if k in row_dict and row_dict[k] is not None:
                    return row_dict[k]
                # Also check case-insensitive match
                for rk, rv in row_dict.items():
                    if rk.lower() == k.lower() or rk.lower().endswith("." + k.lower()):
                        if rv is not None:
                            return rv
            return None

        def _parse_amount(raw_val: object) -> Decimal:
            if not raw_val:
                return Decimal("0")
            cleaned = str(raw_val).replace("INR", "").replace("₹", "").replace(",", "").strip()
            return to_finite_decimal(cleaned, allow_commas=True) or Decimal("0")

        for row in rows:
            pmt_num = str(_get_val(row, "Payment Number", "cp.Payment Number", "payment_number") or "").strip()
            pmt_id = str(_get_val(row, "Payment ID", "cp.Payment ID", "payment_id") or pmt_num).strip()
            if not pmt_num:
                continue

            raw_pmt_date = _get_val(row, "Payment Date", "cp.Payment Date", "payment_date")
            pmt_date_obj = parse_date(raw_pmt_date)
            if not pmt_date_obj:
                continue

            if from_date and pmt_date_obj < from_date:
                continue
            if to_date and pmt_date_obj > to_date:
                continue

            row_cust_id = str(_get_val(row, "Customer ID", "cp.Customer ID", "customer_id") or "").strip()
            if customer_id and row_cust_id and row_cust_id != customer_id:
                continue

            if pmt_num not in headers:
                headers[pmt_num] = {
                    "payment_id": pmt_id,
                    "payment_number": pmt_num,
                    "payment_date": pmt_date_obj.isoformat(),
                    "customer_id": row_cust_id,
                    "customer_name": str(_get_val(row, "Customer Name", "c.Customer Name", "customer_name") or "").strip(),
                    "payment_amount": _parse_amount(_get_val(row, "Payment_Amount", "Amount (BCY)", "Amount")),
                    "unused_amount": _parse_amount(_get_val(row, "Unused Amount (BCY)", "Unused Amount")),
                    "reference_number": str(_get_val(row, "Reference Number", "cp.Reference Number") or "").strip(),
                    "payment_mode": str(_get_val(row, "Payment Mode", "cp.Payment Mode") or "").strip(),
                }

            inv_num = str(_get_val(row, "Invoice Number", "inv.Invoice Number", "invoice_number") or "").strip()
            inv_id = str(_get_val(row, "Invoice ID", "ip.Invoice ID", "inv.Invoice ID", "invoice_id") or "").strip()
            raw_inv_date = _get_val(row, "Invoice Date", "inv.Invoice Date", "invoice_date")
            inv_date_obj = parse_date(raw_inv_date)

            raw_applied_date = _get_val(
                row,
                "Invoice Payment Applied Date",
                "ip.Invoice Payment Applied Date",
                "Date Applied",
                "Applied Date",
            ) or raw_inv_date
            applied_date_obj = parse_date(raw_applied_date)

            if applied_date_obj:
                days_diff = (applied_date_obj - pmt_date_obj).days
                if abs(days_diff) > tolerance_days:
                    amt_applied = _parse_amount(_get_val(row, "Amount Applied", "Amount (BCY)", "ip.Amount (BCY)", "amount_applied"))
                    mismatch_type = str(_get_val(row, "Mismatch Type") or ("Applied After Payment" if days_diff > 0 else "Applied Before Payment"))
                    applications[pmt_num].append(
                        InvoiceApplicationMismatch(
                            invoice_id=inv_id,
                            invoice_number=inv_num,
                            invoice_date=inv_date_obj.isoformat() if inv_date_obj else None,
                            applied_date=applied_date_obj.isoformat(),
                            amount_applied=amt_applied,
                            days_difference=days_diff,
                            mismatch_type=mismatch_type,
                        )
                    )

        mismatches: list[PaymentDateMismatchRecord] = []
        for pmt_num, app_list in applications.items():
            if app_list and pmt_num in headers:
                hdr = headers[pmt_num]
                mismatches.append(
                    PaymentDateMismatchRecord(
                        payment_id=str(hdr["payment_id"]),
                        payment_number=str(hdr["payment_number"]),
                        payment_date=str(hdr["payment_date"]),
                        customer_id=str(hdr["customer_id"]),
                        customer_name=str(hdr["customer_name"]),
                        payment_amount=hdr["payment_amount"] if isinstance(hdr["payment_amount"], Decimal) else Decimal("0"),
                        unused_amount=hdr["unused_amount"] if isinstance(hdr["unused_amount"], Decimal) else Decimal("0"),
                        reference_number=str(hdr["reference_number"]),
                        payment_mode=str(hdr["payment_mode"]),
                        mismatched_applications=app_list,
                    )
                )

        mismatches.sort(key=lambda x: (x.payment_date, x.customer_name, x.payment_number))
        total_mismatched_apps = sum(len(m.mismatched_applications) for m in mismatches)

        return {
            "view_id": self.view_id,
            "payments_scanned": len(headers),
            "mismatched_payments_count": len(mismatches),
            "total_mismatched_applications": total_mismatched_apps,
            "tolerance_days": tolerance_days,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "mismatches": [m.as_dict() for m in mismatches],
        }


def check_customer_payment_dates_analytics(
    analytics_client: AnalyticsExportClient,
    *,
    workspace_id: str = DEFAULT_WORKSPACE_ID,
    view_id: str = DEFAULT_DATE_MISMATCH_VIEW_ID,
    from_date: str | None = None,
    to_date: str | None = None,
    customer_id: str | None = None,
    tolerance_days: int = 0,
) -> dict[str, object]:
    """Audit customer payment vs applied dates via Analytics."""
    checker = AnalyticsCustomerPaymentDateChecker(
        analytics_client=analytics_client,
        workspace_id=workspace_id,
        view_id=view_id,
    )
    return checker.run(
        from_date=from_date,
        to_date=to_date,
        customer_id=customer_id,
        tolerance_days=tolerance_days,
    )
