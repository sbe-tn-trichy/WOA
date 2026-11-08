---
type: reference
description: Generated ERP SDK coverage, authentication, routing and regeneration.
---

# Zoho ERP SDK

`zoho.erp.ZohoERPAPI` exposes 81 resources and 899 named operations generated
from the supplied ERP OpenAPI `.yml` files. It is also exported from `zoho`,
alongside `ZohoERPError`. Resource names come from filenames with hyphens
converted to underscores; method names come from `operationId` converted to
snake case. The checked-in [manifest](../src/zoho/erp/openapi/manifest.json) lists every
method, verb, route, version, required query/header names and source SHA-256.
The client lives in `zoho.erp.client`. Generated types and operation support
live in `zoho.erp.openapi`, with one generated resource module per resource
grouped into the 13 business-area packages listed below. Existing
imports from `zoho.erp.generated` and `zoho.erp.resource` continue to work.
The external source folder is needed only for regeneration.

Applications use the shared auth factory with explicit ERP organization and
data center. ERP needs its own OAuth token and scopes; Books tokens are not
substituted. The token broker keys are `erp` or `zoho_erp_conn`.

```python
from workflows.runtime.auth import get_erp_client

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
declared base YAMLRocks dependency available:

```powershell
.\.venv\Scripts\python.exe apps/generate_erp_sdk.py D:\path\to\zoho_erp_api_doc
.\.venv\Scripts\python.exe -m pytest tests/zoho/erp/test_erp_sdk.py -q
```

On macOS, use `.venv/bin/python apps/generate_erp_sdk.py /path/to/erp_openapi`.

The generator parses all files and compiles every emitted module before staging
resource modules, package exports, `registry.py`, the `generated.py` compatibility
facade and `manifest.json` under `src/zoho/erp/openapi/`. Unsupported servers, conflicting
operation names, unresolved references and empty input fail explicitly. Review
the generated diff and run tests after changing definitions. YAML is a build-time
dependency only; the SDK runtime uses the existing base dependencies.

Automated verification covers all 899 route bindings, HTTP auth/errors,
organization isolation, mutation intent, token refresh, multipart forwarding,
required parameters, invalid identifiers, and deterministic regeneration.
No live ERP calls have been performed; API availability, permissions and
source-schema completeness require separate read-only live verification.

## Resource-module split proposal

Approved and implemented on 2026-11-08. The former 7,525-line monolith is now
81 resource modules covering the same 899 operations. Each class retains its
method implementations, signatures and docstrings; the largest resource class
has 377 lines. The resource-level boundary gives each operation a direct source
file without changing its API behavior.

### Implemented layout

`resource.py` and `manifest.json` remain at the OpenAPI package root.
`registry.py` defines explicit typed `ERPResources` attributes and `RESOURCE_TYPES`.
`generated.py` is a generated compatibility facade exporting existing resource
class names and registry symbols. `__init__.py` continues
exporting the supported package API. Each business-area folder below contains
one snake_case module per existing resource name and an `__init__.py` exporting
its classes. Existing resource/class/operation spellings remain unchanged.

| Folder under `zoho/erp/openapi/` | Resource modules | Resource names |
|---|---|---|
| `sales/` | 9 | `invoices`, `estimates`, `sales_order`, `credit_notes`, `customer_debit_notes`, `retainer_invoices`, `delivery_challans`, `salesreturns`, `customer_payments` |
| `purchasing/` | 6 | `bills`, `purchase_order`, `purchasereceives`, `recurring_bills`, `vendor_credits`, `vendor_payments` |
| `banking/` | 7 | `bank_accounts`, `bank_rules`, `bank_transactions`, `cards`, `payment_links`, `receipts`, `refunds` |
| `accounting/` | 9 | `base_currency_adjustment`, `chart_of_accounts`, `currency`, `journals`, `opening_balance`, `reporting_tags`, `taxes`, `transaction_locking`, `registers` |
| `assets/` | 1 | `fixed_assets` |
| `inventory/` | 8 | `items`, `compositeitems`, `categories`, `pricelists`, `inventoryadjustments`, `batches`, `serialnumbers`, `transferorders` |
| `manufacturing/` | 9 | `bill_of_materials`, `cost_templates`, `job_cards`, `manufacturing_orders`, `operations`, `shop_floor`, `work_center_timings`, `work_center_types`, `work_centers` |
| `people/` | 9 | `departments`, `designations`, `employee_salary`, `employee_statutory`, `employees`, `income_tax_details`, `payruns`, `salary_revisions`, `users` |
| `expenses/` | 6 | `expense_categories`, `expense_claims`, `expense_reports`, `expenses`, `recurring_expenses`, `trips` |
| `subscriptions/` | 6 | `addons`, `coupons`, `plans`, `products`, `subscription`, `unbilled_charges` |
| `projects/` | 3 | `projects`, `tasks`, `time_entries` |
| `organization/` | 6 | `contacts`, `contact_persons`, `custom_modules`, `integration`, `locations`, `organizations` |
| `fulfillment/` | 2 | `packages`, `shipmentorders` |

The complete mapping covers all 81 manifest resources exactly once. Each folder
contains at most nine resource files plus its package initializer, satisfying the
ten-file limit. The existing app/workflow depth setting does not apply to SDK
packages. `assets/` remains a distinct accounting capability despite having one
resource. Root files contain shared contracts, exports and registry wiring.

### Generation safety and compatibility

The generator owns only Python files carrying its generated-file header and the
manifest. Domain assignments are explicit in `DOMAINS`; new resource names must
be assigned deliberately, and duplicate assignments or overfull domains fail
before publication. It refuses handwritten-file collisions and symlink outputs.
Handwritten `resource.py`, package-root exports and unrelated files are preserved.

All modules are compiled before writing, and the complete output is staged beside
the destination on the same filesystem. Existing generated bytes are backed up
before replacements or stale generated-file removals. An exception or keyboard
interrupt during publication restores the previous file set and is reported as a
failure. If recovery itself fails, the error names the retained staging directory
containing recovery files. A hard process/OS termination can leave staged or
partial output: inspect the staging backup and regenerate before using the SDK.
This is recoverable offline generation, not an atomic multi-file hot reload;
run generation without concurrent imports, generators or editors on these files.

Registry order and the entire manifest remain unchanged by the split, including
source hashes, endpoint versions, parameter requirements, operation order and
media/body rules. Legacy imports from `zoho.erp.generated` and
`zoho.erp.openapi.generated` retain class identity, wildcard exports and old
pickle class-lookup paths. Canonical imports use the business-area modules, for
example `zoho.erp.openapi.sales.invoices.Invoices`.

The API-reference generator reads typed attributes from `registry.py`, resolves
each resource source through its explicit import, and compares operation names
and order against the manifest. The catalog includes canonical source links and
actual client attribute names. It never imports generated SDK modules to inspect
these definitions.

### Verification contracts

`tests/zoho/erp/resource_ast_baseline.json` records the pre-split class AST
fingerprints and manifest checksum. Update it only after reviewing an intentional
API, implementation, docstring or source-provenance change. Tests cover all 899
route bindings, all 81 legacy/canonical class identities and pickle paths,
deterministic complete file sets, resource removal/reassignment, invalid or
unmapped input, handwritten-file preservation, domain limits and interrupted
publication rollback. The full project suite also checks API synchronization,
import layers, package discovery and directory counts. Verification is local
macOS arm64; Windows, hosted CI and live ERP availability remain unverified for
this split. No live calls are required to regenerate or test these modules.

## Root generated-file removal and lazy alias

Status: completed. The physical file `src/zoho/erp/generated.py` has been
removed. In its place, `zoho.erp.generated` is registered as an explicit lazy
module alias of `zoho.erp.openapi.generated` via
`utils.general_utils.module_aliases.register_module_aliases` in `zoho/erp/__init__.py`
and `zoho/__init__.py`.

1. `zoho.erp.generated` points lazily to `zoho.erp.openapi.generated`.
2. The OpenAPI compatibility facade, typed registry, resource modules and
   `zoho.erp.resource` adapter remain intact.
3. Tests in `tests/zoho/erp/test_generation.py` verify that `src/zoho/erp/generated.py`
   is absent, both module imports refer to the identical canonical module,
   all 81 class identities/wildcard exports remain available, and legacy pickle
   lookup paths still work.
4. Package-root imports remain lazy. Completely removing the old import path would
   be a separate breaking API change.
