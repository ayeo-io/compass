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


def _crlf(repo):
    (repo / ".gitattributes").write_text("*.py text eol=crlf\n")
    _git(repo, "add", ".gitattributes")
    _git(repo, "commit", "-q", "-m", "attrs")


def test_sha_8_a_crlf_checkout_is_compared_as_checked_out_bytes(repo):
    """With `eol=crlf` the bytes on disk are not the blob in git. The commit
    side is read through git's checkout conversion, as the disk side is."""
    _crlf(repo)
    _setup(repo)
    (repo / "src" / "new.py").write_bytes(b"y = 2\r\n")
    (repo / "tests" / "test_new.py").write_bytes(b"def test_it():\r\n    pass\r\n")
    _run(repo, "tdd-green", PASS)
    land = _land(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={**SCENARIOS, "land_commit": land})
    ok, why = _check(repo)
    assert ok is True, why


def test_sha_8_ship_commit_lands_a_crlf_file_it_tested(repo):
    _crlf(repo)
    (repo / "src" / "new.py").write_bytes(b"y = 1\r\n")
    _run(repo, "tdd-green", PASS)
    _git(repo, "add", "src/new.py")
    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode == 0, result.stdout + result.stderr


def test_sha_9_a_mode_change_after_the_green_fails_the_landed_check(repo):
    _setup(repo)
    (repo / "src" / "new.py").write_text("y = 2\n")
    _run(repo, "tdd-green", PASS)
    assert _record(repo)["file_modes"]["src/new.py"] == "100644"
    (repo / "src" / "new.py").chmod(0o755)
    land = _land(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={**SCENARIOS, "land_commit": land})
    ok, why = _check(repo)
    assert ok is False, why
    assert "src/new.py" in why and "mode" in why


def test_sha_9_ship_commit_refuses_a_mode_change_after_the_green(repo):
    (repo / "src" / "new.py").write_text("y = 1\n")
    _run(repo, "tdd-green", PASS)
    (repo / "src" / "new.py").chmod(0o755)
    _git(repo, "add", "src/new.py")
    result = _cli(repo, "ship-commit", "--issue", SLUG, "-m", "land it")
    assert result.returncode != 0
    assert "src/new.py" in result.stdout + result.stderr


def test_sha_10_a_file_deleted_after_the_red_leaves_no_line(repo):
    _setup(repo)
    _write_manifest(repo, gates="pass", extra={**SCENARIOS, "changed_files": [
        {"path": "src/new.py", "scenarios": ["S-1"]},
        {"path": "src/app.py", "scenarios": ["S-1"]}]})
    _run(repo, "tdd-red", FAIL)
    (repo / "src" / "app.py").unlink()
    (repo / "src" / "new.py").write_text("y = 2\n")
    _run(repo, "tdd-green", PASS)
    result = _sums_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_sha_10_a_file_renamed_after_the_red_leaves_no_line(repo):
    _setup(repo)
    _write_manifest(repo, gates="pass", extra={**SCENARIOS, "changed_files": [
        {"path": "src/app.py", "scenarios": ["S-1"]}]})
    _run(repo, "tdd-red", FAIL)
    (repo / "src" / "app.py").rename(repo / "src" / "renamed.py")
    _write_manifest(repo, gates="pass", extra={**SCENARIOS, "changed_files": [
        {"path": "src/renamed.py", "scenarios": ["S-1"]}]})
    _run(repo, "tdd-green", PASS)
    result = _sums_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_sha_11_the_record_written_last_gives_the_file_lines(tmp_path):
    """Records carry the time to the second. A red and a green in one second,
    then a later record, must leave the green's digests, not the red's."""
    from compass_pkg import evidence_sums
    from compass_pkg.red_first import content_digest
    ev = tmp_path / ".compass" / "work" / "x" / "evidence"
    ev.mkdir(parents=True)
    (tmp_path / "p.py").write_text("v2\n")

    def write(name, stamp, files):
        record = {"timestamp": stamp, "file_sha256": files}
        record["content_digest"] = content_digest(record)
        (ev / name).write_text(json.dumps(record))
        evidence_sums.record_written(str(ev.parent), str(ev / name))

    same = "2026-11-03T10:00:00Z"
    write("red.json", same, {"p.py": hashlib.sha256(b"v1\n").hexdigest()})
    write("green.json", same, {"p.py": hashlib.sha256(b"v2\n").hexdigest()})
    write("isolation.json", "2026-11-03T10:00:05Z", {})
    tool = ["sha256sum"] if shutil.which("sha256sum") else ["shasum", "-a", "256"]
    result = subprocess.run([*tool, "-c", ".compass/work/x/evidence/SHA256SUMS"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
