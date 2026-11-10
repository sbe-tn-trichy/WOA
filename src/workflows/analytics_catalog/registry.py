"""Explicit Analytics consumers; names resolve to stable IDs in each workspace."""

from dataclasses import dataclass
from typing import Literal

from workflows.runtime.config import Config


@dataclass(frozen=True)
class WorkflowViewReference:
    workflow_key: str
    view_name: str
    source_file: str
    usage_type: Literal["read", "create", "update"] = "read"
    view_id: str = ""
    notes: str = ""


def _references(key: str, source: str, names: tuple[str, ...]) -> tuple[WorkflowViewReference, ...]:
    return tuple(WorkflowViewReference(key, name, source) for name in names)


DEFAULT_REFERENCES = (
    *_references("analytics_item_snapshot", "src/workflows/item_catalog/analytics_snapshot.py",
                 ("Accounts (Zoho Books)", "Items (Zoho Books)")),
    *_references("customer_analytics_sync", "src/workflows/customer_analytics_sync.py",
                 ("Customers (Zoho Books)", "Customer Addresses (Zoho Books)",
                  "Customer Contact Persons (Zoho Books)")),
    *_references("customer_normalization", "src/workflows/customer_normalization.py",
                 ("Customers (Zoho Books)", "Customer Addresses (Zoho Books)",
                  "Customer Contact Persons (Zoho Books)")),
    WorkflowViewReference("bank_statement_check", "Bank Statements (Zoho Books)",
                          "src/workflows/bank_statement_check.py", view_id=Config.ANALYTICS_BANK_STATEMENT_VIEW_ID,
                          notes="Read-only HDFC CSV completeness comparison; configurable view ID requires an explicit runtime reference."),
    *_references("unearned_revenue", "src/workflows/unearned_revenue.py",
                 ("Customer Payments (Zoho Books)", "Customers (Zoho Books)",
                  "Accrual Transactions (Zoho Books)", "Accounts (Zoho Books)")),
    WorkflowViewReference("detailed_general_ledger", "detailed general ledger",
                          "okf/analytics-metadata.md", view_id=Config.ANALYTICS_DETAILED_GL_VIEW_ID,
                          notes="FY 2025-26 accrual postings joined to account name and account type."),
    WorkflowViewReference("undeposited_deposit_report", "Undeposited Funds - Deposits and Payment Candidates",
                          "okf/analytics-metadata.md", view_id=Config.ANALYTICS_UNDEPOSITED_CANDIDATES_VIEW_ID,
                          notes="Deposit summary for Undeposited Funds; inferred payment candidates, not confirmed associations."),
    WorkflowViewReference("undeposited_deposit_report", "Undeposited Funds - Deposit Report",
                          "okf/analytics-metadata.md", view_id=Config.ANALYTICS_UNDEPOSITED_REPORT_VIEW_ID,
                          notes="Summary report consuming the deposit candidate query table."),
    WorkflowViewReference("customer_payment_date_check", "Customer Payment vs Applied Date Mismatch",
                          "src/workflows/customer_payment_date_check/checker.py",
                          view_id=Config.ANALYTICS_DATE_MISMATCH_VIEW_ID, notes="Default ID; supply an override for custom deployments."),
    *_references("collection_reconciliation", "src/workflows/collection_reconciliation/reconciler.py",
                 ("Bank Transactions", "Customer Master")),
    *_references("payment_review", "src/workflows/collection_reconciliation/review.py",
                 ("Payment Customer Finder",)),
    *_references("gstr1_verification", "src/workflows/gstr1_verification/analytics.py",
                 ("Locations (Zoho Books)", "Invoices (Zoho Books)", "Credit Notes (Zoho Books)")),
    *_references("gstr1_verification", "src/workflows/gstr1_verification/hsn.py",
                 ("Credit Notes (Zoho Books)", "Credit Note Items (Zoho Books)",
                  "Invoices (Zoho Books)", "Invoice Items (Zoho Books)", "Customers (Zoho Books)")),
    *_references("gstr2_verification", "apps/gst/verify_gstr2.py",
                 ("Bills (Zoho Books)", "Vendors (Zoho Books)", "Expenses (Zoho Books)", "Vendor Credits (Zoho Books)")),
    *_references("payment_inspection", "src/workflows/payment_inspection.py", ("Customer Payments (Zoho Books)",)),
    *_references("payment_renumbering", "src/workflows/payment_renumbering/engine.py", ("Customer Payments (Zoho Books)",)),
    *_references("inter_location_analytics_report", "src/workflows/inter_location_analytics_report.py",
                 ("Customer Payments (Zoho Books)", "Vendor Payments (Zoho Books)", "Locations (Zoho Books)",
                  "Manual Journal Items (Zoho Books)", "Manual Journals (Zoho Books)", "Accounts (Zoho Books)",
                  "Invoice Payments (Zoho Books)", "Invoices (Zoho Books)", "Payments Made (Zoho Books)", "Bills (Zoho Books)")),
    *_references("inter_location_payment_proposals", "src/workflows/inter_location_payment_proposals.py",
                 ("Customer Payments (Zoho Books)", "Vendor Payments (Zoho Books)", "Invoice Payments (Zoho Books)",
                  "Invoices (Zoho Books)", "Payments Made (Zoho Books)", "Bills (Zoho Books)")),
    *_references("monthly_gst_analytics", "apps/gst/check_monthly_gst_analytics.py",
                 ("Accounts (Zoho Books)", "Accrual Transactions (Zoho Books)")),
    WorkflowViewReference("inter_location_analytics_report", "", "src/workflows/inter_location_analytics_report.py",
                          "update", Config.INTER_LOCATION_CONTRA_VIEW_ID, "Default managed query table."),
    WorkflowViewReference("inter_location_contra", "", "apps/inter_location_ops/review_inter_location_contra.py",
                          view_id=Config.INTER_LOCATION_DIFF_VIEW_ID, notes="Default location-difference evidence view."),
    WorkflowViewReference("inter_location_payment_proposals", "", "apps/vendor_payments/propose_inter_location_payment_updates.py",
                          view_id=Config.INTER_LOCATION_CONTRA_VIEW_ID),
    WorkflowViewReference("inter_location_contra", "", "apps/inter_location_ops/propose_inter_location_updates.py",
                          view_id=Config.INTER_LOCATION_CONTRA_VIEW_ID),
)
