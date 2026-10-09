"""Diagnose one run from its issue's own records: the session-diagnosis
issue, GitHub issue #276.

`compass issue diagnose` reads the manifest and the evidence folder, and
reports each stage against the record that shows it ran, a timeline of the
dated records, the deviations, and what the records cannot show.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SLUG = "demo"
CREATED = "2026-10-01"
STAGES = {"assess": "full", "define": "full", "refine": "light", "plan": "full",
          "breakdown": "skipped", "implement": "full", "verify": "full", "ship": "full"}


def _compass(root: Path, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


def _record(evidence: Path, kind: str, scenario: str, when: str) -> None:
    (evidence / f"{kind}-{scenario}.json").write_text(json.dumps({
        "scenario": scenario, "timestamp": when, "passed": kind == "green",
        "exit_code": 0 if kind == "green" else 1}), encoding="utf-8")


def _issue(tmp_path: Path, *, good: bool) -> Path:
    """A feature issue. The good one has a record for every stage it ran.
    The bad one has no refine review, a red dated after its green, a green
    with no red, a failed review round, and a pending gate."""
    root = tmp_path / "proj"
    work = root / ".compass" / "work" / SLUG
    evidence = work / "evidence"
    evidence.mkdir(parents=True)
    docs = root / "docs" / "compass" / f"{CREATED}-{SLUG}"
    docs.mkdir(parents=True)
    for name in ("acceptance-criteria.md", "technical-design.md"):
        (docs / name).write_text("# x\n", encoding="utf-8")
    if good:
        (docs / "requirements-review.md").write_text("# x\n", encoding="utf-8")
    (work / "delivery-approach.md").write_text("# x\n", encoding="utf-8")
    (evidence / "review.md").write_text("Verdict: PASS\n", encoding="utf-8")

    _record(evidence, "red", "A", "2026-10-01T10:00:00+00:00")
    _record(evidence, "green", "A", "2026-10-01T11:00:00+00:00")
    if good:
        _record(evidence, "red", "B", "2026-10-01T10:30:00+00:00")
        _record(evidence, "green", "B", "2026-10-01T11:30:00+00:00")
    else:
        _record(evidence, "green", "B", "2026-10-01T11:30:00+00:00")
        _record(evidence, "red", "B", "2026-10-01T12:00:00+00:00")
        _record(evidence, "green", "C", "2026-10-01T12:30:00+00:00")

    manifest = {
        "schema_version": "2.0", "issue": SLUG, "created": CREATED,
        "status": "landed",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "standard", "goal": "delivery", "role": "engineer",
                       "labels": []},
        "delivery_approach": "feature", "stages": STAGES,
        "scenarios": [{"id": s, "title": f"Given {s}", "intent": "INT-1", "tests": []}
                      for s in ("A", "B", "C")],
        "evidence": [{"id": "EV-T-A", "type": "test-run", "path": "evidence/green-A.json",
                      "scenario": "A"}],
        "gates": [{"id": "verify.correctness", "status": "pass", "evidence": ["EV-T-A"]},
                  {"id": "verify.security", "status": "pass" if good else "pending",
                   "evidence": ["EV-T-A"] if good else []}],
        "artifacts": [
            {"id": "ART-ACCEPTANCE_CRITERIA", "kind": "acceptance-criteria", "status": "draft",
             "path": f"docs/compass/{CREATED}-{SLUG}/acceptance-criteria.md"},
            {"id": "ART-TECHNICAL_DESIGN", "kind": "technical-design", "status": "draft",
             "path": f"docs/compass/{CREATED}-{SLUG}/technical-design.md"}],
        "subtasks": [{"id": "subtask-1", "status": "done",
                      "dispatched_at": "2026-10-01T09:30:00+00:00",
                      "review_rounds": ([{"round": 1, "verdict": "pass",
                                          "at": "2026-10-01T13:00:00+00:00"}] if good else
                                        [{"round": 1, "verdict": "fail",
                                          "at": "2026-10-01T13:00:00+00:00"},
                                         {"round": 2, "verdict": "pass",
                                          "at": "2026-10-01T14:00:00+00:00"}])}],
        "reassessments": [] if good else [{"at": "2026-10-01T09:45:00+00:00",
                                           "reason": "bigger than it looked",
                                           "from": "quick fix", "to": "feature"}],
        "changed_files": [], "claims": [], "follow_ups": [], "friction": [],
        "land_timestamp": "2026-10-01T15:00:00+00:00", "land_commit": "abc1234",
    }
    (work / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                       encoding="utf-8")
    return root


def _section(out: str, title: str) -> str:
    part = out.split(f"\n{title}\n", 1)
    assert len(part) == 2, f"no {title!r} section:\n{out}"
    return part[1].split("\n\n", 1)[0]


def test_each_stage_names_the_record_that_shows_it(tmp_path):
    """SD-A."""
    root = _issue(tmp_path, good=True)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert r.returncode == 0, r.stdout + r.stderr
    stages = _section(r.stdout, "Stages")
    assert "refine" in stages and "requirements-review.md" in stages
    assert "plan" in stages and "technical-design.md" in stages
    assert "implement" in stages and "red-A.json" in stages
    assert "ship" in stages and "abc1234" in stages
    assert "breakdown" in stages and "skipped by the route" in stages
    gates = _section(r.stdout, "Gates")
    assert "verify.correctness" in gates and "pass" in gates and "EV-T-A" in gates


def test_a_manifest_in_old_words_is_shown_in_the_new_words(tmp_path):
    root = _issue(tmp_path, good=True)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert r.returncode == 0, r.stdout + r.stderr
    head = r.stdout.splitlines()[0]
    assert "(feature, done)" in head, head
    stages = _section(r.stdout, "Stages")
    assert "thorough" in stages and "lightweight" in stages, stages
    assert " full " not in stages and " light " not in stages, stages


def test_the_timeline_dates_every_record_oldest_first(tmp_path):
    """SD-B."""
    root = _issue(tmp_path, good=False)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    timeline = _section(r.stdout, "Timeline").splitlines()
    stamps = [line.split()[0] for line in timeline]
    assert stamps == sorted(stamps), timeline
    text = "\n".join(timeline)
    for fragment in ("subtask-1 dispatched", "reassessed", "red B", "green C",
                     "review round 1: fail", "landed"):
        assert fragment in text, fragment
    assert "evidence/red-B.json" in text


def test_a_good_run_has_no_deviation(tmp_path):
    """SD-C, the control: the deviations section is empty for a clean run."""
    root = _issue(tmp_path, good=True)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert "None found in the records." in _section(r.stdout, "Deviations")


def test_a_bad_run_lists_each_deviation(tmp_path):
    """SD-C."""
    root = _issue(tmp_path, good=False)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    dev = _section(r.stdout, "Deviations")
    assert "refine" in dev and "no record" in dev
    assert "B" in dev and "after its green" in dev
    assert "review round 1 failed" in dev
    assert "verify.security" in dev and "pending" in dev


def test_a_declared_acceptance_is_not_a_missing_red(tmp_path):
    """SD-C: acceptance declared without a red is not a deviation."""
    root = _issue(tmp_path, good=True)
    evidence = root / ".compass" / "work" / SLUG / "evidence"
    _record(evidence, "green", "C", "2026-10-01T12:30:00+00:00")
    (evidence / "acceptance-baseline.json").write_text("{}", encoding="utf-8")
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert "None found in the records." in _section(r.stdout, "Deviations")


def test_the_report_says_what_the_records_cannot_show(tmp_path):
    """SD-D."""
    root = _issue(tmp_path, good=True)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    tail = r.stdout.split("\nThe records cannot show\n", 1)
    assert len(tail) == 2, r.stdout
    for fragment in ("interruptions.log keeps only its time and kind", "transcript", "gate",
                     "review round is dated when it was recorded", "token use outside"):
        assert fragment in tail[1], fragment


def test_it_writes_nothing(tmp_path):
    """SD-A: read-only."""
    root = _issue(tmp_path, good=False)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert r.returncode == 0, r.stderr
    after = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    assert before == after


def test_an_unknown_issue_fails(tmp_path):
    root = _issue(tmp_path, good=True)
    r = _compass(root, "issue", "diagnose", "--issue", "no-such-issue")
    assert r.returncode != 0
    assert "no-such-issue" in r.stdout + r.stderr


def test_a_landed_issue_in_this_repository(tmp_path):
    """SD-A against real records, where the local archive has one."""
    work = ROOT / ".compass" / "work" / "decisions-ledger"
    if not (work / "manifest.yml").is_file():
        pytest.skip("the local issue archive is not in this checkout")
    r = _compass(ROOT, "issue", "diagnose", "--issue", "decisions-ledger")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "evidence/red-DL-A.json" in r.stdout


def test_the_verb_is_on_the_public_surface():
    """SD-E."""
    assert "compass issue diagnose" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert "'issue diagnose'" in (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text(
        encoding="utf-8")
    assert "diagnose" in _compass(ROOT, "issue", "--help").stdout


# --- review round 1 ------------------------------------------------------------

def _load(root: Path) -> dict:
    return yaml.safe_load((root / ".compass" / "work" / SLUG / "manifest.yml").read_text())


def _save(root: Path, m: dict) -> None:
    (root / ".compass" / "work" / SLUG / "manifest.yml").write_text(
        yaml.safe_dump(m, sort_keys=False), encoding="utf-8")


def test_an_unbound_red_counts(tmp_path):
    """SD-B, SD-C: `red.json` is a red too, bound to its scenario inside."""
    root = _issue(tmp_path, good=True)
    evidence = root / ".compass" / "work" / SLUG / "evidence"
    (evidence / "red-B.json").unlink()
    (evidence / "red.json").write_text(json.dumps(
        {"scenario": "B", "timestamp": "2026-10-01T10:30:00+00:00"}), encoding="utf-8")
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert "evidence/red.json" in _section(r.stdout, "Timeline")
    assert "None found in the records." in _section(r.stdout, "Deviations")


def test_a_solo_breakdown_is_not_a_deviation(tmp_path):
    """SD-C: a solo run writes no subtasks."""
    root = _issue(tmp_path, good=True)
    m = _load(root)
    m["stages"]["breakdown"] = "multiagent"
    m.pop("subtasks")
    _save(root, m)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert "None found in the records." in _section(r.stdout, "Deviations")


def test_a_spike_without_reds_is_not_a_deviation(tmp_path):
    """SD-C: a spike records no red."""
    root = _issue(tmp_path, good=True)
    for p in (root / ".compass" / "work" / SLUG / "evidence").glob("*-*.json"):
        p.unlink()
    m = _load(root)
    m["delivery_approach"] = "spike"
    m["stages"]["implement"] = "explore"
    _save(root, m)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert "implement" not in _section(r.stdout, "Deviations")


def test_an_unfinished_issue_has_not_reached_its_later_stages(tmp_path):
    """SD-C: an active issue's missing landing and pending gate are not deviations."""
    root = _issue(tmp_path, good=False)
    m = _load(root)
    m["status"] = "active"
    for key in ("land_timestamp", "land_commit"):
        m.pop(key)
    _save(root, m)
    dev = _section(_compass(root, "issue", "diagnose", "--issue", SLUG).stdout, "Deviations")
    assert "ship" not in dev and "verify.security" not in dev


