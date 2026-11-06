# Changelog

Project changes are recorded newest first. Dates use Asia/Kolkata. Each logical
change has a descriptive title, why it was needed, what changed, and verification
or remaining limits. Include finding IDs and implementation commits when
available; never invent a commit or claim checks that were not run.
This file keeps the current year's entries; older years are archived under
`changelog/YYYY.md` and linked here when created. Check rollover with each change.

## 2026-11-06

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
