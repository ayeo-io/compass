# compass_pkg.trail - `trail.md`, the issue's record a reviewer checks with `sha256sum -c`
"""Write `.compass/work/<slug>/trail.md` and say whether it is out of date (#356, ADR-096).

The file has six sections, in the order of the issue text:

1. Who asked: the request link and the requester, which the session records
   as a claim.
2. What was agreed: the scenarios, the freeze at the first red, and the
   sign-off of the scenarios where the issue owes one.
3. Red, for each scenario: each red record.
4. Green: each green record, then the files as the newest green tested them.
5. Who approved, and by what authority: each approval record and waiver.
6. What shipped: the landing, the pull request and the release line.

Under each statement are lines in `sha256sum` format, `<64 hex>  <path>`,
with each path relative to the repository root. From the repository root,
`grep -E '^[0-9a-f]{64}  ' <trail> | sha256sum -c -` checks every file the
trail names, and `shasum -a 256 -c` reads the same lines. The `-` names the
standard input: the macOS `sha256sum` reads no standard input without it. A statement with
no evidence on record says so and has no sum line.

The code and test lines of section 4 hold the digests of the newest green's
`file_sha256`, not of the files on disk, so the check proves that the
committed code is the code that was tested. They hold only at the commit
that holds this version of the file; the header says so.

The file is written in full from the manifest and the files each time, and
the same record gives the same bytes. It holds no time of its own writing
and reads nothing from git but the repository root, so `compass trail
--check` can compare it byte for byte. A landing whose record is committed
with the code (`landed_with_record`) cannot name its own commit, so section 6
says how to find it in git, the way `landing.land_commit` does, instead of
naming a commit id that changes when the record is committed.

This module only reads records. It writes no approval and no other file.
`compass trail`, `compass ship-commit`, `compass issue link set --pr` and
`compass record commit` write the file; `compass check` prints one line when
the file exists.
"""
# DEPENDENCY: standard library (os, subprocess, hashlib); compass_pkg.approval_records
# (shown_text, provenance words), atomic_io, core, evidence_sums (the sum line),
# red_first (the record files), request_link, scenario_freeze, ship_approval,
# spec_location, stable_ids, status_words, terminal, waiver_records.
from __future__ import annotations

import hashlib
import os
import subprocess

from compass_pkg import (approval_records, request_link, scenario_freeze, ship_approval,
                         status_words, waiver_records)
from compass_pkg.atomic_io import atomic_write_text
from compass_pkg.core import (CompassError, find_upwards, issue_arg, load_manifest,
                              resolve_issue_dir)
from compass_pkg.evidence_sums import NAME as SUMS_NAME
from compass_pkg.evidence_sums import sum_line
from compass_pkg.red_first import is_record_name, load_record
from compass_pkg.stable_ids import APPROACH_SPIKE, STAGE_SPECIFY

NAME = "trail.md"
VERB = "compass trail"

#: The section headings, in the order of the issue text.
HEADINGS = (
    "## 1. Who asked",
    "## 2. What was agreed",
    "## 3. Red, for each scenario",
    "## 4. Green",
    "## 5. Who approved, and by what authority",
    "## 6. What shipped",
)

#: The longest command or free text a statement shows.
SHOWN = 200

#: The record types section 5 lists.
APPROVAL_TYPES = ("human-approval", "artifact-approval", "checkpoint-approval",
                  ship_approval.PR_APPROVAL)


class Base:
    """Where the sum paths start. `root` is the project root; `prefix` is the
    project root's path from the repository root ('' when they are the same);
    `in_git` is False outside a git repository, where the paths start at the
    project root."""

    def __init__(self, root, prefix, in_git):
        self.root, self.prefix, self.in_git = root, prefix, in_git

    def path(self, project_rel):
        """A project-relative path as the trail names it."""
        rel = project_rel.replace(os.sep, "/")
        return f"{self.prefix}/{rel}" if self.prefix else rel


