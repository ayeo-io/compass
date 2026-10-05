"""`compass check` enforcing the default guardrails `G1`-`G5`: scenarios have
tests, suite is green, changed code traces to a scenario, gate evidence is
the right type, human approvals are present and structured, follow-ups are
paid.

Each test builds the smallest manifest.yml + evidence set that should pass or
fail a specific check, then asserts exit code and a (loose) message match.
"""

# These tests read the per-check detail, which the command prints only
# under --verbose.
from __future__ import annotations

import json


# --- a baseline-correct manifest.yml the tests mutate one field at a time ------


def _correct_body(write_test_run=True):
    body = {
        "task": "baseline",
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "delivery_approach": "express",
        "scenarios": [
            {"id": "SCN-001", "intent": "INT-1",
             "tests": ["tests/test_x.py::test_y"]},
        ],
        "changed_files": [
            {"path": "src/x.py", "scenarios": ["SCN-001"]},
        ],
        "evidence": [],
        "gates": [
            {"id": "verify.correctness", "status": "pending"},
            {"id": "verify.governance", "status": "pending"},
            {"id": "verify.traceability", "status": "pending"},
        ],
        "follow_ups": [],
    }
    if write_test_run:
        body["evidence"].append({
            "id": "EV-T-SCN-001",
            "type": "test-run",
            "path": "evidence/green.json",
            "scenario": "SCN-001",
        })
    return body


def _make_green(task_dir, scenario="SCN-001"):
    """Write a fake evidence/green.json that the suite-passed check reads."""
    ev = task_dir / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    with (ev / "green.json").open("w") as fh:
        json.dump({"exit_code": 0, "passed": True, "scenario": scenario,
                   "command": "pytest", "timestamp": "2026-05-15T00:00:00+00:00"},
                  fh)


# --- `G1` scenarios-have-tests + suite-passed --------------------------------


def test_check_fails_when_scenarios_have_no_tests(run_cli, make_task):
    body = _correct_body()
    body["scenarios"][0].pop("tests")
    task_dir = make_task("no-tests", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "no-tests")
    assert r.returncode != 0, r
    assert "scenarios-have-tests" in r.stdout, r


def test_check_fails_when_no_test_run_evidence(run_cli, make_task):
    body = _correct_body(write_test_run=False)
    make_task("no-green", body)
    r = run_cli("check", "--verbose", "--issue", "no-green")
    assert r.returncode != 0, r
    assert "suite-passed" in r.stdout, r


def test_check_fails_when_test_run_path_does_not_resolve(run_cli, make_task):
    """A test-run entry pointing at a path that does not exist must fail."""
    body = _correct_body()
    # don't write the green.json file
    task_dir = make_task("dangling-path", body)
    r = run_cli("check", "--verbose", "--issue", "dangling-path")
    assert r.returncode != 0, r
    assert "suite-passed" in r.stdout, r


def test_check_fails_when_test_run_records_failure(run_cli, make_task):
    body = _correct_body()
    task_dir = make_task("not-green", body)
    ev = task_dir / "evidence"
    ev.mkdir(parents=True, exist_ok=True)
    # exit_code != 0 means the recorded run was not green
    with (ev / "green.json").open("w") as fh:
        json.dump({"exit_code": 1, "passed": False}, fh)
    r = run_cli("check", "--verbose", "--issue", "not-green")
    assert r.returncode != 0, r


def test_check_fails_when_test_run_bound_to_unknown_scenario(run_cli, make_task):
    """A test-run entry with `scenario: SCN-999` (not in manifest.yml) must
    fail - the binding has to resolve."""
    body = _correct_body()
    body["evidence"][0]["scenario"] = "SCN-999"   # not in scenarios
    task_dir = make_task("bad-binding", body)
    _make_green(task_dir, scenario="SCN-001")
    r = run_cli("check", "--verbose", "--issue", "bad-binding")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "SCN-999" in combined, r


# --- `G3` traceability (changed_files -> scenario) ---------------------------


def test_check_fails_on_changed_file_without_scenario(run_cli, make_task):
    body = _correct_body()
    body["changed_files"] = [{"path": "src/x.py", "scenarios": []}]
    task_dir = make_task("untraced", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "untraced")
    assert r.returncode != 0, r
    assert "changed-code-traces" in r.stdout, r


def test_check_fails_on_changed_file_pointing_at_unknown_scenario(run_cli,
                                                                  make_task):
    body = _correct_body()
    body["changed_files"] = [{"path": "src/x.py",
                               "scenarios": ["SCN-DOES-NOT-EXIST"]}]
    task_dir = make_task("dangling-scn", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "dangling-scn")
    assert r.returncode != 0, r
    assert "changed-code-traces" in r.stdout, r
    assert "SCN-DOES-NOT-EXIST" in (r.stdout + r.stderr), r


