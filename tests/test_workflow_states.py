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
        i_flight={"subtasks": [{"id": "subtask-1"}]},
    )
    where = {k: sorted(r["slug"] for r in out[k]) for k in
             ("done_this_week", "closed", "backlog", "in_progress", "other")}
    assert where == {
        "done_this_week": ["a_landed", "b_done_completed"],
        "closed": ["c_done_not_planned", "d_abandoned"],
        "backlog": ["e_parked", "f_backlog_hold", "g_queued", "h_backlog_plain"],
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
    ("active", {}, True), (None, {}, True),
    ("parked", {"parked_at": "2026-10-01T09:00:00Z"}, True),
    ("backlog", {"parked_reason": "waiting"}, True),
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


# --- the last readers: manifest, receipt, calibration, receipt_provenance,
# --- replay -------------------------------------------------------------------

@pytest.mark.parametrize("status,extra,judged", [
    ("landed", {}, False), ("done", {"close_reason": "completed"}, False),
    ("done", {"close_reason": "not-planned"}, True),
    ("active", {}, True), (None, {}, True), ("in-review", {}, True)])
def test_vr_c16_a_completed_issue_is_not_judged_for_stale_paths(
        tmp_path, monkeypatch, status, extra, judged):
    from compass_pkg import manifest
    asked = []
    monkeypatch.setattr(manifest, "_newest_bound_record",
                        lambda task, task_dir: asked.append(1))
    m = _with(status, extra, gates=[{"id": "verify.correctness", "status": "pass"}])
    manifest._stale_paths(m, str(tmp_path), str(tmp_path), "HEAD")
    assert bool(asked) is judged


def test_vr_c16_a_completed_issue_is_judged_when_it_is_landed_again(tmp_path, monkeypatch):
    from compass_pkg import manifest
    asked = []
    monkeypatch.setattr(manifest, "_newest_bound_record",
                        lambda task, task_dir: asked.append(1))
    m = _with("done", {"close_reason": "completed"},
              gates=[{"id": "verify.correctness", "status": "pass"}])
    manifest._stale_paths(m, str(tmp_path), str(tmp_path), "HEAD", judge_landed=True)
    assert asked


# --- 6b: the status setter, the blocked flag, the board ----------------------
# Stored status is a `backlog` hold or `done` with a close reason. The three
# states in flight are read from the records and cannot be set by hand.

OLD_STATUS_WORDS = ("landed", "queued", "parked", "abandoned", "active")
PENDING = [{"id": "verify.correctness", "status": "pending"},
           {"id": "verify.architecture", "status": "pending"}]
PASSED = [{"id": "verify.correctness", "status": "pass"},
          {"id": "verify.architecture", "status": "pass"}]
WHY = {"reason": "waiting on a review", "at": "2026-10-08T10:00:00Z"}


def _args(**given):
    import types
    base = dict(status=None, task="the-issue", reason=None, close_reason=None,
                duplicate_of=None, json=False)
    base.update(given)
    return types.SimpleNamespace(**base)


def _saved(task_dir):
    import yaml
    return yaml.safe_load((task_dir / "manifest.yml").read_text())


def _status_cmd():
    from compass_pkg import status_cmd
    return status_cmd


def _set(tmp_path, monkeypatch, fields, **given):
    monkeypatch.chdir(tmp_path)
    task = _project(tmp_path, land_timestamp=None, **fields)
    return task, lambda **more: _status_cmd().cmd_task_set_status(_args(**{**given, **more}))


def test_vr_c1_backlog_stores_a_hold_clears_blocked_and_keeps_the_recorded_work(
        tmp_path, monkeypatch):
    work = {"subtasks": [{"id": "subtask-1"}], "blocked": dict(WHY)}
    task, run = _set(tmp_path, monkeypatch, work)
    run(status="backlog", reason="paused")
    saved = _saved(task)
    assert saved["status"] == "backlog" and "blocked" not in saved
    assert saved["subtasks"] == [{"id": "subtask-1"}]
    assert saved["parked_reason"] == "paused" and saved["parked_at"]


def test_vr_c2_done_completed_records_the_close_reason_and_a_land_time(tmp_path, monkeypatch):
    task, run = _set(tmp_path, monkeypatch, {"gates": PASSED})
    run(status="done", close_reason="completed")
    saved = _saved(task)
    assert saved["status"] == "done" and saved["close_reason"] == "completed"
    assert saved["land_timestamp"]


def test_vr_c3_done_completed_over_unpassed_gates_names_each_and_changes_nothing(
        tmp_path, monkeypatch):
    from compass_pkg.core import CompassError
    task, run = _set(tmp_path, monkeypatch, {"gates": PENDING})
    before = (task / "manifest.yml").read_text()
    with pytest.raises(CompassError) as caught:
        run(status="done", close_reason="completed")
    message = str(caught.value)
    assert "verify.correctness" in message and "verify.architecture" in message
    assert (task / "manifest.yml").read_text() == before


def test_vr_c4_done_not_planned_needs_no_passed_gate(tmp_path, monkeypatch):
    task, run = _set(tmp_path, monkeypatch, {"gates": PENDING})
    run(status="done", close_reason="not-planned")
    saved = _saved(task)
    assert saved["status"] == "done" and saved["close_reason"] == "not-planned"


def test_vr_c5_duplicate_of_stores_the_other_issue_and_the_duplicate_reason(
        tmp_path, monkeypatch):
    task, run = _set(tmp_path, monkeypatch, {})
    _project(tmp_path, slug="the-first")
    run(status="done", duplicate_of="the-first")
    saved = _saved(task)
    assert saved["status"] == "done" and saved["close_reason"] == "duplicate"
    assert saved["duplicate_of"] == "the-first"


def test_vr_c6_a_duplicate_without_the_other_issue_is_refused(tmp_path, monkeypatch):
    from compass_pkg.core import CompassError
    task, run = _set(tmp_path, monkeypatch, {})
    before = (task / "manifest.yml").read_text()
    with pytest.raises(CompassError) as caught:
        run(status="done", close_reason="duplicate")
    assert "duplicate-of" in str(caught.value)
    assert (task / "manifest.yml").read_text() == before


def test_vr_c7_done_with_no_close_reason_is_refused_and_lists_the_three(tmp_path, monkeypatch):
    from compass_pkg.core import CompassError
    task, run = _set(tmp_path, monkeypatch, {})
    before = (task / "manifest.yml").read_text()
    with pytest.raises(CompassError) as caught:
        run(status="done")
    for reason in ("completed", "not-planned", "duplicate"):
        assert reason in str(caught.value)
    assert (task / "manifest.yml").read_text() == before


@pytest.mark.parametrize("state", ["ready", "in-progress", "in-review"])
def test_vr_c8_a_state_the_records_move_cannot_be_set_by_hand(tmp_path, monkeypatch, state):
    from compass_pkg.core import CompassError
    task, run = _set(tmp_path, monkeypatch, {})
    before = (task / "manifest.yml").read_text()
    with pytest.raises(CompassError) as caught:
        run(status=state)
    assert "records" in str(caught.value) and state in str(caught.value)
    assert (task / "manifest.yml").read_text() == before


def test_vr_c8_a_word_that_is_not_a_status_names_the_two_that_are(tmp_path, monkeypatch):
    from compass_pkg.core import CompassError
    _task, run = _set(tmp_path, monkeypatch, {})
    with pytest.raises(CompassError) as caught:
        run(status="landed")
    assert "backlog" in str(caught.value) and "done" in str(caught.value)


def test_vr_c12_ship_commit_records_done_with_the_completed_reason(cli_path, tmp_path):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_ship_commit_derives import _git, _init_repo, _open_issue, _run_ship_commit
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    task_dir = _open_issue(repo, "lands-as-done")
    done = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", "lands-as-done")
    assert done.returncode == 0, done.stdout + done.stderr
    saved = _saved(task_dir)
    assert saved["status"] == "done" and saved["close_reason"] == "completed"
    assert saved["land_timestamp"] and saved["land_commit"]
    assert "blocked" not in saved


def test_vr_c12_ship_commit_clears_a_blocked_flag(cli_path, tmp_path):
    import yaml
    sys.path.insert(0, str(ROOT / "tests"))
    from test_ship_commit_derives import _git, _init_repo, _open_issue, _run_ship_commit
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)
    task_dir = _open_issue(repo, "was-blocked")
    body = yaml.safe_load((task_dir / "manifest.yml").read_text())
    body["blocked"] = dict(WHY)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))
    _git(repo, "add", "-A")
    done = _run_ship_commit(cli_path, repo, "-m", "land it", "--issue", "was-blocked")
    assert done.returncode == 0, done.stdout + done.stderr
    assert "blocked" not in _saved(task_dir)


