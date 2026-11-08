---
name: project-analysis
description: "Triggers on 'Run full project analysis' or /project-analysis. Two-stage review orchestrator: runs Phase 1 data collection (/project-analysis-collect) and Phase 2 deep analysis (/project-analysis-deep)."
---

# Tiered Project Analysis Protocol (Orchestrator)

This workflow coordinates the two-stage project analysis protocol. It can run both stages sequentially, or you can trigger either stage independently.

---

## Standalone Commands

* **Phase 1 (Data Collection & Extraction)**:
  * Slash command: `/project-analysis-collect`
  * Instruction: [project-analysis-collect](../project-analysis-collect/SKILL.md)
  * Target model: Gemini 3.8 Flash
  * Output: `output/project-analysis/structural_digest.json`
* **Phase 2 (Deep Analysis & Reasoning)**:
  * Slash command: `/project-analysis-deep`
  * Instruction: [project-analysis-deep](../project-analysis-deep/SKILL.md)
  * Target model: Gemini 4 Argon
  * Input: `output/project-analysis/structural_digest.json`

---

## Sequential Execution Protocol (`/project-analysis`)

When triggered end-to-end, execute sequentially in two isolated phases:

### Section 1: Data Collection & Extraction (Gemini 3.8 Flash)
1. **Local Pruning**: Scan repository source files, strictly ignoring `.venv/`, `node_modules/`, `target/`, `build/`, `dist/`, `.git/`, test fixtures, and lockfiles.
2. **Extraction Pass**: Extract *only* schemas/models, public interfaces, inter-module call graphs, import dependencies, and core workflow hot paths with zero prose/boilerplate.
3. Save the result to `output/project-analysis/structural_digest.json` (and `output/project-analysis/structural_digest.md`).

### Section 2: Deep Analysis & Reasoning (Gemini 4 Argon)
1. **Input**: Feed *only* the condensed structural digest from Section 1. Never pass raw source directories or full file trees.
2. **Analysis Pass**: Audit architectural integrity (leaks, connection lifecycles, transport bottlenecks), type safety & contracts (typing gaps, payload edge cases), and concurrency/failure resilience (races, blocking, backoff).
3. Output concrete, prioritized recommendations and code patches.
