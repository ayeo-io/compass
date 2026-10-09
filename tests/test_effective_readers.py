"""The readers of configuration read the stored generation.

An issue with a generation is judged by its generation, not by the live
governance files. These tests build a scratch project, commit a generation
with the real command and run the real functions or CLI against it.

Scenario ids: `EF-1` to `EF-12` (issue `effective-readers`). Each test name
starts with its scenario id.
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

from test_generation_store import (SLUG, _committed_project, _manifest, _project,  # noqa: E402
                                   _run, _write_manifest)

SHIPPED = ROOT / "governance"


def _shipped(name):
    return yaml.safe_load((SHIPPED / name).read_text(encoding="utf-8"))


# --- EF-1: the reader helper ---------------------------------------------------------------

def test_ef_1_no_generation_and_no_compass_yml_reads_the_governance_files(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir = _project(tmp_path)
    monkeypatch.chdir(root)
    assert effective.view_or_legacy(str(task_dir)) is None
    assert effective.view_or_legacy(None) is None


def test_ef_1_a_generation_gives_the_stored_view(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir = _committed_project(tmp_path)
    monkeypatch.chdir(root)
    view = effective.view_or_legacy(str(task_dir))
    assert (view.source, view.generation) == ("generation", 1)


def test_ef_1_generation_zero_refuses_and_names_the_fix(tmp_path, monkeypatch):
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    root, task_dir = _project(tmp_path)
    _write_manifest(task_dir, generation=0)
    monkeypatch.chdir(root)
    with pytest.raises(CompassError) as caught:
        effective.view_or_legacy(str(task_dir))
    assert "compass approach evaluate --write" in str(caught.value)


def test_ef_1_a_compass_yml_gives_a_live_view_with_or_without_an_issue(tmp_path, monkeypatch):
    from compass_pkg import effective
    root, task_dir = _project(tmp_path, compass_yml={"schema": 1})
    monkeypatch.chdir(root)
    assert effective.view_or_legacy(str(task_dir)).source == "live"
    assert effective.view_or_legacy(None).source == "live"


# --- EF-2: the accessors equal the governance files for the shipped default -----------------

ASSESSMENTS = (
    {"risk": "contained", "size": "small", "labels": []},
    {"risk": "critical", "size": "large", "labels": ["auth"]},
    {"risk": "trivial", "size": "atomic", "labels": ["payments"]},
)


def _stored(tmp_path, monkeypatch):
    """The view of a committed generation of the shipped default."""
    root, task_dir = _committed_project(tmp_path)
    monkeypatch.chdir(root)
    from compass_pkg import effective
    return effective.view_or_legacy(str(task_dir))


def test_ef_2_guardrail_gates_equal_the_guardrails_file(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch)
    legacy = _shipped("guardrails.yml")
    from compass_pkg.core import reading_matches
    got = stored.guardrail_gates()
    for group in ("defaults", "spike_guardrails"):
        want = [(g["id"], g["name"], list(g["checks"])) for g in legacy[group]]
        have = [(g["id"], g["name"], list(g["checks"])) for g in got[group]]
        assert have == want, group
    assert got["project"] == []
    for old, new in zip(legacy["defaults"], got["defaults"]):
        for assessment in ASSESSMENTS:
            old_applies = reading_matches(old.get("applies_when"), assessment)
            assert stored.matches(new.get("applies_when"), assessment) == old_applies, old["id"]
    for name, body in (legacy.get("checks") or {}).items():
        assert ("blocking_when" in body) == ("blocking_when" in got["checks"].get(name, {})), name
        if "blocking_when" in body:
            for assessment in ASSESSMENTS:
                assert (stored.matches(got["checks"][name]["blocking_when"], assessment)
                        == reading_matches(body["blocking_when"], assessment)), name


def test_ef_2_gate_requirements_equal_the_guardrails_file(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch)
    legacy = _shipped("guardrails.yml")
    requirements, known = stored.gate_requirements()
    assert requirements == {k: list(v) for k, v in legacy["gate_evidence_requirements"].items()}
    assert known == set(legacy["evidence_types"])


def test_ef_2_loop_ceiling_rules_equal_the_policy_file(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch)
    legacy = _shipped("routing-policy.yml")["routing_guardrails"]["loop_ceilings"]
    got = stored.loop_ceiling_rules()
    assert [(r["id"], r["ceiling"], r["limit"]) for r in got] == [
        (r["id"], r["ceiling"], r["limit"]) for r in legacy]
    from compass_pkg.core import reading_matches
    for old, new in zip(legacy, got):
        for assessment in ASSESSMENTS:
            assert stored.matches(new.get("when"), assessment) == reading_matches(
                old.get("when"), assessment), old["id"]


def test_ef_2_the_shipped_default_holds_no_command_check(tmp_path, monkeypatch):
    stored = _stored(tmp_path, monkeypatch)
    assert stored.command_checks() == []


# --- helpers for the commands ---------------------------------------------------------------

def _check_json(root, *extra):
    code, out, err = _run(root, "check", "--issue", SLUG, "--json", *extra)
    return code, json.loads(out), err


def _guardrail_ids(report):
    return {c["guardrail"] for c in report["checks"]}


def _copy_governance(root):
    """The project keeps its own copies of the two governance files."""
    folder = root / "governance"
    folder.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        (folder / name).write_text((SHIPPED / name).read_text(encoding="utf-8"),
                                   encoding="utf-8")
    return folder


# --- EF-3: check judges an issue by its generation ------------------------------------------

def test_ef_3_editing_the_governance_files_does_not_change_the_verdict(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    _, before, _ = _check_json(root)
    assert {"G1", "G2", "G3", "G4"} <= _guardrail_ids(before)
    guardrails = yaml.safe_load((folder / "guardrails.yml").read_text(encoding="utf-8"))
    guardrails["defaults"] = [g for g in guardrails["defaults"] if g["id"] not in ("G2", "G3")]
    (folder / "guardrails.yml").write_text(yaml.safe_dump(guardrails, sort_keys=False),
                                           encoding="utf-8")
    _, after, _ = _check_json(root)
    assert _guardrail_ids(after) == _guardrail_ids(before)
    assert after["checks"] == before["checks"]


def test_ef_3_an_issue_with_no_generation_still_reads_the_edited_files(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    guardrails = yaml.safe_load((folder / "guardrails.yml").read_text(encoding="utf-8"))
    guardrails["defaults"] = [g for g in guardrails["defaults"] if g["id"] != "G2"]
    (folder / "guardrails.yml").write_text(yaml.safe_dump(guardrails, sort_keys=False),
                                           encoding="utf-8")
    _, report, _ = _check_json(root)
    assert "G2" not in _guardrail_ids(report) and "G1" in _guardrail_ids(report)


# --- EF-4: a command check from the generation ------------------------------------------------

COMMAND_PROJECT = {
    "schema": 1, "allow_project_commands": True,
    "checks": {"arch-rule": {
        "statement": "A project rule.", "kind": "deterministic", "impl": "command-passes",
        "severity": "blocking", "on_skipped": "fail",
        "params": {"command": "touch ran.flag"}}},
    "gates": {"P1": {
        "kind": "guardrail", "name": "Project rule", "statement": "A project rule.",
        "stage": "verify", "applies_to": {"ships": True}, "checks": ["arch-rule"]}},
}


def test_ef_4_a_check_with_its_own_id_runs_its_command_from_the_generation(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml=COMMAND_PROJECT)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    (root / "compass.yml").unlink()
    (root / ".compass" / "config.yml").write_text("allow_project_commands: true\n",
                                                  encoding="utf-8")
    _, report, _ = _check_json(root)
    rows = [c for c in report["checks"] if c["guardrail"] == "P1"]
    assert [c["name"] for c in rows] == ["arch-rule"], report
    assert rows[0]["status"] == "pass", rows
    assert (root / "ran.flag").exists()
    assert not any(c["detail"].endswith("NO CLI implementation") for c in report["checks"])


def test_ef_4_a_project_guardrail_of_a_copied_governance_file_runs_from_the_generation(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    _edit_guardrails(folder, lambda body: body.update(project=[{
        "id": "ARCH-1", "name": "Layer rule", "statement": "A rule.", "checks": ["command-passes"],
        "params": {"command": "touch ran.flag"}}]))
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nallow_project_commands: true\n",
                                                  encoding="utf-8")
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    (folder / "guardrails.yml").unlink()
    (folder / "routing-policy.yml").unlink()
    _, report, _ = _check_json(root)
    rows = [c for c in report["checks"] if c["guardrail"] == "ARCH-1"]
    assert rows and all(c["status"] == "pass" for c in rows), report
    assert (root / "ran.flag").exists()


PROJECT_GUARDRAILS = [
    {"id": "PG-A", "name": "Needs tests", "statement": "A project rule.",
     "checks": ["scenarios-have-tests"]},
    {"id": "PG-E", "name": "Command and suite", "statement": "A project rule.",
     "checks": ["command-passes", "suite-passed"], "params": {"command": "true"}},
]


def _project_rows(report):
    return sorted((c["guardrail"], c["name"], c["status"]) for c in report["checks"]
                  if c["guardrail"].startswith("PG-"))


def _project_with_guardrails(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    _edit_guardrails(folder, lambda body: body.update(project=PROJECT_GUARDRAILS))
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nallow_project_commands: true\n",
                                                  encoding="utf-8")
    return root, task_dir, folder


def test_ef_4_every_project_guardrail_shows_the_same_rows_before_and_after_a_commit(tmp_path):
    root, task_dir, folder = _project_with_guardrails(tmp_path)
    _, before, _ = _check_json(root)
    rows = _project_rows(before)
    assert [r[:2] for r in rows] == [("PG-A", "scenarios-have-tests"),
                                     ("PG-E", "command-passes"), ("PG-E", "suite-passed")], rows
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    for name in ("guardrails.yml", "routing-policy.yml"):
        (folder / name).unlink()
    _, after, _ = _check_json(root)
    # The command check is named for its own id once stored; the rows and their
    # verdicts are the same.
    assert [(g, v) for g, _, v in _project_rows(after)] == [(g, v) for g, _, v in rows]
    assert [n for _, n, _ in _project_rows(after)] == [
        "scenarios-have-tests", "PG-E-command-and-suite", "suite-passed"]


def test_ef_4_the_shipped_coverage_floor_example_is_refused_not_misreported(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    _edit_guardrails(folder, lambda body: body.update(project=[{
        "id": "Q1", "name": "Coverage floor", "statement": "Line coverage does not drop.",
        "checks": ["coverage-floor"], "params": {"min_line_coverage": 80},
        "checked_at": ["verify"]}]))
    _, before, _ = _check_json(root)
    rows = [c for c in before["checks"] if c["guardrail"] == "Q1"]
    assert [(c["name"], c["status"]) for c in rows] == [("coverage-floor", "fail")]
    assert "NO CLI implementation" in rows[0]["detail"], rows
    # The commit refuses a check nothing implements, and writes nothing.
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 2 and "coverage-floor" in err and "nothing was written" in err, out + err
    assert not (task_dir / "generations").exists()


def test_ef_4_a_project_guardrail_gate_stores_its_stage_and_its_checks(tmp_path):
    import yaml as _yaml
    root, task_dir, folder = _project_with_guardrails(tmp_path)
    guardrails = _yaml.safe_load((folder / "guardrails.yml").read_text(encoding="utf-8"))
    guardrails["project"][0]["checked_at"] = ["verify"]
    (folder / "guardrails.yml").write_text(_yaml.safe_dump(guardrails, sort_keys=False),
                                           encoding="utf-8")
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    stored = _yaml.safe_load((task_dir / "generations" / "1" / "resolved.yml")
                             .read_text(encoding="utf-8"))
    assert stored["gates"]["PG-A"]["stage"] == "verify"
    assert stored["gates"]["PG-E"]["checks"] == ["PG-E-command-and-suite", "suite-passed"]
    assert stored["checks"]["PG-E-command-and-suite"]["params"] == {"command": "true"}


# --- EF-3 (continued): a copy that omits what the framework ships is still reported ----------

def _copy_missing_a_default(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    _edit_guardrails(folder, lambda body: body.update(
        defaults=[g for g in body["defaults"] if g["id"] != "G2"]))
    return root, task_dir, folder


def test_ef_3_a_guardrail_missing_from_a_governance_copy_is_reported_with_or_without_a_generation(tmp_path):
    root, task_dir, folder = _copy_missing_a_default(tmp_path)
    code, before, err = _run(root, "check", "--issue", SLUG)
    assert "G2" in before and "ABSENT" in before, before + err
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    code, after, err = _run(root, "check", "--issue", SLUG)
    assert "G2" in after and "ABSENT" in after, after + err
    other = tmp_path / "other"
    other.mkdir()
    code, plain, err = _run(_project(other)[0], "check", "--issue", SLUG)
    assert "ABSENT" not in plain, plain


def test_ef_3_policy_drift_is_reported_by_evaluate_with_or_without_a_generation(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    _edit_policy(folder, lambda body: body["routing_guardrails"]["floors"].pop())
    code, before, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--verbose")
    assert "POLICY DRIFT" in before, before + err
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    code, after, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--verbose")
    assert "POLICY DRIFT" in after, after + err


# --- EF-9: the verdict header and the pending change ------------------------------------------

def test_ef_9_check_names_the_generation_and_the_parent_version(tmp_path):
    root, task_dir = _committed_project(tmp_path)
    versions = yaml.safe_load((task_dir / "generations" / "1" / "versions.yml")
                              .read_text(encoding="utf-8"))
    parent = versions["parents"][0]["version"]
    code, out, err = _run(root, "check", "--issue", SLUG)
    assert f"generation 1 (parent {parent})" in out, out + err
    code, out, err = _run(root, "check", "--issue", SLUG, "--verbose")
    assert f"generation 1 (parent {parent})" in out, out + err
    code, out, err = _run(root, "check", "--issue", SLUG, "--json")
    document = json.loads(out)
    assert (document["generation"], document["parent_version"]) == (1, parent)


def test_ef_9_a_changed_config_is_a_pending_change_that_does_not_fail(tmp_path):
    root, task_dir = _committed_project(tmp_path)
    code, clean, _ = _run(root, "check", "--issue", SLUG)
    assert "pending" not in clean
    _write_manifest(task_dir, config={"checks": {"extra": {
        "statement": "A check.", "kind": "deterministic", "impl": "suite-passed",
        "severity": "advisory", "on_skipped": "fail"}}})
    code2, out, err = _run(root, "check", "--issue", SLUG)
    assert "pending" in out and "config:" in out, out + err
    assert "compass approach evaluate --write" in out
    assert code2 == code


def test_ef_9_an_issue_with_no_generation_prints_neither_line(tmp_path):
    root, task_dir = _project(tmp_path)
    for flags in ((), ("--verbose",), ("--json",)):
        code, out, err = _run(root, "check", "--issue", SLUG, *flags)
        assert "generation" not in out and "pending" not in out, out + err


# --- EF-10: compass ci carries on past an issue at generation 0 -------------------------------

def test_ef_10_ci_reports_an_issue_at_generation_zero_and_checks_the_next(tmp_path):
    root, first = _project(tmp_path, slug="a-waiting")
    _, second = _project(tmp_path, slug="b-healthy")
    _write_manifest(first, generation=0)
    code, out, err = _run(root, "ci")
    assert code == 1, out + err
    waiting, healthy = out.split("[issue] b-healthy")
    assert "generation 0" in waiting and "compass approach evaluate --write" in waiting, out
    assert "compass check" in healthy or "check(s)" in healthy, out
    assert "compass ci: FAIL" in out


# --- EF-10: no generation, same output ----------------------------------------------------------

def test_ef_10_check_on_an_issue_with_no_generation_matches_the_legacy_reading(tmp_path):
    root, task_dir = _project(tmp_path)
    _, report, _ = _check_json(root)
    guardrails = _shipped("guardrails.yml")
    expected = {g["id"] for g in guardrails["defaults"]}
    assert _guardrail_ids(report) - {""} <= expected
    assert "G1" in _guardrail_ids(report)
    assert "generations" not in {p.name for p in task_dir.iterdir()}


# --- EF-5: evidence requirements from the generation ------------------------------------------

def _edit_guardrails(folder, edit):
    path = folder / "guardrails.yml"
    body = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(body)
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def _with_artifact_evidence(task_dir):
    _write_manifest(
        task_dir,
        evidence=[{"id": "EV-A", "type": "artifact", "path": "evidence/a.md"}],
        gates=[{"id": "verify.correctness", "status": "pending", "evidence": []}])


def _widen_correctness(body):
    body["gate_evidence_requirements"]["verify.correctness"] = ["test-run", "artifact"]
    body["evidence_types"]["custom-type"] = {"description": "A type added after the commit."}


def test_ef_5_gate_pass_refuses_the_type_the_generation_does_not_accept(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    _with_artifact_evidence(task_dir)
    _edit_guardrails(folder, _widen_correctness)
    code, out, err = _run(root, "gate", "pass", "verify.correctness", "--issue", SLUG,
                          "--evidence", "EV-A")
    assert code != 0 and "accepts evidence of type ['test-run']" in err, out + err
    code, out, err = _run(root, "evidence", "add", "EV-B", "--issue", SLUG,
                          "--type", "custom-type", "--path", "evidence/b.md")
    assert code != 0 and "not a known evidence type" in err, out + err


def test_ef_5_an_issue_with_no_generation_reads_the_widened_file(tmp_path):
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    _with_artifact_evidence(task_dir)
    _edit_guardrails(folder, _widen_correctness)
    code, out, err = _run(root, "gate", "pass", "verify.correctness", "--issue", SLUG,
                          "--evidence", "EV-A")
    assert code == 0, out + err


def test_ef_5_the_receipt_flags_a_type_the_generation_does_not_accept(tmp_path):
    root, task_dir = _committed_project(tmp_path)
    _write_manifest(
        task_dir,
        evidence=[{"id": "EV-A", "type": "artifact", "path": "evidence/a.md"}],
        gates=[{"id": "verify.correctness", "status": "pass", "evidence": ["EV-A"]}])
    code, out, err = _run(root, "issue", "receipt", "--issue", SLUG)
    assert "TYPE-MISMATCH" in out, out + err


def test_ef_5_the_accepts_comments_come_from_the_configuration_committed(tmp_path):
    changed = {"schema": 1, "gates": {"verify.security": {"set": {"accepts": ["security-review"]}}}}
    root, task_dir = _project(tmp_path, compass_yml=changed)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    manifest_text = (task_dir / "manifest.yml").read_text(encoding="utf-8")
    stored = yaml.safe_load((task_dir / "generations" / "1" / "resolved.yml")
                            .read_text(encoding="utf-8"))
    assert stored["gates"]["verify.security"]["accepts"] == ["security-review"]
    comments = [l.strip() for l in manifest_text.splitlines() if "# accepts" in l]
    assert "# accepts: ['security-review']" in comments, comments


# --- EF-6: approach evaluate from the generation ------------------------------------------------

def _evaluate_json(root, slug=SLUG):
    code, out, err = _run(root, "approach", "evaluate", "--issue", slug, "--json")
    assert code == 0, out + err
    return json.loads(out)


def _edit_policy(folder, edit):
    path = folder / "routing-policy.yml"
    body = yaml.safe_load(path.read_text(encoding="utf-8"))
    edit(body)
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")


def _add_gate(body):
    body["route_shapes"]["regular"]["gates"].append("verify.analyze")


def test_ef_6_the_result_matches_the_one_the_governance_files_give(tmp_path):
    root, task_dir = _project(tmp_path)
    _project(tmp_path, slug="other")
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    assert _evaluate_json(root) == _evaluate_json(root, "other")


def test_ef_6_editing_the_live_policy_does_not_change_the_issue_with_a_generation(tmp_path):
    root, task_dir = _project(tmp_path)
    _project(tmp_path, slug="other")
    folder = _copy_governance(root)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    before = _evaluate_json(root)
    _edit_policy(folder, _add_gate)
    assert _evaluate_json(root) == before
    assert "verify.analyze" in _evaluate_json(root, "other")["gates"]
    assert "verify.analyze" not in before["gates"]


def test_ef_6_the_autonomy_is_the_one_the_generation_stored(tmp_path):
    root, task_dir = _project(tmp_path)
    _project(tmp_path, slug="other")
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    before = _evaluate_json(root)
    assert before["checkpoints"], before
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nautonomy: autonomous\n",
                                                  encoding="utf-8")
    assert _evaluate_json(root) == before
    assert _evaluate_json(root, "other")["checkpoints"] != before["checkpoints"]


# --- EF-7: loop ceilings from the generation -----------------------------------------------------

def _ceiling_rule(rules, ceiling):
    return next(r for r in rules if r["ceiling"] == ceiling)


def test_ef_7_the_ceiling_in_force_is_the_one_the_generation_stored(tmp_path, monkeypatch):
    from compass_pkg import loop_ceilings
    root, task_dir = _project(tmp_path)
    folder = _copy_governance(root)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write")
    assert code == 0, out + err
    task = _manifest(task_dir)
    monkeypatch.chdir(root)
    stored = loop_ceilings.loop_ceilings(task, str(task_dir))
    assert stored

    def lower(body):
        for rule in body["routing_guardrails"]["loop_ceilings"]:
            rule["limit"] = 1
    _edit_policy(folder, lower)
    assert loop_ceilings.loop_ceilings(task, str(task_dir)) == stored
    assert loop_ceilings.loop_ceilings(task) != stored
    assert {limit for limit, _ in loop_ceilings.loop_ceilings(task).values()} == {1}


def test_ef_7_the_callers_pass_the_issue(tmp_path):
    import re
    for name in ("subtasks", "run_cmd", "multiagent_check"):
        text = (ROOT / "cli" / "compass_pkg" / f"{name}.py").read_text(encoding="utf-8")
        calls = re.findall(r"\bloop_ceilings\(([^)]*)\)", text)
        calls = [c for c in calls if c.strip() and "def " not in c]
        assert calls and all("task_dir" in c for c in calls), (name, calls)


# --- EF-8: readers with no issue ------------------------------------------------------------------

LAYERED = {
    "schema": 1,
    "checks": {"p-rule": {"statement": "A rule.", "kind": "deterministic",
                          "impl": "suite-passed", "severity": "blocking", "on_skipped": "fail"}},
    "gates": {"PX": {"kind": "guardrail", "name": "Project rule", "statement": "A rule.",
                     "stage": "verify", "applies_to": {"ships": True}, "checks": ["p-rule"]}},
    "rules": {"floors": {"set": {"rules": {"set": {"RP-PROJECT-FLOOR": {
        "order": 99, "when": {"labels_any": ["zzz-label"]},
        "then": {"force_minimum_approach": "full"}, "rationale": "A project floor."}}}}}},
}


def test_ef_8_lessons_refuse_a_guardrail_the_compass_yml_adds(tmp_path, monkeypatch):
    from compass_pkg import lessons
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    monkeypatch.chdir(root)
    assert "PX" in lessons._refusal("never skip PX", "user")
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / ".compass").mkdir()
    monkeypatch.chdir(plain)
    assert lessons._refusal("never skip PX", "user") is None


def test_ef_8_review_rules_know_the_guardrail_the_compass_yml_adds(tmp_path):
    from compass_pkg import review_rules
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    gov = root / "governance"
    gov.mkdir()
    rule = {"id": "RR-001", "blocking": True, "file_patterns": ["cli/*.py"], "enforces": "PX",
            "rule": "Keep it.", "incident": "An incident."}
    (gov / "review-rules.yml").write_text(yaml.safe_dump({"rules": [rule]}), encoding="utf-8")
    assert review_rules.lint_errors(str(gov)) == []
    plain = tmp_path / "plain"
    (plain / "governance").mkdir(parents=True)
    (plain / ".compass").mkdir()
    (plain / "governance" / "review-rules.yml").write_text(
        yaml.safe_dump({"rules": [rule]}), encoding="utf-8")
    for name in ("routing-policy.yml", "guardrails.yml"):
        (plain / "governance" / name).write_text((SHIPPED / name).read_text(encoding="utf-8"),
                                                 encoding="utf-8")
    assert any("PX" in e for e in review_rules.lint_errors(str(plain / "governance")))


def test_ef_8_flow_knows_the_label_the_compass_yml_names(tmp_path, monkeypatch):
    from compass_pkg import flow
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    monkeypatch.chdir(root)
    assert "zzz-label" in flow._routing_labels()
    plain = tmp_path / "plain"
    (plain / ".compass").mkdir(parents=True)
    monkeypatch.chdir(plain)
    assert "zzz-label" not in flow._routing_labels()
    assert "auth" in flow._routing_labels()


def test_ef_8_retro_weights_come_from_the_effective_policy(tmp_path, monkeypatch):
    from compass_pkg import calibration
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    monkeypatch.chdir(root)
    layered = calibration._route_weights()
    assert layered and layered["regular"] == _shipped("routing-policy.yml")[
        "route_shapes"]["regular"]["weight"]
    plain = tmp_path / "plain"
    (plain / ".compass").mkdir(parents=True)
    monkeypatch.chdir(plain)
    assert calibration._route_weights() == layered


def test_ef_8_quick_fix_blockers_read_the_policy_through_effective(tmp_path, monkeypatch):
    from compass_pkg import effective, quick_fix_cmd
    root, _ = _project(tmp_path, compass_yml=LAYERED)
    monkeypatch.chdir(root)
    readings = {"risk": "critical", "familiarity": "brownfield-mapped", "size": "standard",
                "labels": []}
    asked = []
    real = effective.view_or_legacy
    monkeypatch.setattr(effective, "view_or_legacy",
                        lambda *a, **k: asked.append(a) or real(*a, **k))
    layered = quick_fix_cmd._quick_fix_blockers(readings, {})
    assert asked, "the blockers did not ask the effective view"
    assert any(line.startswith("blocked: risk is critical") for line in layered), layered
    monkeypatch.undo()
    plain = tmp_path / "plain"
    (plain / ".compass").mkdir(parents=True)
    monkeypatch.chdir(plain)
    assert quick_fix_cmd._quick_fix_blockers(readings, {}) == layered


# --- EF-11: every read of a governance policy file is in a function that asks effective ----

import ast  # noqa: E402
import re  # noqa: E402

PACKAGE = ROOT / "cli" / "compass_pkg"
POLICY_READ = re.compile(r"os\.path\.join\([^\n]*[\"'](routing-policy|guardrails)\.yml[\"']")

#: Modules that may name a policy file without reading it for an issue: the
#: loaders of the files themselves, the lint, the migration (which reads a
#: project's copies to convert them), the views generated from the preset and
#: the text of help messages.
POLICY_FILE_OWNERS = frozenset({
    "core", "effective", "governance", "legacy_adapter", "legacy_views",
    "legacy_views_template", "policy_cmd", "policy_migrate", "project_commands",
    "verb_help"})

#: Each read of a policy file outside the owners: `(module, function)` and how
#: many reads that function makes. Every one of these functions asks
#: `view_or_legacy` first, and a new read, or a second read in one of them, fails.
EXPECTED_READS = {
    ("approach_diagram", "cmd_approach_diagram"): 1, ("calibration", "_route_weights"): 1,
    ("check_cmd", "cmd_check"): 2, ("checks", "_check_gate_evidence"): 1,
    ("github_labels", "declared_labels"): 1,
    ("checks", "_check_command_passes"): 1, ("flow", "_routing_labels"): 1,
    ("lessons", "_guardrail_ids"): 1, ("loop_ceilings", "loop_ceilings"): 1,
    ("manifest", "_load_gate_requirements"): 1, ("quick_fix_cmd", "_quick_fix_blockers"): 1,
    ("quick_fix_cmd", "cmd_quick_fix_start"): 1, ("receipt", "_receipt_gate_requirements"): 1,
    ("review_rules", "_known_ids"): 1, ("routing", "cmd_route_evaluate"): 2,
}


def _reads(name, text):
    """`{function: [line, ...]}` for each read of a policy file in `text`, and
    the functions whose body does not mention `view_or_legacy`."""
    tree = ast.parse(text)
    lines = text.splitlines()
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    found, unguarded = {}, set()
    for number, line in enumerate(lines, 1):
        if not POLICY_READ.search(line):
            continue
        enclosing = sorted((n for n in functions if n.lineno <= number <= n.end_lineno),
                           key=lambda n: n.end_lineno - n.lineno)
        owner = enclosing[0] if enclosing else None
        key = owner.name if owner else "<module>"
        found.setdefault(key, []).append(number)
        body = "\n".join(lines[owner.lineno - 1:owner.end_lineno]) if owner else ""
        if "view_or_legacy" not in body:
            unguarded.add(key)
    return found, unguarded


def _all_reads():
    out = {}
    for path in PACKAGE.glob("*.py"):
        if path.stem in POLICY_FILE_OWNERS:
            continue
        found, unguarded = _reads(path.stem, path.read_text(encoding="utf-8"))
        for function, hits in found.items():
            out[(path.stem, function)] = (len(hits), function in unguarded)
    return out


def test_ef_11_every_read_of_a_policy_file_is_in_a_function_that_asks_effective_first():
    reads = _all_reads()
    assert {k for k, (_, bad) in reads.items() if bad} == set()
    assert {k: n for k, (n, _) in reads.items()} == EXPECTED_READS


def test_ef_11_the_scan_can_fail():
    direct = 'policy = load_yaml(os.path.join(find_governance(), "routing-policy.yml"))\n'
    guarded = ("def f():\n    view = effective.view_or_legacy()\n    if view is None:\n        "
               + direct.replace("\n", "") + "\n")
    found, unguarded = _reads("m", guarded)
    assert found == {"f": [4]} and unguarded == set()
    # A second read in a function beside a guarded one is caught by name.
    planted = guarded + "\n\ndef planted():\n    " + direct
    found, unguarded = _reads("m", planted)
    assert unguarded == {"planted"}
    # A real reader with a second read planted in its guarded function is caught
    # by the count; with its view lines removed, by the guard.
    text = (PACKAGE / "lessons.py").read_text(encoding="utf-8")
    assert _reads("lessons", text)[1] == set()
    assert _reads("lessons", text.replace("view_or_legacy", "something_else"))[1] == {
        "_guardrail_ids"}
    doubled = text.replace(
        "    try:\n        gr = load_yaml(os.path.join(find_governance(), \"guardrails.yml\"))",
        "    load_yaml(os.path.join(find_governance(), \"guardrails.yml\"))\n    try:\n"
        "        gr = load_yaml(os.path.join(find_governance(), \"guardrails.yml\"))")
    assert len(_reads("lessons", doubled)[0]["_guardrail_ids"]) == 2


# --- EF-11 (continued): the header comments name what a module imports -----------------------

def _compass_imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "compass_pkg":
                names |= {a.name for a in node.names}
            elif node.module.startswith("compass_pkg."):
                names.add(node.module.split(".")[1])
    return names


def test_ef_11_a_dependency_header_that_lists_modules_lists_every_one_imported():
    for name in ("loop_ceilings", "approach_diagram"):
        path = PACKAGE / f"{name}.py"
        header = next(line for line in path.read_text(encoding="utf-8").splitlines()
                      if "DEPENDENCY" in line)
        missing = [m for m in _compass_imports(path) if m not in header]
        assert missing == [], f"{name} imports {missing}, which its DEPENDENCY line omits"


def test_ef_11_the_obligations_header_names_every_module_that_imports_it():
    importers = sorted(p.stem for p in PACKAGE.glob("*.py")
                       if "obligations" in _compass_imports(p) and p.stem != "obligations")
    header = (PACKAGE / "obligations.py").read_text(encoding="utf-8")
    sentence = next(line for line in header.splitlines() if "import this module" in line)
    assert [m for m in importers if f"compass_pkg.{m}" not in sentence] == [], (
        importers, sentence)
