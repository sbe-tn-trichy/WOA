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
| Inter-location Analytics Query Table commands | `apps/manage_inter_location_contra_query_table.py` | Create/update filenames are compatibility adapters; update retains its historical saved view ID. |
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

### Repeatable project analysis

Run `apps/analyze_project.py` with the workspace interpreter for an offline
snapshot under ignored `output/project-analysis/`. JSON contains a versioned
structured inventory; Markdown summarizes diagnostics and review candidates.
The command parses source without importing inspected modules, reading credentials,
calling remote services or refreshing Analytics metadata. Its only project writes
are reports; optional check tools can also write their usual caches.

Fast inspection checks static import boundaries and local file links in README,
INDEX, WORKFLOWS, PROJECT_ANALYSIS and the OKF root index. It reports explicit
mypy target coverage separately from transitive checking. Syntax/read failures
are incomplete inspections. Link anchors, full Markdown parsing, dynamic imports
and financial safety are outside these checks.

`--since COMMIT` compares the resolved commit with HEAD and separately lists staged,
unstaged and untracked changes, including renamed/deleted paths. Direct static
import dependents are review candidates, not a complete impact graph. Changes to
SDK/shared workflow infrastructure, tests, configuration or guidance trigger broader
inspection. Ignored local configuration and recovery state are not inventoried.

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
