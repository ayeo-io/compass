"""Judged checks pass on a review record, and the four ways they fail are told apart.

A check of kind `judged` declares `inputs`. It passes only when its newest
review record says `pass`, names a reviewer the check lists, and holds the
digests of the inputs as they are now and of the check's definition as it is
now. `compass evidence review` writes that record. A project with no judged
check is unchanged.

Scenario ids: `JC-1` to `JC-12` (issue `judged-checks`). Each test name starts
with its scenario id.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_entry_exit_evaluation import (CAPABILITY, _by_check, _config_project,  # noqa: E402
                                        _rows, _view, _write_review)
from test_generation_store import (SLUG, _evaluate_write, _manifest, _project,  # noqa: E402
                                   _run, _write_manifest)

CHECK = "design-review"
STATEMENT = "The design holds against every scenario."
INPUTS = ["technical-design", "acceptance-criteria"]
DESIGN = "# Design\n\nThe design.\n"
CRITERIA = "# Criteria\n\nGiven a, when b, then c.\n"
EXAMPLE = ROOT / "tests" / "fixtures" / "evidence-review-example.json"


# --- helpers ---------------------------------------------------------------------

def _sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _documents(task_dir):
    (task_dir / "technical-design.md").write_text(DESIGN, encoding="utf-8")
    (task_dir / "acceptance-criteria.md").write_text(CRITERIA, encoding="utf-8")


def _judged(inputs=None, reviewers=None, **more):
    body = {"statement": STATEMENT, "kind": "judged", "severity": "blocking",
            "on_skipped": "fail", "inputs": list(INPUTS if inputs is None else inputs)}
    if reviewers is not None:
        body["reviewers"] = list(reviewers)
    body.update(more)
    return body


def _scene(tmp_path, monkeypatch, check=None, **manifest_changes):
    """A project with the capability on, a judged check in the `plan` entry
    list, the two documents it reads and `plan` as the current stage. Returns
    `(root, task_dir, view)`; a test changes the check by passing a view."""
    root, task_dir = _config_project(tmp_path, **manifest_changes)
    _documents(task_dir)
    body = _judged() if check is None else check

    def mutate(resolved):
        resolved["checks"][CHECK] = copy.deepcopy(body)
        resolved["stages"]["plan"]["entry"] = [CHECK]

    return root, task_dir, _view(root, monkeypatch, mutate)


def _check_body(view):
    return view.config["checks"][CHECK]


def _current(task_dir, ids):
    found = {}
    for one in ids:
        path = task_dir / f"{one}.md"
        found[one] = _sha(path.read_bytes()) if path.is_file() else None
    return found


def _stamp(payload):
    from compass_pkg.red_first import content_digest
    return content_digest(payload)


def _record(task_dir, view, *, verdict="pass", reviewer=("person", "jed72"), inputs=None,
            definition=None, reason="Read in full; it holds.", check=CHECK,
            registered=True, stamped=True):
    """Write a review record and register it, as `compass evidence review`
    does, but without calling it, so the reading side is tested alone."""
    from compass_pkg.atomic_io import digest
    body = _manifest(task_dir)
    registry = body.setdefault("evidence", [])
    number = 1 + len([e for e in registry if e.get("check") == check])
    name = f"evidence/review-{check}-{number}.yml"
    payload = {"schema": 1, "check": check, "verdict": verdict, "reason": reason,
               "reviewer": {"kind": reviewer[0], "id": reviewer[1]},
               "inputs": _current(task_dir, INPUTS) if inputs is None else inputs,
               "generation": 1,
               "definition_digest": (digest(_check_body(view)) if definition is None
                                     else definition),
               "at": "2026-10-08T10:00:00Z"}
    if stamped:
        payload["content_digest"] = _stamp(payload)
    (task_dir / "evidence").mkdir(exist_ok=True)
    (task_dir / name).write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    if registered:
        registry.append({"id": f"EV-REVIEW-{check}-{number}", "type": "manual-review",
                         "path": name, "check": check})
        (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                               encoding="utf-8")
    return task_dir / name


def _row(view, task_dir):
    return _by_check(_rows(view, task_dir))[CHECK]


def _cause(row):
    return row.detail.split(":")[0]


# --- JC-1: a judged check passes on a record whose inputs still match ---------------

def test_jc_1_a_matching_pass_record_passes(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, reviewer=("agent", "agent"))
    row = _row(view, task_dir)
    assert row.status == "pass", row.detail
    assert (row.stage, row.side, row.due) == ("plan", "entry", True)
    assert "EV-REVIEW-design-review-1" in row.detail


def test_jc_1_an_evidence_id_is_an_input(tmp_path, monkeypatch):
    root, task_dir, view = _scene(
        tmp_path, monkeypatch, check=_judged(inputs=["technical-design", "EV-NOTE"]))
    (task_dir / "evidence").mkdir()
    note = task_dir / "evidence" / "note.md"
    note.write_text("A note.\n", encoding="utf-8")
    body = _manifest(task_dir)
    body.setdefault("evidence", []).append({"id": "EV-NOTE", "type": "artifact",
                                            "path": "evidence/note.md"})
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    inputs = {"technical-design": _sha(DESIGN.encode()), "EV-NOTE": _sha(note.read_bytes())}
    _record(task_dir, view, inputs=inputs, reviewer=("agent", "a"))
    assert _row(view, task_dir).status == "pass"
    note.write_text("A note, edited.\n", encoding="utf-8")
    assert _row(view, task_dir).status == "fail"


# --- JC-2 to JC-5: the four causes, each on its own ---------------------------------

def test_jc_2_no_record_fails_closed_and_names_the_verb(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    row = _row(view, task_dir)
    assert row.status == "fail" and row.severity == "blocking"
    assert _cause(row) == "no review record"
    assert f"compass evidence review {CHECK}" in row.detail


def test_jc_2_a_record_for_another_check_is_not_this_checks_record(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, check="other-review")
    row = _row(view, task_dir)
    assert _cause(row) == "no review record" and "unusable" not in row.detail


def test_jc_2_a_record_that_is_not_registered_is_not_a_record(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, registered=False)
    assert _cause(_row(view, task_dir)) == "no review record"


def test_jc_2_an_entry_of_another_evidence_type_is_not_a_review(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, reviewer=("agent", "a"))
    body = _manifest(task_dir)
    body["evidence"][0]["type"] = "artifact"
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    assert _cause(_row(view, task_dir)) == "no review record"


def test_jc_2_a_check_that_declares_no_inputs_cannot_pass(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch, check=_judged(inputs=[]))
    _record(task_dir, view, inputs={})
    row = _row(view, task_dir)
    assert row.status == "fail" and "declares no inputs" in row.detail


def test_jc_3_a_fail_verdict_fails_and_shows_the_reason(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, verdict="fail", reason="Section 4 contradicts scenario 2.")
    row = _row(view, task_dir)
    assert row.status == "fail" and _cause(row) == "verdict is fail"
    assert "Section 4 contradicts scenario 2." in row.detail and "jed72" in row.detail


def test_jc_4_a_reviewer_the_check_does_not_list_fails(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)       # reviewers default: [agent]
    _record(task_dir, view, reviewer=("person", "jed72"))
    row = _row(view, task_dir)
    assert row.status == "fail" and _cause(row) == "reviewer not listed"
    assert "jed72" in row.detail and "agent" in row.detail


@pytest.mark.parametrize("listed, reviewer, passes", [
    (None, ("agent", "agent"), True),
    (None, ("agent", "abc123"), True),
    (None, ("person", "jed72"), False),
    (["jed72"], ("person", "jed72"), True),
    (["jed72"], ("person", "someone-else"), False),
    (["jed72"], ("agent", "abc123"), False),
    (["agent", "jed72"], ("person", "jed72"), True),
    (["agent", "jed72"], ("agent", "abc123"), True),
    (["a-role"], ("person", "a-role"), True),
    (["a-role"], ("agent", "a-role"), False),
])
def test_jc_4_the_reviewers_list_decides_who_may_review(tmp_path, monkeypatch, listed,
                                                         reviewer, passes):
    root, task_dir, view = _scene(tmp_path, monkeypatch, check=_judged(reviewers=listed))
    _record(task_dir, view, reviewer=reviewer)
    row = _row(view, task_dir)
    assert (row.status == "pass") is passes, row.detail
    if not passes:
        assert _cause(row) == "reviewer not listed"


@pytest.mark.parametrize("changed", INPUTS)
def test_jc_5_a_changed_input_re_owes_the_review(tmp_path, monkeypatch, changed):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, reviewer=("agent", "agent"))
    assert _row(view, task_dir).status == "pass"
    path = task_dir / f"{changed}.md"
    path.write_text(path.read_text(encoding="utf-8") + "One more line.\n", encoding="utf-8")
    row = _row(view, task_dir)
    assert row.status == "fail" and _cause(row) == "input changed since review"
    assert changed in row.detail
    other = [name for name in INPUTS if name != changed][0]
    assert other not in row.detail
    # A review of the new content clears it; the old record does not.
    _record(task_dir, view, reviewer=("agent", "agent"))
    assert _row(view, task_dir).status == "pass"


def test_jc_5_a_changed_evidence_input_names_the_evidence_id(tmp_path, monkeypatch):
    root, task_dir, view = _scene(
        tmp_path, monkeypatch, check=_judged(inputs=["technical-design", "EV-NOTE"]))
    (task_dir / "evidence").mkdir()
    note = task_dir / "evidence" / "note.md"
    note.write_text("A note.\n", encoding="utf-8")
    body = _manifest(task_dir)
    body.setdefault("evidence", []).append({"id": "EV-NOTE", "type": "artifact",
                                            "path": "evidence/note.md"})
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    _record(task_dir, view, inputs={"technical-design": _sha(DESIGN.encode()),
                                    "EV-NOTE": _sha(note.read_bytes())},
            reviewer=("agent", "a"))
    assert _row(view, task_dir).status == "pass"
    note.write_text("A note, edited.\n", encoding="utf-8")
    row = _row(view, task_dir)
    assert row.status == "fail" and _cause(row) == "input changed since review"
    assert "EV-NOTE" in row.detail and "technical-design" not in row.detail


def test_jc_5_an_input_that_is_gone_reads_as_changed(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, reviewer=("agent", "agent"))
    (task_dir / "technical-design.md").unlink()
    row = _row(view, task_dir)
    assert row.status == "fail" and _cause(row) == "input changed since review"
    assert "technical-design" in row.detail and "missing" in row.detail


def _view_with(root, monkeypatch, body):
    def mutate(resolved):
        resolved["checks"][CHECK] = copy.deepcopy(body)
        resolved["stages"]["plan"]["entry"] = [CHECK]

    return _view(root, monkeypatch, mutate)


def test_jc_5_a_changed_definition_re_owes_the_review(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, reviewer=("agent", "agent"))
    assert _row(view, task_dir).status == "pass"
    changed = _view_with(root, monkeypatch, _judged(
        statement="The design holds, and the rollback is stated."))
    row = _row(changed, task_dir)
    assert row.status == "fail" and _cause(row) == "input changed since review"
    assert "definition" in row.detail


def test_jc_5_the_four_causes_are_reported_apart(tmp_path, monkeypatch):
    seen = {}
    for label, build in {
        "no review record": lambda t, v: None,
        "verdict is fail": lambda t, v: _record(t, v, verdict="fail", reviewer=("agent", "a")),
        "reviewer not listed": lambda t, v: _record(t, v, reviewer=("person", "jed72")),
        "input changed since review": lambda t, v: _record(
            t, v, reviewer=("agent", "a"), inputs={"technical-design": "sha256:0",
                                                   "acceptance-criteria": "sha256:0"}),
    }.items():
        scene = tmp_path / label.replace(" ", "-")
        scene.mkdir()
        root, task_dir, view = _scene(scene, monkeypatch)
        build(task_dir, view)
        row = _row(view, task_dir)
        assert row.status == "fail"
        seen[label] = _cause(row)
    assert seen == {label: label for label in seen}
    assert len(set(seen.values())) == 4


# --- JC-6: the newest record decides; a record changed after writing is not a record --------------

def test_jc_6_a_later_fail_overrides_an_earlier_pass_and_the_reverse(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, reviewer=("agent", "a"))
    assert _row(view, task_dir).status == "pass"
    _record(task_dir, view, verdict="fail", reviewer=("agent", "a"), reason="On reflection, no.")
    row = _row(view, task_dir)
    assert _cause(row) == "verdict is fail" and "EV-REVIEW-design-review-2" in row.detail
    _record(task_dir, view, reviewer=("agent", "a"))
    assert _row(view, task_dir).status == "pass"


def test_jc_6_a_record_edited_after_it_was_written_is_not_a_record(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    path = _record(task_dir, view, verdict="fail", reviewer=("agent", "a"))
    path.write_text(path.read_text(encoding="utf-8").replace("verdict: fail", "verdict: pass"),
                    encoding="utf-8")
    row = _row(view, task_dir)
    assert row.status == "fail" and _cause(row) == "no review record"
    assert "changed after it was written" in row.detail


def test_jc_6_a_record_without_a_stamp_or_file_is_not_a_record(tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    _record(task_dir, view, reviewer=("agent", "a"), stamped=False)
    row = _row(view, task_dir)
    assert _cause(row) == "no review record" and "not stamped" in row.detail
    path = _record(task_dir, view, reviewer=("agent", "a"))
    path.unlink()
    row = _row(view, task_dir)
    assert _cause(row) == "no review record" and "no file" in row.detail


def test_jc_6_a_registered_entry_that_points_at_another_checks_record_is_not_a_record(
        tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch)
    other = _record(task_dir, view, check="other-review")
    body = _manifest(task_dir)
    body["evidence"].append({"id": "EV-MISPLACED", "type": "manual-review",
                             "path": other.relative_to(task_dir).as_posix(), "check": CHECK})
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False),
                                           encoding="utf-8")
    row = _row(view, task_dir)
    assert _cause(row) == "no review record" and "not a review record of" in row.detail


# --- JC-7: the verb writes the record and registers it ------------------------------

def _cli_config(reviewers=None, extra_check=None):
    check = _judged(reviewers=reviewers)
    return {"schema": 1, "capabilities": {CAPABILITY: True},
            "checks": {CHECK: check, **(extra_check or {})},
            "stages": {"plan": {"set": {"entry": {"add": [CHECK]}}}}}


def _cli_project(tmp_path, reviewers=None, documents=True):
    root, task_dir = _project(tmp_path, compass_yml=_cli_config(reviewers))
    assert _evaluate_write(root)[0] == 0
    _write_manifest(task_dir, current_phase="plan")
    if documents:
        _documents(task_dir)
    return root, task_dir


def _review(root, *extra, check=CHECK, verdict="pass", reason="Sections 2 to 6 read; it holds.",
            reviewer="jed72"):
    return _run(root, "evidence", "review", check, "--issue", SLUG, "--verdict", verdict,
                "--reason", reason, "--reviewer", reviewer, *extra)


def _plan_row(root):
    out = _run(root, "check", "--issue", SLUG, "--json")[1]
    rows = [r for r in json.loads(out)["checks"] if r["name"] == CHECK]
    assert len(rows) == 1, out
    return rows[0]


def test_jc_7_the_verb_writes_a_record_that_makes_the_check_pass(tmp_path):
    root, task_dir = _cli_project(tmp_path, reviewers=["jed72"])
    assert _plan_row(root)["status"] == "fail"
    code, out, err = _review(root, "--scope", "technical-design.md")
    assert code == 0, out + err
    path = task_dir / "evidence" / "review-design-review-1.yml"
    record = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert record["schema"] == 1 and record["check"] == CHECK and record["verdict"] == "pass"
    assert record["reason"] == "Sections 2 to 6 read; it holds."
    assert record["reviewer"] == {"kind": "person", "id": "jed72"}
    assert record["scope"] == "technical-design.md" and record["generation"] == 1
    assert record["inputs"] == {"technical-design": _sha(DESIGN.encode()),
                                "acceptance-criteria": _sha(CRITERIA.encode())}
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", record["definition_digest"])
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", record["at"])
    assert record["content_digest"] == _stamp(record)
    entry = [e for e in _manifest(task_dir)["evidence"] if e.get("check") == CHECK]
    assert entry == [{"id": "EV-REVIEW-design-review-1", "type": "manual-review",
                      "path": "evidence/review-design-review-1.yml", "check": CHECK}]
    row = _plan_row(root)
    assert row["status"] == "pass" and row["guardrail"] == "stage:plan:entry"


def test_jc_7_a_second_review_is_numbered_and_the_newest_decides(tmp_path):
    root, task_dir = _cli_project(tmp_path, reviewers=["jed72"])
    assert _review(root)[0] == 0
    assert _review(root, verdict="fail", reason="Found a gap.")[0] == 0
    assert (task_dir / "evidence" / "review-design-review-2.yml").is_file()
    ids = [e["id"] for e in _manifest(task_dir)["evidence"]]
    assert ids == ["EV-REVIEW-design-review-1", "EV-REVIEW-design-review-2"]
    row = _plan_row(root)
    assert row["status"] == "fail" and row["detail"].startswith("verdict is fail")


def test_jc_7_an_agent_reviewer_is_recorded_as_an_agent(tmp_path):
    root, task_dir = _cli_project(tmp_path)                 # default reviewers: [agent]
    assert _review(root, reviewer="agent:session-9")[0] == 0
    record = yaml.safe_load((task_dir / "evidence" / "review-design-review-1.yml")
                            .read_text(encoding="utf-8"))
    assert record["reviewer"] == {"kind": "agent", "id": "session-9"}
    assert _plan_row(root)["status"] == "pass"
    assert _review(root, reviewer="agent")[0] == 0
    record = yaml.safe_load((task_dir / "evidence" / "review-design-review-2.yml")
                            .read_text(encoding="utf-8"))
    assert record["reviewer"] == {"kind": "agent", "id": "agent"}
    assert "scope" not in record


def test_jc_7_a_changed_input_after_the_verb_re_owes_it_end_to_end(tmp_path):
    root, task_dir = _cli_project(tmp_path, reviewers=["jed72"])
    assert _review(root)[0] == 0
    assert _plan_row(root)["status"] == "pass"
    (task_dir / "technical-design.md").write_text(DESIGN + "Changed.\n", encoding="utf-8")
    row = _plan_row(root)
    assert row["status"] == "fail" and row["detail"].startswith("input changed since review")
    assert _review(root)[0] == 0
    assert _plan_row(root)["status"] == "pass"


def test_jc_7_the_verb_leaves_the_other_checks_as_they_were(tmp_path):
    root, task_dir = _cli_project(tmp_path, reviewers=["jed72"])
    before = json.loads(_run(root, "check", "--issue", SLUG, "--json")[1])["checks"]
    assert _review(root)[0] == 0
    after = json.loads(_run(root, "check", "--issue", SLUG, "--json")[1])["checks"]
    keep = lambda rows: [(r["guardrail"], r["name"], r["status"]) for r in rows  # noqa: E731
                         if r["name"] != CHECK]
    assert keep(before) == keep(after)


# --- JC-8: what the verb refuses ------------------------------------------------------

def _tree(task_dir):
    return sorted(p.relative_to(task_dir).as_posix() for p in task_dir.rglob("*")
                  if "generations" not in p.parts), (task_dir / "manifest.yml").read_bytes()


@pytest.mark.parametrize("name, args, needle", [
    ("unknown check", dict(check="no-such-check"), "no such check"),
    ("not judged", dict(check="dor-summary-filled"), "not a judged check"),
    ("empty reason", dict(reason="  "), "reason"),
    ("empty reviewer", dict(reviewer=" "), "reviewer"),
])
def test_jc_8_a_review_that_cannot_be_recorded_exits_2_and_writes_nothing(
        tmp_path, name, args, needle):
    root, task_dir = _cli_project(tmp_path)
    before = _tree(task_dir)
    code, out, err = _review(root, **args)
    assert code == 2 and needle in err, (code, out, err)
    assert out == "" and _tree(task_dir) == before


def test_jc_8_an_input_that_cannot_be_found_is_named(tmp_path):
    root, task_dir = _cli_project(tmp_path)
    (task_dir / "acceptance-criteria.md").unlink()
    before = _tree(task_dir)
    code, out, err = _review(root, reviewer="agent")
    assert code == 2 and "acceptance-criteria" in err and "cannot be found" in err
    assert _tree(task_dir) == before


def test_jc_8_a_check_with_no_inputs_cannot_be_reviewed(tmp_path):
    config = _cli_config()
    config["checks"][CHECK]["inputs"] = []
    root, task_dir = _project(tmp_path, compass_yml=config)
    assert _evaluate_write(root)[0] == 0
    code, out, err = _review(root, reviewer="agent")
    assert code == 2 and "declares no inputs" in err


def test_jc_8_a_verdict_other_than_pass_or_fail_is_refused(tmp_path):
    root, task_dir = _cli_project(tmp_path)
    code, out, err = _review(root, verdict="maybe")
    assert code == 2 and "pass" in err and "fail" in err
    assert not (task_dir / "evidence").exists() or not list((task_dir / "evidence").glob("review-*"))


def test_jc_8_an_issue_with_no_stored_configuration_is_refused_with_the_fix(tmp_path):
    root, task_dir = _project(tmp_path)
    _write_manifest(task_dir, generation=0)
    code, out, err = _review(root)
    assert code == 2 and "approach evaluate --write" in err


# --- JC-9: the --json output is documented and pinned --------------------------------

def _masked(text):
    document = json.loads(text)
    document["at"] = "..."
    document["definition_digest"] = "sha256:..."
    return json.dumps(document, indent=2)


def _example_output(tmp_path):
    root, task_dir = _cli_project(tmp_path, reviewers=["jed72"])
    return _review(root, "--scope", "technical-design.md", "--json")


def test_jc_9_the_json_document_has_these_keys(tmp_path):
    code, out, err = _example_output(tmp_path)
    assert code == 0, err
    document = json.loads(out)
    assert set(document) == {"outcome", "check", "verdict", "evidence_id", "path", "reviewer",
                             "scope", "inputs", "generation", "definition_digest", "at",
                             "detail"}
    assert document["evidence_id"] == "EV-REVIEW-design-review-1"
    assert document["reviewer"] == {"kind": "person", "id": "jed72"}
    assert document["path"] == "evidence/review-design-review-1.yml"


def test_jc_9_the_pinned_example_is_the_real_output_and_the_doc_shows_it(tmp_path):
    code, out, err = _example_output(tmp_path)
    pinned = EXAMPLE.read_text(encoding="utf-8") if EXAMPLE.is_file() else ""
    assert code == 0 and pinned == _masked(out) + "\n"
    page = ROOT / "docs" / "judged-checks.md"
    text = page.read_text(encoding="utf-8") if page.is_file() else ""
    shown = [block for block in re.findall(r"```json\n(.*?)```", text, re.S)
             if '"evidence_id"' in block]
    assert len(shown) == 1 and shown[0].strip() == pinned.strip()


# --- JC-10: help, owning doc, schema and corpus --------------------------------------

def test_jc_10_the_help_text_the_owning_doc_and_the_router_describe_the_verb():
    from compass_pkg import verb_help
    text = verb_help.VERB_DESCRIPTIONS.get("evidence review", "")
    for needle in ("--verdict", "--reviewer", "judged", "exit 2", "re-owed"):
        assert needle in text, needle
    doc = (ROOT / "docs" / "judged-checks.md").read_text(encoding="utf-8") \
        if (ROOT / "docs" / "judged-checks.md").is_file() else ""
    for needle in ("no review record", "verdict is fail", "reviewer not listed",
                   "input changed since review", "evidence review", "--json",
                   "review_records.py", "inputs"):
        assert needle in doc, needle
    router = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    assert any("cli/compass_pkg/review_records.py" in line and "docs/judged-checks.md" in line
               for line in router.splitlines())
    assert "(judged-checks.md)" in router


def test_jc_10_the_stage_list_docs_say_a_judged_check_is_evaluated():
    doc = (ROOT / "docs" / "entry-exit-evaluation.md").read_text(encoding="utf-8")
    assert "(judged-checks.md)" in doc
    assert "`judged`, `evidence` | Not evaluated" not in doc
    assert "`judged` and `evidence` checks are not evaluated" not in doc
    from compass_pkg import stage_lists
    assert "`judged` and `evidence`: not evaluated" not in stage_lists.__doc__
    assert "review_records" in stage_lists.__doc__


def test_jc_10_the_verb_is_listed_in_its_group_help():
    import subprocess
    out = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "evidence", "--help"],
                         capture_output=True, text=True).stdout
    assert "review" in out
    out = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "evidence", "review",
                          "--help"], capture_output=True, text=True).stdout
    for flag in ("--verdict", "--reason", "--reviewer", "--scope", "--issue"):
        assert flag in out, flag


def test_jc_10_the_manifest_schema_declares_the_check_key_of_an_evidence_entry():
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    properties = schema["properties"]["evidence"]["items"]["properties"]
    assert "check" in properties
    reference = (ROOT / "schemas" / "manifest.reference.yml").read_text(encoding="utf-8")
    assert "check:" in reference


def test_jc_10_the_corpus_has_the_verb_with_its_exit_codes():
    import compat_commands as cc
    entries = {e["id"]: e for e in cc.load()}
    expected = {"evidence-review-recorded": 0, "evidence-review-unknown-check": 2,
                "evidence-review-not-judged": 2, "evidence-review-input-missing": 2}
    assert set(expected) <= set(entries)
    assert {i: entries[i]["exit"] for i in expected} == expected
    assert cc.STATES.get("with-judged-check") and cc.STATES.get("with-judged-check-document")


# --- JC-11: a project with no judged check is unchanged --------------------------------

def test_jc_11_the_shipped_default_names_no_judged_or_evidence_check_in_any_list():
    preset = ROOT / "governance" / "presets" / "default"
    checks = yaml.safe_load((preset / "checks.yml").read_text(encoding="utf-8"))["checks"]
    stages = yaml.safe_load((preset / "stages.yml").read_text(encoding="utf-8"))["stages"]
    listed = {c for body in stages.values() for side in ("entry", "exit")
              for c in (body.get(side) or [])}
    assert listed
    assert {checks[c]["kind"] for c in listed} <= {"human", "deterministic"}
    assert not [c for c, body in checks.items() if body.get("kind") == "judged"]


def test_jc_11_no_review_record_is_read_when_no_list_names_a_judged_check(tmp_path, monkeypatch):
    from compass_pkg import review_records
    root, task_dir = _config_project(tmp_path)
    _write_review(task_dir)

    def explode(*args, **kwargs):
        raise AssertionError("a review record was read for a list with no judged check")

    monkeypatch.setattr(review_records, "judge", explode)
    rows = _rows(_view(root, monkeypatch), task_dir)
    assert rows and {r.status for r in rows if r.due} == {"pass"}


def test_jc_11_check_output_and_the_manifest_are_unchanged_without_a_judged_check(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml={"schema": 1, "capabilities": {CAPABILITY: True}})
    assert _evaluate_write(root)[0] == 0
    _write_manifest(task_dir, current_phase="plan")
    _write_review(task_dir)
    before = (task_dir / "manifest.yml").read_bytes()
    data = json.loads(_run(root, "check", "--issue", SLUG, "--json")[1])
    rows = [r for r in data["checks"] if r["guardrail"].startswith("stage:")]
    assert len(rows) == 7 and {r["status"] for r in rows} == {"pass"}
    assert not [r for r in data["checks"] if "review record" in r["detail"]]
    assert (task_dir / "manifest.yml").read_bytes() == before
    assert not list((task_dir / "evidence").glob("review-*")) if (task_dir / "evidence").exists() else True


def test_jc_11_an_evidence_check_still_fails_closed(tmp_path, monkeypatch):
    root, task_dir = _config_project(tmp_path)

    def mutate(resolved):
        resolved["checks"]["needs-evidence"] = {
            "statement": "x", "kind": "evidence", "accepts": ["test-run"],
            "severity": "blocking", "on_skipped": "fail"}
        resolved["stages"]["plan"]["entry"] = ["needs-evidence"]

    row = _by_check(_rows(_view(root, monkeypatch, mutate), task_dir))["needs-evidence"]
    assert row.status == "fail" and "not evaluated" in row.detail


# --- JC-12: due, skipped and advisory apply to a judged check as to any other ---------

def test_jc_12_a_judged_check_that_is_not_due_is_pending_and_reads_no_record(tmp_path, monkeypatch):
    from compass_pkg import review_records
    root, task_dir, view = _scene(tmp_path, monkeypatch, current_phase="define")

    def explode(*args, **kwargs):
        raise AssertionError("read a review record for a list that is not due")

    monkeypatch.setattr(review_records, "judge", explode)
    row = _row(view, task_dir)
    assert row.status == "pending" and row.due is False


@pytest.mark.parametrize("value, status", [("fail", "fail"), ("pass", "pass"),
                                           ("not-applicable", "nothing-to-check")])
def test_jc_12_a_skipped_stage_gives_the_on_skipped_verdict(tmp_path, monkeypatch, value, status):
    root, task_dir, view = _scene(tmp_path, monkeypatch,
                                  check=_judged(on_skipped=value),
                                  stages={"refine": "full", "plan": "skipped"})
    row = _row(view, task_dir)
    assert row.status == status and "plan is skipped" in row.detail


def test_jc_12_an_advisory_judged_check_with_no_record_reports_a_pass_that_says_so(
        tmp_path, monkeypatch):
    root, task_dir, view = _scene(tmp_path, monkeypatch, check=_judged(severity="advisory"))
    row = _row(view, task_dir)
    assert row.status == "pass" and row.detail.startswith("advisory - no review record")


def test_jc_12_the_receipt_shows_the_verdict_of_a_judged_check(tmp_path):
    root, task_dir = _cli_project(tmp_path, reviewers=["jed72"])
    code, out, err = _run(root, "issue", "receipt", "--issue", SLUG)
    assert code == 0, err
    assert re.search(r"design-review\s+fail", out), out
    assert _review(root)[0] == 0
    code, out, err = _run(root, "issue", "receipt", "--issue", SLUG)
    assert re.search(r"design-review\s+pass", out), out