def test_hook_refusals_and_failed_checks_are_in_the_timeline(tmp_path):
    """SD-B: .compass/interruptions.log dates each refusal and failed check."""
    root = _issue(tmp_path, good=True)
    (root / ".compass" / "interruptions.log").write_text(
        "2026-10-01T10:15:00Z\tdemo\thook_blocks\n"
        "2026-10-01T10:16:00Z\tother\thook_blocks\n"
        "2026-10-01T12:15:00Z\tdemo\tcheck_failures\n", encoding="utf-8")
    timeline = _section(_compass(root, "issue", "diagnose", "--issue", SLUG).stdout, "Timeline")
    assert timeline.count("hook refused an edit") == 1
    assert "a check failed" in timeline


def test_a_recorded_cost_is_shown(tmp_path):
    root = _issue(tmp_path, good=True)
    m = _load(root)
    m["subtasks"][0]["cost"] = 41000
    _save(root, m)
    assert "41000 tokens" in _compass(root, "issue", "diagnose", "--issue", SLUG).stdout


@pytest.mark.parametrize("mutate", [
    lambda m: m.update(gates=["not a dict", {"status": "pass"}]),
    lambda m: m.update(gates=[{"id": "g", "status": "pass", "evidence": [{"id": "x"}]}]),
    lambda m: m["subtasks"][0].update(review_rounds=[None]),
    lambda m: m.update(stages=["assess"]),
    lambda m: m.update(reassessments="none"),
])
def test_odd_manifests_do_not_crash(tmp_path, mutate):
    root = _issue(tmp_path, good=True)
    m = _load(root)
    mutate(m)
    _save(root, m)
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr


