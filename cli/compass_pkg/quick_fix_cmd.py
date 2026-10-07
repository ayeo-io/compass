#!/usr/bin/env python3
# =============================================================================
# compass_pkg.quick_fix_cmd - `compass quick-fix start` and
# `compass quick-fix finish`
# =============================================================================
# A B6 comparison session spent 19 to 22 model calls on a quick fix, each
# re-reading the whole context, against 5 to 6 for the same change done the
# R1 way. Most of the extra calls were mechanical steps an agent
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
import hashlib
import io
import json
import os
import re
import subprocess
import textwrap

from compass_pkg.binding import ids_for
from compass_pkg.check_cmd import cmd_check
from compass_pkg import project_settings
from compass_pkg.core import (
    CompassError, _WHEN_KEY_MAP, _one_segment, canonical_shape, display_shape,
    display_stage, docs_dir, find_governance, find_upwards, reading_matches,
    load_manifest, now_iso, load_yaml, manifest_path, resolve_issue_dir, save_manifest,
)
from compass_pkg.dashboard import cmd_issue_artifact
from compass_pkg.init_cmd import ensure_initialised, resolve_project_root
from compass_pkg.manifest import (
    cmd_changed_file_add, cmd_evidence_add, cmd_gate_pass, cmd_land_commit,
    cmd_scenario_add,
)
from compass_pkg.routing import cmd_route_evaluate, evaluate_route
from compass_pkg.start_state import (  # noqa: F401
    _GENERATED_DIRS, _STATE_PATHS, _git_changed_paths, _is_generated,
    _is_issue_state, _record_path, _tracked_paths, changed_since_start)
from compass_pkg.tdd import (_acceptance_state, _neutralise_coverage,
                              _red_record_for, _run_test, cmd_acceptance_record,
                              cmd_tdd_green)
from compass_pkg.terminal import say

#: The three gates a quick fix ever clears (route_shapes.quick-fix.gates in
#: governance/routing-policy.yml). `finish` refuses if any OTHER gate on the
#: issue is still pending - that is heavier work than a quick fix earns.
THREE_GATES = ("verify.correctness", "verify.governance",
              "verify.traceability")

#: The fixed reason a collapsed or skipped stage carries on the quick-fix
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
    st.add_argument("--labels", default="", metavar="TAG[,TAG...]",
                    help="domain tags the change touches, comma-separated - "
                         "auth, payments, personal-data or migrations bring "
                         "the human sign-off (default: none)")
    st.add_argument("--intent", required=True,
                    help="the intent sentence this quick fix serves (recorded as INT-1)")
    st.add_argument("--scenario", required=True,
                    help="the one Given/When/Then scenario that is the spec")
    st.add_argument("--scenario-id", default="TRC-001",
                    help="scenario id (default: TRC-001)")
    st.add_argument("--test", action="append", required=True,
                    help="test node id that exercises the scenario (repeatable, at least one)")
    st.add_argument("--raised-by", metavar="SLUG",
                    help="the issue this was found in")
    st.add_argument("--found-at", metavar="WHERE",
                    help="where: a stage, review, ci or after-landing")
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
                          scenario_id, scenario_text, ledger, advice=()):
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
    if advice:
        # Advisory strategies: they never block, so the record is the only
        # place a session meets them.
        lines += ["", "## Advice", ""]
        for s in advice:
            rationale = " ".join(str(s.get("rationale", "")).split()).rstrip(".")
            lines.append(f"- {s.get('strategy', '?')}: {rationale} "
                         f"({s.get('id', '?')})")
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


_LABEL = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def _split_labels(value):
    """The comma-separated --labels value as a list of domain tags, each
    lowercase words joined by hyphens. The policy's floors and the sign-off
    guardrail match tags exactly, so only `auth`, `payments`,
    `personal-data` and `migrations` bring the sign-off; a well-formed
    synonym such as `pii` passes this check and brings nothing."""
    labels = [t.strip() for t in (value or "").split(",") if t.strip()]
    for tag in labels:
        if not _LABEL.fullmatch(tag):
            raise CompassError(
                f"compass quick-fix start: --labels: {tag!r} is not a label - "
                f"use lowercase words joined by hyphens, e.g. auth or "
                f"personal-data.")
    return labels


