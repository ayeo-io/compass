"""Reassessment recording + `compass retro`.

When `compass approach evaluate --write` computes a delivery approach that
differs from the one already recorded in manifest.yml, the diff is logged
under `reassessments:`. `compass retro` aggregates these across every issue
and classifies the trend as up (assessment under-sizing) or down
(over-sizing).
"""
from __future__ import annotations

import yaml


def _readings_to_args(d):
    out = []
    for k, v in d.items():
        if isinstance(v, list):
            out.extend(["--assessment", f"{k}=" + ",".join(v)])
        else:
            out.extend(["--assessment", f"{k}={v}"])
    return out


# --- the recording behaviour ----------------------------------------------


def test_route_evaluate_write_logs_reframe(run_cli, make_task, project):
    """An issue that already had a delivery approach (the legacy value
    `express`, written on purpose) gets re-evaluated as initiative (after
    `auth` is added to its labels) - the diff must be appended to
    `reassessments:`."""
    body = {
        "task": "rf-task",
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
            "labels": [],
        },
        "delivery_approach": "express",   # the recorded approach the next eval will diff against
    }
    task_dir = make_task("rf-task", body)
    # mutate the assessment (labels=auth) so the next evaluate computes initiative
    body["assessment"]["labels"] = ["auth"]
    (task_dir / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False))

    r = run_cli("approach", "evaluate", "--issue", "rf-task", "--write",
                "--reason", "discovered the change touches auth")
    assert r.returncode == 0, r
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert task["delivery_approach"] == "initiative"
    assert task["reassessments"], "expected a reframes entry"
    rf = task["reassessments"][-1]
    assert rf["from_route"] == "quick-fix"
    assert rf["to_route"] == "initiative"
    assert "auth" in rf["reason"]


def test_route_evaluate_does_not_log_reframe_when_route_unchanged(run_cli,
                                                                  make_task,
                                                                  project):
    """Re-running --write with the same assessment must not spuriously log
    a reassessment."""
    body = {
        "task": "no-rf",
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "delivery_approach": "express",
    }
    task_dir = make_task("no-rf", body)
    r = run_cli("approach", "evaluate", "--issue", "no-rf", "--write")
    assert r.returncode == 0, r
    task = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert task["delivery_approach"] == "quick-fix"
    assert not task.get("reassessments"), f"expected no reframes, got: {task.get('reframes')}"


def test_route_evaluate_warns_when_reframe_has_no_reason(run_cli, make_task,
                                                        project):
    """Re-assessment with no --reason still records the entry, but warns - the
    reason is the calibration signal."""
    body = {
        "task": "rf-noreason",
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
            "labels": ["auth"],
        },
        "delivery_approach": "express",
    }
    task_dir = make_task("rf-noreason", body)
    r = run_cli("approach", "evaluate", "--issue", "rf-noreason", "--write")
    assert r.returncode == 0, r
    combined = r.stdout + r.stderr
    # the CLI must mention the missing reason on stderr
    assert "reason" in combined.lower(), r
    # and name the manifest key a user can edit today
    assert "`reassessments`" in r.stderr and "`reframes`" not in r.stderr, r.stderr


# --- the aggregator: calibration -------------------------------------------


def _task_with_reframes(slug, transitions, base_route="standard"):
    """transitions: list of (from_route, to_route) tuples."""
    return {
        "task": slug,
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "route": base_route,
        "reassessments": [
            {"from_route": fr, "to_route": to, "reason": "x",
             "date": "2026-05-15"}
            for fr, to in transitions
        ],
    }


def test_calibration_no_tasks(run_cli):
    r = run_cli("retro")
    assert r.returncode == 0, r
    assert "no issues" in r.stdout.lower(), r


def test_calibration_aggregates_up_reframes(run_cli, make_task):
    """Three up re-assessments (express -> expedition, standard -> expedition,
    express -> standard) must report 'UNDER-sizing'."""
    make_task("t1", _task_with_reframes(
        "t1", [("express", "expedition")], base_route="expedition"))
    make_task("t2", _task_with_reframes(
        "t2", [("standard", "expedition")], base_route="expedition"))
    make_task("t3", _task_with_reframes(
        "t3", [("express", "standard")], base_route="standard"))
    r = run_cli("retro")
    assert r.returncode == 0, r
    assert "UNDER-sizing" in r.stdout, r