def _blocked(tmp_path, monkeypatch, fields, **given):
    monkeypatch.chdir(tmp_path)
    task = _project(tmp_path, land_timestamp=None, **fields)
    return task, lambda verb, **more: getattr(_status_cmd(), "cmd_issue_blocked_" + verb)(
        _args(**{**given, **more}))


IN_PROGRESS = {"subtasks": [{"id": "subtask-1"}]}


def test_vr_c13_blocked_set_records_the_reason_and_time_and_the_board_shows_it(
        tmp_path, monkeypatch):
    from compass_pkg import flow, lifecycle
    task, run = _blocked(tmp_path, monkeypatch, IN_PROGRESS)
    run("set", reason="waiting on a review")
    saved = _saved(task)
    assert saved["blocked"]["reason"] == "waiting on a review" and saved["blocked"]["at"]
    assert lifecycle.state_of(saved, str(task)) == "in-progress"
    data = flow.board(str(tmp_path / ".compass" / "work"))
    row = next(r for r in data["in_progress"] if r["slug"] == "the-issue")
    assert row["blocked"] == "waiting on a review" and row["state"] == "in-progress"
    assert "BLOCKED: waiting on a review" in flow._board_row("in_progress", row)


def test_vr_c13_blocked_remove_deletes_the_flag_and_refuses_when_there_is_none(
        tmp_path, monkeypatch):
    from compass_pkg.core import CompassError
    task, run = _blocked(tmp_path, monkeypatch, {**IN_PROGRESS, "blocked": dict(WHY)})
    run("remove")
    assert "blocked" not in _saved(task)
    before = (task / "manifest.yml").read_text()
    with pytest.raises(CompassError):
        run("remove")
    assert (task / "manifest.yml").read_text() == before


