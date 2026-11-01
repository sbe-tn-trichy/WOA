# Changelog

Project changes are recorded newest first. Dates use Asia/Kolkata. Each logical
change has a descriptive title, why it was needed, what changed, and verification
or remaining limits. Include finding IDs and implementation commits when
available; never invent a commit or claim checks that were not run.
This file keeps the current year's entries; older years are archived under
`changelog/YYYY.md` and linked here when created. Check rollover with each change.

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
