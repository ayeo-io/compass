"""The board data: the rows `flow.board()` builds for the text board, `--json`
and the board page.

Scenario ids: TRC-A1, A6, A7, B3, B5, B8, B16, B18, D4 and W11 (issue
`compass-board`). The tests build small projects in temporary folders, or read
the tracked archive sample, and call `board()` or run `compass flow`.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from compass_pkg import flow, next_cmd, status_words  # noqa: E402
from compass_pkg.core import load_yaml, normalize_spine  # noqa: E402
from compass_pkg.stable_ids import STAGE_IDS  # noqa: E402

TODAY = datetime.date.today()
THIS = "this checkout"


# --- helpers -----------------------------------------------------------------

def _project(tmp_path, name="proj", git=False):
    root = tmp_path / name
    (root / ".compass" / "work").mkdir(parents=True)
    if git:
        # One commit, so the evidence check can name the tree as it is now.
        (root / "README.md").write_text("hello\n")
        for args in (["init", "-q"], ["add", "README.md"],
                     ["-c", "user.email=t@example.com", "-c", "user.name=t",
                      "commit", "-q", "-m", "base"]):
            subprocess.run(["git", *args], cwd=root, check=True)
    return root


def _write(root, slug, **fields):
    d = root / ".compass" / "work" / slug
    d.mkdir(parents=True, exist_ok=True)
    data = {"schema_version": "2.0", "issue": slug,
            "created": fields.pop("created", TODAY.isoformat())}
    data.update(fields)
    (d / "manifest.yml").write_text(yaml.safe_dump(data, sort_keys=False))
    return d


def _stages(**over):
    stages = {stage: "thorough" for stage in STAGE_IDS}
    stages.update(over)
    return stages


def _artifacts(*kinds):
    return [{"kind": kind, "path": f"{kind}.md", "status": "draft"} for kind in kinds]


def _assessed(**over):
    """The fields that make an issue assessed on the full approach."""
    fields = {"delivery_approach": "full", "stages": _stages()}
    fields.update(over)
    return fields


def _source(root, slug, tree=THIS, also_in=0, refused=None):
    return {"slug": slug, "task_dir": str(root / ".compass" / "work" / slug),
            "tree": tree, "tree_root": str(root), "also_in": also_in,
            "refused": refused}


def _board(root, **kw):
    return flow.board(str(root / ".compass" / "work"), today=TODAY, **kw)


def _row(data, slug):
    for key in ("in_progress", "stale", "in_review", "ready", "backlog",
                "done_this_week", "closed", "other", "unreadable"):
        for row in data[key]:
            if row["slug"] == slug:
                return row
    raise AssertionError(f"no row for {slug}")


def _run(root, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


def _flow_json(root):
    done = _run(root, "flow", "--json")
    assert done.returncode == 0, done.stdout + done.stderr
    return json.loads(done.stdout)


# --- TRC-A1 ------------------------------------------------------------------

RULES = [
    {"id": "RP-ONE", "kind": "requirement", "rationale": "Because the first.",
     "changed": ["gate 'verify.architecture' added", "stage 'refine' set to thorough"]},
    {"id": "RP-TWO", "kind": "cap", "rationale": "Because the second.",
     "changed": ["subtask count capped at 4", "pinned to one worktree"]},
]
GATES = [{"id": "verify.correctness", "status": "pass"},
         {"id": "verify.governance", "status": "pending"},
         {"id": "verify.security", "status": "pending"}]


def test_trc_a1_board_data_carries_the_why_for_each_open_issue(tmp_path):
    root = _project(tmp_path, git=True)
    _write(root, "why-me", **_assessed(
        current_phase="verify", gates=GATES, policy_rules_fired=RULES,
        assessment={"risk": "cross-cutting", "familiarity": "brownfield-mapped",
                    "size": "large", "goal": "delivery", "role": "engineer",
                    "labels": ["public-api", "cli"], "unlisted": "not copied"}))
    out = _flow_json(root)
    row = next(r for r in out["board"]["in_review"] if r["slug"] == "why-me")
    assert row["assessment"] == {
        "risk": "cross-cutting", "familiarity": "brownfield-mapped", "size": "large",
        "goal": "delivery", "role": "engineer", "labels": ["public-api", "cli"]}
    assert row["policy_rules_fired"] == RULES
    assert row["stage_depths"] == _stages()
    assert list(row["stage_depths"]) == list(STAGE_IDS)
    assert row["gate_list"] == GATES
    assert row["gates"] == "1/3"
    assert row["stage"] == "verify"
    assert row["manifest_path"] == ".compass/work/why-me/manifest.yml"
    assert row["tree"] == THIS and row["also_in"] == 0
    assert row["lane"] == "verify"


def test_swarm_and_the_other_retired_words_read_in_the_6_0_words(tmp_path):
    root = _project(tmp_path)
    _write(root, "archived", delivery_approach="full",
           stages=_stages(assess="full", refine="light", breakdown="swarm"),
           assessment={"risk": "contained", "size": "standard"})
    row = _row(_board(root), "archived")
    assert row["stage_depths"]["assess"] == "thorough"
    assert row["stage_depths"]["refine"] == "lightweight"
    assert row["stage_depths"]["breakdown"] == "multiagent"
    assert row["assessment"]["size"] == "medium"


# --- TRC-A6 ------------------------------------------------------------------

PAYLOAD_KEYS = {"summary", "sections", "counts", "board", "friction", "title"}
SECTION_KEYS = {"in_progress", "stale", "in_review", "ready", "backlog",
                "done_this_week", "closed", "other", "unreadable"}
_WORK = {"slug", "delivery_approach", "state", "stage", "gates", "evidence"}
# Written by hand from the rows 6.0.0 built, not read from the code.
KEYS_AT_6_0_0 = {
    "in_progress": _WORK, "stale": _WORK, "in_review": _WORK,
    "ready": {"slug", "delivery_approach", "state"},
    "backlog": {"slug", "delivery_approach", "state", "age_days", "signal", "reason"},
    "done_this_week": {"slug", "delivery_approach", "state", "completed"},
    "closed": {"slug", "delivery_approach", "state", "close_reason"},
    "other": {"slug", "delivery_approach", "status"},
    "unreadable": {"slug", "note"},
}
ADDED_TO_A_PLACED_ROW = {
    "lane", "stage", "gates", "gate_list", "assessment", "policy_rules_fired",
    "stage_depths", "tree", "manifest_path", "also_in", "created", "set_aside",
    "recommendation", "unplaceable"}
ADDED_TO_AN_UNPLACED_ROW = {"tree", "manifest_path", "also_in"}
KEYS_NOW = {
    key: (old | ADDED_TO_AN_UNPLACED_ROW | ({"note"} if key == "other" else set())
          if key in ("other", "unreadable") else old | ADDED_TO_A_PLACED_ROW)
    for key, old in KEYS_AT_6_0_0.items()}
# `close_reason` is text, so it is on the rows of an issue that is done only.
KEYS_NOW["done_this_week"] = KEYS_NOW["done_this_week"] | {"close_reason"}


def _nine_sections(root):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    _write(root, "s-in-progress", **_assessed(artifacts=_artifacts("technical-design")))
    stale = _write(root, "s-stale", **_assessed(
        artifacts=_artifacts("technical-design"),
        evidence=[{"type": "test-run", "path": "evidence/green.json",
                   "scenario": "TRC-1"}]))
    (stale / "evidence").mkdir()
    (stale / "evidence" / "green.json").write_text(json.dumps(
        {"tree_id": "0123456789abcdef0123456789abcdef01234567",
         "timestamp": "2026-10-01T00:00:00+00:00"}))
    _write(root, "s-in-review", **_assessed(gates=GATES))
    _write(root, "s-ready", **_assessed(
        artifacts=_artifacts("acceptance-criteria", "requirements-review")))
    _write(root, "s-backlog", status="backlog", **_assessed())
    _write(root, "s-done", status="done", close_reason="completed",
           land_timestamp=now, **_assessed())
    _write(root, "s-closed", status="done", close_reason="not-planned", **_assessed())
    _write(root, "s-other", status="wibble", **_assessed())
    (root / ".compass" / "work" / "s-unreadable").mkdir()


def test_trc_a6_json_keeps_every_6_0_0_key_and_only_adds_new_ones(tmp_path):
    root = _project(tmp_path, git=True)
    _nine_sections(root)
    out = _flow_json(root)
    assert set(out) == PAYLOAD_KEYS
    assert set(out["board"]) == SECTION_KEYS
    for key, rows in out["board"].items():
        assert rows, f"no {key} row was built, so its keys are not pinned"
        for row in rows:
            assert set(row) - {"blocked"} == KEYS_NOW[key], (key, sorted(row))
            assert KEYS_AT_6_0_0[key] <= set(row), key
    in_progress = out["board"]["in_progress"][0]
    assert in_progress["state"] == "in-progress" and in_progress["gates"] == "0/0"
    assert out["board"]["stale"][0]["evidence"] == "stale"
    assert out["board"]["other"][0]["status"] == "wibble"
    assert out["board"]["done_this_week"][0]["close_reason"] == "completed"
    assert out["board"]["closed"][0]["close_reason"] == "not-planned"


def test_trc_a6_what_the_page_cannot_place_keeps_its_6_0_0_section(tmp_path):
    root = _project(tmp_path)
    _write(root, "future", schema_version="4.0", status="backlog", **_assessed())
    _write(root, "no-such-stage", current_phase="nonsense",
           **_assessed(artifacts=_artifacts("technical-design")))
    _write(root, "bad-assessment", status="backlog",
           **_assessed(assessment="not a mapping"))
    _write(root, "bad-rules", status="backlog",
           **_assessed(policy_rules_fired="not a list"))
    _write(root, "bad-stages", status="backlog", delivery_approach="full",
           stages="not a mapping")
    _write(root, "fine", status="backlog", **_assessed())
    data = _board(root)
    sections = {slug: next(k for k in ("in_progress", "backlog", "ready", "unreadable")
                           if any(r["slug"] == slug for r in data[k]))
                for slug in ("future", "no-such-stage", "bad-assessment", "bad-rules",
                             "bad-stages", "fine")}
    assert sections == {"future": "backlog", "no-such-stage": "in_progress",
                        "bad-assessment": "backlog", "bad-rules": "backlog",
                        "bad-stages": "backlog", "fine": "backlog"}
    reasons = {slug: _row(data, slug)["unplaceable"] for slug in sections}
    assert reasons["fine"] is None and _row(data, "fine")["lane"] == "backlog"
    assert "schema_version" in reasons["future"]
    assert "current_phase" in reasons["no-such-stage"]
    assert "assessment" in reasons["bad-assessment"]
    assert "policy_rules_fired" in reasons["bad-rules"]
    assert "stages" in reasons["bad-stages"]
    for slug in ("future", "no-such-stage", "bad-assessment", "bad-rules", "bad-stages"):
        assert _row(data, slug)["lane"] is None, slug
    assert _row(data, "bad-assessment")["assessment"] is None
    assert _row(data, "bad-rules")["policy_rules_fired"] == []
    assert _row(data, "bad-stages")["stage_depths"] == {}


def test_the_board_counts_done_issues_by_close_reason(tmp_path):
    root = _project(tmp_path)
    now = datetime.datetime.now(datetime.timezone.utc)
    old = now - datetime.timedelta(days=9)
    _write(root, "d-new", status="done", close_reason="completed",
           land_timestamp=now.isoformat(), **_assessed())
    _write(root, "d-old", status="done", close_reason="completed",
           land_timestamp=old.isoformat(), **_assessed())
    for n in (1, 2):
        _write(root, f"d-np{n}", status="done", close_reason="not-planned", **_assessed())
    _write(root, "d-dup", status="done", close_reason="duplicate", **_assessed())
    _write(root, "d-bare", status="done", **_assessed())
    data = _board(root)
    assert data["done_by_reason"] == {"completed": 2, "not-planned": 2, "duplicate": 1}
    assert [r["slug"] for r in data["done_this_week"]] == ["d-new"]
    assert _row(data, "d-new")["lane"] == "done"
    assert _row(data, "d-np1")["lane"] is None
    assert [r["slug"] for r in data["other"]] == ["d-bare"]


def test_the_text_board_says_set_aside_and_no_retired_hold_word(tmp_path):
    root = _project(tmp_path)
    _write(root, "waiting", status="backlog", parked_reason="needs a decision",
           **_assessed())
    text = _run(root, "flow").stdout
    assert "set aside: needs a decision" in text, text
    assert not re.search(r"\bheld\b", text, re.I), text


# --- TRC-A7 ------------------------------------------------------------------

def _reopened_sample(tmp_path):
    """The tracked archive sample with every issue open again. Each issue in the
    sample is done, so the copy drops the keys that close it and keeps the
    records (artifacts, subtasks, evidence, gates) that place it in a stage."""
    import shutil
    import archive
    sample = archive.sample_root()
    root = tmp_path / "reopened"
    shutil.copytree(sample / ".compass" / "work", root / ".compass" / "work")
    if (sample / "docs" / "compass").is_dir():
        shutil.copytree(sample / "docs" / "compass", root / "docs" / "compass")
    for path in (root / ".compass" / "work").glob("*/manifest.yml"):
        manifest = yaml.safe_load(path.read_text())
        for key in ("status", "close_reason", "land_timestamp", "land_commit"):
            manifest.pop(key, None)
        path.write_text(yaml.safe_dump(manifest, sort_keys=False))
    return root / ".compass" / "work"


def _assessed_open_rows(data):
    sections = ("in_progress", "stale", "in_review", "ready", "backlog")
    return [row for key in sections for row in data[key]
            if row["delivery_approach"] != "not assessed"]


def test_trc_a7_the_board_stage_is_the_stage_compass_next_computes(tmp_path):
    work = _reopened_sample(tmp_path)
    data = flow.board(str(work), today=TODAY)
    rows = _assessed_open_rows(data)
    assert len(rows) >= 10, "the reopened sample should hold assessed open issues"
    for row in rows:
        task_dir = str(work / row["slug"])
        manifest = normalize_spine(load_yaml(os.path.join(task_dir, "manifest.yml")))
        expected = next_cmd._current_phase_from_task(manifest, task_dir) or "done"
        assert row["stage"] == expected, row["slug"]


def test_trc_a7_replacing_the_stage_function_changes_the_board(tmp_path, monkeypatch):
    work = _reopened_sample(tmp_path)
    before = {r["slug"]: r["stage"]
              for r in _assessed_open_rows(flow.board(str(work), today=TODAY))}
    assert len(set(before.values())) > 1, "the sample should span several stages"
    monkeypatch.setattr(next_cmd, "_current_phase_from_task",
                        lambda task, task_dir=None: "verify")
    rows = _assessed_open_rows(flow.board(str(work), today=TODAY))
    assert {r["slug"] for r in rows} == set(before)
    assert {row["stage"] for row in rows} == {"verify"}


# --- placement ---------------------------------------------------------------

def test_trc_b3_the_backlog_lane_holds_only_unassessed_and_set_aside_issues(tmp_path):
    root = _project(tmp_path)
    _write(root, "set-aside", status="backlog", parked_reason="waiting for a decision",
           **_assessed(artifacts=_artifacts("technical-design", "distribution-map")))
    _write(root, "new-idea", status="backlog", created="2026-09-01")
    _write(root, "bare-idea")
    _write(root, "defining", **_assessed())
    data = _board(root)
    set_aside, new_idea = _row(data, "set-aside"), _row(data, "new-idea")
    assert (set_aside["lane"], set_aside["stage"]) == ("backlog", "implement")
    assert (new_idea["lane"], new_idea["stage"]) == ("backlog", "assess")
    assert _row(data, "bare-idea")["lane"] == "backlog"
    assert _row(data, "bare-idea")["stage"] == "assess"
    defining = _row(data, "defining")
    assert (defining["lane"], defining["stage"], defining["state"]) == (
        "define", "define", "backlog")
    assert set_aside["set_aside"] is True and new_idea["set_aside"] is True
    assert set_aside["reason"] == "waiting for a decision"
    assert defining["set_aside"] is False
    assert _row(data, "new-idea")["delivery_approach"] == "not assessed"
    assert _row(data, "new-idea")["created"] == "2026-09-01"


def test_trc_b5_a_ready_issue_sits_in_the_lane_of_its_next_stage(tmp_path):
    root = _project(tmp_path)
    _write(root, "ready-one", **_assessed(
        artifacts=_artifacts("acceptance-criteria", "requirements-review")))
    data = _board(root)
    row = _row(data, "ready-one")
    assert [r["slug"] for r in data["ready"]] == ["ready-one"]
    assert (row["state"], row["stage"], row["lane"]) == ("ready", "plan", "plan")
    assert row["delivery_approach"] == "full"


def test_trc_b8_a_blocked_flag_outside_in_progress_and_in_review_is_not_carried(tmp_path):
    root = _project(tmp_path)
    flag = {"reason": "waiting for the schema review", "at": "2026-10-01"}
    _write(root, "blocked-ready", blocked=flag, **_assessed(
        artifacts=_artifacts("acceptance-criteria", "requirements-review")))
    _write(root, "blocked-aside", status="backlog", blocked=flag, **_assessed())
    _write(root, "blocked-working", blocked=flag,
           **_assessed(artifacts=_artifacts("technical-design")))
    data = _board(root)
    # Each card is placed in its lane without the flag, so the page has nothing
    # to show and nothing to count for them.
    assert _row(data, "blocked-ready")["lane"] == "plan"
    assert _row(data, "blocked-aside")["lane"] == "backlog"
    assert _row(data, "blocked-working")["lane"] == "breakdown"
    assert "blocked" not in _row(data, "blocked-ready")
    assert "blocked" not in _row(data, "blocked-aside")
    assert _row(data, "blocked-working")["blocked"] == "waiting for the schema review"
    carrying = [r["slug"] for key in ("in_progress", "stale", "in_review", "ready", "backlog")
                for r in data[key] if "blocked" in r]
    assert carrying == ["blocked-working"]


def test_trc_b16_an_assessed_issue_sits_in_the_lane_compass_next_computes(tmp_path):
    root = _project(tmp_path)
    _write(root, "defining", **_assessed())
    _write(root, "early-design", **_assessed(artifacts=_artifacts("technical-design")))
    data = _board(root)
    defining, early = _row(data, "defining"), _row(data, "early-design")
    assert (defining["lane"], defining["state"]) == ("define", "backlog")
    assert (early["lane"], early["state"]) == ("breakdown", "in-progress")
    for row, slug in ((defining, "defining"), (early, "early-design")):
        task_dir = str(root / ".compass" / "work" / slug)
        manifest = normalize_spine(load_yaml(os.path.join(task_dir, "manifest.yml")))
        assert row["stage"] == next_cmd._current_phase_from_task(manifest, task_dir)
    assert data["counts"] == {"backlog": 1, "in-progress": 1}


def test_trc_b18_an_open_issue_past_verify_sits_in_the_ship_lane(tmp_path):
    root = _project(tmp_path)
    passed = [{"id": "verify.correctness", "status": "pass"},
              {"id": "verify.governance", "status": "pass"}]
    _write(root, "all-passed", **_assessed(gates=passed))
    _write(root, "no-stage-left", **_assessed(
        gates=passed, stages=_stages(ship="skipped")))
    data = _board(root)
    shipping = _row(data, "all-passed")
    assert (shipping["lane"], shipping["state"], shipping["stage"]) == (
        "ship", "in-review", "ship")
    # `compass next` names no stage here, and the row keeps the word it used.
    nothing_left = _row(data, "no-stage-left")
    assert (nothing_left["lane"], nothing_left["state"], nothing_left["stage"]) == (
        "ship", "in-review", "done")


# --- TRC-D4 ------------------------------------------------------------------

def test_trc_d4_a_manifest_the_page_cannot_place_hides_no_other_issue(tmp_path):
    root = _project(tmp_path)
    work = root / ".compass" / "work"
    (work / "no-manifest").mkdir()
    (work / "bad-yaml").mkdir()
    (work / "bad-yaml" / "manifest.yml").write_text("key: [unclosed\n  - : :\n")
    _write(root, "wrong-type", **_assessed(artifacts=_artifacts("technical-design"),
                                           gates=5))
    _write(root, "odd-status", status="wibble", **_assessed())
    _write(root, "done-bare", status="done", **_assessed())
    _write(root, "schema-4", schema_version="4.0", **_assessed())
    _write(root, "no-stage", current_phase="nonsense", **_assessed())
    readable = [f"readable-{n}" for n in range(5)]
    for slug in readable:
        _write(root, slug, **_assessed())
    data = _board(root)
    unplaced = {}
    for row in data["unreadable"]:
        unplaced[row["slug"]] = row["note"]
    for row in data["other"]:
        unplaced[row["slug"]] = row["note"]
    for key in ("in_progress", "stale", "in_review", "ready", "backlog"):
        for row in data[key]:
            if row["unplaceable"]:
                unplaced[row["slug"]] = row["unplaceable"]
    assert sorted(unplaced) == sorted(
        ["no-manifest", "bad-yaml", "wrong-type", "odd-status", "done-bare",
         "schema-4", "no-stage"])
    assert all(isinstance(why, str) and why for why in unplaced.values()), unplaced
    assert "schema_version" in unplaced["schema-4"]
    assert "current_phase" in unplaced["no-stage"]
    assert "close reason" in unplaced["done-bare"]
    assert "wibble" in unplaced["odd-status"]
    for slug in readable:
        assert _row(data, slug)["lane"] == "define", slug
        assert _row(data, slug)["unplaceable"] is None
    for slug in unplaced:
        row = _row(data, slug)
        assert row["tree"] == THIS
        assert row["manifest_path"] == f".compass/work/{slug}/manifest.yml"
        assert row["also_in"] == 0


def test_trc_d4_the_board_reads_a_schema_major_of_one_two_or_three_only():
    assert flow._schema_major_is_read(None)
    assert flow._schema_major_is_read("")
    for version in ("1.0", "2.0", "3.2", 2, 2.0, "3"):
        assert flow._schema_major_is_read(version), version
    for version in ("4.0", "0.9", 4, "x"):
        assert not flow._schema_major_is_read(version), version


# --- TRC-W11 -----------------------------------------------------------------

def test_trc_w11_an_issue_from_another_tree_is_judged_by_that_trees_records(
        tmp_path, monkeypatch):
    here = _project(tmp_path, "here")
    side = _project(tmp_path, "side")
    monkeypatch.chdir(here)
    side_gates = [{"id": "verify.correctness", "status": "pending"},
                  {"id": "side.only-gate", "status": "pass"}]
    side_depths = _stages(define="lightweight", refine="skipped", breakdown="skipped")
    _write(side, "side-only", delivery_approach="full", stages=side_depths,
           gates=side_gates, artifacts=_artifacts("technical-design"))
    _write(side, "side-idea", status="backlog", created="2026-09-20", **_assessed())
    notes = side / "docs" / "compass" / "2026-09-20-side-idea"
    notes.mkdir(parents=True)
    (notes / "notes.md").write_text("# Recommendation\n\nDo the small thing.\n")
    _write(side, "side-regular", created="2026-09-21", delivery_approach="regular",
           stages=_stages(), scenarios=[{"id": "TRC-1", "title": "t"}])
    review = side / "docs" / "compass" / "2026-09-21-side-regular"
    review.mkdir(parents=True)
    (review / "requirements-review.md").write_text("# Requirements review\n")
    sources = [_source(side, slug, tree="side")
               for slug in ("side-only", "side-idea", "side-regular")]
    data = _board(here, sources=sources)
    only = _row(data, "side-only")
    assert only["gate_list"] == side_gates and only["gates"] == "1/2"
    assert only["stage_depths"] == side_depths
    assert only["tree"] == "side"
    assert only["manifest_path"] == ".compass/work/side-only/manifest.yml"
    idea = _row(data, "side-idea")
    assert idea["recommendation"] is True and "recommendation" in idea["signal"]
    assert idea["tree"] == "side"
    # Resolved from the issue's own tree: the review sits in `side`, not here.
    assert _row(data, "side-regular")["state"] == "ready"
    assert not (here / "docs").exists()


def test_a_here_issue_with_no_documents_has_no_recommendation(tmp_path):
    root = _project(tmp_path)
    _write(root, "plain", status="backlog", **_assessed())
    assert _row(_board(root), "plain")["recommendation"] is False


def test_trc_w11_read_checkout_parses_each_manifest_once_and_board_reuses_it(
        tmp_path, monkeypatch):
    root = _project(tmp_path)
    _write(root, "one", **_assessed())
    _write(root, "two", status="done", close_reason="duplicate", **_assessed())
    (root / ".compass" / "work" / "none").mkdir()
    (root / ".compass" / "work" / "garbled").mkdir()
    (root / ".compass" / "work" / "garbled" / "manifest.yml").write_text("a: [oops\n")
    parsed = flow.read_checkout(str(root / ".compass" / "work"))
    assert sorted(parsed) == ["garbled", "none", "one", "two"]
    assert isinstance(parsed["one"], dict) and parsed["one"]["issue"] == "one"
    assert status_words.is_closed(parsed["two"])
    assert parsed["none"] == "no manifest.yml"
    assert parsed["garbled"] == "unreadable manifest.yml"
    calls = []
    real = flow.load_yaml
    monkeypatch.setattr(flow, "load_yaml", lambda path: calls.append(path) or real(path))
    sources = [_source(root, slug) for slug in sorted(parsed)]
    data = _board(root, sources=sources, parsed=parsed)
    assert [c for c in calls if c.endswith("manifest.yml")] == []
    assert [r["slug"] for r in data["unreadable"]] == ["garbled", "none"]
    assert [r["note"] for r in data["unreadable"]] == [
        "unreadable manifest.yml", "no manifest.yml"]
    assert _row(data, "one")["lane"] == "define"


def test_trc_w11_a_refused_folder_is_never_read(tmp_path, monkeypatch):
    here = _project(tmp_path, "here")
    outside = _project(tmp_path, "outside")
    _write(outside, "escape", **_assessed())
    calls = []
    real = flow.load_yaml
    monkeypatch.setattr(flow, "load_yaml", lambda path: calls.append(path) or real(path))
    source = _source(outside, "escape", tree="side",
                     refused="its folder leads out of the tree")
    data = _board(here, sources=[source])
    assert [c for c in calls if "escape" in c] == []
    assert data["unreadable"] == [{
        "slug": "escape", "note": "its folder leads out of the tree", "tree": "side",
        "manifest_path": ".compass/work/escape/manifest.yml", "also_in": 0}]
    assert data["total"] == 1
