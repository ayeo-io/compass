#!/usr/bin/env python3
# =============================================================================
# compass_pkg.quick_fix_cmd - `compass quick-fix start` and
# `compass quick-fix finish`
# =============================================================================
# A B6 comparison session spent 19 to 22 model calls on a quick fix, each
# re-reading the whole context, against 5 to 6 for the same change done the
# R1 way. Most of the extra calls were mechanical steps an agent
# drove one at a time: init, write the manifest from a template read in
# full, evaluate the approach, write the record, trace changed files, check, record the check, pass three gates, devlog,
# commit. These two verbs run that same sequence, through the same code
# every other verb uses, in two calls instead of a dozen.
#
# Neither verb re-implements a record. Each step calls the handler that
# already owns it - `cmd_route_evaluate`, `cmd_scenario_add`, `cmd_changed_file_add`, `cmd_evidence_add`,
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
from compass_pkg import candidate_client, landing
from compass_pkg.path_stages import is_path_issue
from compass_pkg.stable_ids import (
    APPROACH_DELIVERY, APPROACH_QUICK_FIX, GATE_VERIFY_CORRECTNESS, GATE_VERIFY_GOVERNANCE, GATE_VERIFY_TRACEABILITY)
from compass_pkg.core import (
    COMPASS_SCHEMA_VERSION, CompassError, WHEN_KEY_MAP, _one_segment, canonical_shape, display_shape,
    docs_dir, find_upwards,
    load_manifest, load_yaml, manifest_path, resolve_issue_dir, save_manifest,
)
from compass_pkg.init_cmd import ensure_initialised, resolve_project_root
from compass_pkg.manifest import (
    cmd_changed_file_add, cmd_evidence_add, cmd_gate_pass, cmd_land_commit,
    cmd_scenario_add,
)
from compass_pkg.routing import cmd_route_evaluate, evaluate_route
from compass_pkg.start_state import (  # noqa: F401
    _GENERATED_DIRS, _STATE_PATHS, _git_changed_paths, _is_generated,
    _is_issue_state, _record_path, _tracked_paths, changed_since_start)
from compass_pkg.tdd import (_acceptance_state, _neutralise_coverage, _run_test,
                              cmd_acceptance_record, default_loop)
from compass_pkg.tdd_green import _red_record_for, cmd_tdd_green, strategy_applies
from compass_pkg.terminal import say

#: The three gates a quick fix ever clears (route_shapes.quick-fix.gates of the
#: 8.x routing policy). `finish` refuses if any OTHER gate on the
#: issue is still pending - that is heavier work than a quick fix earns.
THREE_GATES = (GATE_VERIFY_CORRECTNESS, GATE_VERIFY_GOVERNANCE,
               GATE_VERIFY_TRACEABILITY)

