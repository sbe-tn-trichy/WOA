"""Customer management: analytics sync, invoice/payment review, normalization, and local store."""
from __future__ import annotations

from .analytics_sync import (
    CustomerAnalyticsSyncResult,
    sync_analytics_customers,
)
from .invoice_payment_review import (
    CustomerInvoicePaymentReview,
    InvoicePaymentRow,
    PaymentAllocationRow,
    invoice_discount_percentage,
    review_customer_invoices_payments,
)
from .local_store import (
    export_pending,
    open_store,
    stage_creator_beats_locally,
    stage_mobile_plan,
    sync_customers,
)
from .normalization import (
    Correction,
    CustomerNormalizationResult,
    ReviewIssue,
    SOURCE_NAMES,
    build_normalized_customers,
    download_customer_normalization_sources,
)
from .table import (
    compact_customer_columns,
    customer_json,
)

__all__ = [
    "CustomerAnalyticsSyncResult",
    "sync_analytics_customers",
    "CustomerInvoicePaymentReview",
    "InvoicePaymentRow",
    "PaymentAllocationRow",
    "invoice_discount_percentage",
    "review_customer_invoices_payments",
    "export_pending",
    "open_store",
    "stage_creator_beats_locally",
    "stage_mobile_plan",
    "sync_customers",
    "Correction",
    "CustomerNormalizationResult",
    "ReviewIssue",
    "SOURCE_NAMES",
    "build_normalized_customers",
    "download_customer_normalization_sources",
    "compact_customer_columns",
    "customer_json",
]
