#!/usr/bin/env python3
# =============================================================================
# compass_pkg.check_cmd - `compass check` and its output
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library.
# =============================================================================

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

# --- dependency check --------------------------------------------------------
# cli/compass_pkg/__init__.py already checked that the bundled copy resolves,
# or exited 3 naming the absolute path it checked, before this module's own
# code runs, so this is never anything but a normal import.
import yaml


import re as _re


import fnmatch
import re as _re
from compass_pkg.core import CHECK_NAME_MAP, migrate_map_section
from compass_pkg.landed_by import LANDED_BY_RELAXES, landed_by_holds, _check_landed_by_resolves
from compass_pkg.checks import NOTHING_TO_CHECK, _check_backfills_paid, _check_changed_code_traces, _check_claim_traces, _check_coherence_check_passes, _check_evidence_identity_matches, _check_command_passes, _check_declared_tests_resolve, _check_dod_evidence_typed, _check_gate_evidence, _check_human_approval, _check_no_trusted_rerun, _check_scenario_has_id_and_intent, _check_scenarios_are_executable, _check_scenarios_have_tests, _check_spike_conclusion_present, _check_spike_no_production_changes, _check_suite_passed
from compass_pkg.borrowed_docs import _check_borrowed_documents_answered
from compass_pkg.dashboard import _check_dashboard_current
from compass_pkg.binding import _check_evidence_matches_tree
from compass_pkg.multiagent_check import _check_multiagent_run_recorded
from compass_pkg.core import FRAMEWORK_ROOT, exit_for_mode, find_governance, load_mode, load_manifest, load_yaml, mode_banner, reading_matches, resolve_issue_dir



CHECK_FNS = {
    "scenarios-have-tests": _check_scenarios_have_tests,
    "scenarios-are-executable": _check_scenarios_are_executable,
    "declared-tests-resolve": _check_declared_tests_resolve,
    "suite-passed": _check_suite_passed,
    "changed-code-traces-to-scenario": _check_changed_code_traces,
    "scenario-has-id-and-intent": _check_scenario_has_id_and_intent,
    "claim-traces-to-scenario": _check_claim_traces,
    "landed-by-resolves": _check_landed_by_resolves,
    "gate-evidence-present": _check_gate_evidence,
    "dod-evidence-typed": _check_dod_evidence_typed,
    "human-approval-present": _check_human_approval,
    "backfills-paid": _check_backfills_paid,
    "spike-conclusion-present": _check_spike_conclusion_present,
    "spike-no-production-changes": _check_spike_no_production_changes,
    "consistency-check-passes": _check_coherence_check_passes,
    "no-trusted-rerun": _check_no_trusted_rerun,
    "command-passes": _check_command_passes,
    "evidence-identity-matches": _check_evidence_identity_matches,
    "evidence-matches-tree": _check_evidence_matches_tree,
    "dashboard-current": _check_dashboard_current,
    "borrowed-documents-answered": _check_borrowed_documents_answered,
    "multiagent-run-recorded": _check_multiagent_run_recorded,
}

