"""Shared cross-service utility modules and organized utility subpackages."""

from __future__ import annotations

import importlib
import sys
import types
from typing import TYPE_CHECKING

from . import file_utils, general_utils, http_utils
from .file_utils import (
    JSONDecodeError,
    YAMLError,
    dump,
    dumps,
    json,
    load,
    loads,
    safe_dump,
    safe_load,
    yaml,
)
from .general_utils import (
    detect_encoding,
    encoding,
    parse_doc_number,
    sequences,
)
from .http_utils import (
    DEFAULT_RETRY_AFTER,
    DEFAULT_TIMEOUT,
    MAX_RETRY_AFTER,
    HTTPError,
    RequestOptions,
    Response,
    SeekableStream,
    Session,
    TransportError,
    capture_upload_positions,
    decode_response,
    extract_retry_after,
    filter_request_kwargs,
    get_json_value,
    http,
    http_transport,
    is_html_body,
    is_json_content_type,
    parse_retry_after,
    request_json,
    rewind_uploads,
    sanitize_error_text,
    send_http_request,
    unwrap_json_body,
    validate_https_override_url,
    write_response_to_file,
)

if TYPE_CHECKING:
    from .file_utils import pdf
    from .file_utils.pdf import read_pdf_pages

# PascalCase aliases
HttpUtils = http_utils
FileUtils = file_utils
GeneralUtils = general_utils

__all__ = [
    # Subpackages
    "http_utils",
    "file_utils",
    "general_utils",
    "HttpUtils",
    "FileUtils",
    "GeneralUtils",
    # Submodules
    "http",
    "http_transport",
    "json",
    "yaml",
    "pdf",
    "sequences",
    "encoding",
    # Functions and classes
    "parse_doc_number",
    "JSONDecodeError",
    "dump",
    "dumps",
    "load",
    "loads",
    "HTTPError",
    "RequestOptions",
    "Response",
    "Session",
    "TransportError",
    "YAMLError",
    "detect_encoding",
    "safe_dump",
    "safe_load",
    "read_pdf_pages",
    "DEFAULT_RETRY_AFTER",
    "DEFAULT_TIMEOUT",
    "MAX_RETRY_AFTER",
    "SeekableStream",
    "capture_upload_positions",
    "decode_response",
    "extract_retry_after",
    "filter_request_kwargs",
    "get_json_value",
    "is_html_body",
    "is_json_content_type",
    "parse_retry_after",
    "request_json",
    "rewind_uploads",
    "sanitize_error_text",
    "send_http_request",
    "unwrap_json_body",
    "validate_https_override_url",
    "write_response_to_file",
]

_REDIRECT_MAP: dict[str, str] = {
    # Direct legacy module aliases
    "utils.http": "utils.http_utils.http",
    "utils.http_transport": "utils.http_utils.http_transport",
    "utils.json": "utils.file_utils.json",
    "utils.yaml": "utils.file_utils.yaml",
    "utils.pdf": "utils.file_utils.pdf",
    "utils.sequences": "utils.general_utils.sequences",
    "utils.encoding": "utils.general_utils.encoding",
    # PascalCase package aliases
    "utils.HttpUtils": "utils.http_utils",
    "utils.FileUtils": "utils.file_utils",
    "utils.GeneralUtils": "utils.general_utils",
    # PascalCase module subpaths
    "utils.HttpUtils.http": "utils.http_utils.http",
    "utils.HttpUtils.http_transport": "utils.http_utils.http_transport",
    "utils.FileUtils.json": "utils.file_utils.json",
    "utils.FileUtils.yaml": "utils.file_utils.yaml",
    "utils.FileUtils.pdf": "utils.file_utils.pdf",
    "utils.GeneralUtils.sequences": "utils.general_utils.sequences",
    "utils.GeneralUtils.encoding": "utils.general_utils.encoding",
}


from .general_utils.module_aliases import register_module_aliases

register_module_aliases(_REDIRECT_MAP)

for _alias, _target_module in [
    ("utils.http", http),
    ("utils.http_transport", http_transport),
    ("utils.json", json),
    ("utils.yaml", yaml),
    ("utils.encoding", encoding),
    ("utils.sequences", sequences),
    ("utils.HttpUtils", http_utils),
    ("utils.FileUtils", file_utils),
    ("utils.GeneralUtils", general_utils),
]:
    sys.modules.setdefault(_alias, _target_module)


def __getattr__(name: str) -> object:
    if name in ("pdf", "read_pdf_pages"):
        pdf_module = importlib.import_module(".file_utils.pdf", __package__)
        globals()["pdf"] = pdf_module
        if name == "read_pdf_pages":
            return pdf_module.read_pdf_pages
        return pdf_module
    fullname = f"utils.{name}"
    if fullname in _REDIRECT_MAP:
        target = _REDIRECT_MAP[fullname]
        mod: types.ModuleType = importlib.import_module(target)
        sys.modules[fullname] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