@pytest.mark.parametrize("fields", [
    {"status": "backlog"},
    {},
    {"status": "done", "close_reason": "completed"},
], ids=["backlog", "ready-or-backlog-by-records", "done"])
def test_vr_c14_blocked_set_outside_progress_and_review_is_refused(tmp_path, monkeypatch, fields):
    from compass_pkg.core import CompassError
    task, run = _blocked(tmp_path, monkeypatch, fields)
    before = (task / "manifest.yml").read_text()
    with pytest.raises(CompassError) as caught:
        run("set", reason="stuck")
    assert "in-progress" in str(caught.value) and "in-review" in str(caught.value)
    assert (task / "manifest.yml").read_text() == before


def test_vr_c14_blocked_set_is_refused_on_a_ready_issue(tmp_path, monkeypatch):
    from compass_pkg.core import CompassError
    ready = {"artifacts": [_doc("acceptance-criteria"), _doc("requirements-review")]}
    task, run = _blocked(tmp_path, monkeypatch, ready)
    with pytest.raises(CompassError) as caught:
        run("set", reason="stuck")
    assert "ready" in str(caught.value) and "in-review" in str(caught.value)


def test_vr_c15_the_board_and_its_json_show_new_state_words_only(tmp_path):
    import json
    import subprocess
    from compass_pkg import flow
    ready = {"artifacts": [_doc("acceptance-criteria"), _doc("requirements-review")]}
    review = {**IN_PROGRESS, "gates": [{"id": "verify.correctness", "status": "pass"}]}
    _board(tmp_path,
           a_backlog={"status": "backlog", "parked_reason": "waiting"},
           b_ready=ready, c_progress=IN_PROGRESS, d_review=review,
           e_done={"status": "done", "close_reason": "completed"},
           f_closed={"status": "done", "close_reason": "not-planned"},
           g_old_landed={"status": "landed"}, h_old_queued={"status": "queued"},
           i_old_active={"status": "active", **IN_PROGRESS})
    root = str(tmp_path / ".compass" / "work")
    data = flow.board(root)
    placed = {k: sorted(r["slug"] for r in data[k]) for k in
              ("backlog", "ready", "in_progress", "in_review", "done_this_week", "closed")}
    assert placed == {"backlog": ["a_backlog", "h_old_queued"], "ready": ["b_ready"],
                      "in_progress": ["c_progress", "i_old_active"],
                      "in_review": ["d_review"],
                      "done_this_week": ["e_done", "g_old_landed"],
                      "closed": ["f_closed"]}
    assert data["counts"] == {"backlog": 2, "ready": 1, "in-progress": 2, "in-review": 1, "done": 3}
    closed = data["closed"][0]
    assert closed["close_reason"] == "not-planned" and closed["state"] == "done"
    for gone in ("held", "next_up", "landed_this_week", "abandoned"):
        assert gone not in data
    shown = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "flow",
                            "--work-root", root, "--json"], capture_output=True, text=True,
                           env={"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path)})
    assert shown.returncode == 0, shown.stderr
    blob = json.dumps(json.loads(shown.stdout))
    for word in OLD_STATUS_WORDS:
        assert f'"{word}"' not in blob, word
    text = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "flow",
                           "--work-root", root], capture_output=True, text=True,
                          env={"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path)})
    assert "IN REVIEW" in text.stdout and "READY" in text.stdout and "BACKLOG" in text.stdout
    for word in ("ABANDONED", "LANDED THIS WEEK", "NEXT UP", "HELD"):
        assert word not in text.stdout, word


def test_vr_c17_each_old_status_word_runs_the_new_setter_and_names_it():
    from compass_pkg import aliases
    wanted = {
        "active": ["issue", "status", "remove"],
        "queued": ["issue", "status", "set", "backlog"],
        "parked": ["issue", "status", "set", "backlog"],
        "landed": ["issue", "status", "set", "done", "--close-reason", "completed"],
        "abandoned": ["issue", "status", "set", "done", "--close-reason", "not-planned"],
        "done": ["issue", "status", "set", "done"],
    }
    for word, new in wanted.items():
        argv, notice = aliases.rewrite(["issue", "set-status", word, "--issue", "x"])
        assert argv == new + ["--issue", "x"], (word, argv)
        assert "issue set-status" in notice and "7.0.0" in notice, notice
        assert " ".join(new[:3]) in notice, notice


def test_vr_c17_an_old_word_through_the_command_line_closes_under_the_same_gate_rule(
        tmp_path):
    import subprocess
    task = _project(tmp_path, gates=PENDING, land_timestamp=None)
    env = {"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path)}
    run = lambda *argv: subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv],
                                       cwd=tmp_path, capture_output=True, text=True, env=env)
    refused = run("issue", "set-status", "landed", "--issue", "the-issue")
    assert refused.returncode != 0 and "have not passed" in refused.stdout + refused.stderr
    assert "is now 'issue status set done --close-reason completed'" in refused.stderr
    assert "status" not in _saved(task)
    closed = run("issue", "set-status", "abandoned", "--issue", "the-issue")
    assert closed.returncode == 0, closed.stderr
    assert _saved(task)["status"] == "done" and _saved(task)["close_reason"] == "not-planned"
    run("issue", "status", "set", "backlog", "--issue", "the-issue")
    assert _saved(task)["status"] == "backlog"
    ended = run("issue", "set-status", "active", "--issue", "the-issue")
    assert ended.returncode == 0, ended.stderr
    assert "status" not in _saved(task)