def _quick_fix_blockers(readings, task):
    """Why the assessment is not a quick fix, read from the policy's own
    quick-fix shape through the evaluator's matching, so a session can act
    on the reason instead of stopping to ask. Every line stays under the
    terminal's 100-character cut, or the instruction at its end is lost."""
    policy = load_yaml(os.path.join(find_governance(), "routing-policy.yml"))
    shapes = (policy.get("routing_strategies") or {}).get("default_shapes") or []
    shape = next((s for s in shapes
                  if canonical_shape(s.get("lean_toward")) == "quick-fix"), None)
    lines = []
    for key, allowed in ((shape or {}).get("when") or {}).items():
        if reading_matches({key: allowed}, readings):
            continue
        name = _WHEN_KEY_MAP.get(key, key)
        if name == "labels_any":
            name = "labels"
        allowed = allowed if isinstance(allowed, list) else [allowed]
        lines.append(f"blocked: {name} is {readings.get(name) or 'not given'}; "
                     f"the quick fix needs {' or '.join(str(a) for a in allowed)}")
    for rule in task.get("policy_rules_fired") or []:
        if rule.get("id"):
            why = rule.get("rationale") or "no reason recorded"
            tag = f"({rule['id']}, {rule.get('kind', 'rule')})"
            wrapped = textwrap.wrap(why, width=96, break_on_hyphens=False)
            if len(wrapped[-1]) + 1 + len(tag) <= 96:
                wrapped[-1] += " " + tag
            else:
                wrapped.append(tag)
            lines += wrapped
    return lines


