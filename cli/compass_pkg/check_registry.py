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
versions a stored generation recorded, so it comes with that increment; this
module only answers "installed major of impl X".
"""
# DEPENDENCY: standard library (dataclasses, typing) and the check
# implementations in this package; no third-party code of its own.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

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
from compass_pkg.dashboard import _check_dashboard_current
from compass_pkg.landed_by import _check_landed_by_resolves
from compass_pkg.multiagent_check import _check_multiagent_run_recorded

CORPUS_ROOT = "tests/fixtures/check-corpus"
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
    _entry("dod-evidence-typed", _check_dod_evidence_typed),
    _entry("human-approval-present", _check_human_approval),
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
    _entry("dashboard-current", _check_dashboard_current),
    _entry("borrowed-documents-answered", _check_borrowed_documents_answered),
    _entry("multiagent-run-recorded", _check_multiagent_run_recorded),
)

REGISTRY: dict[str, CheckImpl] = {e.name: e for e in _ENTRIES}

# Derived, so a check cannot be run without being registered.
CHECK_FNS: dict[str, Callable] = {n: e.fn for n, e in REGISTRY.items()}


def installed_version(impl: str) -> Optional[str]:
    entry = REGISTRY.get(impl)
    return entry.version if entry else None


def installed_major(impl: str) -> Optional[int]:
    entry = REGISTRY.get(impl)
    return entry.major if entry else None