def register(sub, issue_arg):
    """Add `compass quick-fix start|finish` to the top-level parser."""
    p = sub.add_parser(
        "quick-fix",
        help="start and finish a change of any size on the path, in two calls instead of a dozen")
    subs = p.add_subparsers(dest="subcmd", required=True)

    st = subs.add_parser(
        "start", help="assess and record a change and its first scenario in one call")
    st.add_argument("slug", help="issue slug - one path segment")
    # The lean path: the three ratings no longer change what the change owes,
    # so each has a default. A value given is recorded with its reason.
    st.add_argument("--risk", default="contained - not rated at start",
                    metavar="VALUE - REASON", help="risk value and its reason (optional)")
    st.add_argument("--familiarity", default="brownfield-mapped - not rated at start",
                    metavar="VALUE - REASON", help="familiarity value and its reason (optional)")
    st.add_argument("--size", default="small - not rated at start",
                    metavar="VALUE - REASON", help="size value and its reason (optional)")
    st.add_argument("--goal", default=None, metavar="VALUE - REASON",
                    help="goal value and its reason (left out: not assessed)")
    st.add_argument("--urgency", default=None, metavar="VALUE - REASON",
                    help="urgency value and its reason; 'live-defect - <reason>' is the "
                         "hotfix setting")
    st.add_argument("--labels", default="", metavar="TAG[,TAG...]",
                    help="domain tags the change touches, comma-separated - "
                         "auth, payments, personal-data or migrations bring "
                         "the human sign-off (default: none)")
    st.add_argument("--intent", required=True,
                    help="the intent sentence this change serves (recorded as INT-1)")
    st.add_argument("--scenario", default=None,
                    help="the first scenario (left out: the intent sentence)")
    st.add_argument("--scenario-id", default="TRC-001",
                    help="scenario id (default: TRC-001)")
    st.add_argument("--test", action="append",
                    help="test node id (optional: finish reads the changed test files from git)")
    st.add_argument("--expected-acceptance", dest="expected_acceptance",
                    choices=["none", "validation", "refactor"], default=None,
                    metavar="KIND", help="none, validation or refactor")
    st.add_argument("--raised-by", metavar="SLUG",
                    help="the issue this was found in")
    st.add_argument("--found-at", metavar="WHERE",
                    help="where: a stage, review, ci or after-landing")
    st.add_argument("--request", metavar="URL",
                    help="link to the request (https URL or owner/repo#N)")
    st.add_argument("--requester", metavar="NAME",
                    help="who asked (a claim, at most 100 characters)")
    st.set_defaults(func=cmd_quick_fix_start, output_kind="hand-off")

    fi = subs.add_parser(
        "finish", help="trace, check and gate a change in one call; refuses while other evidence is owed")
    fi.add_argument("-m", "--message", required=True, help="the commit message")
    fi.add_argument("--no-commit", action="store_true",
                    help="accepted and ignored: finish never commits; "
                         "`compass ship-commit` does")
    from compass_pkg.acceptance_strategy import LOOPS
    fi.add_argument("--loop", choices=LOOPS, default=None,
                    help="outer: the acceptance suite; inner: a unit test")
    fi.add_argument("--candidate", metavar="ID|local", help="outer loop: the build")
    fi.add_argument("--client", metavar="api|web|cli", help="outer loop: the interface")
    from compass_pkg.release_line import add_argument as add_release_note
    add_release_note(fi)
    issue_arg(fi)
    fi.add_argument("command", nargs=argparse.REMAINDER,
                    help="the test command (after --); finish records the "
                         "green with it after tracing the changed files")
    fi.set_defaults(func=cmd_quick_fix_finish, output_kind="hand-off")


def _quiet_run(fn, mode="quiet", answers=None, **kwargs):
    """Call an existing verb's handler in-process, its own printed output
    captured rather than shown - so reusing the handler (never
    re-implementing its record) does not turn one hand-off into a dozen.
    A dict passed as `answers` receives the handler's arguments afterwards,
    with what the handler set on them, such as `compass check`'s counts."""
    base = {"_mode": mode, "evidence_out": None, "json": False}
    base.update(kwargs)
    ns = argparse.Namespace(**base)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(ns)
    if answers is not None:
        answers.update(vars(ns))
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


def _split_optional(raw, dim):
    """`(None, None)` for a goal or urgency left out (it records no value), else
    'VALUE - reason', which must carry its reason."""
    if raw is None:
        return None, None
    return _split_required(raw, dim)


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


