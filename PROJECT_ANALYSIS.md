# Project analysis and finding register

Review baseline: 2026-11-01. Code and tests remain authoritative. This document
owns cross-project review findings; operational contracts remain in their OKF
concepts. The review sampled shared infrastructure and representative financial
workflows and applications; it is not an exhaustive audit.

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

- **Priority / status:** High / Open; supported by static code inspection.
- **Evidence:** [transport](src/zoho/base_client.py) reuses request arguments for
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

- **Priority / status:** Medium / Open; supported by static code inspection.
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

## Helper

Client injection, Decimal calculations, scoped item selection and explicit
planning are useful foundations. Recovery guarantees vary by workflow:
[payment renumbering](src/workflows/payment_renumbering/engine.py) requires a
checkpoint callback before execution, while paired offsets do not. Share
checkpoint mechanics when appropriate; keep different financial recovery rules
in their domain owners.

### HELPER-001 — Uncertain paired-payment results trigger unsafe compensation

- **Priority / status:** High / Open; failure path established by static review,
  uncertain server completion not reproduced against a live service.
- **Evidence:** [offset processor](src/workflows/vendor_customer_offset/processor.py)
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

- **Priority / status:** Medium / Open; missing validation confirmed statically,
  DNS-rebinding exploitability not demonstrated.
- **Evidence:** [payment review](apps/payment_review.py) and
  [dashboard](apps/dashboard.py) serve token-bearing pages without checking the
  request Host. [Beat allocation](apps/allocate_customer_beats.py) already checks
  the expected local host and port.
- **Impact:** Loopback binding and request tokens alone leave a potential
  DNS-rebinding route to local data/actions in affected browser environments.
- **Correction owner:** App HTTP handlers; a focused shared guard is appropriate
  if its semantics match across these servers.
- **Close when:** Handler tests reject foreign Host values on page/API routes,
  accept documented local addresses/ports, and preserve existing token and
  explicit-confirmation requirements.

### APPS-002 — Workspace test environment cannot start

- **Priority / status:** Medium / Open environment issue; observed 2026-11-01.
- **Evidence:** `.venv/Scripts/python.exe -m pytest -q` exits before collection
  because the Python 3.14 executable referenced by the environment is missing.
  This is not evidence of failing product tests or a CI failure.
- **Correction owner:** Local developer setup. Keep the Python 3.14 requirement;
  recreate the workspace environment using an available compatible interpreter.
- **Close when:** Workspace Python starts, declared dependencies install, and
  relevant tests plus the full suite execute with recorded outcomes. Keep
  unrelated failures distinct from findings addressed by a change.

## Prevent repeated fixes and repeated findings

### APPS-004 — Tracked local/generated artifacts

- **Priority / status:** Medium / Fixed, awaiting verification; cleanup applied 2026-11-01, not committed.
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
  scratch files and the local schedule configuration; removed the generated
  files present locally. Added cache-file and test-scratch ignore rules. Git
  listing confirms no affected paths remain tracked; ignore checks pass.
  SHA-256 comparison confirms local configuration contents are unchanged.
  `.venv/Scripts/python.exe -m pytest -q` cannot start because its interpreter
  is missing, so runtime verification remains pending (APPS-002).

### APPS-005 — Agent policy duplicated in GEMINI.md

- **Priority / status:** Medium / Fixed, awaiting verification; applied 2026-11-01, not committed.
- **Evidence:** `GEMINI.md` links to canonical `AGENTS.md` but repeats Unix-only
  execution commands and permits `uv run`, conflicting with the newer explicit
  interpreter/environment-preservation rules.
- **Close when:** Keep one policy owner in `AGENTS.md`; make `GEMINI.md` a thin
  pointer, retaining only genuinely tool-specific guidance if necessary.
- **Implementation / checks:** Replaced duplicated policy with a five-line
  pointer to `AGENTS.md`; documentation diff checked. Commit evidence remains
  pending; no application behavior changed.

Exact-content comparison found no nonempty duplicate source modules among
readable tracked regular files. Empty package markers and documented/tested
compatibility adapters are not removal candidates solely because they are small.

### Cross-machine follow-up

Portable setup rules now live in [AGENTS.md](AGENTS.md) and the
[development runbook](okf/development-runbook.md). Fresh local environments,
explicit deployment configuration and checkpoint handoff remain necessary.
Documentation changes do not close APPS-002 or prove platform compatibility.

**HELPER-002 — Tenant-specific configuration defaults**: Medium / Open.
[Config](src/workflows/core/config.py) includes deployment-specific defaults for
Analytics organization, payment accounts and a stock-count worksheet. A fresh
machine can inherit these when settings are omitted. Close when affected
workflows require explicit deployment values and fail before network mutations
when values are absent, with tests and documented compatibility migration.
Until then, configure those values explicitly on every deployment.

**APPS-003 — Cross-platform and dependency reproducibility unverified**:
Medium / Open. CI now includes Ubuntu, Windows x64 and macOS 26 arm64 jobs;
passing results and local Windows 11/M4 smoke checks remain unverified.
Dependency ranges are open-ended
and `uv.lock` is ignored. Identical source revisions can resolve different
dependency versions. Close when supported operating systems have recorded
passing validation and a deliberate dependency constraint/lock policy provides
repeatable application installs. Python package compatibility ranges and app
deployment pins have different purposes; do not blindly pin library consumers.

The two reviews in this chat inspected the same unresolved code paths. They did
not implement fixes, so recurrence in their reports is not proof of regression.
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

Recommended work order: APPS-002 to restore verification, HELPER-001 for financial
recovery safety, SDK-001, SDK-002, then APPS-001. This review changed documentation
only; no finding has been implemented or marked Verified.
