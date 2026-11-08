---
type: Plan
---

# Centralized test migration

Prepared 2026-11-07. Related finding: APPS-006 in
[the finding register](../PROJECT_ANALYSIS.md).
Implemented 2026-11-07: 135 test/support files centralized. Collection preserves
all 2,876 default cases and 13 explicit metadata cases. Windows AMD64 CPython
3.14.10: default suite 2,874 passed, 2 skipped, 4 subtests passed (12.08s); explicit
metadata 13 passed (4.59s). macOS and hosted CI were not run.

## Target organization

Mirror canonical source ownership beneath the root `tests/` directory:

```text
tests/
  zoho/
    books/
    inventory/
    analytics/
    helpers/
    transport/
  google_sheets/
  workflows/
    core/
    collection_reconciliation/
    gstr1_verification/
    ... other canonical workflow packages ...
  apps/
    ... application domains matching apps/ ...
  contracts/
    ... packaging, architecture and cross-layer regression contracts ...
  typecheck/
```

Direct SDK modules such as auth/security/base_resource belong directly under
`tests/zoho/` where the ten-file limit permits. `transport/` groups shared client
transport contracts. Domain tests follow the actual canonical package, including
`books_statements`, `customer_management`, `gst` and `inter_location`; legacy
workflow alias names do not create new test categories. Generated ERP tests belong
under `tests/zoho/erp/`. Tests for `apps/` mirror its domains rather than `src/`.
Cross-layer contract files retain cohesive ownership under `contracts/` unless
review establishes independent responsibilities worth separating.

The depth policy currently applies to apps, source workflows and output, not the
root tests tree. Centralizing domain tests therefore removes nested source test
directories without requiring a change to that configured depth. Keep destination
directories within ten files by adding meaningful responsibility groups when
needed; do not invent numbered buckets merely to satisfy the count.

## Migration sequence and acceptance

1. Capture collected node IDs/counts for default discovery and the separately
   excluded metadata module. Inventory helper modules, fixtures and non-test
   assets with each source test directory. Classify by asserted behavior, using
   the import inventory below as candidates rather than automatic destinations.
2. Move each of the eleven source workflow `tests/` directories to
   `tests/workflows/<canonical-package>/`. Retain all test functions and fixtures;
   preserve duplicate filenames through domain subdirectories and importlib mode.
3. Move existing root tests into SDK, workflow, apps and contract categories.
   Inspect mixed files such as `test_books.py`, `test_security.py`,
   `test_performance.py` and `test_type_safety.py` individually. Avoid broad
   test rewrites in a location-only migration.
4. Repair file-relative fixtures, subprocess paths, patch targets, explicit test
   references in documentation/CI and the type-checker targets. Keep production
   imports canonical. Retain root `tests/__init__.py` if still required; add
   package markers only where import behavior requires them. There are no current
   conftest.py files in the inspected checkout; do not introduce global fixture
   scope without a concrete dependency.
5. Set pytest testpaths to `tests` once source test migration is complete. Update
   the metadata ignore path to its new destination, preserving explicit module
   execution. Update typecheck paths only if those files move. Inspect analyzer
   affected-test detection for the new layout.
6. Verify one-to-one old/new node-ID mapping and equal case counts, default and
   explicit metadata collection, targeted moved modules, full parallel suite,
   API-reference check and mypy. Compare skip reasons and check duplicate-module
   imports. Windows verification is required locally; Mac/hosted evidence remains
   a separate requirement. Do not close APPS-006 until its other folder-policy
   discrepancies are resolved.
7. Update the owning organization concept, command references, finding register
   and changelog in the implementation change. Remove empty source test folders
   only after verifying they contain no remaining assets.

## Implemented path mapping

Cross-test imports and project-root-relative asset paths were repaired. Discovery
searches only `tests/`; metadata exclusion follows its new SDK path. Compiler
fixtures retain `tests/typecheck/` paths. The analyzer already recognizes nested
tests by the `tests/` prefix; no implementation change was required. Mixed
regression files remain cohesive under contracts. SDK Books tests retain related
workflow integration assertions. No new fixture scope was introduced.

