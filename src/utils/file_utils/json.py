"""Project JSON codec backed by python-rapidjson."""
from __future__ import annotations

from collections.abc import Callable
from json import detect_encoding
from typing import IO, cast

import rapidjson

JSONDecodeError = rapidjson.JSONDecodeError
_JSONValue = str | int | float | bool | None | list["_JSONValue"] | dict[str, "_JSONValue"]


def _encoder_default(
    default: Callable[[object], object] | None, allow_nan: bool,
) -> Callable[[object], object]:
    def encode(value: object) -> object:
        if isinstance(value, dict):
            # RapidJSON otherwise passes a whole non-string-keyed dictionary to
            # default=str, silently turning structured recovery data into text.
            converted = {}
            for key, item in value.items():
                if isinstance(key, str):
                    name = key
                elif key is None:
                    name = "null"
                elif isinstance(key, bool):
                    name = "true" if key else "false"
                elif isinstance(key, (int, float)):
                    name = rapidjson.dumps(key, allow_nan=allow_nan)
                else:
                    raise TypeError("JSON object keys must be strings, numbers, booleans or None")
                converted[name] = item
            return converted
        if default is not None:
            return default(value)
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
    return encode


def dumps(
    value: object, *, indent: int | None = None, ensure_ascii: bool = True,
    sort_keys: bool = False, default: Callable[[object], object] | None = None,
    allow_nan: bool = True,
) -> str:
    """Encode compact JSON; preserve explicit serializers and exact Decimal numbers."""
    # Keep existing default=str recovery formats. Without an explicit default,
    # Decimal values can be emitted directly as numbers, without a float conversion.
    number_mode = rapidjson.NM_DECIMAL if default is None else rapidjson.NM_NONE
    return rapidjson.dumps(
        value, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys,
        number_mode=number_mode, allow_nan=allow_nan,
        bytes_mode=rapidjson.BM_NONE, iterable_mode=rapidjson.IM_ONLY_LISTS,
        mapping_mode=rapidjson.MM_ONLY_DICTS,
        # Native stubs require a JSON-returning callback; its runtime validates
        # callback results, just as it validates the original value.
        default=cast("Callable[[object], _JSONValue]", _encoder_default(default, allow_nan)),
    )


def loads(value: str | bytes | bytearray) -> object:
    """Decode with existing int/float types and legacy byte-encoding support."""
    if isinstance(value, (bytes, bytearray)):
        encoding = detect_encoding(value)
        if encoding != "utf-8":
            value = value.decode(encoding)
    return rapidjson.loads(value)


def dump(
    value: object, stream: IO[str], *, indent: int | None = None,
    ensure_ascii: bool = True, sort_keys: bool = False,
    default: Callable[[object], object] | None = None, allow_nan: bool = True,
) -> None:
    """Write JSON text to an existing stream; file ownership stays with the caller."""
    rapidjson.dump(
        value, stream, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys,
        number_mode=rapidjson.NM_DECIMAL if default is None else rapidjson.NM_NONE,
        allow_nan=allow_nan, bytes_mode=rapidjson.BM_NONE,
        iterable_mode=rapidjson.IM_ONLY_LISTS, mapping_mode=rapidjson.MM_ONLY_DICTS,
        default=cast("Callable[[object], _JSONValue]", _encoder_default(default, allow_nan)),
    )


def load(stream: IO[str] | IO[bytes]) -> object:
    """Read one JSON document from a text or binary stream."""
    return loads(stream.read())


__all__ = ["JSONDecodeError", "dump", "dumps", "load", "loads"]