# Per-check guidance for structured failure messages. Each entry has the
# *why it matters* and the *how to fix it* - the bits a check's own detail
# string usually does not have room for. The check returns the "what failed";
# this table gives the rest. A failure with guidance reads like support;
# a failure without reads like bureaucracy.
#
# `do` is the one-line form, shown in the default view where the full `fix`
# would not fit. It is WRITTEN OUT, never derived by cutting `fix` at its first
# sentence: a derived short form is a sentence nobody read before it shipped,
# and it would change silently whenever the long text was edited. A missing
# `do` fails the suite rather than falling back to a truncation.
CHECK_GUIDANCE = {
    "borrowed-documents-answered": {
        "why": "A threat model that lists threats and mitigates none is the Threat Modeling Manifesto's named anti-pattern, \"Admiration for the Problem\". A rollback plan nobody has run is a guess - SWEBOK requires the rollback be rehearsed before the deploy, and a guess recorded as a plan is the assertion the evidence-not-assertion guardrail rejects.",
        "fix": "In threat-model.md, give every threat either a TRC- scenario id in acceptance-criteria.md, or the words `risk accepted` and the reason. In rollback-plan.md, run the rollback against something and record what happened, when, and against what.",
        "do": "Answer each threat with a TRC- id or `risk accepted`; rehearse the rollback.",
    },
    "command-passes": {
        "why": 'A project guardrail with `check: command-passes` runs a real command - an architecture check, a linter, a scanner - and the gate is cleared by that command exiting zero, not by anyone saying it would.',
        "fix": 'Run the command the guardrail names and fix what it reports. If this project declares no such guardrail, nothing was checked and the pass is empty - declare one in governance/guardrails.yml with `check: command-passes` to make the gate mean something.',
        "do": 'Run the command the guardrail names, or declare one to make this gate real.',
    },
    "landed-by-resolves": {
        "why": 'An issue can say its work was delivered through a different issue - but only if the pointer resolves. The named issue must exist, have landed, carry a record of its own, and name this one back. Otherwise the claim is a slug that happens to exist, and the record guardrail is available to anything.',
        "fix": "Check the four conditions in turn. The slug must match a directory under .compass/work/; that issue must be `landed`; it must have scenarios of its own; and its `delivered:` list must name this issue. If the work was NOT done elsewhere, remove `landed_by:` and give this issue its own record.",
        "do": 'Fix the `landed_by:` pointer, or remove it and record this issue properly.',
    },
    "declared-tests-resolve": {
        "why": 'A scenario listing a test that is not on disk traces to nothing. The acceptance-before-code guardrail is cleared by a test that exists and runs, not by a path in a file.',
        "fix": "For each unresolved reference, correct the path in the scenario's `tests:` list in manifest.yml, or write the test it names. `pytest --collect-only <path>` tells you whether a reference resolves.",
        "do": 'Correct each `tests:` path in manifest.yml, or write the test it names.',
    },
    "evidence-identity-matches": {
        "why": 'A gate cites an evidence record by id. If the file has changed since, the gate is cleared by something other than what was reviewed - which is the difference between evidence and a filename.',
        "fix": 'Re-run whatever produced the record so it is stamped afresh (`compass tdd-green` for a test run), or point the gate at the record that actually backs it.',
        "do": 'Re-record the evidence, or point the gate at the record that backs it.',
    },
    "evidence-matches-tree": {
        "why": "A green proves a command passed on the tree it ran on. Once that tree changes, the record says nothing about the code that is about to ship - or, for a landed issue, about the commit that landed it.",
        "fix": "Re-run the suite through `compass tdd-green -- <test command>` on the tree you intend to ship, so the newest record names it. For a landed issue, the files the commit landed are not the files that were tested: check out a tree whose changed files match the landing commit, re-run the suite through `compass tdd-green`, and the newest record will name them.",
        "do": "Re-run the suite with `compass tdd-green` on the tree you ship.",
    },
    "multiagent-run-recorded": {
        "why": "A multiagent run splits into subtasks that `compass issue subtask` records. Without this check, an issue could clear every gate and land with a subtask never marked done, or one still failing its last review round, and nothing would say so.",
        "fix": "Record each subtask's progress with `compass issue subtask update`: `--status done` once it is merged, and `--round pass` once its last review passes. The check reports an empty `subtasks:` list, and names any subtask not done or without a passing last round.",
        "do": 'Record each named subtask done, with a passing round, via `compass issue subtask update`.',
    },
    "no-trusted-rerun": {
        "why": "A green recorded from a run nobody observed is an assertion wearing evidence's clothes. The tested-before-ship guardrail wants the run, not a note about it.",
        "fix": 'Re-run the test through `compass tdd-green -- <cmd>`, which runs it, confirms it passes, and records the output it saw.',
        "do": 'Re-run it through `compass tdd-green -- <your test command>`.',
    },
    "scenarios-are-executable": {
        "why": 'Scenarios are meant to be runnable acceptance criteria. This reads the record `compass bdd verify` writes; it never runs the suite itself.',
        "fix": 'Run `compass bdd verify` so the record exists, and account for any scenario it reports as unmatched. If this project has wired no BDD runner, there is nothing to check - see examples/bdd-adapters/ to opt in.',
        "do": 'Run `compass bdd verify`, or wire a runner (see examples/bdd-adapters/).',
    },
    "dashboard-current": {
        "why": "The issue's README is the page a reviewer approves from - it states which documents exist, which one is waiting on them, and what was deliberately left out. Generated from manifest.yml, so once the manifest moves it is an assertion the record contradicts, and a reviewer has no way to tell.",
        "do": 'Run `compass issue dashboard`, then re-read the page.',
        "fix": "Run `compass issue dashboard` to regenerate it, then read the page again before approving anything from it. Never hand-edit it - the next regeneration discards the edit.",
    },
    "scenarios-have-tests": {
        "why": "Every scenario must have a test that exercises it - without one, the scenario is a wish, not a checkable acceptance criterion (the acceptance-before-code guardrail). EXCEPT a `verifiable: narrative` scenario (a failure-mode playbook), which is cleared by being documented - a non-empty When/Then in acceptance-criteria.md - not by a fabricated test.",
        "do": "List at least one test under each scenario's `tests:` in manifest.yml.",
        "fix": "For an ordinary scenario, add at least one test reference to its `tests:` list in manifest.yml (or remove it). For a narrative scenario, mark it `verifiable: narrative` and give it a real When/Then body in acceptance-criteria.md - documentation is its acceptance.",
    },
    "suite-passed": {
        "why": "The tested-before-ship guardrail requires a recorded green test run.",
        "do": 'Run `compass tdd-green --scenario TRC-<id> -- <your test command>`.',
        "fix": "Run `compass tdd-green --scenario TRC-<id> -- <your test command>` - it will run the test, confirm green, and record the evidence in manifest.yml's registry.",
    },
    "changed-code-traces-to-scenario": {
        "why": "Compass requires every production change to trace back to a stated acceptance criterion (the traceability guardrail).",
        "do": 'Trace each file: `compass changed-file add <path> --scenario TRC-<id>`.',
        "fix": "Edit manifest.yml: under each `changed_files:` entry, list the scenario id(s) that drove the change. Add a new scenario if the behaviour was unspecified.",
    },
    "scenario-has-id-and-intent": {
        "why": "Each scenario needs a stable id and an intent link so claims, tests, and code can reference it.",
        "do": 'Give each scenario in manifest.yml an `id:` and an `intent:`.',
        "fix": "Add `id:` (e.g. TRC-A3) and `intent:` (the intent id from intent.md) fields to the scenario in manifest.yml.",
    },
    "claim-traces-to-scenario": {
        "why": "Public claims must trace to a scenario that backs them (traceability) - an unbacked claim is a promise the framework cannot prove.",
        "do": 'Point each claim in launch-readiness.md at a passing scenario id.',
        "fix": "Add a backing `scenario:` field to the claim in manifest.yml, or remove the claim from `claims:`.",
    },
    "gate-evidence-present": {
        "why": "The evidence-not-assertion guardrail: a gate marked pass must point at registry evidence of the right type. A mechanical gate cannot be cleared with a written note.",
        "do": 'Re-run `compass gate pass <gate> --evidence EV-<id>` with an accepted type.',
        "fix": "Add the evidence to the top-level `evidence:` registry with the correct `type:` (see governance/guardrails.yml `gate_evidence_requirements`), then reference its id under the gate's `evidence:` list.",
    },
    "human-approval-present": {
        "why": "The human-sign-off guardrail (a human signs off on the irreversible): this issue touches auth, payments, personal data, or migrations and needs a recorded approval.",
        "do": 'Record the sign-off: `compass evidence add EV-<id> --type human-approval`.',
        "fix": "Add a `human-approval` evidence entry to the registry with approver, role, scope, decision=approved, and timestamp. Then reference it from the relevant gate's evidence.",
    },
    "backfills-paid": {
        "why": "Work deferred for speed - a Hotfix follow-up or a de-scoped artifact - must be done before an issue closes. Otherwise the audit trail has a hole.",
        "do": 'Settle each owed follow-up: `compass follow-up resolve FU-<id>`.',
        "fix": "Complete each unpaid follow-up (writing the deferred artifact, promoting the reproduction scenario, etc.) and set its `status: paid` in manifest.yml.",
    },
    "spike-conclusion-present": {
        "why": "A Spike without a recorded conclusion is just untracked work - the conclusion is what makes the exploration accountable.",
        "do": 'Record the close-out: discard, graduate-to-delivery, or defer.',
        "fix": "Add a `spike-conclusion` evidence entry to the registry with `decision:` (discard | graduate-to-delivery | defer). If graduating, include `next_task:` linking the new delivery issue.",
    },
    "spike-no-production-changes": {
        "why": "A Spike's safety model is that it ships nothing - graduating to delivery must be a fresh triage, not a silent merge.",
        "do": 'Move the production edits to a delivery issue; a spike ships nothing.',
        "fix": "Empty `changed_files:` in this Spike's manifest.yml. If the finding is worth keeping, run `/compass:assess` to start a new delivery issue that owns the code under a real route.",
    },
    "dod-evidence-typed": {
        "why": "The evidence-not-assertion guardrail: the Definition of Done is a typed gate. Every unchecked DoD box must reference typed evidence or a filed follow-up - narrative notes in devlog.md do not count.",
        "do": 'Give each unchecked box an `(evidence: EV-<id>)` or `(follow-up: FU-<id>)` tag.',
        "fix": (
            "For each bare unchecked DoD item: (a) add `(evidence: EV-<id>)` "
            "inline, where EV-<id> is an entry in the issue's evidence registry "
            "with an accepted type; or (b) add `(follow-up: BF-<id>)` inline and "
            "record BF-<id> in manifest.yml follow-ups with status: owed; or (c) tick "
            "the box `[x]` if a human has actually done the work."
        ),
    },
    "consistency-check-passes": {
        "why": "Evidence, not assertion: verify.analyze requires a recorded `compass analyze` run with zero coherence findings, backed by a `consistency-check` evidence entry.",
        "do": 'Run `compass analyze` and settle what it reports.',
        "fix": "Run `compass analyze` - when verify.analyze is in the gate set it exits non-zero on findings, writes a `consistency-check` evidence record, and clears the gate only when there are zero findings. Resolve any reported orphaned scenarios, approach disagreements, or orphan claims first.",
    },
}


