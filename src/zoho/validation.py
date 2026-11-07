"""Small shape checks for untrusted service and file records."""

from collections.abc import Mapping

try:
    from pydantic_core import SchemaValidator, ValidationError, core_schema
    _RECORD_VALIDATOR: SchemaValidator | None = SchemaValidator(
        core_schema.dict_schema(core_schema.str_schema(), core_schema.any_schema())
    )
except ImportError:
    _RECORD_VALIDATOR = None


def require_record(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be an object")
    if _RECORD_VALIDATOR is not None and isinstance(value, dict):
        try:
            return _RECORD_VALIDATOR.validate_python(value)
        except ValidationError:
            raise ValueError(f"{context} must have string keys") from None
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{context} must have string keys")
        result[key] = item
    return result


def require_records(value: object, context: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list")
    return [require_record(item, f"{context}[{index}]") for index, item in enumerate(value)]


def require_text(value: object, context: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{context} must be {'a string' if allow_empty else 'a nonempty string'}")
    return value
