"""guardrails.yml gains no undeclared check, gate or evidence type.

Adding a check or a gate is adding mechanism, and the framework grows by
checks and strategies deliberately, never by accident (ADR-002). These tests
make such an addition visible in review rather than silent.

This is a negative assertion test: a check or gate name declared in
`BASELINE_CHECKS` or `BASELINE_GATES` passes; anything else is a new,
undeclared addition.

It also checks that the empty `project:` list carries a comment saying the
emptiness is deliberate.
"""
from __future__ import annotations
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
GUARDRAILS_YML = "governance/guardrails.yml"

# The known-legitimate check names.
# The invariant is that guardrails.yml gains no new check names. The
# structural comparison against main below is the canonical guard; the
# state-based tests use this list as the known-legitimate set.
BASELINE_CHECKS = {
    # Added by the borrowed document shapes. A threat model that lists
    # threats and mitigates none is the Threat Modeling Manifesto's named
    # anti-pattern, and a rollback plan nobody has rehearsed is a guess.
    # One check reads both, under `G4` rather than as a sixth guardrail
    # (ADR-002).
    "borrowed-documents-answered",
    # Added by the per-issue review dashboard: it is what a reviewer
    # approves from, so it must not be allowed to disagree with the
    # manifest it was rendered from. Joins `G4` rather than becoming a
    # sixth guardrail (ADR-002).
    "dashboard-current",
    "scenarios-have-tests",
    "suite-passed",
    "changed-code-traces-to-scenario",
    "scenario-has-id-and-intent",
    "claim-traces-to-scenario",
    "gate-evidence-present",
    # Added by no-status-for-work-done-elsewhere. An issue whose work was
    # delivered through a different issue points at it with `landed_by:`,
    # and this checks that the pointer resolves both ways. Joins `G3`
    # (traceability) rather than becoming a sixth guardrail (ADR-002) -
    # the pointer is a traceability link, and the check is what stops it
    # being a one-sided claim on somebody else's evidence.
    "landed-by-resolves",
    # Added by tdd-green-unbound-record. Checks whether a registry entry
    # still names the record it was created from, so a gate cannot rest on
    # a record from a different run. Joins `G4` rather than becoming a
    # sixth guardrail (ADR-002).
    "evidence-identity-matches",
    # Added by evidence-binding. A green record names the tree it ran on,
    # and this checks the newest one still names the tree that ships, or,
    # for a landed issue, the files the landing commit holds. Joins `G4`
    # rather than becoming a sixth guardrail (ADR-002).
    "evidence-matches-tree",
    "human-approval-present",
    "backfills-paid",
    "spike-conclusion-present",
    "spike-no-production-changes",
    "dod-evidence-typed",
    "coherence-check-passes",
    "no-trusted-rerun",   # refuses to clear a test-run that only passed on a rerun
    "command-passes",     # runs a project-declared command and needs exit 0
    # Added by record-keeping-integrity. A scenario's declared test id must
    # point at a test that exists, so a named-but-nonexistent test can no
    # longer read as green. Joins `G1`.
    "declared-tests-resolve",
    # Added by phase-2-skills-check-and-cli-split. Checks that every
    # scenario in manifest.yml was accounted for by the project's BDD
    # runner, reading the record `compass bdd verify` writes. Joins `G1`,
    # and no-ops entirely for a project that has set no project.bdd_runner,
    # which is nearly all of them.
    "scenarios-are-executable",
    # Added by dispatch-protocol. A multiagent issue's manifest must show the
    # run that built it completed - every subtask done, with a last review
    # round that passed. Joins the evidence-not-assertion guardrail (`G4`)
    # rather than becoming a sixth guardrail: ADR-002 caps guardrails at
    # five and grows the framework through new checks instead.
    "multiagent-run-recorded",
}

# The legitimate set of gate names in gate_evidence_requirements after landing.
BASELINE_GATES = {
    "verify.correctness",
    "verify.regression",
    "verify.security",
    "verify.governance",
    "verify.traceability",
    "verify.claims",
    "verify.clarity",
    "spike.conclude",
    "verify.analyze",
    # Added with project-declared architecture checks. Recorded under the name
    # it had when it was added; `_rename_gates` maps it forward, so this entry
    # does not need rewriting each time the vocabulary moves.
    "verify.fitness",
}