def cmd_quick_fix_start(args):
    slug = _one_segment(args.slug, "compass quick-fix start")
    risk_v, risk_r = _split_required(args.risk, "risk")
    fam_v, fam_r = _split_required(args.familiarity, "familiarity")
    size_v, size_r = _split_required(args.size, "size")
    goal_v, goal_r = _split_optional(args.goal)
    role_v, role_r = _split_optional(args.role)

    readings = {
        "risk": risk_v, "familiarity": fam_v, "size": size_v,
        "goal": goal_v, "role": role_v, "labels": _split_labels(args.labels),
    }

    # Before writing anything: the evaluator runs on the values in memory,
    # so an unknown value is refused with the dimension named (QFO-3), the
    # same message `compass approach evaluate` would give, before there is
    # a manifest to write it into.
    gov = find_governance()
    policy = load_yaml(os.path.join(gov, "routing-policy.yml"))
    from compass_pkg.core import load_autonomy
    advice = (evaluate_route(readings, policy, load_autonomy())
              .get("applicable_strategies") or [])

    # The title reaches the living spec at ship; refuse it now, before
    # anything is written, if a check on the spec would refuse it there.
    from compass_pkg.manifest import slug_problem, title_problem
    problem = title_problem(resolve_project_root(), args.scenario)
    if problem:
        raise CompassError(f"compass quick-fix start: scenario title refused: {problem}")
    problem = slug_problem(resolve_project_root(), slug)
    if problem:
        raise CompassError(f"compass quick-fix start: issue slug '{slug}' refused: {problem}")

    tests = list(args.test or [])

    project_root = resolve_project_root()
    created_project, _ = ensure_initialised(
        project_root, by="compass quick-fix start")
    created_dirs = [".compass/"] if created_project else []

    # The parent is checked before anything is written, so a mistyped one
    # leaves no half-made issue behind.
    from compass_pkg import lineage
    raised_by, found_at = getattr(args, "raised_by", None), getattr(args, "found_at", None)
    try:
        lineage.check(os.path.join(project_root, ".compass"), raised_by, found_at)
    except CompassError as exc:
        raise CompassError(f"compass quick-fix start: {exc}")

    task_dir = os.path.join(project_root, ".compass", "work", slug)
    if os.path.isdir(task_dir):
        raise CompassError(
            f"compass quick-fix start: '{slug}' already has an issue "
            f"directory at {task_dir} - pick a fresh slug, or continue the "
            f"existing issue with the ordinary verbs.")
    os.makedirs(task_dir, exist_ok=True)
    created = datetime.date.today().isoformat()
    start_record = {
        "schema_version": "2.0",
        "issue": slug,
        "created": created,
        "status": "active",
        "assessment": dict(readings),
        # Where the assess stage ends; finish reads the session's tokens
        # per stage from here (#375).
        "started_at": now_iso(),
    }
    if os.environ.get("CLAUDE_CODE_SESSION_ID"):
        start_record["usage"] = {"session": os.environ["CLAUDE_CODE_SESSION_ID"]}
    if raised_by:
        start_record["raised_by"] = {"issue": raised_by, "found_at": found_at}
    save_manifest(start_record, manifest_path(task_dir))
    chain_line = lineage.hint(os.path.join(project_root, ".compass"), slug)
    chain_detail = [chain_line] if chain_line else []

    _quiet_run(cmd_route_evaluate, reading=None, task=slug, write=True,
              reason=None, kind=None)

    task_dir = resolve_issue_dir(slug)
    task, _ = load_manifest(task_dir)
    approach = task.get("delivery_approach")

    if approach != "quick-fix":
        say(args,
           f"compass quick-fix start: computes to "
           f"{display_shape(approach)}, heavier than a quick fix.",
           detail=[f"issue: {slug}"] + chain_detail + [
                   "the manifest keeps the assessment and the computed approach;",
                   "no approach record and no scenario were written"]
           + _quick_fix_blockers(readings, task)
           + ["next: continue with /compass:assess, or, if a rating was wrong,",
              'correct it: /compass:assess --reassess --reason "..."'],
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
    # The session that moved the pointer works on the new issue, so the
    # pre-tool hook does not refuse its own edits as pointer-moved.
    from compass_pkg.session_lease import SESSION_ENV, record
    record(os.path.join(project_root, ".compass"),
           os.environ.get(SESSION_ENV, ""), slug)

    _write_start_state(project_root, slug)

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
        scenario_text=args.scenario, ledger=ledger, advice=advice,
    )
    with open(doc_path_abs, "w", encoding="utf-8") as fh:
        fh.write(content)

    _quiet_run(cmd_issue_artifact, task=slug, kind="delivery-approach",
              status="draft", reason=None, path=doc_path_rel)
    _quiet_run(cmd_scenario_add, task=slug, scenario_id=args.scenario_id,
              title=args.scenario, intent="INT-1", test=tests)

    from compass_pkg.decisions import settled
    decisions = settled(project_root)
    return say(
        args,
        f"compass quick-fix start: '{slug}' recorded as "
        f"{display_shape(approach)}.",
        detail=([f"created: {', '.join(created_dirs)} - tell the user"]
                if created_dirs else []) + chain_detail + (
            ["settled decisions (read any that touch this change):"]
            + [f"  {line}" for line in decisions] if decisions else []) + [
                f"record : {doc_path_rel}",
                f"next   : write the failing test, then `compass tdd-red "
                f"--scenario {args.scenario_id} -- <test command>`",
                f"then   : write the fix, then `compass quick-fix finish -m "
                f"\"<commit message>\" --no-commit -- <test command>` "
                f"(leave out --no-commit only if the user asked for a "
                f"commit)"],
        decision=True, approach=approach, record=doc_path_rel,
    )


@contextlib.contextmanager
def _at_project_root(root):
    """Change directory to the project root for the wrapped steps, and back
    afterwards (QFG-2). `git status` names paths relative to the repository
    top regardless of the caller's directory, but `git add` - run inside
    `compass check` and `compass ship-commit` - resolves paths relative to
    the process's own working directory, so tracing, checking and staging
    must run from the root even when `finish` itself was invoked from a
    subdirectory."""
    prior = os.getcwd()
    os.chdir(root)
    try:
        yield
    finally:
        os.chdir(prior)


