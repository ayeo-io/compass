#!/usr/bin/env python3
# =============================================================================
# compass_pkg.lessons - `compass lesson add|list|remove|propose|accept`
# =============================================================================
#
# A project's lessons: one-sentence rules a person has had to repeat, kept in
# `lessons.yml` in the project's `.compass` folder, so the next session in
# this repository reads them. The session-start hook injects the `always`
# ones under their own 150-word cap (render_block). ADR-029 records the
# design.
#
# Who added a lesson comes from git config, as in decisions.py. The CLI cannot
# tell whether the person or the model typed the words, so it does not claim
# to: a model proposes into `lessons-pending.yml` in the same folder, and a
# proposal takes effect only on `lesson accept`.
#
# Lessons are advice. No check reads them, a guardrail always wins, and the
# CLI does not judge whether a lesson agrees with the guardrails; it refuses
# only a lesson that names a guardrail id, a model or a tool version.
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/, through core.load_yaml.
# =============================================================================

import datetime
import os
import re
import subprocess

import yaml

from compass_pkg.core import (CompassError, find_compass_dir, find_governance, load_yaml,
                              manifest_path)

LESSONS = "lessons.yml"
PENDING = "lessons-pending.yml"
LESSONS_CAP = 150
CATEGORIES = ("tool", "process", "repo")
APPLIES = ("always", "on_topic")
SOURCES = ("human", "friction", "verify")

# A model id goes stale and pins a choice that is not the project's to make.
_MODEL = re.compile(r"\b(?:claude-[\w.-]+|gpt-[\w.-]+|sonnet|opus|haiku)\b", re.I)
# A tool's version goes stale too: a version straight after a tool's name.
_TOOL_VERSION = re.compile(
    r"\b(?:python|node|nodejs|npm|pytest|go|java|ruby|rust|cargo|pip|git|docker|"
    r"terraform|kubectl|gradle|maven|yarn|pnpm|deno|bun)\s+v?\d+\.\d+(?:\.\d+)?\b", re.I)


def _dir():
    return find_compass_dir()


def _read(name):
    path = os.path.join(_dir(), name)
    data = load_yaml(path) if os.path.isfile(path) else {}
    return data if isinstance(data, dict) else {}


def _load(name):
    return [i for i in _read(name).get("lessons") or [] if isinstance(i, dict)]


