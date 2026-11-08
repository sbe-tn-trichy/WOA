# Project analysis and finding register

Review baseline: 2026-11-01. Code and tests remain authoritative. This document
owns cross-project review findings; operational contracts remain in their OKF
concepts. The review sampled shared infrastructure and representative financial
workflows and applications; it is not an exhaustive audit.

## Baseline and verification record

| Field | Evidence / limitation |
|---|---|
| Original review date | 2026-11-01 |
| Original reviewed commit | Not recorded; do not infer it from the current HEAD |
| Original scope | Shared SDK infrastructure and representative financial workflows/apps; findings below |
| Exclusions | Exhaustive module coverage, live financial state, and Mac execution were not established |
| Tooling inspection date / revision | 2026-11-05 / `7a059766774718b707cf434588276cfdc35e9e8b` plus the local analysis and finding-register updates |
| Tooling inspection scope | Static import boundaries, explicit typing targets, navigation/OKF links and anchors, OKF frontmatter, transitive dependents, affected tests, and Git change inventory; not a new whole-project safety audit |
| Reproduction and results | See the [implementation changelog](CHANGELOG.md#add-offline-project-analysis-and-incremental-review) and [2026-11-05 verification](CHANGELOG.md#expand-offline-project-analysis-and-update-finding-register) for commands, actual checks and platform limitations |

For the next substantive review, record its exact commit and local changes,
scope/exclusions, platform, commands/results, and unresolved limitations here.
Use `--since` with an explicitly selected commit until an original review commit
is established. An inspection report does not advance the substantive review baseline.

## 2026-11-08 ERP module-split verification

Reviewed base `caf389ee2863ab4c40caf0f12d8467e6c67ed377` plus the pre-existing
local changes and approved ERP split. Scope: all 81 class ASTs/signatures/docs,
899 operation routes, manifest/provenance bytes, registry/import/pickle identity,
generator staging/rollback/cleanup, documentation sources and directory limits.
Regeneration from the supplied definitions was byte-identical. macOS arm64 /
workspace CPython 3.14.10: full suite passed (3,857 tests and four subtests);
Ruff, ty and offline architecture/API verification passed with zero diagnostics
or errors. No finding status changes, environment changes or live ERP calls.
Windows and hosted CI remain unverified. See the
[implementation entry](CHANGELOG.md#split-generated-erp-resources-into-business-modules).

## 2026-11-08 capability package verification

ERP split preparation additionally reviewed the current OpenAPI monolith,
generator, public exports, manifest and AST documentation reader against the
same local base and changes. All 913 ERP tests passed; the proposed domain map
covers 81 resources/899 operations without exceeding directory limits. No source
split or finding-status change is claimed. Implementation follows user review of
the [proposal](okf/zoho-erp.md#resource-module-split-proposal).

Reviewed base `caf389ee2863ab4c40caf0f12d8467e6c67ed377` plus the pre-existing
local utility/SDK changes and capability-package reorganization. Scope: import
migration, public exports and legacy module identity, optional-dependency laziness,
developer-tool command adapters, checker/generator paths, navigation and source
directory organization. macOS arm64 / workspace CPython 3.14.10: 3,762 tests and
four subtests passed; Ruff, ty and offline analysis/API verification passed with
zero diagnostics/errors. Source directories meet the ten-file limit; app/workflow
implementations meet the configured depth of one. No finding status is changed.
This structural verification does not certify financial behavior against live
services, output-directory policy, Windows or hosted CI. See the
[project entry](CHANGELOG.md#apply-capability-packages-across-the-project).

## 2026-11-07 pyqwest migration verification

Reviewed `d84be7ecc7ae4e1be742a874440df992c460ca41` plus pre-existing local
changes and the pyqwest migration. Scope: direct HTTP routing, body encoding,
response ownership, retries, timeouts, TLS and dependency/mocking integration.
Platform: macOS arm64, workspace CPython 3.14.10. Native local-server tests
verify multipart replay after 401/429 (SDK-001), fixed-length uploads, incremental
downloads, interrupted-transfer errors, cookie isolation and redirect credential
stripping. Full suite: 3,609 passed and four subtests; ty and analyzer verification
passed. A public documentation GET verified native HTTPS; no live financial
mutations or Zoho/Google endpoint checks were performed. Windows and hosted CI
remain unverified. SDK-003 URL-query logging remains an existing open finding,
not a new migration regression or a resolved issue. See the
[implementation evidence](CHANGELOG.md#migrate-project-http-calls-from-requests-to-pyqwest)
and [transport contracts](okf/http-transport.md). This does not advance the
substantive review baseline or close findings awaiting broader verification.

## 2026-11-07 structure, readability, performance and security review

Reviewed revision `3ee068baa917bfd3b05af3d49242bcaed54aa1f3` plus existing
local edits to CI, pyproject, changelog, runbook, OKF index/log and the untracked
test-performance plan. Platform: Windows AMD64, workspace CPython 3.14.10.
Scope: tracked source layout, static import/documentation checks, shared HTTP
transport, local review handlers, representative stock-transfer/reconciliation
code, dependencies and offline tests. This is a sampled review, not an exhaustive
security audit. No remote mutations, dependency changes or metadata sync occurred.
No live Analytics metadata was analyzed; its sync timestamp was not inspected.

### SDK-003 — URL query secrets bypass request-log redaction

- **Priority / status:** Medium / Closed. Mocked HTTP regressions passed on macOS arm64.
- **Evidence:** `src/zoho/core_sdk/base_client.py:202` logs the complete URL while only
  sanitizing the separate `params` dictionary. An approved-host override URL
  containing `?access_token=REVIEW_SENTINEL` leaves that sentinel in the INFO log.
  Analytics export downloads accept server-supplied download URLs. No actual
  credential disclosure was inspected or asserted.
- **Correction:** Redact sensitive URL query values before logging, including
  signed download credentials. The logger uses the sanitized copy while transport receives the original URL. WorkDrive listing logs sanitize separate request parameters.
- **Close when:** Tests cover endpoint/override query credentials and ordinary
  parameters, with no secret in emitted logs and unchanged outgoing requests.

### APPS-006 — Folder policy and actual layout disagree

- **Priority / status:** Low / Closed. Analyzer and architecture checks share the source policy.
- **Evidence:** At the time of the finding, local `config/config.yaml` is absent, so maximum depth is 1.
  Tracked files total 31 at `src/workflows/`, 15 in `collection_reconciliation/`
  and 13 in `core/`, exceeding the ten-file limit. Eleven domain `tests/`
  directories are at depth 2. Tracked `apps/` layout meets these limits.
  Generated bytecode and tool-owned output caches also exceed literal limits;
  those are distinct from source organization, not candidates for blind moves.
- **Correction:** Agree explicit treatment of tests/tool caches and compatibility
  modules, then align policy and layout. Add diagnostic checks for the agreed
  rules; the current clean analyzer report does not check these limits.
- **Close when:** Source inventory complies with the agreed policy and checks
  detect violations without moving recovery state or breaking legacy commands.

**2026-11-07 follow-up:** Centralized all source tests under root `tests/`,
removing the eleven nested source test directories. Collection retains 2,876
default cases and 13 explicit metadata cases. Default suite: 2,874 passed,
2 skipped, 4 subtests passed; explicit metadata: 13 passed. APPS-006 remains
open at that stage for source file counts and policy/tooling alignment.

**2026-11-08 closure:** The analyzer and architecture gate share directory checks. Fixture tests detect excess files, excessive depth and invalid configuration while excluding output depth. Eleven obsolete bytecode-only directories were removed. See
[test ownership](okf/project-organization.md#test-ownership).

### APPS-007 — Cleanup test assumes temporary directories are outside Git

- **Priority / status:** Low / Closed. All 11 cleanup tests passed with workspace-local `--basetemp`.
- **Evidence:** `tests/test_project_cleanup.py:85` expects Git failure in a plain
  `tmp_path`. With the documented workspace-local basetemp, Git discovers the
  enclosing repository and the expected exception is not raised. Reproduced
  alone; passes with normal host temporary directories.
- **Correction:** The test sets a Git discovery ceiling at the temporary directory's parent. Production fail-closed behavior is unchanged.

### Readability, framework use and performance assessment

The `zoho <- workflows <- apps` split is appropriate; static imports have no
reported violations. Requests session reuse, shared BaseResource behavior,
Decimal-based stock checks, injected clients and reconciliation RLock guards
are useful existing foundations. No framework replacement is justified by this
sample. Test/type tools in base dependencies are an explicit existing policy,
not a newly discovered defect.

Readability is uneven: reconciliation review (1,694 lines), GSTR-2 verifier
(1,597) and stock-count reporting (1,001) deserve focused responsibility reviews.
Extract only cohesive parsing/planning/reporting responsibilities with clear
contracts. The 7,525-line ERP module is generated; edit its generator rather than
manually splitting it. Explicit strict mypy targets cover 26 of 495 inventoried
Python files; this is not total transitive typing coverage. Expand coverage around
financial boundaries. Compatibility redirects are deliberate but add navigation
cost; canonical command documentation should remain the primary entry point.

No production throughput benchmark was run. Shared connection pooling already
avoids repeated handshakes; retain vendor scope and live pre-mutation read-backs
when optimizing API calls. Measure request counts, cache hits and timings before
adding concurrency or caching. In the successful test run, Analytics catalog's
retry/change scenario took 3.30s and compiler contracts took 2.36s. Existing
[performance profiling](okf/test-performance-plan.md) attributes metadata fixture
cost to SQLite work. Prioritize fixture/schema setup and short test-server polling,
then benchmark worker counts; eight workers alone do not establish a speedup.

### Verification and limitations

- `apps/analyze_project.py --verify`: zero diagnostics/inspection errors; API
  reference current; mypy passed all 26 configured files.
- Default pytest outside sandbox: **2,874 passed, 2 skipped, 4 subtests passed
  in 12.48s**. The configured metadata exclusion remains in place.
- Explicit `tests/test_analytics_metadata.py` with workspace TEMP/TMP:
  **13 passed in 1.84s**; all calls mocked, no metadata refresh.
- Initial sandbox run could not create its temporary directory. Workspace-local
  retry: 2,867 passed, 7 failed, 2 skipped, 4 subtests passed in 11.54s;
  six failures were loopback socket permission errors, one was APPS-007.
  Metadata's initial separate run also hit sandbox tempfile permissions; using
  workspace TEMP/TMP resolved it. These are not seven production regressions.
- SDK-003 sentinel reproduction used a mock transport/logger, without network.
- Existing SDK-001/002, HELPER-001/002 and APPS-001/003 verification obligations
  remain; passing local tests does not establish live recovery or hosted/Mac results.
- No dependency advisory database, Git-history secret audit, penetration test,
  macOS run or live financial reconciliation was performed.

## Finding summary

Implementation and verification are separate; the detailed evidence below owns
closure criteria. No findings are closed by adding inspection tooling alone.

| ID | Priority | Correction owner | Implementation | Verification |
|---|---|---|---|---|
| SDK-003 | Medium | SDK request logging | Closed | Endpoint and override URL redaction plus WorkDrive parameter regression tests |
| APPS-006 | Low | Structure policy/tooling | Closed | Shared analyzer/architecture checks and fixture regressions |
| APPS-007 | Low | Cleanup tests | Closed | Cleanup suite passed with workspace-local basetemp |
| SDK-001 | High | SDK transport | Fixed, awaiting verification | Multipart replay regression coverage passes; commit/hosted verification pending |
| SDK-002 | Medium | SDK pagination | Committed (`d0e0067`) | Verified on Windows x64 and macOS arm64; hosted CI evidence pending |
| HELPER-001 | High | Vendor/customer offset | Fixed, awaiting verification | Durable intent, no automatic compensation, read-back recovery tests pass; live behavior unverified |
| HELPER-002 | Medium | Workflow configuration | Fixed, awaiting verification | Removed tenant defaults; fresh/explicit migration and guard tests pass |
| APPS-001 | Medium | Local review servers | Fixed, awaiting verification | Handler rejection/acceptance tests pass; commit/hosted verification pending |
| APPS-002 | Medium | Workspace environment | Committed (`731fe01`, `7a05976`) | Windows x64 and macOS arm64 parallel/serial suites pass; `.python-version` aligned to `3.14.10` |
| APPS-003 | Medium | Cross-platform & dependencies | In progress | Constraints and CI install policy added; pinned runtime/fresh installs/hosted runs pending |
| APPS-004 | Medium | Repository tracking | Committed (`3491064`, `731fe01`) | Verified on Windows x64 and macOS 26.6.2 arm64 |
| APPS-005 | Medium | Agent policy | Committed (`731fe01`) | Verified on Windows x64 and macOS 26.6.2 arm64 |

## 2026-11-06 local corrections and remaining verification

At base `29c9eb2393f2014c229e03a5e222d56baad8ce7d` plus pre-existing local
changes, implemented SDK-001, HELPER-001, HELPER-002 and APPS-001 without live
financial mutations or environment changes. Historical evidence below describes
the original failure mechanisms; this section records their corrections.

- **SDK-001:** Transport snapshots/restores seekable upload offsets before 401
  and 429 retries; rejects non-seekable streams before HTTP. Actual multipart
  replay tests cover raw/tuple uploads and nonzero positions.
- **HELPER-001:** Live offsets require an explicit checkpoint; organization/domain
  scope, exclusive lock, payload intent and known IDs persist around creates.
  Compensation is withheld after any uncertain result. Reruns verify both saved
  payments by live detail reads before skipping already-created bill intents;
  missing/ambiguous state blocks posting. Tests cover response loss, missing IDs,
  checkpoint failures, scope mismatch, stale locks and duplicate prevention.
  See the [recovery contract](okf/vendor-customer-offset.md). Allocation
  identities/amounts are compared after detail reads; discrepancies fail safely.
- **HELPER-002:** Removed the five tenant-specific organization/account/workbook
  defaults. Missing Analytics organization fails before token retrieval; existing
  stock-count/payment guards retain their scoped behavior. Fresh defaults and
  explicit configuration migration are covered by regression tests.
- **APPS-001:** Both handlers reject invalid/duplicate Host headers before pages
  and APIs; local authorities use the actual bound port. Token/confirmation
  regression tests continue to pass.
- **APPS-003:** Added application constraints and applied them to CI installs;
  library compatibility ranges remain separate. Existing Mac `.venv` remains
  CPython 3.14.10, with no installs or interpreter changes. Fresh installs using
  3.14.4 and supported-platform hosted results remain pending. GitHub's PR-run
  lookup for the base SHA returned no runs; this limited lookup does not establish
  whether push-triggered CI ran. Uncommitted fixes have no hosted CI evidence.

Verification commands and final results are recorded in the
[change entry](CHANGELOG.md#harden-transport-offset-recovery-and-deployment-boundaries).
Local fixes remain **Fixed, awaiting verification**, rather than Verified without
implementation commits and required platform evidence. APPS-004/005 retain their
previous verified status; SDK-002/APPS-002 retain their outstanding verification.

## Categories and ownership

| Category | Scope | Responsibility |
|---|---|---|
| SDK | `src/zoho/` clients, transport, resources; `src/google_sheets/` | API contracts, authentication, request execution, pagination, service errors |
| Helper | `src/helpers/`, `src/workflows/core/`, domain packages in `src/workflows/` | Reusable API compositions, financial rules, planning, matching, checkpoints and recovery |
| Apps | `apps/`, `apps/static/`, developer setup and CI | Command selection, inputs, previews, confirmation, local UI boundaries and execution reporting |

These are review categories, not a proposal to move packages. Generic helpers
remain below workflows; domain helpers retain their business-specific rules.
Assign a finding to the layer that owns the correction and link affected callers.

## SDK

The shared transport and Books/Inventory resource base provide clear owners for
cross-service fixes. Existing tests cover token refresh, rate limits, streaming,
and ordinary pagination. Historical hardening is documented in
[SDK audit findings](okf/sdk-audit-findings.md); those improvements do not establish
that every neighboring failure path is covered.

### SDK-001 — File uploads are not safely replayed

- **Priority / status:** High / Fixed, awaiting verification; supported by static code inspection.
- **Original evidence (before the 2026-11-06 correction):** [transport](src/zoho/core_sdk/base_client.py) reuses request arguments for
  401 and rate-limit retries without restoring file positions.
  [WorkDrive upload](src/zoho/wd/resources/files.py) supplies an open binary file.
  Multipart preparation consumes that file before the retry.
- **Impact:** A retry can send empty or incomplete attachment content.
- **Correction owner:** Shared transport; avoid separate fixes in upload callers.
- **Close when:** Regression tests prepare real multipart bodies and prove equal
  content on 401 and 429 retries, including a nonzero initial stream position;
  non-seekable streams have explicit, safe behavior. Existing token and retry
  tests must still pass.

### SDK-002 — Pagination can conceal incomplete reads

- **Priority / status:** Medium / Fixed, awaiting verification; committed in
  `d0e00672976c6bfd3ae5b2c5db450f2fcbfbaf2e`, verified locally on Windows x64
  and macOS 26.6.2 arm64; hosted CI evidence pending.
- **Evidence:** [BaseResource.list_iter](src/zoho/core_sdk/base_resource.py) defaults a
  missing resource key to `[]` and exits before checking pagination when records
  are empty. It does not validate record or pagination field types.
- **Impact:** A malformed response or incorrect resource key can be reported as
  a complete empty/partial dataset. Financial consumers can inherit that error.
- **Correction owner:** Shared resource pagination, preserving documented
  service-specific response contracts.
- **Close when:** Tests cover missing/wrong-type records, malformed pagination,
  an empty page claiming more results, valid empty results and multiple pages.
  Inconsistent responses must fail with endpoint/page context, without silently
  returning partial success or looping indefinitely.
- **Implementation / local evidence:** Committed in
  `d0e00672976c6bfd3ae5b2c5db450f2fcbfbaf2e`. `BaseResource.list_iter` validates
  the resource list/records, page context, boolean continuation flag and echoed
  page number before yielding a page; rejects empty pages claiming continuation.
  `tests/test_resource_validation.py` covers malformed and valid empty responses,
  second-page failure, custom keys, multiple pages and request parameters.
  Raw CRUD/binary responses remain untouched. Full Windows suite results are in
  the [type-safety implementation entry](CHANGELOG.md#implement-incremental-python-type-safety);
  macOS 26.6.2 arm64 passed `tests/test_resource_validation.py`, `mypy`, and the
  full parallel/serial suites (2758 passed, 4 subtests passed in 3.94s / 4.00s
  with 4 workers) on 2026-11-05.
  No live calls or hosted CI runs were performed.

## Helper

Client injection, Decimal calculations, scoped item selection and explicit
planning are useful foundations. Recovery guarantees vary by workflow:
[payment renumbering](src/workflows/payment_renumbering/engine.py) requires a
checkpoint callback before execution, while paired offsets do not. Share
checkpoint mechanics when appropriate; keep different financial recovery rules
in their domain owners.

### HELPER-001 — Uncertain paired-payment results trigger unsafe compensation

- **Priority / status:** High / Fixed, awaiting verification; failure path established by static review,
  uncertain server completion not reproduced against a live service.
- **Original evidence (before the 2026-11-06 correction):** [offset processor](src/workflows/vendor_customer_offset/processor.py)
  creates a customer payment, then a vendor payment. Any exception in the second
  operation, including a missing returned ID, leads to customer-payment deletion.
  It does not reconcile whether the vendor payment actually committed first.
- **Impact:** A committed vendor payment whose response was lost can remain on
  its own after compensation. A process interruption can also lose in-memory
  recovery evidence. A failed rollback report omits the known customer payment ID.
- **Correction owner:** Vendor/customer offset workflow. Its
  [operational contract](okf/vendor-customer-offset.md) must be updated with the fix.
- **Close when:** Persist intent and known IDs around mutations; distinguish
  definite rejection from uncertain completion; verify live state before
  compensation or retry. Cover committed-but-response-lost results, missing IDs,
  rollback failure and interrupted-run recovery without duplicate payments.
  The existing ordinary rollback test alone is insufficient.

## Apps

Applications generally separate presentation from workflow logic and use client
factories. Reviewed mutation UIs use request tokens and explicit confirmation.
Host validation differs across applications, and executable local verification
was unavailable during this review.

### APPS-001 — Local review servers lack consistent Host validation

- **Priority / status:** Medium / Fixed, awaiting verification; missing validation confirmed statically,
  DNS-rebinding exploitability not demonstrated.
- **Original evidence (before the 2026-11-06 correction):** [payment review](apps/bank_collections/payment_review.py) and
  [dashboard](apps/dashboard.py) serve token-bearing pages without checking the
  request Host. [Beat allocation](apps/customers/allocate_customer_beats.py) already checks
  the expected local host and port.
- **Impact:** Loopback binding and request tokens alone leave a potential
  DNS-rebinding route to local data/actions in affected browser environments.
- **Correction owner:** App HTTP handlers; a focused shared guard is appropriate
  if its semantics match across these servers.
- **Close when:** Handler tests reject foreign Host values on page/API routes,
  accept documented local addresses/ports, and preserve existing token and
  explicit-confirmation requirements.

### APPS-002 — Workspace test environment cannot start

- **Priority / status:** Medium / Fixed, awaiting verification; committed in
  `731fe01875699833065e933caf429acf9e0047e6` and
  `7a059766774718b707cf434588276cfdc35e9e8b`, runtime verified on Windows x64
  (2026-11-01/04) and macOS 26.6.2 arm64 (2026-11-05).
- **Evidence:** `.venv/Scripts/python.exe -m pytest -q` exits before collection
  because the Python 3.14 executable referenced by the environment is missing.
  This is not evidence of failing product tests or a CI failure.
- **Correction owner:** Local developer setup. Keep the Python 3.14 requirement;
  recreate the workspace environment using an available compatible interpreter.
- **Close when:** Workspace Python starts, declared dependencies install, and
  relevant tests plus the full suite execute with recorded outcomes. Keep
  unrelated failures distinct from findings addressed by a change.
- **Resolution / verification:** Committed in
  `731fe01875699833065e933caf429acf9e0047e6` and
  `7a059766774718b707cf434588276cfdc35e9e8b`. User restored the CPython 3.14.4
  interpreter on Windows. Added `tzdata` to workflow dependencies and installed it
  in the existing `.venv`; made the HDFC BOM fixture explicitly UTF-8. Redirected
  pytest cache to `output/pytest-cache` because legacy cache directories reject
  writes. Windows x64 full suite passed serially and in parallel (2756 passed,
  1 skipped, 4 subtests passed). On macOS 26.6.2 arm64 (2026-11-05), user-authorized
  `.venv/bin/python -m pip install -e ".[workflows,test,typing]"` installed
  `pytest-xdist==3.8.0`, `mypy==2.4.1`, `types-requests==2.32.4.20250913`,
  `tzdata==2026.6`, and `python-dotenv==1.2.4` (`pip check` clean). Default 4-worker
  parallel pytest passed twice (**2758 passed, 4 subtests passed** in 3.94s and
  4.00s), 2-worker passed in 4.98s, and serial (`-n 0`) passed in 7.67s;
  `analyze_project.py --since HEAD --verify` also passed cleanly. The local Mac
  `.venv` uses `Python 3.14.10` rather than pinned `3.14.4` (tracked under APPS-003).

## Prevent repeated fixes and repeated findings

### APPS-004 — Tracked local/generated artifacts

- **Priority / status:** Medium / Verified; committed in
  `3491064612175fd875a3eb5fda7d4ef9cb0a96d4` and
  `731fe01875699833065e933caf429acf9e0047e6`, verified on Windows x64 and
  macOS 26.6.2 arm64.
- **Evidence:** Eight tracked `src/zoho/**/__pycache__` symlinks include absolute
  targets in an old Mac checkout. Git also tracks nine files in `tests/.tmp/`
  and five in `tests/.tmp_output/`. Four timestamped snapshot JSON files in the
  latter directory have identical nonempty content. `config/statement-schedules.yaml`
  is tracked despite an existing ignore rule and a separate example template.
- **Correction:** Remove generated artifacts from version control after confirming
  no fixture dependency; add ignore coverage for test scratch directories.
  Untrack local configuration while preserving the user's local file and example.
  Review `workspace_metadata/` ownership separately: its SQLite catalog is used
  by workflows and must not be discarded as an ordinary cache.
- **Close when:** Fresh checkout has no tracked cache symlinks/test output/local
  deployment configuration, local configuration remains intact, and relevant
  tests pass.
- **Implementation / checks:** Untracked all eight cache links, fourteen test
  scratch files and the local schedule configuration in
  `3491064612175fd875a3eb5fda7d4ef9cb0a96d4`; added cache-file and test-scratch
  ignore rules in `731fe01875699833065e933caf429acf9e0047e6`. Git listing
  confirms no affected paths remain tracked; ignore checks and SHA-256 comparison
  of local configuration pass. Full test suite verified on Windows x64 and
  macOS 26.6.2 arm64 (2756 passed, 1 skipped, 4 subtests passed).

### APPS-005 — Agent policy duplicated in GEMINI.md

- **Priority / status:** Medium / Verified; committed in
  `731fe01875699833065e933caf429acf9e0047e6`, verified on Windows x64 and
  macOS 26.6.2 arm64.
- **Evidence:** `GEMINI.md` links to canonical `AGENTS.md` but repeats Unix-only
  execution commands and permits `uv run`, conflicting with the newer explicit
  interpreter/environment-preservation rules.
- **Close when:** Keep one policy owner in `AGENTS.md`; make `GEMINI.md` a thin
  pointer, retaining only genuinely tool-specific guidance if necessary.
- **Implementation / checks:** Replaced duplicated policy with a five-line
  pointer to `AGENTS.md` in `731fe01875699833065e933caf429acf9e0047e6`; link and
  documentation checks pass via `apps/analyze_project.py`.

Exact-content comparison found no nonempty duplicate source modules among
readable tracked regular files. Empty package markers and documented/tested
compatibility adapters are not removal candidates solely because they are small.

## Cross-machine follow-up

Portable setup rules now live in [AGENTS.md](AGENTS.md) and the
[development runbook](okf/development-runbook.md). Fresh local environments,
explicit deployment configuration and checkpoint handoff remain necessary.
Documentation changes do not close APPS-002 or prove platform compatibility.

### HELPER-002 — Tenant-specific configuration defaults

- **Priority / status:** Medium / Fixed, awaiting verification.
- **Original evidence (before the 2026-11-06 correction):** [Config](src/workflows/runtime/config.py) includes deployment-specific
  defaults for Analytics organization, payment accounts and a stock-count worksheet.
  A fresh machine can inherit these when settings are omitted.
- **Close when:** Affected workflows require explicit deployment values and fail
  before network mutations when values are absent, with tests and documented
  compatibility migration. Until then, configure those values explicitly on every
  deployment.

### APPS-003 — Cross-platform and dependency reproducibility unverified

- **Priority / status:** Medium / In progress; dependency constraints implemented locally, runtime and hosted verification pending.
- **Evidence:** CI now includes Ubuntu, Windows x64 and macOS 26 arm64 jobs;
  hosted CI results remain unverified. Local macOS 26.6.2 arm64 passed `mypy`,
  `analyze_project.py --verify`, and the full test suite on 2026-11-05 (2758 passed,
  4 subtests passed in 3.94s / 4.00s with 4 workers, 4.98s with 2 workers, and
  7.67s serially), after user-authorized installation of `.[workflows,test,typing]`.
  However, the Mac `.venv` uses CPython 3.14.10 instead of pinned 3.14.4, and
  dependency ranges in base/workflow extras are open-ended while `uv.lock` is
  ignored, so identical source revisions can resolve different dependency versions.
- **Close when:** Supported operating systems have recorded passing validation
  with aligned `.venv` pins/extras and a deliberate dependency constraint/lock
  policy provides repeatable application installs. Python package compatibility
  ranges and app deployment pins have different purposes; do not blindly pin
  library consumers.

The two initial reviews inspected the same unresolved code paths without
implementing fixes, so recurrence in their reports was not proof of regression.
Historical hardening documentation describes completed improvements but has not
served as a cross-project register of remaining gaps.

Use this register for subsequent reviews:

1. Read existing IDs before creating a finding. Update the same ID when the
   trigger, owner and failure path match; link related findings when they differ.
2. Use **Open**, **In progress**, **Fixed, awaiting verification**, **Verified**,
   or **Reopened**. Status changes need evidence; a proposed fix is still Open.
3. Fix the owning layer and inspect its callers. Add a regression test for the
   failure mechanism, including realistic payload consumption or uncertain API
   outcomes where relevant.
4. Record the implementation commit, test names/commands and actual results
   before marking Verified. Record required read-back evidence for authorized
   live changes; unit tests cannot establish remote state.
5. Reopen a Verified finding only with evidence that its failure returned. Keep
   its previous fix/test references and explain why protection was insufficient.
6. Future reports should identify new, changed, verified or reopened findings.
   Unchanged Open findings may be summarized by ID without presenting them as
   newly discovered defects.

Recommended work order for remaining open/pending items: HELPER-001 for financial
recovery safety, SDK-001 for upload retry safety, APPS-001 for local server Host
validation, HELPER-002 for explicit deployment configuration guards, and APPS-003
(including Mac `.venv` pin/extra alignment and hosted CI verification to close
SDK-002 and APPS-002). APPS-004 and APPS-005 are Verified.