def test_check_passes_when_changed_file_traces_to_real_scenario(run_cli, make_task):
    body = _correct_body()
    task_dir = make_task("traced", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "traced")
    assert r.returncode == 0, r
    assert "PASS" in r.stdout, r


# --- `G3` claim traceability -------------------------------------------------


def test_check_fails_when_claim_references_unknown_scenario(run_cli, make_task):
    body = _correct_body()
    body["claims"] = [{"id": "CLM-1", "text": "fast", "scenario": "SCN-???"}]
    task_dir = make_task("bad-claim", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "bad-claim")
    assert r.returncode != 0, r
    assert "claim-traces-to-scenario" in r.stdout, r


def test_check_passes_when_claim_references_a_real_scenario(run_cli, make_task):
    """The control for the test above: the same claim, pointed at a scenario
    the issue has, passes. Together they are this check's mutation proof
    (`tests/mutation_proofs.yml`)."""
    body = _correct_body()
    body["claims"] = [{"id": "CLM-1", "text": "fast", "scenario": "SCN-001"}]
    task_dir = make_task("good-claim", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "good-claim")
    assert r.returncode == 0, r


# --- `G4` gate evidence types ------------------------------------------------


def test_check_fails_on_wrong_evidence_type_for_gate(run_cli, make_task):
    """`verify.correctness` accepts only `test-run`. Clearing it with an
    `artifact` evidence id must fail."""
    body = _correct_body()
    # add an artifact-type evidence and point verify.correctness at it
    body["evidence"].append({
        "id": "EV-ART", "type": "artifact", "path": "notes.md",
    })
    body["gates"][0] = {
        "id": "verify.correctness", "status": "pass",
        "evidence": ["EV-ART"],
    }
    task_dir = make_task("wrong-type", body)
    _make_green(task_dir)
    # also create the file so path-resolution doesn't trip first
    (task_dir / "notes.md").write_text("placeholder")
    r = run_cli("check", "--verbose", "--issue", "wrong-type")
    assert r.returncode != 0, r
    # The FAIL line, not the bare name: --verbose prints every check's name,
    # and another check failing in this fixture would make the exit code
    # non-zero on its own.
    assert "FAIL gate-evidence-present" in r.stdout, r


def test_check_passes_with_correct_evidence_type(run_cli, make_task, project):
    body = _correct_body()
    body["gates"][0] = {
        "id": "verify.correctness", "status": "pass",
        "evidence": ["EV-T-SCN-001"],
    }
    task_dir = make_task("right-type", body)
    _make_green(task_dir)
    # Once an issue claims verify.correctness, `declared-tests-resolve` needs
    # the test it names to exist - claiming a scenario passes while pointing at
    # a test nobody wrote is the thing that check was added to catch. The
    # fixture has to model an issue that is genuinely in that state.
    (project / "tests").mkdir(parents=True, exist_ok=True)
    (project / "tests" / "test_x.py").write_text("def test_y():\n    assert True\n")
    # Same reasoning for `changed-code-traces-to-scenario`: an issue claiming
    # correctness over a file that is not on disk has a broken trace, so the
    # fixture must have the file it says it changed.
    (project / "src").mkdir(parents=True, exist_ok=True)
    (project / "src" / "x.py").write_text("x = 1\n")
    r = run_cli("check", "--verbose", "--issue", "right-type")
    assert r.returncode == 0, r


def test_check_fails_on_old_inline_dict_evidence_shape(run_cli, make_task):
    """The pre-registry inline `{type, path}` shape is explicitly rejected:
    the registry is now the model."""
    body = _correct_body()
    body["gates"][0] = {
        "id": "verify.correctness", "status": "pass",
        "evidence": {"type": "test-run", "path": "evidence/green.json"},
    }
    task_dir = make_task("old-shape", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "old-shape")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "old inline-evidence" in combined or "inline-evidence" in combined, r


def test_check_fails_on_evidence_id_not_in_registry(run_cli, make_task):
    """A gate referencing an evidence id that the registry does not contain."""
    body = _correct_body()
    body["gates"][0] = {
        "id": "verify.correctness", "status": "pass",
        "evidence": ["EV-NOPE"],
    }
    task_dir = make_task("dangling-ev", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "dangling-ev")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "EV-NOPE" in combined, r


# --- `G5` human approvals ----------------------------------------------------


def test_check_fails_on_g5_touched_task_with_no_approval(run_cli, make_task):
    """Touching auth without a human-approval evidence entry => check fails
    on the `G5` check."""
    body = _correct_body()
    body["assessment"]["labels"] = ["auth"]
    body["delivery_approach"] = "expedition"
    task_dir = make_task("g5-no-approval", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "g5-no-approval")
    assert r.returncode != 0, r
    assert "human-approval-present" in r.stdout, r