| Previous path | Current path |
|---|---|
| `src/workflows/bank_vendor_ledger_matching/tests/test_bank_matching.py` | `tests/workflows/bank_vendor_ledger_matching/test_bank_matching.py` |
| `src/workflows/collection_reconciliation/tests/test_bank_statement.py` | `tests/workflows/collection_reconciliation/test_bank_statement.py` |
| `src/workflows/collection_reconciliation/tests/test_bank_transfers.py` | `tests/workflows/collection_reconciliation/test_bank_transfers.py` |
| `src/workflows/collection_reconciliation/tests/test_collection_reconciliation.py` | `tests/workflows/collection_reconciliation/test_collection_reconciliation.py` |
| `src/workflows/collection_reconciliation/tests/test_online_payment_review.py` | `tests/workflows/collection_reconciliation/test_online_payment_review.py` |
| `src/workflows/collection_reconciliation/tests/test_review_efficiency.py` | `tests/workflows/collection_reconciliation/test_review_efficiency.py` |
| `src/workflows/core/tests/test_auth_factories.py` | `tests/workflows/runtime/test_auth_factories.py` |
| `src/workflows/core/tests/test_checkpoint.py` | `tests/workflows/core/test_checkpoint.py` |
| `src/workflows/core/tests/test_payments.py` | `tests/workflows/core/test_payments.py` |
| `src/workflows/core/tests/test_snapshots.py` | `tests/workflows/core/test_snapshots.py` |
| `src/workflows/core/tests/test_usability.py` | `tests/workflows/core/test_usability.py` |
| `src/workflows/duplicate_payment_check/tests/test_duplicate_payment_check.py` | `tests/workflows/duplicate_payment_check/test_duplicate_payment_check.py` |
| `src/workflows/duplicate_payment_check/tests/test_reporting.py` | `tests/workflows/duplicate_payment_check/test_reporting.py` |
| `src/workflows/gstr1_verification/tests/test_analytics.py` | `tests/workflows/gstr1_verification/test_analytics.py` |
| `src/workflows/gstr1_verification/tests/test_hsn.py` | `tests/workflows/gstr1_verification/test_hsn.py` |
| `src/workflows/gstr1_verification/tests/test_report.py` | `tests/workflows/gstr1_verification/test_report.py` |
| `src/workflows/gstr1_verification/tests/test_verifier.py` | `tests/workflows/gstr1_verification/test_verifier.py` |
| `src/workflows/gstr2_verification/tests/test_annual.py` | `tests/workflows/gstr2_verification/test_annual.py` |
| `src/workflows/gstr2_verification/tests/test_bill_snapshot.py` | `tests/workflows/gstr2_verification/test_bill_snapshot.py` |
| `src/workflows/gstr2_verification/tests/test_purchase_snapshot.py` | `tests/workflows/gstr2_verification/test_purchase_snapshot.py` |
| `src/workflows/gstr2_verification/tests/test_verifier.py` | `tests/workflows/gstr2_verification/test_verifier.py` |
| `src/workflows/gstr3b_pnl_comparison/tests/test_comparison.py` | `tests/workflows/gstr3b_pnl_comparison/test_comparison.py` |
| `src/workflows/polycab_credit_memos/tests/test_batch.py` | `tests/workflows/polycab_credit_memos/test_batch.py` |
| `src/workflows/polycab_credit_memos/tests/test_processor.py` | `tests/workflows/polycab_credit_memos/test_processor.py` |
| `src/workflows/polycab_rso/tests/__init__.py` | `tests/workflows/polycab_rso/__init__.py` |
| `src/workflows/polycab_rso/tests/test_processor.py` | `tests/workflows/polycab_rso/test_processor.py` |
| `src/workflows/vendor_customer_offset/tests/test_vendor_customer_offset.py` | `tests/workflows/vendor_customer_offset/test_vendor_customer_offset.py` |
| `src/workflows/vendor_ledger_reconciliation/tests/test_cleaner.py` | `tests/workflows/vendor_ledger_reconciliation/test_cleaner.py` |
| `src/workflows/vendor_ledger_reconciliation/tests/test_vendor_ledger_matching.py` | `tests/workflows/vendor_ledger_reconciliation/test_vendor_ledger_matching.py` |
| `src/workflows/vendor_ledger_reconciliation/tests/test_zeiss_pdf.py` | `tests/workflows/vendor_ledger_reconciliation/test_zeiss_pdf.py` |
| `tests/manual_analytics_query.py` | `tests/zoho/analytics/manual_analytics_query.py` |
| `tests/test_ais_reconciliation.py` | `tests/workflows/ais_reconciliation/test_ais_reconciliation.py` |
| `tests/test_analytics.py` | `tests/zoho/analytics/test_analytics.py` |
| `tests/test_analytics_catalog.py` | `tests/workflows/analytics_catalog/test_analytics_catalog.py` |
| `tests/test_analytics_metadata.py` | `tests/zoho/analytics/test_analytics_metadata.py` |
| `tests/test_api_reference_generator.py` | `tests/apps/tools/test_api_reference_generator.py` |
| `tests/test_apply_inter_location_updates.py` | `tests/workflows/inter_location/test_apply_inter_location_updates.py` |
| `tests/test_apply_neoseal_name_updates.py` | `tests/apps/neoseal_items/test_apply_neoseal_name_updates.py` |
| `tests/test_audit_remediation.py` | `tests/contracts/security/test_audit_remediation.py` |
| `tests/test_audited_financials.py` | `tests/workflows/audited_financials/test_audited_financials.py` |
| `tests/test_auth.py` | `tests/zoho/core_sdk/test_auth.py` |
| `tests/test_backfill_creator_matched_payments.py` | `tests/apps/payments/test_backfill_creator_matched_payments.py` |
| `tests/test_backfill_online_payment_creator_fields.py` | `tests/apps/payments/test_backfill_online_payment_creator_fields.py` |
| `tests/test_bank_statement_check.py` | `tests/workflows/bank_statements/test_bank_statement_check.py` |
| `tests/test_bill_updates.py` | `tests/workflows/purchasing/test_bill_updates.py` |
| `tests/test_books.py` | `tests/zoho/books/test_books.py` |
| `tests/test_books_account_catalog.py` | `tests/workflows/books_statements/test_books_account_catalog.py` |
| `tests/test_books_account_transactions.py` | `tests/zoho/books/test_books_account_transactions.py` |
| `tests/test_books_custom_module_store.py` | `tests/workflows/books_statements/test_books_custom_module_store.py` |
| `tests/test_books_general_ledger_details.py` | `tests/zoho/books/test_books_general_ledger_details.py` |
| `tests/test_books_general_ledger_report.py` | `tests/zoho/books/test_books_general_ledger_report.py` |
| `tests/test_books_pnl_notes.py` | `tests/workflows/books_statements/test_books_pnl_notes.py` |
| `tests/test_books_registers.py` | `tests/zoho/books/test_books_registers.py` |
| `tests/test_books_statement_sheet.py` | `tests/workflows/books_statements/test_books_statement_sheet.py` |
| `tests/test_cliq.py` | `tests/zoho/cliq/test_cliq.py` |
| `tests/test_creator.py` | `tests/zoho/creator/test_creator.py` |
| `tests/test_creator_beat_allocation.py` | `tests/workflows/customer_management/test_creator_beat_allocation.py` |
| `tests/test_creator_beat_sync.py` | `tests/workflows/customer_management/test_creator_beat_sync.py` |
| `tests/test_creator_beats_local.py` | `tests/workflows/customer_management/test_creator_beats_local.py` |
| `tests/test_creator_customer_sync.py` | `tests/workflows/creator_customer_sync/test_creator_customer_sync.py` |
| `tests/test_creator_customer_sync_deletions.py` | `tests/workflows/creator_customer_sync/test_creator_customer_sync_deletions.py` |
| `tests/test_creator_payment_ocr.py` | `tests/workflows/creator_payments/test_creator_payment_ocr.py` |
| `tests/test_customer_analytics_sync.py` | `tests/workflows/customer_management/test_customer_analytics_sync.py` |
| `tests/test_customer_invoice_payment_review.py` | `tests/workflows/customer_management/test_customer_invoice_payment_review.py` |
| `tests/test_customer_local_store.py` | `tests/workflows/customer_management/test_customer_local_store.py` |
| `tests/test_customer_normalization.py` | `tests/workflows/customer_management/test_customer_normalization.py` |
| `tests/test_customer_number_sync.py` | `tests/workflows/customer_management/test_customer_number_sync.py` |
| `tests/test_customer_payment_date_check.py` | `tests/workflows/customer_payment_date_check/test_customer_payment_date_check.py` |
| `tests/test_customer_payment_number_series_update.py` | `tests/zoho/books/test_customer_payment_number_series_update.py` |
| `tests/test_customer_registration.py` | `tests/workflows/customer_registration/test_customer_registration.py` |
| `tests/test_deduplication_regression.py` | `tests/contracts/architecture/test_deduplication_regression.py` |
| `tests/test_efficiency_changes.py` | `tests/contracts/performance/test_efficiency_changes.py` |
| `tests/test_equity_ledger_helper.py` | `tests/helpers/reports/test_equity_ledger_helper.py` |
| `tests/test_erp_sdk.py` | `tests/zoho/erp/test_erp_sdk.py` |
| `tests/test_export_neoseal_items.py` | `tests/apps/neoseal_items/test_export_neoseal_items.py` |
| `tests/test_financial_statement_comparison.py` | `tests/workflows/financial_statement_comparison/test_financial_statement_comparison.py` |
| `tests/test_finding_regressions.py` | `tests/contracts/security/test_finding_regressions.py` |
| `tests/test_google_sheets_sdk.py` | `tests/google_sheets/test_google_sheets_sdk.py` |
| `tests/test_gst_cash_ledger.py` | `tests/workflows/gst/test_gst_cash_ledger.py` |
| `tests/test_gst_monthly.py` | `tests/workflows/gst/test_gst_monthly.py` |
| `tests/test_gstin_alias_config.py` | `tests/workflows/runtime/test_gstin_alias_config.py` |
| `tests/test_gstr2_total_mismatch.py` | `tests/workflows/gstr2_verification/test_gstr2_total_mismatch.py` |
| `tests/test_hardening_followup.py` | `tests/contracts/security/test_hardening_followup.py` |
| `tests/test_helper_extractions.py` | `tests/contracts/architecture/test_helper_extractions.py` |
| `tests/test_helpers.py` | `tests/helpers/test_helpers.py` |
| `tests/test_inter_branch_ledger_helper.py` | `tests/helpers/reports/test_inter_branch_ledger_helper.py` |
| `tests/test_inter_location_analytics_report.py` | `tests/workflows/inter_location/test_inter_location_analytics_report.py` |
| `tests/test_inter_location_contra.py` | `tests/workflows/inter_location/test_inter_location_contra.py` |
| `tests/test_inter_location_location_proposals.py` | `tests/workflows/inter_location/test_inter_location_location_proposals.py` |
| `tests/test_inter_location_payment_proposals.py` | `tests/workflows/inter_location/test_inter_location_payment_proposals.py` |
| `tests/test_inter_location_payment_updates.py` | `tests/workflows/inter_location/test_inter_location_payment_updates.py` |
| `tests/test_inter_location_query_table_apps.py` | `tests/apps/inter_location_ops/test_inter_location_query_table_apps.py` |
| `tests/test_inter_location_split_proposals.py` | `tests/workflows/inter_location/test_inter_location_split_proposals.py` |
| `tests/test_inter_location_vendor_payment_proposals.py` | `tests/workflows/inter_location/test_inter_location_vendor_payment_proposals.py` |
| `tests/test_inter_location_vendor_payment_updates.py` | `tests/workflows/inter_location/test_inter_location_vendor_payment_updates.py` |
| `tests/test_inventory.py` | `tests/zoho/inventory/test_inventory.py` |
| `tests/test_inventory_routing.py` | `tests/contracts/architecture/test_inventory_routing.py` |
| `tests/test_it_balance_sheet_comparison.py` | `tests/workflows/books_statements/test_it_balance_sheet_comparison.py` |
| `tests/test_item_catalog_export.py` | `tests/workflows/item_catalog_export/test_item_catalog_export.py` |
| `tests/test_mail.py` | `tests/zoho/mail/test_mail.py` |
| `tests/test_neoseal_item_audit.py` | `tests/workflows/neoseal_audit/test_neoseal_item_audit.py` |
| `tests/test_neoseal_stable_sync.py` | `tests/workflows/neoseal_stock_count/test_neoseal_stable_sync.py` |
| `tests/test_neoseal_stock_count.py` | `tests/workflows/neoseal_stock_count/test_neoseal_stock_count.py` |
| `tests/test_package_imports.py` | `tests/contracts/architecture/test_package_imports.py` |
| `tests/test_performance.py` | `tests/contracts/performance/test_performance.py` |
| `tests/test_polycab_credit_import.py` | `tests/workflows/polycab_credit_review/test_polycab_credit_import.py` |
| `tests/test_polycab_credit_review.py` | `tests/workflows/polycab_credit_review/test_polycab_credit_review.py` |
| `tests/test_profit_and_loss_schedule_format.py` | `tests/zoho/books/test_profit_and_loss_schedule_format.py` |
| `tests/test_project_analysis.py` | `tests/apps/tools/test_project_analysis.py` |
| `tests/test_project_cleanup.py` | `tests/apps/tools/test_project_cleanup.py` |
| `tests/test_project_dashboard.py` | `tests/apps/test_project_dashboard.py` |
| `tests/test_recheck_inter_location_payment_proposals.py` | `tests/apps/inter_location_ops/test_recheck_inter_location_payment_proposals.py` |
| `tests/test_record_helpers.py` | `tests/helpers/operations/test_record_helpers.py` |
| `tests/test_repair_review_payment_allocations.py` | `tests/apps/bank_collections/test_repair_review_payment_allocations.py` |
| `tests/test_request_safety.py` | `tests/contracts/security/test_request_safety.py` |
| `tests/test_resource_validation.py` | `tests/zoho/core_sdk/test_resource_validation.py` |
| `tests/test_review_online_payments_script.py` | `tests/apps/bank_collections/test_review_online_payments_script.py` |
| `tests/test_review_request_metrics.py` | `tests/contracts/performance/test_review_request_metrics.py` |
| `tests/test_run_collection_reconciliation.py` | `tests/apps/bank_collections/test_run_collection_reconciliation.py` |
| `tests/test_security.py` | `tests/contracts/security/test_security.py` |
| `tests/test_sheet.py` | `tests/zoho/sheet/test_sheet.py` |
| `tests/test_statement_checkbox.py` | `tests/workflows/statement_schedules/test_statement_checkbox.py` |
| `tests/test_statement_schedules.py` | `tests/workflows/statement_schedules/test_statement_schedules.py` |
| `tests/test_stock_transfer.py` | `tests/workflows/stock_transfer/test_stock_transfer.py` |
| `tests/test_stock_transfer_recovery.py` | `tests/workflows/stock_transfer/test_stock_transfer_recovery.py` |
| `tests/test_trial_balance.py` | `tests/zoho/books/test_trial_balance.py` |
| `tests/test_type_safety.py` | `tests/contracts/architecture/test_type_safety.py` |
| `tests/test_unearned_revenue.py` | `tests/workflows/customer_payments/test_unearned_revenue.py` |
| `tests/test_unified_apps.py` | `tests/apps/test_unified_apps.py` |
| `tests/test_update_books_statement_sheet_app.py` | `tests/apps/statements/test_update_books_statement_sheet_app.py` |
| `tests/test_verify_gstr1_app.py` | `tests/apps/gst/test_verify_gstr1_app.py` |
| `tests/test_verify_gstr2_cli.py` | `tests/apps/gst/test_verify_gstr2_cli.py` |
| `tests/test_wd.py` | `tests/workflows/wd/test_wd.py` |
| `tests/test_workflow_refactoring.py` | `tests/contracts/architecture/test_workflow_refactoring.py` |
| `tests/test_workflows_package.py` | `tests/contracts/architecture/test_workflows_package.py` |
