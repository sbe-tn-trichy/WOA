"""ERP module generation, compatibility, provenance and recovery contracts."""

from __future__ import annotations

import ast
import hashlib
import importlib
from importlib.resources import files
from pathlib import Path
import pickle
from unittest.mock import patch

import pytest

from apps.tools import generate_erp_sdk as generator
from zoho.erp.openapi import ERPResources, RESOURCE_TYPES
from utils.file_utils import json


PACKAGE = Path(str(files("zoho.erp.openapi")))
BASELINE = json.loads(Path(__file__).with_name("resource_ast_baseline.json").read_text())


def snapshot(folder: Path) -> dict[str, bytes]:
    return {str(p.relative_to(folder)): p.read_bytes()
            for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def definition(source: Path, name: str = "departments") -> None:
    source.mkdir(exist_ok=True)
    (source / f"{name}.yml").write_text("""openapi: 3.0.0
servers:
  - url: https://www.zohoapis.in/erp/v3
paths:
  /example/{id}:
    get:
      operationId: get_example
""", encoding="utf-8")


def test_resource_asts_and_manifest_match_reviewed_baseline():
    actual = {}
    for path in PACKAGE.glob("*/*.py"):
        for node in ast.parse(path.read_text()).body:
            if isinstance(node, ast.ClassDef):
                actual[node.name] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
    assert actual == BASELINE["classes"]
    assert hashlib.sha256((PACKAGE / "manifest.json").read_bytes()).hexdigest() == BASELINE["manifest_sha256"]


@pytest.mark.parametrize("name, resource", RESOURCE_TYPES.items())
def test_all_resource_imports_and_old_pickle_paths_keep_identity(name, resource):
    for legacy in ("zoho.erp.generated", "zoho.erp.openapi.generated"):
        namespace = {}
        exec(f"from {legacy} import *", namespace)
        assert namespace[resource.__name__] is resource
        old_pickle = f"c{legacy}\n{resource.__name__}\n.".encode()
        assert pickle.loads(old_pickle) is resource
    domain = next(group for group, members in generator.DOMAINS.items() if name in members.split())
    module = importlib.import_module(f"zoho.erp.openapi.{domain}.{name}")
    package = importlib.import_module(f"zoho.erp.openapi.{domain}")
    assert getattr(module, resource.__name__) is getattr(package, resource.__name__) is resource
    assert ERPResources.__annotations__[name] is resource


def test_generation_is_byte_deterministic_and_preserves_handwritten_files(tmp_path):
    source, target = tmp_path / "source", tmp_path / "output"
    definition(source)
    target.mkdir()
    (target / "resource.py").write_text("# handwritten operation support\n")
    generator.generate(source, target)
    first = snapshot(target)
    generator.generate(source, target)
    assert snapshot(target) == first
    assert (target / "resource.py").read_text() == "# handwritten operation support\n"


def test_removed_or_reassigned_resources_clean_only_generated_files(tmp_path, monkeypatch):
    source, target = tmp_path / "source", tmp_path / "output"
    definition(source)
    definition(source, "invoices")
    generator.generate(source, target)
    unrelated = target / "sales" / "notes.py"
    unrelated.write_text("# handwritten notes\n")
    (source / "invoices.yml").unlink()
    monkeypatch.setattr(generator, "DOMAINS", {"organization": "departments"})
    generator.generate(source, target)
    assert not (target / "sales/invoices.py").exists()
    assert not (target / "people/departments.py").exists()
    assert (target / "organization/departments.py").exists()
    assert unrelated.read_text() == "# handwritten notes\n"
    registry = (target / "registry.py").read_text()
    assert "invoices" not in registry
    assert "organization.departments" in registry


@pytest.mark.parametrize("problem", ["unmapped", "server", "syntax", "handwritten"])
def test_invalid_generation_preserves_existing_output(tmp_path, monkeypatch, problem):
    source, target = tmp_path / "source", tmp_path / "output"
    definition(source)
    generator.generate(source, target)
    if problem == "unmapped":
        definition(source, "unknown_resource")
    elif problem == "server":
        path = source / "departments.yml"
        path.write_text(path.read_text().replace("zohoapis.in", "example.com"))
    elif problem == "syntax":
        original = generator.render_modules

        def invalid(resources):
            modules = original(resources)
            modules[Path("registry.py")] = "invalid Python!"
            return modules

        monkeypatch.setattr(generator, "render_modules", invalid)
    else:
        (target / "people/departments.py").write_text("# handwritten collision\n")
    before = snapshot(target)
    with pytest.raises((ValueError, SyntaxError)):
        generator.generate(source, target)
    assert snapshot(target) == before


@pytest.mark.parametrize("failure", [OSError("disk failure"), KeyboardInterrupt()])
def test_interrupted_publication_rolls_back_complete_file_set(tmp_path, failure):
    source, target = tmp_path / "source", tmp_path / "output"
    definition(source)
    generator.generate(source, target)
    before = snapshot(target)
    definition(source, "invoices")
    replace = generator.os.replace
    calls = 0

    def fail_once(source, target):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise failure
        return replace(source, target)

    with patch.object(generator.os, "replace", side_effect=fail_once):
        with pytest.raises(type(failure)):
            generator.generate(source, target)
    assert snapshot(target) == before
    assert not list(tmp_path.glob(".erp-generation-*"))


def test_domain_limit_is_checked_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(generator, "DOMAINS", {"sales": " ".join(f"resource_{n}" for n in range(10))})
    modules = generator.render_modules({f"resource_{n}": (f"Resource{n}", f"class Resource{n}:\n    VALUE = 1\n") for n in range(10)})
    with pytest.raises(ValueError, match="ten generated files"):
        generator.write_modules(tmp_path / "output", modules, {})
    assert not (tmp_path / "output").exists()


def test_duplicate_domain_assignment_is_rejected_before_writing(tmp_path, monkeypatch):
    source = tmp_path / "source"
    definition(source)
    monkeypatch.setattr(generator, "DOMAINS", {"people": "departments", "organization": "departments"})
    with pytest.raises(ValueError, match="Duplicate ERP domain"):
        generator.generate(source, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_symlink_output_is_rejected_without_changing_either_location(tmp_path):
    source, target, outside = tmp_path / "source", tmp_path / "output", tmp_path / "outside"
    definition(source)
    target.mkdir()
    outside.mkdir()
    try:
        (target / "people").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege is unavailable")
        raise
    with pytest.raises(ValueError, match="symlink output"):
        generator.generate(source, target)
    assert not list(outside.iterdir())
    assert sorted(p.name for p in target.iterdir()) == ["people"]


def test_failed_rollback_retains_recovery_backup(tmp_path):
    source, target = tmp_path / "source", tmp_path / "output"
    definition(source)
    generator.generate(source, target)
    before = snapshot(target)
    definition(source, "invoices")
    replace = generator.os.replace
    calls = 0

    def fail_publication_and_recovery(source, target):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError("destination unavailable")
        return replace(source, target)

    with patch.object(generator.os, "replace", side_effect=fail_publication_and_recovery):
        with pytest.raises(RuntimeError, match="recovery failed; previous files remain"):
            generator.generate(source, target)
    stages = list(tmp_path.glob(".erp-generation-*"))
    assert len(stages) == 1
    assert (stages[0] / "previous/generated.py").read_bytes() == before["generated.py"]


def test_root_generated_file_is_absent_and_lazy_alias_preserves_compatibility():
    root_file = Path(__file__).resolve().parents[3] / "src" / "zoho" / "erp" / "generated.py"
    assert not root_file.exists(), "src/zoho/erp/generated.py must be absent; lazy alias replaces it"

    import zoho.erp.generated
    import zoho.erp.openapi.generated

    assert zoho.erp.generated is zoho.erp.openapi.generated
    assert zoho.erp.generated.__spec__.name == "zoho.erp.openapi.generated"