def _quick_fix_blockers(readings, task, task_dir=None):
    """Why the assessment is not a quick fix, read from the policy's own
    quick-fix shape through the evaluator's matching, so a session can act
    on the reason instead of stopping to ask. Every line stays under the
    terminal's 100-character cut, or the instruction at its end is lost."""
    from compass_pkg import effective
    view = effective.effective_for(task_dir)
    policy = view.evaluator_policy()
    matches = view.matches
    shapes = (policy.get("routing_strategies") or {}).get("default_shapes") or []
    shape = next((s for s in shapes
                  if canonical_shape(s.get("lean_toward")) == APPROACH_QUICK_FIX), None)
    lines = []
    for key, allowed in ((shape or {}).get("when") or {}).items():
        if matches({key: allowed}, readings):
            continue
        name = WHEN_KEY_MAP.get(key, key)
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
    goal_v, goal_r = _split_optional(args.goal, "goal")
    urgency_v, urgency_r = _split_optional(getattr(args, "urgency", None), "urgency")

    readings = {"risk": risk_v, "familiarity": fam_v, "size": size_v}
    reasons = {"risk": risk_r, "familiarity": fam_r, "size": size_r}
    if goal_v is not None:
        readings["goal"], reasons["goal"] = goal_v, goal_r
    if urgency_v is not None:
        readings["urgency"], reasons["urgency"] = urgency_v, urgency_r
    readings["labels"] = _split_labels(args.labels)
    if not args.scenario:
        args.scenario = args.intent
    # The request link is optional and never refused for being absent: the check
    # `request-recorded` and the `next:` line ask for it (#356). A malformed one is
    # refused here, before anything is written.
    from compass_pkg import request_link
    request_url, request_target, requester = request_link.parse(
        getattr(args, "request", None), getattr(args, "requester", None),
        "compass quick-fix start")

    # Before writing anything: the evaluator runs on the values in memory,
    # so an unknown value is refused with the dimension named (QFO-3), the
    # same message `compass approach evaluate` would give, before there is
    # a manifest to write it into.
    from compass_pkg import effective
    view = effective.effective_for()
    policy, autonomy = view.evaluator_policy(), view.autonomy
    advice = (evaluate_route(readings, policy, autonomy)
              .get("applicable_strategies") or [])

    # The title reaches the release line and the board; refuse it now, before
    # anything is written, if a check on the spec would refuse it there.
    from compass_pkg.manifest import title_problem
    problem = title_problem(resolve_project_root(), args.scenario)
    if problem:
        raise CompassError(f"compass quick-fix start: scenario title refused: {problem}")

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

    # One request is one issue: 5 of 12 measured sessions opened a second
    # issue for follow-on work and left it unfinished. Name the open issue, so
    # the session can add the work to it instead.
    open_issue = None
    try:
        with open(os.path.join(project_root, ".compass", "current-task"),
                  encoding="utf-8") as fh:
            pointed = fh.read().strip()
        if pointed and pointed != slug:
            from compass_pkg import status_words
            held, _ = load_manifest(os.path.join(project_root, ".compass", "work", pointed))
            if not status_words.is_closed(held):
                open_issue = pointed
    except (OSError, CompassError, ValueError):
        pass

    task_dir = os.path.join(project_root, ".compass", "work", slug)
    if os.path.isdir(task_dir):
        raise CompassError(
            f"compass quick-fix start: '{slug}' already has an issue "
            f"directory at {task_dir} - pick a fresh slug, or continue the "
            f"existing issue with the ordinary verbs.")
    os.makedirs(task_dir, exist_ok=True)
    created = datetime.date.today().isoformat()
    start_record = {
        "schema_version": COMPASS_SCHEMA_VERSION,
        "issue": slug,
        "created": created,
        "assessment": dict(readings),
        "justifications": dict(reasons),
        # A new issue's hand-offs are recorded (checkpoint_outcomes.py).
        "checkpoint_outcomes": [],
    }
    # The commit the change starts from. `finish` reads the changed files as
    # the difference from it, and proves the red on a copy of it.
    from compass_pkg import lean
    base = lean.head_commit(project_root)
    if base:
        start_record[lean.BASE_KEY] = base
    if raised_by:
        start_record["raised_by"] = {"issue": raised_by, "found_at": found_at}
    if request_target is not None:
        start_record["github"] = {"repo": request_target[0], "number": request_target[1]}
    if request_url is not None and requester is None:
        requester = "not stated at start"
    request_link.record(start_record, request_url, requester, by="compass quick-fix start")
    save_manifest(start_record, manifest_path(task_dir))
    chain_line = lineage.hint(os.path.join(project_root, ".compass"), slug)
    chain_detail = [chain_line] if chain_line else []

    try:
        _quiet_run(cmd_route_evaluate, reading=None, task=slug, write=True,
                   reason=None, kind=None,
                   expected_acceptance=getattr(args, "expected_acceptance", None))
    except CompassError:
        # This call made the folder, so a refusal (a compass.yml the lint
        # rejects, for one) takes it away, and the slug stays free.
        import shutil
        shutil.rmtree(task_dir, ignore_errors=True)
        raise

    task_dir = resolve_issue_dir(slug)
    task, _ = load_manifest(task_dir)
    approach = task.get("delivery_approach")
    # On the four-stage path every size starts here: the evidence line says what
    # the change owes, and `finish` refuses while any of it is owed (ADR-092).
    on_path = is_path_issue(task)

    # Every delivery assessment is written onto the path (ADR-092), so only a
    # spike is refused here.
    if not on_path:
        say(args,
           f"compass quick-fix start: computes to "
           f"{display_shape(approach)}, which cannot start as a quick fix.",
           detail=[f"issue: {slug}",
                   "why: a spike explores and ships nothing, so it is not on the path"]
           + chain_detail + [
                   "the manifest keeps the assessment and the computed approach;",
                   "no approach record and no scenario were written"]
           + _quick_fix_blockers(readings, task, task_dir)
           + ["next: continue with /compass:assess, or, if a rating was wrong,",
              'correct it: /compass:assess --reassess --reason "..."'],
           decision=True, approach=approach)
        return 1

    # The start record lives in the git directory, which a linked worktree
    # may not be allowed to write. It is written before the pointer moves,
    # and a failure takes this call's issue folder away, so a retry with the
    # same slug can start again.
    try:
        _write_start_state(project_root, slug)
    except OSError as exc:
        import shutil
        shutil.rmtree(task_dir, ignore_errors=True)
        where = os.path.abspath(exc.filename) if exc.filename else "the git directory"
        raise CompassError(
            f"compass quick-fix start: cannot write the start record in "
            f"{where} ({exc.strerror or exc}). "
            f"Nothing was kept. Give this session write access to that "
            f"folder, then run the same start again.") from None

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

    # The path writes no devlog (ADR-092 decision 12): the acceptance
    # criteria hold the intent and the scenario.
    from compass_pkg.path_writer import criteria_text
    doc_path_rel = docs_dir(task_dir) + "/acceptance-criteria.md"
    doc_abs = os.path.join(project_root, *doc_path_rel.split("/"))
    os.makedirs(os.path.dirname(doc_abs), exist_ok=True)
    with open(doc_abs, "w", encoding="utf-8") as fh:
        # A change that owes the Definition of Done resolves its requirement
        # rows itself; `nfr-rows-resolved` names each one until it does.
        fh.write(criteria_text(
            slug, args.intent, args.scenario_id, args.scenario,
            resolve_rows="definition-of-done" not in task["evidence_required"]))
    _quiet_run(cmd_scenario_add, task=slug, scenario_id=args.scenario_id,
              title=args.scenario, intent="INT-1", test=tests)
    from compass_pkg.decisions import settled
    decisions = settled(project_root)
    # One short hand-off: later calls resend it, so it holds only what the
    # agent acts on.
    said = say(
        args,
        f"compass quick-fix start: '{slug}' started.",
        detail=([f"created: {', '.join(created_dirs)} - tell the user"]
                if created_dirs else []) + chain_detail + (
            # Two lines, so the output layer cuts neither.
            [f"open    : '{open_issue}' is not finished; add same-request work to it:",
             f"`compass issue use {open_issue}`"]
            if open_issue else []) + (
            ["settled decisions (read any that touch this change):"]
            + [f"  {line}" for line in decisions] if decisions else []) + [
                f"scenarios: {doc_path_rel}"],
        decision=True, approach=approach, record=doc_path_rel,
    )
    from compass_pkg.next_line import announce
    return announce(args, task_dir, said)


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


