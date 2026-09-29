#!/usr/bin/env python3
# =============================================================================
# compass_pkg.quick_fix_cmd - `compass quick-fix start` and
# `compass quick-fix finish`
# =============================================================================
# A B6 comparison session spent 19 to 22 model calls on a quick fix, each
# re-reading the whole context, against 5 to 6 for the same change done the
# Superpowers way. Most of the extra calls were mechanical steps an agent
# drove one at a time: init, write the manifest from a template read in
# full, evaluate the approach, write the record, register it, trace
# changed files, check, record the check, pass three gates, devlog,
# commit. These two verbs run that same sequence, through the same code
# every other verb uses, in two calls instead of a dozen.
#
# Neither verb re-implements a record. Each step calls the handler that
# already owns it - `cmd_route_evaluate`, `cmd_issue_artifact`,
# `cmd_scenario_add`, `cmd_changed_file_add`, `cmd_evidence_add`,
# `cmd_gate_pass`, `cmd_check`, `cmd_land_commit` - in-process, with its own
# printed output captured rather than shown, so the two calls still end in
# one hand-off apiece instead of a dozen small ones.
#
# DEPENDENCY: standard library only, plus compass_pkg itself. Any PyYAML
# use happens inside the handlers this module calls (compass_pkg.core and
# friends), which already resolve the bundled copy - see
# cli/compass_pkg/__init__.py.
# =============================================================================
"""`compass quick-fix start` and `compass quick-fix finish`."""
from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import os
import subprocess

from compass_pkg.check_cmd import cmd_check
from compass_pkg.core import (
    CompassError, _one_segment, display_shape, display_stage, docs_dir,
    find_governance,
    load_manifest, load_yaml, manifest_path, resolve_issue_dir, save_manifest,
)
from compass_pkg.dashboard import cmd_issue_artifact
from compass_pkg.init_cmd import ensure_initialised, resolve_project_root
from compass_pkg.manifest import (
    cmd_changed_file_add, cmd_evidence_add, cmd_gate_pass, cmd_land_commit,
    cmd_scenario_add,
)
from compass_pkg.routing import cmd_route_evaluate, evaluate_route
from compass_pkg.tdd import cmd_tdd_green
from compass_pkg.terminal import say

#: The three gates a quick fix ever clears (route_shapes.express.gates in
#: governance/routing-policy.yml). `finish` refuses if any OTHER gate on the
#: issue is still pending - that is heavier work than a quick fix earns.
THREE_GATES = ("verify.correctness", "verify.governance",
              "verify.traceability")

#: The fixed reason a collapsed or skipped stage carries on the express
#: shape (stages: { refine: collapsed, plan: collapsed, breakdown: skipped,
#: ... }). A stage this table does not name is refused rather than printed
#: with no reason - a de-scope ledger entry with nothing to justify it is
#: not a ledger.
STAGE_DESCOPE_REASONS = {
    "refine": "the one scenario states the whole change",
    "plan": "no design decision on this size",
    "breakdown": "one subtask",
}


def register(sub, issue_arg):
    """Add `compass quick-fix start|finish` to the top-level parser."""
    p = sub.add_parser(
        "quick-fix",
        help="assess, build and ship a quick fix in two calls instead of a dozen")
    subs = p.add_subparsers(dest="subcmd", required=True)

    st = subs.add_parser(
        "start", help="assess, evaluate and record a quick fix in one call")
    st.add_argument("slug", help="issue slug - one path segment")
    st.add_argument("--risk", required=True, metavar="VALUE - REASON",
                    help="risk value and its reason, e.g. 'trivial - a one-line text change'")
    st.add_argument("--familiarity", required=True, metavar="VALUE - REASON",
                    help="familiarity value and its reason")
    st.add_argument("--size", required=True, metavar="VALUE - REASON",
                    help="size value and its reason")
    st.add_argument("--goal", default="delivery", metavar="VALUE[ - REASON]",
                    help="goal value, reason optional (default: delivery)")
    st.add_argument("--role", default="engineer", metavar="VALUE[ - REASON]",
                    help="role value, reason optional (default: engineer)")
    st.add_argument("--intent", required=True,
                    help="the intent sentence this quick fix serves (recorded as INT-1)")
    st.add_argument("--scenario", required=True,
                    help="the one Given/When/Then scenario that is the spec")
    st.add_argument("--scenario-id", default="TRC-001",
                    help="scenario id (default: TRC-001)")
    st.add_argument("--test", action="append", required=True,
                    help="test node id that exercises the scenario (repeatable, at least one)")
    st.set_defaults(func=cmd_quick_fix_start, output_kind="hand-off")

    fi = subs.add_parser(
        "finish", help="trace, check, gate and ship a quick fix in one call")
    fi.add_argument("-m", "--message", required=True, help="the commit message")
    fi.add_argument("--no-commit", action="store_true",
                    help="pass the gates and write the records, but leave the "
                         "commit to the user")
    issue_arg(fi)
    fi.add_argument("command", nargs=argparse.REMAINDER,
                    help="the test command (after --); finish records the "
                         "green with it after tracing the changed files")
    fi.set_defaults(func=cmd_quick_fix_finish, output_kind="hand-off")


