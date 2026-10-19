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
# DEPENDENCY: standard library (dataclasses, typing) and the check
# implementations in this package; no third-party code of its own.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from compass_pkg.artifact_status import _check_artifacts_approved
from compass_pkg.binding import _check_evidence_matches_tree
from compass_pkg.borrowed_docs import _check_borrowed_documents_answered
from compass_pkg.checks import (
    _check_backfills_paid, _check_changed_code_traces, _check_claim_traces,
    _check_coherence_check_passes, _check_command_passes,
    _check_declared_tests_resolve, _check_dod_evidence_typed,
    _check_evidence_identity_matches, _check_gate_evidence,
    _check_human_approval, _check_no_trusted_rerun,
    _check_scenario_has_id_and_intent, _check_scenarios_are_executable,
    _check_scenarios_have_tests, _check_spike_conclusion_present,
    _check_spike_no_production_changes, _check_suite_passed)
from compass_pkg.design_size import _check_design_within_word_ceiling
from compass_pkg.landed_by import _check_landed_by_resolves
from compass_pkg.multiagent_check import _check_multiagent_run_recorded
from compass_pkg.readiness_registry import READINESS  # noqa: F401  (re-exported)
from compass_pkg.render_check_entry import _check_rendered_blocks_current
from compass_pkg.section_checks import _check_contracts_declared, _check_nfr_rows_resolved

CORPUS_ROOT = "tests/fixtures/impls"
TIGHTER = ("higher", "lower", "none")


@dataclass(frozen=True)
class CheckImpl:
    name: str
    fn: Callable
    version: str = "1.0.0"
    # Parameter name -> type name. Empty for a check that takes none.
    params_spec: dict = field(default_factory=dict)
    # Parameter name -> `higher`, `lower` or `none` (ADR-037). A missing
    # parameter means `none`, which makes any change to it incomparable.
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
    _entry("suite-passed", _check_suite_passed),
    _entry("changed-code-traces-to-scenario", _check_changed_code_traces),
    _entry("scenario-has-id-and-intent", _check_scenario_has_id_and_intent),
    _entry("claim-traces-to-scenario", _check_claim_traces),
    _entry("landed-by-resolves", _check_landed_by_resolves),
    _entry("gate-evidence-present", _check_gate_evidence),
    # 2.0.0: reads the manifest's item records, never the page (ADR-038: its verdict on a
# page with a ticked box and no record changed from pass to fail).
    _entry("dod-evidence-typed", _check_dod_evidence_typed, version="2.0.0"),
    # 1.1.0: counts only an approval given for guardrail `G5`, with the earlier rule as
    # the floor of a landed issue; the corpus verdicts hold, so the major stays (ADR-066).
    # 1.2.0: a record an `approval-withdrawal` names no longer counts while the issue is
    # in flight; the landed floor and the corpus verdicts hold (ADR-069 decision 6).
    _entry("human-approval-present", _check_human_approval, version="1.2.0"),
    _entry("backfills-paid", _check_backfills_paid),
    _entry("spike-conclusion-present", _check_spike_conclusion_present),
    _entry("spike-no-production-changes", _check_spike_no_production_changes),
    _entry("consistency-check-passes", _check_coherence_check_passes),
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
    _entry("evidence-matches-tree", _check_evidence_matches_tree),
    _entry("rendered-blocks-current", _check_rendered_blocks_current),
    _entry("borrowed-documents-answered", _check_borrowed_documents_answered),
    # 1.1.0: accepts a single-unit record, which only a map registered with
    # `units: 1` writes; no stored record has one, so the corpus verdicts hold (ADR-071).
    _entry("multiagent-run-recorded", _check_multiagent_run_recorded, version="1.1.0"),
    _entry("artifacts-approved", _check_artifacts_approved),
    _entry("nfr-rows-resolved", _check_nfr_rows_resolved),
    # The trigger patterns are declared data a project layer can extend (ADR-033);
    # a list has no order to compare, so any change to one needs a waiver.
    _entry("contracts-declared", _check_contracts_declared,
           params_spec={"trigger_paths": "list", "trigger_contents": "list"},
           tighter={"trigger_paths": "none", "trigger_contents": "none"}),
    # A lower factor refuses more designs, so lowering it tightens the check.
    _entry("design-within-word-ceiling", _check_design_within_word_ceiling,
           params_spec={"factor": "number"}, tighter={"factor": "lower"}),
)

REGISTRY: dict[str, CheckImpl] = {e.name: e for e in _ENTRIES}


@dataclass(frozen=True)
class RemovedCheck:
    """A check id a release removed. An issue stored before the release can still
    list it in a stored generation (ADR-036 judges an issue by what it was
    assessed against), so `compass check` reports it as nothing to check, names
    the release and the check that replaced it, and runs the replacement."""
    removed_in: str
    replaced_by: str

    @property
    def detail(self) -> str:
        return ("nothing to check - this check was removed in %s; %s runs in its place"
                % (self.removed_in, self.replaced_by))


#: The framework-owned table of removed check ids. It is not configurable.
REMOVED: dict[str, RemovedCheck] = {
    "dashboard-current": RemovedCheck("7.0.0", "rendered-blocks-current"),
}

# `READINESS` (imported above) holds the readiness signal implementations
# (ADR-059). They are not checks: they are in neither `REGISTRY` nor `CHECK_FNS`,
# so `compass check` cannot run one.

# Derived, so a check cannot be run without being registered.
CHECK_FNS: dict[str, Callable] = {n: e.fn for n, e in REGISTRY.items()}


def installed_version(impl: str) -> Optional[str]:
    entry = REGISTRY.get(impl)
    return entry.version if entry else None


def installed_major(impl: str) -> Optional[int]:
    entry = REGISTRY.get(impl)
    return entry.major if entry else None