def test_vr_c18_status_remove_ends_a_hold_and_refuses_when_there_is_none(tmp_path, monkeypatch):
    from compass_pkg.core import CompassError
    monkeypatch.chdir(tmp_path)
    task = _project(tmp_path, status="backlog", parked_reason="waiting", **IN_PROGRESS)
    _status_cmd().cmd_task_status_remove(_args())
    saved = _saved(task)
    assert "status" not in saved
    from compass_pkg import lifecycle
    assert lifecycle.state_of(saved, str(task)) == "in-progress"
    before = (task / "manifest.yml").read_text()
    with pytest.raises(CompassError):
        _status_cmd().cmd_task_status_remove(_args())
    assert (task / "manifest.yml").read_text() == before


def test_vr_c19_done_with_no_close_reason_is_left_out_of_the_spec_and_lint_names_it(
        tmp_path):
    import subprocess
    from compass_pkg import flow
    task = _project(tmp_path, status="done", assessment={
        "risk": "contained", "familiarity": "greenfield", "size": "small"},
        scenarios=[{"id": "S-1", "title": "kept out", "intent": "INT-1"}])
    flow.derive_system_spec(str(tmp_path))
    assert "S-1" not in (tmp_path / "docs" / "system-spec.md").read_text()
    env = {"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path)}
    lint = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "issue", "lint",
                           "--issue", "the-issue"], cwd=tmp_path, capture_output=True,
                          text=True, env=env)
    assert lint.returncode == 1 and "close_reason" in lint.stdout, lint.stdout


