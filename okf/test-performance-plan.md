---
type: Plan
---

# Full-suite performance implementation plan

## Target and acceptance

Target: at most 4 seconds from starting the workspace Python process to exit,
including collection, worker startup, all current tests and teardown. Measure
with an external monotonic timer; pytest's reported duration is also recorded.
Scope revised at user request: default collection excludes
`tests/zoho/analytics/test_analytics_metadata.py`. Retain the remaining cases and compiler
contracts without further skips, deselection or cached pass results. Historical
2889-case timings below precede this exclusion and are not like-for-like baselines. Existing platform/dependency skips must be reported.
Validate five consecutive warm runs (each <=4 seconds) and report a separate
cold-cache run. A warm-only result must not be described as unconditional.
Windows AMD64 CPython 3.14.10 is the measured host; macOS and CI need separate
verification. Four seconds is a target, not an established feasible guarantee.

## Measured baseline — 2026-11-06

Revision: `3ee068baa917bfd3b05af3d49242bcaed54aa1f3` plus local dependency,
runbook, changelog and symlink-test changes. Pytest 9.1.0, xdist 3.8.0,
four workers, loadfile distribution. No live service calls requested.

Command: workspace Python `-m pytest -q --durations=25`.
Result: 2887 passed, 2 skipped, 4 subtests passed in 15.24 seconds.
Earlier comparable full run: 14.21 seconds. These are pytest timings, not
externally measured process times. Serial collection-only: 2889 tests in 1.01s.
Durations under concurrency include resource contention.

| Test area | Measured call time | Interpretation |
|---|---:|---|
| Analytics catalog retry/changed/missing definitions | 3.69s | Single-test critical path already consumes most of target |
| Five slow Analytics metadata tests | 6.83s total | Same-file scheduling serializes these on one worker |
| Compiler accept/reject contracts | 1.92s | Fresh temporary mypy cache; two checker calls |
| Six server Host-header cases | About 0.50–0.51s each | serve_forever uses default polling; shutdown is a likely cost |
| Project analysis fixture setup | Up to 0.76s | Investigate fixture setup and subprocess/filesystem work |

## Implementation sequence

1. **Establish repeatable instrumentation.** Capture external elapsed time,
   per-phase durations and per-file totals in ignored output. Run serial and
   2/4/6-worker baselines sequentially, recording counts and machine load.
   Profile collection imports and the two Analytics files separately. Count
   SQLite commits/connections, filesystem writes and actual pacing calls.
   Do not infer database or network causes solely from elapsed time.
2. **Remove measured test-only waits.** In `tests/contracts/security/test_finding_regressions.py`,
   use a short explicit serve_forever poll interval in its server fixture and
   retain real HTTP requests, Host checks and deterministic shutdown/join.
   Verify no leaked threads/ports. Inspect Analytics fixtures for unmocked
   pacing/retry waits; mock only test transport clocks while retaining retry
   count/backoff assertions. Production rate limiting stays enabled.
3. **Reduce Analytics setup and persistence cost.** Start with
   `tests/workflows/analytics_catalog/test_analytics_catalog.py` and `tests/zoho/analytics/test_analytics_metadata.py`.
   Reuse immutable fixture inputs, but keep each mutable database isolated.
   If profiling proves repeated schema construction is dominant, prepare a
   template and copy it per test; keep migration tests on original schemas.
   Preserve real disk/reopen/partial-sync behavior in persistence contracts.
   Avoid disabling SQLite durability globally. Any production transaction
   batching requires separate failure/rollback evidence before adoption.
4. **Improve distribution after fixture safety review.** Compare loadfile
   with load/worksteal using installed xdist capabilities, and 4 versus 6
   workers. Test-level distribution may spread metadata costs, but can increase
   fixture setup. Choose measured total time; retain no worker restart and
   independent temp paths. More workers alone cannot shorten a 3.69s test.
5. **Reduce compiler and collection overhead.** Profile mypy cache creation
   and imports. Evaluate safe incremental cache reuse with isolated writes,
   source/config/version invalidation, and explicit cold validation. Always
   execute positive and negative contracts. Defer heavy test-module imports
   only where collection profiling establishes a benefit. Avoid shared mutable
   caches across workers and do not replace compiler execution with mocks.
6. **Acceptance and reporting.** Repeat full-suite runs with exact counts,
   skipped reasons and serial/parallel consistency; run supported-platform CI.
   Suggested investigation budget: <=1.2s startup/collection, <=2.3s critical
   test path, <=0.5s teardown/reporting. These are allocation targets, not
   predictions. If total exceeds 4s, report the measured floor and remaining
   critical path; a smaller fast subset requires a separate user decision and
   cannot be labeled the full suite.

## Scope and verification limits

This change records analysis and a plan only. Runtime/test optimizations are not
implemented. Related existing finding APPS-003 covers cross-platform validation;
this analysis does not close it. No production financial or persistence rules
may be weakened for the timing goal.

## Eight-worker and metadata follow-up

Eight-worker full runs: 13.58s and 14.48s, each with 2887 passed,
2 skipped and 4 subtests passed. Default changed to eight at user request;
these samples do not establish a consistent speedup over four workers.

Isolated cProfile run of all six metadata downloader tests: 6 passed in 3.15s.
SQLite commit: 218 calls / 1.074s; executescript: 12 / 0.905s;
connection context exits: 144 / 0.615s; execute: 868 / 0.248s.
These internal times total 2.842s. API responses and request pacing are mocked.
Database work is the demonstrated dominant cost; concurrent-run contention
is a plausible explanation for longer full-suite timings, not independently
isolated. Prioritize schema initialization and transaction profiling in step 3.
