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
utils (Shared Transport & Primitives) <-- zoho (API Clients & Auth) <-- helpers (Composite API Operations) <-- workflows (Business Engines) <-- apps (Web UIs & CLI Tools)
```

## Layer Boundaries

0. **Shared Utilities Layer (`utils`)**:
   - Organized into domain subpackages: `utils.http_utils` (HTTP transport and client utilities), `utils.file_utils` (file, document and serialization utilities: JSON, YAML, PDF), and `utils.general_utils` (encoding and sequence parsing).
   - Root aliases and meta-path redirection preserve backward compatibility for legacy module paths (`utils.http`, `utils.json`, etc.) and PascalCase aliases (`HttpUtils`, `FileUtils`, `GeneralUtils`).
   - `utils.file_utils.json` owns the RapidJSON codec and its [financial/recovery compatibility rules](json-codec.md).
   - `utils.http_utils.http_transport` owns the pyqwest adapter. See [HTTP transport](http-transport.md) for request encoding, pool ownership, timeouts, TLS and streaming contracts.
   - Service-agnostic HTTP transport primitives (`utils.http_utils.http`): session/mock-compatible request execution (`send_http_request`, `request_json`), JSON/binary response decoding, HTML error sanitization, bounded `Retry-After` parsing, HTTPS override host validation, seekable upload stream replay (`capture_upload_positions`, `rewind_uploads`), and streaming file downloads (`write_response_to_file`).
   - `utils.file_utils.pdf.read_pdf_pages` extracts text through pypdfium2, normalizes CRLF and closes document/page/text handles. Supplier-specific interpretation stays in each workflow.
   - `utils.file_utils.yaml` uses YAMLRocks, preserves legacy scalar interpretation and validates source tags before conversion so custom/Python tags and multi-document configuration fail closed.
   - `utils.general_utils.encoding.detect_encoding` detects character encoding via Rust chardetng.
   - `utils.general_utils.sequences.parse_doc_number` owns the SDK-safe parsing primitive, re-exported by `helpers.formatting.sequences`.
   - Must not import from `zoho`, `helpers`, `workflows`, `google_sheets`, `apps`, or `scripts`.

1. **Core / Client Layer (`zoho.books`, `zoho.wd`, `zoho.creator`, etc.)**:
   - Shared infrastructure lives in `zoho.core_sdk`; service packages retain their clients and resources. The [capability map](project-organization.md#capability-packages) owns physical layout and compatibility details.
   - Base-client error parsing preserves zero API error codes and falls back to alternate codes only for missing/null primary codes; malformed JSON uses sanitized response text.
   - `zoho.core_sdk.logging.configure_service_logger` owns service logger names, files and compatibility loggers; the base client delegates setup to it.
   - Generic REST endpoint wrappers and authentication; `src/zoho/` contains the core SDK only and does not import `helpers`.

   **Composite helpers (`src/helpers/`, alongside `src/zoho/`):**
   - Public composite operations are exported from `helpers`. Implementations are grouped into catalog, report, formatting and operation packages.
   - Helpers may import SDK clients and utilities, but never workflows, apps or scripts.
   - The former `zoho.helpers` import path is removed; callers must import `helpers`.
   - `utils.general_utils.sequences.parse_doc_number` owns the SDK-safe parsing primitive, re-exported by `helpers.formatting.sequences` and the legacy Books GST module.

2. **Workflow Layer (`workflows`)**:
   - Multi-service domain engines and reconciliation algorithms.
   - Pure library code; receives client instances via dependency injection.
   - `workflows.runtime` owns configuration/client construction; `workflows.core` owns pure shared mechanics. Domain engines live in focused sibling packages.
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
- Books and Inventory resources reuse `zoho.core_sdk.base_resource.BaseResource`; workflow
  conversions reuse `workflows.core.matching` when their semantics fit.
- Public signatures use explicit typed parameters, and stable structured records
  crossing workflow boundaries use `TypedDict` or dataclasses.
- Applications obtain clients from `workflows.runtime.auth` factories.
- Use the Zoho Inventory API for item and inventory-related operations, including
  catalog reads and updates, stock, warehouses, and inventory adjustments.
  Vendor catalog queries must retain `purchase_account_id` scoping. Applications
  inject a separate Inventory client when a Books transaction needs item lookup
  or creation; Books clients do not expose an item resource. See
  [Inventory API routing](zoho-inventory.md) for the public API migration.

## Authentication and failure ownership

`zoho.core_sdk.auth` owns OAuth refresh, the HTTP token broker and explicit Catalyst mutation
token selection. `zoho.core_sdk.security` remains separate: it owns filename/output-path
safety and recursive log-parameter redaction, used by downloads and logging as well
as authenticated clients. Combining them would couple unrelated SDK operations.

`zoho.core_sdk.exceptions` owns the shared exception hierarchy and response metadata.
Existing service exceptions and their constructor fields remain supported.
`ZohoConfigurationError` identifies missing credentials, unavailable keyring setup
and invalid broker configuration; it also remains catchable as `ValueError`.
`ZohoTokenResponseError` identifies malformed, rejected or incomplete token
responses and remains catchable as both `ZohoAuthError` and `ValueError`.
`ZohoTokenServiceError` identifies broker/OAuth HTTP failures and is a
`ZohoAuthError`. Missing keyring dependencies now raise `ZohoConfigurationError`
instead of `ImportError`. All three are exported from `zoho`.

Token-service exceptions suppress unsafe underlying HTTP/response text in displayed
tracebacks. Broker tokens must be strings or null; blank values are missing tokens.
OAuth tokens and positive integer lifetimes are validated before either cached field
is replaced. Refresh/access are serialized per manager; short lifetimes retain a
positive cache window. These exceptions do not authorize automatic replay of
financial mutations. API service errors retain their status/code/payload metadata;
callers should inspect that metadata rather than infer categories from messages.

## Shared primitives and extracted domain workflows

Generic document-number parsing lives in `utils.general_utils.sequences`, re-exported by
`helpers.formatting.sequences` and reusable by
Books GST and workflow consumers. Pure workflow FY selection and sequence analysis
live in `workflows.core`; Analytics queries stay in `payment_inspection`.
Customer validation and invoice-YAML sales-order import are workflow APIs, with
explicit breaking migrations from their former Books bindings. Renumbering uses
live Books state and checkpointed read-back verification. See
[workflow helpers and migration](workflow-helpers.md).
