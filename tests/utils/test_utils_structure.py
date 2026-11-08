"""Tests for organized utilities structure and backward-compatible imports."""
from __future__ import annotations

import importlib
import pytest


def test_subpackages_structure() -> None:
    """Verify subpackages export their submodules and public APIs."""
    from utils import http_utils, file_utils, general_utils
    from utils import HttpUtils, FileUtils, GeneralUtils

    assert HttpUtils is http_utils
    assert FileUtils is file_utils
    assert GeneralUtils is general_utils

    # http_utils
    assert hasattr(http_utils, "http")
    assert hasattr(http_utils, "http_transport")
    assert hasattr(http_utils, "send_http_request")
    assert hasattr(http_utils, "Session")

    # file_utils
    assert hasattr(file_utils, "json")
    assert hasattr(file_utils, "yaml")
    assert hasattr(file_utils, "loads")
    assert hasattr(file_utils, "safe_load")
    assert hasattr(file_utils, "read_pdf_pages")

    # general_utils
    assert hasattr(general_utils, "encoding")
    assert hasattr(general_utils, "sequences")
    assert hasattr(general_utils, "detect_encoding")
    assert hasattr(general_utils, "parse_doc_number")


def test_pascal_case_imports() -> None:
    """Verify PascalCase aliases can be imported and accessed."""
    from utils.HttpUtils import http, http_transport
    from utils.FileUtils import json, yaml
    from utils.GeneralUtils import sequences, encoding

    assert http is not None
    assert http_transport is not None
    assert json is not None
    assert yaml is not None
    assert sequences is not None
    assert encoding is not None


def test_legacy_module_attribute_access() -> None:
    """Verify accessing legacy submodules on the utils package."""
    import utils

    assert hasattr(utils, "http")
    assert hasattr(utils, "http_transport")
    assert hasattr(utils, "json")
    assert hasattr(utils, "yaml")
    assert hasattr(utils, "pdf")
    assert hasattr(utils, "sequences")
    assert hasattr(utils, "encoding")


def test_legacy_direct_submodule_imports() -> None:
    """Verify legacy direct submodule imports via redirect finder."""
    http = importlib.import_module("utils.http")
    http_transport = importlib.import_module("utils.http_transport")
    json = importlib.import_module("utils.json")
    yaml = importlib.import_module("utils.yaml")
    sequences = importlib.import_module("utils.sequences")
    encoding = importlib.import_module("utils.encoding")
    pdf = importlib.import_module("utils.pdf")

    assert hasattr(http, "send_http_request")
    assert hasattr(http_transport, "Session")
    assert hasattr(json, "loads")
    assert hasattr(yaml, "safe_load")
    assert hasattr(sequences, "parse_doc_number")
    assert hasattr(encoding, "detect_encoding")
    assert hasattr(pdf, "read_pdf_pages")


def test_legacy_from_submodule_imports() -> None:
    """Verify from-imports from legacy submodule paths."""
    from utils.http import send_http_request, DEFAULT_TIMEOUT
    from utils.http_transport import Session, HTTPError
    from utils.json import loads, dumps
    from utils.yaml import safe_load, safe_dump
    from utils.sequences import parse_doc_number
    from utils.encoding import detect_encoding
    from utils.pdf import read_pdf_pages

    assert callable(send_http_request)
    assert DEFAULT_TIMEOUT == 30.0
    assert issubclass(HTTPError, Exception)
    assert loads('{"key": 1}') == {"key": 1}
    assert dumps({"key": 1}) == '{"key":1}'
    assert safe_load("key: 1") == {"key": 1}
    assert parse_doc_number("DOC-42") == ("DOC-", 42, 2)
    assert isinstance(detect_encoding(b"hello"), str)
    assert callable(read_pdf_pages)
