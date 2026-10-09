"""`compass policy diff` and the replay harness behind it (ADR-036, ADR-037).

`replay` is pure over resolved configurations: unit tests hand it the small
configurations of `classifier_fixtures`, so a replay takes a fraction of a
second. The end-to-end tests run the real CLI in a scratch project against the
committed preset.

Scenario ids: `PD-1` to `PD-10` (issue `policy-diff`). Each test name starts
with its scenario id.
"""
from __future__ import annotations

import copy
import importlib.util
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

CLI = ROOT / "cli" / "compass"


def _api():
    assert importlib.util.find_spec("compass_pkg.replay") is not None, \
        "cli/compass_pkg/replay.py does not exist"
    from compass_pkg import replay
    return replay


def _has(name):
    """The named public function of the module, or an assertion failure that
    says it is missing."""
    module = _api()
    assert hasattr(module, name), f"replay.{name} does not exist"
    return getattr(module, name)


# --- helpers ---------------------------------------------------------------------

def _env(home):
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1",
            "COLUMNS": "100", "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}


def _run(cwd, *argv):
    r = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd),
                       capture_output=True, text=True, timeout=300)
    return r.returncode, r.stdout, r.stderr


def _project(tmp_path, compass_yml=None):
    """A scratch project root: `.compass/` makes it the root."""
    (tmp_path / ".compass").mkdir(exist_ok=True)
    if compass_yml is not None:
        (tmp_path / "compass.yml").write_text(
            compass_yml if isinstance(compass_yml, str) else yaml.safe_dump(compass_yml),
            encoding="utf-8")
    return tmp_path


