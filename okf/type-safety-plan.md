---
type: Plan
title: Incremental Python Type Safety
status: in-progress
---

# Python type-safety implementation plan

## Outcome and scope

Make incorrect internal calls fail static checks and malformed external records
fail validation before financial planning or mutation. Keep Python, the existing
`zoho <- workflows <- apps` architecture, and existing public behavior unless a
separately identified correctness fix requires a documented change.

The migration is incremental. Its implemented scope and outstanding work are
recorded below; this plan never authorizes live writes. Implement each phase as
a reviewable change with its own changelog evidence.

## Checker migration — 2026-11-07

The active checker is pinned `ty==0.0.99`, run with the workspace interpreter
using `-m ty check`. `tool.ty.src.include` retains the previous explicit target
list and `tool.ty.environment` sets Python 3.14 and the source import path.
Positive and negative compiler contracts exercise ty, including rejection of
swapped IDs, float stock quantities and invalid result statuses. ty defaults
replace mypy strict settings; explicit-Any rejection is not equivalent.
Historical mypy results below describe the earlier checker, not current coverage.
See the [runbook](development-runbook.md#type-checking) for current commands.

## Implementation status — 2026-11-03

- The pinned mypy 2.4.1 development extra and requests stubs are installed in
  the existing, user-authorized CPython 3.14.4 workspace environment. The default
  blocking command checks 24 source/contract files, with strict checking,
  explicit-Any rejection and normal import following. No blanket suppressions,
  casts, or import skipping were added. Imported legacy modules are not yet
  themselves strict targets; the exact checked scope is `tool.mypy.files`.
- CI now configures the same gate on Ubuntu, Windows and macOS. Local Windows
  checks pass; hosted CI and local macOS execution have not been performed.
- Final Windows full-suite verification outside the sandbox: 1824 passed,
  1 optional OCR test skipped, 4 subtests passed. Dependency consistency, CLI
  help and local documentation links also pass. See the project changelog for
  the recorded command context and platform limits.
- Payment renumbering and its CLI have typed client protocols, nominal IDs,
  payment/allocation snapshots, result status literals, and validated API/audit
  boundaries. Existing schema-1 plans remain resumable. Runtime validation runs
  before processing loaded plans; checkpoints still precede writes and live
  read-back still verifies results. Positive contracts check concrete SDK clients
  and a typed fake; negative fixtures prove the checker rejects swapped IDs,
  float quantities and invalid statuses through actual domain APIs.
- Stock-transfer planning/payload construction, offset client/report/tranche
  contracts, shared date/sequence/checkpoint/payment helpers, and collection
  allocation/record/index helpers are included. Collection allocations now reject
  nonfinite payment amounts and invalid invoice balances instead of skipping
  invalid financial input. Existing wire floats are retained; domain calculations
  are not switched to float. These slices do not establish end-to-end coverage
  of stock-transfer execution or collection review.
- Shared BaseResource narrows arbitrary responses to object and validates
  paginated records before yielding a page (SDK-002). Raw CRUD/action responses
  remain untouched at runtime, including binary responses. This deliberately
  requires static consumers to narrow opaque responses before reading fields.
- The initial advisory pre-change scan produced 351 error diagnostics across
  `src` and `apps`; its generated report is local under `output/`. This is a
  baseline, not a passing repository-wide result or a list of verified bugs.

### Remaining implementation

1. Complete offset financial boundary validation. Its historical invalid-to-zero
   conversion remains a separate concern. The later HELPER-001 correction adds
   scoped checkpoints and reconciliation; implementation and verification limits
   belong to the [finding register](../PROJECT_ANALYSIS.md).
2. Carry typed stock-transfer records through its execution CLI and journal;
   migrate collection review/reconciler/repair services and their application
   entry points. The existing total-false proposal records are not proof that
   every field is available in every execution state.
3. Migrate shared HTTP transport/token/callback types and every service override,
   then auth/configuration, Google Sheets and remaining workflow/app boundaries.
   Retain the SDK-001 retry regression coverage documented in the finding
   register. Expand the blocking file list as each slice passes.
4. Verify hosted and primary-machine execution, and publish package typing markers
   with wheel/consumer verification only after supported public APIs are ready.

This is an implemented foundation and financial migration slice, not completion
of every phase below. [Development commands](development-runbook.md#type-checking)
and the [project changelog](../CHANGELOG.md) own operational and test evidence.

## Inspected baseline

- `pyproject.toml` and `.github/workflows/tests.yml` have pytest coverage but no
  configured static checker or type-checking job.
- `zoho.core_sdk.base_client` and `zoho.core_sdk.base_resource` expose dynamic transport/resource
  records; resource clients and several callbacks are typed as `Any`.
- `workflows.payment_renumbering.engine` already has `RenumberPlan` and
  `RenumberResult` TypedDicts, but clients, snapshots, and status strings remain
  loosely typed. Its existing checkpoint/live-verification contract makes it a
  bounded first workflow to migrate.
- `workflows.vendor_customer_offset.processor` uses a validated configuration
  dataclass but dynamic contact, allocation, and result dictionaries.
- `workflows.stock_transfer.processor` has a `TransferLine` dataclass but dynamic
  item/location/bin inputs and nested storage records.
- `workflows.core.snapshots` and `helpers.operations.records` demonstrate existing
  Protocol patterns. Extend the owning modules rather than build a new framework.

## Design rules

1. Treat JSON, CSV, YAML, SQLite rows, UI requests, and checkpoint files as
   untrusted input. Narrow from `object` using explicit validation; a `cast` or
   TypedDict annotation does not validate data. Allow extra vendor fields where
   harmless, but require and validate every field used for financial decisions.
2. Use TypedDict for stable wire/report dictionaries and frozen dataclasses for
   validated domain records. Preserve optional versus absent field semantics.
   Use focused parsers and existing conversions first; do not introduce a runtime
   validation dependency without a demonstrated need and authorization to install.
3. Use `NewType` for materially confusable IDs such as customer, vendor, invoice,
   bill, payment, item, and location IDs, placed at their lowest shared owner.
   Construction follows validation. These types do not enforce runtime identity
   or tenant/vendor scope; continue explicit scope checks.
4. Use Decimal in financial calculations, date/datetime for normalized dates,
   and explicit serialization at boundaries. Preserve existing precision,
   rounding, timezone, and vendor payload contracts. Do not globally change
   `to_decimal`, `parse_date`, or historical permissive conversion semantics.
5. Protocols describe only operations actually required by each workflow and
   must match real SDK signatures. Check concrete clients and representative
   test fakes against them; dynamic mocks alone do not prove compatibility.
6. Model result states with Literal tags and discriminated unions when fields
   differ by state. Known remote IDs and uncertain outcomes must remain visible.
   A type cannot prove that a remote request committed or make a plan authorized.
7. Confine necessary `Any` to documented integration boundaries. No blanket
   missing-import suppression, import skipping, unchecked casts of JSON, or
   whole-file ignores to make a financial module appear checked. Local exceptions
   need an error code, reason, and removal condition.

## Phase 1 — Establish a reproducible checking gate

**Owners:** `pyproject.toml`, `.github/workflows/tests.yml`, development runbook.

- Adopt one checker: ty, invoked through the workspace Python. Verify support
  for CPython 3.14.4, existing syntax, and all three CI platforms before choosing
  a fixed tooling version. Record that version in a separate development extra;
  keep it out of runtime dependencies. Dependency installation is a separately
  authorized environment action under the runbook.
- Inventory diagnostics, missing third-party stubs, public untyped APIs, and
  `Any` propagation. Store generated reports under `output/`; do not guess an
  error count. Check existing installed tooling without modifying the environment.
- Configure source roots/package discovery for `src/zoho`, `src/workflows`, and
  `src/google_sheets`, accounting for package exports and app imports.
- Start a blocking strict target with a small pure module such as
  `workflows.core.sequences`; expand a reviewed module allowlist each phase.
  Keep imports followed normally. An advisory broad scan may accompany the
  blocking target, but must not conceal errors in dependencies of strict targets.
- Require strict checks plus unused-ignore reporting. Strict mode alone permits
  explicit Any; additionally reject explicit Any in migrated domain modules and
  Any from missing imports. Keep any necessary transport exceptions narrowly
  scoped and documented. Verify the selected checker's actual flag behavior.
- Add a CI job using the same configuration/version as local execution. Test
  checker installation and execution on Ubuntu, Windows, and macOS initially;
  preserve full-suite and base-install jobs and record primary-machine limits.

**Exit:** The initial strict target has zero diagnostics; CI fails on an
intentional wrong argument/return during verification; removing the deliberate
mistake restores success. No blanket suppressions or environment replacement.
Document `.venv/Scripts/python.exe -m ty check` on Windows and
`.venv/bin/python -m ty check` on macOS/Linux once configured.

## Phase 2 — Complete payment renumbering end to end

**Owners:** `workflows/payment_renumbering`, its existing helper dependencies,
calling apps, and relevant tests; public exports remain in `__init__.py`.

- Inventory actual response variants, callers, persisted plans/checkpoints, and
  existing tests before defining schemas. Preserve public dictionary shapes
  through explicit adapters where compatibility is needed.
- Introduce typed payment identity, allocation, expected snapshot, discovery,
  and result records; replace unrestricted status strings with the actual states.
- Add focused parsers for Analytics discovery, Books payment envelopes and
  allocations, and saved plan/checkpoint inputs. Reject missing/wrong-type records
  with field/record context and no secret/full-payload logging.
- Replace `books: Any` and `analytics: Any` with narrow compatible Protocols;
  type the checkpoint callback and concrete SDK surface needed to satisfy them.
  Validate UI/CLI inputs before calling the workflow.
- Preserve live identity checks, destination collision checks, checkpoint-before-
  mutation ordering, and post-write read-back. Version persisted formats only if
  necessary; test old checkpoint compatibility or explicit rejection before writes.

**Exit:** The workflow, its typed boundaries and calling app paths pass the
blocking check; existing normal behavior remains covered. Tests cover invalid
envelopes, absent/wrong-type IDs, invalid/nonfinite amounts, malformed allocation
rows and dates, and checkpoint parsing. Static checks demonstrate rejection of
swapped ID types, incorrect amount types, and invalid result-state handling using
small maintained checker fixtures with narrowly coded expected diagnostics.

## Phase 3 — Expand financial workflow coverage

**Order:** vendor/customer offset, stock transfer, then payment allocation and
collection reconciliation. Inventory each slice's callers/dependencies first.

- Offset: type contacts, GSTIN pairing, invoice/bill allocations, tranches,
  payment payloads, and outcomes; validate input before allocation. Replace
  silent invalid-to-zero handling only in a separately tested correctness change.
- Stock transfer: type Inventory items, locations, bins, TransferLine storage
  records and paired transaction results. Preserve purchase-account scoping,
  stock/commitment guards, tax/account rules, and Books/Inventory routing.
- Payment/collection workflows: type review choices, validated plans, allocation
  records, checkpoints and results; retain explicit confirmation and scope guards.
- Carry each slice through its app, serialization, concrete clients and fakes.
  Add modules to the strict gate only when they meet the full acceptance criteria.

**Finding coordination:** HELPER-001 (uncertain offset completion), SDK-001
(upload retries), SDK-002 (pagination), and HELPER-002 (tenant defaults) remain
separate correctness work in the [finding register](../PROJECT_ANALYSIS.md).
Typing does not close them. The later correctness corrections and remaining
verification are recorded there; retain their regression coverage when migrating
types. No live writes are needed to type the workflow.

**Exit per slice:** Zero blocking diagnostics; normal/edge/error tests pass;
invalid financial input fails before any mocked mutation; existing output,
payload, checkpoint, confirmation, and scope contracts are preserved or explicitly
migrated. No financial calculations acquire a float intermediary.

## Phase 4 — Harden shared SDK and remaining application boundaries

- Extend `BaseZohoClient` types for token providers, refresh/completion callbacks,
  headers, query parameters, files, JSON and binary/stream results. Preserve the
  complete request contract in every service override. Use overloads only where
  a real input discriminator determines the return type.
- Type `BaseResource` client interaction without pretending all endpoints have
  identical envelopes. Keep generic CRUD mechanics; add endpoint-owned schemas
  and parsers where workflows need guarantees. Do not rewrite all resources into
  a universal generic schema engine.
- Cover malformed envelopes and pagination under SDK-002's separate behavioral
  acceptance criteria, and retain retry/auth/upload tests around SDK changes.
- Expand strict checking through auth factories, configuration, Google Sheets,
  remaining workflows, CLI arguments and HTTP request parsing. Validate CSV/PDF/
  OCR extraction before it enters financial logic; raw extraction may stay flexible.
- Publish a `py.typed` package marker only once supported public APIs have usable
  annotations; verify built-wheel contents and a consumer type-check smoke case.
  Document partial coverage honestly while migration continues.

**Exit:** Supported public APIs and permanent entry points are in the blocking
scope, structured records are exported, service overrides and client protocols
are compatible, and all remaining dynamic exceptions have narrow owners/reasons.

## Verification and completion

For every implementation slice, run the blocking checker, relevant pytest tests,
and the full suite when practical, using only the existing workspace interpreter.
Mock all network access. Measure progress by checked module coverage, remaining
public Any signatures and reviewed suppressions, not annotation count. Do not
accept a shrinking error count achieved by excluding previously checked modules.

Maintain the runbook as the command owner and this plan as the migration owner;
link rather than duplicate instructions. Update owning workflow concepts for
durable schema/API changes, OKF log, and root changelog. Record actual platform,
interpreter and test results; CI configuration alone proves no compatibility.

Completion means the selected scope has zero diagnostics, external input is
validated before financial decisions, required regression tests pass, and public/
persisted contracts are documented. Repository-wide completion additionally
requires all supported source and app modules in the gate. Static checking never
replaces accounting invariants, recovery, explicit mutation intent or live
verification required by a workflow.

## Tool references

- [ty configuration](https://docs.astral.sh/ty/configuration/)
- [ty rules](https://docs.astral.sh/ty/rules/)
