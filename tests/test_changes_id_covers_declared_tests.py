"""A landed issue's binding covers the test files its scenarios declare.

`changes_id` names the tree of the files an issue changed, and a landed issue
is judged by comparing it with the same files in the commit that landed it.
The set is the files in `changed_files` plus the test files the issue's
scenarios declare. A test a scenario relies on is part of what was tested,
whether or not `changed_files` lists it, so a later change to it shows.

A record built before the set grew carries no `changes_scope`, and is judged
with `changed_files` alone, as it was built.

Scenario ids: CUF-1 to CUF-3, in the delivery approach of issue
`changes-id-misses-unlisted-files`.
"""
from __future__ import annotations

import json

from test_evidence_binding import (SLUG, _check, _git, _green, _record,  # noqa: F401
                                   _write_manifest, repo)

SCENARIOS = {"scenarios": [{"id": "S-1", "title": "new", "intent": "INT-1",
                            "tests": ["tests/test_new.py::test_it"]}]}


def _land(repo):
    _git(repo, "add", "src/new.py", "tests/test_new.py")
    _git(repo, "commit", "-q", "-m", "land")
    return _git(repo, "rev-parse", "HEAD")


def _setup(repo):
    (repo / "src" / "new.py").write_text("y = 2\n")
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    pass\n")
    _write_manifest(repo, gates="pass", extra=SCENARIOS)


def test_cuf_1_a_declared_test_changed_before_the_land_fails_the_check(repo):
    _setup(repo)
    _green(repo)
    assert _record(repo).get("changes_scope") == "changed-files-and-declared-tests"
    # The test is edited after the green and lands edited.
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    assert 1\n")
    land = _land(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={**SCENARIOS, "land_commit": land})
    ok, why = _check(repo)
    assert ok is False, why
    assert "landed" in why


def test_cuf_2_the_tested_files_landing_pass_whatever_head_does_next(repo):
    _setup(repo)
    _green(repo)
    land = _land(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={**SCENARIOS, "land_commit": land})
    ok, why = _check(repo)
    assert ok is True, why
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    assert 2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "later work")
    ok, why = _check(repo)
    assert ok is True, why


def test_cuf_3_a_record_built_before_the_scope_is_judged_as_built(repo):
    from compass_pkg.binding import changes_id
    _setup(repo)
    _green(repo)
    path = repo / ".compass" / "work" / SLUG / "evidence" / "green.json"
    record = json.loads(path.read_text())
    record.pop("changes_scope", None)
    record["changes_id"] = changes_id(str(repo), ["src/new.py"])
    path.write_text(json.dumps(record))
    # The declared test changes before the land; the old record never
    # covered it, so it is judged on the listed source file alone and passes.
    (repo / "tests" / "test_new.py").write_text("def test_it():\n    assert 1\n")
    land = _land(repo)
    _write_manifest(repo, gates="pass", status="landed",
                    extra={**SCENARIOS, "land_commit": land})
    ok, why = _check(repo)
    assert ok is True, why


def test_cuf_1_only_relative_paths_inside_the_project_are_declared():
    from compass_pkg.binding import declared_test_paths
    task = {"scenarios": [{"tests": ["tests/a.py::t", "/etc/passwd::x",
                                     "../outside.py", "tests/b.py", 3]}]}
    assert declared_test_paths(task) == ["tests/a.py", "tests/b.py"]
