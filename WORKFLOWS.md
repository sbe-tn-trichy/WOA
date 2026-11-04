# Workflow Catalog

Implemented domain workflows, grouped by purpose. Code and tests are authoritative. Module links point to reusable library code; permanent runners and review interfaces live in [apps](apps/). Configuration and operational contracts are documented in [OKF](okf/index.md).

Operation describes remote effects; read-only workflows may still write local reports.
Preview / write identifies a write-capable command, not a safety certification;
consult its contract and help for exact mutation controls. Library-only and
unverified command ownership are stated explicitly. The listed entry point is
the preferred starting point; additional stages are described below and in contracts.

## GST

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| GSTR-1 verification | [gstr1_verification](src/workflows/gstr1_verification/) | [verify_gstr1.py](apps/verify_gstr1.py) | Read | [Contract](okf/gstr1-verification.md) |
| GSTR-2 / GSTR-2B purchase verification | [gstr2_verification](src/workflows/gstr2_verification/) | [verify_gstr2.py](apps/verify_gstr2.py) | Read | [Contract](okf/gstr2-verification.md) |
| GSTR-3B vs Books P&L comparison | [gstr3b_pnl_comparison](src/workflows/gstr3b_pnl_comparison/) | [compare_gstr3b_pnl.py](apps/compare_gstr3b_pnl.py) | Read | [Contract](okf/gstr3b-pnl-comparison.md) |
| Monthly GST checks | [gst_monthly](src/workflows/gst_monthly.py) | [check_monthly_gst.py](apps/check_monthly_gst.py) | Read | No dedicated OKF contract identified |
| GST cash-ledger comparison | [gst_cash_ledger](src/workflows/gst_cash_ledger.py) | [check_gst_cash_ledger.py](apps/check_gst_cash_ledger.py) | Read | [Contract](okf/gst-cash-ledger.md) |

## Financial reporting

Unearned Revenue candidates (remote read / local reports): [workflow](src/workflows/unearned_revenue.py), run `apps/find_unearned_revenue.py`; [contract and limitations](okf/unearned-revenue.md).

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| AIS master reconciliation | [ais_reconciliation](src/workflows/ais_reconciliation/) | [compare_ais.py](apps/compare_ais.py) | Read | [Contract](okf/ais-reconciliation.md) |
| Audited financial statements and stock comparison | [audited_financials](src/workflows/audited_financials/) | [compare_audited_financials.py](apps/compare_audited_financials.py) | Read | [Contract](okf/audited-financials-comparison.md) |
| Google statement versus Books schedules | [financial_statement_comparison](src/workflows/financial_statement_comparison/) | [compare_statement_sheet.py](apps/compare_statement_sheet.py) | Read | [Contract](okf/financial-statement-comparison.md) |
| Filed IT balance-sheet comparison | [it_balance_sheet_comparison](src/workflows/it_balance_sheet_comparison.py) | [compare_it_balance_sheet.py](apps/compare_it_balance_sheet.py) | Read | [Contract](okf/it-balance-sheet-comparison.md) |
| Books financial-statement sheet updates | [books_statement_sheet](src/workflows/books_statement_sheet.py) | [update_books_statement_sheet.py](apps/update_books_statement_sheet.py) | Preview / write | [Contract](okf/books-statement-sheet.md) |
| NCE document Preparation | [statement_schedules](src/workflows/statement_schedules/) | [update_statement_schedules.py](apps/update_statement_schedules.py) | Preview / write | [Contract](okf/statement-schedules.md) |
| Books P&L note preparation | [books_pnl_notes](src/workflows/books_pnl_notes.py) | [update_books_statement_sheet.py](apps/update_books_statement_sheet.py) | Preview / write | [Contract](okf/books-statement-sheet.md) |
| Books account-catalog synchronization | [books_account_catalog](src/workflows/books_account_catalog.py) | [update_books_statement_sheet.py](apps/update_books_statement_sheet.py) | Read catalog; runner can write Sheet | [Contract](okf/books-statement-sheet.md) |

## Bank and ledger reconciliation

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| **Bank Statement Categorization / Collection Reconciliation** | [collection_reconciliation](src/workflows/collection_reconciliation/) | [payment_review.py](apps/payment_review.py) | Review / write | [Contract](okf/collection-reconciliation.md) |
| HDFC statement completeness | [bank_statement_check](src/workflows/bank_statement_check.py); run `apps/check_hdfc_statement.py` ([contract](okf/bank-statement-check.md)) | [check_hdfc_statement.py](apps/check_hdfc_statement.py) | Read | [Contract](okf/bank-statement-check.md) |
| Bank–vendor ledger matching | [bank_vendor_ledger_matching](src/workflows/bank_vendor_ledger_matching/) | Library API; no dedicated runner identified | Library API; inspect caller | [Contract](okf/bank-vendor-ledger-matching.md) |
| Vendor ledger reconciliation | [vendor_ledger_reconciliation](src/workflows/vendor_ledger_reconciliation/) | Library API; no dedicated runner identified | Library API; inspect caller | No dedicated OKF contract identified |

