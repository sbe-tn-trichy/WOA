---
type: reference
---

# Item catalog export

`workflows.item_catalog` owns vendor-independent Inventory catalog exports.
The public package exports `export_inventory_items`, `ItemExportRow`,
`export_row`, `write_export_rows` and the stable CSV `FIELDS`.
Use `apps/inventory/export_items.py` as the primary command:

```sh
.venv/bin/python apps/inventory/export_items.py --purchase-account-id PURCHASE_ACCOUNT_ID
.venv/bin/python apps/inventory/export_items.py --purchase-account-id PURCHASE_ACCOUNT_ID --status all
```

The purchase account is required; manufacturer names never determine scope.
The workflow uses Zoho Inventory, requests the selected status (`active` by
default; `inactive` and `all` also supported), and rejects returned items with
missing or different purchase-account IDs before writing either CSV.
It never creates or updates remote items. App clients come from the existing
authentication factory and use the effective local organization configuration.

Default destinations are `output/items.csv` and `output/items_missing_alias.csv`.
Both can be overridden with `--output` and `--missing-output`, including explicit
absolute paths. The paths must differ; existing destination files are replaced.
The CSV columns are item ID, name, SKU, alias, alias-present flag, manufacturer
and purchase-account ID. Whitespace-only aliases are missing. The second CSV
contains only items missing aliases. The two writes are sequential, not atomic
as a pair; a filesystem failure may leave only one updated file.

## Neoseal compatibility

`apps/neoseal_items/export_neoseal_items.py` and `apps/neoseal.py export` remain
supported, preserving the historical `output/neoseal_items.csv` and
`output/neoseal_items_missing_alias.csv` defaults. They share the generic parser
and export logic. `workflows.neoseal_audit.exporter` and the Neoseal package
exports remain compatibility APIs with historical default destinations.
New callers should use `workflows.item_catalog` and the generic app.

Neoseal-specific auditing and name/SKU updates remain owned by
[Neoseal item audit](neoseal-item-audit.md).

## Accounts and Items SQLite snapshot

Run the Analytics snapshot from the repository root:

```sh
.venv/bin/python apps/inventory/sync_analytics_items.py
```

The command downloads the `Accounts (Zoho Books)` and `Items (Zoho Books)`
views using the configured Analytics workspace. It resolves their IDs and
columns from `data/analytics/metadata.sqlite` and prints the last successful
metadata sync time. Use `--catalog-dir`, `--workspace-id`, or `--db` to override
the defaults.

The default destination is `data/analytics/items.sqlite`. It holds `Accounts`
and `Items` with source column names, text values, and their source IDs as
primary keys. `Snapshot` records the workspace, view IDs, download time, and
row counts. Each refresh verifies both exports against source row counts and
replaces both local tables in a single transaction. Use
`workflows.item_catalog.sync_analytics_items()` to call the workflow from Python.
