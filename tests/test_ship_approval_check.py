"""The check `ship-approval-present`: every delivery issue owes a person's
approval at ship.

Step 2 of #355 [Read the ship approval from the merged PR review]. Every
delivery row of `evidence_required` owes the token `ship-approval`; a spike
owes nothing. `compass check` runs the check outside every gate, adds no row
for an issue that does not owe the token, and no waiver excuses it.

The check passes on a `pr-approval` record for the linked pull request, or on
a typed `human-approval` record with `ship:` for this issue and generation that
no withdrawal names. A sign-off of guardrail `G5` does not count (VD-029). It
fails only when the manifest records the pull request as merged and no
approval is on record; otherwise it has nothing to check and names the next
command. The commands that write the two records come in later steps, so the
records here are written by hand.
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from approval_support import SLUG, manifest_of, project, run, save_manifest  # noqa: E402

from compass_pkg import evidence_required, outside_gate, ship_approval  # noqa: E402
from compass_pkg.check_results import NOTHING_TO_CHECK  # noqa: E402

CHECK = ship_approval.CHECK
TOKEN = ship_approval.TOKEN
PR = {"repo": "acme/widgets", "number": 42}
MERGED = dict(PR, merged_at="2026-11-07T01:48:47Z", merge_commit="c" * 40, author="BagToad")
READINGS = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small",
            "goal": "delivery"}


# --- the token -------------------------------------------------------------------------------

@pytest.mark.parametrize("changes", [
    {},                                                    # RP-EVID-LIGHT
    {"urgency": "live-defect"},                            # RP-EVID-DEFECT
    {"size": "large", "risk": "critical"},                 # RP-EVID-STANDARD
    {"labels": ["payments"]},                              # a `G5` label
])
def test_every_delivery_row_owes_the_ship_approval(changes):
    owed = evidence_required.evaluate(dict(READINGS, **changes), {})["evidence_required"]
    assert TOKEN in owed, owed
    assert owed == sorted(owed, key=evidence_required.TOKENS.index), owed


def test_a_spike_owes_no_ship_approval():
    owed = evidence_required.evaluate(dict(READINGS, goal="exploration"), {})
    assert owed["evidence_required"] == [], owed


def test_the_token_meets_no_gate():
    assert TOKEN not in evidence_required.GATE_OF_TOKEN
    owed = evidence_required.evaluate(READINGS, {})
    assert "ship-approval-present" not in owed["gates"], owed["gates"]


def test_the_check_sits_outside_every_gate_and_is_never_waived():
    from compass_pkg import check_set, waiver_records
    doc = check_set.load()
    assert CHECK in outside_gate.CHECKS and CHECK not in outside_gate.SPIKE_CHECKS
    assert not [g for g, body in doc["gates"].items() if CHECK in (body.get("checks") or [])]
    assert CHECK in waiver_records.never_waived(doc)
    assert doc["checks"][CHECK]["on_skipped"] == "not-applicable"
    assert doc["checks"][CHECK]["severity"] == "blocking"
    assert "pr-approval" in doc["evidence_types"]


# --- the verdict, record by record ---------------------------------------------------------

def _task(**changes):
    task = {"status": "active", "generation": 2, "evidence_required": ["scenarios", TOKEN],
            "evidence": []}
    task.update(changes)
    return task


def _pr_approval(**changes):
    record = {"id": "EV-PR-APPROVAL-1", "type": "pr-approval", "pull_request": dict(PR),
              "review_id": 5809189576, "approver": "tidy-dev", "pr_author": "BagToad",
              "decision": "approved", "timestamp": "2026-11-07T01:27:26Z",
              "reviewed_commit": "a" * 40, "head_commit": "a" * 40, "via": "github",
              "issue": "feature", "generation": 2}
    record.update(changes)
    return record


def _typed(**changes):
    record = {"id": "EV-7", "type": "human-approval", "ship": "feature", "approver": "jed72",
              "role": "owner", "scope": "the change at ship", "decision": "approved",
              "timestamp": "2026-11-07T10:00:00Z", "issue": "feature", "generation": 2,
              "via": "prompt"}
    record.update(changes)
    return record


def _g5_signoff():
    return {"id": "EV-3", "type": "human-approval", "approver": "jed72", "role": "owner",
            "scope": "the payments change", "decision": "approved",
            "timestamp": "2026-11-06T10:00:00Z", "issue": "feature", "generation": 2}


def _verdict(task, tmp_path):
    task_dir = tmp_path / ".compass" / "work" / "feature"
    task_dir.mkdir(parents=True, exist_ok=True)
    return ship_approval._check_ship_approval_present(task, str(task_dir))


def test_an_issue_that_does_not_owe_it_has_nothing_to_check(tmp_path):
    passed, detail = _verdict(_task(evidence_required=["scenarios"],
                                    pull_request=dict(MERGED)), tmp_path)
    assert passed is NOTHING_TO_CHECK, detail


def test_an_approving_review_of_the_linked_pull_request_passes(tmp_path):
    passed, detail = _verdict(_task(pull_request=dict(MERGED), evidence=[_pr_approval()]),
                              tmp_path)
    assert passed is True, detail
    for part in ("EV-PR-APPROVAL-1", "tidy-dev", "acme/widgets#42", "2026-11-07T01:27:26Z"):
        assert part in detail, (part, detail)
    assert "merged head" not in detail, detail


def test_the_pass_says_when_the_review_approved_an_earlier_commit(tmp_path):
    record = _pr_approval(reviewed_commit="86ef0593" + "0" * 32,
                          head_commit="6ceb78a5" + "0" * 32)
    passed, detail = _verdict(_task(pull_request=dict(MERGED), evidence=[record]), tmp_path)
    assert passed is True, detail
    assert "86ef0593" in detail and "6ceb78a5" in detail and "merged head" in detail, detail


@pytest.mark.parametrize("record", [
    _pr_approval(pull_request={"repo": "acme/widgets", "number": 41}),
    _pr_approval(pull_request={"repo": "acme/other", "number": 42}),
    _pr_approval(decision="rejected"),
    _pr_approval(approver=""),
], ids=["another-number", "another-repo", "not-approved", "no-approver"])
def test_a_review_record_that_does_not_count_fails_a_merged_pull_request(tmp_path, record):
    passed, detail = _verdict(_task(pull_request=dict(MERGED), evidence=[record]), tmp_path)
    assert passed is False, detail


def test_a_review_record_counts_only_for_a_linked_pull_request(tmp_path):
    passed, detail = _verdict(_task(evidence=[_pr_approval()]), tmp_path)
    assert passed is NOTHING_TO_CHECK, detail


def test_a_typed_ship_approval_passes(tmp_path):
    passed, detail = _verdict(_task(pull_request=dict(MERGED), evidence=[_typed()]), tmp_path)
    assert passed is True, detail
    for part in ("EV-7", "jed72", "via a typed prompt", "2026-11-07T10:00:00Z"):
        assert part in detail, (part, detail)


def test_a_typed_ship_approval_passes_before_any_pull_request(tmp_path):
    passed, detail = _verdict(_task(evidence=[_typed()]), tmp_path)
    assert passed is True, detail


@pytest.mark.parametrize("record", [
    _typed(generation=1),
    _typed(issue="other"),
    _typed(ship="other"),
    _typed(decision="rejected"),
    _typed(timestamp=None),
], ids=["another-generation", "another-issue", "another-ship-subject", "rejected",
        "no-time"])
def test_a_typed_record_that_does_not_count_fails_a_merged_pull_request(tmp_path, record):
    passed, detail = _verdict(_task(pull_request=dict(MERGED), evidence=[record]), tmp_path)
    assert passed is False, detail


def test_a_withdrawn_typed_approval_does_not_count(tmp_path):
    withdrawal = {"id": "EV-8", "type": "approval-withdrawal", "withdraws": "EV-7"}
    passed, detail = _verdict(_task(pull_request=dict(MERGED),
                                    evidence=[_typed(), withdrawal]), tmp_path)
    assert passed is False, detail
    assert "withdrawn" in detail and "EV-7" in detail, detail


def test_a_g5_signoff_does_not_count_as_the_ship_approval(tmp_path):
    """VD-029: a `G5` sign-off is given at specify, before code exists."""
    passed, detail = _verdict(_task(pull_request=dict(MERGED), evidence=[_g5_signoff()]),
                              tmp_path)
    assert passed is False, detail
    assert "`G5` sign-off does not count" in detail, detail


def test_a_merged_pull_request_with_no_approval_fails_and_names_the_typed_approval(tmp_path):
    passed, detail = _verdict(_task(pull_request=dict(MERGED), land_commit="c" * 40,
                                    status="done", close_reason="completed"), tmp_path)
    assert passed is False, detail
    assert detail.startswith("pull request acme/widgets#42 merged with no approving review "
                             "by a person other than its author"), detail
    assert "`/compass:approve` after `compass evidence request --ship`" in detail, detail


def test_an_issue_in_flight_has_nothing_to_check(tmp_path):
    passed, detail = _verdict(_task(pull_request=dict(PR)), tmp_path)
    assert passed is NOTHING_TO_CHECK, detail
    assert detail.startswith("due at ship; read from the merged pull request"), detail
    assert "compass issue link set --pr 42 --issue feature" in detail, detail


def test_a_landed_issue_with_no_merge_recorded_has_nothing_to_check(tmp_path):
    passed, detail = _verdict(_task(land_commit="b" * 40, status="done",
                                    close_reason="completed"), tmp_path)
    assert passed is NOTHING_TO_CHECK, detail
    assert "no merge is recorded" in detail, detail
    assert "compass issue link set --pr <n> --issue feature" in detail, detail
    assert "compass evidence request --ship" in detail, detail


# --- compass check ---------------------------------------------------------------------------

def _statuses(root, slug=SLUG):
    code, out, err = run(root, "check", "--json", "--issue", slug)
    body = json.loads(out)
    return code, {c["name"]: (c["status"], c["detail"]) for c in body["checks"]}


def test_compass_check_reports_the_row_on_a_path_issue(tmp_path):
    root = project(tmp_path)
    body = manifest_of(root)
    assert TOKEN in body["evidence_required"], body["evidence_required"]
    code, rows = _statuses(root)
    assert rows[CHECK][0] == "nothing-to-check", rows[CHECK]

    body["pull_request"] = dict(MERGED)
    save_manifest(root, body)
    code, rows = _statuses(root)
    assert rows[CHECK][0] == "fail", rows[CHECK]
    assert code != 0

    body["evidence"].append(_pr_approval(issue=SLUG, generation=body["generation"]))
    save_manifest(root, body)
    code, rows = _statuses(root)
    assert rows[CHECK][0] == "pass", rows[CHECK]


def test_compass_check_adds_no_row_when_the_token_is_not_owed(tmp_path):
    root = project(tmp_path)
    body = manifest_of(root)
    body["evidence_required"] = [t for t in body["evidence_required"] if t != TOKEN]
    body["pull_request"] = dict(MERGED)
    save_manifest(root, body)
    code, rows = _statuses(root)
    assert CHECK not in rows, rows[CHECK]


def test_a_waiver_of_the_check_is_refused(tmp_path):
    root = project(tmp_path)
    before = (root / ".compass" / "work" / SLUG / "manifest.yml").read_bytes()
    code, out, err = run(root, "waiver", "add", "--check", CHECK, "--reason",
                         "the pull request had no reviewer", "--issue", SLUG)
    assert code != 0 and "never waived" in err, out + err
    assert (root / ".compass" / "work" / SLUG / "manifest.yml").read_bytes() == before


# --- an issue assessed before the token ------------------------------------------------------

def _old_project(tmp_path):
    """A project with an issue assessed before the path: no `evidence_required`,
    no generation, so it is judged by the live check set."""
    root = tmp_path / "old"
    task_dir = root / ".compass" / "work" / "old-issue"
    task_dir.mkdir(parents=True)
    manifest = {"schema_version": "2.0", "issue": "old-issue", "created": "2026-09-01",
                "status": "done", "close_reason": "completed", "delivery_approach": "regular",
                "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                               "size": "medium", "goal": "delivery", "labels": []},
                "stages": {"assess": "full", "define": "full", "refine": "light",
                           "plan": "full", "breakdown": "skipped", "implement": "full",
                           "verify": "full", "ship": "full"},
                "land_commit": "d" * 40, "pull_request": dict(MERGED),
                "scenarios": [{"id": "TRC-001", "intent": "INT-1"}], "evidence": []}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
    return root


def _check_rows(root, monkeypatch):
    """`compass check --json` run in this process, as (exit code, rows)."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("compass_cli_ship", str(ROOT / "cli" / "compass"))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    cli = importlib.util.module_from_spec(spec)
    loader.exec_module(cli)
    monkeypatch.chdir(root)
    out = io.StringIO()
    with redirect_stdout(out):
        code = cli.main(["check", "--json", "--issue", "old-issue"])
    body = json.loads(out.getvalue())
    return code, [(c["guardrail"], c["name"], c["status"]) for c in body["checks"]]


def test_an_old_issue_gains_no_row_from_the_new_check_set_entry(tmp_path, monkeypatch):
    """Section 6.1 of the plan: an issue with no generation reads the live check
    set, which declares the check, so only the token test keeps its rows. The
    rows equal those of the same check set with the entry taken out."""
    from compass_pkg import check_set
    monkeypatch.setenv("COMPASS_OFFLINE", "1")
    root = _old_project(tmp_path)
    with_entry = _check_rows(root, monkeypatch)
    assert CHECK not in [name for _, name, _ in with_entry[1]], with_entry

    doc = check_set.load()
    del doc["checks"][CHECK]
    del doc["names"]["checks." + CHECK]
    del doc["evidence_types"]["pr-approval"]
    doc["never_waived"].remove("checks." + CHECK)
    without = tmp_path / "check-set.yml"
    without.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    real = check_set.path
    monkeypatch.setattr(check_set, "path",
                        lambda root=None: str(without) if root is None else real(root))
    assert check_set.load()["checks"].get(CHECK) is None
    assert _check_rows(root, monkeypatch) == with_entry