Bank Statement Categorization includes Creator collection matching, Analytics-assisted customer suggestions, reviewed expense categorization, online-payment allocation review and allocation repair. Its entry points are [payment_review.py](apps/payment_review.py), [run_collection_reconciliation.py](apps/run_collection_reconciliation.py) and [repair_review_payment_allocations.py](apps/repair_review_payment_allocations.py). See [operational documentation](okf/collection-reconciliation.md).

## Customer payments

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| Duplicate payment check | [duplicate_payment_check](src/workflows/duplicate_payment_check/) | [check_duplicate_payments.py](apps/check_duplicate_payments.py) | Read | [Contract](okf/duplicate-payment-check.md) |
| Payment-date checks and corrections | [customer_payment_date_check](src/workflows/customer_payment_date_check/) | [check_customer_payment_dates.py](apps/check_customer_payment_dates.py) | Read; separate date-update runner writes | [Contract](okf/customer-payment-date-mismatch.md) |
| Customer invoice and payment review | [customer_invoice_payment_review](src/workflows/customer_invoice_payment_review.py) | [review_customer_invoices_payments.py](apps/review_customer_invoices_payments.py) | Read | [Contract](okf/customer-invoice-payment-review.md) |
| Payment inspection and numbering-series analysis | [payment_inspection](src/workflows/payment_inspection.py) | [find_customer_payment_series.py](apps/find_customer_payment_series.py) | Read | [Contract](okf/workflow-helpers.md) |
| Payment renumbering | [payment_renumbering](src/workflows/payment_renumbering/) | [renumber_sbe2627_payments.py](apps/renumber_sbe2627_payments.py) | Preview / write | [Contract](okf/workflow-helpers.md) |

## Inter-location accounting

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| Contra posting audit and review | [inter_location_contra](src/workflows/inter_location_contra.py) | [review_inter_location_contra.py](apps/review_inter_location_contra.py) | Read | [Contract](okf/inter-location-contra.md) |
| Analytics contra Query Table management | [inter_location_analytics_report](src/workflows/inter_location_analytics_report.py) | [manage_inter_location_contra_query_table.py](apps/manage_inter_location_contra_query_table.py) | Preview / write | [Contract](okf/inter-location-contra.md) |
| Payment location-change proposals | [inter_location_location_proposals](src/workflows/inter_location_location_proposals.py) | [propose_inter_location_updates.py](apps/propose_inter_location_updates.py) | Read / local proposals | [Contract](okf/inter-location-contra.md) |
| Customer-payment update proposals | [inter_location_payment_proposals](src/workflows/inter_location_payment_proposals.py) | [propose_inter_location_payment_updates.py](apps/propose_inter_location_payment_updates.py) | Read / local proposals | [Contract](okf/inter-location-contra.md) |
| Customer-payment location and numbering batch updates | [inter_location_payment_updates](src/workflows/inter_location_payment_updates.py) | [move_inter_location_customer_payments.py](apps/move_inter_location_customer_payments.py) | Plan / write | [Contract](okf/inter-location-contra.md) |
| Live-verified customer-payment location moves | [apply_inter_location_updates](src/workflows/apply_inter_location_updates.py) | [apply_inter_location_updates.py](apps/apply_inter_location_updates.py) | Verify / write | [Contract](okf/inter-location-contra.md) |
| Payment split proposals | [inter_location_split_proposals](src/workflows/inter_location_split_proposals.py) | [propose_inter_location_splits.py](apps/propose_inter_location_splits.py) | Read / local proposals | [Contract](okf/inter-location-contra.md) |
| Vendor-payment move proposals | [inter_location_vendor_payment_proposals](src/workflows/inter_location_vendor_payment_proposals.py) | [propose_fy2526_vendor_payment_updates.py](apps/propose_fy2526_vendor_payment_updates.py) | Read / local proposals | [Contract](okf/inter-location-contra.md) |
| Reviewed vendor-payment updates | [inter_location_vendor_payment_updates](src/workflows/inter_location_vendor_payment_updates.py) | [update_selected_vendor_payments.py](apps/update_selected_vendor_payments.py) | Review / write | [Contract](okf/inter-location-contra.md) |

## Creator synchronization

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| Books-to-Creator customer creation and updates | [creator_customer_sync](src/workflows/creator_customer_sync/) | [sync_creator_customers.py](apps/sync_creator_customers.py) | Preview / write | [Contract](okf/creator-customer-delete-sync.md) |
| Customer deletion synchronization | [creator_customer_delete_sync](src/workflows/creator_customer_delete_sync/) | Library API; no dedicated runner identified | Library API; deletes Creator records | [Contract](okf/creator-customer-delete-sync.md) |
| Customer beat allocation | [creator_beat_allocation](src/workflows/creator_beat_allocation.py) | [allocate_customer_beats.py](apps/allocate_customer_beats.py) | Review UI / write | [Contract](okf/creator-customer-delete-sync.md) |
| Assigned Creator beats to Books contacts | [creator_beat_sync](src/workflows/creator_beat_sync.py) | [sync_creator_beats.py](apps/sync_creator_beats.py) | Preview / write | [Contract](okf/creator-customer-delete-sync.md) |
| Books-payment link backfill | [creator_books_payment_link](src/workflows/creator_books_payment_link.py) | [backfill_creator_matched_payments.py](apps/backfill_creator_matched_payments.py) | Preview / write | [Contract](okf/workflow-helpers.md) |
| Online-payment Creator-field backfill | [online_payment_creator_backfill](src/workflows/online_payment_creator_backfill.py) | [backfill_online_payment_creator_fields.py](apps/backfill_online_payment_creator_fields.py) | Preview / write | [Contract](okf/workflow-helpers.md) |

