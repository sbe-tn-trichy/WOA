---
type: Concept
title: Package Architecture & Modularity
description: Layered architecture, import direction rules, and subpackage encapsulation in the WOA repository.
tags: [architecture, modularity, layers, imports]
sources:
  - id: package-root
    resource: https://github.com/sbe-tn-trichy/WOA/blob/main/src/zoho/__init__.py
    title: Package root exports
    author: team:sbe-tn-trichy
    last_modified: 2026-08-02
status: active
---

# Layered Architecture

`WOA` enforces strict modularity through a layered architecture with one-way import rules:

```
utils (Shared Transport & Primitives) <-- zoho (API Clients & Auth) <-- workflows (Business Engines) <-- apps (Web UIs & CLI Tools)
```

## Layer Boundaries

0. **Shared Utilities Layer (`utils.http`)**:
   - `utils.json` owns the RapidJSON codec and its [financial/recovery compatibility rules](json-codec.md).
   - `utils.http_transport` owns the pyqwest adapter. See [HTTP transport](http-transport.md) for request encoding, pool ownership, timeouts, TLS and streaming contracts.
   - Service-agnostic HTTP transport primitives: session/mock-compatible request execution (`send_http_request`, `request_json`), JSON/binary response decoding, HTML error sanitization, bounded `Retry-After` parsing, HTTPS override host validation, seekable upload stream replay (`capture_upload_positions`, `rewind_uploads`), and streaming file downloads (`write_response_to_file`).
   - `utils.pdf.read_pdf_pages` extracts text through pypdfium2, normalizes CRLF and closes document/page/text handles. Supplier-specific interpretation stays in each workflow.
   - `utils.yaml` uses YAMLRocks, preserves legacy scalar interpretation and validates source tags before conversion so custom/Python tags and multi-document configuration fail closed.
   - Must not import from `zoho`, `workflows`, `google_sheets`, `apps`, or `scripts`.

1. **Core / Client Layer (`zoho.books`, `zoho.wd`, `zoho.creator`, `zoho.helpers`, etc.)**:
   - Base-client error parsing preserves zero API error codes and falls back to alternate codes only for missing/null primary codes; malformed JSON uses sanitized response text.
   - `zoho.logging.configure_service_logger` owns service logger names, files and compatibility loggers; the base client delegates setup to it.
   - Generic REST endpoint wrappers, authentication helpers, and reusable composite overlay helpers (`zoho.helpers`).
   - `zoho.helpers` provides domain-agnostic composite functions (e.g. contact/item lookups, custom field extraction, WorkDrive upload-and-attach) reducing boilerplate in workflows.
   - Low-level clients and helpers do not import workflows or apps.

2. **Workflow Layer (`workflows`)**:
   - Multi-service domain engines and reconciliation algorithms.
   - Pure library code; receives client instances via dependency injection.
   - Contains no web servers, UI code, or runnable scripts.

3. **Applications Layer (`apps/`)**:
   - User-facing entry points: local HTTP review servers, dashboards, and CLI runners.
   - Imports from `workflows` and `zoho` to coordinate end-to-end execution.

4. **Ephemeral Scripts (`scripts/`)**:
   - Reserved strictly for temporary, disposable scratch scripts (TTL < 24 hours).

# Design Rules

The agreed [development priorities and scope rules](../AGENTS.md#development-priorities)
govern implementation choices. Repository guidance owns these standards; this
concept documents the architectural boundaries they apply to.

- Lower layers (`zoho`, `workflows`) never import from `apps` or `scripts`.
- Public APIs are exported through the relevant package `__init__.py`.
- UI templates live in `apps/static/`, not in Python string literals.
- Books and Inventory resources reuse `zoho.base_resource.BaseResource`; workflow
  conversions reuse `workflows.core.matching` when their semantics fit.
- Public signatures use explicit typed parameters, and stable structured records
  crossing workflow boundaries use `TypedDict` or dataclasses.
- Applications obtain clients from `workflows.core.auth` factories.
- Use the Zoho Inventory API for item and inventory-related operations, including
  catalog reads and updates, stock, warehouses, and inventory adjustments.
  Vendor catalog queries must retain `purchase_account_id` scoping. Applications
  inject a separate Inventory client when a Books transaction needs item lookup
  or creation; Books clients do not expose an item resource. See
  [Inventory API routing](zoho-inventory.md) for the public API migration.

## Shared primitives and extracted domain workflows

Generic document-number parsing lives in `zoho.helpers.sequences`, reusable by
Books GST and workflow consumers. Pure workflow FY selection and sequence analysis
live in `workflows.core`; Analytics queries stay in `payment_inspection`.
Customer validation and invoice-YAML sales-order import are workflow APIs, with
explicit breaking migrations from their former Books bindings. Renumbering uses
live Books state and checkpointed read-back verification. See
[workflow helpers and migration](workflow-helpers.md).
