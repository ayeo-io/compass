#!/usr/bin/env python3
# =============================================================================
# compass - the subtask record of a multiagent run
# =============================================================================
# A multiagent run handed builders prose, recorded no base commit, and kept no
# state a fresh session could resume from: an interrupted run had to be
# rebuilt from the conversation. The manifest's `subtasks:` list is that
# state, and this module is the only writer of it, so an agent never edits
# the YAML by hand.
#
# Each subtask records the files that crossed a boundary - the brief a
# builder was handed, the result it returned, the reviewer's brief, the
# review package of each dispatch - never their contents: a file is what
# bounds a dispatch, where a paste bounds nothing. It records the base commit
# and the model, the budget and the cost, and the progress a resume needs:
# status, `attempts`, the revision last reviewed, findings not yet resolved,
# and every review round.
#
# The round count is recorded, not capped. The spike that adopted this loop
# (docs/compass/2026-08-27-sdd-loop-spike.md) deferred a fix-round cap until
# Compass has its own rounds to size it from.
#
# Every value that reaches git or the file system is checked first: the base
# is resolved to a full commit id, a subtask id is a plain name, and every
# path stays inside the project.
#
# DEPENDENCY: standard library (os, re, subprocess) and compass_pkg.core.
# =============================================================================
"""`compass issue subtask`: record, resume and package a multiagent run."""
from __future__ import annotations

import os
import re
import subprocess

from compass_pkg.core import (CompassError, docs_dir, find_upwards,
                              load_manifest, now_iso, resolve_issue_dir,
                              save_manifest)

#: dispatched - a builder has its brief; reported - its result is recorded;
#: reviewing - a review of the latest package is under way; integrating -
#: reviewed and passed, not yet merged; done - merged, or dropped with a
#: recorded reason.
STATUSES = ("dispatched", "reported", "reviewing", "integrating", "done")

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_SHA = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")

#: Phrases that tell a reviewer what not to find. A reviewer briefed this way
#: reviews the orchestrator's framing, not the change. Matched after
#: straightening apostrophes and collapsing whitespace, case-blind, within a
#: line and across a line break. It is a fixed list: it catches the common
#: wordings, not every paraphrase, and a false refusal costs one rewording
#: because the refusal quotes the line.
COACHING = ("do not flag", "don't flag", "dont flag", "no need to flag",
            "you can ignore", "can be ignored", "please ignore",
            "already known", "known issue", "already handled",
            "already fixed", "out of scope for this review", "you can skip",
            "no need to check", "don't worry about", "do not worry about")

#: Review cadence by assessed risk, as the worktree-multiagent skill states it.
CADENCE = {
    "trivial": "one review of the integrated result",
    "contained": "one review of the integrated result",
    "cross-cutting": "a review of each subtask's package before integration, and one after",
    "critical": "a review of each subtask's package before integration, with a second reviewer, and one after",
}


def _root(task_dir):
    return os.path.realpath(find_upwards(task_dir, ".compass") or task_dir)


def _confine(root, full, what, shown):
    full = os.path.realpath(full)
    if os.path.commonpath([root, full]) != root:
        raise CompassError(f"compass issue subtask: the {what} {shown} is outside "
                           f"the project.")
    return full


def _inside(root, rel, what):
    """`rel` as a path inside the project that names an existing file."""
    full = _confine(root, os.path.join(root, rel), what, rel)
    if not os.path.isfile(full):
        raise CompassError(f"compass issue subtask: the {what} {rel} does not "
                           f"exist. Write the file first; the record names it.")
    return rel


def _git(args, cwd):
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                              text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        raise CompassError(f"compass issue subtask: git could not run: {exc}")


def _commit(root, rev, what):
    """`rev` resolved to a full commit id, or a refusal. `--end-of-options`
    stops a value such as `--output=<path>` being read as an option."""
    found = _git(["rev-parse", "--verify", "-q", "--end-of-options",
                  f"{rev}^{{commit}}"], root)
    sha = found.stdout.strip()
    if found.returncode != 0 or not _SHA.match(sha):
        raise CompassError(f"compass issue subtask: the {what} {rev!r} is not a "
                           f"commit in this repository.")
    return sha


def _load(args):
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)
    return task_dir, task, path, task.setdefault("subtasks", [])


def _find(subtasks, sid):
    for s in subtasks:
        if s.get("id") == sid:
            return s
    raise CompassError(f"compass issue subtask: no subtask '{sid}' is "
                       f"recorded. Record it with `compass issue subtask add`.")


def _count(value, what):
    if value is not None and value < 0:
        raise CompassError(f"compass issue subtask: a {what} cannot be negative.")
    return value