def summarise_counts(ran, failures, nothing_to_check=0):
    """The one-line verdict `compass check` ends on.

    Three of the default checks can clear with nothing to check - no BDD
    runner wired, no claims recorded, no project guardrails declared. Each is
    labelled honestly on its own line. Folding them into "all N passed"
    would make the count claim more than was checked. They are reported
    apart so the count never overstates.
    """
    if failures:
        return f"compass check: FAIL - {failures} of {ran} check(s) failed."
    # No denominator on a pass. "12 of 15 passed" reads as three failures at
    # a glance, and the total is not a constant anyway - `G5 A human signs off
    # on the irreversible` only runs when the work touches auth, payments,
    # personal data or migrations, so it moves between issues. A denominator
    # is the right thing to print when checks FAILED, which is the branch
    # above.
    if nothing_to_check:
        return (f"compass check: PASS - {ran - nothing_to_check} check(s) "
                f"passed, {nothing_to_check} had nothing to check.")
    return f"compass check: PASS - all {ran} check(s) passed."



# =============================================================================
# The gate verdict, under the terminal output contract
# =============================================================================
# `compass check` collects its results and prints them at the end, because
# code that has already printed cannot decide what to show. --verbose prints
# every check and its result.
# =============================================================================

class _CheckRun:
    """What a run of `compass check` found, before anything is printed."""

    def __init__(self, task_dir, task, mode):
        self.slug = os.path.basename(task_dir)
        self.approach = task.get("delivery_approach", "?")
        self.mode_banner = mode_banner(mode)
        self.rows = []       # (kind, text) in the order they were produced
        self.results = []    # (guardrail, name, passed, detail)
        self.ran = 0
        self.failures = 0
        self.nothing = 0

    def line(self, text):
        self.rows.append(("line", text))

    def guardrail(self, gid, name, skipped=None):
        self.current = gid
        self.rows.append(("guardrail", (gid, name, skipped)))

    def result(self, name, passed, detail):
        self.results.append((getattr(self, "current", "?"), name, passed, detail))
        self.rows.append(("result", (name, passed, detail)))