## Customers and sales

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| Customer contact validation | [customer_validation](src/workflows/customer_validation/) | Library API; no dedicated runner identified | Library API; validation | [Contract](okf/customer-registration.md) |
| Analytics customer sync and local cleanup (primary CLI: `apps/sync_analytics_customers.py`) | [customer_analytics_sync](src/workflows/customer_analytics_sync.py) | [sync_analytics_customers.py](apps/sync_analytics_customers.py) | Remote read / local SQLite write | [Contract](okf/customer-local-store.md) |
| Sales-order import from invoice YAML | [sales_order_import](src/workflows/sales_order_import/) | Library API; no dedicated runner identified | Library API; creates sales orders | No dedicated OKF contract identified |
| Polycab return-sales-order PDF import | [polycab_rso](src/workflows/polycab_rso/) | [import_polycab_rso.py](apps/import_polycab_rso.py) | Write on invocation | [Contract](okf/polycab-rso-import.md) |

[register_customer.py](apps/register_customer.py) additionally supports Creator customer-registration form inspection and record creation directly in the application layer.

## Vendor transactions

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| Polycab credit-memo processing and attachments (primary CLI: `apps/import_polycab_credit.py`; preview by default) | [polycab_credit_memos](src/workflows/polycab_credit_memos/) | [import_polycab_credit.py](apps/import_polycab_credit.py) | Preview / write | [Contract](okf/polycab-credit-import.md) |
| Polycab vendor-credit review and correction | [polycab_credit_review](src/workflows/polycab_credit_review/) | [review_polycab_vendor_credits.py](apps/review_polycab_vendor_credits.py) | Review / write | [Contract](okf/polycab-credit-review.md) |
| GSTIN-checked vendor–customer payment offset | [vendor_customer_offset](src/workflows/vendor_customer_offset/) | Library API; no dedicated runner identified | Library API; creates paired payments | [Contract](okf/vendor-customer-offset.md) |
| Bill updates with payment preservation and posting-date updates | [bill_updates](src/workflows/bill_updates.py) | [update_bill_posting_date.py](apps/update_bill_posting_date.py) | Write-capable; inspect arguments | [Contract](okf/workflow-helpers.md) |

## Inventory and Neoseal

| Workflow | Module | Primary entry point | Operation | Contract |
|---|---|---|---|---|
| Neoseal item audit, catalog export and name updates | [neoseal_audit](src/workflows/neoseal_audit/) | [audit_neoseal_items.py](apps/audit_neoseal_items.py) | Read; separate name-update runner writes | [Contract](okf/neoseal-item-audit.md) |
| Neoseal stock count, sheet formatting and synchronization | [neoseal_stock_count](src/workflows/neoseal_stock_count/) | [neoseal_stock_count.py](apps/neoseal_stock_count.py) | Writes Sheet on invocation | [Contract](okf/neoseal-stock-count.md) |
| Paired stock transfer | [stock_transfer](src/workflows/stock_transfer/) | [transfer_stock.py](apps/transfer_stock.py) | Preview / write | [Contract](okf/stock-transfer.md) |

## Running workflows

Run applications from the repository root using the workspace environment. For example:

```powershell
.\.venv\Scripts\python.exe apps/payment_review.py --help
.\.venv\Scripts\python.exe apps/verify_gstr2.py --help
.\.venv\Scripts\python.exe apps/neoseal_stock_count.py --help
```

Use each app's help and relevant OKF documentation for configuration, arguments and mutation controls. Some workflows are library APIs without a dedicated runner. [dashboard.py](apps/dashboard.py) provides a launcher for common workflows.

## Shared infrastructure

[workflows.core](src/workflows/core/) contains authentication factories, configuration, matching, dates, sequences, checkpoints, snapshots and payment primitives. It is shared infrastructure rather than a standalone business workflow. Empty and cache-only directories are excluded from this catalog.

Customer registration in Books and Creator (creates remote records): [customer_registration](src/workflows/customer_registration/), run with [register_customer.py](apps/register_customer.py). See [usage and recovery](okf/customer-registration.md).

Creator customer-number backfill: [sync_customer_numbers.py](apps/sync_customer_numbers.py), using [customer_registration](src/workflows/customer_registration/) with explicit Books IDs and a dry-run default.

### Creator payment image OCR

Read-only remote review: run `.venv/bin/python apps/review_creator_payment_images.py` to download and review online and cheque payment evidence. See [workflow documentation](okf/creator-payment-ocr.md) for filters, output, and OCR limitations.
