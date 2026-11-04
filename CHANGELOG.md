# Changelog

Project changes are recorded newest first. Dates use Asia/Kolkata. Each logical
change has a descriptive title, why it was needed, what changed, and verification
or remaining limits. Include finding IDs and implementation commits when
available; never invent a commit or claim checks that were not run.
This file keeps the current year's entries; older years are archived under
`changelog/YYYY.md` and linked here when created. Check rollover with each change.

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
