"""Download the Books Accounts and Items replicas into one local SQLite snapshot."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zoho.analytics import ZohoAnalyticsAPI

    from workflows.analytics_catalog import AnalyticsCatalog

ANALYTICS_TABLES = ("Accounts (Zoho Books)", "Items (Zoho Books)")


@dataclass(frozen=True)
class AnalyticsItemSnapshot:
    database: Path
    row_counts: dict[str, int]
    last_successful_metadata_sync_at: str


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def sync_analytics_items(
    analytics: ZohoAnalyticsAPI, catalog: AnalyticsCatalog, destination: Path,
) -> AnalyticsItemSnapshot:
    """Replace Accounts and Items together after verifying both Analytics exports."""
    sources = []
    with catalog.cached_store() as store:
        synced_at = store.get_info("last_successful_sync_at") or "unknown"
        for view_name in ANALYTICS_TABLES:
            matches = [view for view in store.find_views(view_name) if view["name"] == view_name]
            if len(matches) != 1:
                raise ValueError(f"Expected one cached Analytics table named {view_name!r}")
            view_id = str(matches[0]["view_id"])
            columns = [str(column["name"]) for column in store.get_columns(view_id)]
            table = view_name.removesuffix(" (Zoho Books)")
            primary = "Account ID" if table == "Accounts" else "Item ID"
            if primary not in columns:
                raise ValueError(f"Cached Analytics schema for {view_name!r} lacks {primary!r}")
            sources.append((table, view_name, view_id, columns, primary))

    exports = {}
    snapshot = {
        "workspace_id": catalog.workspace_id,
        "last_successful_metadata_sync_at": synced_at,
    }
    for table, view_name, view_id, columns, primary in sources:
        rows = analytics.views.export_all(catalog.workspace_id, view_id, max_attempts=60)
        count = analytics.queries.execute(
            catalog.workspace_id,
            f"SELECT COUNT(*) AS source_count FROM {_quote(view_name)}",
            max_attempts=60,
        )
        if len(count) != 1 or str(count[0].get("source_count")) != str(len(rows)):
            raise ValueError(f"Analytics row count differs from the {view_name!r} export; retry the download")
        expected = set(columns)
        for row in rows:
            actual = set(row.keys())
            if actual != expected:
                missing = sorted(expected - actual)
                extra = sorted(actual - expected)
                parts = []
                if missing:
                    parts.append(f"missing={missing}")
                if extra:
                    parts.append(f"extra={extra}")
                raise ValueError(
                    f"Invalid row in {view_name!r}: schema mismatch ({', '.join(parts)}; "
                    f"cached metadata last synced {synced_at}); refresh Analytics metadata and retry"
                )
            record_id = row.get(primary)
            if not isinstance(record_id, str) or not record_id.strip():
                raise ValueError(f"Invalid row in {view_name!r}; check {primary!r}")
        exports[table] = rows
        # Keep the original Items snapshot keys for existing readers.
        prefix = "accounts_" if table == "Accounts" else ""
        snapshot.update({
            f"{prefix}source_view": view_name,
            f"{prefix}source_view_id": view_id,
            f"{prefix}row_count": str(len(rows)),
        })

    snapshot["downloaded_at"] = datetime.now(timezone.utc).isoformat()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(destination, timeout=30)) as db, db:
        db.execute("BEGIN IMMEDIATE")
        existing = {name for (name,) in db.execute("SELECT name FROM sqlite_schema WHERE type = 'table'")}
        if existing and "Snapshot" not in existing:
            raise ValueError(f"Destination is not an Analytics item snapshot: {destination}")
        db.execute("CREATE TABLE IF NOT EXISTS Snapshot (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        workspace = db.execute("SELECT value FROM Snapshot WHERE key = 'workspace_id'").fetchone()
        if existing and (workspace is None or workspace[0] != catalog.workspace_id):
            raise ValueError(f"Destination belongs to another Analytics workspace: {destination}")
        for table, _, _, columns, primary in sources:
            definitions = ", ".join(
                f"{_quote(column)} TEXT" + (" NOT NULL PRIMARY KEY" if column == primary else "")
                for column in columns
            )
            db.execute(f"DROP TABLE IF EXISTS {_quote(table)}")
            db.execute(f"CREATE TABLE {_quote(table)} ({definitions})")
            placeholders = ", ".join("?" for _ in columns)
            try:
                db.executemany(
                    f"INSERT INTO {_quote(table)} VALUES ({placeholders})",
                    (tuple(row[column] for column in columns) for row in exports[table]),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Cannot store {table}: duplicate or invalid {primary}") from exc
        db.executemany(
            "INSERT INTO Snapshot VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            snapshot.items(),
        )

    return AnalyticsItemSnapshot(destination, {table: len(rows) for table, rows in exports.items()}, synced_at)