def _base(root):
    try:
        found = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                               capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        found = None
    if found is None or found.returncode != 0 or not found.stdout.strip():
        return Base(root, "", False)
    top = os.path.realpath(found.stdout.strip())
    prefix = os.path.relpath(root, top)
    return Base(root, "" if prefix == "." else prefix.replace(os.sep, "/"), True)


def _sha256(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except OSError:
        return None


def _text(value, limit=SHOWN):
    """A value as one line of prose: no control characters, white space folded,
    no backtick (a statement puts commands in backticks)."""
    return approval_records.shown_text(value, limit).replace("`", "'")


def _is_digest(value):
    return (isinstance(value, str) and len(value) == 64
            and all(c in "0123456789abcdef" for c in value))


class _Writer:
    """Collects the lines of one trail."""

    def __init__(self, base, task, task_dir):
        self.base, self.task, self.task_dir = base, task, task_dir
        self.issue_rel = os.path.relpath(task_dir, base.root)
        self.lines = []

    def rel(self, name):
        """A file of the issue folder, relative to the project root."""
        return os.path.join(self.issue_rel, name)

    def say(self, *sentences):
        for sentence in sentences:
            self.lines += [sentence, ""]

    def sums(self, entries):
        """A block of sum lines: `entries` is `(project-relative path, digest or
        None)`; None reads the file's digest from disk, and a missing file
        gives no line."""
        out = []
        for rel, digest in entries:
            digest = digest or _sha256(os.path.join(self.base.root, rel))
            if digest:
                out.append(sum_line(digest, self.base.path(rel)).rstrip("\n"))
        if out:
            self.lines += ["```", *out, "```", ""]

    def manifest_sum(self):
        self.sums([(self.rel("manifest.yml"), None)])


# --- the records ----------------------------------------------------------------------------

def _records(task_dir, kind):
    """`[(name, record)]` of the `red` or `green` record files, by name."""
    evidence = os.path.join(task_dir, "evidence")
    try:
        names = sorted(n for n in os.listdir(evidence) if is_record_name(kind, n))
    except OSError:
        return []
    return [(n, load_record(os.path.join(evidence, n))) for n in names]


def _by_scenario(task, records):
    """The records in the order of the manifest's scenarios, then the rest
    (unbound, or bound to a scenario the manifest no longer holds) by name."""
    ids = _scenario_ids(task)
    ordered = []
    for sid in ids:
        ordered += [(n, r) for n, r in records if r.get("scenario") == sid]
    ordered += [(n, r) for n, r in records if r.get("scenario") not in ids]
    return ordered


def _scenario_ids(task):
    return [s["id"] for s in task.get("scenarios") or []
            if isinstance(s, dict) and isinstance(s.get("id"), str)]


def _label(record):
    sid = record.get("scenario")
    return _text(sid) if isinstance(sid, str) and sid else "An unbound run"


def _loop(name, record):
    loop = record.get("loop")
    if loop not in ("inner", "outer"):
        loop = "outer" if name.endswith(".outer.json") else "inner"
    return " (outer loop)" if loop == "outer" else ""


def _run_line(name, record, verb):
    code = record.get("exit_code")
    return (f"- {_label(record)} {verb} at {_text(record.get('timestamp') or 'an unknown time')}"
            f", exit {_text(code if code is not None else 'unknown')}{_loop(name, record)}: "
            f"`{_text(record.get('command') or '')}`")


def _record_entries(writer, name):
    stem = name[:-len(".json")]
    return [(writer.rel(os.path.join("evidence", name)), None),
            (writer.rel(os.path.join("evidence", stem + ".log")), None)]


def _newest(records):
    """The green record with the newest timestamp; the name breaks a tie."""
    dated = [(str(r.get("timestamp") or ""), n, r) for n, r in records]
    return max(dated)[1:] if dated else None


# --- the sections ---------------------------------------------------------------------------

def _who_asked(w):
    link, requester = request_link.recorded(w.task)
    held = w.task.get(request_link.KEY) if isinstance(w.task.get(request_link.KEY), dict) else {}
    when = held.get("recorded_at")
    if link and requester:
        w.say(f"{_text(requester)} asked at {_text(link, request_link.LINK_MAX)}, recorded "
              f"{_text(when or 'at an unknown time')} with `compass issue link set`. Compass "
              f"does not check who the requester is.")
    else:
        missing = " and ".join(p for p, v in (("no request link", link),
                                               ("no requester", requester)) if not v)
        w.say(f"The record holds {missing}"
              + (f"; the link is {_text(link, request_link.LINK_MAX)}" if link else "")
              + (f"; the requester is {_text(requester)}" if requester else "") + ".")
    w.manifest_sum()


def _what_was_agreed(w):
    scenarios = [s for s in w.task.get("scenarios") or [] if isinstance(s, dict)]
    if scenarios:
        w.lines += [f"- {_text(s.get('id') or '?')}: {_text(s.get('title') or '')}"
                    for s in scenarios] + [""]
    else:
        w.say("The record holds no scenario.")
    frozen = w.task.get(scenario_freeze.KEY)
    spec, sha = scenario_freeze.spec_digest(w.task_dir)
    if isinstance(frozen, dict):
        held = frozen.get("spec_sha256")
        since = "unchanged since" if held == sha else "changed since"
        w.say(f"Frozen at the first red, {_text(frozen.get('at') or 'an unknown time')}, "
              f"spec sha256 {scenario_freeze.short(held)}; {since}.")
    if scenario_freeze.owes_signoff(w.task):
        signed = [e for e in _registry(w.task)
                  if e.get("type") == "checkpoint-approval"
                  and e.get("checkpoint") == STAGE_SPECIFY]
        if signed:
            for e in signed:
                w.say(f"Scenarios signed off by {_text(e.get('approver') or '?')} at "
                      f"{_text(e.get('timestamp') or '?')} ({_text(e.get('id') or '?')}), "
                      f"spec sha256 {scenario_freeze.short(e.get('spec_sha256'))}.")
        else:
            w.say("The scenarios owe a person's sign-off, and none is on record.")
    if sha:
        w.sums([(spec, sha)])
    else:
        w.say("There is no spec file; the scenarios are in the manifest.")
        w.manifest_sum()


def _red(w):
    records = _by_scenario(w.task, _records(w.task_dir, "red"))
    named = {r.get("scenario") for _, r in records}
    for sid in _scenario_ids(w.task):
        if sid not in named:
            w.say(f"- {_text(sid)}: no red on record.")
    for name, record in records:
        w.say(_run_line(name, record, "failed"))
        w.sums(_record_entries(w, name))
    if not records and not _scenario_ids(w.task):
        w.say("No red on record.")


def _green(w):
    records = _by_scenario(w.task, _records(w.task_dir, "green"))
    named = {r.get("scenario") for _, r in records}
    for sid in _scenario_ids(w.task):
        if sid not in named:
            w.say(f"- {_text(sid)}: no green on record.")
    for name, record in records:
        w.say(_run_line(name, record, "passed"))
        w.sums(_record_entries(w, name))
    if not records:
        if not _scenario_ids(w.task):
            w.say("No green on record.")
        return
    name, record = _newest(records)
    digests = record.get("file_sha256")
    files = sorted((p, d) for p, d in digests.items()
                   if isinstance(p, str) and _is_digest(d)) if isinstance(digests, dict) else []
    if not files:
        w.say(f"The newest green ({name}) holds no file digests, so no code file is named.")
        return
    w.say(f"The files as the newest green tested them ({name}). These lines hold at the "
          f"land commit; a later change to the same file makes its line fail at a later "
          f"commit.")
    merged = _merge_commit(w.task)
    if merged:
        # A trail written after the merge is committed later, where other pull
        # requests may have changed these files; the merge commit is where
        # they hold (#356, plan section 4.4).
        w.say(f"Check these at the merge commit {merged}: `git checkout {merged}`.")
    w.sums(files)


def _merge_commit(task):
    """The merge commit `compass issue link set --pr` recorded, or None. Read
    from the manifest, never from git, so the same record gives the same bytes."""
    pr = task.get("pull_request")
    oid = pr.get("merge_commit") if isinstance(pr, dict) and pr.get("merged_at") else None
    if isinstance(oid, str) and len(oid) in (40, 64) and all(c in "0123456789abcdef" for c in oid):
        return oid
    return None


def _registry(task):
    return [e for e in task.get("evidence") or [] if isinstance(e, dict)]


def _subject(record):
    if record.get("type") == ship_approval.PR_APPROVAL:
        pr = record.get("pull_request") or {}
        return f"pull request {_text(pr.get('repo'))}#{_text(pr.get('number'))}"
    if record.get(ship_approval.SHIP):
        return "the change at ship"
    if record.get("type") == "checkpoint-approval":
        return f"the {_text(record.get('checkpoint'))} checkpoint"
    if record.get(waiver_records.SUBJECT):
        return (f"waiver {_text(record[waiver_records.SUBJECT])} of "
                f"{_text(record.get(waiver_records.CHECK) or '?')}")
    if record.get("decisions"):
        ids = record["decisions"]
        shown = ", ".join(_text(i) for i in ids) if isinstance(ids, list) else _text(ids)
        return f"the decisions taken ({shown})"
    if record.get("artifact"):
        return f"document {_text(record['artifact'])}"
    if record.get("check"):
        return f"check {_text(record['check'])}"
    if approval_records.gives_g5(record):
        return "the guardrail `G5` sign-off"
    return _text(approval_records.subject_of(record))


def _authority(task, record):
    via = record.get("via")
    if via == "terminal":
        return "typed at a terminal"
    if via == "prompt":
        asked = record.get("request")
        return ("typed in Claude Code (`/compass:approve`)"
                + (f" for request {_text(asked)}" if asked is not None else ""))
    if via == "delegation":
        key = record.get("delegation")
        held = task.get("delegations_used")
        copy = held.get(key) if isinstance(held, dict) and isinstance(key, str) else None
        words = f"under delegation {_text(key or '?')}"
        if isinstance(copy, dict):
            words += f" given by {_text(copy.get('delegated_by') or '?')}"
            if _is_digest(copy.get("sha256")):
                words += f", copy sha256 {copy['sha256'][:12]}"
        return words + f", used by {_text(record.get('approved_by_agent') or 'an agent')}"
    if via == "github" or record.get("type") == ship_approval.PR_APPROVAL:
        pr = record.get("pull_request") or {}
        return (f"review {_text(record.get('review_id'))} by {_text(record.get('approver'))} "
                f"on {_text(pr.get('repo'))}#{_text(pr.get('number'))}, "
                f"{_text(record.get('url') or 'no URL')}")
    return approval_records.provenance(record)


def _ship_due(task):
    """The sentence for an owed ship approval that is not on record, or None."""
    if not ship_approval.owed(task):
        return None
    registry = _registry(task)
    if any(e.get("type") == ship_approval.PR_APPROVAL or e.get(ship_approval.SHIP)
           for e in registry if e.get("decision") == approval_records.APPROVED):
        return None
    pr = task.get("pull_request")
    if isinstance(pr, dict) and pr.get("repo") and pr.get("number") is not None:
        where = f"{_text(pr['repo'])}#{_text(pr['number'])}"
        if pr.get("merged_at"):
            return (f"Ship approval: none on record for the merged pull request {where}.")
        return f"Ship approval: read from pull request {where} after the merge."
    return ("Ship approval: not on record yet. It is read from the pull request after the "
            "merge with `compass issue link set --pr <n>`, or a person types it after "
            "`compass evidence request --ship`.")


def _who_approved(w):
    shown = False
    for e in _registry(w.task):
        if e.get("type") in APPROVAL_TYPES:
            role = f" ({_text(e['role'])})" if e.get("role") else ""
            w.say(f"- {_text(e.get('id') or '?')}: {_subject(e)}, "
                  f"{_text(e.get('decision') or 'no decision')} by "
                  f"{_text(e.get('approver') or '?')}{role} at "
                  f"{_text(e.get('timestamp') or '?')}, {_authority(w.task, e)}.")
            shown = True
        elif e.get("type") == approval_records.WITHDRAWAL:
            w.say(f"- {_text(e.get('id') or '?')}: withdraws {_text(e.get('withdraws'))}, "
                  f"by {_text(e.get('by') or '?')} at {_text(e.get('at') or '?')}.")
            shown = True
    for waiver in waiver_records.listed(w.task):
        approved = [e.get("id") for e in _registry(w.task)
                    if e.get(waiver_records.SUBJECT) == waiver.get("id")
                    and e.get("decision") == approval_records.APPROVED]
        state = (f"approved in {', '.join(_text(i) for i in approved)}" if approved
                 else "no approval on record, so it excuses nothing")
        if waiver.get("withdrawn_at"):
            state += f"; withdrawn at {_text(waiver['withdrawn_at'])}"
        w.say(f"- Waiver {_text(waiver.get('id'))} of {_text(waiver.get('check'))}: "
              f"{_text(waiver.get('reason') or '')}; {state}.")
        shown = True
    due = _ship_due(w.task)
    if due:
        w.say(due)
    elif not shown:
        w.say("No approval record is on record.")
    w.manifest_sum()


def _what_shipped(w):
    task = w.task
    stamp = task.get("land_timestamp")
    if not status_words.is_completed(task) or not stamp:
        w.say("Not landed yet.")
    elif task.get("land_commit"):
        w.say(f"Landed {_text(stamp)} in {_text(task['land_commit'])}.")
    elif task.get("landed_with_record") is True:
        manifest = w.base.path(w.rel("manifest.yml"))
        w.say(f"Landed {_text(stamp)}, with this record, in the commit that added this "
              f"`land_timestamp` to the manifest. Find it with `git log --format=%H -G "
              f"'^land_timestamp: ' -- {manifest}`.")
    else:
        w.say(f"Landed {_text(stamp)}; the record names no land commit.")
    pr = task.get("pull_request")
    if isinstance(pr, dict) and pr.get("repo") and pr.get("number") is not None:
        line = f"Pull request {_text(pr['repo'])}#{_text(pr['number'])}"
        if pr.get("merged_at"):
            line += (f", merged {_text(pr['merged_at'])} as "
                     f"{_text(pr.get('merge_commit') or 'an unknown commit')}")
        w.say(line + ".")
    note = task.get("release_note")
    if isinstance(note, str) and note.strip():
        w.say(f"Release line: {_text(note, 500)}")
    w.sums([(w.rel("manifest.yml"), None), (w.rel(os.path.join("evidence", SUMS_NAME)), None)])


SECTIONS = (_who_asked, _what_was_agreed, _red, _green, _who_approved, _what_shipped)


def _goal(task_dir):
    """The spec's `**Goal:**` line, or ''."""
    from compass_pkg.spec_location import spec_path
    try:
        with open(spec_path(task_dir), encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("**Goal:**"):
                    return _text(line[len("**Goal:**"):], 300)
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def _header(w, slug):
    trail = w.base.path(w.rel(NAME))
    goal = _goal(w.task_dir)
    where = "repository root" if w.base.in_git else "project root"
    w.lines += [f"# Trail: {_text(slug)}", ""]
    w.say((f"{goal.rstrip('.')}. " if goal else "")
          + "Written by `compass trail`; do not edit.")
    w.lines += [f"From the {where}, check every file named below:", "",
                f"    grep -E '^[0-9a-f]{{64}}  ' {trail} | sha256sum -c -", "",
                "`shasum -a 256 -c` reads the same lines. Run it at the commit that",
                "holds this version of the file "
                f"(`git log -1 --format=%H -- {trail}`).", ""]


# --- writing and checking -------------------------------------------------------------------

def _is_spike(task):
    return task.get("delivery_approach") == APPROACH_SPIKE


def render(task_dir):
    """The text of the issue's `trail.md`. Raises CompassError for a spike,
    which ships no code and has no trail."""
    task_dir = os.path.realpath(task_dir)
    task, _ = load_manifest(task_dir)
    slug = os.path.basename(task_dir)
    if _is_spike(task):
        raise CompassError(f"{VERB}: {slug} is a spike. A spike ships no code, so it has no "
                           f"trail. Nothing was written.")
    root = find_upwards(task_dir, ".compass")
    if not root:
        raise CompassError(f"{VERB}: {task_dir} is not inside a Compass project.")
    w = _Writer(_base(os.path.realpath(root)), task, task_dir)
    _header(w, slug)
    for heading, section in zip(HEADINGS, SECTIONS):
        w.lines += [heading, ""]
        section(w)
    while w.lines and w.lines[-1] == "":
        w.lines.pop()
    return "\n".join(w.lines) + "\n"


def path_of(task_dir):
    return os.path.join(task_dir, NAME)


def write(task_dir):
    """Write `trail.md` and return its path."""
    text = render(task_dir)
    path = path_of(task_dir)
    atomic_write_text(path, text, newline="")
    return path


def first_difference(task_dir):
    """None when `trail.md` matches what `write` would write now; else
    `(line number, expected, found)`, with '' for a line one side lacks.
    Line 0 means the file is missing."""
    expected = render(task_dir)
    try:
        with open(path_of(task_dir), encoding="utf-8", newline="") as fh:
            found = fh.read()
    except (OSError, UnicodeDecodeError):
        return 0, "", ""
    if found == expected:
        return None
    want, have = expected.split("\n"), found.split("\n")
    for number in range(max(len(want), len(have))):
        a = want[number] if number < len(want) else ""
        b = have[number] if number < len(have) else ""
        if a != b:
            return number + 1, a, b
    return len(want), "", ""


def check_line(task, task_dir):
    """`(text, stale)` for `compass check` when the issue has a `trail.md`,
    else None. It reads the files, never git history, and writes nothing."""
    if not os.path.isfile(path_of(task_dir)) or _is_spike(task):
        return None
    try:
        stale = first_difference(task_dir) is not None
    except (CompassError, OSError, ValueError):
        # An unreadable record is `compass check`'s own failure to report; the
        # trail line is a notice and never adds one.
        return None
    if stale:
        return "Trail: out of date; run `compass trail`", True
    return "Trail: up to date", False


def cmd_trail(args):
    from compass_pkg.terminal import say
    task_dir = resolve_issue_dir(args.task)
    slug = os.path.basename(os.path.normpath(task_dir))
    if args.check:
        differs = first_difference(task_dir)
        if differs is None:
            return say(args, f"{VERB}: trail.md of {slug} is up to date.", issue=slug,
                       up_to_date=True)
        number, expected, found = differs
        if number == 0:
            detail = [f"missing  : {path_of(task_dir)}"]
        else:
            detail = [f"line     : {number}", f"expected : {expected[:SHOWN]}",
                      f"found    : {found[:SHOWN]}"]
        say(args, f"{VERB}: trail.md of {slug} is out of date. Run `compass trail --issue "
                  f"{slug}` to write it again.", detail=detail, issue=slug, up_to_date=False)
        return 1
    path = write(task_dir)
    return say(args, f"{VERB}: wrote the trail of {slug}.",
               detail=[f"trail    : {path}",
                       "check    : the file's header gives the sha256sum command"],
               issue=slug, trail=path)


def register(sub):
    """Add `compass trail`."""
    p = sub.add_parser("trail", help="write the issue's trail.md, which a reviewer checks "
                                     "with sha256sum -c", allow_abbrev=False,
                       description="Write .compass/work/<slug>/trail.md from the issue's "
                                   "records: who asked, what was agreed, the red and green "
                                   "of each scenario, who approved and what shipped. Each "
                                   "statement carries sum lines, so a reviewer runs "
                                   "sha256sum -c without Compass. With --check, write "
                                   "nothing and exit 1 when the file is missing or out "
                                   "of date.")
    issue_arg(p)
    p.add_argument("--check", action="store_true",
                   help="write nothing; exit 1 when trail.md differs from what "
                        "`compass trail` would write")
    p.set_defaults(func=cmd_trail, output_kind="hand-off")
