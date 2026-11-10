import sqlite3
from contextlib import closing
from unittest.mock import Mock

import pytest

from workflows.analytics_catalog import AnalyticsCatalog
from workflows.item_catalog import sync_analytics_items
from zoho.analytics import WorkspaceMetadataStore


@pytest.fixture
def snapshot_inputs(tmp_path):
    with WorkspaceMetadataStore(tmp_path / "metadata.sqlite", "workspace") as store:
        store.set_info("last_successful_sync_at", "2026-11-09T07:19:15Z")
        store.replace_views("workspace", [
            {"viewId": "accounts", "viewName": "Accounts (Zoho Books)", "viewType": "Table"},
            {"viewId": "items", "viewName": "Items (Zoho Books)", "viewType": "Table"},
        ])
        for view_id, entity in (("accounts", "Account"), ("items", "Item")):
            store.put_table_metadata(view_id, {"columns": [
                {"columnId": f"{view_id}-id", "columnName": f"{entity} ID"},
                {"columnId": f"{view_id}-name", "columnName": f'{entity} "Name"'},
            ]})
    analytics = Mock()
    catalog = AnalyticsCatalog(None, "workspace", tmp_path)
    destination = tmp_path / "items.sqlite"
    return analytics, catalog, destination


def test_downloads_both_tables_and_refreshes_existing_snapshot(snapshot_inputs):
    analytics, catalog, destination = snapshot_inputs
    analytics.views.export_all.side_effect = [
        [{"Account ID": "001", 'Account "Name"': "Sales"}],
        [{"Item ID": "002", 'Item "Name"': "Pipe"}],
        [{"Account ID": "001", 'Account "Name"': "New sales"}],
        [],
    ]
    analytics.queries.execute.side_effect = [
        [{"source_count": "1"}], [{"source_count": "1"}],
        [{"source_count": "1"}], [{"source_count": "0"}],
    ]
    result = sync_analytics_items(analytics, catalog, destination)
    assert result.row_counts == {"Accounts": 1, "Items": 1}
    assert result.last_successful_metadata_sync_at == "2026-11-09T07:19:15Z"
    with closing(sqlite3.connect(destination)) as db:
        assert db.execute("SELECT * FROM Items").fetchall() == [("002", "Pipe")]
        assert db.execute("SELECT * FROM Accounts").fetchall() == [("001", "Sales")]

    sync_analytics_items(analytics, catalog, destination)
    with closing(sqlite3.connect(destination)) as db:
        assert db.execute("SELECT * FROM Accounts").fetchall() == [("001", "New sales")]
        assert db.execute("SELECT * FROM Items").fetchall() == []
        assert db.execute("SELECT value FROM Snapshot WHERE key='row_count'").fetchone() == ("0",)


@pytest.mark.parametrize(
    ("rows", "count", "error"),
    [
        ([{"Item ID": "2", 'Item "Name"': "Pipe"}], "2", "row count differs"),
        ([{"Item ID": "2"}], "1", "Invalid row"),
        ([{"Item ID": "2", 'Item "Name"': "Pipe"}] * 2, "2", "duplicate or invalid Item ID"),
    ],
)
def test_failed_refresh_preserves_both_tables(snapshot_inputs, rows, count, error):
    analytics, catalog, destination = snapshot_inputs
    analytics.views.export_all.side_effect = [
        [{"Account ID": "1", 'Account "Name"': "Old sales"}],
        [{"Item ID": "2", 'Item "Name"': "Old pipe"}],
        [{"Account ID": "1", 'Account "Name"': "New sales"}],
        rows,
    ]
    analytics.queries.execute.side_effect = [
        [{"source_count": "1"}], [{"source_count": "1"}],
        [{"source_count": "1"}], [{"source_count": count}],
    ]
    sync_analytics_items(analytics, catalog, destination)

    with pytest.raises(ValueError, match=error):
        sync_analytics_items(analytics, catalog, destination)

    with closing(sqlite3.connect(destination)) as db:
        assert db.execute("SELECT * FROM Accounts").fetchall() == [("1", "Old sales")]
        assert db.execute("SELECT * FROM Items").fetchall() == [("2", "Old pipe")]



def test_schema_mismatch_reports_missing_extra_and_sync_time(snapshot_inputs):
    analytics, catalog, destination = snapshot_inputs
    analytics.views.export_all.side_effect = [
        [{"Account ID": "1", 'Account "Name"': "Sales"}],
        [{"Item ID": "2", "Unexpected": "x"}],
    ]
    analytics.queries.execute.side_effect = [
        [{"source_count": "1"}],
        [{"source_count": "1"}],
    ]
    with pytest.raises(ValueError) as exc_info:
        sync_analytics_items(analytics, catalog, destination)
    msg = str(exc_info.value)
    assert "missing=['Item \"Name\"']" in msg
    assert "extra=['Unexpected']" in msg
    assert "2026-11-09T07:19:15Z" in msg
