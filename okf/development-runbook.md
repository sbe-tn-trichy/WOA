---
type: Runbook
title: Development Runbook
description: Local setup, validation commands, and safe development practices for the unified Zoho SDK and workflow packages.
tags: [development, testing, operations, workflows]
sources:
  - id: project-config
    resource: https://github.com/sbe-tn-trichy/zoho_sdk/blob/main/pyproject.toml
    title: Python project configuration
    author: team:sbe-tn-trichy
    last_modified: 2026-08-02
status: active
---

# Local Setup

Both primary machines exclusively use their own project `.venv`. Setup commands
below are for explicitly requested provisioning or repair. Routine execution must
not recreate the environment, switch Python or install/upgrade dependencies.
If `.venv` fails, report the failure and wait for user instruction to repair it.

## Primary machines

| Deployment target | Native architecture | Shell / workspace interpreter |
|---|---|---|
| Windows 11, AMD Ryzen 7600X | x64 | PowerShell / `.venv/Scripts/python.exe` |
| macOS 26 or later, Apple M4 | arm64 | zsh / `.venv/bin/python` |

Use native arm64 Python and native dependencies on the Mac; avoid mixing an
Intel/Rosetta environment with the arm64 environment. Keep the same Git revision
and deployment settings on both machines, with machine-specific credential/input
paths configured locally. On macOS, Homebrew paths can differ from Windows tool
paths; discover tools through PATH or explicit local configuration.

CPython 3.14.4 is pinned in the root `.python-version` for both machines and CI.
The pin guides provisioning; it does not change an existing `.venv`. Report a
version mismatch and obtain user instruction before replacing its interpreter.
The package's `requires-python` remains a library compatibility range, separate
from this exact deployment pin.
New macOS releases are intended targets, not
automatically verified platforms: rerun dependency, import and workflow smoke
checks after an OS, Python or native-tool upgrade before resuming live mutations.

Create a separate virtual environment on every machine. Do not copy `.venv`:
its interpreter paths and installed binaries belong to the local machine.
Use the pinned CPython 3.14.4. Run from the repository root.
With uv installed, these commands work on Windows, Linux and macOS:

```text
uv venv --python 3.14.4
uv pip install --python .venv -e ".[workflows,test]"
```

