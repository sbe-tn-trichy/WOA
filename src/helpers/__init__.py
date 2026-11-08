"""Higher-level overlay helpers and composite operations for Zoho SDK."""

from utils.general_utils.module_aliases import register_module_aliases

_MODULE_ALIASES = {
    "helpers.dates": "helpers.formatting.dates",
    "helpers.gst": "helpers.formatting.gst",
    "helpers.references": "helpers.formatting.references",
    "helpers.sequences": "helpers.formatting.sequences",
    "helpers.files": "helpers.operations.files",
    "helpers.records": "helpers.operations.records",
    "helpers.transactions": "helpers.operations.transactions",
}
register_module_aliases(_MODULE_ALIASES)

from helpers.formatting.sequences import parse_doc_number
from helpers.operations.records import get_verified_record
from helpers.formatting.references import (
    format_reference_lines,
    parse_reference_lines,
    update_reference_lines,
)
from .reports.accounts import (
    extract_bank_deposits,
    extract_bank_withdrawals,
    fetch_bank_accounts_map,
    find_bank_account_by_name,
)
from .catalog.bins import (
    get_bins_by_item_map,
    get_bins_for_items,
    getBinsForItems,
)
from .catalog.contacts import (
    fetch_active_customers_map,
    find_contact_by_gstin,
    find_contact_by_name,
)
from .catalog.custom_fields import (
    ensure_books_custom_fields,
    extract_custom_fields_dict,
    get_custom_field_value,
)
from helpers.formatting.dates import (
    get_financial_year_range,
    get_month_range,
    get_previous_month_range,
    parse_date,
)
from .reports.equity_ledger import EquityLedgerEntry, fetch_equity_general_ledger
from .reports.inter_branch_ledger import (
    InterBranchGeneralLedger,
    InterBranchLedgerEntry,
    fetch_inter_branch_general_ledger,
    fetch_inter_branch_register_transactions,
)
from .reports.profit_and_loss import fetch_profit_and_loss_schedule_format
from helpers.operations.files import (
    download_books_document,
    attach_file_to_books_resource,
    workdrive_upload_and_attach,
    workdrive_upload_file,
)
from helpers.formatting.gst import (
    GSTIN_PATTERN,
    group_contacts_by_gstin,
    is_valid_gstin,
    normalize_gstin,
)
from .catalog.items import (
    fetch_items_by_purchase_account,
    fetch_items_lookup,
    find_item_by_sku_or_name,
    find_item_by_exact_sku,
)
from helpers.operations.transactions import (
    CLOSED_DOCUMENT_STATUSES,
    allocate_documents_fifo,
    fetch_open_bills,
    fetch_open_invoices,
    find_bill_by_number,
    find_transaction_by_number,
    normalize_cheque_number,
    unwrap_record,
)

__all__ = [
    "get_verified_record",
    "download_books_document",
    "format_reference_lines",
    "parse_reference_lines",
    "update_reference_lines",
    "parse_doc_number",
    "EquityLedgerEntry",
    "fetch_equity_general_ledger",
    "InterBranchLedgerEntry",
    "InterBranchGeneralLedger",
    "fetch_inter_branch_general_ledger",
    "fetch_inter_branch_register_transactions",
    "fetch_profit_and_loss_schedule_format",
    # Custom fields
    "get_custom_field_value",
    "extract_custom_fields_dict",
    "ensure_books_custom_fields",
    # Contacts
    "find_contact_by_gstin",
    "find_contact_by_name",
    "fetch_active_customers_map",
    # Items and Bins
    "fetch_items_lookup",
    "fetch_items_by_purchase_account",
    "find_item_by_sku_or_name",
    "find_item_by_exact_sku",
    "get_bins_for_items",
    "getBinsForItems",
    "get_bins_by_item_map",
    # Files
    "workdrive_upload_file",
    "attach_file_to_books_resource",
    "workdrive_upload_and_attach",
    # GST
    "GSTIN_PATTERN",
    "normalize_gstin",
    "is_valid_gstin",
    "group_contacts_by_gstin",
    # Dates
    "parse_date",
    "get_month_range",
    "get_previous_month_range",
    "get_financial_year_range",
    # Bank accounts
    "find_bank_account_by_name",
    "fetch_bank_accounts_map",
    "extract_bank_withdrawals",
    "extract_bank_deposits",
    # Transactions
    "CLOSED_DOCUMENT_STATUSES",
    "find_transaction_by_number",
    "find_bill_by_number",
    "fetch_open_invoices",
    "fetch_open_bills",
    "normalize_cheque_number",
    "allocate_documents_fifo",
    "unwrap_record",
]
