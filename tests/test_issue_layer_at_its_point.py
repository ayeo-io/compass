"""An issue's own layer is judged at the issue's own assessment.

A project layer applies to every assessment the project will ever see, so it
is compared with its parent over the whole grid. An issue has one assessment in
force, so its layer is compared at that assessment: the locks, the
classification and the lint all use the single-assessment form. A parent and a
project layer stay on the grid. Scenario ids `IP-1` to `IP-7` (issue
`issue-layer-at-its-point`). Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import configure_fixtures as fx  # noqa: E402

LAYERED = {"schema": 1}
QUICK_FIX = {"size": "small"}
SPIKE = {"goal": "exploration"}
# How a refusal names the point it was found at: the fixture's own assessment.
_OWN = "at risk contained, familiarity brownfield-mapped, size medium, goal "
DELIVERY_POINT = _OWN + "delivery, role engineer, labels none"
SPIKE_POINT = _OWN + "exploration, role engineer, labels none"


def _issue(tmp_path, assessment=None, **extra):
    """An issue at generation 1 whose assessment is the fixture's with
    `assessment` changed, committed by the real command."""
    body = dict(fx.MANIFEST, **extra)
    body["assessment"] = dict(fx.MANIFEST["assessment"], **(assessment or {}))
    return fx.committed(tmp_path, compass_yml=LAYERED, manifest=body)


def _preview(root, *flags):
    code, out, err = fx.configure(root, "--json", *flags)
    assert out, err
    return code, json.loads(out)


def _codes(doc):
    return [reason.split()[0] for reason in doc["reasons"]]


# --- IP-1: a route pick that drops locked work is refused at the issue's own point -------

def test_ip_1_route_spike_on_a_delivery_issue_is_refused_by_a_lock_at_its_point(tmp_path):
    root, _ = _issue(tmp_path)
    code, doc = _preview(root, "--route", "spike")
    assert code == 1 and doc["verdict"] == "refused"
    locked = [r for r in doc["reasons"] if r.startswith("K-LOCK-REFUSED")]
    assert locked, doc["reasons"]
    assert all(r.endswith(DELIVERY_POINT) for r in locked), locked


# --- IP-2: a spike issue that picks full loses spike.conclude ----------------------------

def test_ip_2_a_spike_issue_that_picks_full_is_refused_by_a_lock(tmp_path):
    root, _ = _issue(tmp_path, SPIKE)
    code, doc = _preview(root, "--route", "full")
    assert code == 1 and doc["verdict"] == "refused"
    locked = [r for r in doc["reasons"] if r.startswith("K-LOCK-REFUSED")]
    assert any("spike.conclude" in r for r in locked), doc["reasons"]
    assert all(r.endswith(SPIKE_POINT) for r in locked), locked


# --- IP-3: a pick that owes at least as much at its point is accepted --------------------

def test_ip_3_a_pick_the_floors_hold_at_the_approach_is_accepted(tmp_path):
    """A critical-risk issue runs `full` whatever it names, so `quick-fix` as a
    pick loosens nothing at its point. Over the grid it reached the spike points
    and was refused."""
    root, task_dir = _issue(tmp_path, {"risk": "critical"})
    assert fx.manifest_of(task_dir)["delivery_approach"] == "full"
    code, doc = _preview(root, "--route", "quick-fix")
    assert code == 0 and doc["verdict"] == "accepted", doc["reasons"]
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert fx.manifest_of(task_dir)["delivery_approach"] == "full"


def test_ip_3_a_pick_with_a_tighter_ceiling_is_accepted_and_committed(tmp_path):
    root, task_dir = _issue(tmp_path)
    code, doc = _preview(root, "--route", "regular", "--ceiling", "subtask_ceiling=1")
    assert code == 0 and doc["verdict"] == "accepted", doc["reasons"]
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    body = fx.manifest_of(task_dir)
    assert body["generation"] == 2 and body["subtask_ceiling"] == 1


def test_ip_3_quick_fix_to_regular_is_incomparable_on_the_subtask_ceiling(tmp_path):
    """The route that owes more gates also allows two subtasks where quick-fix
    allows one, and a higher ceiling is looser."""
    root, _ = _issue(tmp_path, QUICK_FIX)
    code, doc = _preview(root, "--route", "regular")
    assert code == 1 and doc["verdict"] == "refused"
    assert not any(r.startswith("K-LOCK-REFUSED") for r in doc["reasons"]), doc["reasons"]
    assert any("C-INCOMPARABLE" in r and "approaches.subtask_ceiling" in r for r in doc["reasons"])


# --- IP-4: full is not a plain tightening ------------------------------------------------

def test_ip_4_full_on_a_regular_issue_is_refused_as_incomparable_on_the_ceiling(tmp_path):
    root, _ = _issue(tmp_path)
    code, doc = _preview(root, "--route", "full")
    assert code == 1 and doc["verdict"] == "refused"
    assert not any(r.startswith("K-LOCK-REFUSED") for r in doc["reasons"]), doc["reasons"]
    assert any("C-INCOMPARABLE" in r and "approaches.subtask_ceiling" in r
               for r in doc["reasons"]), doc["reasons"]


# --- IP-5: a stage mode already in force is accepted; a loosening is not -----------------

def test_ip_5_refine_collapsed_on_a_quick_fix_issue_is_accepted(tmp_path):
    root, _ = _issue(tmp_path, QUICK_FIX)
    code, doc = _preview(root, "--mode", "refine=collapsed")
    assert code == 0 and doc["verdict"] == "accepted", doc["reasons"]


def test_ip_5_refine_collapsed_on_a_regular_issue_is_refused_without_a_waiver(tmp_path):
    root, _ = _issue(tmp_path)
    code, doc = _preview(root, "--mode", "refine=collapsed")
    assert code == 1 and doc["verdict"] == "refused"
    assert any("C-" in c for c in _codes(doc)), doc["reasons"]


# --- IP-6: a changed assessment is linted even when the configuration is the same --------

def test_ip_6_a_pick_carried_onto_a_spike_assessment_is_refused_on_reassess(tmp_path):
    """Naming `regular` on a regular issue loosens nothing. When the stored
    assessment becomes a spike, the same pick drops the spike obligations. The
    configuration and the computed outcome do not change, so only a lint at the
    new assessment can see it."""
    body = dict(fx.MANIFEST, config={"approach": "regular"})
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED, manifest=body)
    held = fx.manifest_of(task_dir)["config"]
    fx.write_manifest(task_dir, assessment=dict(fx.MANIFEST["assessment"], **SPIKE))
    code, out, err = fx.reassess(root)
    assert code != 0, out
    assert "does not pass the lint" in err and "K-LOCK-REFUSED" in err, err
    after = fx.manifest_of(task_dir)
    assert after["generation"] == 1 and after["config"] == held


def test_ip_6_an_unchanged_assessment_and_configuration_still_reports_no_change(tmp_path):
    body = dict(fx.MANIFEST, config={"approach": "regular"})
    root, task_dir = fx.committed(tmp_path, compass_yml=LAYERED, manifest=body)
    code, out, err = fx.reassess(root)
    assert code == 0, out + err
    assert "no change" in out and fx.manifest_of(task_dir)["generation"] == 1


# --- IP-7: a project layer is still judged over the whole grid ---------------------------

def test_ip_7_a_project_layer_that_drops_a_spike_check_is_still_refused(tmp_path):
    project = {"schema": 1, "owner": "jed72", "checks": {
        "spike-conclusion-present": {"set": {"severity": "advisory"}}}}
    root, task_dir = fx.project(tmp_path, compass_yml=project)
    code, out, err = fx.run(root, "policy", "lint")
    assert code != 0, out + err
    assert "K-LOCK-REFUSED" in out + err


# --- IP-8: the preview's classification is the one the verdict used -----------------------

def test_ip_8_the_preview_classification_is_at_the_issues_own_assessment(tmp_path):
    root, task_dir = _issue(tmp_path)
    code, doc = _preview(root, "--mode", "define=collapsed")
    assert code == 1 and doc["classification"]["result"] == "loosening"
    point = doc["classification"]["first_point"]
    own = fx.manifest_of(task_dir)["assessment"]
    assert point["assessment"] == own
    assert point["represents"] == {k: [v] for k, v in own.items() if k != "labels"}
    assert doc["classification"]["scan"] == "full"


# --- IP-9: a mixed route pick is refused, and the refusal names what makes it mixed ----------

def test_ip_9_the_worked_example_of_a_combined_pick_is_accepted(tmp_path):
    """`--route regular` alone raises nothing on a regular issue, and with the
    ceiling it is a pure tightening. The example in `docs/issue-configure.md`."""
    root, _ = _issue(tmp_path)
    code, doc = _preview(root, "--route", "regular", "--ceiling", "subtask_ceiling=1")
    assert code == 0 and doc["verdict"] == "accepted", doc["reasons"]
    text = (ROOT / "docs" / "issue-configure.md").read_text(encoding="utf-8")
    assert "--route regular --ceiling subtask_ceiling=1" in text


def test_ip_9_bare_regular_on_a_quick_fix_issue_names_every_field_that_makes_it_mixed(tmp_path):
    root, _ = _issue(tmp_path, QUICK_FIX)
    code, doc = _preview(root, "--route", "regular")
    assert code == 1 and doc["verdict"] == "refused"
    [reason] = doc["reasons"]
    assert "approaches.subtask_ceiling" in reason
    tail = reason.split("looser or cannot be compared:", 1)[1]
    assert "approaches.subtask_ceiling" in tail
    assert "approaches.stages (breakdown)" in tail and "approaches.artifacts" in tail
    assert "approaches.gates" not in tail        # a tightening is not listed


def test_ip_9_a_quick_fix_issue_cannot_combine_its_way_to_regular(tmp_path):
    """The ceiling is one of three fields that block it: breakdown (skipped
    against multiagent) and the artifacts owed cannot be compared either."""
    root, _ = _issue(tmp_path, QUICK_FIX)
    code, doc = _preview(root, "--route", "regular", "--ceiling", "subtask_ceiling=1")
    assert code == 1 and doc["verdict"] == "refused"
    assert "approaches.stages (breakdown)" in doc["reasons"][0]