def test_calibration_aggregates_down_reframes(run_cli, make_task):
    """Three down re-assessments report 'OVER-sizing'."""
    make_task("t1", _task_with_reframes(
        "t1", [("expedition", "express")], base_route="express"))
    make_task("t2", _task_with_reframes(
        "t2", [("expedition", "standard")], base_route="standard"))
    make_task("t3", _task_with_reframes(
        "t3", [("standard", "express")], base_route="express"))
    r = run_cli("retro")
    assert r.returncode == 0, r
    assert "OVER-sizing" in r.stdout, r


def test_calibration_balanced(run_cli, make_task):
    """One up, one down - balanced; neither over nor under."""
    make_task("t1", _task_with_reframes(
        "t1", [("express", "standard")], base_route="standard"))
    make_task("t2", _task_with_reframes(
        "t2", [("expedition", "standard")], base_route="standard"))
    r = run_cli("retro")
    assert r.returncode == 0, r
    out = r.stdout
    # neither verdict must be selected when ups == downs == 1
    assert "UNDER-sizing" not in out, r
    assert "OVER-sizing" not in out, r
    # and the route distribution must be reported
    assert "Delivery approaches:" in out, r


# --- `TRC-C5`: unrecorded re-assessments section in calibration output -------


def test_reframe_debt_section(run_cli, make_task, project):
    """`TRC-C5`: compass retro surfaces absorbed mis-frames.

    An issue with scope-bloat devlog phrases and an empty re-assessments list is
    reported in an 'unrecorded re-assessments' section, with the matched devlog signal
    and explicit mention that the signal was absorbed/lost.

    The devlog patterns come from signals.yml, not hardcoded in
    the CLI.
    """
    import pathlib
    import shutil

    # Make sure signals.yml is in the project's governance/ so the CLI can find it
    gov_dir = project / "governance"
    signals_src = pathlib.Path(__file__).resolve().parent.parent / "governance" / "signals.yml"
    if signals_src.is_file() and not (gov_dir / "signals.yml").is_file():
        shutil.copy(signals_src, gov_dir / "signals.yml")

    # Issue with a scope-bloat devlog phrase and no re-assessments
    task_dir = make_task("reframe-debt-task", {
        "task": "reframe-debt-task",
        "created": "2026-05-20",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
        },
        "delivery_approach": "standard",
        "reassessments": [],
    })
    (task_dir / "devlog.md").write_text(
        "2026-05-20: more files than Plan estimated - had to extend the scope\n"
    )

    r = run_cli("retro")
    assert r.returncode == 0, r

    out = r.stdout.lower()
    assert "unrecorded re-assessments" in out, (
        "Expected an 'unrecorded re-assessments' section in calibration output.\n"
        f"Got:\n{r.stdout}"
    )
    # Must name the issue
    assert "reframe-debt-task" in r.stdout.lower(), (
        "Reframe-debt section must name the affected task.\n"
        f"Got:\n{r.stdout}"
    )
    # Must explain the consequence
    assert "scope grew with no re-assessment" in out, (
        "The unrecorded re-assessments section must say the scope grew and none was recorded.\n"
        f"Got:\n{r.stdout}"
    )


def test_reframe_debt_empty_when_no_bloat(run_cli, make_task, project):
    """`TRC-C5` negative case: issues with no scope-bloat phrases get no unrecorded re-assessments section."""
    import pathlib
    import shutil

    gov_dir = project / "governance"
    signals_src = pathlib.Path(__file__).resolve().parent.parent / "governance" / "signals.yml"
    if signals_src.is_file() and not (gov_dir / "signals.yml").is_file():
        shutil.copy(signals_src, gov_dir / "signals.yml")

    make_task("clean-no-bloat", {
        "task": "clean-no-bloat",
        "created": "2026-05-20",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
        },
        "delivery_approach": "standard",
        "reassessments": [],
    })

    r = run_cli("retro")
    assert r.returncode == 0, r
    # No unrecorded re-assessments section when devlog has no scope-bloat phrases
    assert "unrecorded re-assessments" not in r.stdout.lower(), (
        "Unexpected reframe-debt section when no scope-bloat phrases in devlog.\n"
        f"Got:\n{r.stdout}"
    )


