"""The registry of built-in check implementations.

A configuration names a deterministic check by implementation id, and the CLI
runs the implementation it ships. The id alone does not preserve behaviour,
because the code behind it can change in any release. So each implementation
is an entry here with a semantic version and a fixture corpus (ADR-038). A
test fails when a corpus verdict changes and the major version does not.

This module holds data and the lookups over it. It imports the
implementations from where they live and nothing from `check_cmd`, so
`check_cmd` can import `CHECK_FNS` from here without a cycle.

The runtime refusal of a major-version mismatch is not here. It needs the
versions a stored generation recorded, so it is in `impl_versions`; this
module only answers "installed major of impl X".
"""
# DEPENDENCY: standard library (dataclasses, typing), the check implementations in
# this package and `removed_parts` (READY_CHECKS); no third-party code of its own.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from compass_pkg.acceptance_strategy import _check_applicability_agrees
from compass_pkg.outer_loop import (
    _check_outer_loop_attempts_recorded, _check_outer_loop_recorded)
from compass_pkg.support_code import _check_acceptance_support_present
from compass_pkg.isolation import _check_isolation_proven
from compass_pkg.layering import _check_layering_test_passed
from compass_pkg.binding import _check_evidence_matches_tree
from compass_pkg.checks import (
    _check_backfills_paid, _check_changed_code_traces, _check_claim_traces,
    _check_command_passes, _check_declared_tests_resolve, _check_dod_evidence_typed,
    _check_evidence_identity_matches, _check_gate_evidence,
    _check_human_approval, _check_no_trusted_rerun,
    _check_scenario_has_id_and_intent, _check_scenarios_are_executable,
    _check_scenarios_have_tests, _check_spike_conclusion_present,
    _check_spike_no_production_changes, _check_suite_passed)
from compass_pkg.landed_by import _check_landed_by_resolves
from compass_pkg.readiness_registry import READINESS  # noqa: F401  (re-exported)
from compass_pkg.removed_parts import READY_CHECKS
from compass_pkg.section_checks import _check_nfr_rows_resolved
from compass_pkg.request_link import _check_request_recorded
from compass_pkg.ship_approval import _check_ship_approval_present

CORPUS_ROOT = "tests/fixtures/impls"
TIGHTER = ("higher", "lower", "none", "superset")


@dataclass(frozen=True)
class CheckImpl:
    name: str
    fn: Callable
    version: str = "1.0.0"
    # Parameter name -> type name. Empty for a check that takes none.
    params_spec: dict = field(default_factory=dict)
    # Parameter name -> `higher`, `lower`, `none` or `superset` (ADR-037, ADR-073).
    # A missing parameter means `none`, which makes any change to it incomparable.
    # `superset` is for a list parameter: adding entries tightens it.
    tighter: dict = field(default_factory=dict)
    # True only where the implementation runs a command the project wrote.
    executes_project_code: bool = False

    def __post_init__(self):
        # `equivalent` makes a swap between two declared choices equal. A check
        # parameter has no choices, so no check may declare it.
        for param, direction in self.tighter.items():
            if direction == "equivalent":
                raise ValueError(
                    f"check implementation '{self.name}': parameter '{param}' declares "
                    f"the direction equivalent, which needs declared choices, and a "
                    f"check parameter has none")
            # `superset` compares the entries of a list, so another type has none.
            if direction == "superset" and self.params_spec.get(param) != "list":
                raise ValueError(
                    f"check implementation '{self.name}': parameter '{param}' declares "
                    f"the direction superset, which applies to a list parameter only")

    @property
    def corpus(self) -> str:
        return f"{CORPUS_ROOT}/{self.name}"

    @property
    def major(self) -> int:
        return int(self.version.split(".")[0])


def _entry(name, fn, **kw):
    return CheckImpl(name=name, fn=fn, **kw)


