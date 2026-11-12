"""Inspect source without importing or executing it."""

from __future__ import annotations

import ast
import os
import tokenize
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

IGNORED_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        ".nox",
    }
)


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    message: str
    line: int | None = None
    column: int | None = None


@dataclass
class Report:
    files_analyzed: int = 0
    findings: list[Finding] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        if any(item.kind != "syntax" for item in self.findings):
            return 2
        return 1 if self.findings else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "files_analyzed": self.files_analyzed,
            "errors_found": len(self.findings),
            "findings": [asdict(item) for item in self.findings],
        }


def analyze(directory: Path) -> Report:
    """Scan in deterministic order; skip all symlinks and common generated directories.

    files_analyzed counts successfully read files, including syntax-invalid files.
    Unreadable files and directory traversal failures become operational findings.
    """
    report = Report()
    try:
        root = directory.resolve(strict=True)
        if not root.is_dir():
            raise NotADirectoryError("Expected a directory")
    except (OSError, RuntimeError) as exc:
        report.findings.append(Finding(".", "path", str(exc)))
        return report

    def traversal_error(error: OSError) -> None:
        path = Path(error.filename).relative_to(root).as_posix() if error.filename else "."
        report.findings.append(Finding(path, "read", error.strerror or "Traversal failed"))

    for current, dirs, files in os.walk(root, followlinks=False, onerror=traversal_error):
        parent = Path(current)
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS and not (parent / d).is_symlink())
        for name in sorted(files):
            path = parent / name
            if path.suffix != ".py" or path.is_symlink():
                continue
            relative = path.relative_to(root).as_posix()
            try:
                # Honor Python encoding cookies, including non-UTF-8 source files.
                with tokenize.open(path) as source_file:
                    source = source_file.read()
            except (OSError, UnicodeError, SyntaxError) as exc:
                report.findings.append(Finding(relative, "read", str(exc)))
                continue
            report.files_analyzed += 1
            try:
                ast.parse(source, filename=relative)
            except SyntaxError as exc:
                report.findings.append(Finding(relative, "syntax", exc.msg, exc.lineno, exc.offset))
            except (ValueError, RecursionError) as exc:
                report.findings.append(Finding(relative, "parse", str(exc)))
    report.findings.sort(key=lambda item: (item.path, item.kind, item.line or 0))
    return report
