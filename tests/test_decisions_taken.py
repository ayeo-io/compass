"""Decisions an agent took for the person (issue
`artifact-status-written-by-stages`, group C, ASW-26 to ASW-33).

Each test builds a scratch git repository with `compass init` and
`compass approach evaluate --write`, then drives `cli/compass`. `approve` and
`issue decision set` get a pseudo-terminal, as a person at a keyboard has one.

Scenario ids: `ASW-26` to `ASW-33`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from artifact_status_support import (DOCS, HUMAN_DESIGN, SLUG, approve, edit,  # noqa: E402
                                     manifest, manifest_file, project, register, run,
                                     write_manifest)

REVIEW = f"{DOCS}/requirements-review.md"


def _ledger(root, *blocks):
    """Write the requirements review. Each block is (id, question, resolution,
    decided_by)."""
    lines = ["# Requirements review", "", "## Ambiguity ledger", ""]
    for ident, question, resolution, by in blocks:
        lines += [f"### {ident} - A title", "",
                  f"- **Question:** {question}",
                  f"- **Resolution (working answer, pending review):** {resolution}",
                  "  and a second line of the resolution.",
                  f"- **Decided by:** {by}",
                  "- **Status:** resolved", ""]
    (root / REVIEW).write_text("\n".join(lines), encoding="utf-8")


def _decisions(root):
    return {d["id"]: d for d in manifest(root).get("decisions_taken") or []}


def _from_ledger(root):
    return run(root, "issue", "decision", "add", "--from-ledger", "--issue", SLUG)


def _entry(ident, status="open", stage="define", by="builder", **more):
    return {"id": ident, "question": f"Question {ident}?", "resolution": f"Answer {ident}.",
            "by": by, "stage": stage, "status": status, **more}


def _specify_done(root):
    """The records show the path's specify work done: one scenario with an id, an
    intent and a declared test (ADR-092). A listed `specify` checkpoint still waits."""
    (root / REVIEW).unlink(missing_ok=True)
    code, out, err = run(root, "scenario", "add", "TRC-001", "--issue", SLUG, "--intent",
                         "INT-1", "--title", "one", "--test", "tests/test_one.py::test_one")
    assert code == 0, out + err


def _waiting_project(tmp_path, checkpoints, entries, compass_yml=HUMAN_DESIGN,
                     specified=True):
    root = project(tmp_path, compass_yml=compass_yml)
    # `compass next` needs the approach record beside the manifest.
    (manifest_file(root).parent / "delivery-approach.md").write_text("# Approach\n")
    if specified:
        _specify_done(root)
    edit(root, checkpoints=checkpoints, decisions_taken=entries)
    return root


def _next(root):
    code, out, err = run(root, "next", "--issue", SLUG)
    assert code == 0, out + err
    return out


def _stage(root):
    """The stage the resolver gives, which the checkpoints act on: a path stage on a
    path issue (ADR-092)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cli"))
    from compass_pkg import next_cmd
    from compass_pkg.core import normalize_spine
    task_dir = manifest_file(root).parent
    return next_cmd._current_phase_from_task(
        next_cmd._typed(normalize_spine(manifest(root))), str(task_dir))


def _approvals(root):
    return [e for e in manifest(root).get("evidence") or []
            if e.get("type") == "artifact-approval" and e.get("decisions")]


# --- ASW-26 ---------------------------------------------------------------------