def test_vr_c20_the_template_and_the_quick_fix_start_store_no_status(tmp_path):
    import re
    text = (ROOT / "templates" / "manifest.yml").read_text()
    assert not re.search(r"^status:", text, re.M)
    sys.path.insert(0, str(ROOT / "tests"))
    from test_quick_fix_verbs import _git, _start
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "README.md").write_text("hello\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    started = _start(root, "fix-one")
    written = root / ".compass" / "work" / "fix-one"
    assert (written / "manifest.yml").is_file(), started.stdout + started.stderr
    assert "status" not in _saved(written)


def test_vr_c20_recording_work_leaves_the_stored_status_alone(tmp_path):
    import subprocess
    task = _project(tmp_path)
    env = {"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path)}
    for argv in (["scenario", "add", "S-9", "--title", "t", "--intent", "INT-1",
                  "--issue", "the-issue"],
                 ["changed-file", "add", "cli/compass", "--scenario", "S-9",
                  "--issue", "the-issue"]):
        done = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv],
                              cwd=tmp_path, capture_output=True, text=True, env=env)
        assert done.returncode == 0, done.stdout + done.stderr
    saved = _saved(task)
    assert saved["scenarios"] and saved["changed_files"]
    assert "status" not in saved


def test_vr_c21_closing_or_holding_a_blocked_issue_clears_the_flag(tmp_path, monkeypatch):
    task, run = _set(tmp_path, monkeypatch, {**IN_PROGRESS, "blocked": dict(WHY)})
    run(status="done", close_reason="not-planned")
    assert "blocked" not in _saved(task)


def test_vr_c21_a_flag_on_an_issue_that_cannot_carry_it_is_reported_and_ignored(tmp_path):
    import subprocess
    from compass_pkg import lifecycle
    stale = {"status": "backlog", "blocked": dict(WHY)}
    task = _project(tmp_path, assessment={"risk": "contained", "familiarity": "greenfield",
                                          "size": "small"}, **stale)
    assert lifecycle.blocked_flag(_saved(task), str(task)) is None
    assert lifecycle.blocked_flag({**IN_PROGRESS, "blocked": dict(WHY)}, None) == WHY
    env = {"PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path)}
    lint = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "issue", "lint",
                           "--issue", "the-issue"], cwd=tmp_path, capture_output=True,
                          text=True, env=env)
    assert lint.returncode == 1 and "blocked" in lint.stdout, lint.stdout
    row = _board(tmp_path / "board", x=stale)["backlog"][0]
    assert "blocked" not in row


def test_vr_c22_duplicate_of_refuses_itself_an_unknown_issue_and_another_reason(
        tmp_path, monkeypatch):
    from compass_pkg.core import CompassError
    task, run = _set(tmp_path, monkeypatch, {})
    _project(tmp_path, slug="the-first")
    before = (task / "manifest.yml").read_text()
    for given in ({"duplicate_of": "the-issue"}, {"duplicate_of": "no-such-issue"},
                  {"duplicate_of": "the-first", "close_reason": "not-planned"}):
        with pytest.raises(CompassError):
            run(status="done", **given)
        assert (task / "manifest.yml").read_text() == before, given
    run(status="done", duplicate_of="the-first", close_reason="duplicate")
    assert _saved(task)["close_reason"] == "duplicate"


