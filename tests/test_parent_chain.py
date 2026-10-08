"""Chains of git parents, to depth three (issue `parent-chains`).

A git parent can name a git parent of its own. Each one is pinned by sha,
fetched the same way and checked as data. These tests build local git
repositories in a temporary folder and point `COMPASS_PARENT_REMOTE_BASE` at
them, so nothing reaches the network.

Scenario ids: `PC-1` to `PC-8`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import REAL_GIT, commit, fake_git, issue_project, make_remote  # noqa: E402

CLI = ROOT / "cli" / "compass"


# --- helpers -------------------------------------------------------------------

def _env(home, extra=None):
    env = {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(home), "LANG": "C.UTF-8",
           "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    env.update(extra or {})
    return env


def _run(cwd, *argv, env=None):
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd, env),
                          capture_output=True, text=True, timeout=180)
    return done.returncode, done.stdout, done.stderr


def _lint(root, *extra, env=None):
    code, out, err = _run(root, "policy", "lint", "--json", *extra, env=env)
    return code, (json.loads(out) if out.strip().startswith("{") else {}), err


def _codes(report):
    return [f["code"] for f in report.get("findings", [])]


def _ref(sha, repo, ref="1.0.0"):
    return f"github:acme/{repo}@{ref}#{sha}"


def _label(sha, repo, ref="1.0.0"):
    return f"github:acme/{repo}@{ref}#{sha[:7]}"


def _project(tmp_path, extends):
    root = tmp_path / "project"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text(yaml.safe_dump({"schema": 1, "extends": extends}),
                                      encoding="utf-8")
    return root


def _cache(root):
    return root / ".compass" / "cache" / "parents"


def _build(base, docs):
    """Publish `docs` as repositories `p1`, `p2`... Each document is a mapping.
    `docs[0]` is the furthest ancestor and each later one extends the one
    before it. Returns the `(repo, sha)` pairs, furthest first."""
    made, previous = [], None
    for index, doc in enumerate(docs, start=1):
        doc = dict(doc)
        if previous:
            doc["extends"] = _ref(previous[1], previous[0])
        repo = f"p{index}"
        sha = make_remote(base, repo=repo, files={"compass.yml": yaml.safe_dump(doc)})
        previous = (repo, sha)
        made.append(previous)
    return made


def _chain_project(tmp_path, docs):
    base = tmp_path / "remotes"
    made = _build(base, docs)
    repo, sha = made[-1]
    return _project(tmp_path, _ref(sha, repo)), made, {"COMPASS_PARENT_REMOTE_BASE": str(base)}


PLAIN = {"schema": 1}


def _effective(root, env, *extra):
    code, out, err = _run(root, "policy", "effective", *extra, env=env)
    return code, out, err


# --- PC-1: a chain of two ---------------------------------------------------------

def test_pc_1_a_chain_of_two_pinned_parents_loads_furthest_first(tmp_path):
    root, made, env = _chain_project(tmp_path, [PLAIN, PLAIN])
    code, out, err = _effective(root, env, "--json")
    assert code == 0, err
    names = [layer["name"] for layer in json.loads(out)["layers"]]
    assert names == ["default", _label(made[0][1], "p1"), _label(made[1][1], "p2"), "project"]
    for _, sha in made:
        assert (_cache(root) / sha / "compass.yml").is_file()


def test_pc_1_an_ancestor_that_cannot_be_fetched_is_reported_on_the_parent_that_names_it(
        tmp_path):
    base = tmp_path / "remotes"
    missing = "c" * 40
    sha = make_remote(base, repo="p2", files={"compass.yml": yaml.safe_dump(
        {"schema": 1, "extends": _ref(missing, "p1")})})
    root = _project(tmp_path, _ref(sha, "p2"))
    code, report, _ = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 1
    assert _codes(report) == ["L-PARENT-FETCH"], report
    assert report["findings"][0]["layer"] == _label(sha, "p2")


# --- PC-2: depth three, and a refusal past it ---------------------------------------------

def test_pc_2_a_chain_of_three_git_parents_loads(tmp_path):
    root, made, env = _chain_project(tmp_path, [PLAIN, PLAIN, PLAIN])
    code, report, err = _lint(root, env=env)
    assert code == 0, (report, err)
    assert len(report["layers"]) == 5


def test_pc_2_a_fourth_git_parent_is_refused_on_the_third_and_is_not_fetched(tmp_path):
    root, made, env = _chain_project(tmp_path, [PLAIN, PLAIN, PLAIN, PLAIN])
    code, report, _ = _lint(root, env=env)
    assert code == 1
    assert _codes(report) == ["L-PARENT-CHAIN"], report
    finding = report["findings"][0]
    assert finding["layer"] == _label(made[1][1], "p2")
    assert finding["path"] == "extends"
    assert "three" in finding["message"]
    assert not (_cache(root) / made[0][1]).exists(), "the fourth git parent was fetched"


# --- PC-3: a cycle -----------------------------------------------------------------------

def test_pc_3_a_commit_named_twice_in_a_chain_is_a_cycle(tmp_path):
    sha_a, sha_b = "a" * 40, "b" * 40
    root = _project(tmp_path, _ref(sha_a, "pa"))
    for sha, repo, other, other_repo in ((sha_a, "pa", sha_b, "pb"), (sha_b, "pb", sha_a, "pa")):
        folder = _cache(root) / sha
        folder.mkdir(parents=True)
        (folder / "compass.yml").write_text(
            yaml.safe_dump({"schema": 1, "extends": _ref(other, other_repo)}), encoding="utf-8")
    code, report, _ = _lint(root, "--offline")
    assert code == 1
    assert _codes(report) == ["L-PARENT-CYCLE"], report
    assert report["findings"][0]["layer"] == _label(sha_b, "pb")
    assert sha_a[:7] in report["findings"][0]["message"]


# --- PC-4: every parent is data only -----------------------------------------------------

def _settings_keys():
    from compass_pkg import catalogue_spec
    return list(catalogue_spec.SETTINGS_KEYS)


@pytest.mark.parametrize("place", [0, 1, 2], ids=["furthest", "middle", "nearest"])
@pytest.mark.parametrize("key", _settings_keys())
def test_pc_4_a_settings_key_in_any_parent_of_a_chain_is_refused_by_name(
        tmp_path, key, place):
    docs = [dict(PLAIN), dict(PLAIN), dict(PLAIN)]
    docs[place][key] = True
    root, made, env = _chain_project(tmp_path, docs)
    code, report, _ = _lint(root, env=env)
    assert code == 1
    blamed = [f for f in report["findings"] if f["code"] == "L-SETTINGS-KEY"]
    assert len(blamed) == 1, report
    repo, sha = made[place]
    assert blamed[0]["layer"] == _label(sha, repo)
    assert key in blamed[0]["path"] + blamed[0]["message"]
    assert report["stopped_after"] == "layer"


UNLOCK = {"schema": 1, "checks": {"suite-passed": {"unlock": True}}}
UNKNOWN_IMPL = {"schema": 1, "checks": {"evil": {
    "name": "evil", "kind": "mechanical", "impl": "rm-rf", "blocking_when": "fail"}}}


@pytest.mark.parametrize("doc,code", [(UNLOCK, "L-UNLOCK-PLACEMENT"),
                                      (UNKNOWN_IMPL, "L-IMPL-UNKNOWN"),
                                      ({"schema": 1, "mystery": 1}, "L-SCHEMA")],
                         ids=["unlock", "impl", "unknown-key"])
def test_pc_4_an_unlock_an_unknown_impl_or_an_unknown_key_in_the_furthest_parent_is_refused(
        tmp_path, doc, code):
    root, made, env = _chain_project(tmp_path, [doc, PLAIN, PLAIN])
    exit_code, report, _ = _lint(root, env=env)
    assert exit_code == 1
    assert code in _codes(report), report
    blamed = next(f for f in report["findings"] if f["code"] == code)
    assert blamed["layer"] == _label(made[0][1], "p1")


@pytest.mark.parametrize("place", [0, 1, 2], ids=["furthest", "middle", "nearest"])
def test_pc_4_a_settings_key_in_any_parent_of_a_chain_stops_the_commit_of_a_generation(
        tmp_path, monkeypatch, place):
    docs = [dict(PLAIN), dict(PLAIN), dict(PLAIN)]
    docs[place]["allow_project_commands"] = True
    base = tmp_path / "remotes"
    made = _build(base, docs)
    repo, sha = made[-1]
    root, task_dir = issue_project(tmp_path, _ref(sha, repo))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    with pytest.raises(Exception) as caught:
        commit(task_dir)
    assert "allow_project_commands" in str(caught.value), caught.value
    assert not (task_dir / "generations" / "1").exists()


def test_pc_4_the_keys_a_parent_may_hold_are_accepted_at_every_depth(tmp_path):
    allowed = {"schema": 1, "owner": "team", "preset": {"description": "x"},
               "capabilities": {"entry-exit-evaluation": False},
               "approvers": {"project-waiver": ["jed72"]}}
    root, made, env = _chain_project(tmp_path, [allowed, allowed, allowed])
    code, report, err = _lint(root, env=env)
    assert code == 0, (report, err)


# --- PC-5: merge order and provenance -------------------------------------------------------

CHECK = {"kind": "deterministic", "impl": "suite-passed", "severity": "advisory",
         "on_skipped": "fail"}


def test_pc_5_effective_names_the_nearest_parent_that_wrote_each_field(tmp_path):
    docs = [
        {"schema": 1, "owner": "far-team", "checks": {"far-check": dict(CHECK, statement="far")}},
        {"schema": 1, "owner": "middle-team"},
        {"schema": 1, "owner": "near-team", "checks": {"near-check": dict(CHECK, statement="n")}},
    ]
    root, made, env = _chain_project(tmp_path, docs)
    code, out, err = _effective(root, env, "--json")
    assert code == 0, err
    view = json.loads(out)
    labels = [_label(sha, repo) for repo, sha in made]
    assert [layer["name"] for layer in view["layers"]] == ["default", *labels, "project"]
    rows = {row["path"]: row for row in view["fields"]}
    assert rows["owner"]["value"] == "near-team"
    assert rows["owner"]["source"] == labels[2] and rows["owner"]["op"] == "set"
    assert rows["checks.far-check.statement"]["source"] == labels[0]
    assert rows["checks.near-check.statement"]["source"] == labels[2]


# --- PC-6: versions.yml records every parent in order ---------------------------------------------

def test_pc_6_versions_yml_lists_the_default_and_every_git_parent_furthest_first(
        tmp_path, monkeypatch):
    base = tmp_path / "remotes"
    made = _build(base, [PLAIN, PLAIN, PLAIN])
    repo, sha = made[-1]
    root, task_dir = issue_project(tmp_path, _ref(sha, repo))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    stored = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                            .read_text(encoding="utf-8"))
    assert [p["source"] for p in stored["parents"]] == ["shipped", "git", "git", "git"]
    assert [p["sha"] for p in stored["parents"][1:]] == [s for _, s in made]
    assert [p["ref"] for p in stored["parents"][1:]] == [
        f"github:acme/{r}@1.0.0" for r, _ in made]
    assert all(p["digest"].startswith("sha256:") for p in stored["parents"])


# --- PC-7: readers do not fetch an ancestor ------------------------------------------------------

def _chain_with_far_parent_missing(tmp_path):
    root, made, env = _chain_project(tmp_path, [PLAIN, PLAIN])
    code, _, err = _lint(root, env=env)
    assert code == 0, err
    shutil.rmtree(_cache(root) / made[0][1])
    return root, made


@pytest.mark.parametrize("how", ["flag", "env"])
def test_pc_7_an_offline_run_names_the_parent_that_needs_the_missing_ancestor(tmp_path, how):
    root, made = _chain_with_far_parent_missing(tmp_path)
    bin_dir, log = fake_git(tmp_path)
    env = {"PATH": f"{bin_dir}:{REAL_GIT}"}
    if how == "env":
        env["COMPASS_OFFLINE"] = "1"
    code, report, _ = _lint(root, *(("--offline",) if how == "flag" else ()), env=env)
    assert code == 1
    assert _codes(report) == ["L-PARENT-NOT-CACHED"], report
    assert report["findings"][0]["layer"] == _label(made[1][1], "p2")
    assert made[0][1] in report["findings"][0]["message"]
    assert not log.exists(), "git ran offline"


def test_pc_7_a_reader_of_an_issue_never_fetches_an_ancestor(tmp_path):
    base = tmp_path / "remotes"
    made = _build(base, [PLAIN, PLAIN])
    repo, sha = made[-1]
    root, task_dir = issue_project(tmp_path, _ref(sha, repo))
    code, report, err = _lint(root, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (report, err)
    shutil.rmtree(_cache(root) / made[0][1])
    bin_dir, log = fake_git(tmp_path)
    code, out, err = _run(root, "check", "--issue", "feature",
                          env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code != 0 and "L-PARENT-NOT-CACHED" in out + err
    assert not log.exists(), "compass check ran git"


# --- PC-8: the docs ----------------------------------------------------------------------------

def _text(*parts):
    return ROOT.joinpath(*parts).read_text(encoding="utf-8")


def test_pc_8_the_cycle_code_is_a_code_the_lint_can_name():
    from compass_pkg import policy_lint
    assert "L-PARENT-CYCLE" in policy_lint.FINDING_CODES


def test_pc_8_the_owning_docs_describe_the_chain_the_depth_and_the_cycle_code():
    doc = _text("docs", "git-parents.md")
    for phrase in ("L-PARENT-CYCLE", "depth of three", "furthest", "not counted"):
        assert phrase in doc, f"docs/git-parents.md does not mention {phrase!r}"
    assert "chains are not built yet" not in doc.lower()
    assert "Chains of git parents and the depth limit" not in doc
    lint = _text("docs", "policy-lint.md")
    assert "L-PARENT-CYCLE" in lint
    assert "Chains are not built yet" not in lint
    assert "the eleven `L-PARENT-*` codes" in lint