def test_asw_26_ledger_agent_decisions_recorded(tmp_path):
    root = project(tmp_path)
    _ledger(root, ("Q1", "First?", "Do the first.", "spec-author"),
            ("Q2", "Second?", "Do the second.", "the builder, from the maintainer's default"),
            ("Q3", "Third?", "Do the third.", "jed72, the maintainer"))
    code, out, err = _from_ledger(root)
    assert code == 0, out + err
    got = _decisions(root)
    assert sorted(got) == ["Q1", "Q2"]
    assert got["Q1"]["by"] == "spec-author" and got["Q2"]["by"] == "builder"
    assert got["Q1"]["question"] == "First?"
    assert got["Q1"]["resolution"] == "Do the first. and a second line of the resolution."
    assert got["Q1"]["stage"] == "refine" and got["Q1"]["status"] == "open"
    before = manifest_file(root).read_bytes()
    assert _from_ledger(root)[0] == 0
    assert manifest_file(root).read_bytes() == before
    # A reworded question keeps a confirmed entry confirmed.
    body = manifest(root)
    body["decisions_taken"][0]["status"] = "confirmed"
    write_manifest(root, body)
    _ledger(root, ("Q1", "First, reworded?", "Do the first.", "spec-author"),
            ("Q2", "Second?", "Do the second.", "the builder, from the maintainer's default"))
    assert _from_ledger(root)[0] == 0
    got = _decisions(root)
    assert got["Q1"]["question"] == "First, reworded?" and got["Q1"]["status"] == "confirmed"
    assert "reason" not in got["Q1"]
    # A changed resolution reopens it.
    _ledger(root, ("Q1", "First, reworded?", "Do something else.", "spec-author"),
            ("Q2", "Second?", "Do the second.", "the builder, from the maintainer's default"))
    assert _from_ledger(root)[0] == 0
    got = _decisions(root)
    assert got["Q1"]["status"] == "reopened"
    assert got["Q1"]["reason"] == "the resolution changed in the ledger"
    assert got["Q1"]["resolution"] == "Do something else. and a second line of the resolution."
    assert got["Q2"]["status"] == "open"


# --- ASW-27 ---------------------------------------------------------------------

def test_asw_27_decision_add_records_one_entry(tmp_path):
    root = project(tmp_path)
    assert "decisions_taken" not in manifest(root)
    code, out, err = run(root, "issue", "decision", "add", "D-1", "--question", "Which?",
                         "--resolution", "This one.", "--by", "planner", "--stage", "plan",
                         "--issue", SLUG)
    assert code == 0, out + err
    assert manifest(root)["decisions_taken"] == [
        {"id": "D-1", "question": "Which?", "resolution": "This one.", "by": "planner",
         "stage": "plan", "status": "open"}]
    before = manifest_file(root).read_bytes()
    for argv, word in (
            (("D-1", "--by", "planner", "--stage", "plan"), "exists"),
            (("D-2", "--by", "jed72", "--stage", "plan"), "agent"),
            (("D-3", "--by", "planner", "--stage", "deploy"), "stage")):
        code, out, err = run(root, "issue", "decision", "add", *argv, "--question", "q",
                             "--resolution", "r", "--issue", SLUG)
        assert code == 2 and word in (out + err), (argv, out + err)
    assert manifest_file(root).read_bytes() == before


# --- ASW-28 ---------------------------------------------------------------------

# On the four-stage path the define, refine and plan hand-offs are the one specify
# hand-off (ADR-092 decision 1), so a decision taken at define waits at specify.

def test_asw_28_balanced_define_checkpoint_waits_once(tmp_path):
    root = _waiting_project(tmp_path, ["specify"],
                            [_entry("D-1"), _entry("D-2")])
    out = _next(root)
    first = out.splitlines()[0]
    assert first == "Waiting at the specify checkpoint: 2 decision(s) to confirm"
    assert "Answer D-1." in out and "Answer D-2." in out
    assert "Build" not in out
    before = manifest_file(root).read_bytes()
    code, out, err = approve(root, "--decisions", approver="alex",
                             scope="requirement decisions")
    assert code == 2 and "alex" in out + err
    assert manifest_file(root).read_bytes() == before
    code, out, err = approve(root, "--decisions", scope="requirement decisions")
    assert code == 0, out + err
    records = _approvals(root)
    assert len(records) == 1 and records[0]["decisions"] == ["D-1", "D-2"]
    assert records[0]["approver"] == "jed72" and records[0]["stage"] == "specify"
    assert {d["status"] for d in _decisions(root).values()} == {"confirmed"}
    # The decisions no longer hold the issue; the specify hand-off itself still
    # waits for its own answer, so the stage stays specify.
    assert _stage(root) == "specify"
    after = _next(root).splitlines()[0]
    assert after.startswith("Specify") and "decision(s) to confirm" not in after, after
    # Nothing is left to confirm.
    assert approve(root, "--decisions")[0] == 2


