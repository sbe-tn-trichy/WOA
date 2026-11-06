---
type: reference
description: Navigation ownership, overlapping commands, and consolidation boundaries.
---

# Project organization

The README is the starting page for setup and navigation. WORKFLOWS.md owns the
business workflow catalog; INDEX.md owns SDK surface navigation. Detailed generated
Sphinx/Markdown API references live in [docs/api/](../docs/api/README.md) and are built by
[apps/generate_api_reference.py](../apps/generate_api_reference.py). OKF concepts own detailed operational contracts.
Keep detailed instructions in their owning concept and link to them from the starting
pages instead of copying them.

[Project analysis and finding register](../PROJECT_ANALYSIS.md) owns cross-project
review findings, grouped into SDK, helper and apps. Reuse its finding IDs and
record implementation and verification evidence when resolving or reopening an
issue; operational concepts retain ownership of detailed behavior contracts.

`AGENTS.md` is the single repository policy owner; `GEMINI.md` is a discovery
pointer for Gemini. Generated Python caches and test scratch output are ignored,
and local `config/statement-schedules.yaml` is provisioned per machine from its
tracked example. Existing users keep their local configuration when untracking;
new checkouts need to create it before running that workflow.

## Overlap and ownership

| Area | Canonical owner | Why related modules remain separate |
|---|---|---|
| Inter-location unified CLI | `apps/inter_location.py` | Unified dispatcher for contra, proposals, and updates; historical standalone apps delegate here. |
| Neoseal unified CLI | `apps/neoseal.py` | Unified dispatcher for stock count, audit, export, name updates, and formatting; historical apps delegate here. |
| GST verification unified CLI | `apps/verify_gst.py` | Unified dispatcher for GSTR-1, GSTR-2, GSTR-3B vs P&L, and cash ledger; standalone apps delegate here. |
| Inter-location Analytics Query Table commands | `apps/manage_inter_location_contra_query_table.py` | Create/update filenames are compatibility adapters; update retains its historical saved view ID. |
| Inter-location workflow operations | `workflows.inter_location` | Packages contra detection, location/payment proposals, and update logic; root `inter_location_*.py` modules provide compatibility redirects. |
| Books financial statement sheet operations | `workflows.books_statements` | Packages statement sheet preparation, account catalog, custom module stores, and P&L notes; root modules provide compatibility redirects. |
| GST workflow operations | `workflows.gst` | Packages cash-ledger check and monthly GST movements; root modules provide compatibility redirects. |
| Customer management workflow operations | `workflows.customer_management` | Packages analytics sync, invoice/payment review, normalization, and local store; root modules provide compatibility redirects. |
| Books and Inventory CRUD | `zoho.base_resource.BaseResource` | Service base classes select their exception and logger. |
| Bank statement categorization | `workflows.collection_reconciliation` | Review, generic schema reconciliation and allocation repair have different input and mutation contracts. |
| Payment linking/backfills | `workflows.core.payments` for common evidence | Creator-to-Books and Books-to-Creator writes have opposite directions and conflict rules. |
| Neoseal operations | `neoseal_audit` and `neoseal_stock_count` | Catalog quality and stock-sheet synchronization are distinct operations sharing Inventory access. |

Prefer the Query Table manager for new usage:

```bash
.venv/bin/python apps/manage_inter_location_contra_query_table.py --help
```

Without `--view-id`, it previews creation. With `--view-id ID`, it previews an
update. Both require `--apply` to save. Historical create/update commands delegate
to the same parser and execution path; output wording is now shared.

## Further cleanup boundaries

### Routine local cleanup

Run `.venv/bin/python apps/cleanup_project.py` weekly to preview disposable
files older than seven days. Add `--apply` to remove the listed files, or
`--older-than-days N` to change the minimum age. Run when builds and tests are
idle. The command only scans `build/`, `.pytest_cache/`, `output/pytest-cache/`,
`output/mypy-cache/`, `output/tmp/`, and Python bytecode caches beneath `apps/`,
`src/` and `tests/`. It leaves empty directories intact. Git-tracked files and
symlinks are excluded; tracking and file identity are rechecked during apply.
An inspection/deletion failure returns a nonzero status; deletion can be partial.
Checks do not coordinate concurrent writers, so this is not a cleanup service
for actively running workflows.

Scripts, logs, other output, configuration, Analytics metadata, databases and
recovery checkpoints are excluded. New disposable scratch data should go in
`output/tmp/`; do not store evidence or recovery data there. The existing
24-hour scratch-script target requires review and promotion before removal,
rather than deletion based on age alone.

### Promoted scratch operations

