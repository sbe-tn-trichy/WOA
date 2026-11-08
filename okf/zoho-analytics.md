---
type: reference
description: Zoho Analytics v2 generated operations, custom resources, and regeneration.
---

# Zoho Analytics SDK

The Analytics SDK follows the Books split between generated OpenAPI resources
and hand-written helpers. `client.openapi` exposes raw v2 operations by domain.
`client.views`, `client.queries`, and `client.metadata` provide higher-level
behavior from `zoho.analytics.custom`, including row decoding, export polling,
and [resumable SQLite snapshots](analytics-metadata.md). The previous module
paths `zoho.analytics.resources`, `zoho.analytics.metadata`, and
`zoho.analytics.snapshot` resolve to their canonical modules.

```python
workspaces = client.openapi.org_management.get_org_workspaces()
views = client.openapi.views_management.get_views(workspace_id)
rows = client.queries.execute(workspace_id, "SELECT * FROM Sales")
```

The generated [operation manifest](../src/zoho/analytics/openapi/manifest.json)
records the 203 methods in ten domains, their source hashes, upstream operation
IDs, HTTP routes, categories, and OAuth scopes. The [API reference](../docs/api/analytics.md)
links to each resource. Generated methods expose a single API call. Convenience
methods handle multi-step exports, response normalization, and snapshot state.

Generated methods accept named path identifiers and URL-encode them. For
operations that accept `config`, the SDK serializes the dictionary into the
Zoho `CONFIG` query parameter or form field as specified upstream. File imports
accept an `upload` value in the shared HTTP transport's file format. Synchronous
imports also accept `inline_data` as an alternative. Cross-organization copy
operations expose the destination header separately while the client supplies
the source organization header. Setting `regenerateKey` to `True` on
`get_workspace_secret_key` uses the mutation token policy despite the GET route.
Callers close streaming responses. Zoho validates operation-specific config
fields and account permissions.

## Regeneration

The generated sources are pinned to [Zoho's Analytics OAS revision
`211c5bc`](https://github.com/zoho/analytics-oas/tree/211c5bc1ca938b3920d9dd7eb6c3d189c4ea18fb/v2.0).
Use a local checkout of that revision for offline regeneration.

```bash
.venv/bin/python apps/sdk_tools/generate_analytics_sdk.py /absolute/path/to/analytics-oas/v2.0
.venv/bin/python apps/generate_api_reference.py
```

Generation reads the ten domain JSON files. Runtime imports use the generated
Python modules and do not need the upstream checkout.