def _gate_renames() -> dict:
    """Retired gate id -> current gate id, from the shipped rename table.

    This guard's question is "did mechanism appear that nothing declared", not
    "did a name change". Reading `cli/migrate-map.yml` separates the two: a
    renamed gate has a row there and is the same mechanism under a new name,
    while a genuinely new gate has no row and still fails below.

    Hard-coding the current names instead would make this guard pass today and
    go blind to the next rename, which is the failure ADR-015 records - a check
    that quietly stops reading what it was pointed at.
    """
    import yaml

    path = REPO_ROOT / "cli" / "migrate-map.yml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(data.get("gate_ids") or {})


def _rename_gates(names):
    """`names` with every retired gate id mapped to its current spelling."""
    renames = _gate_renames()
    return {renames.get(n, n) for n in names}


def _check_renames() -> dict:
    """Retired check name -> current check name, from the same rename table.

    A renamed check is the same mechanism under a new name, exactly as a
    renamed gate is; a check with no row here is genuinely new and still fails.
    """
    import yaml

    path = REPO_ROOT / "cli" / "migrate-map.yml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict((data.get("values") or {}).get("check_name") or {})


def _rename_checks(names):
    renames = _check_renames()
    return {renames.get(n, n) for n in names}


def _evidence_type_renames() -> dict:
    """Retired evidence type -> current one, from the same rename table."""
    import yaml

    path = REPO_ROOT / "cli" / "migrate-map.yml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict((data.get("values") or {}).get("evidence_type") or {})


