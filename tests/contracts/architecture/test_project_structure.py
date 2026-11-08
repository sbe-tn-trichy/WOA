"""Import identity and entry-point contracts for responsibility-based packages."""

from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

import pytest

import helpers
import utils
import workflows
import zoho


ALIASES = {
    **utils._REDIRECT_MAP,
    **zoho._MODULE_ALIASES,
    **helpers._MODULE_ALIASES,
    **workflows._MODULE_ALIASES,
}
ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("legacy, canonical", sorted(ALIASES.items()))
def test_moved_modules_preserve_identity(legacy: str, canonical: str) -> None:
    old_module = importlib.import_module(legacy)
    new_module = importlib.import_module(canonical)
    assert old_module is new_module
    assert old_module.__spec__.name == canonical


def test_legacy_monkeypatch_updates_canonical_module(monkeypatch) -> None:
    import zoho.auth
    from zoho.core_sdk import auth

    sentinel = object()
    monkeypatch.setattr(zoho.auth, "request_json", sentinel)
    assert auth.request_json is sentinel


def test_package_roots_keep_optional_dependencies_lazy() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "\n".join(
                [
                    "import sys",
                    "import utils, zoho, helpers, workflows",
                    "assert 'pypdfium2' not in sys.modules",
                    "assert 'python_calamine' not in sys.modules",
                    "assert 'workflows.creator_payments.ocr' not in sys.modules",
                ]
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "name",
    [
        "analyze_project",
        "cleanup_project",
        "generate_api_reference",
        "generate_erp_sdk",
    ],
)
def test_developer_tool_entry_points_keep_working(name: str) -> None:
    legacy = importlib.import_module(f"apps.{name}")
    canonical = importlib.import_module(f"apps.tools.{name}")
    assert legacy is canonical
    result = subprocess.run(
        [sys.executable, str(ROOT / "apps" / f"{name}.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()


def test_python_package_directories_stay_within_file_limit() -> None:
    violations = []
    for root in (ROOT / "src", ROOT / "apps", ROOT / "tests"):
        for directory in [root, *(p for p in root.rglob("*") if p.is_dir())]:
            if "__pycache__" in directory.parts or not any(directory.glob("*.py")):
                continue
            # Count source-controlled source/data files, excluding runtime output.
            files = [
                p
                for p in directory.iterdir()
                if p.is_file()
                and p.suffix
                in {
                    ".py",
                    ".json",
                    ".html",
                    ".js",
                    ".css",
                    ".yaml",
                    ".yml",
                }
            ]
            if len(files) > 10:
                violations.append((str(directory.relative_to(ROOT)), len(files)))
    assert not violations, violations
