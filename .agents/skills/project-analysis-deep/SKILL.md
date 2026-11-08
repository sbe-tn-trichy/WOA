---
name: project-analysis-deep
description: "Triggers on '/project-analysis-deep' or 'Run deep project analysis'. Executes Section 2 of the Tiered Project Analysis Protocol using Argon: performs deep architectural, contract, and concurrency review exclusively on the extracted structural digest."
---

# Project Analysis: Deep Analysis & Reasoning (Phase 2)

**Model Target**: Gemini 4 Argon (or Pro frontier model)
**Objective**: Perform deep architectural review, vulnerability discovery, and performance auditing exclusively on the extracted structural digest.

---

## Instructions for the Agent

### 1. Input Specification
* Read **only** the condensed structural digest produced by Phase 1:
  * `output/project-analysis/structural_digest.json` (or `output/project-analysis/structural_digest.md`)
* **Strict Constraint**: Do **never** pass raw source directories, broad file trees, or wholesale codebase dumps into the reasoning context. Rely solely on the extracted structural digest.

### 2. Analysis Pass
Perform focused auditing across three primary dimensions:

1. **Architectural Integrity**:
   * Lifecycle leaks, unclosed connections, and unmanaged sessions.
   * Transport layer bottlenecks, retry storms, and unthrottled external calls.
   * Layering violations (e.g. workflows importing CLI apps, circular dependencies).
2. **Type Safety & Contracts**:
   * Interface parity and typing gaps across boundaries.
   * Payload handling edge cases, missing validation, and unsafe casts.
   * Public contract drift between services and client SDKs.
3. **Concurrency & Failure Modes**:
   * Race conditions, thread/async blocking operations, and deadlocks.
   * Error resilience, transient failure handling, and exponential backoff.
   * State divergence during partial failures or interruptions.

### 3. Deliverables
* Output concrete, prioritized findings (High / Medium / Low).
* Provide actionable recommendations and ready-to-apply code patches for discovered vulnerabilities.
