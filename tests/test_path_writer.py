"""The path writer: `compass approach evaluate --write` on the four-stage path (ADR-092).

The writer is dark-launched behind `routing.PATH_WRITER` (and the variable
`COMPASS_PATH_WRITER=1` for a CLI in a subprocess). The `path_writer` fixture of
`tests/conftest.py` turns it on for one test. With it on, a delivery assessment
writes `evidence_required` and the keys derived from it, and no `stages:`,
`subtask_ceiling:`, `max_worktrees:` or `orchestration:` key. A spike writes the
spike keys as before. With it off, the manifest is exactly the one 8.x wrote.

Issue: ayeo-io/compass-delivery#351 [Replace the approaches and eight stages
with one four-stage path].
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import evidence_required as er  # noqa: E402

EVERY_ISSUE = ["scenarios", "red-before-green", "suite-green",
               "correctness", "governance", "traceability"]
LIGHT = EVERY_ISSUE + ["outer-loop"]
STANDARD = EVERY_ISSUE + ["regression", "security", "clarity", "outer-loop", "isolation",
                          "layering", "definition-of-done"]
THREE = ["verify.correctness", "verify.governance", "verify.traceability"]
LEGACY_ONLY = ("stages", "subtask_ceiling", "max_worktrees", "orchestration")


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True, timeout=60)


def _assessment(**over):
    out = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "medium",
           "goal": "delivery", "urgency": "none", "labels": []}
    out.update(over)
    return out


def _project(tmp_path, slug="demo", **over):
    """A git repository on the live default, with one issue assessed and not evaluated."""
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    assert _run(root, "init").returncode == 0
    task_dir = root / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    assessment = _assessment(**over)
    manifest = {"schema_version": "3.0", "issue": slug, "created": "2026-11-05",
                "assessment": assessment,
                "justifications": {k: f"the {k} was judged" for k in assessment
                                   if k != "labels"}}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    (root / ".compass" / "current-task").write_text(slug + "\n")
    return root


def _manifest(root, slug="demo"):
    return yaml.safe_load((root / ".compass" / "work" / slug / "manifest.yml").read_text())


def _evaluate(root, *extra, slug="demo"):
    result = _run(root, "approach", "evaluate", "--issue", slug, "--write", *extra)
    assert result.returncode == 0, result.stdout + result.stderr
    return _manifest(root, slug)


def _schema_errors(body):
    import json

    import jsonschema
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text())
    return sorted(e.message for e in jsonschema.Draft7Validator(schema).iter_errors(body))


def _assert_path_keys(manifest):
    assert not _schema_errors(manifest), _schema_errors(manifest)
    assert manifest["delivery_approach"] == "delivery"
    for key in LEGACY_ONLY:
        assert key not in manifest, key
    assert manifest["checkpoint_outcomes"] == []
    assert all(g["status"] == "pending" and g["evidence"] == [] for g in manifest["gates"])


def _expected(assessment):
    """What `evidence_required.evaluate` gives under the live default."""
    from compass_pkg.core import load_yaml
    policy = load_yaml(str(ROOT / "governance" / "routing-policy.yml"))
    return er.evaluate(assessment, policy)


# --- the four delivery rows and the spike ----------------------------------------------

def test_a_small_change_writes_the_light_evidence(tmp_path, path_writer):
    root = _project(tmp_path, size="small")
    manifest = _evaluate(root)
    _assert_path_keys(manifest)
    assert manifest["evidence_required"] == LIGHT
    assert [g["id"] for g in manifest["gates"]] == THREE
    assert manifest["acceptance_strategy"] == {
        "state": "on", "routing": "existing-dsl", "expected_acceptance": "none",
        "applies": True, "why": "client-observable behavior"}
    # Balanced is the default autonomy: nothing waits on a light change.
    assert manifest["checkpoints"] == []
    assert [r["id"] for r in manifest["policy_rules_fired"]] == ["RP-EVID-LIGHT"]


def test_a_medium_change_writes_the_standard_evidence(tmp_path, path_writer):
    root = _project(tmp_path)
    manifest = _evaluate(root)
    _assert_path_keys(manifest)
    assert manifest["evidence_required"] == STANDARD
    assert [g["id"] for g in manifest["gates"]] == THREE + [
        "verify.regression", "verify.security", "verify.clarity"]
    assert manifest["acceptance_strategy"]["routing"] == "on"
    assert manifest["checkpoints"] == []
    fired = manifest["policy_rules_fired"]
    assert [r["id"] for r in fired] == ["RP-EVID-STANDARD"]
    assert fired[0]["kind"] == "evidence" and fired[0]["rationale"]


def test_a_live_defect_writes_the_hotfix_evidence_and_reproduce_first(tmp_path, path_writer):
    root = _project(tmp_path, size="small", urgency="live-defect")
    manifest = _evaluate(root)
    _assert_path_keys(manifest)
    expected = _expected(manifest["assessment"])
    assert manifest["evidence_required"] == expected["evidence_required"]
    assert "reproduce-first" in manifest["evidence_required"]
    assert "definition-of-done" in manifest["evidence_required"]
    assert [g["id"] for g in manifest["gates"]] == expected["gates"]
    assert manifest["acceptance_strategy"]["routing"] == "existing-dsl-isolation"
    assert [r["id"] for r in manifest["policy_rules_fired"]] == [
        "RP-EVID-DEFECT", "RP-EVID-REPRODUCE"]


def test_a_g5_label_owes_the_architecture_review_and_two_sign_offs(tmp_path, path_writer):
    root = _project(tmp_path, size="small", labels=["payments"])
    manifest = _evaluate(root)
    _assert_path_keys(manifest)
    expected = _expected(manifest["assessment"])
    assert manifest["evidence_required"] == expected["evidence_required"]
    for token in ("architecture", "scenario-approval", "human-approval"):
        assert token in manifest["evidence_required"], token
    assert "verify.architecture" in [g["id"] for g in manifest["gates"]]
    # `scenario-approval` lists the specify checkpoint under every autonomy value.
    assert manifest["checkpoints"] == ["specify"]
    ids = [r["id"] for r in manifest["policy_rules_fired"]]
    assert ids[0] == "RP-EVID-STANDARD"
    assert {"RP-REQUIRE-004", "RP-EVID-SIGNOFF", "G5"} <= set(ids)


def test_an_exploration_writes_the_spike_keys_and_no_evidence(tmp_path, path_writer):
    root = _project(tmp_path, goal="exploration", size="small")
    manifest = _evaluate(root)
    assert manifest["delivery_approach"] == "spike"
    assert "evidence_required" not in manifest
    assert isinstance(manifest["stages"], dict)
    assert [g["id"] for g in manifest["gates"]] == ["spike.conclude"]


# --- the checkpoints each autonomy value lists (ADR-092 open question 7) --------------

@pytest.mark.parametrize("autonomy, evidence, applies, listed", [
    ("controlled", LIGHT, True, ["assess", "specify", "build", "ship"]),
    ("controlled", LIGHT, False, ["assess", "specify"]),
    ("balanced", STANDARD, True, []),
    ("autonomous", STANDARD, True, []),
    ("balanced", STANDARD + ["scenario-approval"], True, ["specify"]),
    ("autonomous", STANDARD + ["scenario-approval"], False, ["specify"]),
])
def test_the_checkpoints_follow_the_autonomy_and_the_evidence(autonomy, evidence, applies,
                                                               listed):
    from compass_pkg import path_writer
    assert path_writer.checkpoints_for(evidence, autonomy, applies) == listed


# --- the switch off --------------------------------------------------------------------

def test_with_the_switch_off_the_manifest_is_exactly_the_8x_one(tmp_path, monkeypatch):
    monkeypatch.delenv("COMPASS_PATH_WRITER", raising=False)
    root = _project(tmp_path)
    manifest = _evaluate(root)
    manifest.pop("readiness")
    assessment = _assessment()
    assert manifest == {
        "schema_version": "3.0", "issue": "demo", "created": "2026-11-05",
        "assessment": assessment,
        "justifications": {k: f"the {k} was judged" for k in assessment if k != "labels"},
        "evaluated_assessment": assessment,
        "delivery_approach": "regular",
        "policy_rules_fired": [],
        "stages": {"assess": "thorough", "define": "thorough", "refine": "lightweight",
                   "plan": "thorough", "breakdown": "multiagent", "implement": "thorough",
                   "verify": "thorough", "ship": "thorough"},
        "checkpoints": ["define", "plan"],
        "checkpoint_outcomes": [],
        "acceptance_strategy": {"state": "on", "routing": "on", "expected_acceptance": "none",
                                "applies": True, "why": "client-observable behavior"},
        "gates": [{"id": g, "status": "pending", "evidence": []} for g in (
            THREE + ["verify.regression", "verify.clarity", "verify.security"])],
        "evidence": [],
        "subtask_ceiling": 2,
        "generation": 1,
    }


# --- a re-assess moves an old issue onto the path ------------------------------------

def test_a_reassess_moves_an_old_issue_onto_the_path(tmp_path, monkeypatch):
    monkeypatch.delenv("COMPASS_PATH_WRITER", raising=False)
    root = _project(tmp_path)
    old = _evaluate(root)
    assert old["delivery_approach"] == "regular" and "stages" in old

    env_on = {"COMPASS_PATH_WRITER": "1"}
    monkeypatch.setenv(*next(iter(env_on.items())))
    moved = _evaluate(root, "--reason", "move the issue onto the four-stage path")
    _assert_path_keys(moved)
    assert moved["evidence_required"] == STANDARD
    entry = moved["reassessments"][-1]
    assert (entry["from_route"], entry["to_route"]) == ("regular", "delivery")
    assert entry["reason"] == "move the issue onto the four-stage path"
    assert entry["generation"] == {"from": 1, "to": 2}
    assert "stages" in entry["changed"]


# --- what the person reads -------------------------------------------------------------

def test_approach_show_prints_the_evidence_line_on_a_path_issue(tmp_path, path_writer):
    root = _project(tmp_path, size="small")
    _evaluate(root)
    shown = _run(root, "approach", "show", "--issue", "demo")
    assert shown.returncode == 0, shown.stderr
    lines = shown.stdout.splitlines()
    assert lines[0].startswith("Approach: delivery (risk contained")
    assert lines[1] == "Evidence: " + ", ".join(LIGHT)
    assert lines[2].startswith("Writes: .compass/work/demo/")


def test_approach_show_keeps_the_gate_line_on_an_old_issue(tmp_path, monkeypatch):
    monkeypatch.delenv("COMPASS_PATH_WRITER", raising=False)
    root = _project(tmp_path, size="small")
    _evaluate(root)
    shown = _run(root, "approach", "show", "--issue", "demo")
    assert shown.stdout.splitlines()[1] == "Gates: " + ", ".join(THREE)


def test_check_gives_a_verdict_on_a_fresh_path_issue(tmp_path, path_writer):
    root = _project(tmp_path)
    _evaluate(root)
    checked = _run(root, "check", "--issue", "demo")
    assert checked.returncode in (0, 1), checked.stdout + checked.stderr
    assert "Traceback" not in checked.stderr
    assert checked.stdout.strip()


def test_evaluate_json_names_the_evidence_on_the_path(tmp_path, path_writer):
    import json
    root = _project(tmp_path, size="small")
    out = _run(root, "approach", "evaluate", "--issue", "demo", "--json")
    assert out.returncode == 0, out.stderr
    doc = json.loads(out.stdout)
    assert doc["delivery_approach"] == "delivery"
    # A preview reads the governance files of a project with no `compass.yml`,
    # which declare no `S17` strategy, so it owes no outer loop yet.
    assert doc["evidence_required"] == EVERY_ISSUE
    for key in LEGACY_ONLY:
        assert key not in doc, key


# --- `next:` after each verb that writes a record ------------------------------------

GREETING_TEST = ("import pathlib\n\n\n"
                 "def test_greeting_says_hello():\n"
                 "    p = pathlib.Path(__file__).resolve().parent.parent / 'greeting.txt'\n"
                 "    assert p.read_text().strip() == 'Hello'\n")
TEST_ID = "tests/test_greeting.py::test_greeting_says_hello"
TEST_CMD = ["--", sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", TEST_ID]


def _greeting_project(tmp_path):
    root = _project(tmp_path, size="small")
    (root / "tests").mkdir()
    (root / "tests" / "test_greeting.py").write_text(GREETING_TEST)
    (root / "greeting.txt").write_text("Hi\n")
    return root


def _last_line(result):
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _verb_lines(root):
    """The last stdout line of `scenario add`, `tdd-red` and `tdd-green`, in order."""
    added = _run(root, "scenario", "add", "TRC-001", "--issue", "demo", "--title",
                 "Given the greeting, when it is read, then it says Hello",
                 "--intent", "INT-1", "--test", TEST_ID)
    assert added.returncode == 0, added.stdout + added.stderr
    red = _run(root, "tdd-red", "--issue", "demo", "--scenario", "TRC-001",
               "--loop", "inner", *TEST_CMD)
    assert red.returncode == 0, red.stdout + red.stderr
    (root / "greeting.txt").write_text("Hello\n")
    green = _run(root, "tdd-green", "--issue", "demo", "--scenario", "TRC-001",
                 "--loop", "inner", *TEST_CMD)
    assert green.returncode == 0, green.stdout + green.stderr
    return [_last_line(added), _last_line(red), _last_line(green)]


def test_each_verb_that_writes_a_record_ends_with_the_next_command(tmp_path, path_writer):
    root = _greeting_project(tmp_path)
    _evaluate(root)
    added, red, green = _verb_lines(root)
    # The light row owes the outer loop, so the next command after the first
    # scenario and its inner red is the outer-loop red.
    assert added == ("next: compass tdd-red --loop outer --scenario TRC-001 "
                     "-- <acceptance test command>")
    assert red == added
    assert green == added


def test_no_next_line_on_an_old_issue(tmp_path, monkeypatch):
    monkeypatch.delenv("COMPASS_PATH_WRITER", raising=False)
    root = _greeting_project(tmp_path)
    _evaluate(root)
    for line in _verb_lines(root):
        assert not line.startswith("next: "), line


def test_json_output_has_no_next_line(tmp_path, path_writer):
    import json
    root = _greeting_project(tmp_path)
    _evaluate(root)
    added = _run(root, "scenario", "add", "TRC-001", "--issue", "demo", "--title",
                 "Given the greeting, when it is read, then it says Hello",
                 "--intent", "INT-1", "--test", TEST_ID, "--json")
    assert added.returncode == 0, added.stderr
    assert "next" not in json.loads(added.stdout)
