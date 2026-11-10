# Changelog

Project changes are recorded newest first. Dates use Asia/Kolkata. Each logical
change has a descriptive title, why it was needed, what changed, and verification
or remaining limits. Include finding IDs and implementation commits when
available; never invent a commit or claim checks that were not run.
This file keeps the current year's entries; older years are archived under
`changelog/YYYY.md` and linked here when created. Check rollover with each change.

## 2026-11-10

### Report exact column diffs on Analytics items schema mismatch

- **Why:** `sync_analytics_items` raised a generic `ValueError` when the live Zoho Analytics export differed from cached metadata, forcing manual inspection to find which columns changed.
- **What:** Updated `src/workflows/item_catalog/analytics_snapshot.py` to include sorted `missing` and `extra` column lists and `last_successful_metadata_sync_at` in the schema-mismatch error message, plus added a regression test in `tests/workflows/item_catalog_export/test_analytics_snapshot.py`.
- **Verification:** `tests/workflows/item_catalog_export/test_analytics_snapshot.py` passed 5 tests, `ty check` passed, and `apps/generate_api_reference.py --check` passed; `apps/analyze_project.py --verify` reported 0 inspection errors and 1 unrelated missing-anchor diagnostic (`okf/log.md:5`); refreshed `data/analytics/metadata.sqlite` (`2026-11-10T14:21:49Z`) and synced `data/analytics/items.sqlite` (268 Accounts rows, 51,010 Items rows, 64 columns, integrity `ok`) on macOS arm64. Annual rollover checked (2026).

### Apply nine reviewed local Phone corrections

- **Why:** Resolve the user's selected Phone review cases with explicit replacement or blank values.
- **What:** Saved a SQLite backup and change ledger, corrected three Phone values using the agreed country-code format and cleared six selected Phone values. Left the remaining review cases unchanged.
- **Verification:** Full customer-row comparison verified only the nine requested Phone fields changed; SQLite integrity was `ok`. No Books writes or permanent code changes. Annual rollover checked (2026); macOS only.

### Clean reviewed local customer Phone values

- **Why:** Apply the user's explicit duplicate-removal and phone-formatting rules while preserving uncertain numbers for review.
- **What:** Backed up SQLite, cleared 1,011 Phone values matching Mobile after normalization, and formatted 151 remaining valid Phone values with the Indian country-code separator. Retained 13 uncertain Phone values unchanged and saved a change ledger.
- **Verification:** Transactional comparison verified customer identities and every field except the intended Phone edits unchanged; SQLite integrity was `ok`. No Books changes or permanent code change. Annual rollover checked (2026); macOS only.

### Add Branch-filtered customer views

- **Why:** Provide separate Electricals and Zeiss customer views in the local database.
- **What:** Created `Electrical Customers` and `Zeiss Customers` using `SELECT *` with exact Branch filters, including all statuses. Added the views to normalization so future syncs recreate them, and updated the owning documentation.
- **Verification:** All 31 normalization/sync tests passed on macOS. Local read-back verified exact filtered rows and all 61 customer columns: 969 Electricals and 194 Zeiss rows; SQLite integrity was `ok`. No cloud changes. Annual rollover checked (2026).

### Apply six reviewed customer Branch assignments

- **Why:** Apply the user's explicit Branch assignments to six active customers.
- **What:** Validated organization and active Branch options, retained live snapshots and a request checkpoint, sent minimal Books bulk custom-field updates, and synchronized only the six local Branch values with a SQLite backup.
- **Verification:** Books returned code 0; individual read-back verified all six requested values, unchanged display names and unrelated custom fields. Local transaction succeeded and SQLite integrity was `ok`. No permanent code change or unit tests required. macOS only; annual rollover checked (2026).

### Support all Books import duplicate settings

- **Why:** Accept the additional Books import option supplied by the user.
- **What:** Added `create_new` alongside `overwrite` and `skip` in the typed upload API and validation, documented the choices, and tested exact forwarding for all three settings.
- **Verification:** All 30 mocked import tests passed on macOS. No live upload or confirmation performed; `skip` and `create_new` remain unverified live. Annual rollover checked (2026); no archival needed.

### Confirm the reviewed Electricals Branch import through OAuth

- **Why:** Execute the explicitly authorized SDK upload confirmation and verify the saved Branch updates.
- **What:** Fixed confirmation to send organization_id once in the query: Books rejected the original query-plus-form duplication with code 12. Confirmed the staged import with OAuth, retained before/after snapshots and request checkpoints, and documented the verified contract.
- **Verification:** Books returned code 0: all 13 contacts updated, zero created/skipped, no errors. Fresh read-back verified Electricals on all 13 with unchanged display names and unrelated custom fields. All 823 Books tests passed, including 28 import tests; targeted Ruff and ty passed. macOS only. Annual rollover checked (2026); no older-year entries require archival.

### Add explicit Books import confirmation

- **Why:** Support the supplied second-step import confirmation request after staging a CSV.
- **What:** Added `books.imports.confirm(import_id, is_new_flow=False)` using an organization-pinned form-encoded PUT, strict import-ID/flow validation and explicit mutation classification. Documented that confirmation changes live records and requires saved-record verification. No live confirmation attempted: the supplied example ID differs from the SDK-staged upload ID.
- **Verification:** All 823 Books tests passed; targeted Ruff and ty passed on macOS. Mocked tests cover request encoding, invalid IDs/options/organization and error propagation. Confirmation OAuth support remains unverified. Annual rollover checked (2026); no older-year entries require archival.

### Add Books SDK import file upload

- **Why:** Stage the prepared customer Branch CSV through the SDK instead of replaying browser-session credentials.
- **What:** Added `books.imports.upload_file` with typed explicit import options, nonempty CSV validation, organization-pinned multipart fields, public custom-resource export and automatic file closure. Added mocked routing/error tests and owning API documentation. Removed the generated customer CSV's BOM after live Books left Customer Number unmapped; the corrected upload mapped all three requested columns. No import commit was sent.
- **Verification:** OAuth upload returned code 0 and an import ID, with Customer Number, Display Name and CF.Branch mappings checked. Full suite: 4,148 tests and 4 subtests passed; Ruff and targeted ty passed on macOS. Windows and import execution remain unverified. Annual rollover checked (2026); no older-year entries require archival.

### Stage Electricals Branch for thirteen selected customers

- **Why:** Set the explicitly selected active customers to Electricals and prepare their Books Branch updates for review.
- **What:** Updated only those 13 local Branch values, retained a SQLite backup, and prepared minimal Books custom-field payloads with live snapshots and modification baselines. Verified Branch is `cf_b_name` (index 6) and Electricals is an active allowed option. No Books writes performed.
- **Verification:** All 13 live contacts are active customers with blank Branch and ready plans. Local transaction checks showed only the selected Branch fields changed; reopened SQLite confirmed assignments, unchanged other tables and integrity `ok`. Read-only preparation succeeded after a transient timeout. macOS only; no permanent code change or unit tests needed. Annual rollover checked (2026).

### Generify collection review into utilities, helpers, and fetch flow

- **Why:** Reduce `src/workflows/collection_reconciliation/review.py` from 1,700 lines to 400–500 lines, promote reusable Creator/Books/Analytics/utility primitives out of the workflow, and separate the fetch flow from the review/mutation flow.
- **What:**
  - Added `numeric_affixes(value, length=4, is_prefix=False)` and `utc_now_iso()` to `utils.general_utils` (re-exported from `utils`).
  - Extracted `helpers.operations.creator` (`require_creator_success`, `update_and_verify_creator_record`), `helpers.operations.bank_transactions` (uncategorized fetch/get, match lookup/apply, categorization), `helpers.reports.analytics` (`build_batched_like_queries`, `query_or_export_analytics_rows`), and `resolve_chart_of_account`, `resolve_location_by_name`, `resolve_vendor_by_name` in `helpers`.
  - Consolidated cheque presentation checkpointing, invoice allocation previews, payment create/match helpers, and ordered bank candidate indexing in `workflows.collection_payments`, and moved bank-statement view/name-validation helpers into `bank_statement.py` and transfer-proposal merging into `bank_transfers.py`.
  - Split the concurrent fetch, caching, and proposal-building flow into `src/workflows/collection_reconciliation/review_fetch.py` (466 lines), keeping `OnlinePaymentReviewService` and queue/push mutations in `review.py` (492 lines) with backward-compatible re-exports and regenerating `docs/api/`.
- **Verification:** `ty check` passed with 0 diagnostics; `apps/analyze_project.py --verify` and `apps/generate_api_reference.py --check` passed with 0 errors; targeted suites (`tests/workflows/collection_reconciliation`, `tests/contracts/performance`, `tests/helpers`, `tests/utils/general_utils`) passed 304 tests and 2 subtests on macOS arm64. Full default suite ran after final edits (only pre-existing sandbox loopback socket `PermissionError`s in `test_http_transport.py` and `test_finding_regressions.py`). Annual rollover checked (2026); no older-year entries require archival.

### Allocate customer beats for active customers only

- **Why:** Apply the requested 20 km billing-pincode allocation only to active customers, retaining overlapping matches for review.
- **What:** Updated 95 unambiguous active-customer Beat values locally; 45 already matched. Excluded all 1,025 inactive customers and restricted overlap reviews to 363 active customers across 70 pincodes. Coordinate/pincode issues and overlaps remain unchanged; retained a SQLite backup and change report. No cloud writes.
- **Verification:** Reopened SQLite and verified all 95 assignments, identical inactive rows and other tables, and integrity `ok`. Transaction checks confirmed only Beat changed on active rows. Generated reports checked against current status. Cached Analytics metadata last synced 2026-11-09T07:19:15Z; no metadata refresh. macOS only; no code changes or unit tests needed. Annual rollover checked (2026); no older-year entries require archival.

### Refresh customers alongside Books custom modules

- **Why:** The customer sync rejected its target after Sales Person and Beat were downloaded into the same database.
- **What:** Accept the complete Books module table set, including optional local beat staging, while preserving those tables during customer reconciliation and backup. Refetched both sources and regenerated the local beat allocation report.
- **Verification:** 25 focused tests passed on macOS. Live read-back verified 2,030 local customers, including one retained for review, 7 sales persons, 27 beats, and SQLite integrity and foreign keys. Annual rollover checked (2026).

### Remove confusing customer beat view

- **Why:** The customer routing view `beat` was easily confused with the Books `beats` reference table.
- **What:** Removed the local SQLite view and stopped view generation from recreating it; route fields remain in Customers. Updated owning documentation and view assertions.
- **Verification:** Read-back confirms six tables and three views, with only `beat` removed; SQLite integrity is `ok`. All 30 normalization/sync tests passed on macOS. Annual rollover checked (2026); no older-year entries require archival.

### Download Books custom modules into the customer database

- **Why:** Keep the sales-person and beat reference records alongside the local Analytics customer data.
- **What:** Downloaded `cm_user` and `cm_beat` into `sales_persons` and `beats` in `data/analytics/customers.sqlite` using the existing downloader.
- **Verification:** Matched the database owner to the configured Books organization. Verified 7 sales-person rows, 27 beat rows, matching raw snapshots, 2,029 customer rows, and SQLite integrity on macOS. Annual rollover checked (2026).

## 2026-11-09

### Add SG Item Names local view

- **Why:** Review active SG inventory item names in SKU order.
- **What:** Created `SG Item Names` in the local Items SQLite snapshot with the fan view’s eight columns, filtered to the uniquely resolved Polycab SG Stock account (`1094368000051535662`).
- **Verification:** Verified eight columns, 35 rows matching the source filter, ascending SKU order, and SQLite integrity (`ok`) on macOS. Annual rollover checked (2026).

### Add Ledvance Item Names local view

- **Why:** Review active Ledvance inventory item names in SKU order.
- **What:** Created `Ledvance Item Names` in the local Items SQLite snapshot with the fan view’s eight columns, filtered to the uniquely resolved Ledvance Stock account (`1094368000045336631`).
- **Verification:** Verified eight columns, 146 rows matching the source filter, ascending SKU order, and SQLite integrity (`ok`) on macOS. Annual rollover checked (2026).

### Capitalize Neoseal Item Names view

- **Why:** Use the requested capitalization for the local view name.
- **What:** Renamed `neoseal Item Names` to `Neoseal Item Names` in `items.sqlite`.
- **Verification:** Transactional replacement verified the exact stored name and preserved all 98 rows and their order. Annual rollover checked (2026).

### Add Neoseal Item Names local view

- **Why:** Review active Neoseal inventory item names in SKU order.
- **What:** Created `neoseal Item Names` in the local Items SQLite snapshot with the same eight columns as the fan view, filtered to the uniquely resolved Neoseal Stock account (`1094368000034919849`).
- **Verification:** Read back all eight columns and 98 rows, verified SKU ordering, and checked SQLite integrity (`ok`) on macOS. Annual rollover checked (2026).

### Sort Fan Item Names by SKU

- **Why:** Review fan item names in SKU order.
- **What:** Updated the local `items.sqlite` view `Fan Item Names` with `ORDER BY SKU ASC`.
- **Verification:** Transactional replacement preserved all 305 rows and eight columns; checked ascending query results and SQLite integrity (`ok`) on macOS. Annual rollover checked (2026).

### Add Fan Item Names local view

- **Why:** Review active inventory-tracked fan item names and descriptive fields together.
- **What:** Created `Fan Item Names` in the local Items SQLite snapshot, filtered to Inventory Item, Active status and the uniquely resolved Polycab Fan Stock account. Removed Sales Description and Purchase Description on request, leaving eight columns.
- **Verification:** Verified the exact eight-column order and 305 rows after transactional view replacement; initial SQLite integrity checking passed on macOS / workspace CPython 3.14.10. Annual rollover checked (2026).

### Add the local Item Account Analysis view

- **Why:** Query item names, account assignments, and status together in the local Analytics snapshot.
- **What:** Created the six-column `Item Account Analysis` view over `Items` in the local SQLite snapshot. Inventory Account is returned only when Product Type is Inventory Item; other items return NULL to distinguish inventory tracking from account assignment.
- **Verification:** Confirmed column order and 51,007 rows in the live local file. Rehearsed the refresh transaction in memory and verified the view reads the replacement table. Verified the conditional account against the supplied tracked and untracked examples after a transactional view replacement; SQLite integrity check passed. Annual rollover checked (2026).

### Add Analytics Accounts and Items SQLite snapshot

- **Why:** Make the Analytics account and item masters available together for local queries and repeatable refreshes.
- **What:** Added a callable workflow and CLI that resolve the two Books replica views through the cached Analytics catalog, verify the export counts, and refresh `Accounts` and `Items` together in `data/analytics/items.sqlite`.
- **Verification:** macOS arm64 / CPython 3.14.10. Live download and SQLite read-back confirmed 268 Accounts and 51,007 Items, and `PRAGMA integrity_check` returned `ok`. The cached metadata was last synced at 2026-11-09 07:19:15 UTC. Full suite passed (4,123 tests and four subtests), as did Ruff, ty, and offline project verification. Annual rollover checked (2026).

### Migrate customer store to master-child architecture with reporting views