def _reusable_green(task_dir, scenario, command, tree_ids, loop="inner", named=None):
    """The newest bound green already on record for `scenario`, reused
    rather than re-run, when it covers exactly what is being asked now
    (QFG-1): the same loop, command, candidate and client, on the same tree,
    with the same files traced. A second `finish` with nothing new to assert
    must not record a rerun of an unchanged tree - `compass check`'s
    no-trusted-rerun guardrail refuses that, and the taught recovery ("run it
    again") cannot clear it.

    Only a green of the loop this finish records counts. An inner-loop green
    on the same tree is not an outer-loop green: reusing it left an in-scope
    quick fix with no outer-loop green, and every later finish reused it again.
    """
    if not command:
        return False
    try:
        task, _ = load_manifest(task_dir)
    except CompassError:
        return False
    from compass_pkg.acceptance_strategy import loop_of
    record = None
    for e in reversed(task.get("evidence") or []):
        if not (isinstance(e, dict) and e.get("type") == "test-run"
                and e.get("scenario") == scenario and e.get("path")):
            continue
        full_path = os.path.realpath(os.path.join(task_dir, e["path"]))
        if not full_path.startswith(os.path.realpath(task_dir) + os.sep):
            continue  # a record path outside the issue is not this issue's
        try:
            with open(full_path, "r", encoding="utf-8") as fh:
                held = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(held, dict) and loop_of(held) == loop:
            record = held     # one entry per binding and loop - the newest wins
            break
    if record is None:
        return False
    if any(record.get(k) != v for k, v in (named or {}).items()):
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
    old_tree, old_files = record.get("tree_id"), record.get("file_sha256")
    new_tree, new_files = tree_ids.get("tree_id"), tree_ids.get("file_sha256")
    # A green written before ADR-089 holds `changes_id`, not file digests, so
    # it cannot show it covers the same files: it is run again.
    if not (old_tree and new_tree and isinstance(old_files, dict)
            and isinstance(new_files, dict)):
        return False
    return (old_tree == new_tree and old_files == new_files
            and record.get("file_modes") == tree_ids.get("file_modes"))


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


