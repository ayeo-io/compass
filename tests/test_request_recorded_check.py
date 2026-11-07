"""The check `request-recorded`: every delivery issue names who asked for it
and links the request.

Step 2 of #356 [Commit the issue record with the code and add trail.md].
Every delivery row of `evidence_required` owes the token `request`; a spike
owes nothing. `compass check` runs the check outside every gate and adds no
row for an issue that does not owe the token. The check is not a stop: no
command refuses on it. Unlike `ship-approval-present`, a waiver a person
approves can excuse it (VD-031, plan question 4).
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

from approval_support import (OWNER, SLUG, manifest_of, project, run,  # noqa: E402
                              save_manifest)

from compass_pkg import evidence_required, next_step, outside_gate, request_link  # noqa: E402
from compass_pkg.check_results import NOTHING_TO_CHECK  # noqa: E402

CHECK = request_link.CHECK
TOKEN = request_link.TOKEN
LINK = "https://github.com/acme/widgets/issues/42"
READINGS = {"risk": "contained", "familiarity": "brownfield-mapped", "size": "small",
            "goal": "delivery"}


# --- the token -------------------------------------------------------------------------------

@pytest.mark.parametrize("changes", [
    {},                                                    # RP-EVID-LIGHT
    {"urgency": "live-defect"},                            # RP-EVID-DEFECT
    {"size": "large", "risk": "critical"},                 # RP-EVID-STANDARD
    {"labels": ["payments"]},                              # a `G5` label
])
def test_every_delivery_row_owes_the_request_first(changes):
    owed = evidence_required.evaluate(dict(READINGS, **changes), {})["evidence_required"]
    assert owed[0] == TOKEN, owed
    assert owed == sorted(owed, key=evidence_required.TOKENS.index), owed


def test_a_spike_owes_no_request():
    owed = evidence_required.evaluate(dict(READINGS, goal="exploration"), {})
    assert owed["evidence_required"] == [], owed


def test_the_token_meets_no_gate():
    assert TOKEN not in evidence_required.GATE_OF_TOKEN
    owed = evidence_required.evaluate(READINGS, {})
    assert CHECK not in owed["gates"], owed["gates"]


def test_the_check_sits_first_outside_every_gate_and_can_be_waived():
    from compass_pkg import check_set, waiver_records
    doc = check_set.load()
    assert outside_gate.CHECKS[0] == CHECK and CHECK not in outside_gate.SPIKE_CHECKS
    assert not [g for g, body in doc["gates"].items() if CHECK in (body.get("checks") or [])]
    assert CHECK not in waiver_records.never_waived(doc)
    assert doc["checks"][CHECK]["on_skipped"] == "not-applicable"
    assert doc["checks"][CHECK]["severity"] == "blocking"


# --- the verdict -----------------------------------------------------------------------------

def _verdict(task, tmp_path):
    task_dir = tmp_path / ".compass" / "work" / "feature"
    task_dir.mkdir(parents=True, exist_ok=True)
    return request_link._check_request_recorded(task, str(task_dir))


def _task(**changes):
    task = {"status": "active", "generation": 1, "evidence_required": [TOKEN, "scenarios"],
            "evidence": []}
    task.update(changes)
    return task


def test_an_issue_that_does_not_owe_it_has_nothing_to_check(tmp_path):
    passed, detail = _verdict(_task(evidence_required=["scenarios"]), tmp_path)
    assert passed is NOTHING_TO_CHECK, detail


def test_a_link_and_a_requester_pass_and_the_requester_is_named_as_a_claim(tmp_path):
    passed, detail = _verdict(_task(request={"link": LINK, "requester": "Dana Smith"}),
                              tmp_path)
    assert passed is True, detail
    assert "Dana Smith" in detail and LINK in detail and "claim" in detail, detail


def test_no_request_fails_and_names_both_parts_and_the_command(tmp_path):
    passed, detail = _verdict(_task(), tmp_path)
    assert passed is False, detail
    assert "missing the request link and the requester" in detail, detail
    assert ("compass issue link set --issue feature --request <url> --requester <name>"
            in detail), detail


@pytest.mark.parametrize("held, missing", [
    ({"link": LINK}, "missing the requester;"),
    ({"requester": "Dana Smith"}, "missing the request link;"),
    ({"link": "  ", "requester": "Dana Smith"}, "missing the request link;"),
])
def test_a_missing_part_fails_and_is_named(tmp_path, held, missing):
    passed, detail = _verdict(_task(request=held), tmp_path)
    assert passed is False and missing in detail, detail
    assert ("link and" not in detail) and ("and the requester" not in detail), detail


def test_a_linked_github_issue_gives_the_link(tmp_path):
    task = _task(github={"repo": "acme/widgets", "number": 42},
                 request={"requester": "Dana Smith"})
    passed, detail = _verdict(task, tmp_path)
    assert passed is True and LINK in detail, detail


# --- compass check ---------------------------------------------------------------------------

def _statuses(root, slug=SLUG):
    code, out, err = run(root, "check", "--json", "--issue", slug)
    body = json.loads(out)
    return code, {c["name"]: (c["status"], c["detail"]) for c in body["checks"]}


def test_compass_check_reports_the_row_on_a_path_issue(tmp_path):
    root = project(tmp_path)
    body = manifest_of(root)
    assert body["evidence_required"][0] == TOKEN, body["evidence_required"]
    code, rows = _statuses(root)
    assert rows[CHECK][0] == "fail", rows[CHECK]
    assert code != 0

    body["request"] = {"link": LINK, "requester": "Dana Smith"}
    save_manifest(root, body)
    code, rows = _statuses(root)
    assert rows[CHECK][0] == "pass", rows[CHECK]


def test_compass_check_adds_no_row_when_the_token_is_not_owed(tmp_path):
    root = project(tmp_path)
    body = manifest_of(root)
    body["evidence_required"] = [t for t in body["evidence_required"] if t != TOKEN]
    save_manifest(root, body)
    code, rows = _statuses(root)
    assert CHECK not in rows, rows[CHECK]


def test_a_waiver_a_person_approves_turns_the_row_to_waived(tmp_path):
    root = project(tmp_path)
    code, out, err = run(root, "waiver", "add", "--check", CHECK, "--reason",
                         "a typo fix the maintainer saw; no request to link", "--issue", SLUG)
    assert code == 0, out + err
    assert _statuses(root)[1][CHECK][0] == "fail"
    code, out, err = run(root, "evidence", "approve", "--waiver", "W-1", "--approver", OWNER,
                         "--role", "owner", terminal=True)
    assert code == 0, out + err
    assert _statuses(root)[1][CHECK][0] == "waived"
    # `compass next` stops asking for the request once a person excused it.
    task_dir = root / ".compass" / "work" / SLUG
    assert "--request" not in (next_step.next_command(manifest_of(root), str(task_dir)) or "")


def test_next_asks_for_the_request_first(tmp_path):
    root = project(tmp_path)
    task_dir = root / ".compass" / "work" / SLUG
    assert next_step.next_command(manifest_of(root), str(task_dir)) == (
        f"compass issue link set --issue {SLUG} --request <url> --requester <name>")
    body = manifest_of(root)
    body["request"] = {"link": LINK, "requester": "Dana Smith"}
    save_manifest(root, body)
    assert "--request" not in next_step.next_command(manifest_of(root), str(task_dir))


def test_the_request_is_not_a_step_quick_fix_finish_refuses_on(tmp_path):
    root = project(tmp_path)
    task_dir = root / ".compass" / "work" / SLUG
    owed = next_step.owed_commands(manifest_of(root), str(task_dir))
    assert not [c for c in owed if "--request" in c], owed


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
                "land_commit": "d" * 40,
                "scenarios": [{"id": "TRC-001", "intent": "INT-1"}], "evidence": []}
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False),
                                           encoding="utf-8")
    return root


def _check_rows(root, monkeypatch):
    """`compass check --json` run in this process, as (exit code, rows)."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("compass_cli_request",
                                                  str(ROOT / "cli" / "compass"))
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
    """Plan section 5.3: an issue with no generation reads the live check set,
    which declares the check, so only the token test keeps its rows. The rows
    equal those of the same check set with the entry taken out."""
    from compass_pkg import check_set
    monkeypatch.setenv("COMPASS_OFFLINE", "1")
    root = _old_project(tmp_path)
    with_entry = _check_rows(root, monkeypatch)
    assert CHECK not in [name for _, name, _ in with_entry[1]], with_entry

    doc = check_set.load()
    del doc["checks"][CHECK]
    del doc["names"]["checks." + CHECK]
    without = tmp_path / "check-set.yml"
    without.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    real = check_set.path
    monkeypatch.setattr(check_set, "path",
                        lambda root=None: str(without) if root is None else real(root))
    assert check_set.load()["checks"].get(CHECK) is None
    assert _check_rows(root, monkeypatch) == with_entry
