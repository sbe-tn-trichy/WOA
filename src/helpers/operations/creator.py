"""Composite operations and read-back verification helpers for Zoho Creator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from zoho.core_sdk.validation import require_text


class CreatorRecordClient(Protocol):
    def get_records(
        self,
        app_link_name: str,
        report_link_name: str,
        *,
        params: dict[str, object] | None = None,
    ) -> object: ...

    def update_records(
        self,
        app_link_name: str,
        report_link_name: str,
        payload: dict[str, object],
        *,
        record_id: str | None = None,
    ) -> object: ...


def require_creator_success(response: object) -> None:
    """Validate a Creator write response envelope and raise ValueError on error codes."""
    if not isinstance(response, Mapping):
        raise ValueError("Creator returned an invalid update response.")
    payloads: list[Mapping[str, object]] = [response]
    data = response.get("data")
    if isinstance(data, Mapping):
        payloads.append(data)
    elif isinstance(data, list):
        payloads.extend(row for row in data if isinstance(row, Mapping))
    for payload in payloads:
        code = payload.get("code")
        if code is not None and str(code).strip() not in {"0", "3000"}:
            message = str(payload.get("message") or payload.get("description") or "").strip()
            raise ValueError(
                f"Creator rejected the checkpoint update (code={code})"
                + (f": {message}" if message else ".")
            )


def update_and_verify_creator_record(
    creator_client: CreatorRecordClient,
    app_link_name: str,
    report_link_name: str,
    record_id: str,
    fields: Mapping[str, object],
    *,
    field_config: str = "all",
) -> dict[str, object]:
    """Update one Creator record and verify all written fields via read-back."""
    target_id = require_text(record_id, "Creator record ID")
    if not fields:
        raise ValueError("At least one Creator field is required for update.")

    response = creator_client.update_records(
        app_link_name,
        report_link_name,
        {"data": dict(fields)},
        record_id=target_id,
    )
    require_creator_success(response)

    readback = creator_client.get_records(
        app_link_name,
        report_link_name,
        params={
            "criteria": f"ID == {target_id}",
            "field_config": field_config,
        },
    )
    rows = readback.get("data", []) if isinstance(readback, Mapping) else []
    record = next(
        (
            dict(row)
            for row in rows
            if isinstance(row, Mapping) and str(row.get("ID") or "").strip() == target_id
        ),
        None,
    )
    if record is None:
        raise ValueError(
            f"Creator read-back verification failed: record {target_id} was not found."
        )
    for field_name, expected in fields.items():
        actual = str(record.get(field_name) or "").strip()
        expected_text = "" if expected is None else str(expected).strip()
        if actual != expected_text:
            raise ValueError(
                f"Creator read-back verification failed for field '{field_name}'."
            )
    return record


__all__ = [
    "CreatorRecordClient",
    "require_creator_success",
    "update_and_verify_creator_record",
]