def test_check_fails_on_g5_approval_missing_fields(run_cli, make_task):
    """A human-approval entry without the required structured fields must
    fail - partial approvals are worse than missing ones."""
    body = _correct_body()
    body["assessment"]["labels"] = ["auth"]
    body["delivery_approach"] = "expedition"
    body["evidence"].append({
        "id": "EV-APP", "type": "human-approval",
        "decision": "approved",
        # missing approver, role, scope, timestamp
    })
    task_dir = make_task("g5-partial-approval", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "g5-partial-approval")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "missing required" in combined or "approver" in combined, r


def test_check_passes_on_complete_g5_approval(run_cli, make_task):
    body = _correct_body()
    body["assessment"]["labels"] = ["auth"]
    body["delivery_approach"] = "expedition"
    body["evidence"].append({
        "id": "EV-APP", "type": "human-approval",
        "approver": "ada@example.com",
        "role": "engineering-lead",
        "scope": "auth-related migration",
        "decision": "approved",
        "timestamp": "2026-05-15T10:00:00Z",
    })
    task_dir = make_task("g5-ok", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "g5-ok")
    # the approval check must pass - overall result depends on the other
    # checks all passing (they do, in this baseline issue), so we just check
    # the approval check passes its own line.
    assert "PASS human-approval-present" in r.stdout, r


# --- follow-ups: the backfills-paid check (cross-cutting) <!-- vocabulary-scan: allow - names the real check id --> ---


def test_check_fails_on_unpaid_backfill(run_cli, make_task):
    body = _correct_body()
    body["follow_ups"] = [{"id": "BF-1", "description": "promote repro test",
                           "status": "owed"}]
    task_dir = make_task("owed-bf", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "owed-bf")
    assert r.returncode != 0, r
    assert "backfills-paid" in r.stdout, r
    assert "BF-1" in (r.stdout + r.stderr), r


def test_check_passes_with_paid_backfill(run_cli, make_task):
    body = _correct_body()
    body["follow_ups"] = [{"id": "BF-1", "description": "promote repro test",
                           "status": "paid"}]
    task_dir = make_task("paid-bf", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "paid-bf")
    assert r.returncode == 0, r


# --- scenario-has-id-and-intent --------------------------------------------


def test_check_fails_when_scenario_has_no_intent(run_cli, make_task):
    body = _correct_body()
    body["scenarios"][0].pop("intent")
    task_dir = make_task("no-intent", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "no-intent")
    assert r.returncode != 0, r
    assert "scenario-has-id-and-intent" in r.stdout, r


# ---------------------------------------------------------------------------
# Group E - Typed Definition of Done (TRC-E1..E5, `TRC-X4`)
# ---------------------------------------------------------------------------

def _make_task_with_dod(make_task, slug, dod_lines, extra_evidence=None,
                        extra_backfills=None):
    """Create an issue + green evidence + verification-report.md with the
    given DoD lines.  Returns (task_dir, project_root)."""
    body = _correct_body()
    if extra_evidence:
        body["evidence"].extend(extra_evidence)
    if extra_backfills:
        body["follow_ups"] = extra_backfills
    task_dir = make_task(slug, body)
    _make_green(task_dir)
    # Write a verification-report.md that contains a "Definition of Done" section
    dod_content = "\n".join(dod_lines)
    report = (
        "# Verification Report - {}\n\n"
        "## Gate\n\n"
        "### Definition of Done\n\n"
        "{}\n"
    ).format(slug, dod_content)
    (task_dir / "verification-report.md").write_text(report, encoding="utf-8")
    return task_dir


def test_dod_unbacked_fails(run_cli, make_task):
    """`TRC-E1`: A bare unchecked DoD box with no evidence or follow-up tag
    blocks ship - the check must fail."""
    task_dir = _make_task_with_dod(
        make_task,
        "e1-bare-unchecked",
        ["- [ ] All branch-protection rules applied"],
    )
    r = run_cli("check", "--verbose", "--issue", "e1-bare-unchecked")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "dod-evidence-typed" in combined, r
    assert "branch-protection" in combined.lower() or "bare" in combined.lower(), r


def test_dod_with_evidence_passes(run_cli, make_task):
    """`TRC-E2`: An unchecked DoD line tagged (evidence: EV-A1) passes when
    EV-A1 is in the issue's evidence registry with an accepted type."""
    task_dir = _make_task_with_dod(
        make_task,
        "e2-evidence-tag",
        ["- [ ] (evidence: EV-A1) Branch-protection rule applied"],
        extra_evidence=[
            {"id": "EV-A1", "type": "human-approval",
             "approver": "ada@example.com", "role": "lead",
             "scope": "branch protection", "decision": "approved",
             "timestamp": "2026-05-23T10:00:00Z"},
        ],
    )
    r = run_cli("check", "--verbose", "--issue", "e2-evidence-tag")
    # The DoD check itself must pass for this line
    combined = r.stdout + r.stderr
    assert "PASS dod-evidence-typed" in combined, r


