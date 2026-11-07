import io
import json as standard_json
from datetime import date
from decimal import Decimal
from hashlib import sha256
from unittest.mock import patch

import pyqwest
import pytest

from utils import json
from utils.http_transport import Session
from workflows.core.checkpoint import write_atomic_json
from zoho.analytics.snapshot import _json_hash, _pack_json, _unpack_json


def test_decimal_is_emitted_as_exact_json_number_at_http_boundary():
    amount = Decimal("123456789012345678.90")
    with patch("utils.http_transport.pyqwest.SyncHTTPTransport") as factory:
        factory.return_value.execute_sync.return_value = pyqwest.SyncResponse(
            status=200, content=b'{"amount":1.25}')
        session = Session()
        try:
            response = session.request("POST", "https://example.invalid", json={"amount": amount})
        finally:
            session.close()
        payload = factory.return_value.execute_sync.call_args.args[0].content
    assert payload == b'{"amount":123456789012345678.90}'
    assert standard_json.loads(payload, parse_float=Decimal) == {"amount": amount}
    assert response.json() == {"amount": 1.25}
    assert isinstance(response.json()["amount"], float)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), Decimal("NaN"), Decimal("Infinity")])
def test_nonfinite_http_values_fail_before_network(value):
    with patch("utils.http_transport.pyqwest.SyncHTTPTransport") as factory:
        session = Session()
        try:
            with pytest.raises(ValueError):
                session.request("POST", "https://example.invalid", json={"amount": value})
        finally:
            session.close()
        factory.assert_not_called()


def test_existing_recovery_decimal_and_date_strings_are_preserved(tmp_path):
    path = tmp_path / "checkpoint.json"
    write_atomic_json(path, {"amount": Decimal("12.30"), "date": date(2026, 11, 7)})
    expected = {"amount": "12.30", "date": "2026-11-07"}
    assert standard_json.loads(path.read_text()) == expected
    path.write_text(standard_json.dumps(expected), encoding="utf-8")
    with path.open() as stream:
        assert json.load(stream) == expected


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16", "utf-32"])
def test_existing_byte_encodings_and_large_integers(encoding):
    value = {"unicode": "தமிழ்", "integer": 10 ** 100, "fraction": 1.25}
    assert json.loads(standard_json.dumps(value).encode(encoding)) == value
    assert standard_json.loads(json.dumps(value, ensure_ascii=False)) == value


def test_native_stream_writer_and_non_string_keys_preserve_structure():
    value = {1: {None: Decimal("12.30"), False: "value"}}
    stream = io.StringIO()
    json.dump(value, stream, default=str, indent=2)
    assert standard_json.loads(stream.getvalue()) == {"1": {"null": "12.30", "false": "value"}}
    assert stream.getvalue() == json.dumps(value, default=str, indent=2)
    assert not stream.closed
    with pytest.raises(TypeError):
        json.dumps({(1, 2): "invalid"}, default=str)


def test_invalid_json_and_unsupported_types_fail():
    with pytest.raises(json.JSONDecodeError):
        json.loads('{"amount":')
    with pytest.raises(TypeError):
        json.dumps({"bytes": b"invalid"})


def test_analytics_hashes_keep_legacy_float_and_unicode_encoding():
    value = {"tiny": 1e-7, "unicode": "தமிழ்", "large": 10 ** 100}
    original = standard_json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    assert _json_hash(value) == sha256(original.encode()).hexdigest()
    assert _unpack_json(_pack_json(value)) == value
