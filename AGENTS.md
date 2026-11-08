# Repository Guidance

## Source of Truth

- Code and tests are authoritative. Use [`INDEX.md`](INDEX.md) only as a
  navigation aid.
- Before a multi-file or behavior-changing task, read [`okf/index.md`](okf/index.md)
  and the relevant concepts. Correct stale concepts in the same change.

## Development Priorities

Apply these priorities in order; satisfying the requested outcome must preserve
correctness and data safety:

1. **Requested business outcome:** Deliver the task's required behavior. Avoid
   speculative features, frameworks, and unrelated cleanup.
2. **Correctness and data safety:** Preserve accounting rules, vendor scoping,
   explicit mutation intent, recovery checkpoints, and required live verification.
3. **Usability:** Make command selection, inputs, defaults, reports, and errors
   understandable. Explain what an operation will change.
4. **Readability:** Use focused functions, descriptive names, typed inputs, and
   business rules that are easy to locate. Comments explain reasons rather than
   repeat mechanics already clear from the code.
5. **Reuse and maintainability:** Share mechanics only when their semantics match.
   Keep distinct business rules separate even when their implementations resemble
   one another.
6. **Performance:** Optimize demonstrated bottlenecks, especially repeated API
   calls, without obscuring correctness.

## Task Scope and Acceptance

- When the user requests an implementation plan, use the repository-root
  `IMPLEMENTATION.md` alongside `CHECKLIST.md`. Create it if needed and update
  the existing file for plan revisions, unless the user specifies another path.
  Keep the plan local and Git-ignored.

- Establish the expected outcome, acceptance criteria, and whether live changes
  are authorized from the user's request and session context. Ask only when
  material information or authorization is missing; routine work does not need
  a separate approval step.
- Complete the agreed scope before introducing adjacent improvements.
- Tie refactoring to a concrete usability, correctness, or maintenance problem.
  Preserve behavior unless a behavior change is requested or necessary for the
  authorized fix. File size alone is not a reason to rewrite a module.
- For project cleanup, prioritize clear workflow ownership and command selection
  before extracting specific duplicated logic.

## Architecture

- Library code lives in `src/utils/` (cross-service utilities such as `utils.http_utils.http`),
  `src/zoho/` (core SDK), `src/helpers/` (composite API operations), and `src/workflows/` (domain workflows);
  permanent entry points live in `apps/`.
- Read `project_structure.max_nested_folder_depth` from `config/config.yaml` for
  the maximum directory depth beneath `apps/` and `src/workflows/`
  (root depth 0; a direct child is depth 1). Use 2 if the local file or key is
  absent. Depth 2 supports cohesive subpackages within an app or workflow domain.
  Values must be non-negative integers, excluding booleans. The offline analyzer
  and architecture tests check this policy. The optional,
  Git-ignored `output/` directory is exempt from the depth rule.
- Maintain nesting within that configured depth and a strict limit of $\le 10$ files per directory across
  `apps/`, domain packages, and output locations to prevent clutter and preserve
  maintainability.
- Group operational scripts into domain subdirectories within the configured depth under `apps/`
  (e.g., `apps/<domain>/`) alongside unified entry-point dispatchers at the `apps/`
  root. Transparent meta-path redirection in `apps/__init__.py` preserves
  backward-compatible imports for legacy script paths.
- Imports flow `utils <- zoho <- helpers <- workflows <- apps`. `utils` must not import from
  `zoho`, `helpers`, `workflows`, `google_sheets`, `apps`, or `scripts`. The core SDK
  must not import `helpers` or `workflows`; helpers must not import `workflows`.
  Neither SDK, helpers nor workflows may import from `apps` or `scripts`; workflows
  contain no servers or CLI parsers.
- `scripts/` is Git-ignored scratch space with a retention target under 24 hours.
- Keep web HTML/CSS/JS in `apps/static/`, loaded from Python rather than embedded.
- Export supported public APIs and exceptions from the relevant `__init__.py`.

### File organization and refactoring

- Apply responsibility-based organization to every package, including the core
  SDK, helpers, workflows, apps and tests. Before adding or expanding a file,
  inspect its owner, neighboring modules, imports and callers; choose placement
  deliberately rather than defaulting to the package root.
