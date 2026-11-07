---
type: Reference
title: JSON codec
---

# JSON codec

Project-owned JSON parsing and serialization use `utils.json`, backed by pinned
`python-rapidjson==1.26`. The module exports `dump`, `dumps`, `load`, `loads` and
`JSONDecodeError`. Applications, workflows, HTTP payloads and SQLite JSON fields
share this owner. It replaces the unused orjson dependency declaration.

## Financial and recovery contracts

- Without an explicit `default` serializer, Decimal values are emitted directly
  as JSON numbers with their decimal digits intact. No conversion through float
  or automatic rounding is performed.
- Existing explicit serializers retain priority for Decimal values. In
  particular, `write_atomic_json` still defaults to `str`, preserving Decimal
  and date strings in saved recovery data. Checkpoint staging, atomic replacement
  and schema validation are unchanged.
- Decoders continue returning `int` and `float`, matching existing workflow
  contracts. Decimal encoding does not imply Decimal decoding or exact storage by
  the receiving API. Financial calculations continue using their domain parsers.
- HTTP requests retain `allow_nan=False`, rejecting non-finite float/Decimal
  values before transport. Other callers preserve the standard library's existing
  `allow_nan=True` default unless explicitly overridden.

## Compatibility boundaries

Output is text, with compact separators when indentation is omitted. Pretty
printing, key sorting, Unicode escaping, stream output and custom defaults are
supported. Stream output uses RapidJSON's native writer; streams remain owned by
their callers. JSON whitespace and escape spelling may differ from the previous
codec, while decoded values remain equivalent.

Non-string basic dictionary keys are converted to their JSON spellings without
passing the whole dictionary to `default=str`. Unsupported keys and unsupported
bytes/iterables fail rather than silently changing structure. Decoding preserves
legacy UTF-8 BOM and UTF-16/UTF-32 byte input using encoding detection before
native parsing. Arbitrarily large integers remain integers; native-number mode
is not enabled. RapidJSON can reject malformed Unicode or out-of-range numeric
literals earlier than the standard parser.

Analytics snapshot packing and hashes deliberately retain their legacy canonical
standard-library encoder. Float and escape spelling participate in existing
on-disk hashes; changing those bytes would invalidate stored fingerprints. Their
decoding uses the new codec. This migration does not refresh live metadata or
rewrite existing catalogs/checkpoints.

Reference: [python-rapidjson number handling](https://python-rapidjson.readthedocs.io/en/latest/api.html).