@pytest.mark.parametrize("status,extra,header", [
    ("landed", {}, "(landed)"), ("done", {"close_reason": "completed"}, "(landed)"),
    ("active", {}, "(IN PROGRESS - not yet landed)"), (None, {}, "(IN PROGRESS - not yet landed)"),
    ("in-progress", {}, "(IN PROGRESS - not yet landed)"),
    ("backlog", {}, "(BACKLOG)"), ("done", {"close_reason": "not-planned"}, "(DONE)")])
def test_vr_c16_the_receipt_header_reads_both_word_sets(status, extra, header):
    from compass_pkg import receipt
    text = receipt._receipt_render(_with(status, extra, schema_version="2.0"), "the-issue", {})
    assert header in text.splitlines()[1]
    assert ("Verdict: not yet landed" in text) is (header != "(landed)")


@pytest.mark.parametrize("status,extra,counted", [
    ("landed", {}, 1), ("done", {"close_reason": "completed"}, 1),
    ("done", {"close_reason": "not-planned"}, 0), ("abandoned", {}, 0),
    ("active", {}, 0), (None, {}, 0)])
def test_vr_c16_the_impact_report_counts_completed_issues(status, extra, counted):
    from compass_pkg import calibration
    impact = calibration.compute_impact([("the-issue", _with(
        status, extra, delivery_approach="feature", created="2026-10-01",
        land_timestamp="2026-10-08T09:00:00Z"))])
    assert impact["n_landed"] == counted


@pytest.mark.parametrize("status,extra,expired", [
    ("landed", {}, True), ("done", {"close_reason": "completed"}, True),
    ("done", {"close_reason": "not-planned"}, False), ("active", {}, False)])
def test_vr_c16_a_completed_issue_shows_its_issue_waiver_as_expired_at_land(
        tmp_path, status, extra, expired):
    import yaml
    sys.path.insert(0, str(ROOT / "tests"))
    from test_receipt_provenance import CHECK, ISSUE, _issue_waiver_case, _one, _receipt
    root, task_dir = _issue_waiver_case(tmp_path)
    path = task_dir / "manifest.yml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest.update(extra, status=status, land_timestamp="2026-10-08T10:00:00+00:00")
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    row = _one(_receipt(root), "waiver", f"issue:checks.{CHECK}")
    assert ("expired at land 2026-10-08" in row.text) is expired


def test_vr_c16_the_policy_diff_examines_every_issue_that_is_not_closed():
    sys.path.insert(0, str(ROOT / "tests"))
    from test_policy_diff import _advisory, _diff, _issue
    archive = [_issue("a-done", status="done"), _issue("b-landed", status="landed"),
               _issue("c-backlog", status="backlog"), _issue("d-queued", status="queued"),
               _issue("e-flight", status="in-progress"), _issue("f-abandoned", status="abandoned")]
    document = _diff(_advisory, archive=archive, open=True)["open"]
    assert [i["issue"] for i in document["issues"]] == ["c-backlog", "d-queued", "e-flight"]
    assert [i["status"] for i in document["issues"]] == ["backlog", "queued", "in-progress"]
    assert document["examined"] == 3


# --- VR-G9: no retired word in its retired meaning in shipped prose -----------
# Each pattern names a field, so `full` as a delivery approach, the machine
# names `landed_by`, `land_commit`, `land_timestamp` and `landed-by-resolves`,
# and the ordinary verb "to land" all pass. The retired list, the mapping and
# alias tables and the decision records are not scanned: they must name the
# old words.

import re
import subprocess

PROSE_ROOTS = ("commands", "skills", "agents", "docs", "governance")
PROSE_FILES = ("README.md", "CLAUDE.md", "compass-contract.md")
PROSE_SUFFIXES = (".md", ".yml", ".yaml", ".txt")
PROSE_SKIPPED = ("docs/compass/", "docs/system-spec", "docs/upgrade",
                 "governance/decisions/", "governance/terminology.yml",
                 "architecture/decisions/")
