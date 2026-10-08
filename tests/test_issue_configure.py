"""`compass issue configure`: propose a change to an issue's own configuration
layer, preview what it would do, and park it until the next reassess.

Scenario ids: `CR-1` to `CR-4`, `CR-11` and `CR-12` (issue
`configure-and-reassess`). Each test name starts with its scenario id. The
reassess commit, recovery and records are in `test_generation_recovery.py`.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import configure_fixtures as fx  # noqa: E402

TIGHTER = ("--mode", "refine=full")          # refine is light in this issue's approach
LOOSER = ("--mode", "define=collapsed")      # define is light there: collapsing it loosens


def _tree(root):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))


# --- CR-1: the proposal file, and the manifest is left alone ---------------------------

def test_cr_1_a_change_writes_the_proposal_and_leaves_the_manifest_as_it_was(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    before = (task_dir / "manifest.yml").read_bytes()
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 0, out + err
    assert (task_dir / "manifest.yml").read_bytes() == before
    folder = fx.gen(task_dir, 2)
    assert sorted(p.name for p in folder.iterdir()) == ["proposed.yml"]
    proposal = fx.load(folder / "proposed.yml")
    assert list(proposal) == ["schema", "issue", "base_generation", "base_config_digest",
                              "overlay"]
    assert proposal["schema"] == 1 and proposal["issue"] == fx.SLUG
    assert proposal["base_generation"] == 1
    assert proposal["overlay"] == {"stages": {"refine": {"set": {"mode": "full"}}}}


@pytest.mark.parametrize("flags,overlay", [
    (("--route", "full"), {"approach": "full"}),
    (("--autonomy", "controlled"), {"autonomy": "controlled"}),
    (("--ceiling", "subtask_ceiling=2"), {"ceilings": {"subtask_ceiling": 2}}),
    (("--mode", "refine=full", "--mode", "define=full"),
     {"stages": {"refine": {"set": {"mode": "full"}}, "define": {"set": {"mode": "full"}}}}),
])
def test_cr_1_each_flag_builds_its_key_of_the_overlay(tmp_path, flags, overlay):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *flags)
    assert code in (0, 1), out + err
    assert fx.load(fx.gen(task_dir, 2) / "proposed.yml")["overlay"] == overlay


def test_cr_1_from_file_replaces_the_overlay_and_a_flag_adds_to_it(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, config={"autonomy": "balanced"})
    overlay = tmp_path / "overlay.yml"
    overlay.write_text("ceilings:\n  subtask_ceiling: 3\n", encoding="utf-8")
    code, out, err = fx.configure(root, "--from-file", str(overlay), "--autonomy", "controlled")
    assert code in (0, 1), out + err
    assert fx.load(fx.gen(task_dir, 2) / "proposed.yml")["overlay"] == {
        "ceilings": {"subtask_ceiling": 3}, "autonomy": "controlled"}


def test_cr_1_a_pending_proposal_is_the_base_of_the_next_call(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    assert fx.configure(root, *TIGHTER)[0] == 0
    assert fx.configure(root, "--autonomy", "controlled")[0] in (0, 1)
    assert fx.load(fx.gen(task_dir, 2) / "proposed.yml")["overlay"] == {
        "stages": {"refine": {"set": {"mode": "full"}}}, "autonomy": "controlled"}


def test_cr_1_a_stale_pending_proposal_is_not_the_base_of_the_next_call(tmp_path):
    """After a hand edit of `config:`, the proposal no longer describes the
    layer the person is changing, so the next call starts from the edit."""
    root, task_dir = fx.committed(tmp_path)
    assert fx.configure(root, *TIGHTER)[0] == 0
    fx.write_manifest(task_dir, config={"autonomy": "controlled"})
    assert fx.configure(root, "--ceiling", "subtask_ceiling=2")[0] in (0, 1)
    assert fx.load(fx.gen(task_dir, 2) / "proposed.yml")["overlay"] == {
        "autonomy": "controlled", "ceilings": {"subtask_ceiling": 2}}


def test_cr_1_a_call_with_no_change_is_an_error_and_writes_nothing(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    before = _tree(root)
    code, out, err = fx.configure(root)
    assert code == 2, out + err
    assert "--from-file" in out + err
    assert _tree(root) == before


@pytest.mark.parametrize("flags", [("--mode", "refine"), ("--mode", "=full"),
                                   ("--ceiling", "subtask_ceiling=two"),
                                   ("--ceiling", "subtask_ceiling"), ("--autonomy", "reckless")])
def test_cr_1_a_malformed_flag_is_an_error_and_writes_nothing(tmp_path, flags):
    root, task_dir = fx.committed(tmp_path)
    before = _tree(root)
    code, out, err = fx.configure(root, *flags)
    assert code == 2, out + err
    assert _tree(root) == before


def test_cr_1_a_file_that_is_not_a_mapping_is_an_error(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    bad = tmp_path / "overlay.yml"
    bad.write_text("- a\n- b\n", encoding="utf-8")
    code, out, err = fx.configure(root, "--from-file", str(bad))
    assert code == 2, out + err
    assert not fx.gen(task_dir, 2).exists()
    code, out, err = fx.configure(root, "--from-file", str(tmp_path / "missing.yml"))
    assert code == 2 and not fx.gen(task_dir, 2).exists()


@pytest.mark.parametrize("generation", [0, None])
def test_cr_1_an_issue_without_a_stored_generation_is_refused_with_the_fix(tmp_path, generation):
    root, task_dir = fx.project(tmp_path)
    if generation is not None:
        fx.write_manifest(task_dir, generation=generation)
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 2, out + err
    assert "compass approach evaluate --write" in out + err
    assert not (task_dir / "generations").exists()


# --- CR-2: the preview and the exit codes -------------------------------------------------

def test_cr_2_the_preview_names_each_part_and_the_next_step(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 0, out + err
    lines = out.splitlines()
    assert lines[0].startswith("compass issue configure: feature")
    assert "generation 1" in lines[0] and "proposed 2" in lines[0]
    wanted = ["verdict", "proposal", "resolved fields that change",
              "classification", "at this issue's assessment", "records invalidated",
              "next:"]
    for label in wanted:
        assert any(line.strip().startswith(label) for line in lines), (label, out)
    assert any("stages.refine.mode" in line for line in lines), out
    assert '/compass:assess --reassess --reason "..."' in out


def test_cr_2_a_tightening_is_accepted_with_exit_0(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *TIGHTER, "--json")
    assert code == 0, out + err
    doc = json.loads(out)
    assert doc["verdict"] == "accepted" and doc["reasons"] == []
    assert doc["classification"]["result"] in ("tightening", "equivalent")


def test_cr_2_a_loosening_without_a_waiver_writes_the_proposal_and_exits_1(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    before = (task_dir / "manifest.yml").read_bytes()
    code, out, err = fx.configure(root, *LOOSER, "--json")
    assert code == 1, out + err
    doc = json.loads(out)
    assert doc["verdict"] == "refused"
    assert doc["reasons"] and "define" in " ".join(doc["reasons"])
    assert doc["classification"]["result"] in ("loosening", "incomparable")
    assert doc["classification"]["first_point"] is not None
    assert (fx.gen(task_dir, 2) / "proposed.yml").is_file()
    assert (task_dir / "manifest.yml").read_bytes() == before


def test_cr_2_a_refused_text_preview_prints_the_reasons(tmp_path):
    root, _ = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *LOOSER)
    assert code == 1, out + err
    assert "refused" in out and "define" in out


@pytest.mark.parametrize("flags", [("--route", "nonesuch"), ("--mode", "refine=sideways"),
                                   ("--mode", "nostage=full")])
def test_cr_2_the_text_preview_never_prints_a_python_none(tmp_path, flags):
    root, _ = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *flags)
    assert code == 1, out + err
    assert "None" not in out, out


def test_cr_2_a_stage_mode_shows_the_mode_the_issue_has_not_null(tmp_path):
    root, _ = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *LOOSER, "--json")
    assert code == 1, out + err
    doc = json.loads(out)
    change = next(c for c in doc["changes"] if c["path"] == "stages.define.mode")
    assert change["after"] == "collapsed"
    owed = next(c for c in doc["assessment"]["changes"] if c["key"] == "define")
    assert change["before"] == owed["before"] and change["before"] is not None


def test_cr_2_the_preview_says_what_it_builds_on(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 0, out + err
    assert "builds on     : the manifest's config:" in out
    code, out, err = fx.configure(root, "--autonomy", "controlled", "--json")
    assert json.loads(out)["base"] == "pending proposal"
    code, out, err = fx.configure(root, "--ceiling", "subtask_ceiling=2")
    assert "builds on     : the pending proposal" in out


def test_cr_2_one_spelling_of_a_waiver_id_in_the_text(tmp_path):
    import yaml
    root, task_dir = fx.waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(fx.team("advisory")), encoding="utf-8")
    code, out, err = fx.configure(root, "--autonomy", "controlled")
    assert code == 0, out + err
    assert "waiver:issue:checks.team-check (waiver):" in out
    assert "EV-1 (approval): it approved waiver:issue:checks.team-check" in out
    assert "waiver waiver:" not in out and "approved waiver issue:" not in out


def test_cr_2_the_preview_lists_the_resolved_fields_that_change(tmp_path):
    root, _ = fx.committed(tmp_path)
    code, out, err = fx.configure(root, "--autonomy", "controlled", "--json")
    assert code == 0, out + err
    changes = {c["path"]: c for c in json.loads(out)["changes"]}
    assert changes["autonomy"]["before"] == "balanced"
    assert changes["autonomy"]["after"] == "controlled"
    assert list(changes) == sorted(changes)


def test_cr_2_the_assessment_part_shows_what_the_issue_owes_before_and_after(tmp_path):
    root, _ = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *TIGHTER, "--json")
    assert code == 0, out + err
    owed = json.loads(out)["assessment"]
    assert owed["approach"] == {"before": "regular", "after": "regular"}
    assert owed["result"] in ("tightening", "equivalent")
    assert owed["refused"] is None
    for change in owed["changes"]:
        assert list(change) == ["fact", "field", "key", "outcome", "before", "after"]


def test_cr_2_a_project_layer_that_does_not_load_is_an_error_and_writes_nothing(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    (root / "compass.yml").write_text("schema: 1\nstages: oops\n", encoding="utf-8")
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 2, out + err
    assert "stages" in out + err
    assert not fx.gen(task_dir, 2).exists()


def test_cr_2_an_unknown_stage_mode_is_refused_at_commit_so_exit_1(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.configure(root, "--mode", "refine=sideways", "--json")
    assert code == 1, out + err
    doc = json.loads(out)
    assert doc["verdict"] == "refused" and doc["reasons"]
    assert (fx.gen(task_dir, 2) / "proposed.yml").is_file()


# --- CR-3: the JSON contract ---------------------------------------------------------------
# The shape below is the public contract from 6.0.0. The example is pinned in
# tests/fixtures/issue-configure-example.json and shown in docs/issue-configure.md.

CONFIGURE_KEYS = ["schema", "issue", "generation", "proposed", "verdict", "reasons",
                  "proposal", "base", "changes", "classification", "assessment",
                  "invalidates", "next"]
CHANGE_KEYS = ["path", "before", "after"]
CLASSIFICATION_KEYS = ["result", "reason", "scan", "first_point"]
FIRST_POINT_KEYS = ["assessment", "represents", "outcome", "summary", "changes"]
POINT_CHANGE_KEYS = ["fact", "field", "key", "outcome", "parent", "child"]
ASSESSMENT_KEYS = ["approach", "result", "changes", "refused"]
APPROACH_KEYS = ["before", "after"]
ASSESSMENT_CHANGE_KEYS = ["fact", "field", "key", "outcome", "before", "after"]
REFUSED_KEYS = ["before", "after"]
INVALIDATES_KEYS = ["id", "kind", "reason"]
EXAMPLE = ROOT / "tests" / "fixtures" / "issue-configure-example.json"
REFUSED_EXAMPLE = ROOT / "tests" / "fixtures" / "issue-configure-refused-example.json"


def test_cr_3_the_document_has_the_pinned_keys_in_order(tmp_path):
    root, _ = fx.committed(tmp_path)
    code, out, err = fx.configure(root, "--autonomy", "controlled", "--json")
    assert code == 0, out + err
    doc = json.loads(out)
    assert list(doc) == CONFIGURE_KEYS
    assert doc["schema"] == 1 and doc["issue"] == fx.SLUG
    assert (doc["generation"], doc["proposed"]) == (1, 2)
    assert doc["proposal"] == ".compass/work/feature/generations/2/proposed.yml"
    assert doc["changes"] and all(list(c) == CHANGE_KEYS for c in doc["changes"])
    assert list(doc["classification"]) == CLASSIFICATION_KEYS
    assert list(doc["assessment"]) == ASSESSMENT_KEYS
    assert list(doc["assessment"]["approach"]) == APPROACH_KEYS
    assert doc["base"] == "config"
    assert doc["next"] == '/compass:assess --reassess --reason "..."'


def _refused_document(tmp_path):
    """A loosening that needs a waiver, on an issue whose waiver went stale."""
    import yaml
    root, task_dir = fx.waived_project(tmp_path)
    (root / "compass.yml").write_text(yaml.safe_dump(fx.team("advisory")), encoding="utf-8")
    code, out, err = fx.configure(root, *LOOSER, "--json")
    assert code == 1, out + err
    return json.loads(out)


def test_cr_3_every_nested_key_is_in_the_pinned_order(tmp_path):
    doc = _refused_document(tmp_path)
    assert list(doc) == CONFIGURE_KEYS
    assert all(list(c) == CHANGE_KEYS for c in doc["changes"])
    assert list(doc["classification"]) == CLASSIFICATION_KEYS
    point = doc["classification"]["first_point"]
    assert list(point) == FIRST_POINT_KEYS
    assert point["changes"] and all(list(c) == POINT_CHANGE_KEYS for c in point["changes"])
    assert list(doc["assessment"]) == ASSESSMENT_KEYS
    assert list(doc["assessment"]["approach"]) == APPROACH_KEYS
    assert doc["assessment"]["changes"] and all(
        list(c) == ASSESSMENT_CHANGE_KEYS for c in doc["assessment"]["changes"])
    assert doc["invalidates"] and all(list(r) == INVALIDATES_KEYS for r in doc["invalidates"])
    assert {r["kind"] for r in doc["invalidates"]} == {"waiver", "approval"}


def test_cr_3_the_refused_output_equals_the_second_pinned_example(tmp_path):
    doc = _refused_document(tmp_path)
    pinned = json.loads(REFUSED_EXAMPLE.read_text(encoding="utf-8"))
    assert doc == pinned
    assert list(doc) == list(pinned)
    assert doc["verdict"] == "refused"
    assert doc["classification"]["first_point"] is not None
    assert [r["id"] for r in doc["invalidates"]] == ["EV-1", "waiver:issue:checks.team-check"]


def test_cr_3_the_documented_second_example_is_the_pinned_one():
    doc = (ROOT / "docs" / "issue-configure.md").read_text(encoding="utf-8")
    assert REFUSED_EXAMPLE.read_text(encoding="utf-8").strip() in doc


def test_cr_3_every_documented_nested_key_is_in_the_doc():
    doc = (ROOT / "docs" / "issue-configure.md").read_text(encoding="utf-8")
    for name in (CONFIGURE_KEYS + CHANGE_KEYS + CLASSIFICATION_KEYS + FIRST_POINT_KEYS
                 + POINT_CHANGE_KEYS + ASSESSMENT_KEYS + ASSESSMENT_CHANGE_KEYS
                 + REFUSED_KEYS + INVALIDATES_KEYS):
        assert f"`{name}`" in doc, name


def test_cr_3_the_output_equals_the_pinned_example(tmp_path):
    root, _ = fx.committed(tmp_path)
    code, out, err = fx.configure(root, "--autonomy", "controlled", "--json")
    assert code == 0, out + err
    assert EXAMPLE.is_file()
    assert json.loads(out) == json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert list(json.loads(out)) == list(json.loads(EXAMPLE.read_text(encoding="utf-8")))


def test_cr_3_the_documented_example_is_the_pinned_one():
    doc = (ROOT / "docs" / "issue-configure.md").read_text(encoding="utf-8")
    assert EXAMPLE.read_text(encoding="utf-8").strip() in doc


def test_cr_3_json_goes_to_stdout_alone(tmp_path):
    root, _ = fx.committed(tmp_path)
    code, out, err = fx.configure(root, *TIGHTER, "--json")
    assert code == 0
    json.loads(out)
    assert err == ""


# --- CR-4: discard --------------------------------------------------------------------------

def test_cr_4_discard_removes_a_pending_proposal_and_leaves_the_manifest(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.configure(root, *TIGHTER)
    before = (task_dir / "manifest.yml").read_bytes()
    code, out, err = fx.configure(root, "--discard")
    assert code == 0, out + err
    assert not fx.gen(task_dir, 2).exists()
    assert (task_dir / "manifest.yml").read_bytes() == before
    assert fx.gen(task_dir, 1).is_dir()
    assert "generation 2" in out


def test_cr_4_discard_removes_an_incomplete_or_unreferenced_leftover(tmp_path):
    import shutil
    root, task_dir = fx.committed(tmp_path)
    shutil.copytree(fx.gen(task_dir, 1), fx.gen(task_dir, 2))
    (fx.gen(task_dir, 2) / "complete").unlink()
    code, out, err = fx.configure(root, "--discard", "2")
    assert code == 0, out + err
    assert not fx.gen(task_dir, 2).exists()
    shutil.copytree(fx.gen(task_dir, 1), fx.gen(task_dir, 2))
    code, out, err = fx.configure(root, "--discard")
    assert code == 0, out + err
    assert not fx.gen(task_dir, 2).exists()


def test_cr_4_discard_never_removes_the_current_or_an_older_generation(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    for target, said in (("1", "is the generation in force"),
                         ("0", "is older than the one in force")):
        code, out, err = fx.configure(root, "--discard", target)
        assert code == 2, out + err
        assert said in out + err, out + err
    assert (fx.gen(task_dir, 1) / "complete").is_file()


def test_cr_4_nothing_to_discard_is_an_error(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.configure(root, "--discard")
    assert code == 2, out + err
    assert "nothing to discard" in out + err


def test_cr_4_discard_without_a_number_names_the_choices_when_there_are_several(tmp_path):
    import shutil
    root, task_dir = fx.committed(tmp_path)
    shutil.copytree(fx.gen(task_dir, 1), fx.gen(task_dir, 2))
    shutil.copytree(fx.gen(task_dir, 1), fx.gen(task_dir, 3))
    code, out, err = fx.configure(root, "--discard")
    assert code == 2, out + err
    assert "2" in out + err and "3" in out + err
    assert fx.gen(task_dir, 2).is_dir() and fx.gen(task_dir, 3).is_dir()
    assert fx.configure(root, "--discard", "3")[0] == 0
    assert fx.gen(task_dir, 2).is_dir() and not fx.gen(task_dir, 3).exists()


def test_cr_4_discard_does_not_combine_with_a_change(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    code, out, err = fx.configure(root, "--discard", *TIGHTER)
    assert code == 2, out + err


# --- CR-12: refusals ---------------------------------------------------------------------------

def test_cr_12_a_landed_issue_cannot_be_given_a_proposal(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, status="landed")
    before = _tree(root)
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 2, out + err
    assert "landed" in out + err
    assert _tree(root) == before


def test_cr_12_the_store_itself_refuses_a_proposal_for_a_landed_issue(tmp_path):
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, status="landed")
    before = _tree(root)
    with pytest.raises(CompassError, match="landed"):
        effective.write_proposal(str(task_dir), fx.manifest_of(task_dir), {"autonomy": "balanced"})
    assert _tree(root) == before


def test_cr_12_a_landed_issue_is_refused_before_the_preview_is_computed(
        tmp_path, monkeypatch):
    """The preview resolves and classifies, which is slow; a call that cannot
    succeed must not pay for it."""
    import types
    from compass_pkg import config_preview, issue_config_cmd
    from compass_pkg.core import CompassError
    root, task_dir = fx.committed(tmp_path)
    fx.write_manifest(task_dir, status="landed")
    monkeypatch.chdir(root)

    def explode(*args, **kwargs):
        raise RuntimeError("the preview was computed")
    monkeypatch.setattr(config_preview, "build", explode)
    args = types.SimpleNamespace(task=fx.SLUG, discard=None, commit=None, from_file=None,
                                 mode=["refine=full"], route=None, autonomy=None,
                                 ceiling=None, reason=None, _mode=None, json=False)
    with pytest.raises(CompassError, match="landed"):
        issue_config_cmd.run_configure(args)


def test_cr_12_a_symbolic_link_in_the_next_folder_is_refused(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (task_dir / "generations" / "2").symlink_to(outside, target_is_directory=True)
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 2, out + err
    assert "symbolic link" in out + err
    assert list(outside.iterdir()) == []


def test_cr_12_a_discard_does_not_follow_a_symbolic_link(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "keep.txt").write_text("kept", encoding="utf-8")
    (task_dir / "generations" / "2").symlink_to(outside, target_is_directory=True)
    code, out, err = fx.configure(root, "--discard", "2")
    assert code == 2, out + err
    assert (outside / "keep.txt").read_text(encoding="utf-8") == "kept"


def test_cr_12_a_folder_that_holds_a_generation_is_not_overwritten_by_a_proposal(tmp_path):
    import shutil
    root, task_dir = fx.committed(tmp_path)
    shutil.copytree(fx.gen(task_dir, 1), fx.gen(task_dir, 2))
    before = sorted(p.name for p in fx.gen(task_dir, 2).iterdir())
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 2, out + err
    assert "compass issue configure --commit 2" in out + err
    assert "compass issue configure --discard 2" in out + err
    assert sorted(p.name for p in fx.gen(task_dir, 2).iterdir()) == before


def test_cr_12_a_proposal_file_that_is_not_ours_is_refused_not_trusted(tmp_path):
    root, task_dir = fx.committed(tmp_path)
    fx.gen(task_dir, 2).mkdir()
    (fx.gen(task_dir, 2) / "proposed.yml").write_text("overlay: [oops\n", encoding="utf-8")
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 2, out + err
    assert "proposed.yml" in out + err


@pytest.mark.parametrize("text", ["overlay: 3\n", "schema: 1\noverlay: {}\n",
                                  "schema: 2\nissue: feature\nbase_generation: 1\n"
                                  "base_config_digest: x\noverlay: {}\n",
                                  "schema: 1\nissue: feature\nbase_generation: true\n"
                                  "base_config_digest: x\noverlay: {}\n"])
def test_cr_12_a_proposal_of_the_wrong_shape_is_refused_and_not_applied(tmp_path, text):
    root, task_dir = fx.committed(tmp_path)
    fx.gen(task_dir, 2).mkdir()
    path = fx.gen(task_dir, 2) / "proposed.yml"
    path.write_text(text, encoding="utf-8")
    snapshot = _tree(root)
    code, out, err = fx.configure(root, *TIGHTER)
    assert code == 2, out + err
    assert "not a proposal" in out + err and "--discard 2" in out + err
    code, out, err = fx.reassess(root)
    assert code == 2, out + err
    assert "not a proposal" in out + err
    assert _tree(root) == snapshot
    assert path.read_text(encoding="utf-8") == text


# --- CR-11: help, owning doc, assess command and corpus -------------------------------------------

def test_cr_11_the_help_describes_the_verb_and_its_exit_codes(tmp_path):
    code, out, err = fx.run(ROOT, "issue", "configure", "--help")
    assert code == 0, out + err
    flat = " ".join(out.split())
    for word in ("--from-file", "--mode", "--route", "--autonomy", "--ceiling",
                 "--discard", "--commit", "--json", "--issue"):
        assert word in out, word
    for sentence in ("Exit 0", "exit 1", "2"):
        assert sentence.lower() in flat.lower(), sentence
    assert "manifest" in flat


def test_cr_11_the_owning_doc_has_a_row_and_the_assess_command_describes_the_flag():
    readme = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert "issue-configure.md" in readme
    assert "cli/compass_pkg/issue_config_cmd.py" in readme
    assert "cli/compass_pkg/config_preview.py" in readme
    assert (ROOT / "docs" / "issue-configure.md").is_file()
    assess = (ROOT / "commands" / "assess.md").read_text(encoding="utf-8")
    assert "--reset-config" in assess and "compass issue configure" in assess
    assert "generation" in assess


def test_cr_11_the_command_corpus_records_the_verb_with_a_true_reason():
    text = (ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml").read_text(
        encoding="utf-8")
    entries = yaml.safe_load(text)["entries"]
    wanted = {e["id"]: e for e in entries if e["argv"][:2] == ["issue", "configure"]}
    assert len(wanted) >= 3, sorted(wanted)
    for entry in wanted.values():
        marker = f"- id: {entry['id']}\n"
        before = text.split(marker)[0].rstrip().splitlines()
        assert before and before[-1].startswith("#"), entry["id"]
        assert "configure-and-reassess" in "\n".join(before[-6:]), entry["id"]
    assert {e["exit"] for e in wanted.values()} >= {0, 2}