def _reusable_green(task_dir, scenario, command, tree_ids):
    """The newest bound green already on record for `scenario`, reused
    rather than re-run, when it covers exactly what is being asked now
    (QFG-1): the same command, on the same tree, with the same files traced.
    A second `finish` with nothing new to assert must not record a rerun of
    an unchanged tree - `compass check`'s no-trusted-rerun guardrail refuses
    that, and the taught recovery ("run it again") cannot clear it.
    """
    if not command:
        return False
    try:
        task, _ = load_manifest(task_dir)
    except CompassError:
        return False
    record_path = None
    for e in (task.get("evidence") or []):
        if (isinstance(e, dict) and e.get("type") == "test-run"
                and e.get("scenario") == scenario and e.get("path")):
            record_path = e["path"]  # upserted per scenario - last one wins
    if not record_path:
        return False
    full_path = os.path.realpath(os.path.join(task_dir, record_path))
    if not full_path.startswith(os.path.realpath(task_dir) + os.sep):
        return False  # a record path outside the issue is not this issue's
    try:
        with open(full_path, "r", encoding="utf-8") as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return False
    if not isinstance(record, dict):
        return False
    # `tdd-green` stores the command after neutralising a coverage floor for
    # a recognised pytest micro-run (`tdd._neutralise_coverage`); compare
    # against the same form, or an identical command would look changed.
    # Compare the argument lists, not their joined text: `sh -c "a b"` and
    # `sh -c a b` join alike and run differently.
    wanted = _neutralise_coverage(list(command))
    if "argv" in record:
        if record.get("argv") != wanted:
            return False
    elif record.get("command") != " ".join(wanted):
        # A green written before greens carried `argv` has only the joined
        # text. Rerunning it would be flagged as a rerun, so it is reused
        # when the text matches, as it was before.
        return False
    old_tree, old_changes = record.get("tree_id"), record.get("changes_id")
    new_tree, new_changes = tree_ids.get("tree_id"), tree_ids.get("changes_id")
    if not (old_tree and old_changes and new_tree and new_changes):
        return False
    return old_tree == new_tree and old_changes == new_changes


START_STATE = "start-state.json"


def _digest(path):
    return hashlib.sha256(path.encode("utf-8")).hexdigest()


def _untracked_paths(root):
    out = subprocess.run(
        ["git", "ls-files", "-z", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, text=True, check=True).stdout
    return {p for p in out.split("\0") if p}


def _ancestors(path):
    parts = path.split("/")[:-1]
    return ["/".join(parts[:n]) + "/" for n in range(1, len(parts) + 1)]


def _write_start_state(project_root, slug):
    """Record what was already changed or untracked when the quick fix
    starts, so `finish` commits none of it unless the agent traces it.

    The record lives inside the git directory, never in the issue's
    records: a project that commits `.compass/work/` would publish it, and
    the names it holds are the ones it protects. Directories holding no
    tracked file - only untracked or ignored ones, such as a local
    `.claude/` - are recorded too, so a file written into one after
    `start` stays out. `finish` still commits a path the agent traced, or
    a test the scenario declares.
    """
    try:
        tracked_now = _tracked_paths(project_root)
        before = [p for p in _git_changed_paths(project_root)
                  if not _is_issue_state(p, tracked_now)]
        untracked = _untracked_paths(project_root)
        ignored = subprocess.run(
            ["git", "ls-files", "-z", "--others", "--ignored",
             "--exclude-standard", "--directory"], cwd=project_root,
            capture_output=True, text=True, check=True).stdout.split("\0")
        tracked = subprocess.run(
            ["git", "ls-files", "-z"], cwd=project_root, capture_output=True,
            text=True, check=True).stdout.split("\0")
        record = _record_path(project_root, slug)
    except (OSError, subprocess.CalledProcessError):
        return
    tracked_dirs = {d for t in tracked if t for d in _ancestors(t)}
    local = [p for p in list(untracked) + [i for i in ignored if i]
             if not p.startswith(".compass/")]
    local_dirs = {d for p in local for d in _ancestors(p)
                  if d not in tracked_dirs}
    os.makedirs(os.path.dirname(record), exist_ok=True)
    with open(record, "w", encoding="utf-8") as fh:
        head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"],
                              cwd=project_root, capture_output=True,
                              text=True).stdout.strip()
        # `head_at_start` is read only to warn about untraced commits; it
        # never adds a file to the change.
        json.dump({"changed_before_start": sorted(before),
                   "local_dirs_before_start": sorted(local_dirs),
                   "head_at_start": head or None},
                  fh, indent=2)
        fh.write("\n")


