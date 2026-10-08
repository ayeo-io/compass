"""The issue state is read from the records through one accessor (issue
`vocabulary-and-cli-renames`, group C).

Stored values stay in the old words until the writers flip, so each test of a
reader runs once in the old words and once in the new ones. A state that
nothing stored (`ready`, `in-progress`, `in-review`) is derived by
`lifecycle.state_of`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))


def _state_of(manifest, task_dir=None):
    # Imported in the call so a missing module fails the test, not collection.
    from compass_pkg import lifecycle
    return lifecycle.state_of(manifest, task_dir)


def _doc(kind, path="doc.md"):
    return {"kind": kind, "path": path, "status": "draft"}


def _ready_manifest(**extra):
    """Define finished (criteria registered), refine finished (review
    registered), nothing after."""
    m = {"issue": "x", "delivery_approach": "full",
         "stages": {"refine": "full"},
         "artifacts": [_doc("acceptance-criteria"), _doc("requirements-review")]}
    m.update(extra)
    return m


# --- derivation (design 1.3, rules 3 to 7) ----------------------------------

def test_vr_c9_define_and_refine_registered_with_nothing_after_reads_ready():
    assert _state_of(_ready_manifest()) == "ready"


def test_vr_c33_criteria_without_a_review_on_an_uncollapsed_refine_reads_backlog():
    m = {"issue": "x", "delivery_approach": "full", "stages": {"refine": "full"},
         "artifacts": [_doc("acceptance-criteria")]}
    assert _state_of(m) == "backlog"
    assert _state_of({"issue": "x"}) == "backlog"


def test_vr_c31_a_collapsed_refine_with_criteria_registered_reads_ready():
    m = {"issue": "x", "delivery_approach": "quick-fix",
         "stages": {"refine": "collapsed"},
         "artifacts": [_doc("acceptance-criteria")]}
    assert _state_of(m) == "ready"
    m["stages"]["refine"] = "skipped"
    assert _state_of(m) == "ready"


@pytest.mark.parametrize("record", [
    {"artifacts": [_doc("technical-design")]},
    {"artifacts": [_doc("distribution-map")]},
    {"subtasks": [{"id": "subtask-1"}]},
    {"evidence": [{"id": "EV-1", "type": "test-run", "path": "evidence/green.json"}]},
])
def test_vr_c10_a_design_map_subtask_or_test_record_reads_in_progress(record):
    m = _ready_manifest()
    assert _state_of(m) == "ready"
    m["artifacts"] = m["artifacts"] + record.get("artifacts", [])
    m.update({k: v for k, v in record.items() if k != "artifacts"})
    assert _state_of(m) == "in-progress"


def test_vr_c10_a_red_marker_on_disk_reads_in_progress(tmp_path):
    m = _ready_manifest()
    assert _state_of(m, str(tmp_path)) == "ready"
    (tmp_path / ".red").write_text("x")
    assert _state_of(m, str(tmp_path)) == "in-progress"


def test_vr_c11_a_gate_moved_from_pending_reads_in_review():
    m = _ready_manifest(subtasks=[{"id": "subtask-1"}],
                        gates=[{"id": "verify.correctness", "status": "pending"}])
    assert _state_of(m) == "in-progress"
    m["gates"][0]["status"] = "pass"
    assert _state_of(m) == "in-review"


def test_vr_c11_a_verification_report_registered_with_a_path_reads_in_review():
    m = _ready_manifest(subtasks=[{"id": "subtask-1"}])
    assert _state_of(m) == "in-progress"
    m["artifacts"] = m["artifacts"] + [_doc("verification-report", "verification-report.md")]
    assert _state_of(m) == "in-review"
    m["artifacts"][-1].pop("path")
    assert _state_of(m) == "in-progress"


def test_vr_c32_the_current_stage_key_wins_over_the_records():
    m = {"issue": "x", "delivery_approach": "full", "stages": {"refine": "full"},
         "artifacts": [_doc("acceptance-criteria")], "current_phase": "implement"}
    assert _state_of(m) == "in-progress"
    for stage, state in (("assess", "backlog"), ("define", "backlog"), ("refine", "backlog"),
                         ("plan", "in-progress"), ("breakdown", "in-progress"),
                         ("implement", "in-progress"), ("verify", "in-review"),
                         ("ship", "in-review")):
        m["current_phase"] = stage
        assert _state_of(m) == state, stage


# --- the accessor: closed and held, in both word sets (VR-C16) --------------

# `(status, extra keys)` for every way an issue is closed, in the old words
# the writers still store and the new words they will.
CLOSED = [
    ("landed", {}),
    ("abandoned", {}),
    ("done", {"close_reason": "completed"}),
    ("done", {"close_reason": "not-planned"}),
    ("done", {"close_reason": "duplicate", "duplicate_of": "other"}),
    ("done", {}),
]
COMPLETED = [("landed", {}), ("done", {"close_reason": "completed"})]
HELD = [("queued", {}), ("parked", {"parked_reason": "waiting"}),
        ("backlog", {}), ("backlog", {"parked_reason": "waiting"})]
IN_FLIGHT = [None, "active", "ready", "in-progress", "in-review"]


def _with(status, extra, **more):
    m = {"issue": "x", **extra, **more}
    if status is not None:
        m["status"] = status
    return m


@pytest.mark.parametrize("status,extra", CLOSED)
def test_vr_c16_a_closed_issue_reads_done_whatever_its_records(status, extra):
    m = _with(status, extra, subtasks=[{"id": "subtask-1"}],
              gates=[{"id": "verify.x", "status": "pass"}])
    assert _state_of(m) == "done"


@pytest.mark.parametrize("status,extra", HELD)
def test_vr_c16_a_held_issue_reads_backlog_whatever_its_records(status, extra):
    m = _with(status, extra, subtasks=[{"id": "subtask-1"}],
              gates=[{"id": "verify.x", "status": "pass"}])
    assert _state_of(m) == "backlog"


@pytest.mark.parametrize("status", IN_FLIGHT)
def test_vr_c16_an_in_flight_word_is_ignored_and_the_records_decide(status):
    assert _state_of(_with(status, {}, subtasks=[{"id": "subtask-1"}])) == "in-progress"
    assert _state_of(_with(status, {})) == "backlog"


@pytest.mark.parametrize("status,extra", CLOSED)
def test_vr_c16_only_a_completed_close_counts_as_completed(status, extra):
    from compass_pkg import status_words
    m = _with(status, extra)
    assert status_words.is_closed(m)
    assert status_words.is_completed(m) == ((status, extra) in COMPLETED)


def test_vr_c16_an_explicit_close_reason_wins_over_landed():
    from compass_pkg import status_words
    m = _with("landed", {"close_reason": "not-planned"})
    assert status_words.is_closed(m) and not status_words.is_completed(m)


@pytest.mark.parametrize("status,extra", HELD)
def test_vr_c16_a_hold_is_held_and_not_closed(status, extra):
    from compass_pkg import status_words
    m = _with(status, extra)
    assert status_words.is_held(m) and not status_words.is_closed(m)
    assert not status_words.is_completed(m)


@pytest.mark.parametrize("status", IN_FLIGHT)
def test_vr_c16_an_in_flight_issue_is_neither_held_nor_closed(status):
    from compass_pkg import status_words
    m = _with(status, {})
    assert not status_words.is_held(m) and not status_words.is_closed(m)
    assert status_words.is_in_flight(m)


@pytest.mark.parametrize("status,extra", [*CLOSED, *HELD, ("weird", {})])
def test_vr_c16_a_closed_held_or_unknown_status_is_not_in_flight(status, extra):
    from compass_pkg import status_words
    assert not status_words.is_in_flight(_with(status, extra))


def test_vr_c16_a_manifest_that_is_not_a_mapping_is_neither_held_nor_closed():
    from compass_pkg import status_words
    for bad in (None, [], "landed"):
        assert not status_words.is_held(bad) and not status_words.is_closed(bad)


# --- the readers of 4a: flow, next, statusline, stage_lists ------------------

def _project(tmp_path, slug="the-issue", **fields):
    task = tmp_path / ".compass" / "work" / slug
    task.mkdir(parents=True)
    (tmp_path / ".compass" / "current-task").write_text(slug + "\n")
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    import yaml
    data = {"schema_version": "2.0", "issue": slug, "created": "2026-10-02",
            "delivery_approach": "feature", "stages": {"refine": "full"},
            "land_timestamp": "2026-10-08T09:00:00Z"}
    data.update(fields)
    (task / "manifest.yml").write_text(yaml.safe_dump(data, sort_keys=False))
    (task / "delivery-approach.md").write_text("# Delivery approach\n")
    return task


@pytest.mark.parametrize("status,extra", CLOSED)
def test_vr_c16_next_says_a_closed_issue_has_nothing_left(tmp_path, status, extra):
    import subprocess
    _project(tmp_path, **_with(status, extra))
    r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "next"], cwd=tmp_path,
                       capture_output=True, text=True,
                       env={"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "all phases complete"


@pytest.mark.parametrize("status,extra", CLOSED)
def test_vr_c16_the_status_line_shows_a_closed_issue_as_done(tmp_path, status, extra, monkeypatch):
    from compass_pkg import statusline
    _project(tmp_path, **_with(status, extra))
    monkeypatch.setenv("COMPASS_ISSUE", "the-issue")
    assert "done" in statusline.render(str(tmp_path), 200).split()


@pytest.mark.parametrize("status,extra", CLOSED)
def test_vr_c16_a_closed_issue_has_reached_every_stage(status, extra):
    from compass_pkg import stage_lists

    class View:
        @staticmethod
        def stage_order():
            return ["define", "plan", "implement"]

    assert stage_lists._positions(View, _with(status, extra), None) == (
        ["define", "plan", "implement"], 3)


def _board(tmp_path, **issues):
    from compass_pkg import flow
    import datetime
    import yaml
    for slug, fields in issues.items():
        d = tmp_path / ".compass" / "work" / slug
        d.mkdir(parents=True)
        data = {"schema_version": "2.0", "issue": slug, "created": "2026-10-07",
                "delivery_approach": "feature",
                "land_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()}
        data.update(fields)
        (d / "manifest.yml").write_text(yaml.safe_dump(data, sort_keys=False))
    return flow.board(str(tmp_path / ".compass" / "work"))


def test_vr_c16_the_board_places_each_kind_of_close_and_hold(tmp_path):
    out = _board(
        tmp_path,
        a_landed={"status": "landed"},
        b_done_completed={"status": "done", "close_reason": "completed"},
        c_done_not_planned={"status": "done", "close_reason": "not-planned"},
        d_abandoned={"status": "abandoned"},
        e_parked={"status": "parked", "parked_reason": "waiting"},
        f_backlog_hold={"status": "backlog", "parked_reason": "waiting"},
        g_queued={"status": "queued"},
        h_backlog_plain={"status": "backlog"},
        i_flight={},
    )
    where = {k: sorted(r["slug"] for r in out[k]) for k in
             ("landed_this_week", "abandoned", "held", "next_up", "in_progress", "other")}
    assert where == {
        "landed_this_week": ["a_landed", "b_done_completed"],
        "abandoned": ["c_done_not_planned", "d_abandoned"],
        "held": ["e_parked", "f_backlog_hold"],
        "next_up": ["g_queued", "h_backlog_plain"],
        "in_progress": ["i_flight"],
        "other": [],
    }


def test_vr_c16_queue_ageing_counts_a_backlog_hold_with_no_parked_reason(tmp_path):
    from compass_pkg import flow
    _board(tmp_path, a={"status": "backlog"}, b={"status": "backlog", "parked_reason": "x"})
    top, _table = flow.queue_ageing(str(tmp_path / ".compass" / "work"))
    assert "No queued issues" not in top


def test_vr_c16_the_living_spec_keeps_only_completed_issues(tmp_path):
    from compass_pkg import flow
    for slug, status, extra in (("kept", "done", {"close_reason": "completed"}),
                                ("not-planned", "done", {"close_reason": "not-planned"}),
                                ("held", "backlog", {})):
        work = tmp_path / ".compass" / "work" / slug
        work.mkdir(parents=True)
        (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
        import yaml
        (work / "manifest.yml").write_text(yaml.safe_dump({
            "schema_version": "2.0", "task": slug, "created": "2026-08-10",
            "status": status, **extra,
            "scenarios": [{"id": "ID-" + slug.upper(), "title": "behaviour of " + slug,
                           "intent": "INT-1"}]}))
    flow.derive_system_spec(str(tmp_path))
    spec = (tmp_path / "docs" / "system-spec.md").read_text(encoding="utf-8")
    assert "ID-KEPT" in spec
    assert "ID-NOT-PLANNED" not in spec and "ID-HELD" not in spec


# --- the readers of the checks: checks, compliance, the ci sweep, diagnose,
# --- multiagent_check, binding, landed_by ------------------------------------

DONE_WORDS = [("landed", {}), ("done", {"close_reason": "completed"}),
              ("done", {"close_reason": "not-planned"}), ("abandoned", {})]


def _at_project(tmp_path, monkeypatch):
    (tmp_path / ".compass" / "work").mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("status,extra", DONE_WORDS)
def test_vr_c16_declared_tests_are_a_historical_record_once_the_issue_is_done(
        tmp_path, monkeypatch, status, extra):
    from compass_pkg import checks
    _at_project(tmp_path, monkeypatch)
    ok, detail = checks._check_declared_tests_resolve(_with(status, extra), str(tmp_path))
    assert ok and "historical record" in detail


@pytest.mark.parametrize("status,extra", [("active", {}), ("backlog", {}), (None, {})])
def test_vr_c16_declared_tests_are_still_checked_while_the_issue_is_open(
        tmp_path, monkeypatch, status, extra):
    from compass_pkg import checks
    _at_project(tmp_path, monkeypatch)
    ok, detail = checks._check_declared_tests_resolve(_with(status, extra), str(tmp_path))
    assert "historical record" not in detail


@pytest.mark.parametrize("status,extra,reported", [
    ("landed", {}, True), ("done", {"close_reason": "completed"}, True),
    ("done", {"close_reason": "not-planned"}, True), ("queued", {}, True),
    ("backlog", {}, True), ("active", {}, False), (None, {}, False),
    ("in-progress", {}, False), ("in-review", {}, False)])
def test_vr_c16_a_missing_traced_file_is_reported_only_when_the_issue_is_not_open(
        tmp_path, monkeypatch, status, extra, reported):
    from compass_pkg import checks
    _at_project(tmp_path, monkeypatch)
    m = _with(status, extra, scenarios=[{"id": "S-1"}],
              changed_files=[{"path": "gone.py", "scenarios": ["S-1"]}],
              gates=[{"id": "verify.correctness", "status": "pass"}])
    ok, detail = checks._check_changed_code_traces(m, str(tmp_path))
    assert ok is reported


@pytest.mark.parametrize("status,extra,reported", [
    ("landed", {}, True), ("done", {"close_reason": "completed"}, True),
    ("backlog", {}, True), ("active", {}, False), (None, {}, False),
    ("in-progress", {}, False), ("in-review", {}, False)])
def test_vr_c16_a_missing_human_approval_is_reported_only_when_the_issue_is_not_open(
        status, extra, reported):
    from compass_pkg import checks
    ok, _detail = checks._check_human_approval(_with(status, extra, evidence=[]), ".")
    assert ok is reported


@pytest.mark.parametrize("status,extra,counted", [
    ("landed", {}, True), ("done", {"close_reason": "completed"}, True),
    ("active", {}, True), (None, {}, True), ("in-progress", {}, True),
    ("done", {"close_reason": "not-planned"}, False), ("abandoned", {}, False),
    ("queued", {}, False), ("parked", {}, False), ("backlog", {}, False)])
def test_vr_c16_the_compliance_report_reads_completed_and_open_issues(
        tmp_path, status, extra, counted):
    import yaml
    from compass_pkg import compliance
    work = tmp_path / "work"
    (work / "the-issue").mkdir(parents=True)
    (work / "the-issue" / "manifest.yml").write_text(yaml.safe_dump(
        _with(status, extra, created="2026-10-08")))
    found = compliance._issues(str(work), None, 3650)
    assert bool(found) is counted


def _ci_output(tmp_path, status_lines):
    import subprocess
    sys.path.insert(0, str(ROOT / "tests"))
    from test_ci_respects_queued import _project
    project = _project(tmp_path, "the-issue", "active")
    manifest = project / ".compass" / "work" / "the-issue" / "manifest.yml"
    text = manifest.read_text().replace("status: active\n", status_lines)
    manifest.write_text(text)
    r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "ci"], cwd=project,
                       capture_output=True, text=True, timeout=120)
    return r.stdout + r.stderr


@pytest.mark.parametrize("lines,skipped", [
    ("status: backlog\n", True), ("status: queued\n", True), ("status: parked\n", True),
    ("status: abandoned\n", True),
    ("status: done\nclose_reason: not-planned\n", True),
    ("status: done\nclose_reason: duplicate\n", True),
    ("status: landed\n", False), ("status: done\nclose_reason: completed\n", False),
    ("status: active\n", False), ("", False)])
def test_vr_c16_the_sweep_skips_gate_checks_for_a_hold_and_for_work_not_delivered(
        tmp_path, lines, skipped):
    out = _ci_output(tmp_path, lines)
    assert ("gate checks skipped - status is" in out) is skipped, out


def test_vr_c16_the_diagnosis_lists_a_failed_gate_of_a_completed_issue_only(tmp_path):
    from compass_pkg import diagnose
    shown = {stage: [] for stage in diagnose._ORDER}
    gates = [{"id": "verify.correctness", "status": "fail"}]
    for status, extra, listed in (("landed", {}, True),
                                  ("done", {"close_reason": "completed"}, True),
                                  ("done", {"close_reason": "not-planned"}, False),
                                  ("active", {}, False)):
        out = diagnose._deviations(str(tmp_path), _with(status, extra, gates=gates),
                                   {}, shown, [])
        assert any("verify.correctness is fail" in line for line in out) is listed, status


@pytest.mark.parametrize("status,extra,ready", [
    ("landed", {}, True), ("done", {"close_reason": "completed"}, True),
    ("done", {"close_reason": "not-planned"}, True), ("active", {}, False)])
def test_vr_c16_a_closed_issue_is_ready_whatever_its_gates_say(status, extra, ready):
    from compass_pkg import multiagent_check
    m = _with(status, extra, gates=[{"id": "g", "status": "pending"}])
    assert multiagent_check._ready(m) is ready


@pytest.mark.parametrize("status,extra", [("landed", {}),
                                          ("done", {"close_reason": "completed"})])
def test_vr_c16_the_evidence_check_judges_a_completed_issue_as_landed(
        tmp_path, monkeypatch, status, extra):
    from compass_pkg import binding
    monkeypatch.setattr(binding, "_newest_bound_record", lambda t, d: ("p", {}))
    monkeypatch.setattr(binding, "_check_landed", lambda *a: ("judged as landed", ""))
    assert binding._check_evidence_matches_tree(_with(status, extra), str(tmp_path)) == (
        "judged as landed", "")


def _landed_by_project(tmp_path, other_status, other_extra):
    import yaml
    for slug, fields in (("this", {"landed_by": [{"issue": "other"}]}),
                         ("other", {"scenarios": [{"id": "S-1"}], "delivered": ["this"],
                                    **other_extra, "status": other_status})):
        d = tmp_path / ".compass" / "work" / slug
        d.mkdir(parents=True)
        (d / "manifest.yml").write_text(yaml.safe_dump({"issue": slug, **fields}))
    return tmp_path / ".compass" / "work" / "this"


@pytest.mark.parametrize("this_status,this_extra,other_status,other_extra,holds", [
    ("landed", {}, "landed", {}, True),
    ("done", {"close_reason": "completed"}, "done", {"close_reason": "completed"}, True),
    ("done", {"close_reason": "completed"}, "landed", {}, True),
    ("landed", {}, "done", {"close_reason": "completed"}, True),
    ("landed", {}, "done", {"close_reason": "not-planned"}, False),
    ("landed", {}, "active", {}, False),
    ("active", {}, "landed", {}, False),
    ("backlog", {}, "done", {"close_reason": "completed"}, False)])
def test_vr_c16_a_landed_by_pointer_holds_between_completed_issues(
        tmp_path, this_status, this_extra, other_status, other_extra, holds):
    from compass_pkg import landed_by
    import yaml
    task_dir = _landed_by_project(tmp_path, other_status, other_extra)
    task = {"issue": "this", "landed_by": [{"issue": "other"}], "status": this_status,
            **this_extra}
    ok, detail = landed_by.landed_by_holds(task, str(task_dir))
    assert ok is holds, detail
    ran, _detail = landed_by._check_landed_by_resolves(task, str(task_dir))
    assert (ran is True) is holds


# --- the readers of the configuration: generation, effective, policy,
# --- issue_config_cmd, run_cmd ----------------------------------------------

# A closed issue keeps the configuration it closed under; a hold and work in
# flight can still change it.
CLOSED_FOR_CONFIG = [("landed", {}), ("abandoned", {}),
                     ("done", {"close_reason": "completed"}),
                     ("done", {"close_reason": "not-planned"})]
OPEN_FOR_CONFIG = [(None, {}), ("active", {}), ("queued", {}), ("backlog", {})]


def _stored_issue(tmp_path, monkeypatch, status, extra):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_generation_store import _commit, _new_check, _project, _write_manifest
    import yaml
    root, task_dir = _project(tmp_path)
    monkeypatch.chdir(root)
    _commit(root, task_dir)
    # A configuration unlike the stored one, so a later commit has a change
    # to refuse.
    (root / "compass.yml").write_text(
        yaml.safe_dump({"schema": 1, "checks": {"extra": _new_check()}}), encoding="utf-8")
    changes = dict(extra, status=status) if status else dict(extra)
    _write_manifest(task_dir, **changes)
    return root, task_dir, _commit


@pytest.mark.parametrize("status,extra", CLOSED_FOR_CONFIG)
def test_vr_c16_a_closed_issue_cannot_store_a_new_generation(
        tmp_path, monkeypatch, status, extra):
    from compass_pkg.core import CompassError
    root, task_dir, commit = _stored_issue(tmp_path, monkeypatch, status, extra)
    with pytest.raises(CompassError) as caught:
        commit(root, task_dir, delivery_approach="full")
    assert "keeps" in str(caught.value) and "landed under" in str(caught.value)


@pytest.mark.parametrize("status,extra", OPEN_FOR_CONFIG)
def test_vr_c16_an_open_issue_can_store_a_new_generation(tmp_path, monkeypatch, status, extra):
    root, task_dir, commit = _stored_issue(tmp_path, monkeypatch, status, extra)
    assert commit(root, task_dir, delivery_approach="full").number == 2


@pytest.mark.parametrize("status,extra", CLOSED_FOR_CONFIG)
def test_vr_c16_preflight_refuses_a_closed_issue_before_anything_is_printed(
        tmp_path, monkeypatch, status, extra):
    from compass_pkg import effective, generation
    from compass_pkg.core import CompassError
    root, task_dir, _commit = _stored_issue(tmp_path, monkeypatch, status, extra)
    from test_generation_store import OUTCOME
    import yaml
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    manifest.update(OUTCOME)
    manifest["delivery_approach"] = "full"
    resolution = effective.resolve_live(str(root), manifest, task_dir.name, str(task_dir),
                                        validate=True)
    with pytest.raises(CompassError) as caught:
        generation.preflight(str(task_dir), resolution, manifest)
    assert "landed under" in str(caught.value)


@pytest.mark.parametrize("status,extra", CLOSED_FOR_CONFIG)
def test_vr_c16_a_closed_issue_cannot_be_given_a_proposal(tmp_path, monkeypatch, status, extra):
    from compass_pkg import generation
    from compass_pkg.core import CompassError
    root, task_dir, _commit = _stored_issue(tmp_path, monkeypatch, status, extra)
    import yaml
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text())
    with pytest.raises(CompassError) as caught:
        generation.write_proposal(str(task_dir), manifest, {"checks": {}})
    assert "landed under" in str(caught.value)


@pytest.mark.parametrize("status,extra", CLOSED_FOR_CONFIG)
def test_vr_c16_a_closed_issue_cannot_migrate_its_configuration(
        tmp_path, monkeypatch, status, extra):
    from compass_pkg import effective
    from compass_pkg.core import CompassError
    root, task_dir, _commit = _stored_issue(tmp_path, monkeypatch, status, extra)
    with pytest.raises(CompassError) as caught:
        effective.migrate_generation(str(task_dir))
    assert "landed under" in str(caught.value)


@pytest.mark.parametrize("status,extra", CLOSED_FOR_CONFIG)
def test_vr_c16_a_closed_issue_cannot_be_configured(tmp_path, monkeypatch, status, extra):
    import subprocess
    root, task_dir, _commit = _stored_issue(tmp_path, monkeypatch, status, extra)
    r = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "issue", "configure",
                        "--issue", task_dir.name, "--mode", "implement=lightweight"],
                       cwd=root, capture_output=True, text=True, timeout=120)
    assert r.returncode != 0
    assert "landed under" in r.stderr, r.stdout + r.stderr


@pytest.mark.parametrize("status,extra,needs_assessment", [
    ("queued", {}, False), ("backlog", {}, False), ("abandoned", {}, False),
    ("done", {"close_reason": "not-planned"}, False),
    ("done", {"close_reason": "duplicate", "duplicate_of": "other"}, False),
    ("active", {}, True), (None, {}, True), ("parked", {}, True),
    ("landed", {}, True), ("done", {"close_reason": "completed"}, True)])
def test_vr_c16_lint_asks_for_an_assessment_only_from_an_issue_that_started(
        tmp_path, status, extra, needs_assessment):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_ci_queued_issue import _BASE, _lint
    manifest = dict(_BASE, **extra)
    if status:
        manifest["status"] = status
    run = _lint(tmp_path, manifest)
    assert ("assessment" in (run.stdout + run.stderr)) is needs_assessment, run.stdout + run.stderr
