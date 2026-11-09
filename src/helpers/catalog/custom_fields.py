"""Utilities for safely inspecting, extracting, and provisioning Zoho custom field values."""

from __future__ import annotations

import builtins
import re
from collections.abc import Mapping, Sequence
from typing import Protocol


class BooksCustomFieldsResource(Protocol):
    def list_for_entity(self, entity: str) -> builtins.list[dict[str, object]]: ...
    def create(self, requirement: Mapping[str, object]) -> dict[str, object]: ...


class BooksCustomFieldsClient(Protocol):
    custom_fields: BooksCustomFieldsResource


def _normalized_field_name(value: object) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def get_custom_field_value(
    record: Mapping[str, object],
    field_name: str,
    default: object | None = None,
) -> object:
    """Extract a custom field value from a Zoho record across various response shapes.

    Supports:
    1. Direct top-level key matching `field_name`.
    2. Items in `custom_fields` list matching `api_name`, `label`, or `customfield_id`.
    3. Keys in `custom_field_hash` dictionary.
    """
    if not record or not field_name:
        return default

    # 1. Direct top-level key
    if field_name in record:
        val = record.get(field_name)
        return val if val is not None else default

    # 2. Key inside custom_field_hash
    cf_hash = record.get("custom_field_hash")
    if isinstance(cf_hash, dict) and field_name in cf_hash:
        val = cf_hash.get(field_name)
        return val if val is not None else default

    # 3. List of custom field objects: [{'api_name': ..., 'label': ..., 'value': ...}]
    custom_fields = record.get("custom_fields")
    if isinstance(custom_fields, list):
        target = field_name.strip().lower()
        for cf in custom_fields:
            if not isinstance(cf, dict):
                continue
            api_name = str(cf.get("api_name") or "").strip().lower()
            label = str(cf.get("label") or "").strip().lower()
            cf_id = str(cf.get("customfield_id") or "").strip().lower()

            if target in (api_name, label, cf_id):
                val = cf.get("value")
                return val if val is not None else default

    return default


def extract_custom_fields_dict(record: Mapping[str, object]) -> dict[str, object]:
    """Extract all custom fields in a record into a flat dictionary keyed by api_name or label."""
    if not record:
        return {}

    result: dict[str, object] = {}

    cf_hash = record.get("custom_field_hash")
    if isinstance(cf_hash, dict):
        result.update(cf_hash)

    custom_fields = record.get("custom_fields")
    if isinstance(custom_fields, list):
        for cf in custom_fields:
            if not isinstance(cf, dict):
                continue
            key = cf.get("api_name") or cf.get("label") or cf.get("customfield_id")
            if key:
                result[str(key)] = cf.get("value")

    return result


def ensure_books_custom_fields(
    books_client: BooksCustomFieldsClient,
    entity: str,
    requirements: Sequence[Mapping[str, object]],
    create_missing: bool = False,
) -> dict[str, object]:
    """Verify and optionally provision custom fields on a Zoho Books entity."""
    existing = books_client.custom_fields.list_for_entity(entity)
    existing_by_name: dict[str, dict[str, object]] = {}
    ambiguous_names: set[str] = set()
    for field in existing:
        if not isinstance(field, dict):
            continue
        label = str(field.get("label") or "")
        api_name = str(field.get("api_name") or "")
        if api_name.startswith("cf_"):
            api_name = api_name[3:]
        names = {_normalized_field_name(name) for name in (label, api_name)}
        for normalized in names - {""}:
            previous = existing_by_name.setdefault(normalized, field)
            field_id = str(field.get("customfield_id") or "").strip()
            if previous is not field and (
                not field_id or str(previous.get("customfield_id") or "").strip() != field_id
            ):
                ambiguous_names.add(normalized)

    missing: list[dict[str, object]] = []
    misconfigured: list[dict[str, object]] = []
    has_ambiguous_requirement = False
    for requirement in requirements:
        normalized = _normalized_field_name(requirement.get("label"))
        if normalized in ambiguous_names:
            has_ambiguous_requirement = True
            misconfigured.append({
                "field": requirement.get("label", ""),
                "problems": ["multiple Books custom fields share the normalized name"],
            })
            continue
        field = existing_by_name.get(normalized)
        if field is None:
            missing.append(dict(requirement))
            continue
        problems: list[str] = []
        if requirement.get("data_type") and str(field.get("data_type") or "") != requirement["data_type"]:
            problems.append(f"data_type must be {requirement['data_type']!r}")
        if requirement.get("is_unique") and field.get("is_unique") is not True:
            problems.append("field must be unique")
        values_raw = requirement.get("values")
        required_values = (
            {str(row["name"]) for row in values_raw if isinstance(row, dict) and row.get("name")}
            if isinstance(values_raw, list)
            else set()
        )
        actual_raw = field.get("values")
        actual_values = (
            {str(row.get("name") or row.get("value") or "") for row in actual_raw if isinstance(row, dict)}
            if isinstance(actual_raw, list)
            else set()
        )
        absent_values = sorted(required_values - actual_values)
        if absent_values:
            problems.append("missing dropdown values: " + ", ".join(absent_values))
        if problems:
            misconfigured.append({"field": requirement.get("label", ""), "problems": problems})

    created: list[dict[str, object]] = []
    if create_missing and not has_ambiguous_requirement:
        for requirement in missing:
            created.append(books_client.custom_fields.create(requirement))
        missing = []

    return {
        "valid": not missing and not misconfigured,
        "missing": missing,
        "misconfigured": misconfigured,
        "created": created,
    }
