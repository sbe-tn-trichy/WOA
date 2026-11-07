from datetime import date
from io import StringIO

import pytest

from utils import yaml


def test_legacy_scalars_and_quoted_identifiers():
    assert yaml.safe_load(StringIO(
        'enabled: on\ncount: 012\ndate: 2026-11-07\nidentifier: "00123"\n'
    )) == {"enabled": True, "count": 10, "date": date(2026, 11, 7), "identifier": "00123"}


@pytest.mark.parametrize("text", [
    "key: !!python/object:builtins.object {}",
    "key: !custom value",
    "key: [!custom value]",
    "!custom key: value",
    "first: 1\n---\nsecond: 2",
    "key: [unterminated",
])
def test_unsupported_documents_fail(text):
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(text)


def test_dump_roundtrip_preserves_strings_and_unicode():
    value = {"name": "தமிழ்", "identifier": "00123", "flag": "on"}
    dumped = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    assert isinstance(dumped, str)
    assert yaml.safe_load(dumped) == value


def test_empty_yaml_and_merge_keys():
    assert yaml.safe_load("") is None
    assert yaml.safe_load("base: &base {enabled: yes}\ncopy: {<<: *base, count: 2}") == {
        "base": {"enabled": True}, "copy": {"enabled": True, "count": 2},
    }