def test_asw_28_without_declared_approvers_the_owner_confirms(tmp_path):
    root = _waiting_project(tmp_path, ["specify"], [_entry("D-1")],
                            compass_yml={"schema": 1, "owner": "jed72"})
    assert approve(root, "--decisions", approver="alex")[0] == 2
    assert _decisions(root)["D-1"]["status"] == "open"
    assert approve(root, "--decisions")[0] == 0
    assert _decisions(root)["D-1"]["status"] == "confirmed"


def test_asw_28_rejected_is_refused(tmp_path):
    root = _waiting_project(tmp_path, ["specify"], [_entry("D-1")])
    code, out, err = approve(root, "--decisions", "--decision", "rejected")
    assert code == 2 and "compass issue decision set" in out + err
    assert _decisions(root)["D-1"]["status"] == "open"


# --- ASW-29 ---------------------------------------------------------------------

def test_asw_29_controlled_define_checkpoint_waits(tmp_path):
    # Controlled autonomy lists every path stage where `S17` applies.
    root = _waiting_project(tmp_path, ["assess", "specify", "build", "ship"],
                            [_entry("D-1", by="spec-author")])
    out = _next(root)
    assert out.splitlines()[0] == "Waiting at the specify checkpoint: 1 decision(s) to confirm"
    assert "Answer D-1." in out


# --- ASW-30 ---------------------------------------------------------------------

def test_asw_30_autonomous_lists_without_waiting(tmp_path):
    root = _waiting_project(tmp_path, [], [_entry("D-1"), _entry("D-2")])
    out = _next(root)
    # With no checkpoint listed, specify is done once its scenarios exist.
    assert _stage(root) == "build"
    assert out.splitlines()[0].startswith("Build")
    assert "Waiting" not in out
    assert "Answer D-1." in out and "Answer D-2." in out
    assert {d["status"] for d in _decisions(root).values()} == {"open"}
    assert not _approvals(root)


# --- ASW-31 ---------------------------------------------------------------------

def test_asw_31_change_reopens_decision_and_wait_continues(tmp_path):
    root = _waiting_project(tmp_path, ["specify"], [_entry("D-1"), _entry("D-2")])
    argv = ("issue", "decision", "set", "D-2", "--status", "reopened", "--reason",
            "the default is wrong", "--issue", SLUG)
    before = manifest_file(root).read_bytes()
    assert run(root, *argv)[0] == 2                      # no terminal
    code, out, err = run(root, "issue", "decision", "set", "D-2", "--status", "confirmed",
                         "--reason", "x", "--issue", SLUG, terminal=True)
    assert code != 0                                     # confirmed is written only by approve
    assert manifest_file(root).read_bytes() == before
    code, out, err = run(root, *argv, terminal=True)
    assert code == 0, out + err
    got = _decisions(root)
    assert got["D-2"]["status"] == "reopened" and got["D-2"]["reason"] == "the default is wrong"
    assert got["D-1"]["status"] == "open"
    assert not _approvals(root)
    out = _next(root)
    assert out.splitlines()[0] == "Waiting at the specify checkpoint: 2 decision(s) to confirm"
    assert "D-2" in out and "reopened" in out and "the default is wrong" in out


# --- ASW-32 ---------------------------------------------------------------------

