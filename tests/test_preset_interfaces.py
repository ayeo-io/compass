"""The interfaces a later team-layer release relies on (issue `preset-interfaces`).

Four interfaces: fixture groups in `compass policy test`, the classification of
a git parent chain against the shipped default stored in `versions.yml`, a git
parent as an argument of `compass policy diff`, and the map form of `extends:`
with the reserved `preset:` key. These tests run the CLI in a temporary folder
and, for a git parent, point `COMPASS_PARENT_REMOTE_BASE` at a local
repository, so nothing reaches the network.

Scenario ids: `PI-1` to `PI-6`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import REAL_GIT, fake_git, make_remote  # noqa: E402,F401
from test_policy_test import (GOOD, PRESET, _fixture, _json, _preset, _run,  # noqa: E402
                              _test)

GOLDEN = ROOT / "tests" / "fixtures" / "preset-interfaces"


def _group(preset, group, fixtures):
    """Write `fixtures` (a name mapped to a mapping or text) into the folder
    `compass-fixtures/<group>/` of `preset`."""
    folder = Path(preset) / "compass-fixtures" / group
    folder.mkdir(parents=True, exist_ok=True)
    for name, body in fixtures.items():
        text = body if isinstance(body, str) else yaml.safe_dump(body)
        (folder / f"{name}.yml").write_text(text, encoding="utf-8")
    return folder


def _grouped(tmp_path):
    """The preset the golden report was made from: one ungrouped fixture and
    two groups, one of them with a failing fixture."""
    preset = _preset(tmp_path, fixtures={"a-top": GOOD})
    _group(preset, "meets/banking", {"one": GOOD, "two": _fixture({"approach": "full"})})
    _group(preset, "meets/health", {"one": GOOD})
    return preset


# --- PI-1: a folder inside compass-fixtures/ is a group ----------------------------------------

def test_pi_1_a_fixture_in_a_folder_carries_the_folder_as_its_group(tmp_path):
    code, report = _json(tmp_path, _grouped(tmp_path))
    assert code == 1
    assert [(f["file"], f["group"]) for f in report["fixtures"]] == [
        ("a-top.yml", None), ("one.yml", "meets/banking"), ("two.yml", "meets/banking"),
        ("one.yml", "meets/health")]
    assert report["problems"] == []
    assert report["totals"] == {"fixtures": 4, "passed": 3, "failed": 1}


def test_pi_1_the_text_report_shows_the_path_of_a_grouped_fixture(tmp_path):
    _, out, _ = _test(tmp_path, _grouped(tmp_path))
    assert "(compass-fixtures/meets/banking/two.yml)" in out
    assert "(compass-fixtures/a-top.yml)" in out


def test_pi_1_the_report_counts_each_group(tmp_path):
    _, report = _json(tmp_path, _grouped(tmp_path))
    assert report["groups"] == [
        {"group": "meets/banking", "fixtures": 2, "passed": 1, "failed": 1, "result": "fail"},
        {"group": "meets/health", "fixtures": 1, "passed": 1, "failed": 0, "result": "pass"}]


def test_pi_1_a_preset_without_groups_reports_an_empty_list(tmp_path):
    code, report = _json(tmp_path, _preset(tmp_path))
    assert code == 0
    assert report["groups"] == []
    assert report["fixtures"][0]["group"] is None


def test_pi_1_a_folder_that_holds_fixtures_and_folders_is_a_group_of_its_own(tmp_path):
    preset = _preset(tmp_path, fixtures={"a-top": GOOD})
    _group(preset, "meets", {"x": GOOD})
    _group(preset, "meets/banking", {"y": GOOD})
    code, report = _json(tmp_path, preset)
    assert code == 0, report["problems"]
    assert [g["group"] for g in report["groups"]] == ["meets", "meets/banking"]


def test_pi_1_a_run_with_every_group_passing_exits_zero(tmp_path):
    preset = _preset(tmp_path)
    _group(preset, "meets/banking", {"one": GOOD})
    code, out, err = _test(tmp_path, preset)
    assert code == 0, (out, err)
    assert "meets/banking" in out


def test_pi_1_a_failing_fixture_in_a_group_fails_the_run_and_names_the_group(tmp_path):
    code, out, _ = _test(tmp_path, _grouped(tmp_path))
    assert code == 1
    assert "group meets/banking: 2 run, 1 passed, 1 failed" in out
    assert "group meets/health: 1 run, 1 passed, 0 failed" in out


def test_pi_1_a_group_folder_with_nothing_in_it_is_a_problem(tmp_path):
    preset = _preset(tmp_path)
    (preset / "compass-fixtures" / "meets" / "empty").mkdir(parents=True)
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert any("compass-fixtures/meets/empty" in p and "no fixture" in p
               for p in report["problems"]), report["problems"]


def test_pi_1_a_yaml_file_in_a_group_is_a_problem_as_it_is_at_the_top(tmp_path):
    preset = _preset(tmp_path)
    folder = _group(preset, "meets/banking", {"one": GOOD})
    (folder / "two.yaml").write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert any("meets/banking/two.yaml" in p for p in report["problems"]), report["problems"]


def test_pi_1_a_hidden_folder_is_ignored(tmp_path):
    preset = _preset(tmp_path)
    hidden = preset / "compass-fixtures" / ".cache"
    hidden.mkdir()
    (hidden / "x.yml").write_text("not: a fixture", encoding="utf-8")
    code, report = _json(tmp_path, preset)
    assert code == 0, report["problems"]
    assert report["groups"] == []


def test_pi_1_a_linked_folder_is_not_followed(tmp_path):
    preset = _preset(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "x.yml").write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    (preset / "compass-fixtures" / "linked").symlink_to(outside, target_is_directory=True)
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert any("linked" in p and "link" in p for p in report["problems"]), report["problems"]
    assert report["totals"]["fixtures"] == 1


def test_pi_1_a_malformed_fixture_in_a_group_is_an_error_in_that_group(tmp_path):
    preset = _preset(tmp_path)
    _group(preset, "meets/banking", {"bad": "assessment: 1\n"})
    _, report = _json(tmp_path, preset)
    assert report["fixtures"][-1]["status"] == "error"
    assert report["groups"] == [{"group": "meets/banking", "fixtures": 1, "passed": 0,
                                 "failed": 1, "result": "fail"}]


def test_pi_1_a_lint_failure_runs_no_group_and_lists_none(tmp_path):
    preset = _preset(tmp_path, {**PRESET, "autonomy": "balanced"})
    _group(preset, "meets/banking", {"one": GOOD})
    _, report = _json(tmp_path, preset)
    assert report["fixtures_run"] is False
    assert report["groups"] == []


# --- PI-2: the key order is pinned by a fixture ------------------------------------------------

def test_pi_2_the_json_report_with_groups_equals_the_pinned_fixture(tmp_path):
    _, out, _ = _run(tmp_path, "preset", "test", str(_grouped(tmp_path)), "--json")
    golden = json.loads((GOLDEN / "policy-test-groups.json").read_text(encoding="utf-8"))
    assert json.dumps(json.loads(out), indent=1) == json.dumps(golden, indent=1)


def test_pi_2_groups_come_last_at_the_top_and_group_comes_last_on_a_fixture(tmp_path):
    _, report = _json(tmp_path, _grouped(tmp_path))
    assert list(report) == ["schema", "preset", "result", "lint", "fixtures_run", "totals",
                            "fixtures", "problems", "groups"]
    assert list(report["fixtures"][0]) == ["file", "name", "status", "mismatches", "message",
                                           "group"]
    assert list(report["groups"][0]) == ["group", "fixtures", "passed", "failed",
                                           "result"]


# --- PI-3: the chain is classified against the shipped default and stored ---------------------

def _ref(sha, owner="acme", repo="bank", ref="1.2.0"):
    return f"github:{owner}/{repo}@{ref}#{sha}"


LOOSENS = {"approaches": {"regular": {
    "set": {"stages": {"set": {"define": "light"}}},
    "waiver": {"reason": "This team defines in the ticket.", "approved_by": "acme-team",
               "approved_on": "2026-10-05"}}}}
TIGHTENS = {"approaches": {"quick-fix": {"set": {"gates": {"add": ["verify.clarity"]}}}}}
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
    assert found["against"] == "compass:default@6"
    assert found["points"] > 0 and found["raw_points"] >= found["points"]
    assert found["complete"] is True
    assert found["first_looser"]["assessment"]
    assert "define" in found["first_looser"]["summary"]


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


# --- PI-4: a git parent is an argument of policy diff ------------------------------------------

def _diff_project(tmp_path):
    root = tmp_path / "project"
    (root / ".compass").mkdir(parents=True)
    (root / "compass.yml").write_text(yaml.safe_dump({"schema": 1}), encoding="utf-8")
    return root


def _remote(tmp_path, doc, repo="bank", owner="acme"):
    base = tmp_path / "remotes"
    sha = make_remote(base, owner=owner, repo=repo, files={"compass.yml": yaml.safe_dump(doc)})
    return base, sha


def _diff(root, *argv, env=None):
    code, out, err = _run(root, "policy", "diff", *argv, "--json", env=env)
    return code, (json.loads(out) if out.strip().startswith("{") else None), out, err


def test_pi_4_a_git_parent_is_compared_with_the_shipped_default(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    root = _diff_project(tmp_path)
    ref = _ref(sha)
    code, doc, out, err = _diff(root, "default@6", ref, env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (out, err)
    assert doc["a"]["ref"] == "default@6"
    assert doc["b"]["ref"] == ref
    assert doc["b"]["kind"] == "parent"
    assert doc["classification"]["result"] == "tightening"
    assert doc["differs"] is True
    assert (root / ".compass" / "cache" / "parents" / "acme" / "bank" / sha
            / "compass.yml").is_file()


def test_pi_4_a_loosening_parent_is_shown_not_refused(tmp_path):
    base, sha = _remote(tmp_path, _parent(LOOSENS))
    code, doc, out, err = _diff(_diff_project(tmp_path), "default@6", _ref(sha),
                                env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (out, err)
    assert doc["classification"]["result"] == "loosening"


def test_pi_4_one_argument_compares_the_project_with_the_parent(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    code, doc, out, err = _diff(_diff_project(tmp_path), _ref(sha),
                                env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (out, err)
    assert (doc["a"]["ref"], doc["b"]["kind"]) == ("project", "parent")


def test_pi_4_the_parent_may_be_the_first_argument(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    code, doc, out, err = _diff(_diff_project(tmp_path), _ref(sha), "default@6",
                                env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (out, err)
    assert doc["classification"]["result"] == "loosening"


def test_pi_4_a_parent_that_extends_another_is_read_with_its_chain(tmp_path):
    base = tmp_path / "remotes"
    far = make_remote(base, repo="far", files={"compass.yml": yaml.safe_dump(_parent(TIGHTENS))})
    near_doc = _parent({}, extends=_ref(far, repo="far"))
    near = make_remote(base, repo="near", files={"compass.yml": yaml.safe_dump(near_doc)})
    code, doc, out, err = _diff(_diff_project(tmp_path), "default@6", _ref(near, repo="near"),
                                env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (out, err)
    assert doc["classification"]["result"] == "tightening"


def test_pi_4_offline_with_the_parent_uncached_is_refused_and_runs_no_git(tmp_path):
    bin_dir, log = fake_git(tmp_path)
    root = _diff_project(tmp_path)
    code, _, out, err = _diff(root, "default@6", _ref("9" * 40), "--offline",
                              env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code == 2
    assert "L-PARENT-NOT-CACHED" in out + err
    assert not log.exists()


def test_pi_4_an_uncached_parent_is_fetched_and_one_stderr_line_says_so(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    root = _diff_project(tmp_path)
    env = {"COMPASS_PARENT_REMOTE_BASE": str(base)}
    code, _, out, err = _diff(root, "default@6", _ref(sha), env=env)
    assert code == 0, (out, err)
    lines = [line for line in err.splitlines() if line.strip()]
    assert lines == [f"compass policy diff: fetching {_ref(sha)} into .compass/cache/parents/"]
    code, _, out, err = _diff(root, "default@6", _ref(sha), env=env)
    assert code == 0 and err.strip() == "", err


def test_pi_4_offline_never_fetches_and_writes_no_cache(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    root = _diff_project(tmp_path)
    env = {"COMPASS_PARENT_REMOTE_BASE": str(base)}
    code, _, out, err = _diff(root, "default@6", _ref(sha), "--offline", env=env)
    assert code == 2 and "fetching" not in err
    assert not (root / ".compass" / "cache" / "parents").exists()
    code, _, out, err = _diff(root, "default@6", _ref(sha), env={**env, "COMPASS_OFFLINE": "1"})
    assert code == 2 and "fetching" not in err
    assert not (root / ".compass" / "cache" / "parents").exists()


def test_pi_4_a_command_line_reference_error_does_not_repeat_the_extends_prefix(tmp_path):
    code, _, out, err = _diff(_diff_project(tmp_path), "default@6", "github:acme/bank@1.2.0")
    assert code == 2
    assert "extends:" not in out + err
    assert "L-PARENT-NO-SHA" in out + err


def test_pi_4_a_parent_that_turns_a_capability_on_is_compared_with_it_on(tmp_path):
    base, sha = _remote(tmp_path, _parent(CAPABILITY_ON))
    code, doc, out, err = _diff(_diff_project(tmp_path), "default@6", _ref(sha),
                                env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, (out, err)
    assert doc["b"]["capabilities"] == ["entry-exit-evaluation"]
    assert doc["a"]["capabilities"] == []
    assert doc["classification"]["result"] == "tightening"


def test_pi_4_a_cached_parent_is_read_offline(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    root = _diff_project(tmp_path)
    env = {"COMPASS_PARENT_REMOTE_BASE": str(base)}
    assert _diff(root, "default@6", _ref(sha), env=env)[0] == 0
    code, doc, out, err = _diff(root, "default@6", _ref(sha), "--offline", env=env)
    assert code == 0, (out, err)
    assert doc["b"]["kind"] == "parent"


@pytest.mark.parametrize("bad,code_wanted", [
    ("github:acme/bank@1.2.0", "L-PARENT-NO-SHA"),
    ("github:acme/bank@1.2.0#xyz", "L-PARENT-FORM"),
])
def test_pi_4_a_bad_spelling_is_refused_with_its_lint_code(tmp_path, bad, code_wanted):
    bin_dir, log = fake_git(tmp_path)
    code, _, out, err = _diff(_diff_project(tmp_path), "default@6", bad,
                              env={"PATH": f"{bin_dir}:{REAL_GIT}"})
    assert code == 2
    assert code_wanted in out + err
    assert not log.exists()


def test_pi_4_a_parent_with_a_settings_key_is_refused_before_it_is_compared(tmp_path):
    base, sha = _remote(tmp_path, _parent({"autonomy": "balanced"}))
    code, _, out, err = _diff(_diff_project(tmp_path), "default@6", _ref(sha),
                              env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 2
    assert "autonomy" in out + err and "Traceback" not in err


def test_pi_4_the_report_names_the_parent_without_a_machine_path(tmp_path):
    base, sha = _remote(tmp_path, _parent(TIGHTENS))
    root = _diff_project(tmp_path)
    _, _, out, _ = _diff(root, "default@6", _ref(sha),
                         env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert str(tmp_path) not in out


# --- PI-5: the extends map form and the reserved preset key -----------------------------------

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


def test_pi_5_policy_test_passes_a_preset_that_carries_the_preset_key(tmp_path):
    preset = _preset(tmp_path, {**PRESET, "preset": PRESET_BLOCK})
    code, out, err = _test(tmp_path, preset)
    assert code == 0, (out, err)


def test_pi_5_the_preset_index_key_stays_a_settings_key_a_parent_may_not_carry(tmp_path):
    preset = _preset(tmp_path, {**PRESET, "preset_index": "github:acme/index"})
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert "L-SETTINGS-KEY" in [f["code"] for f in report["lint"]["findings"]]


def test_pi_5_two_files_that_differ_only_in_the_preset_block_do_not_differ(tmp_path):
    root = _diff_project(tmp_path)
    (root / "a.yml").write_text(yaml.safe_dump({"schema": 1}), encoding="utf-8")
    (root / "b.yml").write_text(yaml.safe_dump({"schema": 1, "preset": PRESET_BLOCK}),
                                encoding="utf-8")
    code, doc, out, err = _diff(root, "a.yml", "b.yml")
    assert code == 0, (out, err)
    assert doc["differs"] is False
    assert doc["a"]["digest"] == doc["b"]["digest"]


# --- PI-6: the owning docs, help and contract corpus state the interfaces ----------------------

def _doc(*parts):
    return " ".join((ROOT.joinpath(*parts)).read_text(encoding="utf-8").split())


def test_pi_6_policy_test_doc_states_groups_the_group_key_and_the_counts():
    text = _doc("docs", "policy-test.md")
    for needle in ("`groups`", "`group`", "compass-fixtures/meets/banking/", "does not follow",
                   "tests/fixtures/preset-interfaces/policy-test-groups.json"):
        assert needle in text, needle
    assert "are not read yet" not in text
    assert "A later release reads fixtures in folders" not in text


def test_pi_6_policy_diff_doc_lists_the_git_parent_reference_and_its_kind():
    text = _doc("docs", "policy-diff.md")
    for needle in ("github:<owner>/<repo>@<ref>#<sha>", "`parent`", "--offline"):
        assert needle in text, needle


def test_pi_6_git_parents_doc_states_the_stored_classification_and_the_map_form():
    text = _doc("docs", "git-parents.md")
    for needle in ("classification", "before any waiver", "`first_looser`", "`raw_points`",
                   "approved_by", "`preset`", "classify_chain"):
        assert needle in text, needle


def test_pi_6_generation_store_doc_names_the_classification_in_versions_yml():
    assert "and the `classification` of the chain through it" in _doc("docs",
                                                                       "generation-store.md")


def test_pi_6_the_new_module_has_an_owning_doc_row():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    row = next(line for line in readme.splitlines() if "chain_class.py" in line)
    assert row.rstrip().endswith("`docs/git-parents.md` |")


def test_pi_6_help_says_a_folder_is_a_group_and_diff_takes_a_git_parent():
    source = (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text(encoding="utf-8")
    assert "A folder inside compass-fixtures/ is a fixture group" in source
    assert "github:<owner>/<repo>@<ref>#<sha>" in source
    code, out, _ = _run(ROOT, "policy", "diff", "--help")
    assert code == 0 and "github:<owner>/<repo>@<ref>#<sha>" in " ".join(out.split())


CORPUS = ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml"


def test_pi_6_the_contract_corpus_holds_a_grouped_test_and_a_git_parent_diff_with_reasons():
    text = CORPUS.read_text(encoding="utf-8")
    entries = {e["id"]: e for e in yaml.safe_load(text)["entries"]}
    assert "policy-diff-git-parent-offline-uncached" not in entries, "5.6.0 also exited 2"
    for entry_id in ("policy-test-groups",):
        assert entry_id in entries, entry_id
        line = text.index(f"- id: {entry_id}\n")
        before = text[:line].rstrip("\n").splitlines()
        assert before[-1].startswith("#") or any(
            "Added on purpose by preset-interfaces" in b for b in before[-4:]), entry_id


# --- review round: links, group names, capabilities, the date, the cost ------------------------

def _link_cases(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.yml").write_text("SECRET-CONTENT: 1\n", encoding="utf-8")
    (outside / "folder").mkdir()
    (outside / "folder" / "x.yml").write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    return outside


@pytest.mark.parametrize("where", ["", "meets"])
@pytest.mark.parametrize("kind", ["file", "folder", "broken", "file-not-yml"])
def test_pi_1_every_link_is_a_problem_and_nothing_outside_is_read_or_printed(
        tmp_path, where, kind):
    preset = _preset(tmp_path)
    folder = _group(preset, "meets", {"one": GOOD}) if where else preset / "compass-fixtures"
    outside = _link_cases(tmp_path)
    target = {"file": outside / "secret.yml", "folder": outside / "folder",
              "broken": outside / "nowhere.yml", "file-not-yml": outside / "secret.yml"}[kind]
    name = "linked.txt" if kind == "file-not-yml" else "linked.yml" if kind != "folder" \
        else "linked"
    (folder / name).symlink_to(target, target_is_directory=kind == "folder")
    code, out, err = _run(tmp_path, "preset", "test", str(preset), "--json")
    report = json.loads(out)
    assert code == 1, out
    shown = f"compass-fixtures/{where + '/' if where else ''}{name}"
    assert any(shown in p and "link" in p for p in report["problems"]), report["problems"]
    assert "SECRET-CONTENT" not in out + err and "outside" not in out
    assert all(f["name"] != "x" for f in report["fixtures"])
    assert report["totals"]["fixtures"] == (2 if where else 1)


@pytest.mark.parametrize("name", ["Banking", "bank_ing", "-bank", "bank ing", "ba.nk"])
def test_pi_1_a_group_folder_with_a_bad_name_is_a_problem_and_is_not_read(tmp_path, name):
    preset = _preset(tmp_path)
    _group(preset, name, {"one": GOOD})
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert any(name in p and "lower-case" in p for p in report["problems"]), report["problems"]
    assert report["groups"] == [] and report["totals"]["fixtures"] == 1


def test_pi_1_a_group_may_be_three_folders_deep_and_no_more(tmp_path):
    preset = _preset(tmp_path)
    _group(preset, "a/b/c", {"one": GOOD})
    code, report = _json(tmp_path, preset)
    assert code == 0, report["problems"]
    assert [g["group"] for g in report["groups"]] == ["a/b/c"]
    _group(preset, "a/b/c/d", {"two": GOOD})
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert any("a/b/c/d" in p and "3 folders deep" in p for p in report["problems"])
    assert report["totals"]["fixtures"] == 2


def test_pi_1_the_wrong_spellings_are_problems_inside_a_group_too(tmp_path):
    preset = _preset(tmp_path)
    folder = _group(preset, "meets", {"one": GOOD})
    for name in ("two.YML", "three.Yml", "four.yaml", "five.YAML"):
        (folder / name).write_text(yaml.safe_dump(GOOD), encoding="utf-8")
    code, report = _json(tmp_path, preset)
    assert code == 1
    for name in ("two.YML", "three.Yml", "four.yaml", "five.YAML"):
        assert any(f"compass-fixtures/meets/{name}" in p for p in report["problems"]), name
    assert report["totals"]["fixtures"] == 2


def test_pi_1_each_group_has_a_pass_or_fail_result(tmp_path):
    _, report = _json(tmp_path, _grouped(tmp_path))
    assert {g["group"]: g["result"] for g in report["groups"]} == {
        "meets/banking": "fail", "meets/health": "pass"}


def test_pi_1_a_message_over_several_lines_stays_indented_beside_the_group_lines(tmp_path):
    preset = _preset(tmp_path)
    _group(preset, "meets", {"bad": "a: 1\n b: [\n"})
    _, out, _ = _test(tmp_path, preset)
    assert "group meets: 1 run, 0 passed, 1 failed" in out
    assert "Traceback" not in out


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


def test_pi_6_the_docs_state_the_fetch_of_diff_the_form_code_the_cost_and_the_deferral():
    git = _doc("docs", "git-parents.md")
    assert "`compass policy diff`" in git.split("## When Compass fetches")[1].split("##")[0]
    assert "`from` that is not text is `L-PARENT-FORM`" in git
    assert "about 0.6 seconds" in git
    assert "`preset.version`" in git and "not read yet" in git
    assert "`approved_by` and `approved_on` are read from the project's own `compass.yml`" in git
    assert "It writes nothing" not in _doc("docs", "policy-diff.md")
    assert "writes nothing" not in _doc("docs", "policy-diff.md").split("## Options")[1][:400]
    assert "`compass policy diff`" in _doc("docs", "security.md")
    source = (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text(encoding="utf-8")
    line = next(l for l in source.splitlines() if l.strip().startswith('"Compare two conf'))
    assert "It writes nothing" not in line and "cache" in line


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


# ---- fix round: adoption with a git parent -------------------------------------

def _leftover_generation_two(tmp_path, monkeypatch):
    """A project with a git parent, generation 1 committed and a second commit
    stopped after its marker, so generation 2 is complete and unreferenced.
    Returns `(root, task_dir, manifest to adopt with)`."""
    from compass_pkg import effective, generation
    from parent_fixtures import OUTCOME, commit, issue_project
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(_parent(TIGHTENS))})
    root, task_dir = issue_project(tmp_path, _ref(sha))
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    assert commit(task_dir).committed
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    manifest.update(OUTCOME)
    # An overlay, so that generation 2 holds a different configuration from 1.
    manifest["config"] = {"checks": {"extra": {
        "statement": "A check.", "kind": "deterministic", "impl": "suite-passed",
        "severity": "advisory", "on_skipped": "fail"}}}

    class Stop(Exception):
        pass

    def stop(step):
        if step == "marker":
            raise Stop()

    monkeypatch.setattr(generation, "_after_step", stop)
    with pytest.raises(Stop):
        effective.commit_generation(str(task_dir), manifest)
    monkeypatch.undo()
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(base))
    monkeypatch.chdir(root)
    return root, task_dir, manifest


def test_pi_3_a_leftover_generation_is_adopted_when_the_project_has_a_git_parent(
        tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir, manifest = _leftover_generation_two(tmp_path, monkeypatch)
    resolution = effective.resolve_live(str(root), manifest, "feature", str(task_dir))
    effective.preflight(str(task_dir), resolution, manifest, None, 2)
    done = effective.commit_generation(str(task_dir), manifest, adopt=2)
    assert done.committed and done.number == 2
    assert "adopted generation 2" in done.message


def test_pi_3_adoption_still_refuses_a_leftover_whose_versions_differ(tmp_path, monkeypatch):
    from compass_pkg import effective, generation
    from compass_pkg.core import CompassError
    root, task_dir, manifest = _leftover_generation_two(tmp_path, monkeypatch)
    versions = task_dir / "generations" / "2" / "versions.yml"
    doc = yaml.safe_load(versions.read_text(encoding="utf-8"))
    doc["parents"][1]["classification"]["result"] = "loosening"
    versions.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    # Keep the marker whole, so only the comparison with a fresh resolution can refuse.
    marker = task_dir / "generations" / "2" / generation.MARKER
    held = yaml.safe_load(marker.read_text(encoding="utf-8"))
    held["files"]["versions.yml"] = generation.digest({"schema": generation.SCHEMA, **{
        k: v for k, v in doc.items() if k != "schema"}})
    marker.write_text(yaml.safe_dump(held, sort_keys=False), encoding="utf-8")
    resolution = effective.resolve_live(str(root), manifest, "feature", str(task_dir))
    with pytest.raises(CompassError, match="versions.yml no longer match"):
        effective.preflight(str(task_dir), resolution, manifest, None, 2)


def test_pi_1_a_group_folder_holding_only_a_file_that_is_not_a_fixture_is_a_problem(tmp_path):
    preset = _preset(tmp_path)
    folder = preset / "compass-fixtures" / "meets" / "notes"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text("Notes, not a fixture.\n", encoding="utf-8")
    code, report = _json(tmp_path, preset)
    assert code == 1
    assert any("compass-fixtures/meets/notes" in p and "no fixture" in p
               for p in report["problems"]), report["problems"]
    assert all(g["group"] != "meets/notes" for g in report["groups"])


def test_pi_6_policy_diff_docs_and_help_name_both_files_it_writes_in_the_cache_area():
    diff = " ".join(_doc("docs", "policy-diff.md").split())
    git = " ".join(_doc("docs", "git-parents.md").split())
    source = (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text(encoding="utf-8")
    line = next(l for l in source.splitlines() if l.strip().startswith('"Compare two conf'))
    assert ".compass/.gitignore" in diff
    assert "This is the only file `policy diff` writes" not in git
    assert "`.compass/.gitignore`" in git.split("`compass policy diff`, when a reference")[1][:500]
    assert ".compass/.gitignore" in line


def test_pi_6_the_policy_test_doc_does_not_say_a_group_has_any_depth():
    text = " ".join(_doc("docs", "policy-test.md").split())
    assert "at any depth" not in text
    assert "at most 3 folders deep" in text
