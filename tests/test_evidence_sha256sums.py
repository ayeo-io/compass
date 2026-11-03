"""Red and green records hold SHA-256 digests a reviewer can check with `sha256sum`.

A record's `content_digest` is the SHA-256 of re-serialized JSON, and
`changes_id` is a git tree id no commit reaches. Neither can be checked
without Compass. A record now carries `file_sha256`, the SHA-256 of each of
the issue's files (its changed files and declared tests) as `sha256sum`
prints it, and lists the declared tests in `test_files`. The CLI writes
`evidence/SHA256SUMS`, which holds the digest of each record file and of each
of those files, so `sha256sum -c` run from the project root checks them.
A landed issue is judged by the same digests (ADR-089).

Scenario ids: SHA-1 to SHA-7, in ayeo-io/compass-delivery#348.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys

import pytest

from test_evidence_binding import (SLUG, _check, _cli, _git, _record,  # noqa: F401
                                   _write_manifest, repo)

SCENARIOS = {"scenarios": [{"id": "S-1", "title": "new", "intent": "INT-1",
                            "tests": ["tests/test_new.py::test_it"]}]}
FAIL = [sys.executable, "-c", "print('1 failed'); import sys; sys.exit(1)"]
PASS = [sys.executable, "-c", "pass"]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup(repo):
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    assert 0\n")
    _write_manifest(repo, gates="pass", extra=SCENARIOS)


def _run(repo, verb, command):
    result = _cli(repo, verb, "--issue", SLUG, "--", *command)
    assert result.returncode == 0, result.stdout + result.stderr


def _sums_check(repo):
    """`sha256sum -c` over the issue's sums file, run from the project root."""
    tool = (["sha256sum"] if shutil.which("sha256sum")
            else ["shasum", "-a", "256"])
    sums = f".compass/work/{SLUG}/evidence/SHA256SUMS"
    return subprocess.run([*tool, "-c", sums], cwd=repo, capture_output=True,
                          text=True)


def test_sha_1_a_green_holds_the_sha256_of_each_test_and_changed_file(repo):
    _setup(repo)
    (repo / "src" / "new.py").write_text("y = 2\n")
    _run(repo, "tdd-green", PASS)
    record = _record(repo)
    assert record["file_sha256"] == {
        "src/new.py": _sha(repo / "src" / "new.py"),
        "tests/test_new.py": _sha(repo / "tests" / "test_new.py")}
    assert record["test_files"] == ["tests/test_new.py"]
    assert "changes_id" not in record


def test_sha_2_red_then_code_then_green_passes_sha256sum(repo):
    _setup(repo)
    _run(repo, "tdd-red", FAIL)
    (repo / "src" / "new.py").write_text("y = 2\n")
    _run(repo, "tdd-green", PASS)
    sums = (repo / ".compass" / "work" / SLUG / "evidence" / "SHA256SUMS").read_text()
    named = {line.split("  ", 1)[1] for line in sums.splitlines()}
    assert named == {f".compass/work/{SLUG}/evidence/red.json",
                     f".compass/work/{SLUG}/evidence/green.json",
                     "src/new.py", "tests/test_new.py"}
    result = _sums_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_sha_3_a_test_corrected_between_red_and_green_still_passes(repo):
    _setup(repo)
    _run(repo, "tdd-red", FAIL)
    at_red = _sha(repo / "tests" / "test_new.py")
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    assert 1\n")
    _run(repo, "tdd-green", PASS)
    assert _record(repo, "red")["file_sha256"]["tests/test_new.py"] == at_red
    assert _record(repo)["file_sha256"]["tests/test_new.py"] != at_red
    result = _sums_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_sha_4_an_edited_record_or_file_fails_sha256sum(repo):
    _setup(repo)
    _run(repo, "tdd-green", PASS)
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    pass\n")
    assert _sums_check(repo).returncode != 0
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    assert 0\n")
    assert _sums_check(repo).returncode == 0
    green = repo / ".compass" / "work" / SLUG / "evidence" / "green.json"
    green.write_text(green.read_text() + "\n")
    result = _sums_check(repo)
    assert result.returncode != 0 and "green.json" in result.stdout


def _land(repo):
    _git(repo, "add", "src/new.py", "tests/test_new.py")
    _git(repo, "commit", "-q", "-m", "land")
    return _git(repo, "rev-parse", "HEAD")


def test_sha_5_a_landed_issue_is_judged_by_the_file_digests(repo):
    _setup(repo)
    (repo / "src" / "new.py").write_text("y = 2\n")
    _run(repo, "tdd-green", PASS)
    land = _land(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={**SCENARIOS, "land_commit": land})
    ok, why = _check(repo)
    assert ok is True, why
    # A land commit whose test is not the tested one fails, and names it.
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    assert 1\n")
    _git(repo, "add", "tests/test_new.py")
    _git(repo, "commit", "-q", "-m", "a different land")
    _write_manifest(repo, gates="pass", status="landed",
                    extra={**SCENARIOS, "land_commit": _git(repo, "rev-parse", "HEAD")})
    ok, why = _check(repo)
    assert ok is False, why
    assert "tests/test_new.py" in why and "landed" in why


def test_sha_6_an_old_record_is_still_judged_by_its_changes_id(repo):
    from compass_pkg.binding import _changes_id_at, changes_paths
    _setup(repo)
    (repo / "src" / "new.py").write_text("y = 2\n")
    _run(repo, "tdd-green", PASS)
    land = _land(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={**SCENARIOS, "land_commit": land})
    path = repo / ".compass" / "work" / SLUG / "evidence" / "green.json"
    record = json.loads(path.read_text())
    for key in ("file_sha256", "test_files"):
        record.pop(key)
    task = {"changed_files": [{"path": "src/new.py"}], **SCENARIOS}
    record["changes_id"] = _changes_id_at(str(repo), land, changes_paths(task))
    path.write_text(json.dumps(record))
    ok, why = _check(repo)
    assert ok is True, why
    record["changes_id"] = "ab" * 20
    path.write_text(json.dumps(record))
    ok, why = _check(repo)
    assert ok is False, why
    assert "tree" in why


def test_sha_7_content_digest_still_covers_the_file_digests(repo):
    from compass_pkg.evidence_identity import _check_evidence_identity_matches
    import yaml
    _setup(repo)
    _run(repo, "tdd-green", PASS)
    path = repo / ".compass" / "work" / SLUG / "evidence" / "green.json"
    record = json.loads(path.read_text())
    record["file_sha256"]["tests/test_new.py"] = "0" * 64
    path.write_text(json.dumps(record))
    task_dir = repo / ".compass" / "work" / SLUG
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    ok, why = _check_evidence_identity_matches(task, str(task_dir))
    assert ok is False and "edited" in why, why


@pytest.mark.parametrize("name", ["a b.py", "tab\tname.py"])
def test_sha_2_a_path_with_a_space_or_tab_is_checked(repo, name):
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / name).write_text("x = 1\n")
    _write_manifest(repo, gates="pass", extra={"scenarios": [
        {"id": "S-1", "title": "t", "intent": "INT-1", "tests": [f"tests/{name}::t"]}]})
    _run(repo, "tdd-green", PASS)
    result = _sums_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