def test_reframe_debt_suppressed_when_reframe_filed(run_cli, make_task, project):
    """`TRC-C5` suppression case: a filed re-assessment removes the debt for that issue."""
    import pathlib
    import shutil

    gov_dir = project / "governance"
    signals_src = pathlib.Path(__file__).resolve().parent.parent / "governance" / "signals.yml"
    if signals_src.is_file() and not (gov_dir / "signals.yml").is_file():
        shutil.copy(signals_src, gov_dir / "signals.yml")

    task_dir = make_task("reframed-ok", {
        "task": "reframed-ok",
        "created": "2026-05-19",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
        },
        "delivery_approach": "expedition",
        "reassessments": [
            {
                "from_route": "standard",
                "to_route": "expedition",
                "reason": "scope grew",
                "date": "2026-05-20",
            }
        ],
    })
    (task_dir / "devlog.md").write_text(
        "2026-05-19: more files than Plan estimated\n"
    )

    r = run_cli("retro")
    assert r.returncode == 0, r
    # The issue had a bloat phrase BUT a re-assessment was filed after - no debt
    # (If the section is absent entirely, or the issue is not in it, pass.)
    out = r.stdout.lower()
    if "unrecorded re-assessments" in out:
        assert "reframed-ok" not in out, (
            "Task 'reframed-ok' should not appear under unrecorded "
            "re-assessments when a re-assessment was already recorded.\n"
            f"Got:\n{r.stdout}"
        )


# --- friction aggregation: calibration --friction --------------------------
# `TRC-B1`, `TRC-B2`, `TRC-B3`, `TRC-F1`, `TRC-F2`, `TRC-F3`.


def _task_with_friction(slug, friction, base_route="standard"):
    return {
        "task": slug,
        "created": "2026-05-15",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
            "intent": "delivery",
        },
        "route": base_route,
        "friction": friction,
    }


def _friction(proposed_change, category="over-ceremony", source="human"):
    return {
        "phase": "plan",
        "category": category,
        "observation": "ceremony got in the way",
        "proposed_change": proposed_change,
        "source": source,
    }


PC_CLARIFY = "routing-policy.yml: lower Clarify weight for size=small."


def test_friction_groups_recurring_by_category_and_target(run_cli, make_task):
    """`TRC-B1`: friction recurring across issues is grouped by category and by
    proposed_change target, and reports the contributing count."""
    make_task("ft1", _task_with_friction("ft1", [_friction(PC_CLARIFY)]))
    make_task("ft2", _task_with_friction("ft2", [_friction(PC_CLARIFY)]))
    make_task("ft3", _task_with_friction("ft3", [_friction(PC_CLARIFY)]))
    r = run_cli("retro", "--friction")
    assert r.returncode == 0, r
    out = r.stdout
    assert "over-weight" in out, r            # grouped by category
    assert PC_CLARIFY in out, r               # grouped by proposed_change target
    assert "3" in out, r                      # contributing count


def test_friction_one_off_below_threshold(run_cli, make_task):
    """`TRC-B2`: a single occurrence (below the default threshold of 2) is not
    surfaced as a recurring trend."""
    make_task("ft1", _task_with_friction(
        "ft1", [_friction("a one-off proposal nobody else made")]))
    # plus an unrelated recurring pair so the report is non-empty
    make_task("ft2", _task_with_friction("ft2", [_friction(PC_CLARIFY)]))
    make_task("ft3", _task_with_friction("ft3", [_friction(PC_CLARIFY)]))
    r = run_cli("retro", "--friction")
    assert r.returncode == 0, r
    # The recurring cluster is surfaced…
    assert PC_CLARIFY in r.stdout, r
    # …but the one-off must NOT be reported as a recurring/trend item.
    # We assert it does not appear in a "recurring" context: simplest robust
    # check - the JSON view classifies it below threshold.
    rj = run_cli("retro", "--friction", "--format", "json")
    assert rj.returncode == 0, rj
    import json as _json
    data = _json.loads(rj.stdout)
    recurring_pcs = {c["proposed_change"] for c in data["recurring"]}
    assert PC_CLARIFY in recurring_pcs, rj
    assert "a one-off proposal nobody else made" not in recurring_pcs, rj


def test_friction_json_format(run_cli, make_task):
    """`TRC-B3`: --friction --format json emits machine-consumable JSON carrying
    the grouped, threshold-filtered clusters with contributing issue slugs."""
    make_task("ft1", _task_with_friction("ft1", [_friction(PC_CLARIFY)]))
    make_task("ft2", _task_with_friction("ft2", [_friction(PC_CLARIFY)]))
    r = run_cli("retro", "--friction", "--format", "json")
    assert r.returncode == 0, r
    import json as _json
    data = _json.loads(r.stdout)          # must be valid JSON
    assert "recurring" in data, r
    cluster = next(c for c in data["recurring"]
                   if c["proposed_change"] == PC_CLARIFY)
    assert cluster["count"] == 2, r
    assert set(cluster["tasks"]) == {"ft1", "ft2"}, r


