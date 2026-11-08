---
name: project-analysis-collect
description: "Triggers on '/project-analysis-collect' or 'Run project data collection'. Executes Section 1 of the Tiered Project Analysis Protocol using Flash 3.8: mines, prunes, and condenses repository context into output/project-analysis/structural_digest.json."
---

# Project Analysis: Data Collection & Extraction (Phase 1)

**Model Target**: Gemini 3.8 Flash (or fast/efficient model)
**Objective**: Mine, filter, and condense repository context into a compact schema without burning frontier model tokens.

---

## Instructions for the Agent

### 1. Local Pruning
* Scan repository source files using local shell utilities (`find`, `grep`).
* **Strictly ignore**:
  * `.venv/`
  * `node_modules/`
  * `target/`, `build/`, `dist/`
  * `.git/`
  * test fixtures and caches (`.pytest_cache`, `__pycache__`)
  * lockfiles (`uv.lock`, `poetry.lock`, `package-lock.json`)

### 2. Extraction Pass
* Read discovered source files across primary application code, library code, and workflows.
* Extract **only**:
  * **Data structures, schemas, and public API interfaces** (e.g., Pydantic models, TypedDicts, dataclasses, traits, class declarations, exported functions).
  * **Inter-module call graphs, import dependencies, and routing maps**.
  * **Core business logic workflows, hot paths, and transport mechanisms** (HTTP clients, session handling, DB/disk sinks).
* **Strict Constraint**: Zero prose, zero boilerplate copying, and no line-by-line file dumps.

### 3. Output Persistence
* Compile and persist the structural digest into:
  * Primary: `output/project-analysis/structural_digest.json`
  * Human-readable summary: `output/project-analysis/structural_digest.md`
* Report summary metrics upon completion: total files surveyed, modules extracted, and saved artifact paths.
