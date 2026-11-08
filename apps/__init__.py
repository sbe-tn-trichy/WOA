"""Operational applications, web servers, and CLI runners for WOA."""

from __future__ import annotations

import importlib
import sys
import types

from . import _bootstrap  # noqa: F401

_REDIRECT_MAP: dict[str, str] = {
    "apps.analyze_project": "apps.tools.analyze_project",
    "apps.cleanup_project": "apps.tools.cleanup_project",
    "apps.generate_api_reference": "apps.tools.generate_api_reference",
    "apps.generate_erp_sdk": "apps.tools.generate_erp_sdk",
    # tools
    "apps.analytics_metadata": "apps.tools.analytics_metadata",
    "apps.download_books_custom_modules": "apps.tools.download_books_custom_modules",
    "apps.open_homepage": "apps.tools.open_homepage",
    # neoseal
    "apps.apply_neoseal_name_updates": "apps.neoseal_items.apply_neoseal_name_updates",
    "apps.audit_neoseal_items": "apps.neoseal_items.audit_neoseal_items",
    "apps.export_neoseal_items": "apps.neoseal_items.export_neoseal_items",
    "apps.format_stock_count": "apps.neoseal_items.format_stock_count",
    "apps.neoseal_stock_count": "apps.neoseal_items.neoseal_stock_count",
    "apps.sync_neoseal_stockcount": "apps.neoseal_items.sync_neoseal_stockcount",
    # gst
    "apps.check_gst_cash_ledger": "apps.gst.check_gst_cash_ledger",
    "apps.check_monthly_gst": "apps.gst.check_monthly_gst",
    "apps.check_monthly_gst_analytics": "apps.gst.check_monthly_gst_analytics",
    "apps.compare_gstr3b_pnl": "apps.gst.compare_gstr3b_pnl",
    "apps.verify_gstr1": "apps.gst.verify_gstr1",
    "apps.verify_gstr2": "apps.gst.verify_gstr2",
    # statements
    "apps.compare_ais": "apps.statements.compare_ais",
    "apps.compare_audited_financials": "apps.statements.compare_audited_financials",
    "apps.compare_it_balance_sheet": "apps.statements.compare_it_balance_sheet",
    "apps.compare_statement_sheet": "apps.statements.compare_statement_sheet",
    "apps.update_books_statement_sheet": "apps.statements.update_books_statement_sheet",
    "apps.update_statement_schedules": "apps.statements.update_statement_schedules",
    # inventory
    "apps.import_polycab_credit": "apps.inventory.import_polycab_credit",
    "apps.import_polycab_rso": "apps.inventory.import_polycab_rso",
    "apps.recover_stock_transfer": "apps.inventory.recover_stock_transfer",
    "apps.review_polycab_vendor_credits": "apps.inventory.review_polycab_vendor_credits",
    "apps.transfer_stock": "apps.inventory.transfer_stock",
    "apps.update_bill_posting_date": "apps.inventory.update_bill_posting_date",
    # inter_location_ops
    "apps.apply_inter_location_updates": "apps.inter_location_ops.apply_inter_location_updates",
    "apps.create_inter_location_contra_query_table": "apps.inter_location_ops.create_inter_location_contra_query_table",
    "apps.manage_inter_location_contra_query_table": "apps.inter_location_ops.manage_inter_location_contra_query_table",
    "apps.move_inter_location_customer_payments": "apps.inter_location_ops.move_inter_location_customer_payments",
    "apps.propose_inter_location_splits": "apps.inter_location_ops.propose_inter_location_splits",
    "apps.propose_inter_location_updates": "apps.inter_location_ops.propose_inter_location_updates",
    "apps.review_inter_location_contra": "apps.inter_location_ops.review_inter_location_contra",
    "apps.update_inter_location_contra_query_table": "apps.inter_location_ops.update_inter_location_contra_query_table",
    # vendor_payments
    "apps.apply_remaining_vendor_payment_proposals": "apps.vendor_payments.apply_remaining_vendor_payment_proposals",
    "apps.propose_fy2526_vendor_payment_updates": "apps.vendor_payments.propose_fy2526_vendor_payment_updates",
    "apps.propose_inter_location_payment_updates": "apps.vendor_payments.propose_inter_location_payment_updates",
    "apps.recheck_inter_location_payment_proposals": "apps.vendor_payments.recheck_inter_location_payment_proposals",
    "apps.show_fy2526_payment_proposals": "apps.vendor_payments.show_fy2526_payment_proposals",
    "apps.update_selected_vendor_payments": "apps.vendor_payments.update_selected_vendor_payments",
    # customers
    "apps.allocate_customer_beats": "apps.customers.allocate_customer_beats",
    "apps.customer_local_store": "apps.customers.customer_local_store",
    "apps.register_customer": "apps.customers.register_customer",
    "apps.review_customer_invoices_payments": "apps.customers.review_customer_invoices_payments",
    "apps.sync_analytics_customers": "apps.customers.sync_analytics_customers",
    "apps.sync_creator_beats": "apps.customers.sync_creator_beats",
    "apps.sync_creator_customers": "apps.customers.sync_creator_customers",
    "apps.sync_customer_numbers": "apps.customers.sync_customer_numbers",
    # bank_collections
    "apps.check_duplicate_payments": "apps.bank_collections.check_duplicate_payments",
    "apps.check_hdfc_statement": "apps.bank_collections.check_hdfc_statement",
    "apps.find_unearned_revenue": "apps.bank_collections.find_unearned_revenue",
    "apps.payment_review": "apps.bank_collections.payment_review",
    "apps.repair_review_payment_allocations": "apps.bank_collections.repair_review_payment_allocations",
    "apps.review_creator_payment_images": "apps.bank_collections.review_creator_payment_images",
    "apps.run_collection_reconciliation": "apps.bank_collections.run_collection_reconciliation",
    # payments
    "apps.backfill_creator_matched_payments": "apps.payments.backfill_creator_matched_payments",
    "apps.backfill_online_payment_creator_fields": "apps.payments.backfill_online_payment_creator_fields",
    "apps.check_customer_payment_dates": "apps.payments.check_customer_payment_dates",
    "apps.find_customer_payment_series": "apps.payments.find_customer_payment_series",
    "apps.renumber_sbe2627_payments": "apps.payments.renumber_sbe2627_payments",
    "apps.update_invoice_payment_dates": "apps.payments.update_invoice_payment_dates",
    # virtual / compatibility
    "apps.request_metrics": "workflows.core.request_metrics",
}


from utils.general_utils.module_aliases import register_module_aliases

register_module_aliases(_REDIRECT_MAP)


def __getattr__(name: str) -> types.ModuleType:
    fullname = f"apps.{name}"
    if fullname in _REDIRECT_MAP:
        target = _REDIRECT_MAP[fullname]
        mod: types.ModuleType = importlib.import_module(target)
        sys.modules[fullname] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