def _verbose_lines(run):
    """The full view: every check, its result, and the why behind each failure."""
    out = ["compass check - issue '%s' (approach: %s)" % (run.slug, run.approach),
           run.mode_banner, ""]
    for kind, payload in run.rows:
        if kind == "line":
            out.append(payload)
        elif kind == "guardrail":
            gid, name, skipped = payload
            if skipped:
                out.append("  %s %s: %s" % (gid, name, skipped))
            else:
                out.append("  %s %s" % (gid, name))
        else:
            name, passed, detail = payload
            if passed:
                out.append("    PASS %s: %s" % (name, detail))
            else:
                out.append("    FAIL %s" % name)
                out.append("         what: %s" % detail)
                g = CHECK_GUIDANCE.get(name)
                if g:
                    out.append("         why : %s" % g["why"])
                    out.append("         fix : %s" % g["fix"])
    out += ["-" * 60,
            summarise_counts(run.ran, run.failures, run.nothing)]
    return out


def _summary_lines(run):
    """The default view: the verdict, what failed, and what to do about it.

    `why` moves to --verbose. `fix` is what a person acts on; `why` is what
    convinces them it was worth acting on, and when only one fits, the one that
    changes what they do next is the one to keep.

    Every failure is NAMED even when its body is not shown - a verdict that
    says "3 checks failed" without saying which is not something a reader can
    act on, and a check name is its identifier (ADR-017).
    """
    from compass_pkg.terminal import MAX_ITEMS, _fit

    # Deduplicated by check name. Several checks are listed under more than
    # one guardrail - `scenario-has-id-and-intent` runs under both `G2` and
    # `G3` - so a failing run produces two rows with the same name and the
    # same detail. Showing one in the top three and naming it again as
    # hidden reads as the tool being confused about its own findings.
    failed, seen = [], set()
    for _g, n, p, d in run.results:
        if p or n in seen:
            continue
        seen.add(n)
        failed.append((n, d))
    # The verdict counts distinct failing checks, the same set the list below
    # uses. Two numbers that describe the same thing must come from the same
    # set, or a failure can drop out of the list with nothing saying so.
    distinct_failed = len(failed)
    distinct_ran = len({n for _g, n, _p, _d in run.results})
    # Built from the counts, not by re-parsing `summarise_counts`, whose text
    # already starts "compass check: PASS". The "nothing to check" clause is
    # carried through deliberately: a check that inspected nothing must
    # never be reported as one that checked something.
    # An issue with no computed approach has not had `compass approach
    # evaluate` run on it, so say that.
    approach = (run.approach if run.approach and run.approach != "?"
                else "no approach yet - run `compass approach evaluate --write`")
    if distinct_failed:
        verdict = "FAIL - %d of %d check(s) failed on '%s' (%s)" % (
            distinct_failed, distinct_ran, run.slug, approach)
    else:
        nothing = (", %d had nothing to check" % run.nothing) if run.nothing else ""
        verdict = "PASS - %d check(s) passed%s on '%s' (%s)" % (
            distinct_ran - run.nothing, nothing, run.slug, approach)
    out = [_fit(verdict)]

    # Keep the adoption-mode banner in the default view. Without it, an
    # advisory run shows FAIL and exits 0 with nothing to explain why. It
    # costs one line of twelve.
    if run.mode_banner and run.mode_banner.strip():
        out.append(_fit(run.mode_banner.strip()))

    # A guardrail this project's governance omits is reported here, not only
    # under --verbose.
    notices = [t for kind, t in run.rows if kind == "line" and t.strip()]
    for n in notices[:MAX_ITEMS]:
        out.append(_fit(n.strip(), "  "))
    if len(notices) > MAX_ITEMS:
        out.append(_fit("... and %d more notice(s) - run with --verbose"
                        % (len(notices) - MAX_ITEMS), "  "))

    if not failed:
        return out

    out.append("")
    for name, detail in failed[:MAX_ITEMS]:
        out.append(_fit("%s: %s" % (name, detail), "FAIL "))
        g = CHECK_GUIDANCE.get(name)
        if g and g.get("do"):
            out.append(_fit(g["do"], "     fix: "))
    hidden = failed[MAX_ITEMS:]  # drawn from the same set the verdict counts
    if hidden:
        out.append(_fit("... and %d more (%s) - run with --verbose"
                        % (len(hidden), ", ".join(n for n, _ in hidden))))
    return out