def _quiet_run(fn, mode="quiet", **kwargs):
    """Call an existing verb's handler in-process, its own printed output
    captured rather than shown - so reusing the handler (never
    re-implementing its record) does not turn one hand-off into a dozen."""
    base = {"_mode": mode, "evidence_out": None, "json": False}
    base.update(kwargs)
    ns = argparse.Namespace(**base)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(ns)
    return buf.getvalue(), (code or 0)


def _split_required(raw, dim):
    """'VALUE - reason', for a dimension that must carry one (QFO-3)."""
    if raw is None or " - " not in raw:
        raise CompassError(
            f"compass quick-fix start: --{dim} needs a reason, written as "
            f"'VALUE - reason' (got {raw!r}). A value with no reason is a "
            f"guess recorded as a fact.")
    value, reason = raw.split(" - ", 1)
    value, reason = value.strip(), reason.strip()
    if not value or not reason:
        raise CompassError(
            f"compass quick-fix start: --{dim} needs both a value and a "
            f"reason either side of ' - ' (got {raw!r}).")
    return value, reason


def _split_optional(raw):
    """'VALUE' or 'VALUE - reason' - goal and role may omit the reason."""
    if raw is None:
        return None, None
    if " - " in raw:
        value, reason = raw.split(" - ", 1)
        return value.strip(), (reason.strip() or None)
    return raw.strip(), None


def _delivery_approach_md(slug, approach, dims, rules_fired, intent_text,
                          scenario_id, scenario_text, ledger):
    lines = [
        f"# Delivery approach - {slug}",
        "",
        f"**Approach:** {display_shape(approach)}",
        "",
        "## Assessment",
        "",
        "| Dimension | Value | Reason |",
        "|---|---|---|",
    ]
    for name, value, reason in dims:
        lines.append(f"| {name} | {value} | {reason or '(no reason given)'} |")
    lines += ["", "## Policy rules fired", ""]
    if rules_fired:
        for f in rules_fired:
            rationale = str(f.get("rationale", "")).rstrip().rstrip(".")
            lines.append(f"- {rationale} ({f.get('id', '?')}, {f.get('kind', '?')})")
    else:
        lines.append("none")
    lines += [
        "", "## Intent", "", f"INT-1: {intent_text}",
        "", "## Scenario", "", f"{scenario_id}: {scenario_text}",
    ]
    if ledger:
        lines += ["", "## De-scope ledger", "",
                 "| Stage | Action | Reason |", "|---|---|---|"]
        for stage, weight, reason in ledger:
            lines.append(f"| {display_stage(stage)} | {weight} | {reason} |")
    lines.append("")
    return "\n".join(lines)


