---
type: Runbook
title: Development Runbook
description: Local setup, validation commands, and safe development practices for the WOA SDK and workflow packages.
tags: [development, testing, operations, workflows]
sources:
  - id: project-config
    resource: https://github.com/sbe-tn-trichy/WOA/blob/main/pyproject.toml
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

CPython 3.14.10 is pinned in the root `.python-version` for both machines and CI.
The pin guides provisioning; it does not change an existing `.venv`. Report a
version mismatch and obtain user instruction before replacing its interpreter.
The package's `requires-python` remains a library compatibility range, separate
from this exact deployment pin.
New macOS releases are intended targets, not
automatically verified platforms: rerun dependency, import and workflow smoke
checks after an OS, Python or native-tool upgrade before resuming live mutations.

Create a separate virtual environment on every machine. Do not copy `.venv`:
its interpreter paths and installed binaries belong to the local machine.
Use the pinned CPython 3.14.10. Run from the repository root.
With uv installed, these commands work on Windows, Linux and macOS:

```text
uv venv --python 3.14.10
uv pip install --python .venv -e ".[workflows,test]"
```

Without uv, explicitly select an installed CPython 3.14.10 interpreter to bootstrap
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
that the selected interpreter reports exactly 3.14.10 before provisioning, or
use its explicit executable path. Verify the resulting workspace interpreter
with `.venv/bin/python --version` (Windows: `.\.venv\Scripts\python.exe --version`).

Do not borrow another checkout's environment. If the interpreter referenced by
`.venv` is missing, recreate the environment with a compatible interpreter;
never silently fall back to system Python. OCR needs the `ocr` extra as well.
Native tools such as Tesseract and Poppler, and Node for JavaScript UI checks,
need separate installation when required by the selected workflow.

The `workflows` extra includes `tzdata` so `zoneinfo` can resolve IANA names such
as `Asia/Kolkata` on Windows without a system timezone database. Text fixtures
containing a BOM or other Unicode characters must specify UTF-8 explicitly.
Pytest stores its cache under ignored `output/pytest-cache`, avoiding legacy
root cache directories that may retain permissions from another installation.
Pytest temporary test directories are separate from this cache; sandbox access
restrictions must be reported separately from product failures.

## Machine configuration and recovery state

- Copy `config/config.example.yaml` to ignored `config/config.yaml` and adapt the
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

## Default parallel tests

Run the suite with the workspace interpreter:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

On macOS use `.venv/bin/python`. `pyproject.toml` owns the default: four
pytest-xdist worker processes, `--dist=loadfile`, and no automatic worker restart.
The `test` extra includes pinned `pytest-xdist==3.8.0`; the earlier preparation-only
`test-parallel` extra has been replaced by the standard `test` extra. Provision
new test environments using the existing setup commands. Existing environments
need the updated test dependencies installed only when explicitly authorized;
missing xdist is an actionable setup error (failing with unrecognized `-n`,
`--dist`, and `--max-worker-restart` options), not a reason to switch interpreters.
If an existing `.venv` has not yet been authorized to install `pytest-xdist`,
report the missing plugin and, when read-only serial verification is needed in
the interim, pass `-o addopts="--import-mode=importlib"` to bypass the xdist
flags in `pyproject.toml`.

