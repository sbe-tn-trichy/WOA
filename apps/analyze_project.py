"""Offline repository inspection; never imports the inspected project modules."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
from utils import json
from pathlib import Path
import re
import subprocess
import sys
from time import perf_counter
import tomllib
from typing import NotRequired, TypedDict
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ("README.md", "INDEX.md", "WORKFLOWS.md", "PROJECT_ANALYSIS.md", "okf/index.md")


class ChangeRecord(TypedDict):
    status: str
    path: str
    old_path: NotRequired[str]


class Diagnostic(TypedDict):
    file: str
    message: str
    line: NotRequired[int | None]
    rule: NotRequired[str]


class Verification(TypedDict):
    command: list[str]
    status: str
    output: str
    duration_seconds: float
    returncode: NotRequired[int]


class TypingScope(TypedDict):
    configured_targets: list[str]
    explicitly_covered: list[str]
    outside_explicit_targets: list[str]


class Capture(TypedDict):
    utc: str
    duration_seconds: float


class Snapshot(TypedDict):
    schema_version: int
    revision: str
    baseline: str | None
    changes: dict[str, list[ChangeRecord]]
    python_files: list[str]
    typing: TypingScope
    finding_ids: list[str]
    review_baseline_text: str
    review_candidates: dict[str, list[str]]
    diagnostics: list[Diagnostic]
    errors: list[Diagnostic]
    limitations: list[str]
    verification: NotRequired[list[Verification]]
    capture: NotRequired[Capture]


def git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            encoding="utf-8", errors="replace", timeout=30)
    if result.returncode:
        raise ValueError(result.stderr.strip() or "Git inspection failed")
    return result.stdout.rstrip("\r\n")


def changed_records(raw: str) -> list[ChangeRecord]:
    """Parse NUL-delimited name-status output, preserving spaces and renames."""
    fields = iter(raw.split("\0"))
    records: list[ChangeRecord] = []
    for status in fields:
        if not status:
            continue
        path = next(fields)
        record: ChangeRecord = {"status": status, "path": path}
        if status.startswith(("R", "C")):
            record = {"status": status, "old_path": path, "path": next(fields)}
        records.append(record)
    return records


def module_name(path: str) -> str:
    parts = list(Path(path).with_suffix("").parts)
    if parts[0] == "src":
        parts.pop(0)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def imports(tree: ast.AST, module: str, package: bool) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = module.split(".") if package else module.split(".")[:-1]
                parent = parent[:len(parent) - node.level + 1]
                base = ".".join(parent + ([base] if base else []))
            found.append((node.lineno, base))
            found.extend((node.lineno, f"{base}.{alias.name}") for alias in node.names)
    return found


def heading_slug(heading: str) -> str:
    text = re.sub(r"`([^`]*)`", r"\1", heading.strip().lower())
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text).strip("-")


def markdown_headings(path: Path, cache: dict[Path, set[str]]) -> set[str]:
    resolved = path.resolve()
    if resolved not in cache:
        content = resolved.read_text(encoding="utf-8", errors="replace")
        cache[resolved] = {heading_slug(h) for h in re.findall(r"^#{1,6}\s+(.+)$", content, re.MULTILINE)}
    return cache[resolved]


def inspect(root: Path, since: str | None = None) -> Snapshot:
    revision = git(root, "rev-parse", "HEAD")
    changes: dict[str, list[ChangeRecord]] = {
        "staged": changed_records(git(root, "diff", "--cached", "--name-status", "-z", "--find-renames")),
        "unstaged": changed_records(git(root, "diff", "--name-status", "-z", "--find-renames")),
        "untracked": [{"status": "?", "path": p} for p in git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0") if p],
    }
    baseline = None
    if since:
        baseline = git(root, "rev-parse", "--verify", "--end-of-options", since + "^{commit}")
        changes["committed"] = changed_records(git(root, "diff", "--name-status", "-z", "--find-renames", baseline, revision))
    tracked = git(root, "ls-files", "-z").split("\0")
    candidates = set(tracked) | {r["path"] for r in changes["untracked"]}
    files = sorted(p for p in candidates if p.endswith(".py") and p.startswith(("src/", "apps/", "tests/")) and (root / p).is_file())
    diagnostics: list[Diagnostic] = []
    errors: list[Diagnostic] = []
    graph: dict[str, list[str]] = {}
    for path in files:
        try:
            tree = ast.parse((root / path).read_text(encoding="utf-8-sig"), filename=path)
        except (SyntaxError, UnicodeError, OSError) as exc:
            errors.append({"file": path, "line": getattr(exc, "lineno", None), "message": str(exc)})
            continue
        module = module_name(path)
        dependencies = imports(tree, module, path.endswith("/__init__.py"))
        graph[path] = sorted({name for _, name in dependencies})
        forbidden = {"apps", "scripts"}
        if path.startswith("src/utils/"):
            forbidden.update({"zoho", "workflows", "google_sheets"})
        elif path.startswith("src/zoho/"):
            forbidden.add("workflows")
        if path.startswith(("src/utils/", "src/zoho/", "src/workflows/")):
            for line, name in dependencies:
                if name.split(".")[0] in forbidden:
                    diagnostic: Diagnostic = {"file": path, "line": line, "rule": "import-layer", "message": f"Forbidden import: {name}"}
                    if diagnostic not in diagnostics:
                        diagnostics.append(diagnostic)
    config = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    targets = config.get("tool", {}).get("ty", {}).get("src", {}).get("include", [])
    covered = [p for p in files if any(p == t.rstrip("/") or p.startswith(t.rstrip("/") + "/") for t in targets)]
    optional_docs = [p for p in ("AGENTS.md", "GEMINI.md", "CHANGELOG.md") if (root / p).is_file()]
    okf_docs = sorted(p.relative_to(root).as_posix() for p in (root / "okf").glob("*.md") if p.is_file()) if (root / "okf").is_dir() else []
    checked_docs = list(dict.fromkeys([*DOCUMENTS, *optional_docs, *okf_docs]))
    heading_cache: dict[Path, set[str]] = {}
    for doc in checked_docs:
        document = root / doc
        if not document.is_file():
            if doc in DOCUMENTS:
                errors.append({"file": doc, "message": "Required navigation document is missing"})
            continue
        content = document.read_text(encoding="utf-8")
        if doc == "okf/log.md" and content.startswith("---\n"):
            diagnostics.append({"file": doc, "line": 1, "rule": "okf-frontmatter", "message": "okf/log.md must not have YAML frontmatter"})
        elif doc.startswith("okf/") and doc not in {"okf/index.md", "okf/log.md"}:
            frontmatter = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", content, re.DOTALL)
            if not frontmatter or not re.search(r"^type:\s*\S+", frontmatter.group(1), re.MULTILINE):
                diagnostics.append({"file": doc, "line": 1, "rule": "okf-frontmatter", "message": "Missing required YAML frontmatter with non-empty type"})
        for line, text in enumerate(content.splitlines(), 1):
            for raw_target in re.findall(r"(?<!!)\[[^\]]+\]\(([^)]+)\)", text):
                cleaned = raw_target.strip("<>")
                target, _, anchor = cleaned.partition("#")
                if not target or re.match(r"[a-zA-Z][\w+.-]*:", target):
                    continue
                resolved_target = document.parent / unquote(target)
                if not resolved_target.exists():
                    diagnostics.append({"file": doc, "line": line, "rule": "local-link", "message": f"Missing target: {target}"})
                elif anchor and resolved_target.is_file() and resolved_target.suffix.lower() == ".md":
                    if unquote(anchor).lower() not in markdown_headings(resolved_target, heading_cache):
                        diagnostics.append({"file": doc, "line": line, "rule": "local-link", "message": f"Missing anchor: {cleaned}"})
    analysis = (root / "PROJECT_ANALYSIS.md").read_text(encoding="utf-8")
    changed_paths = sorted({r[k] for group in changes.values() for r in group for k in ("path", "old_path") if k in r})
    modules = {module_name(p) for p in changed_paths if p.endswith(".py")}
    dependents = sorted(p for p, deps in graph.items() if any(d == m or d.startswith(m + ".") for d in deps for m in modules))
    reached: set[str] = set()
    frontier = set(modules)
    while frontier:
        next_paths = {
            p for p, deps in graph.items()
            if p not in reached and any(d == m or d.startswith(m + ".") for d in deps for m in frontier)
        }
        if not next_paths:
            break
        reached.update(next_paths)
        frontier = {module_name(p) for p in next_paths} - modules
    transitive = sorted(reached - set(dependents) - set(changed_paths))
    affected_tests = sorted(
        p for p in (reached | (set(changed_paths) & set(files)))
        if p.startswith("tests/") or Path(p).name.startswith("test_") or Path(p).name.endswith("_test.py")
    )
    broad = [p for p in changed_paths if p.startswith(("src/utils/", "src/workflows/core/", "src/zoho/", ".github/", "tests/", "okf/")) or p in {"pyproject.toml", "AGENTS.md", ".python-version", *DOCUMENTS}]
    return {"schema_version": 1, "revision": revision, "baseline": baseline, "changes": changes,
            "python_files": files, "typing": {"configured_targets": targets, "explicitly_covered": covered,
            "outside_explicit_targets": sorted(set(files) - set(covered))},
            "finding_ids": re.findall(r"^### ([A-Z]+-\d+)", analysis, re.MULTILINE),
            "review_baseline_text": analysis.split("## Categories and ownership")[0],
            "review_candidates": {
                "changed": changed_paths,
                "direct_dependents": dependents,
                "transitive_dependents": transitive,
                "affected_tests": affected_tests,
                "broader_review_triggers": broad,
            },
            "diagnostics": diagnostics, "errors": errors,
            "limitations": ["Static imports only; dynamic imports and indirect dependencies require review.",
                            "Explicit ty targets are not transitive type-check coverage.",
                            "Link checks cover designated navigation, changelog, and OKF Markdown files (including cross-file heading anchors), not in-page anchors or all Markdown syntax.",
                            "Incremental candidates do not establish financial safety or verify unchanged code."]}


def verify(root: Path) -> list[Verification]:
    results: list[Verification] = []
    for args in (["apps/generate_api_reference.py", "--check"], ["-m", "ty", "check"]):
        start = perf_counter()
        command = [sys.executable, *args]
        try:
            completed = subprocess.run(command, cwd=root, capture_output=True, encoding="utf-8", errors="replace", timeout=180)
            unavailable = "No module named" in completed.stderr
            results.append({"command": command, "status": "incomplete" if unavailable else "passed" if completed.returncode == 0 else "failed",
                            "returncode": completed.returncode, "output": completed.stdout + completed.stderr,
                            "duration_seconds": round(perf_counter() - start, 3)})
        except (OSError, subprocess.TimeoutExpired) as exc:
            results.append({"command": command, "status": "incomplete", "output": str(exc), "duration_seconds": round(perf_counter() - start, 3)})
    return results


def render(report: Snapshot) -> str:
    lines = ["# Project analysis snapshot", "", f"Revision: `{report['revision']}`", "",
             f"Python files: {len(report['python_files'])}; explicit ty targets cover {len(report['typing']['explicitly_covered'])} files.",
             f"Diagnostics: {len(report['diagnostics'])}; inspection errors: {len(report['errors'])}.",
             f"Comparison baseline: `{report['baseline'] or 'not requested'}`.", ""]
    if "capture" in report:
        lines.extend([f"Captured: {report['capture']['utc']}; duration: {report['capture']['duration_seconds']}s.", ""])
    lines.extend(["## Changes", ""])
    for group, records in report["changes"].items():
        lines.append(f"- {group}: {len(records)}")
        lines.extend(f"  - {r['status']} `{r.get('old_path', r['path'])}`" + (f" → `{r['path']}`" if "old_path" in r else "") for r in records)
    for title, findings in (("Diagnostics", report["diagnostics"]), ("Inspection errors", report["errors"])):
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- `{r['file']}:{r.get('line', '')}`: {r['message']}" for r in findings)
    lines.extend(["", "## Review candidates", ""])
    for group, paths in report["review_candidates"].items():
        lines.append(f"- {group}: " + ", ".join(f"`{p}`" for p in paths))
    lines.extend(["", "## Verification", ""])
    lines.extend(f"- `{' '.join(r['command'])}`: {r['status']} ({r['duration_seconds']}s)\n\n```text\n{r['output'].rstrip()}\n```" for r in report["verification"])
    if not report["verification"]:
        lines.append("Not requested.")
    lines.extend(["", "## Existing review baseline", "", report["review_baseline_text"], "", "Finding IDs: " + ", ".join(report["finding_ids"]), "", "## Limitations", ""])
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", help="Commit to compare with HEAD; local changes are also reported")
    parser.add_argument("--verify", action="store_true", help="Also run API reference check and configured ty")
    args = parser.parse_args()
    start = perf_counter()
    try:
        report = inspect(ROOT, args.since)
        report["verification"] = verify(ROOT) if args.verify else []
        report["capture"] = {"utc": datetime.now(timezone.utc).isoformat(), "duration_seconds": round(perf_counter() - start, 3)}
        destination = ROOT / "output" / "project-analysis"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (destination / "report.md").write_text(render(report), encoding="utf-8")
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Inspection incomplete: {exc}", file=sys.stderr)
        return 2
    print(f"Report: {destination / 'report.md'} ({report['capture']['duration_seconds']}s)")
    if report["errors"] or any(r["status"] == "incomplete" for r in report["verification"]):
        return 2
    return 1 if report["diagnostics"] or any(r["status"] == "failed" for r in report["verification"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
