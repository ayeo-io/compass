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