PROSE_MARKER = "vocabulary-scan: allow"

RETIRED_PROSE = {
    "a status field holding a retired status":
        r"\bstatus: ?`?(?:landed|queued|parked|abandoned|active)\b",
    "a retired status named as a state":
        r"`(?:landed|queued|parked|abandoned)`",
    "'blocks land' for 'blocks shipping'":
        r"\bblocks? land\b",
    "the run stage under its old name":
        r"--stage[ =]build\b",
    "the friction flag or key under its old name":
        r"--phase\b|--note-phase\b|\bphase: ?`?(?:assess|define|refine|plan|breakdown|implement|"
        r"verify|ship)\b",
    "a depth word used as a stage mode or an artifact depth":
        r"\b(?:mode|depth)s?: ?`?(?:full|light|full-plus-backfill)\b|`full-plus-backfill`",
}


def _prose_files(root):
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=str(root), capture_output=True,
                            text=True)
    if listed.returncode == 0 and listed.stdout:
        names = sorted(n for n in listed.stdout.split("\0") if n)
    else:                                   # not a git checkout: walk the folders
        names = sorted(str(p.relative_to(root)) for p in
                       [root / f for f in PROSE_FILES] + [
                           q for d in PROSE_ROOTS for q in (root / d).rglob("*")]
                       if p.is_file())
    for name in names:
        top = name.split("/", 1)[0]
        if (top in PROSE_ROOTS or name in PROSE_FILES) and name.endswith(PROSE_SUFFIXES) \
                and not name.startswith(PROSE_SKIPPED):
            yield name


def retired_prose(root):
    """`file:line: reason: text` for each line that uses a retired word in its
    retired meaning."""
    found = []
    for name in _prose_files(root):
        try:
            text = (Path(root) / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if PROSE_MARKER in line:
                continue
            for reason, pattern in RETIRED_PROSE.items():
                if re.search(pattern, line):
                    found.append(f"{name}:{number}: {reason}: {line.strip()[:100]}")
    return found


def test_vr_g9_shipped_prose_uses_no_retired_word_in_its_retired_meaning():
    found = retired_prose(ROOT)
    assert not found, f"{len(found)} lines:\n" + "\n".join(found[:60])


@pytest.mark.parametrize("line", [
    "The issue has `status: landed` in its manifest.",
    "Set it with status: parked and a reason.",
    "An issue is `queued` until it is picked up.",
    "A failing check blocks land for the whole branch.",
    "Run `compass run <slug> --stage build` to start.",
    "Record it with `compass issue friction --phase plan`.",
    "friction:\n  - phase: implement",
    "Each stage sets `mode: full` or `depth: light`.",
    "The slowest mode is `full-plus-backfill`.",
])
def test_vr_g9_a_planted_retired_use_is_reported(tmp_path, line):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "page.md").write_text(line + "\n", encoding="utf-8")
    found = retired_prose(tmp_path)
    assert found and found[0].startswith("docs/page.md:"), (line, found)


@pytest.mark.parametrize("line", [
    "The delivery approach is `full`, and a stage runs in `thorough` mode.",
    "`landed_by` names the commit; `land_commit` and `land_timestamp` hold the record.",
    "The check `landed-by-resolves` reads the pointer.",
    "A change lands when ship-commit commits it; the issue is `done`.",
    "Run `compass run <slug> --stage implement`.",
    "Record it with `compass issue friction --stage plan`.",
    "A stage `phase` is the older word for a stage.",
    "status: backlog",
    "`status: landed` is read as done  <!-- vocabulary-scan: allow - names the old word -->",
])
def test_vr_g9_an_allowed_use_is_not_reported(tmp_path, line):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "page.md").write_text(line + "\n", encoding="utf-8")
    assert retired_prose(tmp_path) == []


def test_vr_g9_the_retired_list_and_the_decision_records_are_not_scanned(tmp_path):
    for rel in ("governance/terminology.yml", "governance/decisions/x.md",
                "docs/compass/2026-10-08-x/note.md", "docs/system-spec.md"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("status: landed and --stage build\n", encoding="utf-8")
    assert retired_prose(tmp_path) == []
