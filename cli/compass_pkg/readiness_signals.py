# compass_pkg.readiness_signals - one function per readiness implementation
"""The readiness signal implementations (ADR-059), one plain function each,
named by `readiness_registry.ReadinessImpl.function`.

Each takes the run's `Context`, the signal id and its catalogue entry, and
returns a mapping with:

- `result`: `present` or `absent`, and nothing else;
- `reason`: one line that says why;
- `not_run`: for a command signal whose command did not run, why not
  (`undeclared`, `disabled`, `untrusted`, `budget` or `no-checkout`), else
  None;
- `fix`: for an absent signal, `{change, file}`: the one change that makes it
  present and the file that change touches.

No implementation opens a network connection or reads outside the
repository. The command signals read only what `readiness_run` reported
about the command the project declared.
"""
# DEPENDENCY: standard library (dataclasses, json, os); compass_pkg.project_settings.
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from compass_pkg import project_settings

CLEAN = "in a clean checkout of HEAD"
NO_IGNORED = "which holds no ignored or uncommitted file"
AGENT_FILES = ("AGENTS.md", "CLAUDE.md")
CODEOWNERS_FILES = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS", ".gitlab/CODEOWNERS")
PRE_COMMIT_FILES = (".pre-commit-config.yaml", ".pre-commit-config.yml", "lefthook.yml",
                    "lefthook.yaml", ".lefthook.yml", ".husky/pre-commit")


@dataclass
class Context:
    """What the signals of one run share. `outcomes` maps a command signal's
    id to its `readiness_run.Outcome`; `not_run` maps one whose command did
    not run to `(kind, reason)`."""
    root: str
    outcomes: dict = field(default_factory=dict)
    not_run: dict = field(default_factory=dict)

    @property
    def settings_file(self):
        return project_settings.settings_file(self.root)


def _present(reason, **extra):
    return {"result": "present", "reason": reason, "not_run": None, **extra}


def _absent(reason, change, file, not_run=None, **extra):
    return {"result": "absent", "reason": reason, "not_run": not_run,
            "fix": {"change": change, "file": file}, **extra}


def planned_command(root, entry):
    """`(key, command text or None, own limit in seconds or None)` for a
    command signal's catalogue entry."""
    params = entry.get("params") or {}
    if entry.get("impl") == "tests-under-limit":
        key = params.get("command") or "test_command"
        return key, project_settings.project_text(root, key), \
            float(params.get("limit_seconds") or 120)
    key = params.get("key")
    return key, project_settings.project_text(root, key), None


def _exists(root, names):
    return next((name for name in names if os.path.isfile(os.path.join(root, name))), None)


def agent_instructions_present(ctx, signal_id, entry):
    found = _exists(ctx.root, AGENT_FILES)
    if found:
        return _present(f"{found} is at the repository root")
    return _absent("no AGENTS.md or CLAUDE.md at the repository root",
                   "add an agent instructions file at the repository root", "AGENTS.md")


def codeowners_present(ctx, signal_id, entry):
    found = _exists(ctx.root, CODEOWNERS_FILES)
    if found:
        return _present(f"{found} names who reviews changes")
    return _absent("no CODEOWNERS file at the root, .github/, docs/ or .gitlab/",
                   "add a CODEOWNERS file that names who reviews changes", "CODEOWNERS")


def pre_commit_hooks_present(ctx, signal_id, entry):
    found = _exists(ctx.root, PRE_COMMIT_FILES)
    if found:
        return _present(f"{found} configures pre-commit hooks")
    return _absent("no pre-commit hook configuration (.pre-commit-config.yaml, lefthook.yml "
                   "or .husky/pre-commit)", "add a pre-commit hook configuration",
                   ".pre-commit-config.yaml")


def project_declaration(ctx, signal_id, entry):
    key = (entry.get("params") or {}).get("key")
    value = project_settings.project_text(ctx.root, key)
    if value:
        return _present(f"project.{key} declares: {value.strip().splitlines()[0]}")
    return _absent(f"not declared - set project.{key} in {ctx.settings_file}",
                   f"declare project.{key}", ctx.settings_file)


def _green_records(evidence):
    """`{scenario: [record, ...]}` for an issue's green records, oldest first."""
    found = {}
    for name in sorted(os.listdir(evidence)):
        if not (name.startswith("green") and name.endswith(".json")):
            continue
        try:
            with open(os.path.join(evidence, name), encoding="utf-8") as handle:
                record = json.load(handle)
        except (OSError, ValueError):
            continue
        if isinstance(record, dict):
            found.setdefault(str(record.get("scenario") or "(no scenario)"), []).append(record)
    for records in found.values():
        records.sort(key=lambda r: str(r.get("timestamp") or ""))
    return found