def _emit_check(run, args):
    """Render the run in the mode the caller asked for."""
    from compass_pkg.terminal import mark_handled, resolve_mode

    mark_handled()
    mode = resolve_mode(args)
    if mode == "json":
        print(json.dumps({
            "issue": run.slug, "approach": run.approach,
            "ran": run.ran, "failed": run.failures,
            "nothing_to_check": run.nothing,
            "notices": [t.strip() for kind, t in run.rows
                        if kind == "line" and t.strip()],
            "checks": [{"guardrail": g, "name": n,
                        "status": ("nothing-to-check"
                                   if p is NOTHING_TO_CHECK else
                                   "pass" if p else "fail"),
                        "detail": d}
                       for g, n, p, d in run.results],
        }, indent=2))
        return
    if mode == "quiet" and not run.failures:
        return
    lines = _verbose_lines(run) if mode == "verbose" else _summary_lines(run)
    # --evidence-out writes the FULL verdict, so the summary on screen has
    # something to link to.
    out_path = getattr(args, "evidence_out", None)
    if out_path:
        from compass_pkg.terminal import write_capture

        write_capture(out_path, "\n".join(_verbose_lines(run)))
        lines = list(lines) + ["", "Full verdict written to: %s" % out_path]
    print("\n".join(lines))


