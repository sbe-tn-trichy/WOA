"""Preview or remove old disposable project files; never clean arbitrary output."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
DISPOSABLE = (
    Path("output/pytest-cache"), Path("output/mypy-cache"), Path("output/tmp"),
    Path(".pytest_cache"), Path("build"),
)
SOURCE_ROOTS = (Path("apps"), Path("src"), Path("tests"))


@dataclass(frozen=True)
class Candidate:
    path: Path
    size: int
    mtime_ns: int
    device: int
    inode: int


def tracked_files(root: Path) -> set[Path]:
    result = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-C", str(root), "ls-files", "-z"],
        capture_output=True, timeout=30, check=True,
    )
    return {Path(os.fsdecode(p)) for p in result.stdout.split(b"\0") if p}


def allowed(path: Path) -> bool:
    if path.is_absolute() or not path.parts or ".." in path.parts:
        return False
    return any(path.is_relative_to(p) for p in DISPOSABLE) or (
        path.parts[0] in {str(p) for p in SOURCE_ROOTS}
        and "__pycache__" in path.parts[:-1]
        and path.suffix in {".pyc", ".pyo"}
    )


def has_symlink(root: Path, relative: Path) -> bool:
    return any((root / parent).is_symlink() for parent in (relative, *relative.parents))


def plan_cleanup(root: Path, older_than_days: float, now: float | None = None) -> list[Candidate]:
    if not math.isfinite(older_than_days) or older_than_days < 0:
        raise ValueError("--older-than-days must be a finite nonnegative number")
    tracked = tracked_files(root)
    cutoff = (time.time() if now is None else now) - older_than_days * 86400
    candidates = []
    for base in (*DISPOSABLE, *SOURCE_ROOTS):
        if has_symlink(root, base) or not (root / base).exists():
            continue
        for directory, dirs, files in os.walk(root / base, followlinks=False, onerror=_raise_walk_error):
            dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
            for name in files:
                path = Path(directory) / name
                relative = path.relative_to(root)
                if not allowed(relative) or relative in tracked or has_symlink(root, relative):
                    continue
                info = path.lstat()
                if stat.S_ISREG(info.st_mode) and info.st_mtime < cutoff:
                    candidates.append(Candidate(relative, info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino))
    return sorted(candidates, key=lambda item: str(item.path))


def _raise_walk_error(error: OSError) -> None:
    raise error


def apply_cleanup(root: Path, candidates: list[Candidate]) -> int:
    """Recheck tracking and file identity immediately before each removal."""
    tracked = tracked_files(root)
    removed = 0
    for item in candidates:
        if not allowed(item.path) or item.path in tracked or has_symlink(root, item.path):
            raise ValueError(f"Refusing changed or protected path: {item.path}")
        path = root / item.path
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or (
            info.st_size, info.st_mtime_ns, info.st_dev, info.st_ino
        ) != (item.size, item.mtime_ns, item.device, item.inode):
            raise ValueError(f"File changed since preview: {item.path}; rerun cleanup")
        path.unlink()
        removed += 1
        print(f"Removed {item.path}")
    return removed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Delete listed files; default only previews")
    parser.add_argument("--older-than-days", type=float, default=7, help="Minimum age in days (default: 7)")
    args = parser.parse_args()
    try:
        candidates = plan_cleanup(ROOT, args.older_than_days)
        for item in candidates:
            print(f"{item.size:>12} bytes  {item.path}")
        print(f"{'Apply' if args.apply else 'Preview'}: {len(candidates)} files, "
              f"{sum(item.size for item in candidates):,} bytes")
        if args.apply:
            print(f"Completed: {apply_cleanup(ROOT, candidates)} files removed")
        else:
            print("Use --apply to delete. Scripts, logs, reports, metadata and recovery state are excluded.")
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"Cleanup failed (an apply may be partial): {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