_ENTRIES = (
    _entry("scenarios-have-tests", _check_scenarios_have_tests),
    _entry("scenarios-are-executable", _check_scenarios_are_executable),
    _entry("declared-tests-resolve", _check_declared_tests_resolve),
    # 1.1.0: needs a red for each scenario on an issue created from 2026-11-03; older
    # issues keep the rule they had, so the corpus verdicts hold (ADR-088).
    _entry("suite-passed", _check_suite_passed, version="1.1.0"),
    _entry("changed-code-traces-to-scenario", _check_changed_code_traces),
    _entry("scenario-has-id-and-intent", _check_scenario_has_id_and_intent),
    _entry("claim-traces-to-scenario", _check_claim_traces),
    _entry("landed-by-resolves", _check_landed_by_resolves),
    _entry("gate-evidence-present", _check_gate_evidence),
    # 2.0.0: reads the manifest's item records, never the page (ADR-038: its verdict on a
# page with a ticked box and no record changed from pass to fail).
    # 2.1.0: an issue created from 2026-11-04 is judged once every gate has passed, with
    # no verification report; older issues keep the report rule, so the corpus verdicts
    # hold (ADR-091).
    # 2.2.0: on a path issue a follow-up meets an item only when it links to a GitHub
    # issue; an issue assessed before 9.0.0 keeps every follow-up rule, so the corpus
    # verdicts hold (ADR-093).
    _entry("dod-evidence-typed", _check_dod_evidence_typed, version="2.2.0"),
    # 1.1.0: counts only an approval given for guardrail `G5`, with the earlier rule as
    # the floor of a landed issue; the corpus verdicts hold, so the major stays (ADR-066).
    # 1.2.0: a record an `approval-withdrawal` names no longer counts while the issue is
    # in flight; the landed floor and the corpus verdicts hold (ADR-069 decision 6).
    _entry("human-approval-present", _check_human_approval, version="1.2.0"),
    # 1.1.0: a path issue has nothing to check, because its follow-ups link to GitHub
    # issues; an issue assessed before 9.0.0 keeps the rule, so the corpus verdicts
    # hold (ADR-093).
    _entry("backfills-paid", _check_backfills_paid, version="1.1.0"),
    _entry("spike-conclusion-present", _check_spike_conclusion_present),
    _entry("spike-no-production-changes", _check_spike_no_production_changes),
    _entry("no-trusted-rerun", _check_no_trusted_rerun),
    # A guardrail declares exactly one of `command` (a shell string) or
    # `script` (a file run with no shell); policy lint enforces that.
    _entry("command-passes", _check_command_passes,
           params_spec={"command": "string", "script": "string",
                        "args": "list", "timeout_seconds": "integer"},
           tighter={"command": "none", "script": "none", "args": "none",
                    "timeout_seconds": "none"},
           executes_project_code=True),
    _entry("evidence-identity-matches", _check_evidence_identity_matches),
    # 1.1.0: a landed issue is judged by the SHA-256 of each file a record holds;
    # a record written before that keeps its changes_id reading, so the corpus
    # verdicts hold (ADR-089).
    _entry("evidence-matches-tree", _check_evidence_matches_tree, version="1.1.0"),
    _entry("nfr-rows-resolved", _check_nfr_rows_resolved),
    _entry("acceptance-applicability-agrees", _check_applicability_agrees),
    _entry("outer-loop-recorded", _check_outer_loop_recorded),
    _entry("acceptance-support-present", _check_acceptance_support_present),
    _entry("outer-loop-attempts-recorded", _check_outer_loop_attempts_recorded),
    _entry("isolation-proven", _check_isolation_proven),
    _entry("layering-test-passed", _check_layering_test_passed),
    # The ship approval every delivery issue owes (#355, VD-029).
    _entry("ship-approval-present", _check_ship_approval_present),
    # The request link every delivery issue owes (#356, VD-031).
    _entry("request-recorded", _check_request_recorded),
)

REGISTRY: dict[str, CheckImpl] = {e.name: e for e in _ENTRIES}


@dataclass(frozen=True)
class RemovedCheck:
    """A check id a release removed. An issue stored before the release can still
    list it in a stored generation (ADR-036 judges an issue by what it was
    assessed against), so `compass check` reports it as nothing to check, names
    the release and the check that replaced it, and runs the replacement."""
    removed_in: str
    #: None when nothing replaces the check.
    replaced_by: Optional[str]

    @property
    def detail(self) -> str:
        if self.replaced_by is None:
            return ("nothing to check - this check was removed in %s, with no "
                    "replacement" % self.removed_in)
        return ("nothing to check - this check was removed in %s; %s runs in its place"
                % (self.removed_in, self.replaced_by))


#: The framework-owned table of removed check ids. It is not configurable.
REMOVED: dict[str, RemovedCheck] = {
    # 7.0.0 replaced it with `rendered-blocks-current`, which 9.0.0 removes in turn, so
    # nothing replaces it now (ADR-091).
    "dashboard-current": RemovedCheck("7.0.0", None),
    # 9.0.0 runs each issue in one session, so no run splits into subtasks (ADR-090).
    "multiagent-run-recorded": RemovedCheck("9.0.0", None),
    # 9.0.0 removes `compass analyze`, so no consistency report is written (ADR-091).
    "consistency-check-passes": RemovedCheck("9.0.0", None),
    # 9.0.0 renders no block, issue page or project index (ADR-091).
    "rendered-blocks-current": RemovedCheck("9.0.0", None),
    # 9.0.0 keeps one issue document (ADR-091), so the checks of the others go.
    "artifacts-approved": RemovedCheck("9.0.0", None),
    "design-within-word-ceiling": RemovedCheck("9.0.0", None),
    "contracts-declared": RemovedCheck("9.0.0", None),
    "borrowed-documents-answered": RemovedCheck("9.0.0", None),
}

#: Every check id Compass no longer has: the removed checks above and the
#: Definition of Ready checks a path issue does not owe (ADR-092,
#: `removed_parts.READY_CHECKS`). `compass check` refuses a project check, a list
#: of checks in `compass.yml` or an open waiver that names one
#: (`check_cmd.deleted_check_refusal`), so a setting cannot ask for a check that
#: never runs.
DELETED_CHECKS: frozenset[str] = frozenset(REMOVED) | frozenset(READY_CHECKS)

# `READINESS` (imported above) holds the readiness signal implementations
# (ADR-059). They are not checks: they are in neither `REGISTRY` nor `CHECK_FNS`,
# so `compass check` cannot run one. Nothing runs one since 9.0.0 (ADR-093); lint
# and the classifier still read the signals a stored 8.x generation
# declares.

# Derived, so a check cannot be run without being registered.
CHECK_FNS: dict[str, Callable] = {n: e.fn for n, e in REGISTRY.items()}


def installed_version(impl: str) -> Optional[str]:
    entry = REGISTRY.get(impl)
    return entry.version if entry else None


def installed_major(impl: str) -> Optional[int]:
    entry = REGISTRY.get(impl)
    return entry.major if entry else None