def _owed_refusal(args, slug, owed):
    """Exit 1 before anything is written, with one `next:` line per owed item.
    `--json` names them as `owed`, so its document keeps one shape."""
    from compass_pkg.terminal import resolve_mode
    outcome = (f"compass quick-fix finish: '{slug}' still owes {len(owed)} item(s); "
               f"no gate passed and nothing was committed.")
    if resolve_mode(args) == "json":
        say(args, outcome, owed=owed)
        return 1
    say(args, outcome, decision=True)
    for command in owed:
        print(f"next: {command}")
    return 1


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
    on_path = is_path_issue(task)
    if on_path and approach == APPROACH_DELIVERY:
        return _lean_finish(args, task_dir, slug, command)
    if approach != (APPROACH_DELIVERY if on_path else APPROACH_QUICK_FIX):
        raise CompassError(
            f"compass quick-fix finish: '{slug}' is "
            f"{display_shape(approach)}, not "
            + ("a delivery issue - this verb clears the gates of a change that ships."
               if on_path else "quick fix - this verb only clears the quick-fix gate set."))

    # On the path `finish` serves any delivery issue, and refuses while it owes
    # anything but the three gates and the green it records itself (ADR-092).
    if on_path:
        from compass_pkg.next_step import owed_commands
        owed = owed_commands(task, task_dir, THREE_GATES)
        if owed:
            return _owed_refusal(args, slug, owed)
    other_pending = [g.get("id") for g in (task.get("gates") or [])
                     if isinstance(g, dict) and g.get("id") not in THREE_GATES
                     and g.get("status") == "pending"] if not on_path else []
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
    # An outer-loop green on an in-scope issue names its candidate and client
    # (ADR-085); refuse a finish without them before anything is traced or run.
    # The finish chooses its loop, so a session cannot always tell which one it
    # records: on the inner loop the two flags are taken and not written.
    loop = getattr(args, "loop", None) or default_loop(task_dir)
    named_flags = ((getattr(args, "candidate", None), getattr(args, "client", None))
                   if loop == "outer" else (None, None))
    candidate_client.named("quick-fix finish", "outer", None, getattr(args, "client", None),
                           False, {})     # an unknown client is refused on either loop
    candidate_client.named("quick-fix finish", loop, *named_flags,
                           loop == "outer" and strategy_applies(task_dir), ids_for(task_dir))

    # The project root - the directory holding .compass/ - not necessarily
    # where the agent ran `finish` from (QFG-2). Tracing, `compass check` and
    # staging run from there; the test command runs where it was given,
    # because its own paths are relative to that directory.
    invoked_from = os.getcwd()
    project_root = find_upwards(task_dir, ".compass") or invoked_from

    # A finish that lands runs the landing refusals with the other
    # preconditions, before it traces, tests or writes anything. They judge the
    # manifest with a given release line applied; the line itself is judged here
    # too, and written only once the gates pass (ADR-065).
    from compass_pkg import release_line
    note = release_line.given(args, task_dir, "compass quick-fix finish", task)
    if not getattr(args, "no_commit", False):
        from compass_pkg.manifest import run_landing_refusals
        run_landing_refusals(release_line.project(task, note), task_dir)

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

    named = candidate_client.named("quick-fix finish", loop, *named_flags, False, tree_ids_now)
    for sid in scenario_ids:
        if _reusable_green(task_dir, sid, command, tree_ids_now, loop, named):
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
                       verified_by=None, command=list(command), loop=loop,
                       candidate=named_flags[0], client=named_flags[1],
                       prerun=_shared_run())
        except CompassError as exc:
            raise CompassError(
                f"compass quick-fix finish: the green or acceptance for {sid} "
                f"failed - no "
                f"gate passed and nothing was committed.\n{exc}")

    with _at_project_root(project_root):
        evidence_path_rel = "evidence/check-output.txt"
        evidence_path_abs = os.path.join(task_dir, evidence_path_rel)
        counts = {}
        check_out, check_code = _quiet_run(
            cmd_check, mode="summary", answers=counts, task=slug,
            evidence_out=evidence_path_abs)
        # The request link is not a stop (#356, VD-033): when the only failure
        # is `request-recorded`, the gates pass and `compass check` keeps
        # failing on it until the request is recorded or a person waives it.
        request_only = (check_code != 0 and counts.get("request_failures")
                        and counts.get("failed_checks") == counts["request_failures"])
        if check_code != 0 and not request_only:
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
        _quiet_run(cmd_gate_pass, task=slug, gate_id=GATE_VERIFY_CORRECTNESS,
                  evidence=correctness_ids)
        _quiet_run(cmd_gate_pass, task=slug, gate_id=GATE_VERIFY_GOVERNANCE,
                  evidence=[check_ev_id])
        _quiet_run(cmd_gate_pass, task=slug, gate_id=GATE_VERIFY_TRACEABILITY,
                  evidence=[check_ev_id])
        if getattr(args, "no_commit", False):
            # Nothing lands here, so the line is stored now; a landing writes it itself.
            release_line.store(task_dir, note, "compass quick-fix finish")

        evidence_ids = correctness_ids + [check_ev_id]
        if not on_path:     # the path writes no devlog (ADR-092 decision 12)
            devlog_path = os.path.join(task_dir, "devlog.md")
            if not os.path.isfile(devlog_path):
                with open(devlog_path, "w", encoding="utf-8") as fh:
                    fh.write(f"# Devlog - {slug}\n\n")
            message_first_line = (args.message or "").splitlines()[0] if args.message else ""
            with open(devlog_path, "a", encoding="utf-8") as fh:
                fh.write(f"- {datetime.date.today().isoformat()}: "
                        f"{message_first_line} (evidence: {', '.join(evidence_ids)})\n")

        detail = [f"gates    : {', '.join(THREE_GATES)} -> pass",
                  f"evidence : {', '.join(evidence_ids)}"]
        if request_only:
            from compass_pkg import request_link
            # The command has a line of its own, so the output layer never cuts it.
            detail += [f"request  : not recorded, so `compass check` fails on "
                       f"{request_link.CHECK} until you run",
                       f"`{request_link.command(task_dir)}`"]

        # A commit is the user's to ask for. With --no-commit the gates and
        # records are complete and the change is left in the working tree.
        if getattr(args, "no_commit", False):
            # The same command the `next:` line names, so the two cannot disagree.
            task, _ = load_manifest(task_dir)
            from compass_pkg.next_step import ship_commit_command
            from compass_pkg.next_line import announce
            return announce(args, task_dir, say(
                args,
                f"compass quick-fix finish: '{slug}' checked, not committed.",
                # The command has a line of its own, so the output layer never cuts it.
                detail=detail + [
                    "commit   : when asked, stage the traced files, then run",
                    f"`{ship_commit_command(task, task_dir)}`"],
                decision=True, gates=list(THREE_GATES), evidence=evidence_ids,
                committed=False,
            ))

        # The issue folder is not named: in committed mode `ship-commit`
        # stages the record itself, and in kept-out mode nothing under
        # `.compass/` is staged (#356).
        stage_paths = sorted(set(production_paths) | set(artifact_paths))
        ship_out, ship_code = _quiet_run(cmd_land_commit, task=slug,
                                         message=args.message,
                                         files=stage_paths, release_note=note)
        if ship_code != 0:
            # The commit may stand, but the issue did not land: a hook
            # changed an issue file during the commit. The start record
            # stays for the next try.
            raise CompassError(
                f"compass quick-fix finish: '{slug}' did not land.\n"
                + ship_out.strip())
        ship_tail_lines = [ln for ln in ship_out.strip().splitlines() if ln.strip()]
        ship_tail = ship_tail_lines[-1] if ship_tail_lines else "commit recorded"
        landed, _ = load_manifest(task_dir)
        committed_files = _commit_files(landing.land_commit(landed, task_dir), project_root)
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
               for p in untraced] + [ship_tail],
            decision=True, gates=list(THREE_GATES), evidence=evidence_ids,
            committed=True,
        )