- **Why:** Adopt an ergonomic master-child architecture for local customer analytics (1 Master `Customers` table for all 1:1 attributes + 1 Child `Customer Addresses` table for 1:N address records) with 4 focused reporting views, eliminating artificial 1:1 table fragmentation and cross-table joins while supporting direct, zero-join tabular queries in Python and Polars.
- **What:**
  - Updated `src/workflows/customer_management/normalization.py` and `analytics_sync.py` to use two physical tables (`TABLES = ('Customers', 'Customer Addresses')`).
  - Consolidated all 1:1 financial attributes (credit limit, payment terms, GSTIN, PAN, balances) and route attributes (district, jurisdiction, transporter, beat, branch, optical division) into the physical `Customers` master table, excluding `Customer Owner ID`.
  - Configured automatic reporting view generation creating `Customer_core` (21 columns), `financials` (15 columns), and `beat` (5 columns) querying `Customers` directly, and `addresses` (22 columns) querying `Customer Addresses`.
  - Updated concept documentation in `okf/customer-local-store.md` and repaired inbound entry links in `okf/log.md`.
  - Re-synchronized [`data/analytics/customers.sqlite`](file:///Users/vak/Documents/workspace/WOA/data/analytics/customers.sqlite) from the preserved source snapshot.
- **Verification:** Verified `Customers` master table contains 61 columns and 2,029 rows; `Customer Addresses` contains 30 columns and 3,219 rows; verified all 4 views (`Customer_core`: 21 cols, `financials`: 15 cols, `beat`: 5 cols, `addresses`: 22 cols) select directly without joins; verified Polars integration (`pl.read_database`); all 89 customer management tests passed; `ty check` passed with 0 diagnostics; `apps/analyze_project.py` passed with 0 diagnostics; `PRAGMA integrity_check` returned `ok`; annual rollover checked (2026).

### Install Polars in workspace virtual environment

- **Why:** Provide the Polars DataFrame library in `.venv` upon user request for high-performance tabular data manipulation.
- **What:** Installed `polars==2.1.0` and `polars-runtime-32==2.1.0` in the workspace virtual environment using `uv`.
- **Verification:** Verified `import polars as pl` succeeds with version `2.1.0` in `.venv/bin/python` (CPython 3.14.10 on macOS arm64); verified `uv pip check --python .venv` reports all 90 packages compatible with 0 dependency conflicts; annual rollover checked (2026).

### Move local Analytics data and download customers

- **Why:** Keep the Analytics catalog and downloaded customer data together in a Git-ignored workspace directory.
- **What:** Renamed the local `metadata/` directory to `data/`, updated the ignore rule, and downloaded the normalized Analytics customer database to `data/analytics/customers.sqlite`.
- **Verification:** The read-only Analytics sync downloaded 2,029 customers and 3,219 addresses. Both SQLite files passed integrity checks, and Git ignored both paths. Used cached metadata last synced at 2026-11-09 07:19:15 UTC. Annual rollover checked (2026).

### Remediate hardcoded organization identifiers and strings (CHK-HC.1 to CHK-HC.7)

- **Why:** Prevent leakage and coupling to organization-specific entity IDs, view IDs, table IDs, clearing accounts, workspace IDs, and branch prefixes across workflows, apps, tests, examples, and documentation.
- **What:**
  - `CHK-HC.1` (Inter-location workflows): Replaced module-level constant `ACCOUNT_ID = "1094368000002033114"` in `src/workflows/inter_location/apply_updates.py` with `Config.INTER_LOCATION_CLEARING_ACCOUNT_ID` and added `clearing_account_id` parameter; parameterized `account_id` default in `sync_inter_location_contra_query_table` (`analytics_report.py`); removed hardcoded `_OBSERVED_PAYMENT_PREFIXES` dictionary in `payment_proposals.py` and sourced prefixes from `Config.LOCATION_PAYMENT_PREFIXES` with explicit parameter override; updated unit tests to use synthetic clearing account and location IDs.
  - `CHK-HC.2` (Analytics test runner): Removed hardcoded fallback defaults `"60018545708"` and `"264324000000002043"` in `tests/zoho/analytics/manual_analytics_query.py`, reading from environment or config profiles and raising explicit errors when unset.
  - `CHK-HC.3` (CLI Apps): Removed hardcoded branch prefixes (`"SBE2627CP-"`, `"SBE2526CP-"`, `"SB2526CP-"`) from default arguments in `apps/payments/renumber_sbe2627_payments.py`, `apps/inter_location_ops/move_inter_location_customer_payments.py`, and `apps/vendor_payments/show_fy2526_payment_proposals.py`, resolving prefixes dynamically from proposals or requiring explicit CLI flags.
  - `CHK-HC.4` (Example configurations): Sanitized real Google Sheet tab `gid` integers (`1177861729`, `41480615`, `1447215420`) to generic integers `0, 1, 2, 3` in `config/statement-schedules.example.yaml`.
  - `CHK-HC.5` (Example mappings): Replaced production Google Spreadsheet IDs, URLs, location IDs, partner personal names, and account IDs with standard placeholders in `examples/financial_statement_fy2425.mapping.json` and `examples/it_balance_sheet_fy2425.mapping.json`.
  - `CHK-HC.6` (Documentation & API references): Replaced production workspace ID `264324000000002043` in `INDEX.md` code snippet and replaced hardcoded IDs in `okf/` concepts (`analytics-metadata.md`, `bank-statement-check.md`, `collection-reconciliation.md`, `configuration.md`, `unearned-revenue.md`) with configuration references.
  - `CHK-HC.7` (Reconciliation workflows): Added configurable `cash_account_name`, `vendor_advance_vendor_name`, and `vendor_advance_location_name` fields to `OnlinePaymentReviewConfig` and wired them through `apps/bank_collections/payment_review.py` and `src/workflows/collection_reconciliation/review.py`.
- **Verification:** On macOS arm64 / CPython 3.14.10: `.venv/bin/python -m ty check` passed with 0 diagnostics across full scope; `pytest tests/workflows/inter_location/ tests/apps/inter_location_ops/ tests/contracts/architecture/ tests/workflows/statement_schedules/ tests/workflows/financial_statement_comparison/ tests/workflows/collection_reconciliation/ tests/workflows/vendor_ledger_reconciliation/` passed (416 tests passed); `apps/analyze_project.py --verify` and `apps/generate_api_reference.py --check` passed with 0 issues; annual rollover checked (2026); no live API mutations.

### Repair cross-platform CI checks

- **Why:** Run 42576153227 exposed missing optional imports in type checking, tests that depended on deployment configuration, and a Windows checkout mismatch in the ERP manifest hash (APPS-003, HELPER-002).
- **What:** Install OCR and keyring dependencies in the type-check job, supply explicit test IDs or mock configuration defaults, and preserve LF for the byte-verified ERP manifest.
- **Verification:** macOS arm64 / CPython 3.14.10: 4,119 tests and four subtests passed. All 164 affected tests passed in a source copy with no deployment configuration and an empty home directory. ty, offline analysis and API reference checks passed. CRLF conversion reproduced the exact Windows failure hash. Annual rollover checked (2026). Hosted CI for the fix is pending.

### Add local metadata directory and initialize analytics SQLite catalog

- **Why:** Provide a local, git-ignored workspace directory (`metadata/analytics/`) for storing Zoho Analytics metadata SQLite databases without polluting version control.
- **What:**
  - Added `metadata/` to `.gitignore`.
  - Created root `metadata/` and nested `metadata/analytics/` directory.
  - Initialized canonical SQLite database `metadata/analytics/metadata.sqlite` conforming to Analytics schema version 5.
- **Verification:** Verified `git check-ignore -v metadata/analytics/metadata.sqlite` matches rule `.gitignore:24:metadata/`; verified SQLite database integrity with `PRAGMA integrity_check` returning `ok` and `schema_version` equal to `5`; ran `apps/analyze_project.py` with 0 issues; annual rollover checked (2026); no live API mutations.

### Complete Phase 5 applications and distribution milestone type safety migration (CHK-5.1 to CHK-5.3)

- **Why:** Deliver CHK-5.1, CHK-5.2, and CHK-5.3 to achieve 100% full-repository type safety across all applications in `apps/` and the Zoho SDK in `src/zoho/`, eliminate untyped `Any`, establish PEP 561 distribution readiness via `src/zoho/py.typed`, and expand `[tool.ty.src].include` to full `"src"` and `"apps"` coverage with 0 diagnostics and 0 regressions.
- **What:**
  - `CHK-5.1` (Financial, Tax, Banking & Statement Apps): Strictly typed CLI argument parsing, execution flags, protocol return types, and workflow invocations across `apps/gst/`, `apps/inter_location_ops/`, `apps/inter_location.py`, `apps/vendor_payments/`, `apps/statements/`, `apps/bank_collections/`, `apps/payments/`, and `apps/verify_gst.py`. Promoted all packages to `[tool.ty.src].include`.
  - `CHK-5.2` (Inventory, Customer, Neoseal, Dashboard & Tooling Apps): Aligned `BaseResource.create` and `BaseResource.update` to accept `Mapping[str, object]` for direct `TypedDict` and mapping compatibility; added `invoice_number` to `TransferPayload`; updated `helpers.operations.transactions.unwrap_record` to accept `object` and candidate keys; narrowed stock balances, recovery protocols, and bin reads in `apps/inventory/transfer_stock.py` and `recover_stock_transfer.py`; typed host/port resolution in `apps/dashboard.py`; handled dynamic server ports in `apps/customers/allocate_customer_beats.py`; and resolved all diagnostics across `apps/tools/`, `apps/sdk_tools/`, `apps/neoseal_items/`, and `apps/neoseal.py`.
  - `CHK-5.3` (Distribution Milestone): Added `src/zoho/py.typed` PEP 561 type marker file, registered `"zoho" = ["py.typed"]` in `[tool.setuptools.package-data]`, updated `[tool.ty.src].include` to full repository scope (`["src", "apps", "tests/typecheck/renumber_contracts.py"]`), made `read_audited_workbook` calamine import lazy, added WorkDrive parameter redaction in `Files.list_files`, and regenerated API reference docs (`docs/api/`).
- **Verification:** On macOS arm64 / CPython 3.14.10: `.venv/bin/python -m ty check` passed with 0 diagnostics across full repository scope (`src` and `apps`); `.venv/bin/pytest -q` passed with 4119 passed, 4 subtests passed; `apps/generate_api_reference.py` confirmed docs in sync; `apps/analyze_project.py` confirmed full ty coverage with 0 diagnostics and architectural depth/count limits maintained; annual rollover checked (2026); no live API mutations.

### Complete Phase 4 financial and operational workflows and CHK-5.0 apps bootstrap standardization

- **Why:** Deliver CHK-4.1, CHK-4.2, CHK-4.3, CHK-4.4, and CHK-5.0 to achieve 100% strict type safety across all 32 domain workflow packages under `src/workflows/`, eliminate untyped `Any`, resolve all 61 `import-not-found` diagnostics across `apps/`, promote all workflow packages to `[tool.ty.src].include` (expanding coverage to 447 source files at 0 diagnostics), and bring 58 app files immediately to 0 diagnostics.
- **What:**
  - `CHK-4.1` (Offsets, Collections, Banking & Payments): Resolved diagnostics across 11 packages (`collection_payments`, `customer_payments`, `creator_payments`, `stock_transfer`, `payment_renumbering`, `vendor_customer_offset`, `vendor_ledger_reconciliation`, `bank_statements`, `bank_vendor_ledger_matching`, `duplicate_payment_check`, `customer_payment_date_check`, `collection_reconciliation`, `inter_location`) and promoted to `[tool.ty.src].include`.
  - `CHK-4.2` (Statements, Schedules, Comparisons & AIS): Defined `ScheduleConfig`, `NoteConfig`, `ScheduleAssetItem`, `ClassifiedItem` TypedDicts in `statement_schedules/workflow.py`, resolved `Generator` typing in `core/checkpoint.py`, typed `MasterRow` and caller protocols in `ais_reconciliation/`, resolved comparison tuples, and promoted `statement_schedules`, `financial_statement_comparison`, `audited_financials`, `books_statements`, and `ais_reconciliation` to `[tool.ty.src].include`.
  - `CHK-4.3` (GST & Tax): Defined `BooksRequestClient` protocol in `gst/cash_ledger.py`, fixed tuple typing in `gst/monthly.py`, explicit `GSTAmounts` constructor in `gstr1_verification/amounts.py`, date range narrowing and document parsing in `gstr1_verification/verifier.py`, and typed JSON loading, tax subtractions, and vendor dictionary maps in `gstr2_verification/verifier.py`. Promoted `gst`, `gstr1_verification`, `gstr2_verification`, and `gstr3b_pnl_comparison` to `[tool.ty.src].include`.
  - `CHK-4.4` (Inventory, Purchasing, Neoseal & Customer): Narrowed JSON loads and materialized tables in `customer_management/` (`analytics_sync.py`, `local_store.py`, `normalization.py`, `table.py`), typed creator sync batch updates in `creator_customer_sync/syncer.py`, added response dictionary coercions in `customer_registration/` (`__init__.py`, `numbers.py`), typed `CustomerValidationReport` in `customer_validation/validator.py`, resolved layout dictionary unrolling and sheet rows in `neoseal_stock_count/` (`processor.py`, `reporting.py`, `formulas.py`), cast duplicate map in `neoseal_audit/naming_rules.py`, typed verified records and attachments in `polycab_credit_memos/` (`importer.py`, `processor.py`) and `polycab_credit_review/` (`correction.py`, `workflow.py`), unapplied payment reallocations in `purchasing/bill_updates.py`, and catalog lookup in `sales_order_import/importer.py`. Promoted all 12 packages to `[tool.ty.src].include`.
  - `CHK-5.0` (CLI Bootstrap Standardization): Replaced `try: from . import _bootstrap except ImportError: import _bootstrap` across 59 app scripts and sibling imports in `apps/inter_location_ops/create_inter_location_contra_query_table.py` and `update_inter_location_contra_query_table.py` with `if __package__:` and `importlib.import_module("_bootstrap")` fallback, eliminating all 61 `import-not-found` diagnostics across `apps/` and bringing 58 app files to 0 diagnostics.
- **Verification:** On macOS arm64 / CPython 3.14.10: `.venv/bin/python -m ty check` passed with 0 diagnostics across all configured targets (covering 447 source files); `.venv/bin/python -m pytest tests/workflows/ -q` passed with 1163 passed, 4 subtests passed; `apps/generate_api_reference.py` confirmed reference docs up to date; `apps/analyze_project.py` confirmed 702 files, 447 ty targets, 0 diagnostics, and architectural depth/count compliance; annual rollover checked (2026); no live API mutations.

## 2026-11-08

### Complete Phase 2 service clients and Phase 3 core workflow infrastructure type safety migration (CHK-2.3 to CHK-3.3)

- **Why:** Deliver CHK-2.3, CHK-2.4, CHK-2.5, CHK-2.6, CHK-3.1, CHK-3.2, and CHK-3.3 by eliminating `Any` annotations from Creator, Analytics Custom/OpenAPI, WorkDrive, Sheet, Mail, Cliq, ERP, Google Sheets, Workflow Runtime, Workflow Core, and Analytics Catalog modules; resolve protocol and typing diagnostics; and expand `[tool.ty.src].include` to 321 source files with 0 diagnostics.
- **What:**
  - `CHK-2.3` (Creator & Analytics Custom): Aligned `ZohoCreatorAPI.request` with `BaseZohoClient.request`, added strict parameter and return types across `creator/client.py`, and handled optional headers cleanly. Added strict parameter/return types and `TypedDict` metadata records to `src/zoho/analytics/client.py`, `src/zoho/analytics/custom/` (`metadata.py`, `resources.py`, `snapshot.py`). Added to `[tool.ty.src].include`.
  - `CHK-2.4` (WorkDrive, Sheet, Mail & Cliq): Used `builtins.list` in `src/zoho/mail/base.py` and `messages.py` to resolve shadowing; aligned `Folders.create` and `Messages.list` via `@overload`; aligned `ZohoWorkdriveAPI.request` supporting legacy positional calls; eliminated all `Any` in `wd/`, `sheet/`, `mail/`, `cliq/`. Added to `[tool.ty.src].include`.
  - `CHK-2.5` (OpenAPI Generated Resources & ERP SDK): Resolved `invalid-argument-type` diagnostics in `src/zoho/books/openapi/resource.py` and aligned `ERPClient.request`. Promoted `src/zoho/books/openapi`, `src/zoho/analytics/openapi`, and `src/zoho/erp` into `[tool.ty.src].include`.
  - `CHK-2.6` (Google Sheets SDK): Defined `GoogleSheetsResourceProtocol` for Google Sheets `Resource` (`spreadsheets()` method) to resolve all 8 `unresolved-attribute` diagnostics, narrowed `json.loads` error handling, eliminated all `Any` across `src/google_sheets/`, and added `"src/google_sheets"` to `[tool.ty.src].include`.
  - `CHK-3.1` (Workflow Runtime Config & Auth): Defined `ProjectStructureConfig`, `DashboardWorkflowsConfig`, and `RuntimeFileConfig` TypedDict schemas for configuration parsing across `config.py`. Narrowed tuple conversions for GST cash and excluded/split payment ID configs via `_parse_id_tuple`, eliminated all `Any`, strictly typed client factory functions in `auth.py`, and added `"src/workflows/runtime"` to `[tool.ty.src].include`.
  - `CHK-3.2` (Workflow Core Infrastructure): Narrowed `json.load` output and previous snapshot verification in `src/workflows/core/snapshots.py`, replaced `Counter[str]` duration storage with `dict[str, float]` in `src/workflows/core/request_metrics.py`, annotated `@contextmanager` with `Generator`, and eliminated all `Any` across `matching.py`, `models.py`, `request_metrics.py`, and `snapshots.py`. Promoted `"src/workflows/core"` in `[tool.ty.src].include`.
  - `CHK-3.3` (Analytics Catalog): Replaced `Iterator` with `Generator` on the two `@contextmanager` methods in `src/workflows/analytics_catalog/service.py`, narrowed view ID usage to string in registry refresh, eliminated all `Any`, and added `"src/workflows/analytics_catalog"` to `[tool.ty.src].include`.
  - Regenerated API reference documentation in `docs/api/` via `apps/generate_api_reference.py`, marked CHK-2.3 through CHK-3.3 complete in `CHECKLIST.md` and `IMPLEMENTATION.md`.
- **Verification:** On macOS arm64 / CPython 3.14.10: `.venv/bin/python -m ty check` passed with 0 diagnostics across all configured targets (covering 321 source files); full test runs passed across `tests/google_sheets/` (21 passed), `tests/workflows/core` (43 passed), `tests/workflows/runtime` (7 passed), `tests/workflows/analytics_catalog` & `tests/zoho/analytics/test_analytics_metadata.py` (27 passed), `tests/zoho/books/test_books_openapi.py`, `tests/zoho/erp/test_erp_sdk.py`, `tests/zoho/analytics/test_openapi.py` (1,767 passed), `tests/zoho/creator` & `tests/zoho/analytics` (75 passed), `tests/zoho/mail`, `tests/zoho/cliq`, `tests/zoho/sheet`, `tests/workflows/wd` (71 passed); `apps/generate_api_reference.py --check` confirmed docs up to date; `apps/analyze_project.py --verify` confirmed 702 files, 321 ty targets, 0 diagnostics; annual rollover checked (2026); no live API mutations.

### Strictly type Books custom and Inventory modules (CHK-2.2)

- **Why:** Deliver CHK-2.2 by eliminating `Any` annotations from `src/zoho/books/custom/`, `src/zoho/books/client.py`, `src/zoho/books/base.py`, and `src/zoho/inventory/`, defining covariant error class resolution on `BaseResource`, narrowing response handling from `object`, adding nominal `PurchaseAccountId` and `OrganizationId` types, and expanding `[tool.ty.src].include`.
- **What:**
  - Resolved `invalid-mutable-override` across `BaseResource`, `src/zoho/books/base.py`, and `src/zoho/inventory/base.py` by defining `error_class` as a covariant read-only `@property`.
  - Replaced all 100+ `Any` occurrences with explicit types across 19 files in `src/zoho/books/custom/` (`banking.py`, `contacts.py`, `gst.py`, `ledger.py`, `mixins.py`, `projects.py`, `purchases.py`, `reports.py`, `sales.py`), `src/zoho/books/client.py`, and `src/zoho/inventory/` (`client.py` and all 10 resource modules under `catalog/`, `fulfillment/`, and `movements/`).
  - Defined `BooksGstClient` caller protocol and `_ConformingDoc` TypedDict in `gst.py`; added `@overload` signatures for streaming vs. object responses in `contacts.py` and `gst.py` statements and reports.
  - Added `PurchaseAccountId` and `OrganizationId` nominal types in `src/zoho/core_sdk/identifiers.py` and re-exported from `zoho.core_sdk` and `zoho` package roots.
  - Aligned `BaseZohoClient.request` and service client overrides to accept `Mapping[str, object] | Sequence[object] | None` payloads and `Mapping[str, str] | None` headers.
  - Added `"src/zoho/inventory"`, `"src/zoho/books/client.py"`, `"src/zoho/books/base.py"`, and `"src/zoho/books/custom"` to `[tool.ty.src].include` in `pyproject.toml`.
  - Regenerated API documentation in `docs/api/` via `apps/generate_api_reference.py`, marked `CHK-2.2` complete in `CHECKLIST.md` and `IMPLEMENTATION.md`, and updated `okf/log.md`.
- **Verification:** On macOS arm64 / CPython 3.14.10: `.venv/bin/python -m ty check` passed with zero diagnostics across the entire gate; 948 tests passed in `tests/zoho/books`, `tests/zoho/inventory`, `tests/contracts/architecture/test_type_safety.py`, and `tests/helpers`; 17 tests passed in `tests/workflows/vendor_customer_offset/`; 13 tests passed in `tests/zoho/analytics/test_analytics_metadata.py`; `apps/generate_api_reference.py --check`, `ruff check src apps tests`, and `apps/analyze_project.py --verify` all passed with zero diagnostics. Annual rollover checked: entries remain in 2026. No live API mutations.

### Strictly type shared helpers and expand ty gate to src/helpers

- **Why:** Deliver CHK-2.1 by eliminating `Any` annotations from `src/helpers/`, introducing explicit Protocol contracts for Zoho Books, Inventory, Analytics, and WorkDrive client interactions, and expanding the blocking `ty` type checking gate to cover all of `src/helpers/`.
- **What:**
  - Migrated all helper subpackages (`formatting/`, `operations/`, `catalog/`, and `reports/`), eliminating all 109 `Any` occurrences across 12 files down to zero.
  - Defined focused Protocol contracts: `BooksFileClient` and `WorkDriveFileClient` in `files.py`; `BooksInvoicesClient`, `BooksBillsSearchClient`, and `BooksBillsClient` in `transactions.py`; `AnalyticsBinClient` and `AnalyticsQueriesResource` in `bins.py`; `BooksContactsClient` and `BooksContactsResource` in `contacts.py`; `BooksCustomFieldsClient` and `BooksCustomFieldsResource` in `custom_fields.py`; `BooksBankAccountsClient` in `accounts.py`; `BooksPnLClient` in `profit_and_loss.py`; and `BooksLocationsClient`, `BooksEquityClient`, and `BooksInterBranchClient` in `equity_ledger.py` and `inter_branch_ledger.py`.
  - Replaced `Any` parameters, returns, and wire records across `gst.py`, `records.py`, `items.py`, and ledger entry `TypedDict`s with `object` and `Mapping[str, object]`.
  - In `pyproject.toml`, collapsed individual formatting helper entries in `[tool.ty.src].include` to `"src/helpers"` (indexing 62 source files in the blocking gate).
  - Regenerated `docs/api/helpers.md` via `apps/generate_api_reference.py`, repaired anchor reference in `okf/log.md`, and marked `CHK-2.1` complete in `CHECKLIST.md` and `IMPLEMENTATION.md`.
- **Verification:** On macOS arm64 / CPython 3.14.10: `.venv/bin/python -m ty check` passed with zero diagnostics across 62 files; 79 tests in `tests/helpers/`, 52 tests in `tests/contracts/architecture/test_type_safety.py`, 17 tests in `tests/workflows/vendor_customer_offset/`, and 13 tests in `tests/zoho/analytics/test_analytics_metadata.py` passed; `apps/generate_api_reference.py --check`, `ruff check src apps tests`, and `apps/analyze_project.py --verify` all passed with zero diagnostics. Annual rollover checked: entries remain in 2026. No live API mutations.

### Check search cardinality before financial writes

- **Why:** First-match searches can hide duplicates or miss later-page records, leading workflows to select the wrong entity or treat an existing order as new.
- **What:** Added paginated customer search by name, GSTIN and phone and unique resolvers for Inventory items, Books bills, transactions and clearing accounts. Migrated the affected Polycab, sales-order and offset callers. Custom-field provisioning blocks ambiguous requirements. Existing lookup and map interfaces retain their compatibility behavior.
- **Verification:** The full suite passed 4,119 tests and four subtests on macOS arm64 with CPython 3.14.10. Mocked tests covered pagination, duplicate IDs, ambiguity, later-page failure and blocked writes. Annual rollover checked. No live API requests.

### Remove redundant sequence parser wrapper from helpers.formatting

- **Why:** `src/helpers/formatting/sequences.py` was a pure pass-through wrapper around `utils.general_utils.sequences.parse_doc_number` with no additional helper logic.
- **What:**
  - Deleted `src/helpers/formatting/sequences.py` and updated `src/helpers/__init__.py`, `src/helpers/formatting/__init__.py`, `src/workflows/core/sequences.py`, and `src/workflows/gstr1_verification/verifier.py` to import `parse_doc_number` directly from `utils.general_utils.sequences` while redirecting the legacy `helpers.sequences` module alias to `utils.general_utils.sequences`.
  - Removed `src/helpers/formatting/sequences.py` from `apps/tools/generate_api_reference.py`, regenerated `docs/api/helpers.md`, and updated `INDEX.md`, `okf/architecture.md`, `okf/workflow-helpers.md`, `okf/log.md`, `tests/contracts/architecture/test_workflow_refactoring.py`, and `tests/helpers/operations/test_record_helpers.py`.
- **Verification:** On macOS arm64 / CPython 3.14.10: 396 tests (and 2 subtests) across `tests/helpers/`, `tests/contracts/architecture/`, `tests/apps/tools/test_api_reference_generator.py`, and `tests/workflows/gstr1_verification/` passed; `apps/generate_api_reference.py` and `apps/analyze_project.py --verify` passed with zero diagnostics. Annual rollover checked: all root entries remain in 2026.

### Plan cardinality checks for helper searches

- **Why:** Single-record helpers can select the first match or miss matches on later pages, which can affect downstream financial operations.
- **What:** Reviewed helper search and indexing behavior, traced affected callers, and recorded the staged rollout and acceptance checks in the local implementation plan and checklist.
- **Verification:** Static source and caller review completed. Confirmed that both planning files are Git-ignored and checked annual rollover. Planning only, with no runtime changes or live API requests.

### Move hardcoded workspace, view, and account identifiers to configuration

- **Why:** Eliminate hardcoded tenant-specific Zoho Analytics workspace/view IDs, Books/Inventory account, location, and item IDs, and machine-private paths from `src/helpers/`, `src/workflows/`, and `apps/` (extending HELPER-002) while preserving the `utils <- zoho <- helpers <- workflows <- apps` import boundary.
- **What:**
  - Added deployment configuration keys to `Config` in `src/workflows/runtime/config.py` with empty code defaults (`ANALYTICS_WORKSPACE_ID` with `ZOHO_ANALYTICS_WORKSPACE_ID` fallback, `ANALYTICS_DATE_MISMATCH_VIEW_ID`, `ANALYTICS_BANK_STATEMENT_VIEW_ID`, `ANALYTICS_CUSTOMER_FINDER_VIEW_ID`, `ANALYTICS_DETAILED_GL_VIEW_ID`, `ANALYTICS_UNDEPOSITED_CANDIDATES_VIEW_ID`, `ANALYTICS_UNDEPOSITED_REPORT_VIEW_ID`, `INTER_LOCATION_CONTRA_VIEW_ID`, `INTER_LOCATION_DIFF_VIEW_ID`, `GSTR2_DEFAULT_JSON_PATH`, `GST_CASH_LEDGER_ACCOUNT_IDS`, `POLYCAB_RMA_ITEM_ID`, `POLYCAB_RMA_ACCOUNT_ID`, `POLYCAB_CLEARING_ACCOUNT_ID`, `POLYCAB_SCHEME_ACCOUNT_ID`, `NEOSEAL_DUPLICATE_MAP`, `SALES_ACCOUNT_ID`, `UNEARNED_REVENUE_ACCOUNT_ID`, `INTER_BRANCH_ACCOUNT_ID`, `INTER_LOCATION_CLEARING_ACCOUNT_ID`, `LOCATION_PAYMENT_PREFIXES`, `INTER_LOCATION_EXCLUDED_PAYMENT_IDS`, `INTER_LOCATION_HANDLED_SPLIT_PAYMENT_IDS`, `SELECTED_VENDOR_PAYMENT_MOVES`, and `EXCLUDED_LOCATION_ID`), populated placeholders in `config/config.example.yaml`, and migrated active values into local `config/config.yaml`.
  - Set `DEFAULT_WORKSPACE_ID = ""` in `src/helpers/catalog/bins.py` and `account_id`/`excluded_location_id` defaults to `""` in `src/helpers/reports/inter_branch_ledger.py` with pre-request validation so `src/helpers/` neither hardcodes tenant IDs nor imports `workflows`.
  - Updated workflows (`customer_payment_date_check`, `bank_statements`, `customer_payments.unearned_revenue`, `gstr1_verification`, `inter_location`, `polycab_credit_memos`, `neoseal_audit`, `analytics_catalog.registry`) and CLI apps (`customers`, `payments`, `tools`, `gst`, `statements`, `bank_collections`, `neoseal_items`, `inventory`, `inter_location_ops`, `vendor_payments`) to source defaults from `Config`.
  - Regenerated `docs/api/helpers.md`, expanded `test_deployment_defaults_are_empty_and_explicit_values_migrate` in `tests/contracts/security/test_finding_regressions.py` and `TestBinsHelper` in `tests/helpers/test_helpers.py`, and updated `okf/configuration.md` and `okf/log.md`.
- **Verification:** On macOS arm64 / CPython 3.14.10: 178 targeted tests across helpers, workflows, apps, and security contracts passed; `apps/generate_api_reference.py` and `apps/analyze_project.py --verify` passed with zero errors; full pytest suite passed 4,087 tests and 4 subtests (only the 14 localhost socket tests failed in the sandbox due to loopback bind/connect restrictions). Annual rollover checked: all root entries remain in 2026.

### Remove the camelCase bin stock alias

- **Why:** Keep a single spelling for the warehouse bin stock helper.
- **What:** Removed `getBinsForItems` from the bins module and its re-exports. Existing callers can use `helpers.get_bins_for_items`.
- **Verification:** All 75 helper and API reference tests passed on macOS arm64 with CPython 3.14.10. A source search found no Python references to the removed alias. Annual rollover checked.

### Enforce India-only Zoho routing and shared HTTP contracts for Mail, WorkDrive, and Analytics

- **Why:** Deliver CHK-1.3 and CHK-1.4 by enforcing the India data center (`in`) routing policy across all Zoho SDK clients, typing authentication boundaries and request retry parameters, and establishing shared HTTP transport contracts with runtime backward-compatibility for WorkDrive.
- **What:**
  - Added class-level attribute annotations to `CatalystAuth` (`direct_token`, `catalyst_token_url`, `service_key`, `allow_direct_token_fallback`) resolving all 11 attribute diagnostics in `src/zoho/core_sdk/auth.py`.
  - Enforced India data center (`in`) policy across `ZohoOAuth2Manager`, `BaseZohoClient`, and service client constructors (`books`, `inventory`, `creator`, `mail`, `analytics`, `cliq`, `sheet`, `wd`); non-`"in"` domains explicitly reject with `ZohoConfigurationError`.
  - Fixed `upload_positions` in `BaseZohoClient._retry_after_auth_failure` and `_retry_rate_limited` to `Sequence[tuple[http.SeekableStream, int]]`.
  - Added a runtime positional compatibility shim in `ZohoWorkdriveAPI.request` detecting legacy `(stream, override_url, files)` calls with `DeprecationWarning` and unit tests in `tests/workflows/wd/test_wd.py`.
  - Promoted `"src/zoho/core_sdk"` and added `"src/zoho/__init__.py"` to `[tool.ty.src].include` in `pyproject.toml`.
- **Verification:** On macOS arm64 / CPython 3.14.10: `ty check` passed with zero diagnostics across all 45 covered source files; 2,222 tests in `tests/zoho/`, 22 tests in `tests/workflows/wd/`, and 239 architecture tests in `tests/contracts/architecture/` passed; `apps/analyze_project.py` reported zero diagnostics and zero errors. Annual rollover checked: root entries remain in 2026. No live API mutations.


### Support depth-two app and workflow packages

- **Why:** Allow cohesive subpackages within app and workflow domains while retaining the ten-file source directory cap (APPS-006).
- **What:** Set the configured and default depth to two. Resolve app bootstraps from the checkout marker and anchor web templates under `apps/static/`. Cover depth-two targets with the existing legacy import mechanism.
- **Verification:** The focused suites passed 190 tests on macOS arm64 with CPython 3.14.10, and all three web runners accepted `--help` from outside the checkout. The offline analyzer reported zero diagnostics. The full run with localhost access passed 4,067 tests and four subtests and reported 37 failures in SDK, request metrics, and generated API reference checks while other SDK changes were in progress. Annual rollover checked.

### Redact request-log queries and type security helpers

- **Why:** SDK-003 allowed secrets from query strings into SDK request logs.
- **What:** Mask sensitive query values in logged URLs and sanitize WorkDrive list parameters. Preserve the transport inputs. Promote security and logging modules into the type gate (CHK-1.1 and CHK-1.2).
- **Verification:** Three mocked log regressions and 13 explicit Analytics metadata tests passed. The initial execution batch passed 4,080 tests and four subtests on macOS arm64 with CPython 3.14.10. Configured ty, Ruff, offline analysis and API documentation checks passed. Annual rollover checked. No live API requests.

### Enforce shared source directory limits

- **Why:** APPS-006 required matching organization policy and tooling.
- **What:** The analyzer and architecture tests share source file-count and configurable depth checks, excluding generated output. Removed eleven obsolete bytecode-only test directories (CHK-0.2).
- **Verification:** Analyzer and architecture suites passed 119 tests on macOS arm64 with CPython 3.14.10. Annual rollover checked.

### Isolate cleanup test Git discovery

- **Why:** APPS-007 reproduced when pytest used a workspace-local temporary directory.
- **What:** Set a Git discovery ceiling in the failure fixture (CHK-0.3).
- **Verification:** All 11 cleanup tests passed with workspace-local `--basetemp` on macOS arm64 with CPython 3.14.10. Annual rollover checked.

### Expand type checking to the utilities package

- **Why:** Check utility modules and compatibility imports together.
- **What:** Fixed package-level alias imports and promoted the full utilities package into the configured type gate (CHK-1.0).
- **Verification:** Configured ty passed on macOS arm64 with CPython 3.14.10. Annual rollover checked.

### Exempt generated output from the folder depth rule

- **Why:** The optional, Git-ignored output directory holds generated artifacts.
- **What:** Aligned repository guidance, the organization concept, and CHK-0.2 to limit depth checks to apps and workflow source.
- **Verification:** Checked documentation alignment, Git ignore status, and whitespace. Annual rollover checked. Documentation change only.

### Record India-only Zoho routing and shared HTTP requirements

- **Why:** Set the deployment and transport requirements before implementing the SDK typing slices.
- **What:** Updated the local implementation plan and checklist to require Zoho India hosts and shared HTTP utilities for Mail, WorkDrive and Analytics.
- **Verification:** Checked both documents for matching requirements and checked annual rollover. Planning change only, with no runtime tests.

### Add tiered project-analysis skills for isolated collection and deep analysis

- **Why:** Enable running the two-stage review protocol either end-to-end or independently as isolated phases (Phase 1 context extraction on Gemini 3.8 Flash, Phase 2 deep architectural reasoning on Gemini 4 Argon) without burning routine context token budget.
- **What:** Created `.agents/skills/project-analysis-collect/SKILL.md` (slash command `/project-analysis-collect`, outputting to `output/project-analysis/structural_digest.json`) and `.agents/skills/project-analysis-deep/SKILL.md` (slash command `/project-analysis-deep`, reading strictly from the structural digest). Updated `.agents/skills/project-analysis/SKILL.md` as the unified orchestrator linking both standalone workflows.
- **Verification:** Verified skill discovery paths and YAML frontmatter format across `.agents/skills/`. Ran offline project analysis (`apps/analyze_project.py`) with zero diagnostics or errors. Annual rollover checked: root entries remain in 2026. No runtime, environment or live API changes.

### Remove root ERP generated adapter in favor of lazy module alias

- **Why:** Eliminate the physical root adapter `src/zoho/erp/generated.py` from the ERP package root while preserving 100% backward compatibility for legacy module imports, class lookups, and pickle deserialization.
- **What:** Removed `src/zoho/erp/generated.py`. Registered `zoho.erp.generated` as an explicit lazy alias for `zoho.erp.openapi.generated` in `src/zoho/erp/__init__.py` and `src/zoho/__init__.py` using `utils.general_utils.module_aliases.register_module_aliases`. Added regression contract in `tests/zoho/erp/test_generation.py` ensuring the root file is absent, module identity is preserved, and class imports and pickle paths keep full identity. Updated `okf/zoho-erp.md`, `okf/log.md`, `CHECKLIST.md`, and `IMPLEMENTATION.md`.
- **Verification:** macOS arm64 / workspace CPython 3.14.10: 1,008 ERP tests passed (`pytest tests/zoho/erp/ -q`), 93 architecture tests passed (`pytest tests/contracts/architecture/test_project_structure.py -q`), `ty check` passed with 0 diagnostics, and Ruff checks passed on `src/zoho/erp/`. Annual rollover checked: root entries remain in 2026. No live API mutations or dependency changes.


### Restructure the Analytics SDK around Zoho OpenAPI

- **Why:** Give Analytics the same generated/custom package split as Books and make Zoho's v2 operations discoverable through the SDK.
- **What:** Added ten domain resources under `client.openapi` covering the 203 operations in the pinned Zoho specifications. Moved export, query, metadata and SQLite support under `custom/`, preserving client attributes and legacy module identity. Added the offline generator, operation manifest and API reference.
- **Verification:** Verified all 203 routes against the pinned upstream specs and reproduced generated files byte for byte. On macOS arm64 / CPython 3.14.10, 4,069 tests and four subtests passed in the full suite, plus 13 separately collected metadata tests. Ruff, ty, offline architecture and API reference checks passed. Annual rollover checked. Live endpoints were not exercised.

### Refine and synchronize the checklist implementation plan with whole-project analysis

- **Why:** Ground `CHECKLIST.md` and `IMPLEMENTATION.md` in a complete empirical whole-project analysis across all 702 Python files with shared `CHK-*` identifiers, and resolve open review decisions on trusted OAuth hosts, positional override compatibility, OpenAPI generator typing scope, and structure/metadata verification gates.
- **What:** Assigned 1-to-1 `CHK-*` identifiers (`CHK-0.1`–`CHK-0.3`, `CHK-1.0`–`CHK-5.3`) across `CHECKLIST.md` and `IMPLEMENTATION.md`, recorded the 521-diagnostic broad `ty` scan and explicit `Any` counts per phase/step, added Phase 0 items for `APPS-006` (`CHK-0.2`), `APPS-007` (`CHK-0.3`), and completed `CHK-0.1`, added `CHK-5.0` for standardizing the 61 `_bootstrap`/sibling CLI imports across `apps/`, and mapped all 28 domain workflow packages and the restructured Analytics OpenAPI/custom SDK packages. Resolved the three design decisions and three corrections: (1) required an explicit mapping of trusted Zoho OAuth account hosts in `CHK-1.3` instead of an open-ended regex, (2) specified runtime/overload positional compatibility adapters and regression tests for `ZohoWorkdriveAPI.request`, `Messages.list`, and `Folders.create` in `CHK-1.4`/`CHK-2.4` plus `builtins.list` for Mail annotations, (3) aligned `CHK-2.5` across `generate_books_sdk.py`, `apps/sdk_tools/generate_analytics_sdk.py`, and `generate_erp_sdk.py` with explicit contracts for raw JSON (`object`), binary downloads, and `stream=True` (`Response`), and (4) aligned `CHK-0.2` structure policy (`project_structure.max_nested_folder_depth`) and the acceptance gate's explicit `tests/zoho/analytics/test_analytics_metadata.py` run.
- **Verification:** macOS arm64 / workspace CPython 3.14.10: `apps/analyze_project.py --verify` passed (702 Python files, 34 explicit `ty` targets with 0 diagnostics, API reference in sync); `ruff check src apps tests` passed with 0 diagnostics; broad `ty check -c 'src.include = ["src", "apps"]'` inventoried 521 diagnostics across 132 files; directory file-count and depth audit verified $\le 10$ files per directory across `src/`, `apps/`, and `tests/`. Annual rollover checked: root entries remain in 2026. No runtime, environment or live API changes.

### Prepare removal of the root ERP generated adapter

- **Why:** Remove a redundant root re-export file while keeping generated code under OpenAPI ownership.
- **What:** Reviewed runtime, generator, documentation and compatibility-test references; recorded the removal plan and local checklist item. Proposed retaining the old module path through the existing lazy-alias mechanism. The file remains in place pending review.
- **Verification:** macOS arm64 / workspace CPython 3.14.10: 1,007 ERP tests passed. The isolated alias trial preserved all 81 class imports, wildcard exports and old pickle lookups; offline documentation/link analysis and whitespace checks passed. Annual rollover checked: root entries remain in 2026. No runtime, environment or live API changes.

### Standardize the local implementation plan location

- **Why:** Give agents one consistent location for implementation plans requested by the user.
- **What:** Added a Git-ignored root `IMPLEMENTATION.md` alongside the local checklist and documented the convention in `AGENTS.md`.
- **Verification:** Verified the root plan matches the reviewed plan with repository-relative links, the ignore rule applies, and the agent guidance is present. Annual rollover checked.

### Split generated ERP resources into business modules

- **Why:** Give each ERP operation a findable resource file while preserving generated SDK behavior and reproducibility.
- **What:** Replaced the monolith with 81 resource modules in 13 approved domain packages, a typed registry and compatibility facade. Updated deterministic generation with explicit mapping, staged publication, rollback and generated-only cleanup; retained all class ASTs and manifest bytes. The API catalog now follows registry imports and links canonical sources. Added compatibility, provenance and generation-failure regressions.
- **Verification:** macOS arm64 / workspace CPython 3.14.10: full suite passed (3,857 tests plus four subtests); Ruff, ty, API synchronization, whitespace and offline analysis passed. Regeneration from the supplied definitions was byte-identical; all 81 resource ASTs and manifest bytes match the baseline. Compatibility, cleanup, interruption/recovery and ten-file directory contracts passed. Windows, hosted CI and live ERP remain unverified. Annual rollover checked: root entries remain in 2026. No dependency, environment or live API changes.

### Prepare the ERP resource-module split for review

- **Why:** Make generated ERP operations easier to locate and debug while preserving deterministic regeneration and public imports.
- **What:** Reviewed the 7,525-line generated file, generator, registry, documentation reader and tests; documented a complete 81-resource map across 13 business folders, compatibility requirements and staged generation/verification steps. Source splitting awaits the requested user review.
- **Verification:** All 81 manifest resources mapped exactly once, with at most ten files per proposed domain; all 913 existing ERP tests passed on macOS arm64 / CPython 3.14.10. Documentation/link and whitespace checks passed. Annual rollover checked: root entries remain in 2026. No generated source, live API or environment changes.

### Split generated Books resources by domain

- **Why:** Keep generated operation code readable within the 400-line file limit.
- **What:** The Books generator emits domain modules and splits large resources into operation groups. The original module re-exports the resource classes and registry.
- **Verification:** All 651 generated function ASTs and the 854-operation manifest match the baseline. The largest generated module has 381 lines. Full suite passed on macOS with CPython 3.14.10 (3,763 tests and 4 subtests). ty passed. Annual rollover checked. No live API calls.

### Apply capability packages across the project

- **Why:** Extend the utility layout across the SDK, helpers, workflows and tests so responsibilities are easier to locate and debug.
- **What:** Grouped shared SDK code, Inventory resource families, helper capabilities, workflow runtime and collection/Creator/customer payment operations; consolidated 21 workflow redirect files into lazy aliases and retained developer-tool CLI adapters. Migrated imports, mirrored tests, checker/generator targets and navigation, preserving utility and ERP editor changes. Added alias identity/laziness, command and directory-size contracts.
- **Verification:** macOS arm64 / workspace CPython 3.14.10: full suite passed (3,762 tests plus four subtests); Ruff, ty, API synchronization, whitespace and offline analysis passed with zero diagnostics/errors. Canonical/legacy module identity, lazy optional dependencies, direct CLI adapters, source-directory file limits and configured app/workflow depth checks passed. Windows and hosted CI were not run. Annual rollover checked: root entries remain in 2026. No environment or live API changes.

### Align the ERP OpenAPI package with Books

- **Why:** Give the ERP client and its generated OpenAPI artifacts the same separation used by Books.
- **What:** Moved the generated resources, operation base and packaged manifest under `zoho.erp.openapi`. Preserved existing ERP imports and refreshed eight source hashes from the supplied bundle.
- **Verification:** Full suite passed on macOS with CPython 3.14.10 (3759 tests and 4 subtests). Regeneration produced identical Python and operation metadata for 81 resources and 899 operations. Annual rollover checked. No live ERP calls.

### Organize utility modules into dedicated subpackages

- **Why:** Group individual utility scripts in `src/utils/` into clean, domain-specific directories (`http_utils`, `file_utils`, `general_utils`) to eliminate directory clutter while preserving import backward compatibility and zero regressions.
- **What:** Moved `http.py` and `http_transport.py` into `src/utils/http_utils/`; moved `json.py`, `yaml.py`, and `pdf.py` into `src/utils/file_utils/`; moved `encoding.py` and `sequences.py` into `src/utils/general_utils/`. Added package `__init__.py` files exporting public symbols and submodules. Implemented transparent meta-path redirection and root attribute aliases in `src/utils/__init__.py` supporting both snake_case (`http_utils`, `file_utils`, `general_utils`) and PascalCase (`HttpUtils`, `FileUtils`, `GeneralUtils`) imports as well as legacy submodule paths (`from utils.http import ...`, `import utils.json`, etc.). Updated `pyproject.toml` type checking targets, regenerated API reference docs, updated `okf/architecture.md`, and added regression tests in `tests/utils/test_utils_structure.py`.
- **Verification:** macOS arm64 CPython 3.14.10: all 74 tests in `tests/utils` and all 7 tests in `tests/apps/tools/test_api_reference_generator.py` passed; `apps/analyze_project.py` passed with zero errors or diagnostics; API reference generated and synchronized cleanly. Annual rollover checked: root entries remain in 2026.

### Require responsibility-based file organization

- **Why:** Future work should keep core SDK and other packages focused instead of accumulating unrelated files at package roots.
- **What:** Added a general AGENTS policy for inspecting ownership before placement, grouping related implementations, deciding splits/merges by responsibility, correcting touched directories, and verifying imports, compatibility, tests and file counts after moves. Linked the policy from project organization.
- **Verification:** Documentation links, policy consistency and whitespace checked; no runtime changes, so tests were not run. Annual rollover checked: root entries remain in 2026.

### Clarify SDK authentication failures and preserve token state

- **Why:** OAuth/broker failures escaped as inconsistent built-in/transport errors, and invalid expiry could replace a cached token before validation.
- **What:** Added typed configuration, token-response and token-service exceptions with root exports, retained service exception metadata and compatible ValueError catches, validated broker tokens/expiry before caching, serialized refresh, and sanitized token failure tracebacks. Kept security/path/redaction utilities separate from authentication and documented ownership and the keyring ImportError migration.
- **Verification:** macOS arm64 / workspace CPython 3.14.10: 3,658 tests plus four subtests passed outside sandbox localhost restrictions; ty and offline architecture/API verification passed with zero diagnostics/errors. Regression coverage includes malformed tokens/expiry, cache preservation, keyring failures, concurrency, redaction and exception compatibility. Annual rollover checked: root entries remain in 2026. No environment or live API changes.

### Move composite helpers out of the core SDK

- **Why:** Keep `src/zoho/` focused on the core SDK and expose composite operations alongside it.
- **What:** Moved helpers to `src/helpers/`, grouped catalog/report implementations within directory file limits, migrated callers and tests, and updated checker targets, API generation, navigation and architecture rules. SDK document-number parsing now uses `utils.sequences`, re-exported by helpers. The old `zoho.helpers` imports are removed.
- **Verification:** macOS arm64 / workspace CPython 3.14.10: full suite passed (3,629 tests plus four subtests) outside sandbox localhost restrictions; ty and offline analysis/API checks passed with zero diagnostics/errors. No live services or environment changes. Annual rollover checked: root entries remain in 2026.

### Rename the local work items checklist

- **Why:** Use one checklist for all project work items.
- **What:** Renamed `TYPE_SAFETY_CHECKLIST.md` to `CHECKLIST.md`, generalized its title and introduction, and updated its ignore rule while preserving existing tasks.
- **Verification:** Confirmed the rename, retained task content and Git ignore behavior; whitespace check passed. Documentation-only change; runtime tests not needed. Annual rollover checked: root entries remain in 2026.

## 2026-11-07

### Remediate Ruff Core SDK linting and exception chaining diagnostics

- **Why:** Clean up exception chaining, session attribute access, and import ordering across the Core SDK identified during Ruff static analysis.
- **What:** Added `from None` exception chaining to `zoho.security.resolve_output_path` and `zoho.validation.require_record` to avoid misleading nested tracebacks on input validation failures (`B904`). Replaced constant `getattr(session, "request")` with explicit callable validation in `utils.http.request_json` (`B009`). Simplified `zoho.base_resource._prepare_payload` and used `contextlib.suppress` in `zoho.base_client.close` (`SIM105`, `SIM108`). Organized and sorted import blocks across `src/utils` and `src/zoho` (`I001`).
- **Verification:** macOS arm64 CPython 3.14.10: `.venv/bin/python -m ruff check --select B,SIM,I,UP` on Core SDK passed with `All checks passed!`; `ty check` passed; offline analysis passed with zero errors; full SDK/contracts test suite passed 2,213 tests outside sandbox loopback socket restrictions. Annual rollover checked: root entries remain in 2026.


### Adopt python-rapidjson for project JSON handling

- **Why:** Use the requested native JSON codec with exact Decimal number serialization while preserving financial recovery and cached metadata compatibility.
- **What:** Replaced the unused orjson declaration with python-rapidjson 1.26 and migrated 93 source callers through typed `utils.json`. HTTP Decimal values serialize without float conversion; explicit default serializers, existing int/float decoding, byte encodings, native stream writing and atomic checkpoint schemas remain supported. Added basic non-string key normalization to prevent RapidJSON from turning whole dictionaries into default=str text. Output uses native compact whitespace. Kept the legacy Analytics canonical encoder for existing compressed blobs/hashes; no catalog refresh/rewrite. Updated public exports, API docs, concepts and editable metadata.
- **Verification:** macOS arm64 CPython 3.14.10: full suite 3,622 passed plus four subtests; 13 codec regressions cover exact large Decimal HTTP payloads, non-finite rejection, recovery strings, byte encodings, large integers, dictionary structure, errors and legacy hashes. ty passed 31 targets; analyzer verification reported zero diagnostics/errors; 88 installed packages compatible. Initial failures exposed expected compact-whitespace changes and sandbox server restrictions, resolved before final verification. No live API mutations or metadata sync; Windows and hosted CI remain unverified. Annual rollover checked: root entries remain in 2026.

### Add Ruff linter and formatter to project dependencies

- **Why:** Enable fast, native Python 3.14 syntax checking and formatting using Astral's Rust-based linter.
- **What:** Installed `ruff` 0.17.4 into `.venv`, added `ruff>=0.17.0` to `dependencies` in `pyproject.toml`, and pinned `ruff==0.17.4` in `constraints.txt`. Configured `[tool.ruff.lint]` rule selection in `pyproject.toml` for Python 3.14 syntax upgrade rules (`UP006`, `UP007`, `UP035`, `UP045`, `UP046`, `UP047`).
- **Verification:** macOS arm64 CPython 3.14.10: `.venv/bin/python -m ruff check` passed with `All checks passed!`; `.venv/bin/python -m ty check` passed; offline project analysis passed with zero errors. Annual rollover checked: root entries remain in 2026.


### Integrate Rust-backed date parsing, boundary validation, regex, and encoding detection

- **Why:** Replace pure-Python bottlenecks across financial date parsing, untrusted dictionary validation, regex matching, environment loading, and CSV encoding detection with high-performance Rust-backed engines.
- **What:** Installed `pydantic-core` 2.50.4, `orjson` 3.13.0, `regex` 2026.11.7, `chardetng-py` 0.3.5, and `dotenvy-py` 0.1.0 into `.venv`; added declarations to `pyproject.toml` and baseline pins to `constraints.txt`. Accelerated `zoho.helpers.dates.parse_date` with compiled `speedate` date parsing via `pydantic_core.SchemaValidator`. Accelerated `zoho.validation.require_record` using `pydantic_core` native mapping schema validation. Accelerated GSTIN regex matching via `regex`. Added `src/utils/encoding.py` (`detect_encoding`) powered by Mozilla's Rust `chardetng` detector. Wired `workflows.core.config` to support `dotenvy_py`.
- **Verification:** macOS arm64 CPython 3.14.10: `ty check` passed all targets in ~50ms; offline analyzer passed with zero errors; unit and contract test suites passed 3,373 tests outside sandbox loopback socket restrictions. Microbenchmarks verified ~10x date parse speedup, 4.4x JSON serialization speedup, and 2.5x record validation speedup. Annual rollover checked: root entries remain in 2026.


### Migrate project HTTP calls from Requests to pyqwest

- **Why:** Adopt the requested Rust-backed HTTP client without changing financial retry intent or upload/download safety.
- **What:** Added the typed pyqwest 0.13.0 transport adapter and routed Zoho, token-broker and direct Sheets REST callers through it. Preserved query/form encoding, certificate bundles, connect/read timeouts, fixed-length multipart bodies, caller-owned upload streams and service retry ownership. Fixed eager download buffering; native responses close on completion/failure. Migrated test interception, removed Requests stubs from direct dependencies, retained Requests transitively for Google libraries, refreshed editable metadata and updated API/operational documentation.
- **Verification:** macOS arm64 CPython 3.14.10: full suite 3,609 passed plus four subtests; 13 native loopback checks covered multipart 401/429 replay (SDK-001), Content-Length, query/form/JSON encoding, incremental binary downloads, interrupted streams, timeout errors, redirect credential stripping and cookie isolation. Public pyqwest documentation HTTPS smoke returned 200 with validated TLS. ty passed 30 targets; analyzer verification reported zero diagnostics/errors; 81 installed packages compatible. Initial failures were corrected or due to stale generated docs/sandbox local-server restrictions. No live financial/API mutations; Windows, hosted CI and live Zoho/Google endpoint behavior remain unverified. SDK-003 remains open. Annual rollover checked: root entries remain in 2026.

### Uninstall obsolete checker and reader packages from virtual environment

- **Why:** Physical package installations for replaced tooling (`mypy`, `pdfplumber`, `openpyxl`, `xlrd`) lingered in the local `.venv`, and `TYPE_SAFETY_CHECKLIST.md` contained stale references to `mypy`.
- **What:** Uninstalled `mypy`, `types-requests`, `mypy_extensions`, `ast_serialize`, `openpyxl`, `xlrd`, `et_xmlfile`, `pdfplumber`, and `pdfminer.six` from `.venv`. Updated `TYPE_SAFETY_CHECKLIST.md` to reference `ty check` and `[tool.ty.src].include`.
- **Verification:** macOS arm64 CPython 3.14.10: `.venv/bin/python -m ty check` passed all targets in ~50ms; focused test suite passed 332 tests outside sandbox loopback socket restrictions. Annual rollover checked: root entries remain in 2026.


### Remove obsolete mypy dependency constraints

- **Why:** The configured checker is ty, so the former mypy support-package pins no longer serve the project baseline.
- **What:** Removed ast-serialize, librt and pathspec from `constraints.txt`. Kept local installations intact because the retained mypy installation still requires them; its removal was previously declined.
- **Verification:** Confirmed the three names are absent from project dependencies and constraints; ty checks passed on macOS with workspace CPython 3.14.10. No runtime behavior changed; tests not rerun. Annual rollover checked: root entries remain in 2026.

### Replace PDF and spreadsheet readers with PDFium and calamine

- **Why:** Adopt the requested native PDF and spreadsheet readers without retaining pdfplumber, xlrd or openpyxl as project dependencies.
- **What:** Switched supplier PDF parsers to shared pypdfium2 page extraction with normalized newlines and explicit native handle cleanup. Migrated audited XLSX and vendor XLS reads to python-calamine, preserving coordinates, cached formula values and typed dates. Replaced the test-only XLSX writer with a minimal standard-library fixture; updated dependency declarations, constraints, optional-import checks, API docs and owning concepts. Installed python-calamine 0.9.1 and refreshed editable metadata; retained existing pypdfium2 5.9.0.
- **Verification:** macOS arm64 CPython 3.14.10: full suite 3,596 passed plus four subtests outside sandbox local-server restrictions; native PDF extraction, handle failure cleanup, real XLSX cached formulas/leading blanks and typed-date tests passed; ty passed 29 targets; analyzer verification reported zero diagnostics/errors. No live posting. Representative supplier PDF/XLS layouts, Windows and hosted CI remain unverified; PDFium does not reproduce pdfplumber layout analysis. Old reader packages may remain installed locally; project imports and declarations no longer use them. Annual rollover checked: root entries remain in 2026.

### Replace PyYAML with YAMLRocks

- **Why:** Adopt the requested YAML library while preserving configuration safety and legacy scalar interpretation.
- **What:** Pinned YAMLRocks 0.7.1 in place of PyYAML; migrated all application/workflow/test imports through `utils.yaml`. The shared loader validates source tags before conversion and rejects custom/Python tags, complex keys and multiple documents. Retained compatible text dumping; documented that dates dump as quoted ISO strings. Updated configuration/deployment/SDK concepts, type-check targets and API references. Installed the native macOS wheel and refreshed editable metadata; PyYAML remains installed for a legacy local distribution.
- **Verification:** macOS arm64 CPython 3.14.10: full suite 3,590 passed plus four subtests; final utility/tool checks 73 passed; ty passed 28 targets; analyzer verification reported zero diagnostics/errors; 88 installed packages compatible. Initial tests exposed tag rejection differences, corrected with source-tag validation. Metadata refresh succeeded with isolated building after the no-isolation attempt lacked setuptools. Hosted CI and Windows execution remain unverified. Annual rollover checked: root entries remain in 2026.

### Replace mypy checks with ty

- **Why:** Use the requested Astral type checker while retaining the incremental financial contract scope.
- **What:** Pinned ty 0.0.99 instead of mypy in project dependencies and constraints; migrated configuration, CI, project analyzer and positive/negative compiler contracts. Adjusted protocol narrowing, Requests callable typing, class annotations and generator annotations without changing request behavior. Updated checker documentation and generated API reference. Installed ty locally; mypy removal was declined, so it remains installed but is no longer configured or required. ty defaults do not reproduce mypy strict explicit-Any restrictions.
- **Verification:** macOS arm64 CPython 3.14.10: ty passed the retained 27-file scope; all three intentionally invalid domain contracts were rejected; SDK/utility/tool/architecture suite passed (2,141 tests). Project analyzer verification passed with zero diagnostics/errors and API docs current. Hosted CI and Windows execution remain unverified. Annual rollover checked: root entries remain in 2026.

### Standardize dependency management on uv

- **Why:** Remove the split between local uv setup and pip-based CI while preserving the deployment baseline (APPS-003).
- **What:** All CI jobs provision `.venv` and install/check constrained dependencies with pinned uv 0.11.12 through the official setup action; checks run with automatic syncing disabled. README, repository guidance, runbook and OCR instructions now use uv for package management; routine workflow commands use the workspace interpreter. Existing constraints and dependency versions are unchanged.
- **Verification:** macOS arm64 CPython 3.14.10: uv validated 86 installed packages; contract/tool tests passed (316) after rerunning outside sandbox restrictions on local servers; CI YAML parsed; offline analysis reported zero diagnostics/errors; whitespace check passed. No environment recreation, package install/upgrade or lock regeneration. Fresh installs and hosted Windows/Linux/macOS CI remain unverified. Annual rollover checked: root entries remain in 2026.

### Remove redundant exception class pass statements

- **Why:** Exception class docstrings already provide valid class bodies.
- **What:** Removed nine redundant `pass` statements from `zoho.exceptions` and normalized class spacing without changing behavior.
- **Verification:** SDK tests: 1,935 passed on macOS with workspace CPython 3.14.10. Annual rollover checked: root entries remain in 2026.

### Remove redundant Zoho download wrapper

- **Why:** `zoho.downloads` only re-exported the shared HTTP file writer.
- **What:** Removed the wrapper and switched all six SDK callers and the performance test to `utils.http.write_response_to_file`. Updated the API-reference generator, regenerated core documentation, and corrected the SDK concept. Resource-specific download behavior remains with its existing owners.
- **Verification:** macOS workspace CPython 3.14.10: SDK, HTTP utility, performance and API-reference tests passed (2,022); API reference regenerated. Annual rollover checked: root entries remain in 2026.

### Narrow rate-limit JSON exception handling

- **Why:** Avoid hiding unexpected failures during rate-limit detection.
- **What:** Catch only `ValueError` from JSON decoding and use early returns for successful responses and non-object payloads; preserve existing rate-limit rules.
- **Verification:** macOS workspace CPython 3.14.10: SDK and utility tests passed (1,967), covering status/code/message detection, invalid JSON, non-object payloads and propagation of unexpected errors. Annual rollover checked: root entries remain in 2026.

### Simplify base-client error handling

- **Why:** Separate response error parsing from exception construction and preserve valid zero error codes.
- **What:** Extracted `_parse_error`, limited JSON fallback to decoding failures, and made exception formatting explicit. Missing/null primary codes fall back to `error_code`; zero remains intact.
- **Verification:** macOS workspace CPython 3.14.10: SDK and HTTP utility tests passed (1,957), including zero codes, alternate fields, malformed/non-object JSON, error metadata and successful responses. Annual rollover checked: root entries remain in 2026.

### Remove unused base-client JSON content-type alias

- **Why:** The private alias was unused after HTTP utility extraction.
- **What:** Removed `_is_json_content_type` from `zoho.base_client`; repository source and tests have no callers. The shared HTTP helper remains available.
- **Verification:** HTTP utility and service logger tests: 44 passed on macOS with workspace CPython 3.14.10. Annual rollover checked: root entries remain in 2026.

### Centralize service logger setup

- **Why:** Keep service-specific logging configuration out of the shared HTTP client.
- **What:** Moved service logger mappings and compatibility logger setup into `zoho.logging.configure_service_logger`; the base client delegates to it. Preserved logger names, filenames, setup order and unknown-service fallback.
- **Verification:** macOS CPython 3.14.10: logger and contract tests passed (296 tests). Initial sandbox run blocked six local-server tests; rerun outside the sandbox passed. Annual rollover checked: root entries remain in 2026.

### Extract shared HTTP utility layer into `utils.http` and simplify `zoho.auth`

- **Why:** HTTP transport primitives (session/mock-aware dispatch, JSON/binary decoding, HTML error sanitization, bounded `Retry-After` parsing, HTTPS override URL validation, upload stream position replay, and streaming downloads) were embedded across `zoho.base_client`, `zoho.auth`, `zoho.downloads`, and Google Sheets REST workflow callers, while response envelope unwrapping and key extraction were repeatedly duplicated.
- **What:** Added `src/utils/http.py` (and `src/utils/__init__.py`) as a strictly typed, service-agnostic HTTP layer under `src/utils/`, including `unwrap_json_body`, `get_json_value`, and key-extraction support in `request_json`. Wired `zoho.base_client.BaseZohoClient`, `zoho.auth` (`HttpTokenProvider`, `ZohoOAuth2Manager`, `CatalystAuth`), `zoho.downloads`, `workflows.statement_schedules.writer`, and `workflows.financial_statement_comparison.comparison` to reuse `utils.http`. Condensed `zoho.auth` token-broker parsing and flattened `refresh_token` and `CatalystAuth.get_token_for_request` branches while preserving public signatures and mock patch compatibility. Refactored `zoho.base_client.BaseZohoClient.request` into a clean prepare -> execute -> retry -> notify -> decode sequence with module-level `from utils import http` import and focused helper methods (`_build_headers`, `_execute_http`, `_retry_after_auth_failure`, `_retry_rate_limited`, `_notify_request_completed`, flattened `_raise_for_status`). Enforced `utils` import boundaries in `apps/analyze_project.py`, added `src/utils/http.py` to strict `mypy` targets and `docs/api/core.md` generation, added unit tests in `tests/utils/test_http.py`, and added local `TYPE_SAFETY_CHECKLIST.md` to `.gitignore`.
- **Verification:** Regenerated `docs/api/core.md`; `mypy` passed on all 27 configured strict targets; offline project analyzer reported 0 diagnostics and 0 errors; pytest passed across `tests/utils`, `tests/zoho`, `tests/workflows/statement_schedules`, `tests/workflows/financial_statement_comparison`, `tests/workflows/core`, `tests/contracts`, and `tests/apps/tools` (2,020 passed in 4.36s). Annual rollover checked: root entries remain in 2026.

### Rename the checkout and rebuild its environment

- **Why:** Complete the local WOA rename without leaving editable installs tied to the former checkout location.
- **What:** Renamed the checkout to WOA, preserved local work/configuration/recovery data, and rebuilt its native virtual environment with the existing 85 dependency versions and the WOA editable package. Retained the former environment temporarily for recovery; cleared stale test bytecode after relocation.
- **Verification:** macOS arm64 CPython 3.14.10; dependency check and SDK/workflow imports passed. Full default suite: 3,520 passed, 4 subtests passed after clearing old-path bytecode (initial run: one source-inspection failure). Git whitespace check passed; no live workflows run. Annual rollover checked: root entries remain in 2026.

### Align the local remote with the WOA rename

- **Why:** GitHub repository naming changed to WOA while this checkout retained the former remote URL.
- **What:** Updated local origin fetch/push URLs to the canonical WOA repository and documented checkout-folder migration requirements. Project/package branding already uses WOA; environment and checkout location remain unchanged.
- **Verification:** GitHub repository lookup confirmed the canonical clone URL; fetch succeeded and main matches origin/main. `git diff --check` passed. No runtime changes or dependency installs; tests not rerun. Annual rollover checked: root entries remain in 2026.

### Restore local work after Git synchronization

- **Why:** Bring this checkout up to date while preserving ongoing Books SDK work.
- **What:** Fast-forwarded to `d84be7e`, retained both sets of changelog entries, and restored local tests under the incoming test layout.
- **Verification:** No unmerged paths; `git diff --check` passed. Focused offline suite: 963 passed on macOS with workspace CPython 3.14.10. Corrected the moved new test’s repository-root lookup after initial collection errors. Annual rollover checked: root entries remain in 2026.

### Centralize tests by source ownership

- **Why:** Align test navigation with SDK, workflow and application owners and remove nested source test directories (APPS-006).
- **What:** Moved 135 test/support files into categorized root test folders; repaired cross-test imports and asset paths; updated pytest discovery, metadata exclusion, CI and operational references. Preserved a [complete path mapping](okf/test-organization-plan.md#implemented-path-mapping). Every destination directory has at most ten files; other APPS-006 issues remain open.
- **Verification:** Windows AMD64 CPython 3.14.10: exact collection parity (2,876 default cases and 13 explicit metadata cases); default suite 2,874 passed, 2 skipped, 4 subtests passed (12.08s); metadata 13 passed (4.59s). API-reference and mypy passed; documentation/whitespace checks run. macOS/hosted CI not run. Annual rollover checked: root entries remain in 2026.


### Prepare centralized test migration

- **Why:** User requested preparation to centralize tests and match source ownership.
- **What:** Added a destination structure, static root-test import inventory and migration/acceptance steps in the [plan](okf/test-organization-plan.md). Linked from OKF navigation. No test moves performed.
- **Verification:** Inspected canonical source packages, root-test imports, fixture/path patterns and pytest configuration. Documentation analysis and whitespace checks run; runtime tests unnecessary for this planning-only change. Annual rollover checked: existing root entries remain in 2026. Implementation still requires collection parity and full-suite verification.


### Review structure, maintainability, performance and security

- **Why:** Requested project-wide assessment with reproducible evidence.
- **What:** Recorded sampled review, SDK-003 URL-log disclosure, APPS-006 layout-policy mismatch and APPS-007 temporary-directory test assumption in [the finding register](PROJECT_ANALYSIS.md#2026-11-07-structure-readability-performance-and-security-review). Documented analyzer limitations; application behavior unchanged.
- **Verification:** Windows AMD64 CPython 3.14.10: analyzer/API-reference/mypy passed; default suite 2,874 passed, 2 skipped, 4 subtests passed (12.48s); separately excluded metadata module 13 passed (1.84s). Mocked URL-secret reproduction confirmed. Sandbox failures and platform/live/advisory limitations recorded in the register. Rollover checked: root entries are all 2026.

## 2026-11-06

### Exclude metadata module from default test collection

- **Why:** User requested removal of metadata tests from the default suite.
- **What:** Ignore `tests/test_analytics_metadata.py` during default discovery; preserve explicit module execution and Analytics catalog coverage. Updated runbook and performance-plan scope.
- **Verification:** Windows CPython 3.14.10: default suite 2874 passed, 2 skipped, 4 subtests passed in 11.96s; explicit module collection still finds 13 tests. Diff whitespace check passed. Annual rollover checked: root entries remain in 2026.

### Increase default test workers to eight

- **Why:** Evaluate and adopt the requested higher parallelism.
- **What:** Set pytest and manual CI defaults to eight workers; retain lower CI choices and update the runbook and performance plan.
- **Verification:** Windows CPython 3.14.10 full runs: 13.58s and 14.48s, each 2887 passed, 2 skipped, 4 subtests passed. Improvement over four workers is not consistent across these samples; macOS/CI unverified. Isolated metadata profiling identified SQLite as the dominant cost (6 passed in 3.15s). Annual rollover checked: root entries remain in 2026.

### Plan four-second full-suite performance

- **Why:** Establish an evidence-based route to the requested four-second full test run.
- **What:** Added a phased [implementation plan](okf/test-performance-plan.md) covering waits, Analytics persistence fixtures, scheduling, compiler overhead and strict full-suite acceptance. Related APPS-003 remains open.
- **Verification:** Windows AMD64 CPython 3.14.10: profiled full suite 2887 passed, 2 skipped, 4 subtests passed in 15.24s; serial collection 2889 cases in 1.01s. Four-second feasibility remains unproven; no optimization applied. Annual rollover checked: root entries remain in 2026.

### Handle unavailable Windows symlink privilege in cleanup tests

- **Why:** The cleanup integration test failed during setup on Windows hosts without symlink creation privileges, before testing cleanup behavior.
- **What:** Skip that integration test only for WinError 1314 during directory symlink creation; other errors still fail and symlink-capable hosts retain the original safety assertions. Documented the verification limit in the runbook; production cleanup is unchanged.
- **Verification:** Windows AMD64 / workspace CPython 3.14.10: cleanup tests 10 passed, 1 skipped; full suite 2887 passed, 2 skipped, 4 subtests passed in 14.21s. Actual symlink assertions remain unverified on this host because privilege is unavailable. Diff whitespace check passed; annual rollover checked: root entries remain in 2026.

### Install all declared dependencies in the Windows environment

- **Why:** The existing workspace environment lacked the dependencies needed for development and workflow execution.
- **What:** Installed the editable project and all declared extras into the existing virtual environment using `constraints.txt`; retained its CPython 3.14.10 interpreter. No native external tools were installed.
- **Verification:** Windows AMD64: installation succeeded, `pip check` found no broken requirements, direct-library import checks and Asia/Kolkata timezone resolution passed; pytest 9.1.0, xdist 3.8.0 and mypy 2.4.1 load successfully. Full test suite not run as part of this installation. Annual rollover checked: root entries remain in 2026.

### Require type checking dependencies in every installation

- **Why:** Type checking should be available without selecting an optional extra.
- **What:** Moved pinned mypy and requests type stubs into base dependencies, retained an empty `typing` compatibility extra, and updated the runbook.
- **Verification:** Workspace TOML checks confirmed exact mandatory versions, no optional duplicates and the compatibility alias; diff whitespace check passed. Full suite remains blocked by missing pytest in the existing environment; no packages installed. Annual rollover checked: root entries remain in 2026.

### Require timezone data and YAML support in every installation

- **Why:** Timezone resolution and YAML configuration support should be available without selecting workflow extras.
- **What:** Moved `tzdata` and `PyYAML>=6.0.3` from the workflows extra into base dependencies and updated the setup runbook.
- **Verification:** Workspace CPython 3.14.10 TOML checks confirmed both requirements occur in base dependencies and no optional group duplicates them; diff whitespace check passed. Full suite remains blocked by missing pytest in the existing environment; no packages installed. Annual rollover checked: all root entries are from 2026.

### Require the test runner in every installation

- **Why:** A base installation could not run the required test suite because pytest was optional.
- **What:** Moved pytest and pinned pytest-xdist into base dependencies; retained an empty `test` extra for compatible existing commands and updated the runbook.
- **Verification:** Parsed TOML and checked mandatory requirements, compatibility extra and configured parallel runner. Full suite remains blocked by missing pytest in the existing Windows CPython 3.14.10 environment; no packages installed. Annual rollover checked: root entries remain in 2026.

### Keep generated Analytics metadata local

- **Why:** Workspace metadata caches and generated analysis reports are local artifacts rather than project source.
- **What:** Ignore `workspace_metadata/` and remove its four tracked artifacts from the Git index, preserving the local cache and reports.
- **Verification:** Confirmed the artifacts are ignored, absent from the Git index, and retained locally; targeted diff whitespace check passed. No runtime code changed; tests not run. Annual rollover checked: root entries remain in 2026.

### Keep VS Code settings local to each machine

- **Why:** Editor settings and automatic dashboard tasks are machine-specific and are not portable across the project machines.
- **What:** Ignore the entire `.vscode/` directory and stop tracking `settings.json` and `tasks.json`, retaining the local files.
- **Verification:** Confirmed both files are ignored, absent from the Git index, and still present locally; targeted diff whitespace check passed. No runtime code changed; tests not run. Annual rollover checked: root entries remain in 2026.

### Name the project WOA

- **Why:** Give the broader workflow and operations project the chosen identity beyond its Zoho SDK foundation.
- **What:** Adopted WOA — Workflows, Ops and Automations across project documentation, Python distribution metadata, dashboard title, installation hints and generated API references. Dashboard favorites read the former storage key for compatibility. Vendor SDK and workflow import names retain their meanings. GitHub rename is user-managed; remote/source URLs and local folder migration remain pending. Existing editable environment metadata needs an explicitly authorized reinstall; folder migration also requires environment reprovisioning because installed paths are absolute.
- **Verification:** Windows x64 / workspace CPython 3.14.4: 39 focused tests passed, including generated-document synchronization, package imports and old/new favorites storage behavior. Full suite with workspace-local temporary directories: 2880 passed, 1 skipped, 4 subtests passed; 8 failures from socket permissions (6), symlink privilege (1) and cleanup Git-discovery expectations (1). Initial full run also encountered sandbox temporary-directory permissions. API references regenerated; `git diff --check` passed. Interpreter differs from the required 3.14.10; environment unchanged. Annual rollover checked: root entries remain in 2026.
### Deduplicate Books endpoint wrappers and separate custom resources

- **Why:** Generated method synonyms and repeated source routes exposed duplicate
  wrappers for existing SDK endpoints.
- **What:** Moved hand-written Books resources/mixins into `custom/`, parallel
  to `openapi/`; migrated repository imports and removed old forwarding paths.
  Generation now assigns 843 unique method/path pairs one canonical owner
  across 854 source entries: 629 generated and 214 existing wrappers. Downloads
  and payment-number helpers delegate to their canonical wrappers; bill and
  invoice overrides identical to inherited implementations were removed.
  Preserved bill defaults/requirements and array task creation. Updated the
  [Books migration contract](okf/zoho-books.md#openapi-operation-coverage).
- **Verification:** macOS arm64 / workspace CPython 3.14.10: focused tests
  794 passed; final full suite 3533 passed, 4 subtests passed. Tests cover
  normalized cross-file deduplication, duplicate-custom-wrapper rejection and
  helper delegation. Source hashes, all 854 operation records and 843 canonical
  owners match; mypy, API-reference/diff checks and offline analysis pass with
  zero diagnostics/errors. Books directories meet the 10-file limit. No live
  API changes; hosted platform verification remains pending. Annual rollover
  checked: root entries remain in 2026.

### Complete Books OpenAPI operation wrappers

- **Why:** Most operations in the supplied Books OpenAPI bundle lacked dedicated
  SDK wrappers, including recurring documents, settings and document actions.
- **What:** Added 854 explicit operation methods across 44 generated resources,
  preserving legacy convenience methods and shared `BaseResource`/transport.
  Added offline generation with source hashes, packaged operation metadata,
  path/query/header validation, organization guards and upload/array encoding.
  Excluded 31 item operations under the existing Inventory routing policy.
  Documented [usage and regeneration](okf/zoho-books.md#openapi-operation-coverage).
- **Verification:** macOS arm64 / workspace CPython 3.14.10: focused Books checks
  907 passed; full suite 3753 passed, 4 subtests passed. All 44 source hashes and
  854 operations match the supplied definitions. Mypy, API-reference checks,
  diff checks and offline analysis pass (zero diagnostics/errors). The initial
  full run found stale generated API docs; regenerated them before the passing
  rerun. No live API calls; hosted platform verification remains pending.
  Annual rollover checked: all root entries belong to 2026.

### Clarify and rename the unified YAML configuration

- **Why:** Give the unified configuration a neutral filename and make profile selection, project policy and workflow identifiers easier to understand.
- **What:** Renamed local settings to `config/config.yaml` and the template to `config/config.example.yaml`. Ordered both as active profile, shared project structure, then independent runtime profiles; added section explanations and comments for ambiguous IDs, defaults and selection rules. Preserved every parsed value and existing profile/section names. Made the canonical filename highest priority, retaining legacy fallbacks, and updated setup/policy references and tests.
- **Verification:** Both parsed YAML documents match their originals and effective runtime file configuration is unchanged. macOS / workspace CPython 3.14.10: 35 focused tests passed; full suite: 2889 passed, 4 subtests passed. Tests cover canonical-path precedence, invalid YAML and profile/template contracts. `git diff --check` passed; local settings remain ignored. No live calls. Annual rollover checked: root entries remain in 2026.

### Merge directory policy into the runtime YAML configuration

- **Why:** Keep local project settings in one YAML file instead of separate directory-policy and runtime files.
- **What:** Merged `config/config.yaml` into `config/zoho_config.yaml` and removed the former after verifying preservation. Added top-level `project_structure.max_nested_folder_depth` to the example; policy is shared across profiles and runtime values remain in the active profile. Updated repository guidance and configuration ownership; the old path remains a supported loader fallback.
- **Verification:** Parsed merged settings match both source documents and effective runtime file configuration is unchanged. macOS / workspace CPython 3.14.10: 35 focused tests passed, including the merged policy/profile layout and example setting; `git diff --check` passed. Full suite not repeated because no runtime code changed. Local settings remain ignored; no live calls. Annual rollover checked: root entries remain in 2026.

### Migrate project configuration files to YAML

- **Why:** Use YAML consistently for local settings and templates in `config/`.
- **What:** Converted both local JSON settings files and the runtime template to `.yaml`, preserving parsed values. The runtime loader safely parses YAML before legacy JSON and fails closed for invalid or missing profiles; legacy JSON fallbacks remain supported. Updated ignore rules, policy, setup instructions, manual reader and template checks. PyYAML already belongs to the workflows extra; no environment changes.
- **Verification:** Compared every converted document and effective runtime file configuration before/after without exposing values. macOS / workspace CPython 3.14.10: 35 focused tests passed; full suite: 2889 passed, 4 subtests passed. Coverage includes native YAML profiles, quoted identifiers, precedence, malformed/empty/non-object YAML, unsafe tags and legacy JSON. `git diff --check` passed; no JSON files remain in `config/`; local YAML settings remain ignored. No live calls. Annual rollover checked: root entries remain in 2026.

### Consolidate local settings and templates under config

- **Why:** Keep local project settings and configuration templates together as requested.
- **What:** Moved the two local root JSON settings files and runtime example into `config/`; existing YAML templates remain there. Prioritized `config/zoho_config.json` ahead of `config/config.json` to preserve runtime profiles alongside directory policy, retaining legacy root fallbacks and fail-closed validation. Updated policy, setup/dashboard documentation, the manual reader and template tests. Local settings remain ignored.
- **Verification:** All moved files preserved byte hashes and effective file configuration compared equal before/after without exposing values. macOS / workspace CPython 3.14.10: 28 focused tests passed; full suite: 2882 passed, 4 subtests passed. New precedence and invalid-profile fallback tests pass; `git diff --check` passed. No live API calls. Annual rollover checked: root entries remain in 2026.

### Configure project directory nesting depth

- **Why:** Make the nesting limit adjustable instead of hard-coding one level in repository guidance.
- **What:** Added local Git-ignored root `config.json` with `project_structure.max_nested_folder_depth: 1`. Updated policy and its owning concept with organization roots, depth counting, non-negative integer requirements, and fallback 1. This guides organization without automatic enforcement or file moves.
- **Verification:** Parsed the local JSON and checked the configured value/type; `git diff --check` passed. No runtime code changed, so tests were not rerun. Annual rollover checked: all root entries remain in 2026.

### Remove obsolete Creator customer deletion-sync workflow

- **Why:** Remove the requested obsolete workflow package, which only aliased full customer reconciliation.
- **What:** Removed the compatibility package and root exports, removed its catalog entry and alias-only test, and migrated deletion-safety tests to the canonical customer sync API. Updated the owning concept; the active customer sync CLI and reconciliation remain available.
- **Verification:** macOS / workspace CPython 3.14.10: 72 focused tests passed; full suite passed (2878 tests, 4 subtests). Initial sandboxed full run had six localhost-bind permission failures; permitted rerun passed. No remaining source/test references to the removed API; `git diff --check` passed. Annual rollover checked: root entries remain in 2026. No live API changes.

### Fix Windows cleanup test path comparison

- **Why:** Hosted CI run [#67](https://github.com/sbe-tn-trichy/zoho_sdk/actions/runs/42202567269)
  failed on Windows because the cleanup assertion compared native backslash
  strings with forward-slash literals, blocking the matrix for SDK-001.
- **What:** Compare `Path` objects on both sides of the existing cleanup
  assertion, preserving its exact candidate-set and business-data checks.
- **Verification:** Full suite on macOS arm64 / workspace CPython 3.14.10:
  2879 passed, 4 subtests passed. Initial sandboxed focused run had six
  localhost-bind permission failures; the full permitted rerun passed.
  Windows hosted rerun remains pending; no production behavior changed.
  Annual rollover checked: root entries are all from 2026.

### Reorganize output folder adhering to file count limits and shallow nesting

- **Why:** `output/` had accumulated 21 flat files in the root and multiple subdirectories with large file counts (e.g. 428 files in `mobile_empty_preparation/`, 177 in `creator_payment_ocr/images/`, 900+ across 35 directories in `archive/2026-10-27_144954/`), violating the rule of maintaining $\le 10$ files per directory and cluttering project inspection.
- **What:** Reorganized `output/` so that 100% of its directories strictly contain $\le 10$ files:
  1. Preserved the exact 10 canonical active outputs (`gstr2_*` snapshots, `it_balance_sheet_*`, `inter_location_contra_review.json`, `unearned_revenue.json`, `neoseal_item_audit.md`, and `README.md`) at the root of `output/`.
  2. Moved 3 scratch Python scripts from `output/` to `scripts/`.
  3. Archived 14 completed past operational runs and loose run artifacts into `output/archive/2026-11-06_completed_runs.tar.gz` with a full JSON manifest (`manifest_2026-11-06.json`).
  4. Compressed the historical `output/archive/2026-10-27_144954/` tree into `output/archive/2026-10-27_144954.tar.gz`.
  5. Compacted intermediate per-file snapshots in `output/statement-schedules/`, `output/customer_cleanup/mobile_empty_preparation/`, and `output/creator_payment_ocr/` into `.tar.gz` packages, leaving primary plans, summaries, and Markdown reports immediately accessible.
  6. Updated `output/README.md` to document all active and archived outputs.
- **Verification:** Verified all 22 directories under `output/` strictly contain $\le 10$ files; full test suite passed (2,873 passed, 4 subtests passed); offline project analysis (`apps/analyze_project.py --verify`) clean with 0 diagnostics and 0 inspection errors; mypy and API documentation checks pass. Annual rollover checked: all entries remain in 2026.

### Generalize Inventory item catalog export

- **Why:** Purchase-account-based export logic was reusable across vendors but
  lived in the Neoseal package and used Neoseal-only command/output names.
- **What:** Added `workflows.item_catalog` and `apps/inventory/export_items.py`
  with neutral CSV defaults and active/inactive/all status selection. Retained
  Neoseal command/library compatibility and old output defaults. Validate account
  scope and distinct output paths before writing; updated owning documentation
  and command navigation.
- **Verification:** macOS arm64 / workspace CPython 3.14.10: focused
  exporter/compatibility/launcher tests: 21 passed; full suite: 2879 passed,
  4 subtests passed. The first sandboxed run could not bind localhost in six
  server tests; the permitted unsandboxed rerun passed. Offline analysis:
  zero diagnostics/errors; API-reference and configured mypy checks passed.
  Both export CLI help checks and `git diff --check` passed. No live API calls.
  Annual rollover checked for 2026; no older root entries require archival.

### Reorganize apps into shallow domain subfolders adhering to file count limits

- **Why:** 70 top-level scripts in `apps/` violated the project health constraint of maintaining $\le 10$ files per directory, making navigation cluttered and maintenance difficult.
- **What:** Reorganized all standalone scripts into shallow, 1-level domain subfolders: `apps/bank_collections/`, `apps/customers/`, `apps/gst/`, `apps/inter_location_ops/`, `apps/inventory/`, `apps/neoseal_items/`, `apps/payments/`, `apps/statements/`, `apps/tools/`, and `apps/vendor_payments/`. Every single directory in `apps/` (including the root `apps/`) now contains $\le 10$ Python files. Implemented a zero-overhead PEP 451 `_AppsRedirectFinder` in `apps/__init__.py` to provide 100% transparent backwards compatibility and exact module object identity for existing tests and callers. Updated `apps/dashboard.py`, `apps/_bootstrap.py`, unified CLIs, and documentation links. Codified the $\le 10$ files per directory limit and shallow hierarchy policy in `AGENTS.md` and `okf/project-organization.md`.
- **Verification:** Verified file count constraint ($\le 10$ Python files per directory across all directories under `apps/`); full test suite passed (2,861 passed, 4 subtests passed); offline project analysis (`apps/analyze_project.py --verify`) passed with 0 diagnostics, 0 inspection errors, mypy clean across 26 source files, and API reference documentation up to date. Annual rollover checked: all entries remain in 2026.

### Introduce unified domain CLI entry points in apps

- **Why:** 70 top-level scripts in `apps/` created cognitive overhead and discoverability friction across inter-location, Neoseal, and GST tasks.
- **What:** Created unified subcommand entry points for three primary domains: `apps/inter_location.py`, `apps/neoseal.py`, and `apps/verify_gst.py`. Each dispatcher provides structured `--help`, command discovery, and robust argument forwarding with `sys.argv` context preservation, while all standalone scripts remain intact for backward compatibility. Added test suite `tests/test_unified_apps.py`.
- **Verification:** `tests/test_unified_apps.py` passes (6 tests); full suite passes (2861 passed, 4 subtests passed); offline analysis (`apps/analyze_project.py --verify`) clean with 0 diagnostics and 0 inspection errors; mypy and API documentation checks pass. Annual rollover checked: all entries remain in 2026.

### Package customer management workflow modules

- **Why:** Five loose modules for customer management (`customer_analytics_sync`, `customer_invoice_payment_review`, `customer_local_store`, `customer_normalization`, `customer_table`) remained in `src/workflows/`.
- **What:** Consolidated them into the cohesive package `workflows.customer_management`, exposing clean public symbols via `__init__.py`. Replaced the root files with transparent `sys.modules` compatibility redirects, preserving identical module identity and monkeypatch behavior for existing apps and tests.
- **Verification:** 58 focused tests passed; full test suite passed (2855 passed, 4 subtests passed); offline project analysis (`apps/analyze_project.py --verify`) passed with 0 diagnostics and 0 inspection errors; mypy and API documentation checks passed. Annual rollover checked: all entries remain in 2026.

### Package Books statements and GST workflow modules

- **Why:** Loose modules for Books statements/catalogs (`books_statement_sheet`, `books_account_catalog`, `books_custom_module_store`, `books_pnl_notes`, `it_balance_sheet_comparison`) and GST (`gst_cash_ledger`, `gst_monthly`) cluttered the `src/workflows/` root.
- **What:** Consolidated them into two packages: `workflows.books_statements` and `workflows.gst`, each exporting clean public symbols via `__init__.py`. Replaced the root files with transparent `sys.modules` compatibility redirects, preserving identical module identity and monkeypatch behavior for existing apps and tests.
- **Verification:** 47 focused tests passed across both domains; full test suite passed (2855 passed, 4 subtests passed); offline project analysis (`apps/analyze_project.py --verify`) passed with 0 diagnostics and 0 inspection errors; mypy and API documentation checks passed. Annual rollover checked: all entries remain in 2026.

### Package inter-location workflow modules

- **Why:** Nine loose inter-location modules in `src/workflows/` cluttered the top-level directory and made domain ownership fragmented.
- **What:** Consolidated contra detection, location/payment proposals, and update logic into the structured package `workflows.inter_location` with public exports in `__init__.py`. Replaced the root `inter_location_*.py` and `apply_inter_location_updates.py` files with thin re-exporting compatibility redirects, maintaining zero-breakage for existing CLI and test callers.
- **Verification:** 62 focused inter-location tests passed; full test suite passed (2855 passed, 4 subtests passed); offline project analysis (`apps/analyze_project.py --verify`) passed with 0 diagnostics and 0 inspection errors; mypy and API documentation checks passed. Annual rollover checked: all entries remain in 2026.

### Align CPython version pin to 3.14.10 and remove external venv path

- **Why:** The workspace was executing CPython 3.14.10 on macOS arm64 while `.python-version` pinned 3.14.4; an extraneous editable install reference (`zoho_usable_functions`) in `.venv` pointed outside the workspace, causing sandbox permission failures during `pip check`.
- **What:** Aligned `.python-version`, CI workflow matrix, `AGENTS.md`, `README.md`, development runbook and finding register to CPython 3.14.10. Removed obsolete external `.pth` and `dist-info` files for `zoho_usable_functions` from `.venv`, ensuring all imports resolve hermetically from `src/`.
- **Verification:** macOS arm64: `pip check` passes cleanly ("No broken requirements found"); `.venv/bin/python apps/analyze_project.py --verify` passes with 0 diagnostics, 0 inspection errors, mypy clean across 26 source files, and API docs up to date; `git diff --check` passes cleanly; full test suite passes (2852 passed, 4 subtests passed). Annual rollover checked: all entries remain in 2026.

### Harden transport, offset recovery and deployment boundaries

- **Why:** SDK-001, HELPER-001/002 and APPS-001 exposed upload corruption,
  unsafe uncertain-payment compensation, inherited tenant IDs and unvalidated
  local HTTP authorities; APPS-003 lacked an application dependency baseline.
- **What:** Restore upload offsets on retries and reject non-seekable streams;
  require scoped, locked offset checkpoints with intent/ID persistence and
  read-back before resuming, withholding automatic compensation; remove tenant
  defaults and guard Analytics org configuration; validate Host before both
  local servers' routes. Add application constraints to CI installs, regression
  tests, migration/recovery documentation and finding-register evidence.
- **Verification:** macOS arm64 workspace suite: **2860 passed, 4 subtests
  passed** (4 workers); final offset recovery tests: **16 passed**. `mypy`,
  offline analysis, API-reference check, `pip check`
  and `git diff --check` pass. No live financial changes, environment replacement
  or dependency installation. Mac CPython 3.14.10 remains
  outside the 3.14.4 pin; fresh constrained installs, Windows and hosted runs of
  these local changes remain unverified. GitHub PR-run lookup at the base SHA
  returned no runs. Annual rollover checked: root entries remain in 2026.


### Promote reusable scratch operations to workflows and apps

- **Why:** Useful local scripts contained fixed record selections, duplicated
  formula logic and financial recovery operations without permanent ownership.
- **What:** Extended Creator customer sync with explicit IDs and selected live
  read-back; extracted StockCount formula helpers from the app; added offline
  Polycab evidence review using existing parsing/accounting rules; added a
  preview-first recorded-pair recovery helper/app with stock guards, atomic
  intent checkpoints and verified posting. Removed eight superseded ignored
  scratch implementations; preserved evidence, configuration and recovery data.
  Updated owning concepts and command navigation.
- **Verification:** macOS arm64: 154 focused/related tests passed, including
  preview/apply boundaries, scope guards, probe cleanup, offline evidence,
  stock/bin validation, uncertain posting and read-back failures. Full-suite
  snapshot: 2829 passed, 9 failed, 4 subtests passed; failures are in concurrently
  edited dashboard/payment-review Host checks and their test fixtures, outside
  this change. Offline analysis reports zero diagnostics/errors; API-reference
  check and configured mypy (26 source files) passed. CLI help smoke checks
  passed for all four entry points. No live services were called or changed.
  Workspace CPython 3.14.10 differs from the 3.14.4 pin; Windows unverified.
  Annual rollover checked: all root entries are from 2026; no archive needed.

### Add safe repeatable project cleanup

- **Why:** Generated build/cache files accumulate, while scratch scripts and
  other output may contain useful code or essential financial recovery state.
- **What:** Added `apps/cleanup_project.py`, previewing known disposable paths
  older than seven days and requiring `--apply` for removal. Excludes tracked
  files, symlinks and business output; rechecks file identity before deletion
  and fails explicitly on inspection or apply errors. Documented weekly usage
  and domain-owned scratch-code promotion candidates without moving scripts.
- **Verification:** Focused cleanup tests: 11 passed on macOS arm64 with workspace
  CPython 3.14.10 (pin remains 3.14.4). Actual checkout preview listed 188 files,
  1,356,928 bytes; no project artifacts were deleted. Full suite: 2769 passed,
  4 subtests passed. Offline analysis completed successfully; `git diff --check`
  passed (Git emitted a local fsmonitor IPC warning). Annual rollover checked:
  all root entries are from 2026; no archive needed. Windows execution unverified.

## 2026-11-05

### Expand offline project analysis and update finding register

- **Why:** `apps/analyze_project.py` only reported 1-hop static import dependents,
  omitted affected test mapping, OKF frontmatter checks, and cross-file Markdown
  heading anchor validation, and missed `HELPER-002`/`APPS-003` because their
  finding headings were not standardized in `PROJECT_ANALYSIS.md`. In addition,
  `PROJECT_ANALYSIS.md` still listed `SDK-002`, `APPS-002`, `APPS-004`, and
  `APPS-005` as uncommitted with no macOS verification.
- **What:** Extended `apps/analyze_project.py` to compute multi-hop
  `transitive_dependents` and `affected_tests` in `review_candidates`, validate
  cross-file Markdown heading anchors and local links across `AGENTS.md`,
  `GEMINI.md`, `CHANGELOG.md`, and `okf/*.md`, and enforce OKF frontmatter rules
  (`type:` on concept files; no frontmatter on `okf/log.md`). Standardized
  `HELPER-002` and `APPS-003` headings and summary rows in `PROJECT_ANALYSIS.md`
  (all 9 finding IDs now extracted), recorded implementation commits
  (`3491064612175fd875a3eb5fda7d4ef9cb0a96d4`,
  `731fe01875699833065e933caf429acf9e0047e6`,
  `d0e00672976c6bfd3ae5b2c5db450f2fcbfbaf2e`,
  `7a059766774718b707cf434588276cfdc35e9e8b`) and macOS 26.6.2 arm64 verification
  outcomes, and marked `APPS-004` and `APPS-005` Verified. Updated
  [project organization](okf/project-organization.md#repeatable-project-analysis),
  the [runbook](okf/development-runbook.md#default-parallel-tests), and
  [AGENTS.md](AGENTS.md#workflow-command-index), and added fixture tests in
  `tests/test_project_analysis.py`.
- **Verification:** macOS 26.6.2 (`Darwin 25.6.0 arm64`) with workspace
  `.venv/bin/python` (CPython 3.14.10, pytest 9.1.0, xdist 3.8.0, mypy 2.4.1):
  installed user-authorized `.[workflows,test,typing]` in `.venv` (`pip check`
  clean). `.venv/bin/python apps/analyze_project.py --since HEAD --verify`
  passed with exit code 0 (0 diagnostics, 0 inspection errors, all 9 finding IDs
  extracted, `tests/test_project_analysis.py` identified in `affected_tests`,
  `generate_api_reference.py --check` passed, and configured `mypy` passed on all
  25 source files). Focused tests (`tests/test_type_safety.py`,
  `tests/test_project_analysis.py`, `tests/test_api_reference_generator.py`,
  `tests/test_resource_validation.py`: 95 passed) and full-suite runs passed
  with 4 workers twice (3.94s / 4.00s), 2 workers (`-n 2`: 4.98s), and serially
  (`-n 0`: 7.67s): **2758 passed, 0 skipped, 4 subtests passed**, 0 worker
  restarts; `git diff --check` passed. Hosted CI and Mac `.venv` patch-pin
  alignment (`3.14.10` vs pinned `3.14.4`) remain tracked under `APPS-003`.
  Annual rollover checked: root history contains only 2026 entries; no archive
  needed. No live services were modified.

## 2026-11-04

### Make parallel pytest the default

- **Why:** Default testing should use multiple workers rather than require a
  separate opt-in command after preparation.
- **What:** Moved pinned pytest-xdist into the standard `test` extra, installed
  it and its execnet dependency in the existing workspace environment, and set
  pytest defaults to four worker processes with file scheduling and no automatic
  worker restart. CI test jobs use the same defaults; manual runs retain 0/2/4
  worker selection. Updated the [runbook](okf/development-runbook.md#default-parallel-tests)
  with serial debugging (`-n 0`), fixture boundaries and platform limits.
- **Verification:** Windows x64 / workspace CPython 3.14.4, pytest 9.1.1,
  xdist 3.8.0: complete suite passed twice with two workers (17.08s / 17.02s),
  twice with four workers (13.32s / 13.68s; final run used the default command),
  and serially with `-n 0` (26.98s). Every run: 2756 passed, 1 skipped,
  4 subtests passed; no worker restarts. Used fresh ignored workspace temporary
  directories for sandbox access. TOML/YAML/default checks, `pip check`,
  analysis `--verify` (mypy/API reference), and `git diff --check` passed.
  macOS and hosted CI remain unverified. Annual rollover checked: root history
  contains only 2026 entries; no archive needed. No live services were changed.

### Prepare optional parallel pytest execution

- **Why:** The serial suite has no configured worker runner or measured parallel
  baseline; preparation must preserve repeatability and the existing environment.
- **What:** Declared a pinned optional `test-parallel` extra using pytest-xdist,
  added manual CI selection of 0/2/4 worker processes with file scheduling, and
  documented fixture review, serial comparison, repeat runs and cross-platform
  acceptance in the [runbook](okf/development-runbook.md#default-parallel-tests).
  Ordinary local/push/PR commands remain serial. No local packages were installed.
- **Verification:** Windows x64 / workspace CPython 3.14.4: serial full suite
  with `--durations=15` passed (2756 passed, 1 skipped, 4 subtests passed in
  26.14s), using fresh workspace temporary directories for sandbox access.
  Parsed TOML/YAML and checked worker choices/defaults; `pip check`, offline
  analysis with verification (including mypy and API-reference check), and
  `git diff --check` passed. Parallel execution/performance, macOS and hosted
  paths remain unverified: the optional local plugin is absent and installation
  was not requested. Annual rollover checked: root entries remain in 2026;
  no archive needed.

### Add offline project analysis and incremental review

- **Why:** Repeated reviews had no reproducible inventory or recorded commit
  baseline, requiring repeated navigation and manual checks of unchanged areas.
- **What:** Added `apps/analyze_project.py` with static import-layer and navigation
  checks, explicit mypy scope, Git changes/renames, direct-dependent review
  candidates, optional existing verification commands, and JSON/Markdown reports.
  Added fixture tests, strict typing and a CI inspection step. Expanded the
  workflow catalog with entry points, remote operation profiles and contract
  links; recorded existing finding summaries and baseline limitations without
  closing findings. Review procedure is owned by
  [project organization](okf/project-organization.md#repeatable-project-analysis).
- **Verification:** Windows x64 / workspace CPython 3.14.4: focused analysis
  and API-generator tests passed (20); configured mypy passed (25 source files);
  API-reference `--check`, analysis `--since HEAD --verify`, and `git diff --check`
  passed. Fast inspection took 0.94 seconds and combined analysis/verification
  about 1.7 seconds; these are local measurements, not performance guarantees.
  Full suite via workspace `python -m pytest -q` passed: 2756 passed, 1 skipped,
  4 subtests passed. Sandbox temporary-directory access failures were
  resolved by using ignored workspace test directories and process-local TEMP/TMP.
  macOS and hosted CI were not run locally. Annual rollover checked: root history
  contains only 2026 entries, so no archive was needed. No live services, metadata
  sync, dependency installs or environment replacement were performed.

### Add generated Sphinx and Markdown API reference

- **Why:** While `INDEX.md` provides high-level SDK navigation, detailed module
  documentation, parameter types, class attributes, and mixin capabilities lived
  only in source comments and docstrings.
- **What:** Implemented `apps/generate_api_reference.py` to inspect AST signatures,
  type annotations, docstrings, class attributes, and inline module comments across
  all SDK modules. Generated comprehensive Sphinx and GitHub-flavored Markdown
  reference pages under `docs/` and `docs/api/` (`core.md`, `books.md`,
  `inventory.md`, `analytics.md`, `erp.md`, `creator.md`, `mail.md`, `wd.md`,
  `sheet.md`, `cliq.md`, `helpers.md`, `google_sheets.md`, `README.md`, `conf.py`,
  `index.rst`, `index.md`). Added `--check` verification mode and comprehensive
  tests in `tests/test_api_reference_generator.py`. Linked generated documentation
  from `INDEX.md`, `AGENTS.md`, and `okf/project-organization.md`.
- **Verification:** Ran `.venv/bin/pytest tests/test_api_reference_generator.py` (7 passed)
  and full test suite `.venv/bin/pytest -q` (2743 passed, 1 skipped, 4 subtests passed).
  Verified generator with `.venv/bin/python apps/generate_api_reference.py --check`.
  Annual rollover checked: all root entries belong to 2026.

### Extend Gemini read-command permissions

- **Why:** The workspace allowlist omitted common read-only inspection commands.
- **What:** Added working-directory, ripgrep, file metadata, disk usage, diff and
  specific Git inspection commands to `.gemini/settings.json`, preserving existing
  permissions.
- **Verification:** Parsed the JSON and checked the added entries and whitespace
  on macOS. No application tests needed for this permission-list change.
  Annual rollover checked: all root dated entries belong to 2026.

## 2026-11-03

### Add ERP SDK from local OpenAPI definitions

- **Why:** The supplied ERP API definitions needed a usable Python client in
  the existing SDK.
- **What:** Added 81 resources with 899 named operations, preserving ERP v1/v3
  routes; reused shared OAuth/HTTP transport, added ERP errors and an auth factory,
  organization isolation, YAML regeneration and source-hash provenance. Added
  [usage and limitations](okf/zoho-erp.md) and mocked coverage.
- **Verification:** Windows x64 CPython 3.14.4: 912 ERP tests passed; full suite
  2736 passed, 1 skipped, 4 subtests passed. Initial sandbox temp-directory
  permission failures cleared with process-local temp storage under `output/`.
  All 81 source hashes match; whitespace checks pass. No live ERP calls or
  mutations. macOS and live permissions remain unverified.
  Annual rollover checked: all root dated entries belong to 2026.

### Record payment guidance, Analytics snapshot and Metabase removal

- **Why:** Local operational knowledge and the cached Analytics snapshot were
  missing from project history.
- **What:** Documented [payment-linked deposits](okf/zoho-books.md#payment-linked-deposits),
  the bank-line identifier in [Payment Customer Finder](okf/collection-reconciliation.md),
  and [Metabase removal](okf/metabase-local.md), including preservation of source
  SQLite files. Updated the cached Analytics snapshot and reports: 200 views,
  2,214 columns, and the additional Payment Customer Finder column.
- **Verification:** Reviewed the local documentation/report diffs and checked
  whitespace. The snapshot records its last successful metadata sync as
  2026-10-29T11:38:50Z; no metadata refresh or live verification was performed
  during this history update. Runtime tests were not run for this documentation
  change. Annual rollover checked: all dated project entries belong to 2026.

### Implement incremental Python type safety

- **Why:** Dynamic clients, financial dictionaries and unchecked recovery data
  allowed interface errors and malformed records to reach financial workflows.
- **What:** Added an authorized pinned development checker and three-platform CI
  gate; migrated payment renumbering/CLI, shared helpers, stock planning, offset
  reports/contracts and collection allocation/index records into the strict scope.
  Added validated external records and nominal IDs, retained schema-1 recovery
  and wire formats, and rejected malformed pagination (SDK-002). Documented
  remaining transport, execution-service and application migration work; no
  repository-wide completion or HELPER-001 recovery fix is claimed.
- **Verification:** Windows x64 CPython 3.14.4: strict mypy passes 24 files;
  checker fixtures reject swapped IDs, float quantities and invalid status values.
  Full mocked suite outside the sandbox: 1824 passed, 1 skipped (optional OCR),
  4 subtests passed in 16.79 seconds. Dependency consistency, CLI help,
  documentation links and whitespace checks pass. Sandbox-only temporary-directory
  permission failures are distinct from product failures. Hosted CI and macOS
  remain unverified. No live API changes. Annual rollover checked: all
  dated project entries belong to 2026.

## 2026-11-02

### Plan incremental Python type safety

- **Why:** Financial workflows accept dynamic clients and records without a
  static-checking gate, weakening internal interface guarantees.
- **What:** Added a phased plan for mypy adoption, validated records, typed client
  contracts and workflow migration, starting with payment renumbering. Linked
  existing correctness findings without claiming they are resolved.
- **Verification:** Compared targets with source, configuration, CI and finding
  register; documentation links and whitespace checked. Documentation only;
  no dependencies installed, checker/tests run, or live changes made. Annual
  rollover checked: existing dated project entries are all in 2026.

## 2026-11-01

### Keep changelog history concise with annual archives

- **Why:** A permanent single-file history would become difficult to navigate.
- **What:** Required a rollover check on every logical change, preserving older
  years in linked archives and keeping entries concise. No archive is needed yet.
- **Verification:** All dated entries belong to 2026; documentation links and
  whitespace checks passed. No runtime changes or tests required.

### Require a project changelog for every change

- **Why:** The knowledge log did not consistently explain the reason for each
  project change or provide a single project-wide history.
- **What:** Created this file and made it mandatory for every logical change,
  including code, tests, dependencies, CI, rules, documentation and cleanup.
  The OKF log retains its narrower documentation role and links here.
- **Verification:** Documentation links and Git whitespace checks reviewed;
  no runtime behavior changed.

### Fix Windows timezone, encoding and pytest-cache failures

- **Why:** Windows lacked an IANA timezone database; a Unicode BOM fixture used
  the platform encoding; legacy pytest-cache permissions prevented writes.
- **What:** Declared `tzdata` in workflow extras and installed it in the existing
  `.venv`; wrote the BOM fixture as UTF-8; configured cache storage under ignored
  `output/pytest-cache`. Related finding: APPS-002.
- **Verification:** CPython 3.14.4 on Windows, full suite outside the sandbox:
  1750 passed, 1 skipped, 4 subtests passed. The skip is the OCR test because
  optional `pytesseract` is absent. No warnings. Mac execution remains unverified.

### Remove generated artifacts and conflicting policy copies

- **Why:** Tracked caches referenced an old Mac checkout, test output added noise,
  and duplicated agent rules conflicted with the canonical policy.
- **What:** Removed eight tracked cache links and fourteen generated test files;
  untracked local schedule configuration while preserving its contents; added
  ignore rules; reduced `GEMINI.md` to an `AGENTS.md` pointer.
  Related findings: APPS-004 and APPS-005.
- **Verification:** Git tracking/ignore checks passed and the local configuration
  hash was unchanged. The full suite subsequently passed as recorded above.

### Define the two-machine environment and review baseline

- **Why:** Windows 11 x64 and macOS 26+ Apple Silicon need explicit environment
  ownership, portable commands and a shared record of unresolved findings.
- **What:** Pinned CPython 3.14.4 in `.python-version` and CI; documented exclusive
  per-machine `.venv` use and explicit authorization for environment changes;
  configured Windows/macOS CI alongside Ubuntu; created the SDK/helper/apps
  finding register with stable IDs and closure criteria.
- **Verification:** Documentation and whitespace checks passed. Windows full-suite
  results are recorded above; hosted CI and the M4 Mac were not executed here.
  Dependency reproducibility and tenant-default gaps remain open in the register.

Earlier workflow and architecture history is available in the
[knowledge change log](okf/log.md). It has not been reconstructed as a complete
project release history.
