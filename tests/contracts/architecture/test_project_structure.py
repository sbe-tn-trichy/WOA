"""Import identity and entry-point contracts for responsibility-based packages."""

from __future__ import annotations

import importlib
from pathlib import Path
import shutil
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


@pytest.mark.parametrize(
    "entry",
    sorted(
        path.relative_to(ROOT).as_posix()
        for path in (ROOT / "apps").rglob("*.py")
        if path.name not in {"__init__.py", "_bootstrap.py"}
        and "_bootstrap" in path.read_text(encoding="utf-8")
    ),
)
def test_app_direct_import_startup(entry: str) -> None:
    # Use the direct-script import branch without invoking the workflow's main.
    # Reject network/process activity so this check cannot run live operations.
    probe = "\n".join([
        "import pathlib, runpy, sys",
        "def offline(event, args):",
        "    if event in {'socket.connect', 'socket.bind', 'subprocess.Popen', 'os.system'}:",
        "        raise RuntimeError('Unexpected startup activity: ' + event)",
        "sys.addaudithook(offline)",
        "path = pathlib.Path(sys.argv[1]).resolve()",
        "sys.path.insert(0, str(path.parent))",
        "runpy.run_path(str(path), run_name='__startup_probe__')",
    ])
    result = subprocess.run(
        [sys.executable, "-c", probe, entry],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr


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


def test_source_directory_limits():
    from apps.tools.analyze_project import git, structure_diagnostics

    paths = git(ROOT, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    assert not structure_diagnostics(ROOT, set(paths.split("\0")) - {""})


@pytest.mark.parametrize("subdirectory", ["apps", "apps/group", "apps/group/domain"])
def test_direct_bootstrap_resolves_checkout(tmp_path, subdirectory: str) -> None:
    checkout = tmp_path / "checkout"
    entry_dir = checkout / subdirectory
    entry_dir.mkdir(parents=True)
    (checkout / "pyproject.toml").touch()
    src = checkout / "src"
    src.mkdir()
    (src / "checkout_marker.py").touch()
    shutil.copyfile(ROOT / "apps/_bootstrap.py", entry_dir / "_bootstrap.py")
    entry = entry_dir / "entry.py"
    entry.write_text(
        "import _bootstrap\n"
        "import checkout_marker\n"
        "print(_bootstrap._ROOT)\n",
        encoding="utf-8",
    )
    # A direct script needs its own directory on sys.path. Skip site packages
    # so the editable installation cannot supply any checkout imports.
    args = [sys.executable, "-E", "-S", str(entry)]
    result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == checkout.resolve()

    (checkout / "pyproject.toml").unlink()
    result = subprocess.run(args, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Could not find pyproject.toml above" in result.stderr


def test_nested_app_preserves_legacy_import_and_finds_template(tmp_path) -> None:
    checkout = tmp_path / "checkout"
    apps = checkout / "apps"
    nested = apps / "group/domain"
    nested.mkdir(parents=True)
    (checkout / "pyproject.toml").touch()
    (apps / "static").mkdir()
    (apps / "static/payment_review.html").write_text("nested template", encoding="utf-8")
    shutil.copyfile(ROOT / "apps/_bootstrap.py", apps / "_bootstrap.py")
    shutil.copyfile(ROOT / "apps/bank_collections/_bootstrap.py", nested / "_bootstrap.py")
    source = (ROOT / "apps/__init__.py").read_text(encoding="utf-8")
    (apps / "__init__.py").write_text(
        source.replace('"apps.bank_collections.payment_review"', '"apps.group.domain.payment_review"'),
        encoding="utf-8",
    )
    shutil.copyfile(ROOT / "apps/bank_collections/payment_review.py", nested / "payment_review.py")
    script = (
        "import sys\n"
        "sys.path[:0] = sys.argv[1:]\n"
        "import apps.payment_review as legacy\n"
        "from apps.group.domain import payment_review\n"
        "assert legacy is payment_review\n"
        "assert payment_review.__spec__.name == 'apps.group.domain.payment_review'\n"
        "assert payment_review.HTML == 'nested template'\n"
    )
    result = subprocess.run(
        [sys.executable, "-I", "-c", script, str(checkout), str(ROOT / "src")],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