Eight local scratch implementations were superseded and removed after promotion.
Their fixed customer IDs, expected document counts and obsolete Flat-column
migration assumptions are not permanent defaults. Evidence JSON/PDFs and journals
remain intact. Other one-off scripts still require separate review.

| Former scratch operation | Permanent owner and command |
|---|---|
| `sync_one_creator_customer.py`, `sync_requested_customers.py` | [Creator customer sync](creator-customer-delete-sync.md#explicit-customer-selection), using repeated `--customer-id` selections on `apps/sync_creator_customers.py` |
| `verify_stockcount_formulas.py`, `apply_stockcount_formulas.py`, `update_stockcount_formulas.py` | [Stock-count formula helpers](neoseal-stock-count.md#formula-inspection-and-execution), used by `apps/sync_neoseal_stockcount.py`; obsolete positional formulas are replaced by the existing stable SKU plan |
| `audit_polycab_pdf_records.py`, `report_polycab_pdf_records.py` | [Polycab credit review](polycab-credit-review.md#saved-evidence-review), using the canonical parser/rules and `apps/review_polycab_vendor_credits.py` for live or saved evidence |
| `recover_stock_transfer.py` | [Recorded-pair recovery](stock-transfer.md#recorded-pair-recovery), using `workflows.stock_transfer.recover_stock_transfer` and `apps/recover_stock_transfer.py` |

Domain helpers stay with their workflow packages; only shared mechanics such as
cell addresses, currency parsing and atomic checkpoints use existing common owners.

### Repeatable project analysis

Run `apps/analyze_project.py` with the workspace interpreter for an offline
snapshot under ignored `output/project-analysis/`. JSON contains a versioned
structured inventory; Markdown summarizes diagnostics and review candidates.
The command parses source without importing inspected modules, reading credentials,
calling remote services or refreshing Analytics metadata. Its only project writes
are reports; optional check tools can also write their usual caches.

Fast inspection checks static import boundaries, local file links and cross-file
Markdown heading anchors in README, INDEX, WORKFLOWS, PROJECT_ANALYSIS, AGENTS,
GEMINI, CHANGELOG and `okf/*.md`, plus OKF frontmatter rules (`type:` required
on concept files; no frontmatter on `okf/log.md`). It reports explicit mypy target
coverage separately from transitive checking. Syntax/read failures are incomplete
inspections. In-page anchors, full CommonMark parsing, dynamic imports and
financial safety are outside these checks.

`--since COMMIT` compares the resolved commit with HEAD and separately lists staged,
unstaged and untracked changes, including renamed/deleted paths. Review candidates
include 1-hop `direct_dependents`, multi-hop `transitive_dependents`, and
`affected_tests` (test files that changed or statically import changed modules
directly or transitively); static imports remain review candidates rather than a
complete runtime impact graph. Changes to SDK/shared workflow infrastructure,
tests, configuration or guidance trigger broader inspection. Ignored local
configuration and recovery state are not inventoried.

`--verify` additionally runs the existing API reference check and configured mypy
using the executing interpreter. It never installs tools. Exit codes are 0 for
completed clean checks, 1 for diagnostics/check failures, and 2 for incomplete
execution (including missing tooling or invalid revisions). Failed invocations
before report generation leave any previous report intact; check its capture time.
Verification subprocesses have bounded timeouts. Capture time and measured duration
are separate from otherwise stable inventory data; verification logs/timings can vary.

For a review, read the finding register first, select a known baseline, inspect
changed code and affected callers, and run relevant tests. Record the reviewed
commit/local changes, scope, exclusions, platform and verification evidence in
PROJECT_ANALYSIS. Keep periodic whole-project reviews: unchanged code is not
certified by incremental inspection. Financial checkpoints, vendor scoping and
live-state recovery require business-specific review and authorized verification.

WORKFLOWS owns entry points, remote operation profiles and contract links. Read
profiles may still generate local reports. Keep recovery details in the linked
contracts and do not infer safety from names, `dry_run` flags or checkpoint calls.

Large modules worth reviewing include GSTR-2's verifier, collection review, and
Neoseal stock-count reporting. Size alone does not prove duplication. Extract
cohesive parsing, planning or reporting responsibilities with tests before moving
files or merging workflows. Preserve live-state checks, checkpoint recovery,
purchase-account scoping and domain-specific amount/date semantics.

Inter-location proposal, review and execution commands are stages of a workflow,
not automatically duplicate implementations. Keep their review/mutation boundary
visible when simplifying the catalog or adding a unified command.

Related: [Architecture](architecture.md), [shared helpers](workflow-helpers.md),
[workflow catalog](../WORKFLOWS.md).