Without uv, explicitly select an installed CPython 3.14.4 interpreter to bootstrap
`.venv`, then use only its local interpreter. Windows PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[workflows,test]"
```

Linux/macOS:

```bash
python3.14 -m venv .venv
.venv/bin/python -m pip install -e ".[workflows,test]"
```

The `py -3.14` and `python3.14` selectors identify a minor version only; confirm
that the selected interpreter reports exactly 3.14.4 before provisioning, or
use its explicit executable path. Verify the resulting workspace interpreter
with `.venv/bin/python --version` (Windows: `.\.venv\Scripts\python.exe --version`).

Do not borrow another checkout's environment. If the interpreter referenced by
`.venv` is missing, recreate the environment with a compatible interpreter;
never silently fall back to system Python. OCR needs the `ocr` extra as well.
Native tools such as Tesseract and Poppler, and Node for JavaScript UI checks,
need separate installation when required by the selected workflow.

## Machine configuration and recovery state

- Copy `zoho_config.example.json` to ignored `config/config.json` and adapt the
  active profile. Follow the [configuration reference](configuration.md) for
  mappings and credentials. Check process environment and home configuration:
  they can change effective settings even with the same project files.
- Explicitly configure organization, domain, account/location scope, worksheet
  destinations and `TOKEN_URL`. Some existing defaults are tenant-specific;
  successful imports do not establish that the correct tenant was selected.
- A localhost token broker must run on the executing machine, or use an
  explicitly configured reachable service. Never commit tokens, `.env` files,
  broker secrets or local credential JSON. Ignore rules do not untrack files
  already committed.
- Provision inputs and cached Analytics metadata separately. Git does not move
  ignored `output/` data, SQLite catalogs or checkpoints. Metadata refresh remains
  an explicit manual operation; do not trigger it automatically during setup.
- Before moving an unfinished mutation, securely transfer recovery state and
  reconcile live IDs/status. Avoid overlapping mutation runs: local file locks
  and atomic replacement do not coordinate different machines.
- Review ownership of a specific checkout if Git reports dubious ownership.
  Do not disable Git safety globally or configure a wildcard safe-directory.

# Validation

```text
.venv/bin/python -m pip check
.venv/bin/python -c "import zoho; import workflows.core.auth"
.venv/bin/python -m pytest -q
```

On Windows replace `.venv/bin/python` with `.\.venv\Scripts\python.exe`.
For environments without pip, use `uv pip check --python .venv` for read-only
dependency validation. If pytest is absent, report the missing dependency;
installation requires explicit user instruction. Unittest discovery is not an
equivalent replacement for the full suite.

CI is configured for Python 3.14.4 full-suite and base-install checks on Ubuntu,
Windows Server 2025 x64 and macOS 26 arm64, with Node available for UI tests.
These are hosted-runner proxies: Windows Server is not Windows 11, and the Mac
runner is not the user's M4. Passing CI must be supplemented by local smoke
checks on both primary machines. No passing result is implied by configuration.
Record OS, architecture, interpreter version, revision and test outcomes when
investigating machine-specific failures. Runner details are documented in the
[GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

# Development Rules

- Keep generic HTTP and service-client behavior below `workflows`.
- Inject low-level clients into workflows instead of importing workflow code from client packages.
- Mock retry sleeps at their transport call site and set mock backfill fixtures to `books_request_interval_seconds=0.0`; retain assertions for retry counts and requested backoff durations. Production rate limiting and pacing remain enabled.
- Mock network calls in unit tests. Live verification must use runtime credentials and read-only operations unless a mutation is explicitly intended.
- Keep every concrete service `request()` override compatible with the full `BaseZohoClient.request()` signature and forward transport options unchanged.
- Treat `POST`, `PUT`, `PATCH`, and `DELETE` as mutations. Mark a semantically read-only POST explicitly with `is_mutation=False` and cover the exception with a test.
- Never commit tokens, `.env` files, generated reports, logs, or `.codex` artifacts.
- Use canonical `workflows` package names. Retain a compatibility alias only when
  it is explicit, documented, and covered by tests.
- All files placed in `scripts/` are strictly temporary with a 24-hour retention lifespan. Permanent user-facing tools, web servers, and CLI runners belong in `apps/`.
- Never inline HTML/CSS/JS in Python files; save web templates under `apps/static/`.
- Subclass `zoho.base_resource.BaseResource` for all Books and Inventory resources to prevent duplicate CRUD and pagination logic.
- Declare explicit type annotations (PEP 484) on all public function signatures instead of untyped `*args, **kwargs`.
- Use `workflows.core.auth` client factories for all SDK client instantiations.
- Save generated project artifacts under `output/` by default. A documented API
  may honor an explicit absolute caller path after safe validation.

# Safe Workflow Execution

Use dry-run options where a workflow provides them. Verify organization, domain, vendor, location, and destination identifiers before running mutations. Token values and authorization headers must never be logged.

## NeoSeal item alias review

Run the read-only export below to create an all-items catalog and a smaller
review list for NeoSeal Inventory items that do not yet have an `alias_name`:

```bash
uv run python apps/export_neoseal_items.py \
  --purchase-account-id "$NEOSEAL_PURCHASE_ACCOUNT_ID"
```

The export always requests `status="active"`; inactive catalog records are never
included in review or downstream update inputs. The default outputs are `output/neoseal_items.csv` and
`output/neoseal_items_missing_alias.csv`. The latter is the working list for
recording the vendor's exact supplied item name in Books `alias_name`; the
script scopes the catalog by the dedicated NeoSeal purchase account rather than
by a free-text manufacturer value, and never creates or updates Inventory items.

# Related Knowledge

See [Package Architecture](architecture.md), [Configuration Reference](configuration.md), and [OKF Maintenance](okf-maintenance.md).