def _guardrails_on_main() -> dict | None:
    """guardrails.yml as it stands on main, or None if main is not reachable.

    CI clones at depth 1, so the main ref is often absent there and no
    comparison is possible. Returning None makes the caller pass rather than
    fail on a missing ref, which is what a branch-relative test can honestly
    do in a shallow checkout.
    """
    import yaml

    result = subprocess.run(
        ["git", "show", f"main:{GUARDRAILS_YML}"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return yaml.safe_load(result.stdout)


def _mechanism(data: dict) -> dict:
    """The parts of guardrails.yml that are mechanism rather than prose.

    Everything a check, a gate, or the CLI acts on. Free text (`name`,
    `statement`, `description`) is deliberately excluded: rewording a
    guardrail is an editorial act, adding one is a structural act, and only
    the second is what this file guards against.
    """
    def rules(items):
        return {
            r["id"]: {
                "checks": sorted(r.get("checks", [])),
                "checked_at": sorted(r.get("checked_at", [])),
                "applies_when": r.get("applies_when"),
                "params": r.get("params"),
            }
            for r in (items or [])
        }

    return {
        "top_level_keys": sorted(data.keys()),
        "check_names": sorted(data.get("checks", {})),
        # Evidence types normalise through the rename table before comparison,
        # for the same reason gate ids and check names do: a rename is the same
        # mechanism under a new name, an addition is not.
        "evidence_types": sorted(
            _evidence_type_renames().get(t, t)
            for t in (data.get("evidence_types") or {})),
        # Gate ids are normalised through the shipped rename table before the
        # comparison, so a rename reads as the same mechanism and only an
        # undeclared addition shows up as a difference. See _gate_renames.
        "gate_evidence_requirements": {
            _gate_renames().get(gate, gate): sorted(
                _evidence_type_renames().get(t, t) for t in types)
            for gate, types in (data.get("gate_evidence_requirements") or {}).items()
        },
        "defaults": rules(data.get("defaults")),
        "spike_guardrails": rules(data.get("spike_guardrails")),
        "project": rules(data.get("project")),
    }


def test_no_new_check_names_added():
    """No new check name has appeared in the checks: block in guardrails.yml."""
    import yaml

    guardrails_path = REPO_ROOT / GUARDRAILS_YML
    current_content = yaml.safe_load(guardrails_path.read_text(encoding="utf-8"))
    current_checks = set(current_content.get("checks", {}).keys())

    new_checks = current_checks - _rename_checks(BASELINE_CHECKS)
    assert not new_checks, (
        f"guardrails.yml gained new checks: {new_checks}. A new check is new\n"
        "mechanism: add it here deliberately, with the change that introduces it."
    )


def test_no_new_gate_names_added():
    """No new gate name has appeared in gate_evidence_requirements."""
    import yaml

    guardrails_path = REPO_ROOT / GUARDRAILS_YML
    current_content = yaml.safe_load(guardrails_path.read_text(encoding="utf-8"))
    current_gates = set(current_content.get("gate_evidence_requirements", {}).keys())

    new_gates = current_gates - _rename_gates(BASELINE_GATES)
    assert not new_gates, (
        f"guardrails.yml gained new gates: {new_gates}. A new gate is new\n"
        "mechanism: add it here deliberately, with the change that introduces it."
    )


def test_guardrails_gains_no_mechanism_on_this_branch():
    """A branch may not add mechanism to guardrails.yml *undeclared*.

    Compares the parsed structure with main. Prose can change; mechanism
    must not grow unless declared. A check declared in BASELINE_CHECKS
    passes, because the decision record that caps guardrails at five and
    permits new checks under an existing guardrail (ADR-002) allows it.
    Gates, evidence types and rules must match main.
    """
    import yaml

    baseline = _guardrails_on_main()
    if baseline is None:
        return  # main not reachable (shallow clone); nothing to compare against

    current = yaml.safe_load((REPO_ROOT / GUARDRAILS_YML).read_text(encoding="utf-8"))
    before, after = _mechanism(baseline), _mechanism(current)

    # Checks declared in BASELINE_CHECKS are a sanctioned, reviewed addition;
    # everything else in the mechanism must match main exactly.
    for field in sorted(before):
        b, a = before[field], after[field]
        if field == "check_names":
            added = set(a) - set(b)
            assert added <= _rename_checks(BASELINE_CHECKS), (
                f"guardrails.yml gained undeclared check(s): "
                f"{sorted(added - BASELINE_CHECKS)}.\n"
                "A new check is new mechanism (ADR-002). Declare it in "
                "BASELINE_CHECKS above, with a comment naming the change that "
                "introduces it, so the addition is visible in review."
            )
            assert _rename_checks(set(b)) - set(a) == set(), (
                f"guardrails.yml removed check(s): "
                f"{sorted(_rename_checks(set(b)) - set(a))}. "
                "Removing a check silently weakens every adopting project."
            )
            continue
        if field == "defaults":
            # A guardrail may gain a declared check; it may not gain or lose a
            # guardrail, nor change when it is checked.
            assert sorted(b) == sorted(a), (
                f"guardrails.yml changed the guardrail set: {sorted(b)} -> "
                f"{sorted(a)}. The count is capped at five (ADR-002).")
            for gid in b:
                assert b[gid]["checked_at"] == a[gid]["checked_at"], (
                    f"{gid} changed when it is checked: "
                    f"{b[gid]['checked_at']} -> {a[gid]['checked_at']}")
                gained = set(a[gid]["checks"]) - _rename_checks(set(b[gid]["checks"]))
                assert gained <= BASELINE_CHECKS, (
                    f"{gid} gained undeclared check(s): "
                    f"{sorted(gained - BASELINE_CHECKS)}")
                lost = _rename_checks(set(b[gid]["checks"])) - set(a[gid]["checks"])
                assert lost == set(), (
                    f"{gid} lost check(s): {sorted(lost)}")
            continue
        assert b == a, (
            f"guardrails.yml changed mechanism in {field!r} relative to main.\n"
            f"  on main: {b!r}\n"
            f"  now:     {a!r}\n"
            "Guardrails are capped at five and grow by checks and strategies, "
            "not by new rules (ADR-002). Rewording prose is fine; adding a "
            "gate, evidence type, or rule is not."
        )


def test_empty_project_guardrails_are_explained():
    """The empty `project:` list says why it is empty.

    An empty list looks identical whether it is deliberate or an oversight, and
    the difference matters: it is what makes an adopting repo see no
    project-level check until it declares one. A reader should not have to
    guess which it is.

    The no-growth guarantee is checked by
    `test_guardrails_gains_no_mechanism_on_this_branch` above and by
    `test_no_project_guardrails_declared_in_framework_repo`.
    """
    text = (REPO_ROOT / GUARDRAILS_YML).read_text(encoding="utf-8")
    idx = text.find("project: []")
    assert idx != -1, "guardrails.yml must ship with an empty project: [] list"
    trailing = text[idx:].splitlines()[1:3]
    assert any(l.lstrip().startswith("#") and l.strip() != "#" for l in trailing), (
        "The empty `project: []` list must be followed by a comment explaining "
        "that it is deliberate, so a reader can tell it apart from an oversight."
    )