def test_a_record_that_is_not_an_object_does_not_crash(tmp_path):
    root = _issue(tmp_path, good=True)
    (root / ".compass" / "work" / SLUG / "evidence" / "green-D.json").write_text("[1, 2]")
    r = _compass(root, "issue", "diagnose", "--issue", SLUG)
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr


# --- review round 2 ------------------------------------------------------------

def _deviations_of(root: Path) -> str:
    return _section(_compass(root, "issue", "diagnose", "--issue", SLUG).stdout, "Deviations")


def test_a_queued_issue_has_no_deviation_for_stages_it_never_reached(tmp_path):
    root = _issue(tmp_path, good=True)
    work = root / ".compass" / "work" / SLUG
    for p in (work / "evidence").glob("*"):
        p.unlink()
    for p in (root / "docs" / "compass" / f"{CREATED}-{SLUG}").glob("*"):
        p.unlink()
    m = _load(root)
    m.update(status="queued", scenarios=[], artifacts=[], subtasks=[], gates=[])
    for key in ("land_timestamp", "land_commit"):
        m.pop(key)
    _save(root, m)
    assert "None found in the records." in _deviations_of(root)


def test_a_gap_before_a_later_record_is_a_deviation_on_an_active_issue(tmp_path):
    """The control: an active issue that implemented without a plan record."""
    root = _issue(tmp_path, good=True)
    (root / "docs" / "compass" / f"{CREATED}-{SLUG}" / "technical-design.md").unlink()
    m = _load(root)
    m["status"] = "active"
    m["artifacts"] = [a for a in m["artifacts"] if a["kind"] != "technical-design"]
    _save(root, m)
    assert "plan ran in the route" in _deviations_of(root)


