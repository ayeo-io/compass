"""The check set gains no undeclared check or gate.

Adding a check or a gate is adding mechanism, and the framework grows by
checks and strategies deliberately, never by accident (ADR-002). These tests
make such an addition visible in review rather than silent.

This is a negative assertion test: a check or gate name declared in
`BASELINE_CHECKS` or `BASELINE_GATES` passes; anything else is a new,
undeclared addition.

9.0.0 deleted the generated view `guardrails.yml` (ADR-098), so
these tests read the check set in that view's shape. The comparison of the
view with main, and the comment on its empty `project:` list, went with the
file: the check set's bytes are pinned per version
(`tests/fixtures/check-set-digests.yml`), so no change to it goes unseen.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
GUARDRAILS_YML = "guardrails.yml"

# The known-legitimate check names.
# The invariant is that guardrails.yml gains no new check names. The
# structural comparison against main below is the canonical guard; the
# state-based tests use this list as the known-legitimate set.
#: Checks a release removed on purpose, each with the change that removed it. Anything
#: else missing from guardrails.yml fails the comparison with main.
REMOVED_CHECKS = {
    # documents-carry-judgement: replaced by `rendered-blocks-current`, which checks
    # every block Compass writes in an issue's documents and not only the README.
    "dashboard-current",
    # ayeo-io/compass-delivery#353: 9.0.0 renders no block, issue page or project
    # index (ADR-091). A stored generation that lists it reports it as nothing to check.
    "rendered-blocks-current",
    # ayeo-io/compass-delivery#352: 9.0.0 runs each issue in one session, so no
    # run splits into subtasks to record (ADR-090). A stored generation that
    # lists it reports it as nothing to check.
    "multiagent-run-recorded",
    # ayeo-io/compass-delivery#353: 9.0.0 removes `compass analyze`, so no
    # consistency report is written to check (ADR-091). A stored generation that
    # lists it reports it as nothing to check.
    "consistency-check-passes",
    # ayeo-io/compass-delivery#353: 9.0.0 keeps one issue document (ADR-091), so the
    # checks that read the others go. A stored generation that lists one reports it as
    # nothing to check.
    "artifacts-approved",
    "contracts-declared",
    "design-within-word-ceiling",
    "borrowed-documents-answered",
}

# Gates a release removed on purpose, each with the change that removed it. A
# gate here may leave `gate_evidence_requirements`; any other change still fails.
REMOVED_GATES = {
    # ayeo-io/compass-delivery#353: `verify.analyze` accepted only the evidence
    # `compass analyze` wrote, and 9.0.0 removes that command (ADR-091).
    "verify.analyze",
}

# Guardrails a release moved to another stage on purpose, each with its new
# `checked_at` list, read on the four-stage path (ADR-092). `G1` is judged at
# build, where the red and green records are made, and was judged at `verify`,
# which the path shows as ship (ayeo-io/compass-delivery#351, plan section 2.3).
MOVED_STAGES = {"G1": ["build", "ship"]}

BASELINE_CHECKS = {
    # #355 added the ship approval and #356 the request link, after the view
    # `guardrails.yml` froze; the check set holds both.
    "ship-approval-present",
    "request-recorded",
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
    # Added by document-set-sections (ADR-064). The spec's Non-functional
    # requirements rows. It sits in no guardrail: `G2` and `G4` are locked.
    "nfr-rows-resolved",
    # Added by acceptance-strategy-core (strategy `S17`). The advisory check that the
    # stored applicability of the four-layer acceptance strategy agrees with the
    # records. It sits in no guardrail, so `G1` and `G4` keep their checks.
    "acceptance-applicability-agrees",
    # Added by loop-marking (ADR-080). The blocking check that an in-scope issue of the
    # four-layer acceptance strategy has an outer-loop red and an outer-loop green on the
    # current tree. It sits in no guardrail, so `G1` and `G4` keep their checks.
    "outer-loop-recorded",
    # Added by support-code-readiness. The advisory check that the project names its
    # acceptance support code and each named path exists; it states the claim limit.
    # It sits in no guardrail, so `G1` and `G4` keep their checks.
    "acceptance-support-present",
    # Added by `attempts-required` (ADR-084). The blocking check that each outer-loop
    # green of an in-scope issue records `attempts`. It sits in no guardrail, so `G4`
    # and its locked no-trusted-rerun keep their rules.
    "outer-loop-attempts-recorded",
    # Added by `isolation-and-layering` (ADR-086). The blocking checks that an in-scope
    # issue holds a passing isolation proof and layering record, written only by their
    # commands. They sit in no guardrail, so `G1` and `G4` keep their checks.
    "isolation-proven",
    "layering-test-passed",
}

# The evidence types a branch may add to guardrails.yml, each named for the
# change that adds it.
BASELINE_EVIDENCE_TYPES = {
    # Added by artifact-status-written-by-stages (ADR-050). A person's approval
    # of one document or of a set of decisions. No gate accepts it and
    # `human-approval-present` never reads it, so it cannot clear `G5`.
    "artifact-approval",
    # Added by autonomy-ratio-and-cost (ADR-063). A person's answer to one
    # checkpoint hand-off, written only by `compass evidence approve
    # --checkpoint`. It has no `check` key, no gate accepts it and
    # `human-approval-present` never reads it, so it cannot clear `G5`; a
    # separate type keeps that locked check unchanged.
    "checkpoint-approval",
    # Added by approve-inside-claude-code (ADR-069 decision 6). A person's
    # withdrawal of a guardrail `G5` sign-off made under a delegation, written
    # only by `/compass:reject <record id>`. No gate accepts it; it only stops
    # the withdrawn record counting for `human-approval-present` in flight.
    "approval-withdrawal",
    # Added by isolation-and-layering (ADR-086). The records of the four-layer
    # acceptance strategy, each written only by its command (`compass isolation
    # record`, `compass layering record`); `compass evidence add` refuses both.
    # No gate accepts them; only isolation-proven and layering-test-passed read them.
    "isolation-proof",
    "layering",
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


def _current_stages(names):
    """Stage names as the current spelling, each shown as the path stage it maps
    to (ADR-092). A stage renamed since main is the same stage, so a spelling
    change alone is not a change of when a guardrail is checked. `specify` and
    `build` are v1 names too, so only a v1 list is renamed."""
    import yaml

    sys.path.insert(0, str(REPO_ROOT / "cli"))
    from compass_pkg.path_stages import path_stage_of, rename_v1_stage_keys
    path = REPO_ROOT / "cli" / "migrate-map.yml"
    renames = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("stage_keys") or {}
    shown = [path_stage_of(n) or n for n in rename_v1_stage_keys(list(names), renames)]
    return sorted(set(shown))


def _in_current_stages(value):
    """`value` with every `checked_at` list spelled in the current stage names."""
    if isinstance(value, dict):
        return {k: _current_stages(v) if k == "checked_at" else _in_current_stages(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [_in_current_stages(v) for v in value]
    return value


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
    """No new check name has appeared in the checks of the check set."""
    from check_set_files import view as shipped_view
    current_content = shipped_view("guardrails.yml")
    current_checks = set(current_content.get("checks", {}).keys())

    new_checks = current_checks - _rename_checks(BASELINE_CHECKS)
    assert not new_checks, (
        f"guardrails.yml gained new checks: {new_checks}. A new check is new\n"
        "mechanism: add it here deliberately, with the change that introduces it."
    )


def test_no_new_gate_names_added():
    """No new gate name has appeared in the gates that accept evidence."""
    from check_set_files import view as shipped_view
    current_content = shipped_view("guardrails.yml")
    current_gates = set(current_content.get("gate_evidence_requirements", {}).keys())

    new_gates = current_gates - _rename_gates(BASELINE_GATES)
    assert not new_gates, (
        f"guardrails.yml gained new gates: {new_gates}. A new gate is new\n"
        "mechanism: add it here deliberately, with the change that introduces it."
    )