# --- the lean finish (experiment branch exp-lean) -------------------------------------------

def _short(text, limit=96):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _check_failures(check_out, limit=5):
    """The failing checks of a `compass check` summary, one line each."""
    lines = [ln.strip() for ln in check_out.splitlines()
             if ln.startswith("FAIL ") and not ln.startswith("FAIL - ")]
    more = [f"... and {len(lines) - limit} more"] if len(lines) > limit else []
    return [_short(ln, 200) for ln in lines[:limit]] + more


def _lean_finish(args, task_dir, slug, command):
    """`compass quick-fix finish` on the lean path: one call writes the record.

    It reads the scenarios from the acceptance criteria and the changed files
    from git, proves the red on a copy of the base commit, records the green
    on the working tree, runs `compass check`, passes the three gates and asks
    for the approvals a person owes. It commits nothing: `compass ship-commit`
    does. Running it again after more edits replaces the red and the green."""
    from compass_pkg import lean, release_line
    invoked_from = os.getcwd()
    project_root = find_upwards(task_dir, ".compass") or invoked_from
    task, task_path = load_manifest(task_dir)

    def refuse(why, step):
        print(f"compass quick-fix finish: '{slug}' is not checked - {why}")
        print(f"next: {step}")
        return 1

    owed = lean.specify_owed(task, task_dir)
    if owed:
        return refuse("a person has not approved its scenarios.", owed)

    base = lean.base_commit(task, project_root, slug)
    added = lean.sync_scenarios(task, lean.spec_of(task_dir))
    task[lean.MESSAGE_KEY] = args.message
    if base and not task.get(lean.BASE_KEY):
        task[lean.BASE_KEY] = base
    save_manifest(task, task_path)
    scenario_ids = [s["id"] for s in task.get("scenarios") or []
                    if isinstance(s, dict) and s.get("id")
                    and s.get("verifiable") != "narrative"]
    if not scenario_ids:
        raise CompassError(f"compass quick-fix finish: '{slug}' has no scenario; write one "
                           f"in its acceptance-criteria.md, then run finish again.")

    keep = {cf.get("path") for cf in task.get("changed_files") or [] if isinstance(cf, dict)}
    with _at_project_root(project_root):
        code_paths, documents, left_out = lean.changed_paths(
            project_root, base, slug, lean.doc_prefix(task_dir), keep)
        test_paths = [p for p in code_paths if lean.is_test_path(p)]
        tests = [p for p in test_paths if os.path.isfile(os.path.join(project_root, p))]
        lean.record_change(task_dir, project_root, code_paths, documents, tests)

    argv = _neutralise_coverage(list(command))
    ids = ids_for(task_dir)
    proved = None
    try:
        if not lean.records_current(task_dir, scenario_ids, argv, ids):
            red_code, red_out, kind = lean.prove_red(
                project_root, base, test_paths, argv, invoked_from,
                declared=ids.get("test_files") or ())
            lean.drop_greens(task_dir, scenario_ids)
            stamp = lean.write_reds(task_dir, scenario_ids, argv, red_code, red_out, kind,
                                    base, tests, ids)
            lean.wait_past(stamp)
            shared = {"argv": argv, "tree_ids": ids_for(task_dir), "result": _run_test(argv)}
            if shared["result"][0] != 0:
                tail = "\n".join(shared["result"][1].splitlines()[-12:])
                raise CompassError(
                    f"compass quick-fix finish: the tests fail on the working tree (exit "
                    f"{shared['result'][0]}); nothing is checked.\n{tail}")
            for sid in scenario_ids:
                _quiet_run(cmd_tdd_green, task=slug, scenario=sid, verified_by=None,
                           command=list(command), loop="inner", candidate=None, client=None,
                           prerun=shared)
            proved = red_code
    except CompassError as exc:
        # A refusal is short: the agent reads it again on every later call.
        lines = str(exc).splitlines()
        print("\n".join(lines[:1] + lines[1:][-12:]))
        print("next: fix what the line above names, then run the same finish again")
        return 1

    with _at_project_root(project_root):
        evidence_rel = "evidence/check-output.txt"
        counts = {}
        check_out, check_code = _quiet_run(
            cmd_check, mode="summary", answers=counts, task=slug,
            evidence_out=os.path.join(task_dir, evidence_rel))
        # The `G5` sign-off is a person's, and finish asks for it below. When it
        # is the only failure the record is complete but for that answer, and
        # `compass ship-commit` refuses to land until `compass check` passes.
        failing = {ln.split()[1].rstrip(":") for ln in check_out.splitlines()
                   if ln.startswith("FAIL ") and len(ln.split()) > 1 and ln.split()[1] != "-"}
        # An issue that landed and was then changed (a review fix) fails
        # `evidence-matches-tree` until `compass ship-commit` lands it again.
        from compass_pkg import status_words
        relanding = status_words.is_completed(task)
        if relanding:
            failing.discard("evidence-matches-tree")
            check_code = check_code if failing else 0
        signoff_only = check_code != 0 and failing == {"human-approval-present"}
        if check_code != 0 and not signoff_only:
            print(f"compass quick-fix finish: '{slug}' is not checked - `compass check` "
                  f"fails:")
            for line in _check_failures(check_out):
                print("  " + line)
            print("next: fix what the lines above name, then run the same finish again")
            return 1

        task, _ = load_manifest(task_dir)
        pending = [g.get("id") for g in task.get("gates") or []
                   if isinstance(g, dict) and g.get("status") != "pass"]
        if proved is not None or pending:
            taken = {e.get("id") for e in task.get("evidence") or [] if isinstance(e, dict)}
            n = 1
            while f"EV-CHECK-{n}" in taken:
                n += 1
            _quiet_run(cmd_evidence_add, task=slug, evidence_id=f"EV-CHECK-{n}",
                       type="command-output", path=evidence_rel, scenario=None)
            task, _ = load_manifest(task_dir)
            runs = sorted({e.get("id") for e in task.get("evidence") or []
                           if isinstance(e, dict) and e.get("type") == "test-run"
                           and e.get("scenario") in scenario_ids})
            _quiet_run(cmd_gate_pass, task=slug, gate_id=GATE_VERIFY_CORRECTNESS, evidence=runs)
            for gate in (GATE_VERIFY_GOVERNANCE, GATE_VERIFY_TRACEABILITY):
                _quiet_run(cmd_gate_pass, task=slug, gate_id=gate, evidence=[f"EV-CHECK-{n}"])
        task, _ = load_manifest(task_dir)
        if release_line.owes(task, task_dir) and not release_line.held(task):
            line = release_line.clean(getattr(args, "release_note", None)
                                      or (args.message or "").splitlines()[0])
            if line and not release_line.text_problem(task_dir, line, "compass quick-fix finish"):
                release_line.store(task_dir, line, "compass quick-fix finish")
        waiting = lean.request_owed_approvals(task_dir)

    print(f"compass quick-fix finish: '{slug}' checked"
          + (", but for the `G5` sign-off" if signoff_only else "") + ". Nothing is committed.")
    if proved is not None:
        print(f"  red      : the tests fail on the base commit {str(base)[:8]} (exit {proved}), "
              f"with {len(tests)} test file(s) of the change")
        print("  green    : the tests pass on the working tree")
    else:
        print("  records  : the red and the green already cover these files")
    print(f"  scenarios: {', '.join(scenario_ids)}"
          + (f" ({len(added)} read from the acceptance criteria)" if added else ""))
    print(f"  files    : {len(code_paths) + len(documents)} traced from git")
    if left_out:
        print(f"  left out : {_short(', '.join(left_out), 80)} (changed before start; "
              f"`compass changed-file add` takes one in)")
    ship = "When they ask for a commit, run compass ship-commit"
    if not waiting:
        print("next: run compass ship-commit to land the fix on this branch" if relanding
              else "next: when the person asks for a commit, run compass ship-commit")
        return 0
    from compass_pkg import approval_requests
    if os.environ.get(approval_requests.CHANNEL_ENV) == "terminal":
        # This host has no person-only approval event: the person runs the
        # command in their own terminal.
        held = {r.get("number"): r for r in approval_requests.pending(task_dir)}
        for number, _what in waiting:
            print("  approve  : " + approval_requests._terminal_command(held[number]))
        print(f"next: stop and ask the person to run each `approve :` command above in "
              f"their own terminal. {ship}")
        return 0
    asks = " and ".join(f"/compass:approve {number} ({what})" for number, what in waiting)
    print(f"next: stop and ask the person to type {asks}. {ship}")
    return 0
