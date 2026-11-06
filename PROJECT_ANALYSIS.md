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

## Finding summary

Implementation and verification are separate; the detailed evidence below owns
closure criteria. No findings are closed by adding inspection tooling alone.

| ID | Priority | Correction owner | Implementation | Verification |
|---|---|---|---|---|
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
| Helper | `src/zoho/helpers/`, `src/workflows/core/`, domain packages in `src/workflows/` | Reusable API compositions, financial rules, planning, matching, checkpoints and recovery |
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
- **Original evidence (before the 2026-11-06 correction):** [transport](src/zoho/base_client.py) reuses request arguments for
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
- **Evidence:** [BaseResource.list_iter](src/zoho/base_resource.py) defaults a
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
- **Original evidence (before the 2026-11-06 correction):** [Config](src/workflows/core/config.py) includes deployment-specific
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
