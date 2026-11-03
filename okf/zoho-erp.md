---
type: reference
description: Generated ERP SDK coverage, authentication, routing and regeneration.
---

# Zoho ERP SDK

`zoho.erp.ZohoERPAPI` exposes 81 resources and 899 named operations generated
from the supplied ERP OpenAPI `.yml` files. It is also exported from `zoho`,
alongside `ZohoERPError`. Resource names come from filenames with hyphens
converted to underscores; method names come from `operationId` converted to
snake case. The checked-in [manifest](../src/zoho/erp/manifest.json) lists every
method, verb, route, version, required query/header names and source SHA-256.
The external source folder is needed only for regeneration, never at runtime.

Applications use the shared auth factory with explicit ERP organization and
data center. ERP needs its own OAuth token and scopes; Books tokens are not
substituted. The token broker keys are `erp` or `zoho_erp_conn`.

```python
from workflows.core.auth import get_erp_client

with get_erp_client(org_id="YOUR_ERP_ORGANIZATION", domain="in") as erp:
    result = erp.departments.list_departments(params={"page": 1, "per_page": 200})
    details = erp.departments.get_department_details("DEPARTMENT_ID")
    # Explicit mutation, only when intended:
    # erp.departments.create_department(body={"department_name": "Accounts"})
```

Each generated method has named string path arguments and keyword-only `body`,
`params`, `headers`, `files`, `stream` and `timeout` arguments. Query filters go
in `params`, JSON fields in `body`; multipart operations send `body` as form
fields and `files` using requests' multipart convention. Callers own file
handles. Binary responses and streamed responses retain shared transport
behavior. Return values are raw API responses; there are no inferred response
models or automatic pagination. Request-body field schemas are not validated;
the service remains authoritative. Required query/header parameters and required
bodies declared by the source are checked locally.

Organization scope is injected and conflicting overrides rejected. Path IDs are
encoded as individual segments. Each operation uses its source v1 or v3 route,
with the configured data-center suffix; the direct SDK defaults to India as in
the source definitions, while the workflow factory uses the configured domain.
Availability outside India has not been verified. Shared transport provides
OAuth refresh, timeouts, mutation-aware token selection and HTTP errors through
`ZohoERPError`. The SDK does not add dry-run behavior to low-level mutations.
Existing shared transport limitations, including multipart retry replay
(SDK-001 in the [finding register](../PROJECT_ANALYSIS.md)), still apply.

Inventory workflow routing and vendor catalog scoping remain owned by the
[Inventory client guidance](zoho-inventory.md); ERP resource availability does
not migrate existing workflows to ERP.

## Regeneration

From the repository root with the existing workspace environment and the
declared workflow PyYAML dependency available:

```powershell
.\.venv\Scripts\python.exe apps/generate_erp_sdk.py D:\path\to\zoho_erp_api_doc
.\.venv\Scripts\python.exe -m pytest tests/test_erp_sdk.py -q
```

The generator parses all files and compiles the generated Python before writing
`src/zoho/erp/generated.py` and `manifest.json`. Unsupported servers, conflicting
operation names, unresolved references and empty input fail explicitly. Review
the generated diff and run tests after changing definitions. YAML is a build-time
dependency only; the SDK runtime uses the existing base dependencies.

Automated verification covers all 899 route bindings, HTTP auth/errors,
organization isolation, mutation intent, token refresh, multipart forwarding,
required parameters, invalid identifiers, and deterministic regeneration.
No live ERP calls have been performed; API availability, permissions and
source-schema completeness require separate read-only live verification.