def test_an_omitted_document_is_shown_with_its_reason(tmp_path):
    root = _issue(tmp_path, good=True)
    (root / "docs" / "compass" / f"{CREATED}-{SLUG}" / "technical-design.md").unlink()
    m = _load(root)
    for a in m["artifacts"]:
        if a["kind"] == "technical-design":
            a.update(status="omitted", reason="the criteria name the one function", path=None)
    _save(root, m)
    out = _compass(root, "issue", "diagnose", "--issue", SLUG).stdout
    assert "omitted: the criteria name the one function" in _section(out, "Stages")
    assert "None found in the records." in _section(out, "Deviations")


def test_a_green_with_no_red_anywhere_is_a_deviation(tmp_path):
    root = _issue(tmp_path, good=True)
    for p in (root / ".compass" / "work" / SLUG / "evidence").glob("red-*.json"):
        p.unlink()
    assert "no red anywhere in the issue" in _deviations_of(root)


def test_a_green_whose_red_is_on_another_scenario_is_not_a_deviation(tmp_path):
    root = _issue(tmp_path, good=True)
    (root / ".compass" / "work" / SLUG / "evidence" / "red-B.json").unlink()
    assert "None found in the records." in _deviations_of(root)


def test_an_acceptance_record_counts_as_declared(tmp_path):
    root = _issue(tmp_path, good=True)
    evidence = root / ".compass" / "work" / SLUG / "evidence"
    for p in evidence.glob("red-*.json"):
        p.unlink()
    (evidence / "acceptance-A.json").write_text(json.dumps({"scenario": "A"}), encoding="utf-8")
    assert "None found in the records." in _deviations_of(root)


def test_a_distribution_map_is_breakdowns_record(tmp_path):
    root = _issue(tmp_path, good=True)
    (root / "docs" / "compass" / f"{CREATED}-{SLUG}" / "distribution-map.md").write_text("# x\n")
    m = _load(root)
    m.pop("subtasks")
    m["stages"]["breakdown"] = "multiagent"
    _save(root, m)
    stages = _section(_compass(root, "issue", "diagnose", "--issue", SLUG).stdout, "Stages")
    assert "distribution-map.md" in stages


def test_landed_by_is_a_ship_record(tmp_path):
    root = _issue(tmp_path, good=True)
    m = _load(root)
    for key in ("land_timestamp", "land_commit"):
        m.pop(key)
    m["landed_by"] = ["abc1234", "def5678"]
    _save(root, m)
    out = _compass(root, "issue", "diagnose", "--issue", SLUG).stdout
    assert "landed abc1234, def5678" in _section(out, "Stages")
    assert "None found in the records." in _section(out, "Deviations")