def cmd_quick_fix_start(args):
    slug = _one_segment(args.slug, "compass quick-fix start")
    risk_v, risk_r = _split_required(args.risk, "risk")
    fam_v, fam_r = _split_required(args.familiarity, "familiarity")
    size_v, size_r = _split_required(args.size, "size")
    goal_v, goal_r = _split_optional(args.goal)
    role_v, role_r = _split_optional(args.role)

    readings = {
        "risk": risk_v, "familiarity": fam_v, "size": size_v,
        "goal": goal_v, "role": role_v, "labels": [],
    }

    # Before writing anything: the evaluator runs on the values in memory,
    # so an unknown value is refused with the dimension named (QFO-3), the
    # same message `compass approach evaluate` would give, before there is
    # a manifest to write it into.
    gov = find_governance()
    policy = load_yaml(os.path.join(gov, "routing-policy.yml"))
    evaluate_route(readings, policy)

    tests = list(args.test or [])

    project_root = resolve_project_root()
    created_project, _ = ensure_initialised(
        project_root, by="compass quick-fix start")
    created_dirs = [".compass/"] if created_project else []

    task_dir = os.path.join(project_root, ".compass", "work", slug)
    if os.path.isdir(task_dir):
        raise CompassError(
            f"compass quick-fix start: '{slug}' already has an issue "
            f"directory at {task_dir} - pick a fresh slug, or continue the "
            f"existing issue with the ordinary verbs.")
    os.makedirs(task_dir, exist_ok=True)
    created = datetime.date.today().isoformat()
    save_manifest({
        "schema_version": "2.0",
        "issue": slug,
        "created": created,
        "status": "active",
        "assessment": dict(readings),
    }, manifest_path(task_dir))

    _quiet_run(cmd_route_evaluate, reading=None, task=slug, write=True,
              reason=None, kind=None)

    task_dir = resolve_issue_dir(slug)
    task, _ = load_manifest(task_dir)
    approach = task.get("delivery_approach")

    if approach != "quick-fix":
        say(args,
           f"compass quick-fix start: '{slug}' computes to "
           f"{display_shape(approach)}, heavier than a quick fix. The "
           f"manifest keeps the assessment and the computed approach; "
           f"no approach record and no scenario were written.",
           detail=["next: continue with /compass:assess"],
           decision=True, approach=approach)
        return 1

    ledger = []
    for stage, weight in (task.get("stages") or {}).items():
        if weight in ("collapsed", "skipped"):
            reason = STAGE_DESCOPE_REASONS.get(stage)
            if reason is None:
                raise CompassError(
                    f"compass quick-fix start: stage '{stage}' is {weight} "
                    f"with no recorded reason - a collapsed or skipped "
                    f"stage must say why it is safe, and this one is not "
                    f"in the fixed table.")
            ledger.append((stage, weight, reason))

    # Written only once the approach is a quick fix, so a heavier result
    # leaves the pointer on whatever issue it named before.
    with open(os.path.join(project_root, ".compass", "current-task"),
             "w", encoding="utf-8") as fh:
        fh.write(slug + "\n")

    doc_dir_rel = docs_dir(task_dir)
    doc_path_rel = f"{doc_dir_rel}/delivery-approach.md"
    doc_path_abs = os.path.join(project_root, doc_path_rel)
    if not os.path.isdir(os.path.join(project_root, "docs", "compass")):
        created_dirs.append("docs/compass/")
    os.makedirs(os.path.dirname(doc_path_abs), exist_ok=True)
    content = _delivery_approach_md(
        slug=slug, approach=approach,
        dims=[("Risk", risk_v, risk_r), ("Familiarity", fam_v, fam_r),
              ("Size", size_v, size_r), ("Goal", goal_v, goal_r),
              ("Role", role_v, role_r)],
        rules_fired=task.get("policy_rules_fired") or [],
        intent_text=args.intent, scenario_id=args.scenario_id,
        scenario_text=args.scenario, ledger=ledger,
    )
    with open(doc_path_abs, "w", encoding="utf-8") as fh:
        fh.write(content)

    _quiet_run(cmd_issue_artifact, task=slug, kind="delivery-approach",
              status="draft", reason=None, path=doc_path_rel)
    _quiet_run(cmd_scenario_add, task=slug, scenario_id=args.scenario_id,
              title=args.scenario, intent="INT-1", test=tests)

    return say(
        args,
        f"compass quick-fix start: '{slug}' recorded as "
        f"{display_shape(approach)}.",
        detail=([f"created: {', '.join(created_dirs)} - tell the user"]
                if created_dirs else []) + [
                f"record : {doc_path_rel}",
                f"next   : write the failing test, then `compass tdd-red "
                f"--scenario {args.scenario_id} -- <test command>`",
                f"then   : write the fix, then `compass quick-fix finish -m "
                f"\"<commit message>\" --no-commit -- <test command>` "
                f"(leave out --no-commit only if the user asked for a "
                f"commit)"],
        decision=True, approach=approach, record=doc_path_rel,
    )