def _git(root, *argv):
    env = {**_env(root), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
    return subprocess.run(["git", *argv], cwd=root, env=env, capture_output=True,
                          text=True, check=True).stdout


# A change that loosens the shipped default: one check turned advisory.
LOOSER = {"schema": 1, "checks": {"suite-passed": {"set": {"severity": "advisory"}}}}
# A change that tightens it: one check turned blocking that is not.
BROKEN = "schema: 1\nstages: oops\n"
SET_UNKNOWN = {"schema": 1, "checks": {"no-such-check": {"set": {"severity": "advisory"}}}}


# --- PD-1: the references ---------------------------------------------------------------

@pytest.mark.parametrize("ref", ["default", "default@6", "compass:default@6",
                                 "default@6.0.0"])
def test_pd_1_the_shipped_default_has_one_label_and_its_version(ref, tmp_path):
    config = _has("resolve_ref")(ref, _project(tmp_path))
    assert (config.ref, config.kind, config.default_version) == ("default@6", "default",
                                                                 "6.0.0")
    assert config.capabilities == ()
    assert "approaches" in config.config


def test_pd_1_another_major_of_the_default_is_refused_by_name(tmp_path):
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")("default@7", _project(tmp_path))
    assert "default@7" in str(caught.value) and "default@6" in str(caught.value)


def test_pd_1_a_project_with_no_file_is_the_shipped_default(tmp_path):
    resolve = _has("resolve_ref")
    root = _project(tmp_path)
    project, default = resolve("project", root), resolve("default@6", root)
    assert (project.ref, project.kind) == ("project", "project")
    assert project.digest == default.digest
    assert project.config == default.config


def test_pd_1_a_project_file_is_layered_over_the_default(tmp_path):
    resolve = _has("resolve_ref")
    root = _project(tmp_path, LOOSER)
    project = resolve("project", root)
    assert project.config["checks"]["suite-passed"]["severity"] == "advisory"
    assert project.digest != resolve("default", root).digest
    assert project.default_version == "6.0.0"


def test_pd_1_a_path_is_one_file_over_the_default_and_the_label_has_no_path(tmp_path):
    root = _project(tmp_path)
    proposal = tmp_path / "proposed" / "next.yml"
    proposal.parent.mkdir()
    proposal.write_text(yaml.safe_dump(LOOSER), encoding="utf-8")
    config = _has("resolve_ref")(str(proposal), root)
    assert config.kind == "file"
    assert config.ref == "file:proposed/next.yml"
    assert config.config["checks"]["suite-passed"]["severity"] == "advisory"
    outside = Path(os.path.dirname(str(tmp_path))) / "outside.yml"
    outside.write_text(yaml.safe_dump(LOOSER), encoding="utf-8")
    try:
        assert _has("resolve_ref")(str(outside), root).ref == "file:outside.yml"
    finally:
        outside.unlink()


def test_pd_1_a_relative_path_is_read_from_the_working_folder(tmp_path):
    root = _project(tmp_path)
    (tmp_path / "next.yml").write_text(yaml.safe_dump(LOOSER), encoding="utf-8")
    config = _has("resolve_ref")("next.yml", root, cwd=tmp_path)
    assert config.ref == "file:next.yml"


def test_pd_1_the_copied_governance_files_resolve_as_legacy(tmp_path):
    root = _project(tmp_path)
    (root / "governance").mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copy(ROOT / "governance" / name, root / "governance" / name)
    config = _has("resolve_ref")("legacy", root)
    assert (config.ref, config.kind, config.default_version) == ("legacy", "legacy", None)
    assert "approaches" in config.config


def test_pd_1_legacy_without_copied_files_is_refused(tmp_path):
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")("legacy", _project(tmp_path))
    message = str(caught.value)
    assert message.startswith("legacy: the project holds no copied governance")
    assert "routing-policy.yml" in message and "guardrails.yml" in message
    assert "not found" not in message


def test_pd_1_a_git_revision_reads_the_file_as_it_was_then(tmp_path):
    root = _project(tmp_path, LOOSER)
    _git(root, "init", "-q")
    _git(root, "add", "compass.yml")
    _git(root, "commit", "-q", "-m", "first")
    (root / "compass.yml").write_text("schema: 1\n", encoding="utf-8")
    resolve = _has("resolve_ref")
    then = resolve("git:HEAD", root)
    assert (then.ref, then.kind) == ("git:HEAD", "git")
    assert then.config["checks"]["suite-passed"]["severity"] == "advisory"
    assert resolve("project", root).config["checks"]["suite-passed"]["severity"] == "blocking"


def test_pd_1_a_revision_with_no_file_is_the_shipped_default(tmp_path):
    root = _project(tmp_path)
    (root / "other.txt").write_text("x\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "other.txt")
    _git(root, "commit", "-q", "-m", "first")
    resolve = _has("resolve_ref")
    assert resolve("git:HEAD", root).digest == resolve("default", root).digest


def test_pd_1_an_unknown_revision_and_an_option_are_refused(tmp_path):
    from compass_pkg.core import CompassError
    root = _project(tmp_path)
    _git(root, "init", "-q")
    for ref in ("git:nope", "git:--output=x"):
        with pytest.raises(CompassError) as caught:
            _has("resolve_ref")(ref, root)
        assert ref in str(caught.value)


def test_pd_1_a_revision_outside_a_git_repository_is_refused(tmp_path):
    from compass_pkg.core import CompassError
    root = _project(tmp_path)
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")("git:HEAD", root)
    assert "git:HEAD" in str(caught.value)


@pytest.mark.parametrize("ref", ["nonsense", "generation:demo:1", "default@", ""])
def test_pd_1_an_unknown_reference_names_itself(ref, tmp_path):
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")(ref, _project(tmp_path))
    message = str(caught.value)
    assert (ref in message) or ref == ""
    if ref.startswith("generation:"):
        assert "does not yet compare against a stored generation" in message
        assert "compass policy show --issue demo" in message
        assert "has not landed" not in message


def test_pd_1_a_file_that_does_not_parse_or_merge_names_its_reference(tmp_path):
    from compass_pkg.core import CompassError
    root = _project(tmp_path)
    broken = tmp_path / "broken.yml"
    broken.write_text("schema: 1\nschema: 2\n", encoding="utf-8")
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")(str(broken), root)
    assert "file:broken.yml" in str(caught.value)
    bad_layer = tmp_path / "layer.yml"
    bad_layer.write_text(BROKEN, encoding="utf-8")
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")(str(bad_layer), root)
    assert "file:layer.yml" in str(caught.value)
    assert "policy lint" in str(caught.value)
    unmergeable = tmp_path / "unmergeable.yml"
    unmergeable.write_text(yaml.safe_dump(SET_UNKNOWN), encoding="utf-8")
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")(str(unmergeable), root)
    assert "M-SET-UNKNOWN" in str(caught.value)


def test_pd_1_the_arguments_default_as_the_design_says():
    refs = _has("default_refs")
    assert refs([]) == ("git:HEAD", "project")
    assert refs(["proposed.yml"]) == ("project", "proposed.yml")
    assert refs(["default@6", "project"]) == ("default@6", "project")
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError):
        refs(["a", "b", "c"])


# --- the small configurations for the replay tests ---------------------------------

def _config(label, config, capabilities=(), kind="project"):
    return _api().Config(label, kind, config, tuple(capabilities), {}, "6.0.0")


def _pair(change=None, labels=None):
    """`(A, B)`: the small base configuration, and a copy that `change` edits."""
    import classifier_fixtures as fixtures
    before = fixtures.base()
    after = fixtures.base()
    if labels:
        before = fixtures.with_labels(before, *labels)
        after = fixtures.with_labels(after, *labels)
    if change:
        change(after)
    return _config("before", before), _config("after", after)


def _advisory(config):
    config["checks"]["tests-pass"]["severity"] = "advisory"


def _small_for_large(config):
    """Size large no longer leans towards the full approach."""
    config["rules"]["default_shapes"]["rules"]["S-1"]["then"]["lean_toward"] = "regular"


def _reword(config):
    config["checks"]["tests-pass"]["statement"] = "The suite passed, again."


def _diff(change=None, labels=None, **kwargs):
    a, b = _pair(change, labels)
    return _has("diff")(a, b, **kwargs)


def _set(document, name):
    found = [s for s in document["replay"]["sets"] if s["name"] == name]
    assert len(found) == 1, document["replay"]["sets"]
    return found[0]


def _changes(document, name):
    return [c for c in document["replay"]["changes"] if c["set"] == name]


# --- PD-2: the classification is the classifier's own JSON ------------------------------

def test_pd_2_the_classification_is_the_classifiers_json_unchanged():
    from compass_pkg import classify
    a, b = _pair(_advisory)
    document = _has("diff")(a, b)
    expected = classify.classify(a.config, b.config, parent_name="before",
                                 child_name="after").to_json()
    assert document["classification"] == expected
    assert document["classification"]["result"] == "loosening"
    assert classify.json_shape_errors(document["classification"]) == []


def test_pd_2_the_two_references_are_the_parent_and_child_of_the_classification():
    document = _diff(_advisory)
    assert document["classification"]["parent"] == "before"
    assert document["classification"]["child"] == "after"
    assert document["a"]["ref"] == "before" and document["b"]["ref"] == "after"


def test_pd_2_the_capabilities_of_each_side_reach_the_classifier():
    from compass_pkg import classify
    a, b = _pair()
    b.capabilities = ("entry-exit-evaluation",)
    document = _has("diff")(a, b)
    expected = classify.classify(a.config, b.config, parent_capabilities=(),
                                 child_capabilities=("entry-exit-evaluation",),
                                 parent_name="before", child_name="after").to_json()
    assert document["classification"] == expected
    assert document["b"]["capabilities"] == ["entry-exit-evaluation"]


def test_pd_2_identical_configurations_are_the_identical_scan():
    document = _diff()
    assert document["classification"]["scan"] == "identical"
    assert document["classification"]["result"] == "equivalent"
    assert document["differs"] is False


def test_pd_2_the_text_names_the_verdict_and_both_references():
    text = "\n".join(_has("diff_text")(_diff(_advisory)))
    assert "before" in text and "after" in text
    assert "classification: loosening" in text


# --- PD-3: the grid is replayed -----------------------------------------------------------

def test_pd_3_a_loosened_check_changes_every_point_and_each_difference_is_a_quartet():
    document = _diff(_advisory)
    grid = _set(document, "grid")
    assert grid["replayed"] == 2 and grid["changed"] == 2 and grid["skipped"] is None
    changes = _changes(document, "grid")
    assert len(changes) == 2
    for change in changes:
        assert list(change) == ["set", "issue", "assessment", "represents", "differences"]
        assert change["issue"] is None
        assert change["assessment"]["labels"] == []
        assert change["represents"]["size"] in (["small"], ["large"])
        for difference in change["differences"]:
            assert list(difference) == ["field", "key", "before", "after"]
    first = changes[0]["differences"]
    assert [(d["field"], d["key"]) for d in first] == [("checks", "tests-pass")]
    assert first[0]["before"]["severity"] == "blocking"
    assert first[0]["after"]["severity"] == "advisory"
    # At the large point the full approach also owes the unchanged check
    # `no-secrets`; a name whose value did not change is not a difference.
    assert [(d["field"], d["key"]) for d in changes[1]["differences"]] == [
        ("checks", "tests-pass")]


def test_pd_3_a_change_to_a_route_lists_the_approach_and_what_follows():
    document = _diff(_small_for_large)
    grid = _set(document, "grid")
    assert (grid["replayed"], grid["changed"]) == (2, 1)
    (change,) = _changes(document, "grid")
    assert change["assessment"]["size"] == "large"
    fields = {d["field"]: d for d in change["differences"]}
    assert fields["approach"]["before"] == "full" and fields["approach"]["after"] == "regular"
    assert "verify.security" in fields["gate_set"]["before"]
    assert "verify.security" not in fields["gate_set"]["after"]


def test_pd_3_a_change_nothing_reads_replays_every_point_and_lists_none():
    document = _diff(_reword)
    grid = _set(document, "grid")
    assert grid["replayed"] == 2 and grid["changed"] == 0
    assert _changes(document, "grid") == []
    assert document["classification"]["result"] == "equivalent"
    assert document["differs"] is False


def test_pd_3_identical_configurations_replay_nothing_and_say_why():
    document = _diff()
    grid = _set(document, "grid")
    assert grid["replayed"] == 0 and grid["changed"] == 0
    assert grid["skipped"] == "the configurations are identical"
    assert document["replay"]["changes"] == []


def test_pd_3_the_points_come_in_scan_order_and_stand_for_their_classes():
    document = _diff(_advisory)
    sizes = [c["assessment"]["size"] for c in _changes(document, "grid")]
    assert sizes == ["small", "large"]
    assert _changes(document, "grid")[0]["represents"] == {
        "risk": ["contained", "critical"],
        "familiarity": ["greenfield", "brownfield-unmapped"], "size": ["small"]}


def test_pd_3_a_value_only_one_side_accepts_is_a_difference_of_its_own():
    def drop_large(config):
        config["dimensions"]["size"]["values"] = ["small"]
    document = _diff(drop_large)
    changes = _changes(document, "grid")
    one_side = [c for c in changes
                if any(d["field"] == "dimensions.values" for d in c["differences"])]
    assert len(one_side) == 1
    (difference,) = one_side[0]["differences"]
    assert (difference["key"], difference["before"], difference["after"]) == (
        "size", True, False)
    assert one_side[0]["assessment"]["size"] == "large"


def test_pd_3_a_side_the_evaluator_refuses_is_an_evaluation_difference():
    import classifier_fixtures as fixtures
    a, b = _pair()
    a.config = fixtures.with_spike(a.config)
    b.config = fixtures.with_spike(b.config, when={"risk": "contained"})
    document = _has("diff")(a, b)
    assert _set(document, "grid")["changed"] >= 1
    assert all(d["field"] != "evaluation" or d["before"] != d["after"]
               for c in _changes(document, "grid") for d in c["differences"])


# --- PD-4: the label combinations ------------------------------------------------------------

def test_pd_4_each_point_with_a_label_is_replayed_by_size_then_name():
    document = _diff(_advisory, labels=("ci", "docs"))
    labels = _set(document, "labels")
    # Labels: auth (named by the base floor), ci and docs - seven non-empty subsets.
    assert labels["replayed"] == 2 * 7 and labels["changed"] == 2 * 7
    changes = _changes(document, "labels")
    first_class = [c["assessment"]["labels"] for c in changes[:7]]
    assert first_class == [["auth"], ["ci"], ["docs"], ["auth", "ci"], ["auth", "docs"],
                           ["ci", "docs"], ["auth", "ci", "docs"]]
    assert all(c["assessment"]["labels"] for c in changes)
    assert all(not c["assessment"]["labels"] for c in _changes(document, "grid"))


def test_pd_4_the_sets_come_in_the_order_grid_then_labels():
    document = _diff(_advisory)
    assert [s["name"] for s in document["replay"]["sets"]][:2] == ["grid", "labels"]
    kinds = [c["set"] for c in document["replay"]["changes"]]
    assert kinds == sorted(kinds, key=["grid", "labels"].index)


def test_pd_4_a_change_only_a_label_shows_is_listed_in_the_labels_set_alone():
    def soften_floor(config):
        config["rules"]["floors"]["rules"]["F-1"]["then"]["force_minimum_approach"] = "regular"
    document = _diff(soften_floor)
    assert _set(document, "grid")["changed"] == 0
    labels = _set(document, "labels")
    assert (labels["replayed"], labels["changed"]) == (2, 1)
    (change,) = _changes(document, "labels")
    assert change["assessment"]["labels"] == ["auth"]
    assert change["assessment"]["size"] == "small"
    assert any(d["field"] == "approach" and d["before"] == "full"
               and d["after"] == "regular" for d in change["differences"])


def test_pd_4_more_than_eight_named_labels_skips_the_set_and_keeps_the_grid():
    names = [f"l{i}" for i in range(8)]
    document = _diff(_advisory, labels=names)
    labels = _set(document, "labels")
    assert labels["replayed"] == 0 and labels["changed"] == 0
    assert "more than eight named labels" in labels["skipped"]
    assert "9" in labels["skipped"]
    grid = _set(document, "grid")
    assert grid["replayed"] == 2 and grid["changed"] == 2 and grid["skipped"] is None
    assert document["differs"] is True


def test_pd_4_identical_configurations_skip_the_labels_set_too():
    labels = _set(_diff(), "labels")
    assert labels["replayed"] == 0 and labels["skipped"] == "the configurations are identical"


# --- PD-5: the archive's assessments ----------------------------------------------------------

ASSESSMENT = {"risk": "contained", "familiarity": "greenfield", "size": "large",
              "labels": []}


def _issue(slug, assessment=ASSESSMENT, status="landed", config=None):
    return _has("Issue")(slug, status, copy.deepcopy(assessment), config)


def _drop_large(config):
    config["dimensions"]["size"]["values"] = ["small"]


def test_pd_5_each_archived_assessment_is_replayed_by_slug_and_a_change_names_its_issue():
    archive = [_issue("b-issue"), _issue("a-issue", dict(ASSESSMENT, size="small"))]
    document = _diff(_advisory, archive=archive)
    entry = _set(document, "archive")
    assert (entry["replayed"], entry["changed"], entry["skipped"]) == (2, 2, None)
    changes = _changes(document, "archive")
    assert [c["issue"] for c in changes] == ["a-issue", "b-issue"]
    first = changes[0]
    assert list(first) == ["set", "issue", "assessment", "represents", "differences"]
    assert first["represents"] is None
    assert first["assessment"] == {"familiarity": "greenfield", "labels": [],
                                   "risk": "contained", "size": "small"}
    assert [(d["field"], d["key"]) for d in first["differences"]] == [("checks", "tests-pass")]


def test_pd_5_a_change_nothing_reads_lists_no_archived_issue():
    document = _diff(_reword, archive=[_issue("a-issue")])
    entry = _set(document, "archive")
    assert (entry["replayed"], entry["changed"]) == (1, 0)
    assert document["differs"] is False


def test_pd_5_a_value_one_side_lacks_is_an_evaluation_difference():
    document = _diff(_drop_large, archive=[_issue("holds-large"),
                                           _issue("holds-small", dict(ASSESSMENT, size="small"))])
    (change,) = _changes(document, "archive")
    assert change["issue"] == "holds-large"
    (difference,) = change["differences"]
    assert difference["field"] == "evaluation" and difference["key"] is None
    assert difference["before"] == "runs"
    assert difference["after"].startswith("cannot run: ") and "large" in difference["after"]


def test_pd_5_an_assessment_neither_side_can_run_in_the_same_way_is_no_difference():
    broken = {"familiarity": "greenfield", "size": "small", "labels": []}
    document = _diff(_advisory, archive=[_issue("no-risk", broken)])
    entry = _set(document, "archive")
    assert (entry["replayed"], entry["changed"]) == (1, 0)


def test_pd_5_an_issue_with_no_assessment_is_not_replayed():
    document = _diff(_advisory, archive=[_issue("none", None), _issue("fine")])
    assert _set(document, "archive")["replayed"] == 1


def test_pd_5_the_set_is_skipped_for_identical_configurations_and_an_empty_archive():
    identical = _diff(archive=[_issue("a-issue")])
    entry = _set(identical, "archive")
    assert entry["replayed"] == 0 and entry["skipped"] == "the configurations are identical"
    empty = _diff(_advisory)
    entry = _set(empty, "archive")
    assert entry["replayed"] == 0 and entry["skipped"] == "the project holds no archived issue"


def test_pd_5_the_archive_is_read_from_the_manifests_of_the_project(tmp_path):
    root = _project(tmp_path)
    work = root / ".compass" / "work"
    for slug, status in (("zeta", "landed"), ("alpha", "active"), ("mid", "abandoned")):
        (work / slug).mkdir(parents=True)
        (work / slug / "manifest.yml").write_text(yaml.safe_dump(
            {"issue": slug, "status": status, "assessment": ASSESSMENT,
             **({"config": {"stages": {}}} if slug == "alpha" else {})}), encoding="utf-8")
    (work / "no-manifest").mkdir()
    (work / "broken").mkdir()
    (work / "broken" / "manifest.yml").write_text("issue: [unclosed\n", encoding="utf-8")
    (work / "list").mkdir()
    (work / "list" / "manifest.yml").write_text("- not\n- a mapping\n", encoding="utf-8")
    issues = _has("read_archive")(root)
    assert [i.slug for i in issues] == ["alpha", "broken", "list", "mid", "zeta"]
    assert [i.unreadable for i in issues] == [False, True, True, False, False]
    # The state is read from the records: no stored status, no records, so
    # `alpha` is in the backlog; the other two are closed.
    assert [i.status for i in issues if not i.unreadable] == ["backlog", "done", "done"]
    assert issues[0].config == {"stages": {}} and issues[3].config is None
    assert issues[0].assessment == ASSESSMENT
    assert _has("read_archive")(tmp_path / "nowhere") == []


# --- PD-6: --open --------------------------------------------------------------------------------

WAIVED = {"checks": {"tests-pass": {
    "set": {"severity": "advisory"},
    "waiver": {"reason": "A spike needs it.", "approved_by": "EV-APPROVAL"}}}}
WAIVED_SHIPPED = {"checks": {"suite-passed": {
    "set": {"severity": "advisory"},
    "waiver": {"reason": "A spike needs it.", "approved_by": "EV-APPROVAL"}}}}
OPEN_KEYS = ["issue", "status", "assessment", "differences", "unresolved"]
WAIVER_KEYS = ["issue", "waiver", "entry", "field", "before", "after", "message"]


def _open(document):
    assert document["open"] is not None
    return document["open"]


def test_pd_6_without_the_option_the_open_section_is_null():
    assert _diff(_advisory, archive=[_issue("a", status="active")])["open"] is None


def test_pd_6_only_issues_still_in_flight_are_examined_and_listed_by_slug():
    # `read_archive` gives each issue the state its records show, so a row
    # carries a state word and an issue in flight stores no status.
    archive = [_issue("landed-one", status="done"), _issue("parked-one", status="backlog"),
               _issue("abandoned-one", status="done"), _issue("active-one", status="in-progress"),
               _issue("queued-one", status="backlog", assessment=dict(ASSESSMENT, size="small")),
               _issue("no-status", status="ready")]
    document = _diff(_advisory, archive=archive, open=True)
    section = _open(document)
    assert section["examined"] == 4
    assert [i["issue"] for i in section["issues"]] == ["active-one", "no-status",
                                                      "parked-one", "queued-one"]
    assert [i["status"] for i in section["issues"]] == ["in-progress", "ready", "backlog",
                                                       "backlog"]
    for entry in section["issues"]:
        assert list(entry) == OPEN_KEYS
        assert entry["unresolved"] is None
        assert [(d["field"], d["key"]) for d in entry["differences"]] == [
            ("checks", "tests-pass")]


def test_pd_6_an_issue_the_change_does_not_touch_is_examined_and_not_listed():
    document = _diff(_reword, archive=[_issue("calm", status="active")], open=True)
    section = _open(document)
    assert section["examined"] == 1 and section["issues"] == []
    assert section["waivers"] == []
    assert document["differs"] is False


def test_pd_6_the_issues_own_layer_is_applied_on_both_sides():
    pinned = _issue("pinned", status="active", config={"approach": "regular"})
    free = _issue("free", status="active")
    document = _diff(_small_for_large, archive=[pinned, free], open=True)
    assert [i["issue"] for i in _open(document)["issues"]] == ["free"]


def test_pd_6_an_issue_layer_one_side_cannot_merge_is_listed_as_unresolved():
    def drop_check(config):
        del config["checks"]["no-secrets"]
        config["gates"]["verify.security"]["checks"] = []
    layer = {"checks": {"no-secrets": {"set": {"severity": "advisory"}}}}
    document = _diff(drop_check, archive=[_issue("stuck", status="active", config=layer)],
                     open=True)
    (entry,) = _open(document)["issues"]
    assert entry["unresolved"]["side"] == "b"
    assert "M-SET-UNKNOWN" in entry["unresolved"]["message"]
    assert entry["differences"] == []
    assert list(entry["unresolved"]) == ["side", "message"]
    assert document["differs"] is True


def test_pd_6_an_issue_waiver_whose_parent_value_changed_needs_re_approval():
    waived = _issue("waived", status="active", config=WAIVED)
    document = _diff(_advisory, archive=[waived], open=True)
    (entry,) = _open(document)["waivers"]
    assert list(entry) == WAIVER_KEYS
    assert (entry["issue"], entry["waiver"], entry["entry"], entry["field"]) == (
        "waived", "issue:checks.tests-pass", "checks.tests-pass", "severity")
    assert (entry["before"], entry["after"]) == ("blocking", "advisory")
    assert "severity" in entry["message"]


def test_pd_6_a_change_elsewhere_asks_for_no_re_approval():
    def other(config):
        config["checks"]["no-secrets"]["severity"] = "advisory"
    waived = _issue("waived", status="active", config=WAIVED)
    document = _diff(other, archive=[waived], open=True)
    assert _open(document)["waivers"] == []


def test_pd_6_a_waiver_listing_alone_makes_the_documents_differ():
    def waived_field(config):
        config["checks"]["tests-pass"]["statement"] = "The suite passed, again."
    layer = {"checks": {"tests-pass": {
        "set": {"statement": "Mine."},
        "waiver": {"reason": "A reason.", "approved_by": "EV-APPROVAL"}}}}
    document = _diff(waived_field, archive=[_issue("w", status="active", config=layer)],
                     open=True)
    assert document["classification"]["result"] == "equivalent"
    assert [w["field"] for w in _open(document)["waivers"]] == ["statement"]
    assert document["differs"] is True


def test_pd_6_a_landed_issues_waiver_is_never_listed():
    document = _diff(_advisory, archive=[_issue("done", status="landed", config=WAIVED)],
                     open=True)
    assert _open(document)["examined"] == 0 and _open(document)["waivers"] == []


def test_pd_6_nothing_is_written(tmp_path):
    root = _project(tmp_path)
    work = root / ".compass" / "work" / "live"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(yaml.safe_dump(
        {"issue": "live", "status": "active", "assessment": ASSESSMENT, "config": WAIVED}),
        encoding="utf-8")
    before = sorted((str(p.relative_to(root)), p.read_bytes()) for p in root.rglob("*")
                    if p.is_file())
    a, b = _pair(_advisory)
    _has("diff")(a, b, archive=_has("read_archive")(root), open=True)
    after = sorted((str(p.relative_to(root)), p.read_bytes()) for p in root.rglob("*")
                   if p.is_file())
    assert before == after


# --- the command, end to end ------------------------------------------------------------------

def _diff_cli(root, *argv):
    code, out, err = _run(root, "policy", "diff", *argv)
    return code, out, err


def _diff_json(root, *argv):
    code, out, err = _run(root, "policy", "diff", "--json", *argv)
    try:
        return code, json.loads(out), err
    except ValueError:
        return code, out, err


def _live_project(base):
    """A project whose compass.yml loosens a check, with one active issue that
    holds a waiver on that check, one queued issue with no layer and one
    landed issue."""
    root = _project(base, LOOSER)
    for slug, status, extra in (
            ("live-issue", "active", {"config": WAIVED_SHIPPED}), ("old-issue", "landed", {}),
            ("plain-issue", "queued", {})):
        work = root / ".compass" / "work" / slug
        work.mkdir(parents=True)
        (work / "manifest.yml").write_text(yaml.safe_dump(
            {"issue": slug, "status": status, "assessment": {
                "risk": "trivial", "familiarity": "greenfield", "size": "atomic",
                "goal": "delivery", "role": "engineer", "labels": []}, **extra}),
            encoding="utf-8")
    return root


@pytest.fixture(scope="module")
def looser_run(tmp_path_factory):
    """One real run of the whole command over the shipped default and a
    loosened project, with `--exit-code` and `--open`: the slow part of the
    end-to-end tests is done once."""
    root = _live_project(tmp_path_factory.mktemp("looser"))
    code, document, err = _diff_json(root, "--exit-code", "--open", "default@6", "project")
    return root, code, document, err


@pytest.fixture(scope="module")
def looser_text(looser_run):
    root = looser_run[0]
    return _diff_cli(root, "default@6", "project")


# --- PD-7: the exit codes --------------------------------------------------------------------

def test_pd_7_with_exit_code_a_difference_exits_1(looser_run):
    _, code, document, err = looser_run
    assert code == 1, err
    assert document["differs"] is True
    assert document["classification"]["result"] == "loosening"


def test_pd_7_without_it_a_difference_still_exits_0(looser_text):
    code, out, err = looser_text
    assert code == 0, err
    assert "loosening" in out


def test_pd_7_identical_configurations_exit_0_even_with_exit_code(tmp_path):
    root = _project(tmp_path)
    for argv in (("default@6", "project"), ("--exit-code", "default@6", "project")):
        code, out, err = _diff_cli(root, *argv)
        assert code == 0, (argv, out, err)
        assert "no difference" in out


def test_pd_7_an_unreadable_or_unresolvable_input_exits_2(tmp_path, tmp_path_factory):
    root = _project(tmp_path)
    cases = [(("nonsense",), "nonsense"), (("default@6", "generation:demo:1"),
                                           "stored generation"),
             (("--exit-code", "missing.yml"), "missing.yml")]
    for argv, said in cases:
        code, out, err = _diff_cli(root, *argv)
        assert code == 2, (argv, out, err)
        assert said in err, (argv, err)
    broken = _project(tmp_path_factory.mktemp("broken"), BROKEN)
    code, out, err = _diff_cli(broken, "--exit-code", "default@6", "project")
    assert code == 2 and "project" in err and "policy lint" in err


def test_pd_7_one_argument_compares_the_project_with_it(tmp_path):
    root = _project(tmp_path)
    (root / "proposed.yml").write_text("schema: 1\n", encoding="utf-8")
    code, document, err = _diff_json(root, "proposed.yml")
    assert code == 0, err
    assert (document["a"]["ref"], document["b"]["ref"]) == ("project", "file:proposed.yml")
    assert document["differs"] is False


def test_pd_7_no_argument_compares_the_file_at_head_with_the_working_file(
        tmp_path, tmp_path_factory):
    root = _project(tmp_path, "schema: 1\n")
    _git(root, "init", "-q")
    _git(root, "add", "compass.yml")
    _git(root, "commit", "-q", "-m", "first")
    code, document, err = _diff_json(root)
    assert code == 0, err
    assert (document["a"]["ref"], document["b"]["ref"]) == ("git:HEAD", "project")
    code, out, err = _diff_cli(_project(tmp_path_factory.mktemp("plain")))
    assert code == 2 and "git:HEAD" in err


# --- PD-8: --json is complete, stable and pinned ----------------------------------------------

EXAMPLE = ROOT / "tests" / "fixtures" / "policy-diff-json-example.json"
TOP_KEYS = ["schema", "differs", "a", "b", "classification", "replay", "open"]
CONFIG_KEYS = ["ref", "kind", "default_version", "digest", "capabilities"]
REPLAY_KEYS = ["sets", "changes", "unreadable"]
SET_KEYS = ["name", "replayed", "changed", "skipped"]
CHANGE_KEYS = ["set", "issue", "assessment", "represents", "differences"]
DIFFERENCE_KEYS = ["field", "key", "before", "after"]
OPEN_SECTION_KEYS = ["examined", "issues", "waivers", "unreadable"]
UNRESOLVED_KEYS = ["side", "message"]


def _example_document():
    """Every part of the document: a grid change, a label change, an archived
    issue, an open issue that cannot merge, one that changes, and a waiver
    that needs re-approval."""
    import classifier_fixtures as fixtures

    def after(config):
        _small_for_large(config)
        _advisory(config)
        config["rules"]["floors"]["rules"]["F-1"]["then"]["force_minimum_approach"] = "regular"
        del config["checks"]["no-secrets"]
        config["gates"]["verify.security"]["checks"] = []

    before_config = fixtures.base()
    after_config = fixtures.base()
    after(after_config)
    a = _api().Config("default@6", "default", before_config, (), {}, "6.0.0")
    b = _api().Config("project", "project", after_config, ("artifact-freshness",), {},
                      "6.0.0")
    layer = {"checks": {"no-secrets": {"set": {"severity": "advisory"}}}}
    archive = [
        _has("Issue")("broken-issue", None, None, None, True),
        _issue("landed-issue", dict(ASSESSMENT, size="small"), "landed"),
        _issue("stuck-issue", ASSESSMENT, "parked", layer),
        _issue("waived-issue", ASSESSMENT, "active", WAIVED),
        _issue("plain-issue", dict(ASSESSMENT, labels=["auth"]), "queued"),
    ]
    return _api().diff(a, b, archive, open=True)


def _key_tree(value):
    """The keys at every depth, from the first item of each list."""
    if isinstance(value, dict):
        return {k: _key_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_key_tree(value[0])] if value else []
    return None


def test_pd_8_every_part_of_the_document_has_its_keys_in_the_pinned_order():
    document = _example_document()
    assert list(document) == TOP_KEYS
    assert list(document["a"]) == CONFIG_KEYS and list(document["b"]) == CONFIG_KEYS
    assert list(document["replay"]) == REPLAY_KEYS
    for entry in document["replay"]["sets"]:
        assert list(entry) == SET_KEYS
    assert document["replay"]["changes"]
    for change in document["replay"]["changes"]:
        assert list(change) == CHANGE_KEYS
        for difference in change["differences"]:
            assert list(difference) == DIFFERENCE_KEYS
    assert list(document["open"]) == OPEN_SECTION_KEYS
    assert document["open"]["issues"] and document["open"]["waivers"]
    for issue in document["open"]["issues"]:
        assert list(issue) == OPEN_KEYS
        for difference in issue["differences"]:
            assert list(difference) == DIFFERENCE_KEYS
        if issue["unresolved"]:
            assert list(issue["unresolved"]) == UNRESOLVED_KEYS
    for waiver in document["open"]["waivers"]:
        assert list(waiver) == WAIVER_KEYS


def test_pd_8_the_example_reaches_every_set_and_every_kind_of_open_entry():
    document = _example_document()
    assert {c["set"] for c in document["replay"]["changes"]} == {"grid", "labels", "archive"}
    assert any(i["unresolved"] for i in document["open"]["issues"])
    assert any(i["differences"] for i in document["open"]["issues"])
    assert document["replay"]["unreadable"] == ["broken-issue"]
    assert document["open"]["unreadable"] == ["broken-issue"]
    assert document["classification"]["result"] == "incomparable" or \
        document["classification"]["result"] == "loosening"


def test_pd_8_every_outcome_has_every_key():
    check = _has("diff_shape_errors")
    for name, document in {
            "identical": _diff(), "equivalent": _diff(_reword),
            "loosening": _diff(_advisory), "open-empty": _diff(_reword, open=True),
            "unreadable": _diff(_advisory, archive=[_broken("bad")], open=True),
            "capped": _diff(_advisory, labels=[f"l{i}" for i in range(8)]),
            "example": _example_document()}.items():
        assert check(document) == [], name
        assert list(document) == TOP_KEYS, name


def test_pd_8_the_same_input_gives_the_same_bytes_whatever_the_order_it_arrives_in():
    one = json.dumps(_example_document())
    assert json.dumps(_example_document()) == one
    a, b = _pair(_advisory)
    issues = [_issue("c"), _issue("a"), _issue("b", status="active")]
    forward = json.dumps(_api().diff(a, b, issues, open=True))
    backward = json.dumps(_api().diff(a, b, list(reversed(issues)), open=True))
    assert forward == backward


def test_pd_8_the_digest_follows_the_configuration_and_its_capabilities():
    one, other = _pair()
    assert one.digest == other.digest and one.digest.startswith("sha256:")
    other.capabilities = ("artifact-freshness",)
    assert one.digest != other.digest
    _, changed = _pair(_advisory)
    assert one.digest != changed.digest


def test_pd_8_assessment_keys_are_sorted_so_no_input_order_leaks():
    document = _example_document()
    for change in document["replay"]["changes"]:
        assert list(change["assessment"]) == sorted(change["assessment"])


def test_pd_8_the_shape_checker_rejects_a_changed_document():
    check = _has("diff_shape_errors")
    document = _example_document()
    assert check(document) == []
    broken = dict(document)
    del broken["open"]
    assert check(broken)
    assert check({("verdict" if k == "differs" else k): v for k, v in document.items()})
    assert check(dict(document, differs="yes"))
    deeper = json.loads(json.dumps(document))
    deeper["replay"]["changes"][0]["differences"][0].pop("before")
    assert check(deeper)
    deeper = json.loads(json.dumps(document))
    deeper["replay"]["changes"][0]["set"] = "everything"
    assert check(deeper)
    deeper = json.loads(json.dumps(document))
    deeper["open"]["issues"][0]["unresolved"] = {"side": "c", "message": "x"}
    assert check(deeper)
    deeper = json.loads(json.dumps(document))
    deeper["a"]["kind"] = "url"
    assert check(deeper)


def test_pd_8_the_shape_is_pinned_by_a_committed_example():
    assert EXAMPLE.is_file(), "tests/fixtures/policy-diff-json-example.json does not exist"
    got = _example_document()
    want = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert got == want
    # The order of the keys is part of the shape.
    assert json.dumps(got) == json.dumps(want)
    assert _api().JSON_SCHEMA_VERSION == want["schema"] == 1
    assert _api().diff_shape_errors(want) == []


def test_pd_8_the_command_prints_the_documented_shape_and_no_path(looser_run):
    root, _, document, _ = looser_run
    assert _has("diff_shape_errors")(document) == []
    from compass_pkg import classify
    assert classify.json_shape_errors(document["classification"]) == []
    example = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    assert list(document) == list(example)
    assert _key_tree(document["a"]) == _key_tree(example["a"])
    # The dimensions of an assessment belong to the configuration, so they
    # differ between the small example and the shipped default.
    for key in ("assessment", "represents"):
        for part in (document, example):
            part["replay"]["changes"][0][key] = None
    assert document["replay"].pop("unreadable") == []
    assert example["replay"].pop("unreadable") == ["broken-issue"]
    assert _key_tree(document["replay"]) == _key_tree(example["replay"])
    assert _key_tree(document["open"]["waivers"]) == _key_tree(example["open"]["waivers"])
    assert str(root) not in json.dumps(document)
    assert [s["name"] for s in document["replay"]["sets"]] == ["grid", "labels", "archive"]
    assert document["replay"]["sets"][0]["replayed"] == 288
    # The issue that holds the waiver already runs at the looser value, so only
    # the issue with no layer changes.
    assert [i["issue"] for i in document["open"]["issues"]] == ["plain-issue"]
    assert [w["issue"] for w in document["open"]["waivers"]] == ["live-issue"]


def test_pd_8_the_command_prints_the_document_in_one_byte_form(tmp_path):
    root = _project(tmp_path)
    code, out, _ = _run(root, "policy", "diff", "--json", "default@6", "project")
    assert code == 0
    from compass_pkg import policy_lint
    assert out == policy_lint.dumps(json.loads(out)) + "\n"
    assert json.loads(out)["classification"]["scan"] == "identical"


# --- PD-9: the text output -----------------------------------------------------------------------

def _text(document):
    return _has("diff_text")(document)


def test_pd_9_identical_configurations_print_one_line_after_the_heading():
    lines = _text(_diff())
    assert lines == ["compass policy diff: before -> after",
                     "no difference: the two configurations route and check alike"]


def test_pd_9_the_text_shows_the_verdict_the_sets_and_the_first_changes():
    lines = _text(_diff(_small_for_large, archive=[_issue("old-one")]))
    text = "\n".join(lines)
    assert lines[0] == "compass policy diff: before -> after"
    assert lines[1].startswith("classification: tightening") or \
        lines[1].startswith("classification: loosening")
    assert "  grid: 2 replayed, 1 changed" in lines
    assert "  labels: 2 replayed, 1 changed" in lines
    assert "  archive: 1 replayed, 1 changed" in lines
    assert "at risk contained, familiarity greenfield, size large, labels none" in text
    assert "approach: \"full\" -> \"regular\"" in text
    assert "issue old-one" in text


def test_pd_9_a_skipped_set_says_why_and_a_long_set_is_counted_not_listed():
    names = [f"l{i}" for i in range(8)]
    lines = _text(_diff(_advisory, labels=names))
    assert any(l.startswith("  labels: skipped - more than eight named labels") for l in lines)
    many = _text(_diff(_advisory, labels=("ci", "docs", "ops")))
    text = "\n".join(many)
    assert "  labels: " in text
    assert "... and 25 more in labels; --json lists every one" in text
    after_heading = many[many.index(next(l for l in many if l.startswith("  labels: "))):]
    shown = [l for l in after_heading if l.startswith("    at ")]
    assert len(shown) == _api().TEXT_LIMIT


def test_pd_9_open_issues_and_waivers_are_listed_under_their_own_heading():
    lines = _text(_example_document())
    text = "\n".join(lines)
    assert "open issues: 3 examined, 3 would change" in lines
    assert "  stuck-issue (parked): cannot merge on b: issue: M-SET-UNKNOWN" in text
    assert "waivers needing re-approval:" in lines
    assert any("waived-issue" in l and "issue:checks.tests-pass" in l for l in lines)


def test_pd_9_lines_stay_within_a_hundred_columns_and_use_no_em_dash():
    for lines in (_text(_example_document()), _text(_diff(_advisory))):
        assert all(len(l) <= 100 for l in lines), [l for l in lines if len(l) > 100]
        assert not any(chr(0x2014) in l for l in lines)


def test_pd_9_the_command_prints_the_same_lines(looser_text):
    code, out, _ = looser_text
    assert out.splitlines()[0] == "compass policy diff: default@6 -> project"
    assert "classification: loosening" in out
    assert "  grid: 288 replayed, 144 changed" in out
    assert "  labels: 4320 replayed, 2160 changed" in out
    assert "  archive: 3 replayed, 3 changed" in out
    assert 'severity: "blocking" -> "advisory"' in out
    assert "--json lists every one" in out
    assert "open issues" not in out


# --- PD-10: the verb is registered, documented and within the caps ---------------------------------

DOC = ROOT / "docs" / "policy-diff.md"
MODULE = ROOT / "cli" / "compass_pkg" / "replay.py"


def _help(root, *argv):
    code, out, err = _run(root, *argv, "--help")
    assert code == 0, err
    return out


def test_pd_10_the_verb_sits_beside_lint_and_effective_and_describes_itself(tmp_path):
    root = _project(tmp_path)
    listing = _help(root, "policy")
    for verb in ("lint", "show", "diff"):
        assert verb in listing
    text = _help(root, "policy", "diff")
    for word in ("--open", "--exit-code", "--json", "default@6", "git:", "legacy"):
        assert word in text, word


def test_pd_10_the_long_description_says_what_the_verb_compares_and_how_it_exits():
    from compass_pkg import verb_help
    text = verb_help.VERB_DESCRIPTIONS.get("policy diff", "")
    for word in ("classif", "replay", "--open", "--exit-code", "--json", "0", "1", "2"):
        assert word in text, word


def test_pd_10_the_corpus_records_each_new_entry_with_its_reason():
    text = (ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml").read_text(
        encoding="utf-8")
    lines = text.splitlines()
    wanted = ("policy-diff-identical", "policy-diff-identical-exit-code",
              "policy-diff-bad-reference", "policy-diff-differs-exit-code")
    for entry in wanted:
        assert f"- id: {entry}" in lines, entry
        index = lines.index(f"- id: {entry}")
        reason = [l for l in lines[max(0, index - 5):index] if l.startswith("#")]
        assert reason and "Added on purpose by policy-diff" in " ".join(reason), entry


def test_pd_10_the_module_declares_its_dependencies_and_only_the_verbs_import_it():
    import re
    text = MODULE.read_text(encoding="utf-8")
    header = text.split("from __future__", 1)[0]
    assert "# DEPENDENCY:" in header
    for name in ("classify", "obligations", "merge", "waivers", "policy_lint"):
        assert f"compass_pkg.{name}" in header or name in header, name
    pattern = re.compile(r"^\s*(from compass_pkg import [^\n]*\breplay\b|"
                         r"from compass_pkg\.replay import|import compass_pkg\.replay)",
                         re.M)
    users = [p.name for p in sorted((ROOT / "cli").rglob("*.py"))
             if "vendor" not in p.parts and p.name != "replay.py"
             and pattern.search(p.read_text(encoding="utf-8"))]
    # `policy update` runs the same classification and replay to show what a
    # move of the shipped default changes, so it is the second importer.
    assert users == ["policy_cmd.py", "policy_update.py"]


def test_pd_10_the_module_changes_no_file_but_one_temporary_copy():
    import re
    text = MODULE.read_text(encoding="utf-8")
    assert not re.search(r"atomic_write|shutil|os\.(remove|unlink|rename|replace|makedirs)",
                         text)
    assert len(re.findall(r'open\([^)]*"w"', text)) == 1
    assert text.index('open(path, "w"') < text.index("def resolve_ref")


def test_pd_10_the_owning_docs_table_names_the_module_and_the_doc():
    text = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    row = next((l for l in text.splitlines() if "cli/compass_pkg/replay.py" in l
                and l.startswith("|")), "")
    assert "docs/policy-diff.md" in row
    assert "(policy-diff.md)" in text
    assert DOC.is_file()


def test_pd_10_the_doc_documents_the_references_the_options_and_every_json_key():
    assert DOC.is_file(), "docs/policy-diff.md does not exist"
    text = DOC.read_text(encoding="utf-8")
    keys = (TOP_KEYS + CONFIG_KEYS + REPLAY_KEYS + SET_KEYS + CHANGE_KEYS + DIFFERENCE_KEYS
            + OPEN_SECTION_KEYS + OPEN_KEYS + UNRESOLVED_KEYS + WAIVER_KEYS)
    for key in keys:
        assert f"`{key}`" in text, key
    for word in ("--open", "--exit-code", "--json", "default@6", "git:<revision>", "legacy",
                 "generation:", "grid", "labels", "archive", "five"):
        assert word in text, word
    for kind in _api().CONFIG_KINDS:
        assert f"`{kind}`" in text, kind
    assert "tests/fixtures/policy-diff-json-example.json" in text


def test_pd_10_the_docs_json_sketch_is_valid_json_with_the_documented_top_level_keys():
    import re
    assert DOC.is_file(), "docs/policy-diff.md does not exist"
    text = DOC.read_text(encoding="utf-8")
    blocks = re.findall(r"```json\n(.*?)```", text, re.S)
    assert blocks, "docs/policy-diff.md has no JSON sketch"
    sketch = json.loads(blocks[0])
    assert list(sketch) == TOP_KEYS


def test_pd_10_core_py_stays_within_its_cap_and_the_entry_script_is_unchanged():
    lines = (ROOT / "cli" / "compass_pkg" / "core.py").read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 1200
    assert "replay" not in (ROOT / "cli" / "compass").read_text(encoding="utf-8")


# --- review fixes -------------------------------------------------------------------------------

def _broken(slug):
    return _has("Issue")(slug, None, None, None, True)


def test_pd_5_a_manifest_that_does_not_parse_is_listed_not_dropped():
    archive = [_issue("ok", status="active"), _broken("bad")]
    document = _diff(_advisory, archive=archive, open=True)
    assert document["replay"]["unreadable"] == ["bad"]
    assert _set(document, "archive")["replayed"] == 1
    assert _open(document)["unreadable"] == ["bad"]
    assert _open(document)["examined"] == 1
    assert _diff(archive=archive)["replay"]["unreadable"] == ["bad"]
    assert _diff(_advisory, archive=[_issue("ok")])["replay"]["unreadable"] == []
    assert _diff(_advisory)["open"] is None


def test_pd_9_unreadable_manifests_are_named_in_the_text():
    text = "\n".join(_text(_diff(_advisory, archive=[_broken("bad")], open=True)))
    assert "unreadable manifests (not replayed): bad" in text


@pytest.mark.parametrize("ref", ["compass:defaultfoo", "compass:default@7", "compass:defaults"])
def test_pd_1_only_the_exact_prefixed_default_is_the_default(ref, tmp_path):
    from compass_pkg.core import CompassError
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")(ref, _project(tmp_path))
    assert ref in str(caught.value)
    assert _has("resolve_ref")("compass:default", _project(tmp_path)).ref == "default@6"


def test_pd_1_an_error_names_the_reference_once(tmp_path):
    from compass_pkg.core import CompassError
    root = _project(tmp_path)
    (tmp_path / "dup.yml").write_text("schema: 1\nschema: 2\n", encoding="utf-8")
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")(str(tmp_path / "dup.yml"), root)
    assert str(caught.value).count("file:dup.yml") == 1
    (tmp_path / "compass.yml").write_text(yaml.safe_dump(SET_UNKNOWN), encoding="utf-8")
    with pytest.raises(CompassError) as caught:
        _has("resolve_ref")("project", root)
    assert str(caught.value).count("project:") == 1
    assert "M-SET-UNKNOWN" in str(caught.value)


def test_pd_9_a_list_difference_names_what_was_added_and_removed():
    lines = _text(_diff(_small_for_large))
    gate = [l for l in lines if l.startswith("      gate_set")]
    assert gate and 'removed ["verify.security"]' in gate[0] and "->" not in gate[0]
    def add_gate(config):
        config["approaches"]["regular"]["gates"].append("verify.security")
    lines = _text(_diff(add_gate))
    assert any('added ["verify.security"]' in l for l in lines)


def test_pd_9_a_list_that_only_changes_order_says_so():
    lines = _api()._difference_lines(
        [{"field": "entry", "key": "plan", "before": ["a", "b"], "after": ["b", "a"]}], "  ")
    assert lines == ['  entry plan: reordered ["b", "a"]']


def test_pd_5_the_empty_set_says_which_kind_of_empty():
    none = _diff(_advisory)
    assert _set(none, "archive")["skipped"] == "the project holds no archived issue"
    bare = _diff(_advisory, archive=[_issue("a", None)])
    assert _set(bare, "archive")["skipped"] == "no archived issue has a recorded assessment"


def test_pd_4_a_capped_grid_with_no_visible_change_still_differs():
    names = [f"l{i}" for i in range(8)]
    document = _diff(_reword, labels=names)
    assert document["classification"]["result"] == "incomparable"
    assert _set(document, "grid")["changed"] == 0
    assert document["differs"] is True


def test_pd_5_the_archive_replays_without_the_issues_own_layer():
    pinned = _issue("pinned", status="active", config={"approach": "regular"})
    document = _diff(_small_for_large, archive=[pinned], open=True)
    assert [c["issue"] for c in _changes(document, "archive")] == ["pinned"]
    assert _open(document)["issues"] == []


def test_pd_10_the_corpus_reason_does_not_claim_every_report_verb_exits_0():
    text = (ROOT / "tests" / "fixtures" / "compat" / "contract-4-commands.yml").read_text(
        encoding="utf-8")
    assert "every report verb" not in text


def test_pd_10_the_policy_verbs_module_registers_diff_once_and_holds_no_merge_markers():
    # Read as text: a half-merged module fails here with its cause, not at import.
    text = (ROOT / "cli" / "compass_pkg" / "policy_cmd.py").read_text(encoding="utf-8")
    for marker in ("<<<<<<<", "=======\n", ">>>>>>>"):
        assert marker not in text, marker
    assert text.count("def run_policy_diff(") == 1
    assert text.count('pls.add_parser("diff"') == 1