def test_owed_backfill_chains(run_cli, make_task):
    """`TRC-E3`: follow-up chain.
    Part A: T1's DoD line tagged with the legacy (backfill: BF-1) spelling, <!-- vocabulary-scan: allow - the legacy tag this test deliberately exercises -->
            kept on purpose, passes T1's check.
    Part B: T2's compass check fails because T1 has BF-1 status=owed
            with target_task=T2.
    """
    # ---- Part A: T1 passes ----
    task_dir_t1 = _make_task_with_dod(
        make_task,
        "e3-t1",
        ["- [ ] (backfill: BF-1) Fix the integration test harness"],
        extra_backfills=[
            {"id": "BF-1", "description": "Fix the integration test harness",
             "status": "owed", "target_task": "e3-t2"},
        ],
    )
    r_t1 = run_cli("check", "--verbose", "--issue", "e3-t1")
    combined_t1 = r_t1.stdout + r_t1.stderr
    assert "PASS dod-evidence-typed" in combined_t1, (
        "T1's DoD check should pass when backfill is tagged and recorded", r_t1)

    # ---- Part B: T2 fails because T1 has an owed follow-up targeting T2 ----
    # Make T2 as a minimal passing issue (no DoD issues itself)
    task_dir_t2 = _make_task_with_dod(
        make_task,
        "e3-t2",
        ["- [x] All unit tests green"],  # checked - no evidence tag needed
    )
    r_t2 = run_cli("check", "--verbose", "--issue", "e3-t2")
    assert r_t2.returncode != 0, (
        "T2 check should fail because T1's BF-1 (target_task=e3-t2) is owed", r_t2)
    combined_t2 = r_t2.stdout + r_t2.stderr
    assert "BF-1" in combined_t2 or "e3-t1" in combined_t2, (
        "Failure message should mention the blocking backfill or its source", r_t2)


def test_narrative_not_evidence(run_cli, make_task):
    """`TRC-E4`: A bare unchecked DoD line fails even when devlog.md contains
    'USER TO APPLY' - narrative notes do NOT clear the typed DoD check."""
    task_dir = _make_task_with_dod(
        make_task,
        "e4-user-to-apply",
        ["- [ ] Configure the staging environment"],
    )
    # Write a devlog.md with USER TO APPLY to confirm it has no effect
    (task_dir / "devlog.md").write_text(
        "# Devlog\n\n## 2026-05-23\n\nUSER TO APPLY the env config.\n",
        encoding="utf-8",
    )
    r = run_cli("check", "--verbose", "--issue", "e4-user-to-apply")
    assert r.returncode != 0, r
    combined = r.stdout + r.stderr
    assert "dod-evidence-typed" in combined, r
    # The failure message should cite `G4` (evidence, not assertion)
    assert "G4" in combined or "evidence" in combined.lower(), r


def test_human_approval_clears_dod(run_cli, make_task):
    """`TRC-E5`: A DoD line with (evidence: EV-A1) where EV-A1 is of type
    human-approval passes - human-approval is an accepted DoD evidence type."""
    task_dir = _make_task_with_dod(
        make_task,
        "e5-human-approval",
        ["- [ ] (evidence: EV-H1) Branch-protection rule applied"],
        extra_evidence=[
            {"id": "EV-H1", "type": "human-approval",
             "approver": "bob@example.com", "role": "lead",
             "scope": "branch protection", "decision": "approved",
             "timestamp": "2026-05-23T12:00:00Z"},
        ],
    )
    r = run_cli("check", "--verbose", "--issue", "e5-human-approval")
    combined = r.stdout + r.stderr
    assert "PASS dod-evidence-typed" in combined, r


def test_empty_dod_passes(run_cli, make_task):
    """`TRC-X4`: An issue with no DoD section (or empty DoD) passes the typed
    DoD check - backward compat for issues that predate the typed check."""
    # Case 1: no verification-report.md at all
    body = _correct_body()
    task_dir = make_task("x4-no-report", body)
    _make_green(task_dir)
    r = run_cli("check", "--verbose", "--issue", "x4-no-report")
    combined = r.stdout + r.stderr
    assert "PASS dod-evidence-typed" in combined, (
        "Should pass when verification-report.md is absent", r)

    # Case 2: verification-report.md exists but DoD section is empty
    task_dir2 = _make_task_with_dod(
        make_task,
        "x4-empty-dod",
        [],  # no DoD lines
    )
    r2 = run_cli("check", "--verbose", "--issue", "x4-empty-dod")
    combined2 = r2.stdout + r2.stderr
    assert "PASS dod-evidence-typed" in combined2, (
        "Should pass when DoD section has no items", r2)