def no_flaky_records(ctx, signal_id, entry):
    work = os.path.join(ctx.root, ".compass", "work")
    issues = sorted(os.listdir(work)) if os.path.isdir(work) else []
    for issue in issues:
        evidence = os.path.join(work, issue, "evidence")
        if not os.path.isdir(evidence):
            continue
        for scenario, records in sorted(_green_records(evidence).items()):
            # `tdd-green` keeps one record per scenario, so two seldom
            # disagree. A green record marked `rerun_without_change` is the
            # other sign: the same command was run again over the same tree
            # until it passed, which is how a flaky test is hidden.
            if len(records) >= 2 and \
                    bool(records[-1].get("passed")) != bool(records[-2].get("passed")):
                found = "its last two green records disagree"
            elif any(r.get("rerun_without_change") is True for r in records):
                found = "a green record was re-run with no change until it passed"
            else:
                continue
            return _absent(f"issue {issue}, scenario {scenario}: {found}",
                           f"fix the flaky test behind {scenario} and record a clean green",
                           f".compass/work/{issue}/evidence/")
    return _present("no scenario's recorded test results disagree or were re-run "
                    "without a change")


def _not_run(ctx, signal_id, key):
    kind, reason = ctx.not_run[signal_id]
    if kind == "undeclared":
        return _absent(reason, f"declare project.{key}", ctx.settings_file, not_run=kind)
    if kind == "disabled":
        return _absent(reason, "set allow_project_commands: true", ctx.settings_file,
                       not_run=kind)
    if kind == "no-checkout":
        return _absent(reason, "commit the project, then run compass readiness again",
                       "the repository's first commit", not_run=kind)
    return _absent(reason, f"run compass readiness where the contribution is trusted, so "
                   f"{key} can run", "the CI job that runs compass readiness", not_run=kind)


#: The reason of a command the shared time budget stopped.
OVER_BUDGET = "ran over the time limit"


#: The reason of a command the budget ended before it began.
NOT_STARTED = "not run: the time limit was reached"


def _over_budget(ctx, key, outcome, extra):
    change = (f"make the project commands finish sooner, so {key} fits the readiness "
              f"time budget")
    if outcome.status == "not-started":
        return _absent(NOT_STARTED, change, ctx.settings_file, not_run="budget", **extra)
    return _absent(OVER_BUDGET, change, ctx.settings_file, **extra)


def _failed(outcome):
    last = next((line.strip() for line in reversed(outcome.output_tail.splitlines())
                 if line.strip()), "")
    said = f"; its last line: {last}" if last else ""
    return (f"{outcome.key} exited {outcome.exit_code} {CLEAN}, {NO_IGNORED}{said}")


def project_command_succeeds(ctx, signal_id, entry):
    key = (entry.get("params") or {}).get("key")
    if signal_id in ctx.not_run:
        return _not_run(ctx, signal_id, key)
    outcome = ctx.outcomes[signal_id]
    extra = {"key": key, "command": outcome.command}
    if outcome.status == "passed":
        return _present(f"{key} exited 0 {CLEAN}", **extra)
    if outcome.status in ("over-budget", "not-started"):
        return _over_budget(ctx, key, outcome, extra)
    return _absent(_failed(outcome), f"make {key} exit 0 {CLEAN}",
                   f"the files {key} reports on", **extra)


def tests_under_limit(ctx, signal_id, entry):
    key = (entry.get("params") or {}).get("command") or "test_command"
    if signal_id in ctx.not_run:
        return _not_run(ctx, signal_id, key)
    outcome = ctx.outcomes[signal_id]
    extra = {"key": key, "command": outcome.command,
             "duration_seconds": outcome.duration_seconds}
    if outcome.status == "passed":
        return _present(f"{key} passed in {outcome.duration_seconds} seconds {CLEAN}", **extra)
    if outcome.status in ("over-budget", "not-started"):
        return _over_budget(ctx, key, outcome, extra)
    if outcome.status == "over-limit":
        limit = _limit_words((entry.get("params") or {}).get("limit_seconds") or 120)
        return _absent(f"over {limit}", f"make {key} finish within {limit}, or set this "
                       f"signal's command to test_micro_command in a project layer",
                       ctx.settings_file, **extra)
    return _absent(_failed(outcome), f"make {key} pass {CLEAN}",
                   f"the tests {key} runs", **extra)


def _limit_words(limit_seconds):
    """"two minutes" for the shipped limit, else the seconds."""
    seconds = float(limit_seconds)
    return "two minutes" if seconds == 120 else f"{seconds:g} seconds"
