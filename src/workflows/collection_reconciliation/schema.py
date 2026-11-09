from dataclasses import dataclass
from collections.abc import Mapping, Sequence
from typing import Any

from helpers import ensure_books_custom_fields
from workflows.runtime.exceptions import SchemaValidationError


@dataclass(frozen=True)
class CreatorFieldRequirement:
    api_name: str
    allowed_types: tuple[int, ...]
    required_choices: tuple[str, ...] = ()
    expected_default: str = ""
    must_be_lookup: bool = False


COLLECTION_FIELD_REQUIREMENTS: tuple[CreatorFieldRequirement, ...] = (
    CreatorFieldRequirement("Record_ID", (9,)),
    CreatorFieldRequirement("Payment_ID", (1, 9)),
    CreatorFieldRequirement("Payment_Date", (10,)),
    CreatorFieldRequirement("Amount", (6, 8)),
    CreatorFieldRequirement("Payment_Mode", (12,), ("Cash", "Online", "Cheque")),
    CreatorFieldRequirement("Reference_Number", (1,)),
    CreatorFieldRequirement("Customer_Name", (12,), must_be_lookup=True),
    CreatorFieldRequirement(
        "Reconciliation_Status",
        (12,),
        ("Pending", "Confirmed", "Unmatched_Manual"),
        "Pending",
    ),
    CreatorFieldRequirement("Zoho_Books_Payment_ID", (1,)),
)

AUDIT_FIELD_REQUIREMENTS: tuple[CreatorFieldRequirement, ...] = (
    CreatorFieldRequirement("Creator_Record_ID", (1, 5, 9)),
    CreatorFieldRequirement("Stage", (1, 12)),
    CreatorFieldRequirement("Message", (1, 2)),
    CreatorFieldRequirement("Payload", (1, 2)),
    CreatorFieldRequirement("Occurred_At", (11,)),
)

BOOKS_CUSTOM_FIELD_REQUIREMENTS: tuple[dict[str, Any], ...] = (
    {
        "label": "Creator Record ID",
        "data_type": "string",
        "entity": "customer_payment",
        "show_on_pdf": False,
        "is_mandatory": False,
        "is_unique": True,
    },
    {
        "label": "Creator Payment ID",
        "data_type": "number",
        "entity": "customer_payment",
        "show_on_pdf": False,
        "is_mandatory": False,
        "is_unique": True,
    },
)


def _normalized_field_name(value: Any) -> str:
    return "".join(character for character in str(value or "").casefold() if character.isalnum())


def _field_rows(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    for key in ("fields", "data", "result"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        if isinstance(rows, dict):
            nested = rows.get("fields") or rows.get("data")
            if isinstance(nested, list):
                return [row for row in nested if isinstance(row, dict)]
    return []


def _creator_field_name(field: Mapping[str, Any]) -> str:
    return str(
        field.get("link_name")
        or field.get("api_name")
        or field.get("field_name")
        or field.get("name")
        or ""
    )


def _creator_field_type(field: Mapping[str, Any]) -> Any:
    value = field.get("type")
    if isinstance(value, dict):
        value = value.get("id") or value.get("value")
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return value


def _creator_choices(field: Mapping[str, Any]) -> list[str]:
    rows = field.get("choices") or field.get("values") or field.get("allowed_values") or []
    choices: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                value = row.get("value") or row.get("key") or row.get("name")
            else:
                value = row
            if value not in (None, ""):
                choices.append(str(value))
    return choices


def validate_creator_form_fields(
    payload: Any,
    requirements: Sequence[CreatorFieldRequirement],
) -> dict[str, Any]:
    fields = {_creator_field_name(row): row for row in _field_rows(payload)}
    missing: list[str] = []
    wrong_types: list[dict[str, Any]] = []
    wrong_choices: list[dict[str, Any]] = []
    wrong_defaults: list[dict[str, Any]] = []
    wrong_lookup_fields: list[str] = []
    unverified_defaults: list[str] = []
    for requirement in requirements:
        field = fields.get(requirement.api_name)
        if field is None:
            missing.append(requirement.api_name)
            continue
        actual_type = _creator_field_type(field)
        if actual_type not in requirement.allowed_types:
            wrong_types.append(
                {
                    "field": requirement.api_name,
                    "actual_type": actual_type,
                    "allowed_types": list(requirement.allowed_types),
                }
            )
        if requirement.required_choices:
            actual_choices = _creator_choices(field)
            absent = [
                choice for choice in requirement.required_choices
                if choice not in actual_choices
            ]
            if absent:
                wrong_choices.append(
                    {
                        "field": requirement.api_name,
                        "missing_choices": absent,
                        "actual_choices": actual_choices,
                    }
                )
        if requirement.expected_default:
            default_keys = ("default_value", "initial_value", "default")
            present_key = next((key for key in default_keys if key in field), None)
            if present_key is None:
                unverified_defaults.append(requirement.api_name)
            elif str(field.get(present_key) or "") != requirement.expected_default:
                wrong_defaults.append(
                    {
                        "field": requirement.api_name,
                        "expected": requirement.expected_default,
                        "actual": field.get(present_key),
                    }
                )
        if requirement.must_be_lookup and field.get("is_lookup_field") is not True:
            wrong_lookup_fields.append(requirement.api_name)
    return {
        "valid": (
            not missing
            and not wrong_types
            and not wrong_choices
            and not wrong_defaults
            and not wrong_lookup_fields
        ),
        "missing": missing,
        "wrong_types": wrong_types,
        "wrong_choices": wrong_choices,
        "wrong_defaults": wrong_defaults,
        "wrong_lookup_fields": wrong_lookup_fields,
        "unverified_defaults": unverified_defaults,
    }


def ensure_books_customer_payment_fields(
    books_client: Any,
    create_missing: bool = False,
) -> dict[str, Any]:
    return ensure_books_custom_fields(
        books_client,
        entity="customer_payment",
        requirements=BOOKS_CUSTOM_FIELD_REQUIREMENTS,
        create_missing=create_missing,
    )


def require_valid_schema(report: Mapping[str, Any]) -> None:
    invalid = [name for name, result in report.items() if not result.get("valid", False)]
    if invalid:
        raise SchemaValidationError(
            "Reconciliation schema validation failed for: " + ", ".join(invalid)
        )
