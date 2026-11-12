# Python Code Review Lab

A small, read-only CLI that scans a local repository for Python syntax errors
and emits a structured JSON report suitable for a CI step.

This is a **learning and portfolio project**, demonstrating Python fundamentals,
debugging, defensive file handling and automated tests. It is not professional
Python experience, a security auditor or a replacement for human code review.

## Problem and scope

A repository may contain broken Python files outside its usual test path.
This tool walks the tree and parses each `.py` file using the standard-library
`ast` module. It never imports the target modules or executes their code.
There are no runtime dependencies.

## Requirements and installation

Python **3.11 or newer**. Parsing follows the grammar of the interpreter running
the CLI: use the same Python version as the project you are reviewing.

```bash
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
```

## Commands and real examples

```bash
code-review-lab examples/clean
# Equivalent module entry point:
python -m code_review_lab examples/clean
```

Actual output for the included `examples/clean/greeting.py`:

```json
{
  "schema_version": 1,
  "files_analyzed": 1,
  "errors_found": 0,
  "findings": []
}
```

Generate a reproducible broken input outside the source tree:

```bash
mkdir -p /tmp/review-lab-example
printf 'def broken(:\n' > /tmp/review-lab-example/broken.py
code-review-lab /tmp/review-lab-example
```

Actual output on Python 3.12 (exit code 1):

```json
{
  "schema_version": 1,
  "files_analyzed": 1,
  "errors_found": 1,
  "findings": [
    {
      "path": "broken.py",
      "kind": "syntax",
      "message": "invalid syntax",
      "line": 1,
      "column": 12
    }
  ]
}
```

Messages may differ between Python versions. Paths inside a valid root are
relative POSIX-style paths; line and column offsets are one-based. For an
invalid root, the finding path is `.`. Operational exception messages can include
the local path: review the report before sharing it publicly.

```bash
code-review-lab ./my-repository > report.json
```

| Exit code | Meaning |
| --- | --- |
| 0 | Scan completed with no findings (including an empty directory) |
| 1 | At least one syntax error; no operational failure |
| 2 | Invalid path, read/encoding/traversal/parse resource error, or CLI usage error |

Operational failures take priority over syntax findings. CLI usage errors are
standard argparse errors on stderr; completed scans emit JSON on stdout.
`files_analyzed` counts successfully read Python files, even when syntax is
invalid. Unreadable files are findings but do not increment that count.
`errors_found` counts all findings, including operational errors.

## Architecture

- `analyzer.py`: deterministic traversal, encoding-aware reads, AST parsing and
  typed report/finding data classes.
- `cli.py`: argparse input, JSON serialization and exit-code mapping.
- `__main__.py`: module entry point.
- `tests/`: temporary-directory tests covering clean and invalid syntax,
  ignored directories, encodings, read and traversal failures, symlinks,
  invalid roots, ordering, exit codes and the no-execution guarantee.

Ignored directories: `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`,
`.pytest_cache`, `.ruff_cache`, `.mypy_cache`, `.tox` and `.nox`.
File and directory symlinks are skipped to avoid following ordinary links
outside the scan tree or recursing through loops. Python encoding cookies
are supported through `tokenize.open`.

## Development and validation

```bash
python -m pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest -q
code-review-lab examples/clean
```

Locally validated on Python 3.12: **23 pytest tests passed**, Ruff lint and
format checks passed. The workflow definition checks Python 3.11–3.14;
that matrix is not claimed as passing until its GitHub run completes.
No benchmark or coverage percentage is claimed.

## Limitations and next steps

- Syntax checks do not detect logical bugs, vulnerable dependencies, type
  errors, undefined names, formatting issues or malicious behavior.
- AST parsing is not execution, but very large/deep files can consume CPU or
  memory. This is not a sandbox for hostile, concurrently modified trees.
- Symlink checks are best-effort and do not protect against filesystem races.
- `.gitignore` rules are not interpreted; ignored directory names are fixed.
- Files are processed sequentially and fully read into memory.
- Possible improvements: configurable exclusions, file-size limits, a JSON
  Schema, optional Ruff integration and safe resource isolation.