- Follow the established capability-package pattern (for example, `utils.http_utils`
  and `zoho.core_sdk`); see the [package map](okf/project-organization.md#capability-packages).
  Keep package roots focused on public exports and essential shared contracts.
  Group related implementations into clearly named subpackages when a directory
  mixes responsibilities or would exceed ten files. Respect the configured
  nesting limit wherever it applies; do not flatten unrelated code to satisfy it.
- Keep each module focused on one cohesive responsibility. Extract independent
  responsibilities when extending a mixed module; merge modules only when they
  share ownership, dependencies and reasons to change. A shared topic such as
  "security" does not by itself justify combining authentication, path handling
  and log redaction.
- Use descriptive domain or capability names. Avoid catch-all `misc`, `common`
  or `helpers` modules inside packages when a specific owner can be named;
  `src/helpers/` remains the established composite API layer.
- Scope reorganization to the requested work and affected owners. Existing mixed
  or overfull directories require a focused correction when touched, not an
  unrelated repository-wide rewrite; file length alone does not justify a split.
- For moves or splits, update imports, package exports, mirrored tests, type-check
  targets, generators and owning documentation together. Preserve supported
  public imports through tested re-exports when compatibility is required, and
  document intentional breaking changes. Verify import direction and cycles,
  relevant behavior and directory file counts before reporting completion.

## Implementation

- Prefer small reusable modules and established dependencies over duplicate or
  bespoke infrastructure.
- Extend the existing owner first. Add a module when it has a distinct
  responsibility, and prefer small helpers with explicit inputs over generic
  engines with many switches.
- Compare business semantics before consolidating code; similar names or
  structure alone do not establish duplication.
- Give each operation a clear primary entry point. Retain older commands only
  for needed compatibility, documented and covered by tests.
- Fail with actionable context. Never silently skip invalid financial records
  or report incomplete work as successful.
- Books and Inventory resources reuse `zoho.core_sdk.base_resource.BaseResource`.
- Reuse `workflows.core.matching` conversions when their semantics fit.
- Public APIs use explicit typed parameters. Use `TypedDict` or dataclasses for
  stable structured records crossing workflow boundaries.
- Applications construct SDK clients through `workflows.runtime.auth` factories.
- Use the Zoho Inventory API for item and inventory-related operations, including
  item catalog reads and updates, stock, warehouses, and inventory adjustments.
- Scope item catalog queries in vendor workflows (bills, purchase orders, vendor
  credits, and catalog exports) using `purchase_account_id` to prevent
  cross-vendor item collisions while using the Zoho Inventory API.
- Deliver complete implementations; do not leave accidental placeholders,
  `pass`, or TODO markers. Intentional abstract/protocol stubs are allowed.


## Execution Environment & Fast-Path

- **Immediate Execution**: Attempt a requested execution first without unrelated exploration. This does not authorize live mutations or bypass explicit confirmation. If the interpreter/configuration is unavailable, report the failure and follow the setup runbook; never switch silently to another environment or tenant.
- Use uv for authorized environment provisioning, package installation and dependency checks; pip is not required. Follow the runbook and preserve the constraints baseline.
- Always run Python commands and tests using the workspace virtual environment:
  - Windows PowerShell: `.\.venv\Scripts\python.exe <script>` and `.\.venv\Scripts\python.exe -m pytest`.
  - Linux/macOS: `.venv/bin/python <script>` and `.venv/bin/python -m pytest`.
  - Use the explicit workspace interpreter above for routine execution. Do not use a runner that may automatically create or synchronize the environment.
- Never invoke global/system `python` or bare `pytest` for project execution. An explicitly selected compatible interpreter may bootstrap `.venv` as described in the runbook.

### Multiple machines

- Primary deployment targets are Windows 11 x64 (Ryzen 7600X) and macOS 26+ arm64 (Apple M4). Use native x64 Python on Windows and native arm64 Python on the Mac. See the runbook for verification limits and OS-upgrade checks.
- Both machines exclusively use their own project `.venv`. Do not switch environments, recreate `.venv`, change Python, or install/upgrade dependencies without explicit user instruction. If execution fails, report the failure and propose the needed repair; do not automatically alter the environment.

- Discover the checkout root and host OS; do not assume a drive, username, shell, sibling checkout or installed tool path. Run from the repository root.
- Both project environments must use CPython 3.14.10, pinned in `.python-version`. Create `.venv` separately when provisioning is requested; never copy or sync it. A pin does not modify or validate an existing environment. Version mismatches require reporting, not automatic replacement. Install declared extras only when explicitly instructed.
- Keep credentials and deployment configuration local. Follow the [configuration hierarchy](okf/configuration.md); verify effective organization, domain and account/location scope before live work. Process environment and home configuration can differ across machines.
- `localhost` refers to the executing machine. Provision its token broker or explicitly configure a reachable service.
- Git does not transfer ignored reports, SQLite catalogs or recovery checkpoints. Securely transfer required recovery state and reconcile live records before resuming on another machine; a missing checkpoint does not prove nothing was posted. Avoid overlapping financial mutations without workflow-specific coordination.
- Read [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md) before reviews or related fixes. Reuse finding IDs and record implementation/test evidence before closure; unchanged open findings are not new regressions.
- Follow the [development runbook](okf/development-runbook.md). Report actual tested platforms; written rules alone do not establish OS compatibility.

### Workflow Command Index

The table uses Linux/macOS paths. On Windows replace `.venv/bin/python` with
`.\.venv\Scripts\python.exe` and `.venv/bin/pytest` with
`.\.venv\Scripts\python.exe -m pytest`, retaining script paths and arguments.

| Workflow / Task | Direct Execution Command |
|---|---|
| **GSTR-2 Verification** | `.venv/bin/python apps/verify_gstr2.py` |
| **GSTR-3B vs P&L Comparison** | `.venv/bin/python apps/compare_gstr3b_pnl.py` |
| **Payment Review / Allocations** | `.venv/bin/python apps/payment_review.py` |
| **Bank Collection Reconciliation** | `.venv/bin/python apps/run_collection_reconciliation.py` |
| **Neoseal Stock Count** | `.venv/bin/python apps/neoseal_stock_count.py` |
| **Neoseal Item Audit** | `.venv/bin/python apps/audit_neoseal_items.py` |
| **Apply Neoseal Name Updates** | `.venv/bin/python apps/apply_neoseal_name_updates.py` |
| **Export Inventory Items** | `.venv/bin/python apps/inventory/export_items.py --purchase-account-id ACCOUNT_ID` |
| **Creator Customer Sync** | `.venv/bin/python apps/sync_creator_customers.py` |
| **Creator Beat Sync** | `.venv/bin/python apps/sync_creator_beats.py` |
| **Stock Transfer** | `.venv/bin/python apps/transfer_stock.py` |
| **Project Dashboard** | `.venv/bin/python apps/dashboard.py` |
| **Offline Project Analysis** | `.venv/bin/python apps/analyze_project.py` |
| **Generate API Reference** | `.venv/bin/python apps/generate_api_reference.py` |
| **Run All Tests** | `.venv/bin/pytest -q` |


## Safety and Verification

- Analytics design and metadata analysis must use `workflows.analytics_catalog.AnalyticsCatalog`
  and the canonical SQLite catalog. Use cached metadata for analysis and design
  planning; show the last successful metadata sync time in Markdown outputs and
  responses. Refresh metadata only when the user requests manual sync. After live
  query-table changes, verify saved SQL with targeted read-back before reporting
  success; this does not imply a full catalog sync. Report sync failures explicitly.
- Maintain Analytics workflow/view references in `analytics_catalog/registry.py`;
  provide explicit references for configurable view IDs. Use the catalog's workflow
  impact report before changing shared views.

- Generated project artifacts default to `output/`. APIs may honor a caller's
  explicit absolute path when documented and safely validated.
- Never commit credentials, local configuration, generated output, logs, or
  `.codex` artifacts. Mock network access in unit tests; mutations require
  explicit intent and should offer dry-run behavior where practical.
- Add pytest coverage for changed normal, edge, and error paths. Tests may live
  in `tests/` or beside workflows as configured by `pyproject.toml`.
- Run the relevant tests and, when practical, the full suite. Report unrelated
  failures accurately; do not change unrelated work merely to make the suite green.

## OKF Maintenance

### Mandatory project changelog

- Update root [CHANGELOG.md](CHANGELOG.md) in the same change for every logical project change: code, tests, dependencies, CI, configuration behavior, rules, documentation, refactoring, cleanup and reversions. Do this before reporting completion, even when no commit is requested.
- Every entry must explain **Why**, **What**, and **Verification** (actual checks/results or why not run and remaining limitations). Group related edits into one logical entry; update that entry during the same task instead of logging each file save.
- Use a newest-first ISO date in Asia/Kolkata and a descriptive change title. Date alone is insufficient. Add related finding IDs and implementation commit references when available; timestamps are optional and must include a timezone if used.
- Describe local/environment changes without secrets, credentials, customer data or machine-private paths. Routine read-only inspections and generated test/cache output do not require entries unless they lead to a project or environment change. Editing the changelog itself does not require a recursive extra entry.
- `CHANGELOG.md` owns project change history. `okf/log.md` records knowledge-bundle changes and links to the project entry when applicable; it does not replace the mandatory project entry.
- On every logical change, check annual rollover using the current Asia/Kolkata year. Keep only current-year entries in root `CHANGELOG.md`; move older entries intact to `changelog/YYYY.md` for their original year, creating an archive only when needed. Merge without duplicating existing entries, retain newest-first ordering and link each archive from the root file. Repair affected relative links and inbound entry links when moving content; never discard history.
- Keep each entry concise: one logical change, a short reason, resulting behavior and verification. Link to commits, findings and owning documentation for detail instead of copying diffs or logging individual file edits. This rollover check is part of each change, not a separate recurring task.

When a change creates durable knowledge about architecture, configuration,
operations, public APIs, compatibility, or known limitations:

Keep one documentation owner for each topic and link to it elsewhere instead
of copying detailed instructions.

1. Update the relevant OKF concept and its nearest `index.md` if needed.
2. Give each concept file (except `index.md` and `log.md`) YAML frontmatter with
   a non-empty `type`.
3. Add a concise newest-first entry to the nearest `log.md` under an ISO date.
4. Use ordinary Markdown links and exclude transient status, secrets, tokens,
   customer data, and details already obvious from the diff.

Only the root `okf/index.md` has frontmatter (`okf_version` only); `log.md` has none.