def test_friction_view_writes_nothing(run_cli, make_task, project):
    """`TRC-F2`: the friction view is read-only - it writes no manifest.yml and no
    file under governance/, and exits 0."""
    import hashlib

    task_dir = make_task("ft1", _task_with_friction("ft1", [_friction(PC_CLARIFY)]))
    task_yml = task_dir / "manifest.yml"

    def _tree_sha(root):
        h = hashlib.sha256()
        for p in sorted(root.rglob("*")):
            if p.is_file():
                h.update(p.relative_to(root).as_posix().encode())
                h.update(p.read_bytes())
        return h.hexdigest()

    gov_before = _tree_sha(project / "governance")
    task_before = hashlib.sha256(task_yml.read_bytes()).hexdigest()

    r = run_cli("retro", "--friction")
    assert r.returncode == 0, r

    assert _tree_sha(project / "governance") == gov_before, (
        "TRC-F2 violated: --friction modified a file under governance/")
    assert hashlib.sha256(task_yml.read_bytes()).hexdigest() == task_before, (
        "TRC-F2 violated: --friction mutated manifest.yml")


def test_friction_never_in_land_gate(framework_root):
    """`TRC-F1`: friction is a strategy-class signal - it never appears as a
    guardrail check or in the ship gate. A regression guard against the
    design breaking ADR-002."""
    guardrails = (framework_root / "governance" / "guardrails.yml").read_text().lower()
    assert "friction" not in guardrails, (
        "TRC-F1 violated: guardrails.yml references friction - it must never "
        "be a gate (ADR-002).")
    ship = (framework_root / "commands" / "ship.md").read_text()
    # The gate is the checklist under the '## Gate - ship refuses to close …'
    # heading (not the intro, and not the Procedure, where friction capture is
    # an explicit *non*-gate step).
    gate_section = ship.split("## Gate", 1)[-1].lower()
    assert "friction" not in gate_section, (
        "TRC-F1 violated: friction appears in ship's 'refuses to close' gate.")


def test_friction_recorded_but_unclusterable_is_not_reported_as_none(
        run_cli, make_task):
    """An issue that recorded friction with no proposed_change (e.g. a derived
    re-assessment entry, or a human note without a proposal) must NOT be reported as
    'No friction recorded' - that line is for an empty corpus only. The entry is
    still surfaced (by category), it just hasn't clustered into a trend."""
    make_task("ft1", _task_with_friction("ft1", [
        {"phase": "build", "category": "tooling",
         "observation": "the devlog auto-log is noisy", "source": "human"},
    ]))
    r = run_cli("retro", "--friction")
    assert r.returncode == 0, r
    out = r.stdout
    assert "1 issue" in out, r
    assert "No friction recorded" not in out, (
        "recorded-but-unclusterable friction must not read as 'No friction "
        f"recorded':\n{out}")
    assert "tooling" in out, r          # the entry is still visible by category


def test_calibration_without_friction_unchanged(run_cli, make_task):
    """`TRC-F3`: plain `compass retro` (no --friction) ignores friction
    entirely - its output never mentions friction. The no-op guarantee."""
    make_task("ft1", _task_with_friction("ft1", [_friction(PC_CLARIFY)]))
    make_task("ft2", _task_with_friction("ft2", [_friction(PC_CLARIFY)]))
    r = run_cli("retro")
    assert r.returncode == 0, r
    assert "friction" not in r.stdout.lower(), (
        "TRC-F3 violated: plain calibration leaked friction into its output.")


def test_calibration_does_not_mutate_task_yml(run_cli, make_task, project):
    """Calibration is read-only - manifest.yml must be unchanged after running."""
    import pathlib
    import hashlib
    import shutil

    gov_dir = project / "governance"
    signals_src = pathlib.Path(__file__).resolve().parent.parent / "governance" / "signals.yml"
    if signals_src.is_file() and not (gov_dir / "signals.yml").is_file():
        shutil.copy(signals_src, gov_dir / "signals.yml")

    task_dir = make_task("immutable-task", {
        "task": "immutable-task",
        "created": "2026-05-20",
        "assessment": {
            "risk": "contained",
            "familiarity": "brownfield-mapped",
            "size": "small",
        },
        "delivery_approach": "standard",
        "reassessments": [],
    })
    (task_dir / "devlog.md").write_text(
        "more files than Plan estimated\n"
    )

    task_yml = task_dir / "manifest.yml"
    sha_before = hashlib.sha256(task_yml.read_bytes()).hexdigest()

    r = run_cli("retro")
    assert r.returncode == 0, r

    sha_after = hashlib.sha256(task_yml.read_bytes()).hexdigest()
    assert sha_before == sha_after, (
        f"calibration mutated manifest.yml, but it must be read-only\n"
        f"Before SHA: {sha_before}\nAfter SHA:  {sha_after}"
    )
