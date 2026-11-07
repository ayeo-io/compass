"""Two interfaces a team layer relies on, kept after 9.0.0 removed the preset verbs.

The classification of a git parent chain against the shipped default, stored in
`versions.yml` (PI-3), and the map form of `extends:` with the reserved
`preset:` key (PI-5). `compass preset test` and `compass policy diff`, which
PI-1, PI-2 and PI-4 covered, were removed in 9.0.0 (ADR-094). These tests run
the CLI in a temporary folder and, for a git parent, point
`COMPASS_PARENT_REMOTE_BASE` at a local repository, so nothing reaches the
network.

Scenario ids: `PI-3`, `PI-5` and `PI-6`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import REAL_GIT, make_remote  # noqa: E402


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


def _ref(sha, owner="acme", repo="bank", ref="1.2.0"):
    return f"github:{owner}/{repo}@{ref}#{sha}"


LOOSENS = {"gates": {"verify.architecture": {
    "set": {"accepts": {"add": ["manual-review"]}},
    "waiver": {"reason": "This team reviews architecture in pairing.",
               "approved_by": "acme-team", "approved_on": "2026-10-05"}}}}


TIGHTENS = {"rules": {"team_floors": {
    "kind": "floors", "hit": {"add_gate": "collect"},
    "rules": {"TEAM-001": {"order": 1, "when": {"risk": "trivial"},
                           "then": {"add_gate": "verify.clarity"},
                           "rationale": "This team reviews clarity on trivial changes."}}}}}


CAPABILITY_ON = {"capabilities": {"entry-exit-evaluation": True}}


def _parent(doc, **over):
    return {"schema": 1, "owner": "acme-team", **doc, **over}


def _commit_stored(tmp_path, monkeypatch, docs):
    """Commit a generation for a project that extends a chain of parents.
    `docs` runs from the nearest parent to the furthest; each document but the
    last extends the next. Returns the stored `versions.yml`."""
    from parent_fixtures import commit, issue_project
    base = tmp_path / "remotes"
    shas, extends = [], None
    for index, doc in reversed(list(enumerate(docs))):
        doc = dict(doc)
        if extends:
            doc["extends"] = extends
        sha = make_remote(base, repo=f"repo{index}", files={"compass.yml": yaml.safe_dump(doc)})
        extends = _ref(sha, repo=f"repo{index}")
        shas.append(sha)
    root, task_dir = issue_project(tmp_path, extends)
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    return yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                          .read_text(encoding="utf-8"))


def test_pi_3_a_loosening_parent_is_stored_as_loosening_though_its_waiver_excuses_it(
        tmp_path, monkeypatch):
    stored = _commit_stored(tmp_path, monkeypatch, [_parent(LOOSENS)])
    found = stored["parents"][1]["classification"]
    assert found["result"] == "loosening"
    assert found["against"] == "compass:default@8"
    assert found["points"] > 0 and found["raw_points"] >= found["points"]
    assert found["complete"] is True
    assert found["first_looser"]["assessment"]
    assert "verify.architecture" in found["first_looser"]["summary"]


def test_pi_3_a_tightening_parent_is_stored_as_tightening_with_no_looser_point(
        tmp_path, monkeypatch):
    stored = _commit_stored(tmp_path, monkeypatch, [_parent(TIGHTENS)])
    found = stored["parents"][1]["classification"]
    assert found["result"] == "tightening"
    assert found["first_looser"] is None


def test_pi_3_the_stored_block_has_the_pinned_keys_in_order(tmp_path, monkeypatch):
    stored = _commit_stored(tmp_path, monkeypatch, [_parent(TIGHTENS)])
    assert list(stored["parents"][1]) == ["ref", "sha", "version", "digest", "source",
                                          "classification"]
    assert list(stored["parents"][1]["classification"]) == [
        "against", "result", "points", "raw_points", "complete", "first_looser"]


def test_pi_3_each_parent_of_a_chain_holds_the_classification_of_the_chain_through_it(
        tmp_path, monkeypatch):
    # The furthest parent tightens; the nearest loosens a stage on top of it.
    stored = _commit_stored(tmp_path, monkeypatch, [_parent(LOOSENS), _parent(TIGHTENS)])
    far, near = stored["parents"][1], stored["parents"][2]
    assert [p["source"] for p in stored["parents"]] == ["shipped", "git", "git"]
    assert far["classification"]["result"] == "tightening"
    assert near["classification"]["result"] == "incomparable"
    assert near["classification"]["first_looser"] is not None


def test_pi_3_the_shipped_default_has_no_classification_and_a_project_without_a_parent_none(
        tmp_path, monkeypatch):
    from parent_fixtures import commit, issue_project
    root, task_dir = issue_project(tmp_path, "compass:default@6")
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    stored = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                            .read_text(encoding="utf-8"))
    assert all("classification" not in p for p in stored["parents"])


def test_pi_3_reading_the_live_configuration_does_not_run_the_classifier(
        tmp_path, monkeypatch):
    from compass_pkg import classify, effective
    from parent_fixtures import issue_project
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(_parent(TIGHTENS))})
    root, task_dir = issue_project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)

    def refuse(*args, **kwargs):
        raise AssertionError("the classifier ran for a read")
    monkeypatch.setattr(classify, "classify", refuse)
    resolution = effective.resolve_live(root, fetch=True)
    assert "classification" not in resolution.versions["parents"][1]


def _diff_project(tmp_path):
    root = tmp_path / "project"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text(yaml.safe_dump({"schema": 1}), encoding="utf-8")
    return root


def _remote(tmp_path, doc, repo="bank", owner="acme"):
    base = tmp_path / "remotes"
    sha = make_remote(base, owner=owner, repo=repo, files={"compass.yml": yaml.safe_dump(doc)})
    return base, sha


def _lint_file(root, doc, *extra, env=None):
    path = root / "compass.yml"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    code, out, err = _run(root, "policy", "lint", "--json", *extra, env=env)
    return code, json.loads(out), err


def _codes(report):
    return [f["code"] for f in report["findings"]]


def _effective_layers(root, env=None):
    code, out, err = _run(root, "policy", "show", "--json", env=env)
    assert code == 0, (out, err)
    return json.loads(out)["layers"]


MAP = {"approved_by": "acme-team", "approved_on": "2026-10-08"}


def test_pi_5_the_map_form_of_a_shipped_extends_reads_without_error(tmp_path):
    root = _diff_project(tmp_path)
    code, report, err = _lint_file(root, {"schema": 1, "extends": {
        "from": "compass:default@6", **MAP}})
    assert code == 0, (report, err)
    assert _codes(report) == []


def test_pi_5_the_map_form_of_a_git_extends_resolves_the_parent(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    root = _diff_project(tmp_path)
    env = {"COMPASS_PARENT_REMOTE_BASE": str(base)}
    doc = {"schema": 1, "extends": {"from": _ref(sha), **MAP}}
    code, report, err = _lint_file(root, doc, env=env)
    assert code == 0, (report, err)
    names = [layer["name"] for layer in _effective_layers(root, env)]
    assert len(names) == 3 and names[0] == "default" and names[-1] == "project"


def test_pi_5_the_map_form_and_the_string_form_give_the_same_parent_layer(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    root = _diff_project(tmp_path)
    env = {"COMPASS_PARENT_REMOTE_BASE": str(base)}
    _lint_file(root, {"schema": 1, "extends": _ref(sha)}, env=env)
    as_string = _effective_layers(root, env)
    _lint_file(root, {"schema": 1, "extends": {"from": _ref(sha), **MAP}}, env=env)
    as_map = _effective_layers(root, env)
    # The project layer differs because its own `extends:` key is part of its
    # digest; the git parent below it is the same layer.
    assert as_map[:2] == as_string[:2]
    assert as_map[2]["digest"] != as_string[2]["digest"]


def test_pi_5_a_git_parent_may_extend_in_the_map_form(tmp_path):
    base = tmp_path / "remotes"
    far = make_remote(base, repo="far", files={"compass.yml": yaml.safe_dump(_parent(TIGHTENS))})
    near_doc = _parent({}, extends={"from": _ref(far, repo="far"), **MAP})
    near = make_remote(base, repo="near", files={"compass.yml": yaml.safe_dump(near_doc)})
    root = _diff_project(tmp_path)
    code, report, err = _lint_file(root, {"schema": 1, "extends": _ref(near, repo="near")},
                                   env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (report, err)


@pytest.mark.parametrize("extends", [
    {"approved_by": "acme-team"},
    {"from": "compass:default@6", "colour": "red"},
    {"from": "compass:default@6", "approved_by": ["a"]},
])
def test_pi_5_a_malformed_map_is_a_schema_finding(tmp_path, extends):
    code, report, _ = _lint_file(_diff_project(tmp_path), {"schema": 1, "extends": extends})
    assert code == 1
    assert "L-SCHEMA" in _codes(report)


def test_pi_5_a_bad_spelling_inside_the_map_has_the_same_code_as_the_string(tmp_path):
    code, report, _ = _lint_file(_diff_project(tmp_path), {
        "schema": 1, "extends": {"from": "github:acme/bank@1.2.0", **MAP}})
    assert code == 1
    assert "L-PARENT-NO-SHA" in _codes(report)


def test_pi_5_a_from_that_is_not_text_has_the_form_code_of_the_string(tmp_path):
    code, report, _ = _lint_file(_diff_project(tmp_path), {
        "schema": 1, "extends": {"from": 6}})
    assert code == 1
    assert "L-PARENT-FORM" in _codes(report)


PRESET_BLOCK = {"name": "banking", "description": "For banks.", "version": "1.0.0",
                "anything": {"nested": [1, 2]}}


def test_pi_5_the_preset_key_reads_without_error_in_a_project(tmp_path):
    code, report, err = _lint_file(_diff_project(tmp_path), {"schema": 1, "preset": PRESET_BLOCK})
    assert code == 0, (report, err)
    assert _codes(report) == []


def test_pi_5_a_change_of_the_preset_block_does_not_change_the_layer_digest(tmp_path):
    root = _diff_project(tmp_path)
    _lint_file(root, {"schema": 1, "preset": PRESET_BLOCK})
    first = _effective_layers(root)
    _lint_file(root, {"schema": 1, "preset": {"description": "changed"}})
    second = _effective_layers(root)
    _lint_file(root, {"schema": 1})
    bare = _effective_layers(root)
    assert first == second == bare


def test_pi_5_the_preset_block_of_a_git_parent_does_not_change_its_digest(
        tmp_path, monkeypatch):
    def parent_digest(sub, block):
        folder = tmp_path / sub
        folder.mkdir()
        doc = _parent(TIGHTENS)
        if block is not None:
            doc["preset"] = block
        stored = _commit_stored(folder, monkeypatch, [doc])
        return stored["parents"][1]["digest"]
    assert parent_digest("a", PRESET_BLOCK) == parent_digest("b", None)


def test_pi_5_the_preset_key_must_be_a_mapping(tmp_path):
    code, report, _ = _lint_file(_diff_project(tmp_path), {"schema": 1, "preset": "banking"})
    assert code == 1
    assert "L-SCHEMA" in _codes(report)


def test_pi_3_a_parent_that_turns_a_capability_on_is_classified_with_it_on(
        tmp_path, monkeypatch):
    stored = _commit_stored(tmp_path, monkeypatch, [_parent(CAPABILITY_ON)])
    assert stored["parents"][1]["classification"]["result"] == "tightening"


def test_pi_3_more_than_eight_named_labels_give_an_incomplete_incomparable_block():
    # A commit refuses such a chain at the lint (it cannot prove the locks), so the
    # function is called directly: the block must still say the grid was not run.
    from compass_pkg import chain_class, layers, policy_lint
    shipped, _ = policy_lint.load_parent()
    names = [f"label{i}" for i in range(6)]
    doc = _parent({"rules": {"mine": {"kind": "floors", "hit": {"force_minimum_approach": "max"},
                                      "rules": {"R1": {
                                          "order": 1, "when": {"labels_any": names},
                                          "then": {"force_minimum_approach": "full"}}}}}})
    layer = layers.Layer("p", "parent", doc, layers.layer_digest(doc, "parent"))
    found = chain_class.classify_chain(shipped, [layer], "compass:default@6")[0]
    assert found["complete"] is False
    assert found["result"] == "incomparable"
    assert found["points"] == 0


def test_pi_3_an_unchanged_commit_does_not_run_the_classifier(tmp_path, monkeypatch):
    from compass_pkg import classify
    from parent_fixtures import commit, issue_project
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(_parent(TIGHTENS))})
    root, task_dir = issue_project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    calls = []
    real = classify.classify
    monkeypatch.setattr(classify, "classify", lambda *a, **k: calls.append(1) or real(*a, **k))
    again = commit(task_dir)
    assert again.committed is False
    assert calls == []


def test_pi_5_approved_on_must_be_a_real_date_that_is_not_in_the_future(tmp_path):
    root = _diff_project(tmp_path)
    for bad in ("yesterday", "2026-13-45", "2999-01-01"):
        code, report, _ = _lint_file(root, {"schema": 1, "extends": {
            "from": "compass:default@6", "approved_by": "acme-team", "approved_on": bad}})
        assert code == 1, bad
        assert "L-SCHEMA" in _codes(report), bad
    for good in ("2026-10-08", "2025-01-31"):
        code, report, err = _lint_file(root, {"schema": 1, "extends": {
            "from": "compass:default@6", "approved_by": "acme-team", "approved_on": good}})
        assert code == 0, (good, report, err)
    (root / "compass.yml").write_text(
        "schema: 1\nextends:\n  from: compass:default@6\n  approved_by: a\n"
        "  approved_on: 2026-10-08\n", encoding="utf-8")
    assert _run(root, "policy", "lint")[0] == 0


def test_pi_5_the_schema_marks_approved_on_as_a_date():
    schema = json.loads((ROOT / "schemas" / "compass.schema.json").read_text(encoding="utf-8"))
    option = schema["properties"]["extends"]["oneOf"][1]
    assert option["properties"]["approved_on"]["format"] == "date"


def test_pi_6_no_merge_conflict_marker_is_left_in_the_tracked_sources():
    import subprocess
    files = subprocess.run(["git", "ls-files", "cli", "docs", "schemas", "tests"], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    left = []
    for name in files:
        path = ROOT / name
        if path.suffix not in (".py", ".md", ".yml", ".json") or not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith(("<<<<<<< ", ">>>>>>>> ")) or line == "=======":
                left.append(f"{name}:{number}")
    assert left == []


# Moved from the tests of `compass policy update`, which 9.0.0 removed: the
# spelling of `extends: compass:default@<n>` is still read by
# `acceptance_strategy.pinned_below` and the resolver.

def test_up_9_extends_is_read_and_written_by_one_pair_of_functions():
    from compass_pkg import layers
    from compass_pkg.core import CompassError
    parse, write = layers.parse_extends, layers.default_extends
    assert parse("compass:default@6") == ("default", 6)
    assert write(7) == "compass:default@7"
    assert parse(write(12)) == ("default", 12)
    for bad in ("compass:default@6.0.0", "compass:default", "default@6", "compass:default@x",
                "github:a/b@main#abc", None, 6):
        with pytest.raises(CompassError):
            parse(bad)