Use `-n 0` for serial debugging or comparison and `-n 2` to use fewer workers:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -n 0
.\.venv\Scripts\python.exe -m pytest -q -n 2
```

File scheduling keeps tests from the same file on one worker. It does not isolate
filesystem paths or serialize resources shared across files. Use temporary paths,
dynamic ports and mocked remote calls. Session fixtures execute per worker, not
once for the entire run. See the [xdist distribution contract](https://pytest-xdist.readthedocs.io/en/stable/distribution.html)
and [fixture guidance](https://pytest-xdist.readthedocs.io/en/stable/how-to.html#making-session-scoped-fixtures-execute-only-once).
For genuinely shared resources, fix the owning fixture or explicitly coordinate
access; avoid grouping or suppressing flaky tests merely to obtain a passing run.
Compiler contract tests already use temporary mypy caches and API-generation tests
write generated files to temporary destinations.

Push and pull-request CI jobs use the configured default, including type-check
regression tests. Manual **Run workflow → test_workers** defaults to 4 and allows
0 (serial) or 2. The ordinary test extra supplies xdist in all test jobs; base
runtime installation remains independent of the test extra.

When changing workers or distribution, record OS/architecture, interpreter/plugin
versions, revision/local changes and comparable serial/parallel wall times. Repeat
parallel full-suite runs and compare collected/passed/skipped counts. Worker crashes
fail the run instead of restarting and concealing an intermittent failure. Verify
on both primary machines and the hosted matrix; local Windows success does not
establish macOS or hosted-runner compatibility. Actual results belong in the
[project changelog](../CHANGELOG.md#make-parallel-pytest-the-default).
Use fresh sandbox temporary directories as described below when required.

## Offline project analysis

From the repository root on Windows:

```powershell
.\.venv\Scripts\python.exe apps/analyze_project.py
.\.venv\Scripts\python.exe apps/analyze_project.py --since HEAD --verify
.\.venv\Scripts\python.exe -m pytest -q tests/test_project_analysis.py tests/test_api_reference_generator.py
```

On macOS use `.venv/bin/python` for the same arguments. Select a known reviewed
commit instead of HEAD for a substantive incremental review. Reports overwrite
`output/project-analysis/report.json` and `report.md`; preserve them separately
when needed as evidence. Exit codes and review limitations are owned by
[project organization](project-organization.md#repeatable-project-analysis).
The full suite remains `.\.venv\Scripts\python.exe -m pytest -q` on Windows.
If sandbox access blocks pytest's default temporary directory, supply a fresh
`--basetemp=output/pytest-<unique-run-name>`; pytest clears a supplied existing
base directory, so never select a directory containing useful artifacts.
Tests using standard-library `tempfile` may additionally need process-local
`TEMP` and `TMP` pointing at a fresh ignored `output/` subdirectory. This does
not require changing the virtual environment or machine configuration.

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

CI is configured for Python 3.14.10 full-suite and base-install checks on Ubuntu,
Windows Server 2025 x64 and macOS 26 arm64, with Node available for UI tests.
These are hosted-runner proxies: Windows Server is not Windows 11, and the Mac
runner is not the user's M4. Passing CI must be supplemented by local smoke
checks on both primary machines. No passing result is implied by configuration.
Record OS, architecture, interpreter version, revision and test outcomes when
investigating machine-specific failures. Runner details are documented in the
[GitHub runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

# Development Rules

## Type checking

The optional `typing` extra pins mypy and requests stubs for development; it is
not a runtime dependency. Install it in the existing project environment only
when dependency installation is explicitly authorized. Do not synchronize or
replace the environment to run a check.

Run the blocking scope from the repository root:

```powershell
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m pytest -q tests/test_type_safety.py tests/test_resource_validation.py
```

On macOS/Linux use `.venv/bin/python` for both commands. `tool.mypy.files` in
`pyproject.toml` owns the growing checked scope; imported legacy modules are
followed normally but are not all strict targets. A passing check does not mean
the entire repository is typed. Explicit Any and Any from missing imports are
rejected in checked targets; do not fix diagnostics using blanket ignores or
casts of external data. Positive/negative contract tests run the same pinned
checker, including actual SDK clients and a typed fake. They skip only when the
optional checker is absent; the type-check CI job installs it before running them.

The CI gate is configured on all three existing runner platforms. Actual hosted
results and primary-machine smoke results remain required. See the
[migration plan](type-safety-plan.md) for implementation status and remaining work.

## Source and workflow rules

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

## Item catalog and alias review

Use the [item catalog export](item-catalog.md) for any Inventory purchase account.
It owns command usage, status selection, CSV destinations and the retained
Neoseal compatibility entry points. Exporting reads Inventory and writes local
reports; it does not change remote item records.

# Related Knowledge

See [Package Architecture](architecture.md), [Configuration Reference](configuration.md), and [OKF Maintenance](okf-maintenance.md).

## Application dependency baseline (APPS-003)

`constraints.txt` pins the base, workflows, test and typing dependency closure
from the 2026-11-06 macOS environment. Provision application deployments with the
workspace interpreter using `-m pip install -c constraints.txt -e
".[workflows,test,typing]"` only when environment provisioning is authorized.
CI applies the same constraints to its install jobs. Library consumers retain
compatibility ranges in `pyproject.toml`; constraints are an application policy,
not mandatory library dependency pins. Optional OCR/Jupyter tools are outside
this baseline. Windows also constrains its pytest colorama dependency.

Update constraints deliberately from a reviewed environment and validate fresh
installs plus the supported-platform CI matrix. The initial baseline has local
suite evidence on CPython 3.14.10; fresh constrained installs on pinned
3.14.10 and hosted cross-platform runs remain required. Do not replace an existing
workspace environment or upgrade dependencies merely to align this file.