@pytest.mark.parametrize("red_command, says", [
    ("pytest tests/a.py", "from the same command"),
    ("pytest tests/b.py", "from a different command (pytest tests/b.py)"),
])
def test_a_late_red_names_its_command(tmp_path, red_command, says):
    root = _issue(tmp_path, good=True)
    evidence = root / ".compass" / "work" / SLUG / "evidence"
    (evidence / "green-B.json").write_text(json.dumps(
        {"scenario": "B", "timestamp": "2026-10-01T11:30:00+00:00",
         "command": "pytest tests/a.py"}), encoding="utf-8")
    (evidence / "red-B.json").write_text(json.dumps(
        {"scenario": "B", "timestamp": "2026-10-01T12:00:00+00:00",
         "command": red_command}), encoding="utf-8")
    assert says in _deviations_of(root)


def test_unbound_records_are_not_paired(tmp_path):
    root = _issue(tmp_path, good=True)
    evidence = root / ".compass" / "work" / SLUG / "evidence"
    (evidence / "green.json").write_text(json.dumps(
        {"timestamp": "2026-10-01T09:00:00+00:00"}), encoding="utf-8")
    (evidence / "red.json").write_text(json.dumps(
        {"timestamp": "2026-10-01T09:30:00+00:00"}), encoding="utf-8")
    assert "None found in the records." in _deviations_of(root)


def test_events_after_the_landing_are_marked(tmp_path):
    root = _issue(tmp_path, good=True)
    (root / ".compass" / "interruptions.log").write_text(
        "2026-11-01T10:00:00Z\tdemo\tcheck_failures\n", encoding="utf-8")
    timeline = _section(_compass(root, "issue", "diagnose", "--issue", SLUG).stdout, "Timeline")
    assert "a check failed (after landing)" in timeline


# --- the output edges from review round 3 (#277) -------------------------------

def test_a_landed_by_mapping_prints_its_issue(tmp_path):
    root = _issue(tmp_path, good=True)
    m = _load(root)
    for key in ("land_timestamp", "land_commit"):
        m.pop(key)
    m["landed_by"] = [{"issue": "other-issue"}]
    _save(root, m)
    out = _compass(root, "issue", "diagnose", "--issue", SLUG).stdout
    assert "{" not in _section(out, "Stages")
    assert "other-issue" in _section(out, "Stages")


def test_an_unbound_green_is_named_unbound(tmp_path):
    root = _issue(tmp_path, good=True)
    evidence = root / ".compass" / "work" / SLUG / "evidence"
    for p in evidence.glob("*.json"):
        p.unlink()
    (evidence / "green.json").write_text(json.dumps(
        {"timestamp": "2026-10-01T11:00:00+00:00"}), encoding="utf-8")
    dev = _deviations_of(root)
    assert "scenario (unbound): a green" in dev, dev


def test_an_early_omission_does_not_move_how_far_the_issue_reached(tmp_path):
    root = _issue(tmp_path, good=True)
    work = root / ".compass" / "work" / SLUG
    for p in (work / "evidence").glob("*"):
        p.unlink()
    for p in (root / "docs" / "compass" / f"{CREATED}-{SLUG}").glob("*"):
        p.unlink()
    m = _load(root)
    m.update(status="active", scenarios=[], subtasks=[], gates=[],
             artifacts=[{"id": "ART-DISTRIBUTION_MAP", "kind": "distribution-map",
                         "status": "omitted", "reason": "a solo run"}])
    m["stages"]["breakdown"] = "multiagent"
    for key in ("land_timestamp", "land_commit"):
        m.pop(key)
    _save(root, m)
    assert "None found in the records." in _deviations_of(root)


def test_an_issue_landed_through_another_points_there(tmp_path):
    root = _issue(tmp_path, good=True)
    work = root / ".compass" / "work" / SLUG
    for p in (work / "evidence").glob("*"):
        p.unlink()
    m = _load(root)
    for key in ("land_timestamp", "land_commit"):
        m.pop(key)
    m["landed_by"] = [{"issue": "other-issue"}]
    _save(root, m)
    dev = _deviations_of(root)
    assert "implement ran in the route" not in dev
    assert "landed through other-issue" in dev