def cmd_check(args):
    gov = find_governance()
    guardrails = load_yaml(os.path.join(gov, "guardrails.yml"))
    task_dir = resolve_issue_dir(args.task)
    task, _ = load_manifest(task_dir)
    readings = task.get("assessment") or {}
    mode = load_mode()

    # A spike ships nothing, so the delivery guardrails (`G1`-`G5`) do not apply.
    # It is still controlled: it must conclude, and it must not change
    # production code. On a spike, `compass check` runs `spike_guardrails`
    # from guardrails.yml instead.
    if task.get("delivery_approach") == "spike":
        spike_gs = list(guardrails.get("spike_guardrails", []))
        run = _CheckRun(task_dir, task, mode)
        if not spike_gs:
            # Report this as a failed check, not a line: the default view
            # and --json show only checks. Do not count it as a check that
            # ran, because nothing ran.
            run.guardrail("", "spike control")
            run.result("spike-guardrails-declared", False,
                       "no `spike_guardrails:` defined in guardrails.yml - "
                       "a Spike is uncontrolled")
            run.ran = run.failures = 1
            _emit_check(run, args)
            return exit_for_mode(1, mode)
        failures = 0
        ran = 0
        for g in spike_gs:
            gid = g.get("id", "?")
            run.guardrail(gid, g.get("name", ""))
            for check_name in g.get("checks", []):
                fn = CHECK_FNS.get(check_name)
                ran += 1
                if fn is None:
                    failures += 1
                    run.result(check_name, False,
                               "declared spike guardrail check has NO CLI "
                               "implementation")
                    continue
                try:
                    passed, detail = fn(task, task_dir)
                except Exception as exc:
                    passed, detail = False, f"check errored: {exc}"
                if not passed:
                    failures += 1
                run.result(check_name, passed, detail)

        # Follow-ups apply to every delivery approach, and a spike most often
        # owes one - a graduating spike leaves deferred work behind by
        # design - so the spike branch must reach the follow-up block below.
        ran += 1
        try:
            passed, detail = _check_backfills_paid(task, task_dir)
        except Exception as exc:                        # noqa: BLE001
            passed, detail = False, f"check errored: {exc}"
        run.guardrail("", "outstanding follow-ups")
        run.result("backfills-paid", passed, detail)
        if not passed:
            failures += 1

        run.ran, run.failures = ran, failures
        _emit_check(run, args)
        return exit_for_mode(failures, mode)

    all_guardrails = list(guardrails.get("defaults", [])) + list(guardrails.get("project", []))
    declared_checks = guardrails.get("checks") or {}
    failures = 0
    ran = 0
    # Checks that cleared with nothing to inspect. Counted apart so the
    # summary never reports a check that inspected nothing as something it
    # verified.
    nothing_to_check = 0
    # Reads `delivery_approach`, the live manifest key.
    run = _CheckRun(task_dir, task, mode)

    # Report a guardrail the project's file omits when it would apply to
    # this issue. Only this issue's: a full list on every run would not be
    # read, and `compass policy lint` prints the full list.
    declared_ids = {g.get("id") for g in all_guardrails}
    try:
        fw_guardrails = load_yaml(
            os.path.join(FRAMEWORK_ROOT, "governance", "guardrails.yml"))
        fw_defaults = (fw_guardrails.get("defaults") or []) if isinstance(
            fw_guardrails, dict) else []
    except Exception:                                   # noqa: BLE001
        fw_defaults = []
    for fg in fw_defaults:
        fid = fg.get("id")
        if fid in declared_ids:
            continue
        applies = fg.get("applies_when")
        if applies and not reading_matches(applies, readings):
            continue          # absent, but would not have applied here anyway
        run.line(f"  {fid} {fg.get('name', '')}: ABSENT from this project's "
                 f"governance, and it applies to this assessment - the "
                 f"framework defines it but governance/guardrails.yml does "
                 f"not. Run `compass policy lint`.")

    for g in all_guardrails:
        gid = g.get("id", "?")
        applies = g.get("applies_when")
        if applies and not reading_matches(applies, readings):
            run.guardrail(gid, g.get("name", ""),
                          skipped="not applicable for this assessment - skipped")
            continue
        run.guardrail(gid, g.get("name", ""))
        for check_name in g.get("checks", []):
            fn = CHECK_FNS.get(check_name)
            # A project that ran /compass:init before ADR-023 has its own
            # guardrails.yml naming the retired spelling. The check still
            # ships; only its name moved, so say that rather than telling the
            # author to implement a function that already exists.
            if fn is None:
                current = migrate_map_section(
                    "values", {}).get("check_name", CHECK_NAME_MAP)
                if check_name in current:
                    check_name = current[check_name]
                    fn = CHECK_FNS.get(check_name)
            ran += 1
            if fn is None:
                # A declared guardrail check with no implementation is the one
                # thing that quietly breaks the guardrail/strategy model: the
                # team believes they have a hard, blocking check, and they do
                # not. So this FAILS - loudly - rather than warning.
                failures += 1
                run.result(check_name, False,
                           "declared guardrail check has NO CLI implementation "
                           "- it cannot run, so it is not a guardrail. "
                           "Implement it in CHECK_FNS, or move the guardrail "
                           "to strategies.md.")
                continue
            # `landed_by` moves the record claim to another issue rather
            # than waiving it. Only the named checks in `LANDED_BY_RELAXES`
            # stand down, and only once the pointer has been checked in
            # full - the named issue exists, has landed, carries a record,
            # and names this one back.
            # A relaxation that fired on the field's mere presence would waive
            # the guardrail for anything that typed a slug.
            if check_name in LANDED_BY_RELAXES:
                held, why = landed_by_holds(task, task_dir)
                if held:
                    run.result(check_name, NOTHING_TO_CHECK,
                               "%s - %s" % (why, "this issue does not carry "
                                                 "its own record, and is not "
                                                 "asked to"))
                    continue

            try:
                passed, detail = fn(task, task_dir)
            except Exception as exc:  # a check must not crash the run
                passed, detail = False, f"check errored: {exc}"

            # A check may declare `blocking_when:` in guardrails.yml - an
            # assessment-scoped condition, exactly like a guardrail's
            # `applies_when:`. Below that threshold a finding is reported and
            # does not fail the run. Governance holds the condition as data;
            # this code only evaluates it, which is the mechanism side of
            # the boundary ADR-001 draws.
            blocking_when = (declared_checks.get(check_name) or {}).get(
                "blocking_when")
            if (not passed and blocking_when
                    and not reading_matches(blocking_when, readings)):
                passed = True
                detail = ("advisory for this assessment - %s. It blocks when %s."
                          % (detail, json.dumps(blocking_when)))

            if not passed:
                failures += 1
            elif passed is NOTHING_TO_CHECK:
                nothing_to_check += 1
            run.result(check_name, passed, detail)

    # follow-ups are cross-cutting - always run them
    ran += 1
    try:
        # Wrap this one too: a malformed `follow_ups:` list must not crash
        # check, receipt, rework-scan, flow --digest or ci.
        passed, detail = _check_backfills_paid(task, task_dir)
    except Exception as exc:                            # noqa: BLE001
        passed, detail = False, f"check errored: {exc}"
    run.guardrail("", "outstanding follow-ups")
    run.result("backfills-paid", passed, detail)
    if not passed:
        failures += 1

    run.ran, run.failures, run.nothing = ran, failures, nothing_to_check
    _emit_check(run, args)
    return exit_for_mode(failures, mode)