def _untraced_since_start(project_root, slug, traced):
    """Files committed since `start` that nobody traced. Named in the
    hand-off, never traced: a commit after `start` may be someone else's."""
    try:
        with open(_record_path(project_root, slug), encoding="utf-8") as fh:
            head = json.load(fh).get("head_at_start")
    except (OSError, ValueError, AttributeError,
            subprocess.CalledProcessError):
        return []
    if not head:
        return []
    out = subprocess.run(["git", "diff", "--name-only", "-z", head, "HEAD"],
                         cwd=project_root, capture_output=True, text=True)
    if out.returncode != 0:
        return []
    tracked = _tracked_paths(project_root)
    return sorted(p for p in out.stdout.split("\0")
                  if p and p not in traced and not _is_issue_state(p, tracked)
                  and not p.startswith("docs/compass/")
                  and not _is_generated(p))


def _start_state(task_dir, project_root, slug):
    """What `start` recorded, as (paths, directories, hashed), or None when
    there is no usable record. A record in the git directory holds plain
    paths; an older `start` wrote SHA-256 digests beside the manifest."""
    try:
        with open(_record_path(project_root, slug), encoding="utf-8") as fh:
            data = json.load(fh)
        paths = data.get("changed_before_start")
        dirs = data.get("local_dirs_before_start")
        if isinstance(paths, list) and isinstance(dirs, list):
            return set(paths), set(dirs), False
    except (OSError, ValueError, AttributeError,
            subprocess.CalledProcessError):
        pass
    try:
        with open(os.path.join(task_dir, START_STATE), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("digest") != "sha256":
        return None
    paths = data.get("changed_before_start")
    dirs = data.get("untracked_dirs_before_start")
    if not isinstance(paths, list) or not isinstance(dirs, list):
        return None
    return set(paths), set(dirs), True


def _not_the_change(paths, traced, declared_tests, state, untracked):
    """The changed paths `finish` must not commit on its own say-so, each
    with why: `before`, when it was already changed or untracked at `start`
    or sits in a directory that was wholly untracked then; `unrecorded`,
    when the issue has no start record and the path is untracked. A path
    that is traced, or is a test the scenario declares, is never refused."""
    refused = []
    for p in paths:
        if p in traced or p in declared_tests:
            continue
        if state is not None:
            before_paths, before_dirs, hashed = state
            key = _digest if hashed else (lambda x: x)
            if (key(p) in before_paths
                    or any(key(d) in before_dirs for d in _ancestors(p))):
                refused.append((p, "before"))
        elif p in untracked:
            refused.append((p, "unrecorded"))
    return refused


def _refusal(refused, scenario_id):
    groups = (
        ("before", "were already changed or untracked when this quick fix "
                   "started, or sit in a directory that was untracked then"),
        ("unrecorded", "are untracked, and this issue has no record of what "
                       "was there when it started"),
    )
    lines = ["compass quick-fix finish: no gate passed and nothing was "
             "committed. Nothing traced these changed path(s), and they"]
    for key, why in groups:
        group = [p for p, k in refused if k == key]
        if group:
            lines.append(f"{why}:")
            lines += [f"  {p}" for p in group]
    lines += [
        "",
        f"If a path belongs to this change, trace it: `compass changed-file "
        f"add <path> --scenario {scenario_id}`.",
        "Otherwise keep it out of the commit: for a tracked file, `git "
        "restore <path>` or `git stash push -- <path>`; for an untracked "
        "one, move it out of the working tree or add it to .gitignore. "
        "Then run finish again.",
    ]
    return "\n".join(lines)


def _commit_files(land_commit, root):
    """The files of the commit the issue landed in, as `ship-commit`
    recorded it: the commit it made, or HEAD when the fix was already
    committed. Read from git, not from printed text."""
    commits = [land_commit] if land_commit else []
    if not commits:
        return []
    out = subprocess.run(
        ["git", "show", "--name-only", "-z", "--format=", commits[0]],
        cwd=root, capture_output=True, text=True).stdout
    return [f for f in out.split("\0") if f.strip()]


def _shown(name):
    """A name as the reader can tell it apart: quoted when it holds a
    control character, which the terminal would otherwise show as a space."""
    return repr(name) if any(ord(c) < 32 for c in name) else name


def _commit_lines(files, slug):
    """One line per committed file outside the issue's own records, so none
    is cut off, and the records as one line with their count."""
    records = f".compass/work/{slug}/"
    own = [f for f in files if f.startswith(records)]
    rest = [f for f in files if not f.startswith(records)]
    lines = [f"commits : {_shown(f)}" for f in rest]
    if own:
        lines.append(f"commits : {records} ({len(own)} record file(s))")
    return lines


def _record_usage(task_dir, finish_started_at):
    """Write the stage boundaries finish knows and the tokens the session
    spent in each stage. Never fails the finish: whatever goes wrong is
    recorded as one of the fixed reasons in `session_usage.REASONS`."""
    from compass_pkg import session_usage
    path = manifest_path(task_dir)
    task, _ = load_manifest(task_dir)
    task["finish_started_at"] = finish_started_at
    task["committed_at"] = now_iso()
    work = os.path.dirname(task_dir)
    others = []
    for name in sorted(os.listdir(work)):
        other = manifest_path(os.path.join(work, name))
        if os.path.join(work, name) != task_dir and os.path.isfile(other):
            try:
                others.append(load_yaml(other) or {})
            except Exception:                              # noqa: BLE001
                continue
    project_root = os.path.dirname(os.path.dirname(work))
    try:
        prices = project_settings.settings(project_root).get("prices") or {}
        task["usage"] = session_usage.stage_usage(
            task_dir, task, others, prices=prices if isinstance(prices, dict) else {})
    except project_settings.SettingsConflict:
        raise
    except Exception:                                    # noqa: BLE001
        previous = task.get("usage") if isinstance(task.get("usage"), dict) else {}
        task["usage"] = {"recorded": False, "reason": "unreadable",
                         **({"session": previous["session"]}
                            if isinstance(previous.get("session"), str) else {})}
    save_manifest(task, path)


def cmd_quick_fix_finish(args):
    finish_started_at = now_iso()
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

    # The project root - the directory holding .compass/ - not necessarily
    # where the agent ran `finish` from (QFG-2). Tracing, `compass check` and
    # staging run from there; the test command runs where it was given,
    # because its own paths are relative to that directory.
    invoked_from = os.getcwd()
    project_root = find_upwards(task_dir, ".compass") or invoked_from

    with _at_project_root(project_root):
        all_paths = _git_changed_paths(project_root)
        doc_prefix = docs_dir(task_dir) + "/"
        tracked = _tracked_paths(project_root)
        production_paths = [p for p in all_paths
                            if not _is_issue_state(p, tracked)
                            and not p.startswith(doc_prefix)]
        artifact_paths = [p for p in all_paths if p.startswith(doc_prefix)]
        existing_traced = {cf.get("path") for cf in (task.get("changed_files") or [])
                           if isinstance(cf, dict)}

        # A path that was already changed or untracked when the quick fix
        # started is never committed on finish's own say-so: a local note
        # or archive would otherwise be published by the next push. Paths
        # that appeared after `start` are taken as the change's.
        declared_tests = {t.split("::", 1)[0] for sc in scenarios
                          for t in (sc.get("tests") or []) if isinstance(t, str)}
        untracked_now = _untracked_paths(project_root)
        refused = _not_the_change(
            production_paths, existing_traced, declared_tests,
            _start_state(task_dir, project_root, slug), untracked_now)
        if refused:
            raise CompassError(_refusal(refused, scenario_ids[0]))

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
    # with the command exactly as the agent gave it, in the directory the
    # agent ran `finish` from (QFG-2) - the command's own paths are relative
    # to there. A green covers the files traced when it ran, so one recorded
    # before tracing would not cover what lands; and a refused call leaves
    # its traces saved, so a later call that skipped the green would ship on
    # the earlier, failed one. A scenario whose newest green already covers
    # this exact command on this exact tree is reused instead of re-run, so
    # a second `finish` with nothing new to assert is not recorded as a
    # rerun of an unchanged tree (QFG-1).
    tree_ids_now = ids_for(task_dir)
    # One passing run on one tree is evidence for every scenario it covers,
    # so the command runs once, on the first scenario that needs it, and the
    # others record that same run. Each scenario still gets its own record
    # and its own red check.
    shared = {}

    def _shared_run():
        if not shared:
            argv = _neutralise_coverage(list(command))
            shared.update(argv=argv, tree_ids=ids_for(task_dir),
                          result=_run_test(argv))
        return shared

    for sid in scenario_ids:
        if _reusable_green(task_dir, sid, command, tree_ids_now):
            continue
        try:
            # Work with no natural red - a refactor, config, docs - declares
            # an acceptance before the change instead of recording a red.
            # The acceptance record is then this scenario's green, run on the
            # tree that lands. It must run the command that was declared: a
            # refactor's record refuses another command itself, and a
            # validation is refused here, or finish's test command would
            # stand in for the validator that was promised.
            state = _acceptance_state(task_dir)
            if state and not os.path.isfile(_red_record_for(task_dir, sid)):
                if (state.get("kind") == "validation"
                        and " ".join(command) != state.get("command")):
                    raise CompassError(
                        f"compass acceptance: this issue declared the "
                        f"validator\n  {state.get('command')}\nbut finish "
                        f"was given\n  {' '.join(command)}\nRun finish with "
                        f"the declared command after `--`.")
                _quiet_run(cmd_acceptance_record, task=slug, scenario=sid,
                           command=list(command))
                continue
            _quiet_run(cmd_tdd_green, task=slug, scenario=sid,
                       verified_by=None, command=list(command),
                       prerun=_shared_run())
        except CompassError as exc:
            raise CompassError(
                f"compass quick-fix finish: the green or acceptance for {sid} "
                f"failed - no "
                f"gate passed and nothing was committed.\n{exc}")

    with _at_project_root(project_root):
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

        # The friction the CLI can derive, as ship step 6 records it for a
        # shipped issue; without it no quick fix ever carried friction.
        # Advisory: a failure here is reported and never stops the finish.
        try:
            from compass_pkg.calibration import cmd_friction_capture
            _quiet_run(cmd_friction_capture, task=slug, internal=True, note=None)
            recorded = load_manifest(task_dir)[0].get("friction") or []
            if recorded:
                detail.append(f"friction : {len(recorded)} entr"
                              f"{'y' if len(recorded) == 1 else 'ies'} recorded "
                              f"(`compass retro --friction`)")
        except (CompassError, OSError) as exc:
            detail.append(f"friction : not captured ({exc})")

        _record_usage(task_dir, finish_started_at)

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
        ship_out, ship_code = _quiet_run(cmd_land_commit, task=slug,
                                         message=args.message,
                                         files=stage_paths)
        if ship_code != 0:
            # The commit may stand, but the issue did not land: a hook
            # changed an issue file during the commit. The start record
            # stays for the next try.
            raise CompassError(
                f"compass quick-fix finish: '{slug}' did not land.\n"
                + ship_out.strip())
        ship_tail_lines = [ln for ln in ship_out.strip().splitlines() if ln.strip()]
        ship_tail = ship_tail_lines[-1] if ship_tail_lines else "commit recorded"
        # Landing re-derives the living spec. When that fails the land still
        # stands, so ship-commit only notes it - and a note finish dropped
        # left the issue out of the spec with nothing said.
        spec_lines = [ln.strip() for ln in ship_tail_lines
                      if "living spec" in ln and ln.strip() != ship_tail.strip()]
        missing = re.search(r"missing from \.compass/work/: (.+?)\. ", ship_out)
        if missing:
            # The output layer shortens a long line, and the names are the
            # part a reader needs, so they get a short line of their own.
            spec_lines = ["living spec NOT re-derived: records missing for "
                          + missing.group(1)]
        if any("NOT re-derived" in ln or "commit failed" in ln for ln in spec_lines):
            spec_lines.append(
                "fix it: copy those issue folders into .compass/work/, then "
                "run `compass issue refresh-spec`")
        landed, _ = load_manifest(task_dir)
        committed_files = _commit_files(landed.get("land_commit"), project_root)
        traced_now = {cf.get("path") for cf in (landed.get("changed_files")
                                                or []) if isinstance(cf, dict)}
        untraced = _untraced_since_start(project_root, slug, traced_now)
        # The start record has done its work; a later issue with this slug
        # must not read it.
        try:
            os.remove(_record_path(project_root, slug))
        except (OSError, subprocess.CalledProcessError):
            pass

        return say(
            args,
            f"compass quick-fix finish: '{slug}' shipped.",
            detail=detail + _commit_lines(committed_files, slug)
            + [f"not traced: {_shown(p)} - committed since start; trace it "
               f"with `compass changed-file add` if it is this fix's"
               for p in untraced] + spec_lines + [ship_tail],
            decision=True, gates=list(THREE_GATES), evidence=evidence_ids,
            committed=True,
        )
