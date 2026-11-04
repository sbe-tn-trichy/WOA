"""Offline fixtures for project inspection and incremental review scope."""
import ast
import json
from pathlib import Path
import subprocess

import pytest

from apps import analyze_project as audit


@pytest.fixture
def repo(tmp_path):
    def run(*args):
        result = subprocess.run(["git", "-C", str(tmp_path), *args], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    run("init")
    run("config", "user.email", "fixture@example.invalid")
    run("config", "user.name", "Fixture")
    for document in audit.DOCUMENTS:
        path = tmp_path / document
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Fixture\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.mypy]\nfiles = ["src/workflows/core", "apps/one.py"]\n', encoding="utf-8")
    for path, content in {
        "src/workflows/core/one.py": "VALUE = 1\n",
        "src/workflows/use.py": "from .core import one\n",
        "apps/one.py": "from workflows import use\n",
    }.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    run("add", ".")
    run("commit", "-m", "Fixture baseline")
    return tmp_path, run


def test_relative_imports():
    assert (1, "workflows.core.one") in audit.imports(ast.parse("from .core import one"), "workflows.use", False)
    assert (1, "workflows.core.one") in audit.imports(ast.parse("from . import one"), "workflows.core", True)
    assert audit.module_name("src/workflows/core/__init__.py") == "workflows.core"


def test_changes_and_dependents(repo):
    root, run = repo
    baseline = audit.git(root, "rev-parse", "HEAD")
    run("mv", "apps/one.py", "apps/renamed file.py")
    run("commit", "-m", "Rename")
    (root / "src/workflows/core/one.py").write_text("VALUE = 2\n", encoding="utf-8")
    run("add", "src/workflows/core/one.py")
    (root / "src/workflows/use.py").unlink()
    (root / "apps/new file.py").write_text("import workflows.core.one\n", encoding="utf-8")
    report = audit.inspect(root, baseline)
    assert report["changes"]["committed"][0]["old_path"] == "apps/one.py"
    assert report["changes"]["unstaged"][0]["status"] == "D"
    assert report["changes"]["untracked"][0]["path"] == "apps/new file.py"
    assert "apps/new file.py" in report["review_candidates"]["direct_dependents"]
    assert "src/workflows/core/one.py" in report["review_candidates"]["broader_review_triggers"]


def test_typing_diagnostics_and_stability(repo):
    root, _ = repo
    (root / "src/workflows/core/one.py").write_text("import apps.bad\n", encoding="utf-8")
    (root / "README.md").write_text("[missing](absent.md)\n[remote](https://example.invalid)\n", encoding="utf-8")
    report = audit.inspect(root)
    assert report == audit.inspect(root)
    assert report["typing"]["explicitly_covered"] == ["apps/one.py", "src/workflows/core/one.py"]
    assert {d["rule"] for d in report["diagnostics"]} == {"import-layer", "local-link"}
    assert all(d["line"] == 1 for d in report["diagnostics"])


def test_malformed_source_and_invalid_revision(repo):
    root, _ = repo
    (root / "apps/one.py").write_text("def broken(\n", encoding="utf-8")
    assert audit.inspect(root)["errors"][0]["file"] == "apps/one.py"
    with pytest.raises(ValueError):
        audit.inspect(root, "--invalid-revision")


def test_sdk_boundary_and_valid_links(repo):
    root, _ = repo
    sdk = root / "src/zoho/sample.py"
    sdk.parent.mkdir(parents=True)
    sdk.write_text("from workflows import core\nimport scripts.scratch\n", encoding="utf-8")
    (root / "README.md").write_text("[local](<apps/one.py>)\n[anchor](#section)\n", encoding="utf-8")
    report = audit.inspect(root)
    assert not report["errors"]
    assert {d["rule"] for d in report["diagnostics"]} == {"import-layer"}
    assert {d["line"] for d in report["diagnostics"]} == {1, 2}


def test_missing_navigation_document_is_incomplete(repo):
    root, _ = repo
    (root / "INDEX.md").unlink()
    assert audit.inspect(root)["errors"] == [{"file": "INDEX.md", "message": "Required navigation document is missing"}]


def test_verification_failures(monkeypatch, tmp_path):
    results = iter([
        subprocess.CompletedProcess([], 1, "out of sync", ""),
        subprocess.CompletedProcess([], 1, "", "No module named mypy"),
    ])
    monkeypatch.setattr(audit.subprocess, "run", lambda *a, **k: next(results))
    assert [r["status"] for r in audit.verify(tmp_path)] == ["failed", "incomplete"]
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("fixture", 180)
    monkeypatch.setattr(audit.subprocess, "run", timeout)
    assert all(r["status"] == "incomplete" for r in audit.verify(tmp_path))


@pytest.mark.parametrize("diagnostics,errors,verification,expected", [
    ([], [], [], 0),
    ([{"file": "x", "message": "bad"}], [], [], 1),
    ([], [{"file": "x", "message": "bad"}], [], 2),
    ([], [], [{"status": "failed", "command": ["check"], "output": "failed", "duration_seconds": 0}], 1),
    ([], [], [{"status": "incomplete", "command": ["check"], "output": "missing", "duration_seconds": 0}], 2),
])
def test_cli_reports_and_exit_codes(repo, monkeypatch, diagnostics, errors, verification, expected):
    root, _ = repo
    report = audit.inspect(root)
    report.update(diagnostics=diagnostics, errors=errors)
    monkeypatch.setattr(audit, "ROOT", root)
    monkeypatch.setattr(audit, "inspect", lambda *a: report)
    monkeypatch.setattr(audit, "verify", lambda *a: verification)
    monkeypatch.setattr("sys.argv", ["analyze_project", "--verify"])
    assert audit.main() == expected
    saved = json.loads((root / "output/project-analysis/report.json").read_text(encoding="utf-8"))
    assert saved["verification"] == verification
    assert "# Project analysis snapshot" in (root / "output/project-analysis/report.md").read_text(encoding="utf-8")


def test_cli_invalid_baseline_does_not_write(repo, monkeypatch):
    root, _ = repo
    monkeypatch.setattr(audit, "ROOT", root)
    monkeypatch.setattr("sys.argv", ["analyze_project", "--since", "not-a-commit"])
    assert audit.main() == 2
    assert not (root / "output").exists()