def cmd_subtask_add(args):
    task_dir, task, path, subtasks = _load(args)
    root = _root(task_dir)
    if not _ID.match(args.id or ""):
        raise CompassError(f"compass issue subtask: {args.id!r} is not a subtask "
                           f"id. Use letters, digits, '.', '_' and '-', starting "
                           f"with a letter or digit.")
    if any(s.get("id") == args.id for s in subtasks):
        raise CompassError(f"compass issue subtask: '{args.id}' is already "
                           f"recorded. Use `update --attempt` to dispatch it again.")
    brief = _inside(root, args.brief, "brief")
    base = _commit(root, args.base or "HEAD", "base")
    subtasks.append({"id": args.id, "brief": brief, "base_sha": base,
                     "model": args.model, "budget": _count(args.budget, "budget"),
                     "status": "dispatched", "attempts": 1,
                     "dispatched_at": now_iso()})
    save_manifest(task, path)
    print(f"compass issue subtask: {args.id} dispatched from {base[:12]} "
          f"({args.model}, budget {args.budget}).")
    return 0


def _norm(text):
    return " ".join(text.replace("’", "'").replace("‘", "'")
                    .lower().split())


def _refuse_coaching(root, rel):
    try:
        with open(os.path.join(root, rel), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CompassError(f"compass issue subtask: the reviewer brief {rel} "
                           f"cannot be read as text: {exc}")
    for n, line in enumerate(lines):
        # The line alone, then the line joined to the next, so a phrase split
        # across a line break is found and quoted where it starts.
        here = _norm(line)
        joined = _norm(" ".join(lines[n:n + 2]))
        if any(p in here for p in COACHING) or \
                any(p in joined and p not in _norm(" ".join(lines[n + 1:n + 2]))
                    for p in COACHING):
            raise CompassError(
                f"compass issue subtask: refusing the reviewer brief {rel}: "
                f"line {n + 1} tells the reviewer what not to find:\n"
                f"  {line.strip()}\n"
                "A reviewer briefed this way reviews the framing, not the "
                "change. State what to review, and let the review decide "
                "what matters.")


def cmd_subtask_update(args):
    task_dir, task, path, subtasks = _load(args)
    root = _root(task_dir)
    s = _find(subtasks, args.id)
    if args.brief:
        new = _inside(root, args.brief, "brief")
        if new != s.get("brief"):
            s.setdefault("earlier_briefs", []).append(s.get("brief"))
            s["brief"] = new
    if args.report:
        s["report"] = _inside(root, args.report, "result")
    if args.review_brief:
        rel = _inside(root, args.review_brief, "reviewer brief")
        _refuse_coaching(root, rel)
        s["review_brief"] = rel
    if args.status:
        if args.status not in STATUSES:
            raise CompassError(f"compass issue subtask: '{args.status}' is not a "
                               f"subtask status. Permitted: {', '.join(STATUSES)}.")
        s["status"] = args.status
    if args.reviewed:
        s["reviewed_revision"] = _commit(root, args.reviewed, "reviewed revision")
    if args.attempt:
        s["attempts"] = int(s.get("attempts") or 0) + 1
    findings = s.setdefault("findings", [])
    if args.finding:
        findings.append({"text": args.finding, "resolved": False})
    if args.resolve is not None:
        if not 1 <= args.resolve <= len(findings):
            raise CompassError(f"compass issue subtask: {args.id} has no "
                               f"finding {args.resolve}; findings count from 1.")
        findings[args.resolve - 1]["resolved"] = True
    if args.round:
        rounds = s.setdefault("review_rounds", [])
        rounds.append({"round": len(rounds) + 1, "verdict": args.round,
                       "at": now_iso()})
    if args.cost is not None:
        s["cost"] = _count(args.cost, "cost")
        budget = s.get("budget")
        if isinstance(budget, int) and args.cost > budget:
            # An overrun is recorded, not stopped: the run goes on, and the
            # finding is what the review reads.
            findings.append({"text": f"cost {args.cost} exceeds the budget "
                                     f"{budget} this dispatch was given",
                             "resolved": False})
    if not findings:
        s.pop("findings")
    save_manifest(task, path)
    print(f"compass issue subtask: {args.id} updated ({s.get('status')}).")
    return 0


def cmd_subtask_next(args):
    _, task, _, subtasks = _load(args)
    risk = (task.get("assessment") or {}).get("risk")
    if not subtasks:
        print("compass issue subtask next: no subtask is recorded yet.")
        return 0
    open_ = [s for s in subtasks if s.get("status") != "done"]
    if not open_:
        print("compass issue subtask next: every subtask is done.")
        return 0
    # Work already under way resumes before work not yet started.
    order = {st: i for i, st in enumerate(reversed(STATUSES))}
    open_.sort(key=lambda s: order.get(s.get("status"), len(order)))
    print("compass issue subtask next: resume or dispatch, in this order:")
    if risk in CADENCE:
        print(f"  risk {risk}: {CADENCE[risk]}")
    for s in open_:
        line = (f"  {s['id']}  {s.get('status')}  attempt {s.get('attempts', 1)}"
                f"  base {str(s.get('base_sha', '?'))[:12]}")
        if s.get("reviewed_revision"):
            line += f"  reviewed {s['reviewed_revision'][:12]}"
        print(line)
        for key, label in (("brief", "brief"), ("report", "result"),
                           ("review_brief", "reviewer brief"),
                           ("package", "package")):
            if s.get(key):
                print(f"      {label}: {s[key]}")
        for f in s.get("findings") or []:
            if not f.get("resolved"):
                print(f"      unresolved: {f.get('text')}")
    return 0


def cmd_subtask_package(args):
    task_dir, task, path, subtasks = _load(args)
    root = _root(task_dir)
    s = _find(subtasks, args.id)
    base = _commit(root, s.get("base_sha", ""), "base")
    head = _commit(root, args.head or "HEAD", "head")
    # The builder's commit also carries its red and green records and its
    # result. Those are not the change under review, and in a rehearsal they
    # made up most of the package, so the diff leaves them out.
    diff = _git(["diff", "--end-of-options", f"{base}..{head}", "--", ".",
                 ":(exclude).compass", ":(exclude)docs/compass"], root)
    if diff.returncode != 0:
        raise CompassError(f"compass issue subtask: cannot diff {base[:12]}"
                           f"..{head[:12]}: {diff.stderr.strip()}")
    if not diff.stdout.strip():
        raise CompassError(
            f"compass issue subtask: the diff from {base[:12]} to {head[:12]} is "
            f"empty. In the orchestrator's checkout HEAD holds none of the "
            f"builder's commits: name the subtask's branch with --head.")
    rel = os.path.join(docs_dir(task_dir), "subtasks", args.id,
                       f"package-{s.get('attempts', 1)}.diff")
    full = _confine(root, os.path.join(root, rel), "package", rel)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(diff.stdout)
    s["package"] = rel
    save_manifest(task, path)
    print(f"compass issue subtask: review package for {args.id} written to {rel}.")
    return 0


def register(issue_subparsers, issue_arg):
    """Add `compass issue subtask ...` to the `issue` verb."""
    p = issue_subparsers.add_parser(
        "subtask", help="record, resume and package the subtasks of a multiagent run")
    sub = p.add_subparsers(dest="subtask_cmd", required=True)

    a = sub.add_parser(
        "add", help="record a dispatch: brief file, model, budget, base commit",
        description="Record that a subtask was dispatched: the brief file the "
                    "builder was handed, the model and token budget, and the "
                    "commit it starts from (HEAD unless --base is given), "
                    "stored as a full commit id. Refuses a brief that does "
                    "not exist and a base that is not a commit.")
    a.add_argument("id")
    a.add_argument("--brief", required=True, help="the brief file the builder is handed")
    a.add_argument("--model", required=True, help="the model the dispatch uses")
    a.add_argument("--budget", required=True, type=int, help="tokens the dispatch may use")
    a.add_argument("--base", help="the commit the builder starts from (default: HEAD)")
    issue_arg(a)
    a.set_defaults(func=cmd_subtask_add, output_kind="hand-off")

    u = sub.add_parser(
        "update", help="record a subtask's progress",
        description="Record a subtask's progress: its status, a new brief for "
                    "another attempt, its result file, the reviewer's brief "
                    "(refused if it matches a fixed list of phrases that say "
                    "what not to flag), the revision reviewed, findings, "
                    "review rounds, the cost, or another attempt. A cost over "
                    "the budget adds a finding.")
    u.add_argument("id")
    u.add_argument("--status", help=" | ".join(STATUSES))
    u.add_argument("--brief", help="the brief for this attempt; the earlier one is kept")
    u.add_argument("--report", help="the result file the builder returned")
    u.add_argument("--review-brief", dest="review_brief",
                   help="the reviewer's brief; refused if it matches a fixed "
                        "list of phrases that say what not to flag")
    u.add_argument("--reviewed", help="the commit the latest review read")
    u.add_argument("--finding", help="an unresolved finding")
    u.add_argument("--resolve", type=int, help="mark finding N resolved (from 1)")
    u.add_argument("--round", choices=("pass", "fail"), help="append a review round")
    u.add_argument("--cost", type=int, help="tokens the dispatch used")
    u.add_argument("--attempt", action="store_true", help="count another attempt")
    issue_arg(u)
    u.set_defaults(func=cmd_subtask_update, output_kind="hand-off")

    n = sub.add_parser(
        "next", help="what to resume or dispatch, from the record alone",
        description="List every subtask not yet done - work under way first - "
                    "with its status, attempt, base commit, the revision last "
                    "reviewed, its files and its unresolved findings, and the "
                    "review cadence the issue's risk calls for, so a fresh "
                    "session resumes an interrupted run from the record alone.")
    issue_arg(n)
    n.set_defaults(func=cmd_subtask_next, output_kind="hand-off")

    k = sub.add_parser(
        "package", help="write the review package: the diff from the base commit",
        description="Write the diff from the subtask's base commit to --head "
                    "(HEAD by default; name the subtask's branch) into the "
                    "issue's documents, one file per attempt, leaving out "
                    ".compass/ and docs/compass/, and record its path. Refuses "
                    "an empty diff. The reviewer reads this file rather than "
                    "deriving a diff.")
    k.add_argument("id")
    k.add_argument("--head", help="the revision to diff to - the subtask's branch")
    issue_arg(k)
    k.set_defaults(func=cmd_subtask_package, output_kind="hand-off")