def test_asw_32_later_decision_waits_at_next_checkpoint(tmp_path):
    # On the path the hand-offs are assess, specify, build and ship (ADR-092): a
    # decision taken at assess waits at assess, and one taken while the scenarios
    # are written waits at specify, once they exist.
    root = _waiting_project(tmp_path, ["assess", "specify"], [_entry("D-1", stage="assess")],
                            specified=False)
    assert _next(root).splitlines()[0] == (
        "Waiting at the assess checkpoint: 1 decision(s) to confirm")
    assert approve(root, "--decisions")[0] == 0
    _ledger(root, ("Q4", "Fourth?", "Do the fourth.", "spec-author"))
    assert _from_ledger(root)[0] == 0
    _specify_done(root)
    out = _next(root)
    assert out.splitlines()[0] == "Waiting at the specify checkpoint: 1 decision(s) to confirm"
    assert "Answer D-1." not in out and "Do the fourth." in out
    code, out, err = approve(root, "--decisions")
    assert code == 0, out + err
    assert _decisions(root)["Q4"]["status"] == "confirmed"
    # The specify hand-off is answered, so the issue moves on to build.
    code, out, err = run(root, "evidence", "approve", "--checkpoint", "specify", "--issue", SLUG,
                         "--approver", "jed72", "--role", "maintainer", terminal=True)
    assert code == 0, out + err
    code, out, err = run(root, "issue", "decision", "add", "D-5", "--question", "q",
                         "--resolution", "r", "--by", "builder", "--stage", "implement",
                         "--issue", SLUG)
    assert code == 0, out + err
    out = _next(root)
    assert _stage(root) == "build"
    assert "Waiting" not in out and out.splitlines()[0].startswith("Build")
    assert _decisions(root)["D-5"]["status"] == "open"


# --- ASW-33 ---------------------------------------------------------------------

def _second_issue(root, slug, entries, **more):
    folder = root / ".compass" / "work" / slug
    folder.mkdir(parents=True)
    body = dict(manifest(root), issue=slug, decisions_taken=entries, **more)
    body.pop("artifacts", None)
    write_manifest(root, body, slug)


def test_asw_33_the_report_counts_decision_shares(tmp_path):
    from compass_pkg import decisions_taken
    root = project(tmp_path, evaluate=False)
    edit(root, decisions_taken=[_entry("A-1", "confirmed"), _entry("A-2", "confirmed")])
    _second_issue(root, "second", [_entry("B-1", "reopened", reason="changed")])
    _second_issue(root, "third", [_entry("C-1", "open")], status="done",
                  close_reason="completed")
    got = decisions_taken.report(str(root / ".compass" / "work"))
    assert (got["total"], got["confirmed"], got["changed"], got["never_confirmed"]) == (4, 2, 1, 1)
    assert got["open_in_flight"] == 0
    assert got["share"] == {"confirmed": 50, "changed": 25, "never_confirmed": 25}


# --- D205: a ledger entry now decided by a person ---------------------------------

def test_d205_ledger_entry_decided_by_a_person_is_reported_not_confirmed(tmp_path):
    root = project(tmp_path, compass_yml=HUMAN_DESIGN)
    _ledger(root, ("Q1", "First?", "Do the first.", "spec-author"),
            ("Q2", "Second?", "Do the second.", "spec-author"))
    assert _from_ledger(root)[0] == 0
    before = manifest_file(root).read_bytes()
    _ledger(root, ("Q1", "First?", "Do the first.",
                   'jed72, 2026-10-10 (in the session: "As recommended")'),
            ("Q2", "Second?", "Do the second.", "alex, 2026-10-10"))
    code, out, err = _from_ledger(root)
    assert code == 0, out + err
    flat = " ".join(out.split())
    lines = {"Q1": flat.split("Q1:")[1].split("Q2:")[0], "Q2": flat.split("Q2:")[1]}
    assert "compass evidence approve --decisions" in lines["Q1"] and "jed72" in lines["Q1"]
    assert "alex" in lines["Q2"] and "not an approver" in lines["Q2"]
    # A ledger line is a file an agent can write, so it confirms nothing.
    assert manifest_file(root).read_bytes() == before
    assert {d["status"] for d in _decisions(root).values()} == {"open"}
