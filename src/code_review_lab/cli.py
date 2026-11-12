"""Command-line entry point. Reports go to stdout; usage errors go to stderr."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from code_review_lab.analyzer import analyze


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect local Python syntax without executing code"
    )
    parser.add_argument("directory", type=Path, help="Local repository directory")
    args = parser.parse_args(argv)
    report = analyze(args.directory)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=True))
    return report.exit_code