def _save(name, items):
    # `last_id` keeps the highest number ever issued, so a removed lesson's
    # id is never given to a new one.
    before = _read(name)
    last = before.get("last_id") or 0
    # The ids in the file before this write count too, so a hand-written
    # file with no `last_id` still never reissues a removed id.
    old = [i for i in before.get("lessons") or [] if isinstance(i, dict)]
    nums = [int(str(i.get("id", ""))[3:]) for i in items + old
            if str(i.get("id", ""))[3:].isdigit()]
    data = dict(before)
    data.update(last_id=max([int(last)] + nums), lessons=items)
    with open(os.path.join(_dir(), name), "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def _decider():
    for key in ("compass.decidedBy", "user.name"):
        try:
            r = subprocess.run(["git", "config", key], cwd=os.path.dirname(_dir()),
                               capture_output=True, text=True)
        except OSError:
            return None
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    return None


def _guardrail_ids():
    try:
        gr = load_yaml(os.path.join(find_governance(), "guardrails.yml"))
    except CompassError:
        return set()
    return {str(g.get("id")) for key in ("defaults", "project")
            for g in gr.get(key) or [] if isinstance(g, dict) and g.get("id")}


def _refusal(rule, source):
    """The reason a rule cannot be a lesson, or None."""
    if not rule.strip():
        return "a lesson needs a rule."
    if len(rule.split()) > LESSONS_CAP:
        return (f"it has {len(rule.split())} words; the lessons a session reads are capped "
                f"at {LESSONS_CAP} words in all, so one rule must be shorter.")
    if source == "verify":
        return "source verify is reserved; a lesson from verify is not supported yet."
    for gid in sorted(_guardrail_ids()):
        if re.search(rf"\b{re.escape(gid)}\b", rule):
            return (f"it names guardrail {gid}. A lesson cannot refer to or change a "
                    f"guardrail; governance changes go through governance/.")
    m = _MODEL.search(rule)
    if m:
        return f"it names a model ({m.group(0)}), which goes stale."
    m = _TOOL_VERSION.search(rule)
    if m:
        return f"it names a tool version ({m.group(0)}), which goes stale."
    return None


def _norm(text):
    return " ".join(str(text).lower().split())


def _next_id(prefix, name):
    data = _read(name)
    used = [int(str(i.get("id"))[len(prefix):]) for i in data.get("lessons") or []
            if isinstance(i, dict) and str(i.get("id", "")).startswith(prefix)
            and str(i.get("id"))[len(prefix):].isdigit()]
    return f"{prefix}{max(used + [int(data.get('last_id') or 0)]) + 1:03d}"


def _place(items, entry):
    """Add `entry` to `items` with the dedup rules: an exact repeat is refused;
    a rule that contains an existing one replaces it. Returns the replaced id."""
    new = _norm(entry["rule"])
    for old in items:
        if _norm(old["rule"]) == new:
            raise CompassError(f"{old['id']} already says this.")
    replaced = next((old for old in items if _norm(old["rule"]) in new), None)
    if replaced:
        items.remove(replaced)
        entry["superseded"] = replaced["id"]
    items.append(entry)
    return replaced["id"] if replaced else None


def _entry(args, prefix, name, source):
    reason = _refusal(args.rule, source)
    if reason:
        raise CompassError(f"not recorded: {reason}")
    return {"id": _next_id(prefix, name), "rule": " ".join(args.rule.split()),
            "category": args.category, "applies": args.applies, "source": source,
            "issue": args.issue or "", "created": datetime.date.today().isoformat()}


def cmd_lesson_add(args):
    decider = _decider()
    if not decider:
        raise CompassError("no decider: set `git config compass.decidedBy <name>` or "
                           "`git config user.name <name>`.")
    lessons = _load(LESSONS)
    entry = _entry(args, "LS-", LESSONS, args.source)
    entry["added_by"] = decider
    replaced = _place(lessons, entry)
    _save(LESSONS, lessons)
    print(f"compass lesson add: {entry['id']} recorded, added by {decider}"
          + (f"; it replaces {replaced}." if replaced else "."))
    return 0


def cmd_lesson_propose(args):
    pending = _load(PENDING)
    entry = _entry(args, "LP-", PENDING, "human")
    if any(_norm(l["rule"]) == _norm(entry["rule"]) for l in _load(LESSONS)):
        raise CompassError("a lesson already says this.")
    _place(pending, entry)
    _save(PENDING, pending)
    print(f"compass lesson propose: {entry['id']} is pending. It takes effect only "
          f"when someone runs `compass lesson accept {entry['id']}`.")
    return 0


def cmd_lesson_accept(args):
    pending = _load(PENDING)
    entry = next((p for p in pending if p.get("id") == args.id), None)
    if entry is None:
        raise CompassError(f"no pending proposal {args.id}; see `compass lesson list`.")
    decider = _decider()
    if not decider:
        raise CompassError("no decider: set `git config compass.decidedBy <name>` or "
                           "`git config user.name <name>`.")
    lessons = _load(LESSONS)
    accepted = {k: v for k, v in entry.items() if k not in ("id", "superseded")}
    accepted["id"] = _next_id("LS-", LESSONS)
    accepted["added_by"] = decider
    replaced = _place(lessons, accepted)
    pending.remove(entry)
    _save(LESSONS, lessons)
    _save(PENDING, pending)
    print(f"compass lesson accept: {args.id} is now {accepted['id']}, added by {decider}"
          + (f"; it replaces {replaced}." if replaced else "."))
    return 0


def cmd_lesson_list(args):
    lessons, pending = _load(LESSONS), _load(PENDING)
    if not lessons and not pending:
        print("compass lesson list: no lessons and no proposals.")
        return 0
    for l in lessons:
        note = "" if l.get("applies") == "always" else "  (on_topic: stored, not yet surfaced)"
        print(f"{l['id']}  {l['rule']}  [{l.get('category')}, by {l.get('added_by')}]{note}")
    for p in pending:
        print(f"{p['id']}  {p['rule']}  [pending: run compass lesson accept {p['id']}]")
    return 0


def _remember(name, key, text):
    """Keep `text` under `key` in file `name`, so `retro --lessons` does not
    propose it again."""
    data = _read(name)
    seen = [t for t in data.get(key) or [] if isinstance(t, str)]
    if _norm(text) not in {_norm(t) for t in seen}:
        seen.append(text)
    data[key] = seen
    data.setdefault("lessons", [])
    with open(os.path.join(_dir(), name), "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh, sort_keys=False, allow_unicode=True)


def cmd_lesson_remove(args):
    lessons = _load(LESSONS)
    gone = next((l for l in lessons if l.get("id") == args.id), None)
    if gone is None:
        raise CompassError(f"no lesson {args.id}; see `compass lesson list`.")
    _save(LESSONS, [l for l in lessons if l is not gone])
    _remember(LESSONS, "removed", str(gone.get("rule", "")))
    print(f"compass lesson remove: {args.id} removed.")
    return 0


def cmd_lesson_decline(args):
    pending = _load(PENDING)
    entry = next((p for p in pending if p.get("id") == args.id), None)
    if entry is None:
        raise CompassError(f"no pending proposal {args.id}; see `compass lesson list`.")
    _save(PENDING, [p for p in pending if p is not entry])
    _remember(PENDING, "declined", str(entry.get("rule", "")))
    print(f"compass lesson decline: {args.id} declined. compass retro --lessons "
          f"will not propose it again.")
    return 0


def render_block(compass_dir):
    """The injected text for `always` lessons, oldest first, within the cap.
    Empty when there are none."""
    path = os.path.join(compass_dir, LESSONS)
    if not os.path.isfile(path):
        return ""
    try:
        data = load_yaml(path)
    except CompassError:
        return ""
    items = [l for l in (data.get("lessons") if isinstance(data, dict) else None) or []
             if isinstance(l, dict) and l.get("applies", "always") == "always" and l.get("rule")]
    if not items:
        return ""
    shown, words = [], 0
    for l in items:
        n = len(str(l["rule"]).split())
        if words + n > LESSONS_CAP:
            break
        shown.append(str(l["rule"]))
        words += n
    lines = ["[Project lessons]",
             "These lessons are this project's advice. A guardrail always wins over a lesson. "
             "To record a new one the person states, run compass lesson propose with their words."]
    lines += [f"- {r}" for r in shown]
    if len(shown) < len(items):
        lines.append(f"(Showing {len(shown)} of {len(items)} lessons; "
                     f"{len(items) - len(shown)} omitted to stay within {LESSONS_CAP} words. "
                     f"Run compass lesson list to see them all.)")
    return "\n".join(lines)


def propose_from_friction(work_dir, min_issues=3):
    """Pending proposals for friction seen in `min_issues` distinct issues.
    Exact text after case and spacing are normalised; a reworded row does
    not match. Returns the new pending entries."""
    seen = {}
    for slug in sorted(os.listdir(work_dir)) if os.path.isdir(work_dir) else []:
        path = manifest_path(os.path.join(work_dir, slug))
        if not os.path.isfile(path):
            continue
        try:
            m = load_yaml(path)
        except CompassError:
            continue
        for row in (m.get("friction") if isinstance(m, dict) else None) or []:
            if isinstance(row, dict) and row.get("observation"):
                text = " ".join(str(row["observation"]).split())
                seen.setdefault(_norm(text), (text, set()))[1].add(slug)
    lessons, pending = _load(LESSONS), _load(PENDING)
    known = {_norm(l["rule"]) for l in lessons + pending}
    known |= {_norm(t) for t in _read(LESSONS).get("removed") or [] if isinstance(t, str)}
    known |= {_norm(t) for t in _read(PENDING).get("declined") or [] if isinstance(t, str)}
    added = []
    for key, (text, issues) in sorted(seen.items()):
        if len(issues) < min_issues or key in known or _refusal(text, "friction"):
            continue
        entry = {"id": _next_id("LP-", PENDING), "rule": text, "category": "process",
                 "applies": "always", "source": "friction", "issue": sorted(issues)[0],
                 "created": datetime.date.today().isoformat()}
        pending.append(entry)
        added.append(entry)
        _save(PENDING, pending)
    return added


def cmd_retro_lessons(args):
    added = propose_from_friction(os.path.join(_dir(), "work"))
    if not added:
        print("compass retro --lessons: no friction recurs in three issues that is "
              "not already a lesson or a proposal.")
        return 0
    print(f"compass retro --lessons: {len(added)} proposal(s) pending acceptance:")
    for e in added:
        print(f"  {e['id']}  {e['rule']}")
    print("Accept one with `compass lesson accept <id>`; nothing is a lesson until then.")
    return 0


def register(sub):
    """Add `compass lesson` and its subcommands to the top-level parser."""
    p = sub.add_parser("lesson", help="record this project's lessons for later sessions")
    subs = p.add_subparsers(dest="subcmd", required=True)

    def _rule_args(q, with_source):
        q.add_argument("rule", help="one sentence")
        q.add_argument("--category", choices=CATEGORIES, default="process")
        q.add_argument("--applies", choices=APPLIES, default="always",
                       help="always: injected each session; on_topic: stored, not yet surfaced")
        q.add_argument("--issue", metavar="SLUG", help="the issue it came from")
        if with_source:
            q.add_argument("--source", choices=SOURCES, default="human")

    add = subs.add_parser("add", help="record a lesson now; who added it comes from git config")
    _rule_args(add, True)
    add.set_defaults(func=cmd_lesson_add, output_kind="hand-off")
    pro = subs.add_parser("propose", help="hold a lesson for acceptance")
    _rule_args(pro, False)
    pro.set_defaults(func=cmd_lesson_propose, output_kind="hand-off")
    acc = subs.add_parser("accept", help="turn a pending proposal into a lesson")
    acc.add_argument("id", help="the proposal's LP- id")
    acc.set_defaults(func=cmd_lesson_accept, output_kind="hand-off")
    lst = subs.add_parser("list", help="each lesson and each pending proposal")
    lst.set_defaults(func=cmd_lesson_list, output_kind="hand-off")
    dec = subs.add_parser("decline", help="drop a pending proposal; retro will not propose it again")
    dec.add_argument("id", help="the proposal's LP- id")
    dec.set_defaults(func=cmd_lesson_decline, output_kind="hand-off")
    rem = subs.add_parser("remove", help="delete one lesson")
    rem.add_argument("id", help="the lesson's LS- id")
    rem.set_defaults(func=cmd_lesson_remove, output_kind="hand-off")
