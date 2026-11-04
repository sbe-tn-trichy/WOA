"""Tests for API reference documentation generator."""
from __future__ import annotations

from pathlib import Path
import pytest

from apps.generate_api_reference import (
    ROOT,
    generate_all_docs,
    parse_module,
    format_func_signature,
    main,
)
import ast


def test_parse_module_auth() -> None:
    auth_file = ROOT / "src/zoho/auth.py"
    mod_doc = parse_module(auth_file)

    assert mod_doc.module_path == "zoho.auth"
    class_names = [c.name for c in mod_doc.classes]
    assert "HttpTokenProvider" in class_names
    assert "ZohoOAuth2Manager" in class_names
    assert "CatalystAuth" in class_names

    token_provider = next(c for c in mod_doc.classes if c.name == "HttpTokenProvider")
    assert token_provider.docstring is not None
    assert "Retrieve service tokens" in token_provider.docstring

    method_names = [m.name for m in token_provider.methods]
    assert "__init__" in method_names
    assert "get_tokens" in method_names
    assert "get_token" in method_names


def test_parse_module_purchases_attributes_and_mixins() -> None:
    purchases_file = ROOT / "src/zoho/books/resources/purchases.py"
    mod_doc = parse_module(purchases_file)

    bills_cls = next(c for c in mod_doc.classes if c.name == "Bills")
    assert "BaseResource" in bills_cls.bases
    assert "StatusMixin" in bills_cls.bases
    assert "ApprovalMixin" in bills_cls.bases
    assert "CreditsMixin" in bills_cls.bases

    attr_names = [a.name for a in bills_cls.attributes]
    assert "required_fields" in attr_names
    assert "defaults" in attr_names
    assert "line_item_required_fields" in attr_names

    # Check comments captured for attributes
    req_fields = next(a for a in bills_cls.attributes if a.name == "required_fields")
    assert any("Top-level requirements" in c for c in req_fields.comments)

    methods = {m.name: m for m in bills_cls.methods}
    assert "normalize_bill_number" in methods
    assert "@staticmethod" in methods["normalize_bill_number"].decorators
    assert "find_duplicate_groups" in methods
    assert "@classmethod" in methods["find_duplicate_groups"].decorators
    assert methods["find_duplicate_groups"].docstring is not None
    assert "repeated non-blank bill numbers" in methods["find_duplicate_groups"].docstring


def test_parse_module_security_functions() -> None:
    security_file = ROOT / "src/zoho/security.py"
    mod_doc = parse_module(security_file)

    fn_names = [f.name for f in mod_doc.functions]
    assert "mask_sensitive_value" in fn_names
    assert "sanitize_log_params" in fn_names
    assert "sanitize_filename" in fn_names
    assert "resolve_output_path" in fn_names

    mask_fn = next(f for f in mod_doc.functions if f.name == "mask_sensitive_value")
    assert mask_fn.docstring is not None
    assert "last 4 characters" in mask_fn.docstring
    assert "val: Any" in mask_fn.signature
    assert "-> str" in mask_fn.signature


def test_signature_formatting_edge_cases() -> None:
    code = """
def sample_func(pos_only: int, /, pos_or_kw: str = 'hello', *args: float, kw_only: bool = True, **kwargs: object) -> bool:
    return True
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    assert isinstance(func_node, ast.FunctionDef)
    sig = format_func_signature(func_node)
    assert sig == "def sample_func(pos_only: int, /, pos_or_kw: str = 'hello', *args: float, kw_only: bool = True, **kwargs: object) -> bool"


def test_docs_in_sync_check_mode() -> None:
    docs_root = ROOT / "docs"
    output_dir = ROOT / "docs" / "api"
    in_sync, changed = generate_all_docs(docs_root, output_dir, check_only=True)
    assert in_sync, f"Documentation is out of sync. Changed files: {changed}"
    assert len(changed) == 0


def test_generate_all_docs_in_temp_dir(tmp_path: Path) -> None:
    docs_root = tmp_path / "docs"
    output_dir = docs_root / "api"

    in_sync, changed = generate_all_docs(docs_root, output_dir, check_only=False)
    assert not in_sync
    assert len(changed) == 16

    # Verify key files were generated
    assert (output_dir / "README.md").exists()
    assert (output_dir / "core.md").exists()
    assert (output_dir / "books.md").exists()
    assert (output_dir / "inventory.md").exists()
    assert (output_dir / "analytics.md").exists()
    assert (output_dir / "erp.md").exists()
    assert (output_dir / "creator.md").exists()
    assert (output_dir / "mail.md").exists()
    assert (output_dir / "wd.md").exists()
    assert (output_dir / "sheet.md").exists()
    assert (output_dir / "cliq.md").exists()
    assert (output_dir / "helpers.md").exists()
    assert (output_dir / "google_sheets.md").exists()
    assert (docs_root / "conf.py").exists()
    assert (docs_root / "index.rst").exists()
    assert (docs_root / "index.md").exists()

    # Verify idempotency
    in_sync2, changed2 = generate_all_docs(docs_root, output_dir, check_only=True)
    assert in_sync2
    assert len(changed2) == 0


def test_cli_check_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["generate_api_reference.py", "--check"])
    assert main() == 0
