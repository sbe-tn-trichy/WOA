"""Cleanup never treats ignored business data as disposable."""
import os
from pathlib import Path
import subprocess

import pytest

from apps.cleanup_project import Candidate, allowed, apply_cleanup, plan_cleanup


@pytest.fixture
def repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return tmp_path


def put(root, name, age=20):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("data")
    os.utime(path, (1000000 - age * 86400, 1000000 - age * 86400))
    return path


def test_plan_and_apply_preserve_business_data(repo):
    disposable = ["output/tmp/old.txt", "output/mypy-cache/cache.db", "build/lib/example.py", "src/zoho/__pycache__/x.pyc"]
    protected = ["scripts/recover.py", "output/stock_transfer/execution.json", "output/archive/report.json",
                 "workspace_metadata/catalog.sqlite", "logs/app.log", "src/zoho/client.py",
                 "src/zoho/__pycache__/evidence.json"]
    for name in disposable + protected:
        put(repo, name)
    put(repo, "output/tmp/recent.txt", age=1)
    tracked = put(repo, "build/tracked.txt")
    subprocess.run(["git", "-C", str(repo), "add", "build/tracked.txt"], check=True)
    plan = plan_cleanup(repo, 7, now=1000000)
    assert {str(c.path) for c in plan} == set(disposable)
    assert all((repo / c.path).exists() for c in plan)
    assert apply_cleanup(repo, plan) == len(disposable)
    assert all((repo / name).exists() for name in protected)
    assert tracked.exists()


def test_symlink_directory_and_file_are_skipped(repo, tmp_path_factory):
    outside = tmp_path_factory.mktemp("outside")
    target = put(outside, "valuable", age=20)
    (repo / "output").mkdir()
    (repo / "output/tmp").symlink_to(outside, target_is_directory=True)
    assert plan_cleanup(repo, 0, now=1000000) == []
    (repo / "build").mkdir()
    (repo / "build/link").symlink_to(target)
    assert plan_cleanup(repo, 0, now=1000000) == []
    assert target.exists()


def test_changed_file_refused(repo):
    path = put(repo, "output/tmp/change.txt")
    plan = plan_cleanup(repo, 0, now=1000000)
    path.write_text("new contents")
    with pytest.raises(ValueError, match="changed since preview"):
        apply_cleanup(repo, plan)
    assert path.exists()


def test_newly_tracked_file_refused(repo):
    path = put(repo, "build/new.txt")
    plan = plan_cleanup(repo, 0, now=1000000)
    subprocess.run(["git", "-C", str(repo), "add", "build/new.txt"], check=True)
    with pytest.raises(ValueError, match="protected path"):
        apply_cleanup(repo, plan)
    assert path.exists()


@pytest.mark.parametrize("days", [-1, float("nan"), float("inf")])
def test_invalid_retention(repo, days):
    with pytest.raises(ValueError, match="finite nonnegative"):
        plan_cleanup(repo, days)


def test_git_failure_is_not_empty_tracking(tmp_path):
    with pytest.raises(subprocess.CalledProcessError):
        plan_cleanup(tmp_path, 7)


@pytest.mark.parametrize("name", ["build/../config/config.json", "/build/x", "../build/x"])
def test_unsafe_paths_not_allowed(name):
    assert not allowed(Path(name))
