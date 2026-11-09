"""Fetch resource details with explicit response-shape and identity checks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol


class _RecordResource(Protocol):
    def get(self, identifier: str) -> Mapping[str, object]: ...


class SearchResource(Protocol):
    def list_all(
        self, params: dict[str, object] | None = None, resource_key: str | None = None,
    ) -> object: ...


class AmbiguousMatchError(ValueError):
    """More than one distinct record satisfied a unique lookup."""


def distinct_records(
    rows: Iterable[dict[str, object]], id_key: str,
) -> list[dict[str, object]]:
    matches: dict[str, dict[str, object]] = {}
    for row in rows:
        value = row.get(id_key)
        if type(value) not in (str, int) or not str(value).strip():
            raise ValueError(f"Matching record has an invalid {id_key}")
        matches.setdefault(str(value).strip(), row)
    return list(matches.values())


def unique_record(
    rows: Iterable[dict[str, object]], id_key: str,
) -> dict[str, object] | None:
    matches = distinct_records(rows, id_key)
    if len(matches) > 1:
        raise AmbiguousMatchError(f"Expected one match by {id_key}, found {len(matches)}")
    return matches[0] if matches else None


def get_verified_record(
    resource: _RecordResource, identifier: str, key: str, id_key: str,
) -> dict[str, object]:
    """Fetch a dictionary detail and verify its ID against the requested ID.

    ``key`` selects the response envelope and ``id_key`` selects the record ID.
    Numeric response IDs are compared as strings. Invalid response shapes,
    missing IDs and mismatched IDs raise ValueError; resource errors propagate.
    """
    response = resource.get(identifier)
    record = response.get(key) if isinstance(response, Mapping) else None
    if (not isinstance(record, dict) or record.get(id_key) is None
            or str(record[id_key]) != identifier):
        raise ValueError(f"Resource returned an invalid {key} detail for {identifier}")
    return record