# Directories a test run or an interpreter writes, never a person. A
# project with no .gitignore for them still shows them as untracked, and
# they change between the green and the commit: traced and committed, they
# make the landed files differ from the tested ones and fail the check on
# the issue just landed.
_GENERATED_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache",
                   ".ruff_cache", ".tox", ".nox"}


def _is_generated(path):
    parts = path.split("/")
    return (any(p in _GENERATED_DIRS for p in parts[:-1])
            or path.endswith((".pyc", ".pyo")))


def _git_changed_paths(cwd):
    out = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=cwd, capture_output=True, text=True, check=True,
    ).stdout
    paths = []
    for line in out.splitlines():
        if not line.strip():
            continue
        rest = line[3:]
        if " -> " in rest:
            rest = rest.split(" -> ", 1)[-1]
        path = rest.strip().strip('"')
        if not _is_generated(path):
            paths.append(path)
    return paths


def cmd_quick_fix_finish(args):
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, _ = load_manifest(task_dir)
    slug = task.get("issue")
    command = list(getattr(args, "command", None) or [])
    if command and command[0] == "--":
        command = command[1:]

    # Every precondition is checked before anything is written (QFO-5).
    if not command:
        raise CompassError(
            "compass quick-fix finish needs the test command after `--`: "
            "`compass quick-fix finish -m <message> -- <test command>`. It "
            "records the green itself, after tracing the changed files, so "
            "the green covers exactly what lands.")

    approach = task.get("delivery_approach")
    if approach != "quick-fix":
        raise CompassError(
            f"compass quick-fix finish: '{slug}' is "
            f"{display_shape(approach)}, not quick fix - this verb only "
            f"clears the quick-fix gate set.")

    other_pending = [g.get("id") for g in (task.get("gates") or [])
                     if isinstance(g, dict) and g.get("id") not in THREE_GATES
                     and g.get("status") == "pending"]
    if other_pending:
        raise CompassError(
            f"compass quick-fix finish: gate(s) {', '.join(other_pending)} "
            f"are still pending and are not one of the three quick-fix "
            f"finish clears ({', '.join(THREE_GATES)}). Clear them first.")

    scenarios = [s for s in (task.get("scenarios") or []) if isinstance(s, dict)]
    if not scenarios:
        raise CompassError(
            f"compass quick-fix finish: '{slug}' has no scenario recorded "
            f"- quick-fix start writes one before this can run.")
    scenario_ids = [s.get("id") for s in scenarios]

    cwd = os.getcwd()
    all_paths = _git_changed_paths(cwd)
    doc_prefix = docs_dir(task_dir) + "/"
    production_paths = [p for p in all_paths
                        if not p.startswith(".compass/")
                        and not p.startswith(doc_prefix)]
    artifact_paths = [p for p in all_paths if p.startswith(doc_prefix)]
    existing_traced = {cf.get("path") for cf in (task.get("changed_files") or [])
                       if isinstance(cf, dict)}

    if len(scenarios) > 1:
        untraced = [p for p in production_paths if p not in existing_traced]
        if untraced:
            raise CompassError(
                f"compass quick-fix finish: '{slug}' has {len(scenarios)} "
                f"scenarios and {len(untraced)} changed path(s) are not "
                f"yet traced to one: {', '.join(untraced)}. Run `compass "
                f"changed-file add <path> --scenario <id>` for each, then "
                f"re-run.")
    else:
        sole = scenario_ids[0]
        for p in production_paths:
            if p not in existing_traced:
                _quiet_run(cmd_changed_file_add, task=slug, path=p,
                          scenario=[sole])
                existing_traced.add(p)

    for p in artifact_paths:
        if p not in existing_traced:
            _quiet_run(cmd_changed_file_add, task=slug, path=p,
                      scenario=list(scenario_ids))
            existing_traced.add(p)

    # The green runs here, on every call, after the files are traced and
    # with the command exactly as the agent gave it. A green covers the files
    # traced when it ran, so one recorded before tracing would not cover what
    # lands; and a refused call leaves its traces saved, so a later call that
    # skipped the green would ship on the earlier, failed one.
    for sid in scenario_ids:
        try:
            _quiet_run(cmd_tdd_green, task=slug, scenario=sid,
                       verified_by=None, command=list(command))
        except CompassError as exc:
            raise CompassError(
                f"compass quick-fix finish: the green for {sid} failed - no "
                f"gate passed and nothing was committed.\n{exc}")

    evidence_path_rel = "evidence/check-output.txt"
    evidence_path_abs = os.path.join(task_dir, evidence_path_rel)
    check_out, check_code = _quiet_run(
        cmd_check, mode="summary", task=slug, evidence_out=evidence_path_abs)
    if check_code != 0:
        raise CompassError(
            f"compass quick-fix finish: `compass check` failed - no gate "
            f"passed and nothing was committed. Full output: "
            f"{evidence_path_abs}\n{check_out.strip()[-1500:]}")

    task, _ = load_manifest(task_dir)
    existing_ids = {e.get("id") for e in (task.get("evidence") or [])
                    if isinstance(e, dict)}
    n = 1
    while f"EV-CHECK-{n}" in existing_ids:
        n += 1
    check_ev_id = f"EV-CHECK-{n}"
    _quiet_run(cmd_evidence_add, task=slug, evidence_id=check_ev_id,
              type="command-output", path=evidence_path_rel, scenario=None)

    task, _ = load_manifest(task_dir)
    correctness_ids = sorted({
        e.get("id") for e in (task.get("evidence") or [])
        if isinstance(e, dict) and e.get("type") == "test-run"
        and e.get("scenario") in scenario_ids
    })
    _quiet_run(cmd_gate_pass, task=slug, gate_id="verify.correctness",
              evidence=correctness_ids)
    _quiet_run(cmd_gate_pass, task=slug, gate_id="verify.governance",
              evidence=[check_ev_id])
    _quiet_run(cmd_gate_pass, task=slug, gate_id="verify.traceability",
              evidence=[check_ev_id])

    devlog_path = os.path.join(task_dir, "devlog.md")
    if not os.path.isfile(devlog_path):
        with open(devlog_path, "w", encoding="utf-8") as fh:
            fh.write(f"# Devlog - {slug}\n\n")
    evidence_ids = correctness_ids + [check_ev_id]
    message_first_line = (args.message or "").splitlines()[0] if args.message else ""
    with open(devlog_path, "a", encoding="utf-8") as fh:
        fh.write(f"- {datetime.date.today().isoformat()}: "
                f"{message_first_line} (evidence: {', '.join(evidence_ids)})\n")

    detail = [f"gates    : {', '.join(THREE_GATES)} -> pass",
              f"evidence : {', '.join(evidence_ids)}"]

    # A commit is the user's to ask for. With --no-commit the gates and
    # records are complete and the change is left in the working tree.
    if getattr(args, "no_commit", False):
        return say(
            args,
            f"compass quick-fix finish: '{slug}' checked, not committed.",
            detail=detail + [
                f"commit   : when asked, `compass ship-commit --issue {slug} "
                f"-m \"<message>\"` after staging the traced files"],
            decision=True, gates=list(THREE_GATES), evidence=evidence_ids,
            committed=False,
        )

    stage_paths = sorted(set(production_paths) | set(artifact_paths)
                         | {f".compass/work/{slug}"})
    ship_out, _ = _quiet_run(cmd_land_commit, task=slug, message=args.message,
                             files=stage_paths)
    ship_tail_lines = [ln for ln in ship_out.strip().splitlines() if ln.strip()]
    ship_tail = ship_tail_lines[-1] if ship_tail_lines else "commit recorded"

    return say(
        args,
        f"compass quick-fix finish: '{slug}' shipped.",
        detail=detail + [ship_tail],
        decision=True, gates=list(THREE_GATES), evidence=evidence_ids,
        committed=True,
    )
