import json
from unittest.mock import patch

import pytest

from code_review_lab.analyzer import IGNORED_DIRS, analyze
from code_review_lab.cli import main


def test_clean_source_is_not_executed(tmp_path):
    (tmp_path / "danger.py").write_text("raise RuntimeError('never execute me')\n")
    report = analyze(tmp_path)
    assert report.files_analyzed == 1
    assert report.exit_code == 0


def test_syntax_location_and_deterministic_order(tmp_path):
    for name in ["z.py", "a.py"]:
        (tmp_path / name).write_text("def broken(:\n")
    report = analyze(tmp_path)
    assert report.files_analyzed == 2
    assert [f.path for f in report.findings] == ["a.py", "z.py"]
    assert all(f.line == 1 and f.column for f in report.findings)
    assert report.exit_code == 1


@pytest.mark.parametrize("name", sorted(IGNORED_DIRS))
def test_ignored_directories(tmp_path, name):
    ignored = tmp_path / name
    ignored.mkdir()
    (ignored / "bad.py").write_text("def broken(:")
    assert analyze(tmp_path).files_analyzed == 0


def test_nested_files_and_non_python(tmp_path):
    child = tmp_path / "src"
    child.mkdir()
    (child / "valid.py").write_text("x = 1\n")
    (child / "ignored.txt").write_text("invalid python")
    assert analyze(tmp_path).files_analyzed == 1


def test_encoding_cookie(tmp_path):
    (tmp_path / "latin.py").write_bytes(b"# coding: latin-1\nname = 'caf\xe9'\n")
    assert analyze(tmp_path).exit_code == 0


def test_invalid_encoding(tmp_path):
    (tmp_path / "bad.py").write_bytes(b"\xff")
    report = analyze(tmp_path)
    assert report.files_analyzed == 0
    assert report.findings[0].kind == "read"
    assert report.exit_code == 2


def test_read_failure(tmp_path):
    (tmp_path / "blocked.py").write_text("x = 1")
    with patch("code_review_lab.analyzer.tokenize.open", side_effect=PermissionError("denied")):
        report = analyze(tmp_path)
    assert report.exit_code == 2
    assert report.findings[0].kind == "read"


def test_directory_traversal_failure(tmp_path):
    def walk(root, **kwargs):
        kwargs["onerror"](PermissionError(13, "denied", str(root / "blocked")))
        return iter(())

    with patch("code_review_lab.analyzer.os.walk", side_effect=walk):
        report = analyze(tmp_path)
    assert report.exit_code == 2
    assert report.findings[0].path == "blocked"


def test_symlinks_are_skipped(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "valid.py").write_text("x = 1")
    (tmp_path / "linked.py").symlink_to(source / "valid.py")
    (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
    assert analyze(tmp_path).files_analyzed == 1


@pytest.mark.parametrize("kind", ["missing", "file"])
def test_invalid_root(tmp_path, kind):
    path = tmp_path / kind
    if kind == "file":
        path.touch()
    report = analyze(path)
    assert report.exit_code == 2
    assert report.findings[0].kind == "path"


def test_cli_json_and_exit_code(tmp_path, capsys):
    (tmp_path / "bad.py").write_text("def broken(:")
    assert main([str(tmp_path)]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["schema_version"] == 1
    assert data["errors_found"] == 1


def test_cli_missing_argument():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_empty_directory(tmp_path):
    assert analyze(tmp_path).to_dict() == {
        "schema_version": 1,
        "files_analyzed": 0,
        "errors_found": 0,
        "findings": [],
    }
