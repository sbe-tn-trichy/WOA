"""Composite Zoho Analytics query-batching and export fallback helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol


class _AnalyticsQueriesResource(Protocol):
    def execute(self, workspace_id: str, sql: str) -> object: ...


class _AnalyticsViewsResource(Protocol):
    def export_all(
        self,
        workspace_id: str,
        view_id: str,
        *,
        max_attempts: int = 60,
    ) -> object: ...


class AnalyticsQueryOrExportClient(Protocol):
    @property
    def queries(self) -> _AnalyticsQueriesResource: ...
    @property
    def views(self) -> _AnalyticsViewsResource: ...


def build_batched_like_queries(
    table_name: str,
    select_columns: Sequence[str],
    like_column: str,
    tokens: Sequence[str],
    *,
    where_prefix: str = "",
    max_tokens_per_query: int = 35,
    max_sql_bytes: int = 6000,
) -> list[str]:
    """Build SQL-budgeted ``LIKE`` queries batched across ``tokens``."""
    if max_tokens_per_query < 1 or max_sql_bytes < 256:
        raise ValueError("Analytics batch limits must be positive and SQL budget at least 256 bytes.")
    if not select_columns:
        raise ValueError("At least one select column is required.")
    cols = ", ".join(f'"{col}"' for col in select_columns)
    base_where = f"{where_prefix} AND (" if where_prefix else "("
    prefix = f'SELECT {cols} FROM "{table_name}" WHERE {base_where}'
    queries: list[str] = []
    clauses: list[str] = []
    for token in tokens:
        safe = token.replace("'", "''")
        clause = f'"{like_column}" LIKE \'%{safe}%\''
        candidate = prefix + " OR ".join([*clauses, clause]) + ")"
        if clauses and (
            len(clauses) >= max_tokens_per_query
            or len(candidate.encode("utf-8")) > max_sql_bytes
        ):
            queries.append(prefix + " OR ".join(clauses) + ")")
            clauses = []
        if len((prefix + clause + ")").encode("utf-8")) > max_sql_bytes:
            raise ValueError("A query token exceeds the Analytics SQL budget.")
        clauses.append(clause)
    if clauses:
        queries.append(prefix + " OR ".join(clauses) + ")")
    return queries


def query_or_export_analytics_rows(
    analytics_client: object,
    workspace_id: str,
    *,
    queries: Sequence[str] = (),
    fallback_view_id: str = "",
    max_export_attempts: int = 60,
) -> tuple[list[dict[str, object]], bool]:
    """Execute SQL queries when supported, falling back to full view export.

    Returns ``(rows, used_full_export)``.
    """
    queries_api = getattr(analytics_client, "queries", None)
    execute = getattr(queries_api, "execute", None)
    views_api = getattr(analytics_client, "views", None)
    export_all = getattr(views_api, "export_all", None)

    if callable(execute) and queries:
        try:
            all_rows: list[dict[str, object]] = []
            for sql in queries:
                rows = execute(workspace_id, sql)
                if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
                    raise ValueError("Analytics returned an invalid query result.")
                all_rows.extend(dict(row) for row in rows)
            return all_rows, False
        except Exception:
            if not callable(export_all) or not fallback_view_id:
                raise

    if callable(export_all) and fallback_view_id:
        rows = export_all(
            workspace_id,
            fallback_view_id,
            max_attempts=max_export_attempts,
        )
        if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
            raise ValueError("Analytics returned an invalid export result.")
        return [dict(row) for row in rows], True

    raise ValueError("Analytics has no supported historical lookup API.")


__all__ = [
    "AnalyticsQueryOrExportClient",
    "build_batched_like_queries",
    "query_or_export_analytics_rows",
]
