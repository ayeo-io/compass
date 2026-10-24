# compass_pkg.delegations - a person's standing approval for a named agent
"""Delegations of approvals to one named agent, for a stated time and scope
(ADR-069).

A delegation is a file, `.compass/delegations/DL-<n>.yml`, written only by the
prompt hook from a typed `/compass:delegate` (`handle_delegate`). No CLI verb
writes one. It names:

It is typed with flags, each optional and in any order (`parse_flags`):
`/compass:delegate [--agent <name>] [--until <time>] [--on <issues>]
[--for <forms>] [--max <n>]`. A file written now has `format: 2` and names:

- who it covers: one agent, exactly as Claude Code reports it, plugin prefix
  included (`compass:architect`), or `main` for the session's main agent
  (`--agent`; `any` is refused); with no `--agent`, the agents of the typing
  session (`covers_session`);
- an end time (`--until`), in the future, with no upper limit; with none, it
  lasts until revoked;
- the issues it covers (`--on`), each at the generation it had when the
  delegation was made; with none, every issue at any generation;
- the forms it covers: `checks`, `documents`, `checkpoints`, `decisions`,
  `check:<id>`, and `g5` only when typed (default: the first four);
- optionally `max_uses`.

A file with no `format` is a 7.0.0 file. It is read by the 7.0.0 rules: a
missing `until` or `issues` grants nothing, and `labels` is read but never
written. No limit is put on how many are in force.

A delegation that covers `g5` takes effect
only when the person types back a code the hook showed them in its block
message (`confirm`), because a prompt suggestion accepted with Tab lets the
model word the first command (measured on Claude Code 2.1.300; the owner's
answer of 2026-10-15). The code is 64 bits, 16 hex characters shown in
groups of four, so its salted hash cannot be searched within the
confirmation window. Only the hash is stored. Claude Code also writes the
block message to the session transcript (measured on 2.1.301), so the
pre-tool hook refuses the agent's tools on the transcript and on this folder
(`approval_guard`).

Each typed `/compass:delegate` is used once: a prompt id that a delegation,
or a delegation waiting for its code, already holds is refused.

The named agent approves with `compass evidence approve <form> --delegated
--as <agent>` (`authorise`, then `record_use`). The record's `approver` is the
person who delegated; it also holds `approved_by_agent`, `delegation` and
`via: delegation`. Each use writes a line to the issue's devlog.
`/compass:revoke` ends delegations early (`handle_revoke`). A delegation never
covers delegation: the agent cannot create, extend or revoke one, or reject an
approval.

The pre-tool hook refuses the agent's edit tools on these files and checks a
delegated call's caller (`approval_guard`). A process running as the same
operating system user can still write them, as ADR-069 decision 8 states.
"""
# DEPENDENCY: standard library (datetime, hashlib, os, re, secrets); compass_pkg.
# approvals, atomic_io, core, prompt_approval (the hook's result types).
from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import re
import secrets

from compass_pkg import approvals, atomic_io
from compass_pkg.core import CompassError, load_manifest, load_yaml

FOLDER = "delegations"
FORMAT = 2
CONFIRM_MINUTES = 10
#: The confirmation code's length in bytes: 64 bits, 16 hex characters.
CODE_BYTES = 8
DEFAULT_FORMS = ("checks", "documents", "checkpoints", "decisions")
FORMS = ("g5",) + DEFAULT_FORMS
#: The words of the old positional form, which `parse_flags` refuses.
KEYWORDS = ("until", "on", "for", "labels", "max")
FLAGS = ("--agent", "--until", "--on", "--for", "--max")
FLAG_FORM = ("/compass:delegate [--agent <name>] [--until <time>] [--on <issues>] "
             "[--for <forms>] [--max <n>]")
#: The form word that covers each subject form of an approval.
COVERS = {"guardrail": "g5", "check": "checks", "artifact": "documents",
          "checkpoint": "checkpoints", "decisions": "decisions"}
WORDS = {"g5": "the guardrail 5 sign-off", "checks": "human checks",
         "documents": "documents", "checkpoints": "checkpoints",
         "decisions": "decisions taken for you"}
VERB = "compass evidence approve"


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


def _iso(when):
    return when.astimezone(datetime.timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z")


def _parse_iso(text):
    return datetime.datetime.fromisoformat(str(text).replace("Z", "+00:00"))


def _local(when):
    return when.astimezone().strftime("%Y-%m-%d %H:%M %Z").strip()


def folder(compass_dir):
    return os.path.join(compass_dir, FOLDER)


@contextlib.contextmanager
def _lock(compass_dir):
    os.makedirs(folder(compass_dir), exist_ok=True)
    with atomic_io.locked(os.path.join(folder(compass_dir), approvals.LOCK)):
        yield


#: The delegation lock, for a caller that also holds an issue's approval lock.
locked = _lock


def _write(path, body):
    import yaml
    atomic_io.atomic_write_text(path, yaml.safe_dump(body, sort_keys=False))


def all_delegations(compass_dir):
    found = []
    where = folder(compass_dir)
    if os.path.isdir(where):
        for name in sorted(os.listdir(where)):
            if re.fullmatch(r"DL-\d+\.yml", name):
                try:
                    body = load_yaml(os.path.join(where, name))
                except CompassError:
                    continue
                if isinstance(body, dict):
                    found.append(body)
    return sorted(found, key=lambda d: int(str(d.get("id", "DL-0"))[3:] or 0))


def _is_format_2(delegation):
    return delegation.get("format") == FORMAT


def ended(delegation, now=None):
    """Why a delegation is not in force, or None when it is."""
    now = now or _now()
    if delegation.get("revoked_at"):
        return f"{delegation.get('id')} was revoked at {delegation['revoked_at']}"
    # No end time means until revoked, in a format 2 file only: in a 7.0.0 file a
    # missing `until` is damage and grants nothing.
    if not (_is_format_2(delegation) and delegation.get("until") is None):
        try:
            until = _parse_iso(delegation.get("until"))
        except (TypeError, ValueError):
            return f"{delegation.get('id')} has no readable end time"
        if until <= now:
            return f"{delegation.get('id')} ended at {delegation.get('until')}"
    cap = delegation.get("max_uses")
    if cap and int(delegation.get("uses") or 0) >= int(cap):
        return f"{delegation.get('id')} reached its max of {cap} use(s)"
    return None


def in_force(compass_dir, now=None):
    return [d for d in all_delegations(compass_dir) if ended(d, now) is None]


def _covers_words(forms):
    return ", ".join(WORDS.get(f, f.replace("check:", "the human check ")) for f in forms)


# --- /compass:delegate ----------------------------------------------------------------------

def _refused(text):
    from compass_pkg.prompt_approval import Refused
    return Refused(f"Compass: {text} Nothing was written.")


def _end_time(text, now):
    local = now.astimezone()
    if re.fullmatch(r"\d{1,2}:\d{2}", text):
        hour, minute = (int(x) for x in text.split(":"))
        if hour > 23 or minute > 59:
            raise _refused(f"'{text}' is not an end time.")
        # A wall-clock time is read in the machine's time zone on that day, so a
        # day that changes to or from summer time still ends at the time typed.
        when = local.replace(tzinfo=None, hour=hour, minute=minute, second=0,
                             microsecond=0)
        if when.astimezone() <= local:
            when += datetime.timedelta(days=1)
        return when.astimezone()
    try:
        when = datetime.datetime.fromisoformat(text)
    except ValueError:
        raise _refused(f"'{text}' is not an end time. Give one as HH:MM or "
                       f"YYYY-MM-DDTHH:MM.") from None
    return when if when.tzinfo else when.astimezone()


def parse_flags(words):
    """The flags of `/compass:delegate`, as `{name: text}` with the dashes cut
    off, from words already split on white space. Case matters. A word in a
    value position is a value unless it starts with `--`, so `--max -1` is
    refused by the `--max` check and `--agent --until 08:00` as a flag with no
    value. Refuses the old positional form, `--labels`, an unknown flag, a flag
    given twice, `--flag=value` and a stray word."""
    if words and not words[0].startswith("-") and any(w in KEYWORDS for w in words[1:]):
        raise _refused(f"the form '/compass:delegate <agent> until <time> ...' is no longer "
                       f"used. Type {FLAG_FORM}.")
    found = {}
    i = 0
    while i < len(words):
        word = words[i]
        if not word.startswith("-"):
            raise _refused(f"'{word}' belongs to no flag. Type {FLAG_FORM}.")
        if word.startswith("--") and "=" in word:
            name, _, value = word.partition("=")
            raise _refused(f"'{word}' joins a flag to its value with '='. Write "
                           f"'{name} {value}' instead.")
        if word == "--labels":
            raise _refused("--labels is no longer a flag. Name the issues with "
                           "--on <issues>.")
        if word not in FLAGS:
            raise _refused(f"'{word}' is not a flag of /compass:delegate. Type {FLAG_FORM}.")
        if word[2:] in found:
            raise _refused(f"{word} is given twice.")
        if i + 1 >= len(words) or words[i + 1].startswith("--"):
            raise _refused(f"{word} needs a value. Type {FLAG_FORM}.")
        found[word[2:]] = words[i + 1]
        i += 2
    return found


def _issues_named(slugs, session):
    """`{slug: generation}` for the issues `--on` names, each looked up in every
    worktree of the repository. Refuses a name that is not one folder name, an
    issue no worktree holds (naming the folders searched) and an issue that two
    worktrees hold (naming both)."""
    from compass_pkg import worktree_lookup
    for slug in slugs:
        if not slug or slug in (".", "..") or "/" in slug or "\\" in slug:
            raise _refused(f"'{slug}', named after --on, is not the name of one issue "
                           f"folder.")
    listing = worktree_lookup.list_worktrees(session.project)
    issues = {}
    for slug in slugs:
        try:
            task_dir = worktree_lookup.find_issue(listing, slug)
        except worktree_lookup.HeldTwice as exc:
            raise _refused(f"'{slug}', named after --on, is held by more than one "
                           f"worktree: {' and '.join(exc.folders)}. Compass cannot tell "
                           f"which one is meant; remove or rename one.") from None
        except worktree_lookup.NotFound as exc:
            note = f" {exc.note[0].upper()}{exc.note[1:]}." if exc.note else ""
            raise _refused(f"'{slug}', named after --on, is in none of the work folders "
                           f"searched: {', '.join(exc.searched)}.{note}") from None
        task, _ = load_manifest(task_dir)
        issues[slug] = task.get("generation")
    return issues


def parse(args, session, now):
    """The delegation `/compass:delegate <args>` asks for. Refuses anything
    outside the limits."""
    found = parse_flags(args.split())
    agent = found.get("agent")
    if agent is not None and agent.lower() == "any":
        raise _refused("a delegation names one agent, and 'any' is refused, so that each "
                       "approval names who made it.")
    if agent is None and not session.session_id:
        raise _refused("Compass cannot name this session, so it cannot cover this "
                       "session's agents. Type --agent <name> to name an agent instead.")
    until = None
    if "until" in found:
        until = _end_time(found["until"], now)
        if until <= now:
            raise _refused(f"the end time '{found['until']}' has passed ({_local(until)}).")
    forms = found.get("for", ",".join(DEFAULT_FORMS)).split(",")
    for form in forms:
        if form not in FORMS and not re.fullmatch(r"check:[\w.-]+", form):
            raise _refused(f"'{form}' is not a form a delegation covers; use g5, checks, "
                           f"documents, checkpoints, decisions or check:<id>.")
    issues = _issues_named(found["on"].split(","), session) if "on" in found else {}
    cap = None
    if "max" in found:
        if not found["max"].isdigit() or int(found["max"]) < 1:
            raise _refused(f"--max takes a whole number of approvals, at least 1, not "
                           f"'{found['max']}'.")
        cap = int(found["max"])
    body = {"format": FORMAT, "delegated_by": session.approver, "role": session.role,
            "approver_source": session.approver_source, "created_at": _iso(now)}
    if agent is not None:
        body["agent"] = agent
    else:
        body["covers_session"] = session.session_id
    if until is not None:
        body["until"] = _iso(until)
    if issues:
        body["issues"] = issues
    body["forms"] = forms
    if cap is not None:
        body["max_uses"] = cap
    body.update(uses=0, created_via="prompt", session_id=session.session_id,
                prompt_id=session.prompt_id)
    return body


def _hash(salt, code):
    return hashlib.sha256(f"{salt}:{code}".encode("utf-8")).hexdigest()


def _confirm_path(compass_dir, session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "no-session")
    return os.path.join(folder(compass_dir), f"confirm-{safe}.yml")


def _write_delegation(compass_dir, body):
    existing = [int(str(d.get("id"))[3:]) for d in all_delegations(compass_dir)
                if str(d.get("id", "")).startswith("DL-")]
    number = max(existing + [0]) + 1
    body = dict({"id": f"DL-{number}"}, **body, nonce=secrets.token_hex(16))
    _write(os.path.join(folder(compass_dir), f"DL-{number}.yml"), body)
    return body


def _who(body):
    """Who a delegation covers, as the person reads it."""
    return body["agent"] if body.get("agent") else "this session's agents"


def _until_words(body):
    """When a delegation ends, as the person reads it."""
    if body.get("until") is None:
        return "until you type /compass:revoke"
    return f"until {_local(_parse_iso(body['until']))}"


def _confirmation(body):
    from compass_pkg.prompt_approval import HookResult
    issues = (", ".join(body["issues"]) if body.get("issues")
              else "every issue in the repository's worktrees")
    covers = _covers_words(body["forms"])
    who = _who(body)
    if "g5" in body["forms"]:
        g5 = (f"{who} may sign off irreversible work, such as an archive "
              f"migration or a release tag, {_until_words(body)}")
    else:
        g5 = "not the guardrail 5 sign-off"
    extra = ""
    if body.get("labels"):
        extra += f"; only issues labeled {', '.join(body['labels'])}"
    if body.get("max_uses"):
        extra += f"; at most {body['max_uses']} approval(s)"
    if body.get("agent"):
        scope = (f"{body['agent']} approves in any session. The other agents of this "
                 f"session are not covered.")
        use = f"Only {body['agent']} may use it"
        name = body["agent"]
    else:
        scope = ("The agents of other sessions are not covered; --agent <name> covers "
                 "that agent in any session.")
        use = "Only the agents of this session may use it"
        name = "<your own agent name>"
    return HookResult(
        False,
        f"Compass: {body['id']} lets {who} approve for {body['delegated_by']} "
        f"{_until_words(body)} on {issues}: {covers}; {g5}{extra}. {scope} Type "
        f"/compass:revoke to end it early.",
        f"The person delegated approvals to {who} as {body['id']} {_until_words(body)}, "
        f"covering {covers} on {issues}. {use}, with `compass evidence approve ... "
        f"--delegated --as {name}`, where {name} is the agent's own name: `main` for the "
        f"main agent.")


def _refuse_used_prompt(compass_dir, prompt_id):
    """Refuse a prompt id that a delegation file, or a delegation waiting for
    its code, already holds, so a replayed command writes nothing."""
    from compass_pkg.prompt_approval import Refused
    for body in all_delegations(compass_dir):
        if prompt_id in (body.get("prompt_id"), body.get("requested_prompt_id")):
            raise Refused(f"Compass: this typed command was already answered "
                          f"({body.get('id')}). Nothing more was written.")
    where = folder(compass_dir)
    for name in sorted(os.listdir(where)) if os.path.isdir(where) else []:
        if not re.fullmatch(r"confirm-.+\.yml", name):
            continue
        try:
            waiting = load_yaml(os.path.join(where, name))
        except CompassError:
            continue
        held = (waiting.get("delegation") or {}) if isinstance(waiting, dict) else {}
        if isinstance(held, dict) and held.get("prompt_id") == prompt_id:
            raise Refused("Compass: this typed command was already answered (a delegation "
                          "waits for its code). Nothing more was written.")


def _show_code(code):
    return "-".join(code[i:i + 4] for i in range(0, len(code), 4))


def _typed_code(text):
    """The code as typed, without hyphens and in lower case, or '' when it is
    not 16 hex characters."""
    code = str(text or "").replace("-", "").lower()
    return code if re.fullmatch(r"[0-9a-f]{%d}" % (CODE_BYTES * 2), code) else ""


def handle_delegate(session):
    compass_dir = session.compass_dir
    now = _now()
    words = session.args.split()
    with _lock(compass_dir):
        _refuse_used_prompt(compass_dir, session.prompt_id)
        if words[:1] == ["confirm"]:
            return _confirm(compass_dir, session, words[1] if len(words) > 1 else "", now)
        body = parse(session.args, session, now)
        if "g5" in body["forms"]:
            code = secrets.token_hex(CODE_BYTES)
            salt = secrets.token_hex(8)
            _write(_confirm_path(compass_dir, session.session_id),
                   {"session_id": session.session_id, "created_at": _iso(now),
                    "salt": salt, "code_hash": _hash(salt, code), "delegation": body})
            from compass_pkg.prompt_approval import Refused
            raise Refused(
                f"Compass: this delegation would let {_who(body)} sign off irreversible "
                f"work, such as an archive migration or a release tag, "
                f"{_until_words(body)}. Nothing is written until you "
                f"confirm. To confirm, type /compass:delegate confirm {_show_code(code)} in this "
                f"session within {CONFIRM_MINUTES} minutes.")
        return _confirmation(_write_delegation(compass_dir, body))


def _confirm(compass_dir, session, code, now):
    path = _confirm_path(compass_dir, session.session_id)
    # A code that is not 16 hex characters is refused before its hash is
    # compared, so a code from a confirmation file an earlier version wrote,
    # 8 characters long, never confirms.
    code = _typed_code(code)
    try:
        waiting = load_yaml(path) if os.path.isfile(path) else None
    except CompassError:
        waiting = None
    if (not isinstance(waiting, dict) or not code
            or waiting.get("session_id") != session.session_id
            or waiting.get("code_hash") != _hash(waiting.get("salt"), code)):
        raise _refused("that code does not match a delegation waiting in this session.")
    if now - _parse_iso(waiting["created_at"]) > datetime.timedelta(minutes=CONFIRM_MINUTES):
        os.remove(path)
        raise _refused(f"the code is more than {CONFIRM_MINUTES} minutes old; type the "
                       f"/compass:delegate command again.")
    os.remove(path)
    body = dict(waiting["delegation"], prompt_id=session.prompt_id,
                requested_prompt_id=waiting["delegation"].get("prompt_id"))
    if body.get("until") is not None and _parse_iso(body["until"]) <= now:
        raise _refused("the end time of that delegation has passed.")
    return _confirmation(_write_delegation(compass_dir, body))


# --- /compass:revoke ------------------------------------------------------------------------

def _covered(delegation, session_id):
    """Who a delegation covers, relative to the session that reads it."""
    if delegation.get("agent"):
        return f"{delegation['agent']} in every session"
    if delegation.get("covers_session") and delegation["covers_session"] == session_id:
        return "this session"
    return "another session"


def handle_revoke(session):
    from compass_pkg.prompt_approval import HookResult
    compass_dir = session.compass_dir
    now = _now()
    named = session.args.split()[0] if session.args.split() else ""
    with _lock(compass_dir):
        live = in_force(compass_dir, now)
        if named:
            live = [d for d in live if d.get("id") == named]
        if not live:
            raise _refused(f"no delegation{' ' + named if named else ''} is in force.")
        for body in live:
            body.update(revoked_by=session.approver, revoked_at=_iso(now))
            _write(os.path.join(folder(compass_dir), f"{body['id']}.yml"), body)
    ids = ", ".join(d["id"] for d in live)
    covered = "; ".join(f"{d['id']} covered {_covered(d, session.session_id)}" for d in live)
    return HookResult(False, f"Compass: revoked {ids}; no agent may approve under "
                             f"{'it' if len(live) == 1 else 'them'} from now on. "
                             f"{covered}.",
                      f"The person revoked {ids}. Do not run a delegated approval under "
                      f"{'it' if len(live) == 1 else 'them'}.")


# --- a delegated approval -------------------------------------------------------------------

def _labels(task):
    return set((task.get("assessment") or {}).get("labels") or [])


def _why_not(delegation, agent, slug, task, form, value, now, session_id=""):
    name = delegation.get("id")
    session_scope = (_is_format_2(delegation) and not delegation.get("agent")
                     and bool(delegation.get("covers_session")))
    if not session_scope and delegation.get("agent") != agent:
        return None
    if delegation.get("created_via") != "prompt":
        return (f"{name} was not written by a typed /compass:delegate (created_via: "
                f"{delegation.get('created_via')})")
    # A session delegation covers the agents of the session it was typed in, as
    # the pre-tool hook's ticket reports it, and no other.
    if session_scope and not (session_id and delegation["covers_session"] == session_id):
        return f"{name} covers only the agents of the session it was typed in"
    reason = ended(delegation, now)
    if reason:
        return reason
    issues = delegation.get("issues") or {}
    # A format 2 file that names no issue covers every issue, at any generation.
    if not (_is_format_2(delegation) and not issues):
        if slug not in issues:
            return f"{name} covers {', '.join(issues) or 'no issue'}, not {slug}"
        if issues[slug] != task.get("generation"):
            return (f"{name} covers {slug} at generation {issues[slug]}, and it is at "
                    f"generation {task.get('generation')}")
    forms = delegation.get("forms") or []
    if COVERS[form] not in forms and not (form == "check" and f"check:{value}" in forms):
        return f"{name} covers {_covers_words(forms)}, not {WORDS[COVERS[form]]}"
    if delegation.get("labels") and not (_labels(task) & set(delegation["labels"])):
        return f"{name} covers only issues labeled {', '.join(delegation['labels'])}"
    return ""


def authorise(task_dir, form, value, agent, session_id="", compass_dir=None):
    """The delegation in force that lets `agent`, in session `session_id`, record
    this approval. `compass_dir` is the common store's `.compass/` folder; it
    defaults to the issue's own, as in a project with one checkout. Raises
    CompassError naming why none does."""
    compass_dir = compass_dir or os.path.dirname(os.path.dirname(task_dir))
    slug = os.path.basename(os.path.normpath(task_dir))
    task, _ = load_manifest(task_dir)
    now = _now()
    reasons = []
    for delegation in all_delegations(compass_dir):
        why = _why_not(delegation, agent, slug, task, form, value, now, session_id)
        if why == "":
            return delegation
        if why:
            reasons.append(why)
    if not reasons:
        raise CompassError(f"{VERB}: no delegation in force names {agent}. Ask the person "
                           f"with `compass evidence request` and stop. Nothing was written.")
    raise CompassError(f"{VERB}: {'; '.join(reasons)}. Ask the person with `compass "
                       f"evidence request` and stop. Nothing was written.")


def record_use(task_dir, delegation, agent, done, subject, compass_dir=None):
    """Count the use on the delegation, index the record in the delegation file
    (`records`: the issue, its folder, the record ids and the time, so a summary
    reads only the folders that hold a record) and write the devlog's audit
    line. `compass_dir` is the common store's `.compass/` folder."""
    compass_dir = compass_dir or os.path.dirname(os.path.dirname(task_dir))
    path = os.path.join(folder(compass_dir), f"{delegation['id']}.yml")
    body = load_yaml(path)
    body["uses"] = int(body.get("uses") or 0) + 1
    body.setdefault("records", []).append(
        {"issue": os.path.basename(os.path.normpath(task_dir)), "folder": str(task_dir),
         "ids": list(done.evidence_ids), "at": _iso(_now())})
    _write(path, body)
    line = (f"- {_iso(_now())} - {', '.join(done.evidence_ids)} recorded by {agent} under "
            f"{delegation['id']} for {delegation.get('delegated_by')}: {subject}.\n")
    devlog = os.path.join(task_dir, "devlog.md")
    with open(devlog, "a", encoding="utf-8") as fh:
        fh.write(line)


# --- the person's review of delegated approvals ----------------------------------------------

#: The record that withdraws a guardrail 5 sign-off made under a delegation.
WITHDRAWAL = "approval-withdrawal"
#: The record types an approval under a delegation can write.
DELEGATED_TYPES = ("human-approval", "artifact-approval", "checkpoint-approval")


def _issue_dirs(compass_dir):
    work = os.path.join(compass_dir, "work")
    if not os.path.isdir(work):
        return []
    from compass_pkg.core import manifest_path
    return [os.path.join(work, name) for name in sorted(os.listdir(work))
            if os.path.isfile(manifest_path(os.path.join(work, name)))]


def _waiting(record):
    return (isinstance(record, dict) and record.get("via") == "delegation"
            and record.get("type") in DELEGATED_TYPES and not record.get("reviewed_at"))


def _store_compass(compass_dir):
    """The common store's `.compass/` folder for the project that holds
    `compass_dir`, or None when there is no store."""
    from compass_pkg import worktree_lookup
    store = worktree_lookup.common_store(os.path.dirname(compass_dir))
    return None if store.folder is None else os.path.dirname(store.folder)


def _moved(slug, compass_dir):
    """The folder of an indexed issue that was moved: found again by its slug."""
    from compass_pkg import worktree_lookup
    try:
        return worktree_lookup.find_issue(
            worktree_lookup.list_worktrees(os.path.dirname(compass_dir)), str(slug))
    except (worktree_lookup.NotFound, worktree_lookup.HeldTwice):
        return None


def _want(wanted, folder, ids):
    """Note that `folder` is read for the records `ids`, or for every waiting
    record when `ids` is None."""
    key = os.path.realpath(folder)
    old = wanted.get(key)
    if key in wanted and (old[1] is None or ids is None):
        wanted[key] = (old[0], None)
    elif key in wanted:
        wanted[key] = (old[0], old[1] | set(ids))
    else:
        wanted[key] = (folder, None if ids is None else set(ids))


def unreviewed(compass_dir):
    """`[(folder, manifest, record)]` for each approval made under a delegation
    that the person has not marked reviewed, in any worktree. Only the folders
    the delegations' `records` index names are read, plus the issues a 7.0.0
    file names, so a project with no delegation file starts no git process
    from a main checkout and opens no manifest: the summary runs on every
    prompt."""
    store = _store_compass(compass_dir)
    if store is None:
        return []
    wanted = {}
    for delegation in all_delegations(store):
        for entry in delegation.get("records") or []:
            if not isinstance(entry, dict):
                continue
            folder = entry.get("folder")
            if not (folder and os.path.isdir(folder)) and entry.get("issue"):
                folder = _moved(entry["issue"], compass_dir)
            if folder:
                _want(wanted, folder, entry.get("ids") or [])
        if not _is_format_2(delegation):
            for slug in delegation.get("issues") or {}:
                folder = os.path.join(compass_dir, "work", str(slug))
                if os.path.isdir(folder):
                    _want(wanted, folder, None)
    found = []
    for folder, ids in sorted(wanted.values(), key=lambda item: item[0]):
        try:
            task, _ = load_manifest(folder)
        except CompassError:
            continue
        found += [(folder, task, r) for r in task.get("evidence") or []
                  if _waiting(r) and (ids is None or r.get("id") in ids)]
    return found


def _subject(record):
    if record.get("type") == "artifact-approval" and record.get("artifact"):
        return f"document '{record['artifact']}'"
    if record.get("type") == "artifact-approval" and record.get("decisions"):
        return "the decisions taken for you"
    if record.get("type") == "checkpoint-approval":
        return f"the {record.get('checkpoint')} checkpoint"
    if record.get("check"):
        return f"human check '{record['check']}'"
    return "guardrail 5 sign-off"


def _self_written(task, record):
    """True when the agent approved a document registered in the same session."""
    if record.get("type") != "artifact-approval" or not record.get("artifact"):
        return False
    entry = next((a for a in task.get("artifacts") or []
                  if isinstance(a, dict) and a.get("kind") == record["artifact"]), {})
    session = record.get("session_id")
    return bool(session) and entry.get("registered_session") == session


def _plural(number, word):
    return f"{number} {word}" if number == 1 else f"{number} {word}s"


def session_start_lines(project, session_id, source, now=None):
    """What session start tells the person about delegations in force with no
    end time: one line each, with its age in whole days, who it covers, whether
    it covers the session that is starting and how many approvals it has given.
    After `/clear`, a line also says that a session delegation of the earlier
    session no longer covers this one: `/clear` gives a new session id and no
    field names the old one, so Compass cannot say a session ended, only that
    it is not this one. '' when there is none."""
    now = now or _now()
    store = _store_compass(os.path.join(project, ".compass"))
    if store is None:
        return ""
    listed = [d for d in all_delegations(store)
              if _is_format_2(d) and d.get("until") is None and ended(d, now) is None]
    if not listed:
        return ""
    lines = ["Compass: delegations in force with no end time:"]
    for d in listed:
        name = d.get("id")
        try:
            days = max(0, (now - _parse_iso(d.get("created_at"))).days)
        except (TypeError, ValueError):
            days = 0
        tail = (f"In force for {_plural(days, 'day')}; "
                f"{_plural(int(d.get('uses') or 0), 'approval')}.")
        if d.get("agent"):
            text = (f"{name} has no end time and covers {d['agent']} in every session, "
                    f"including this one. It stays in force until you type "
                    f"/compass:revoke {name}.")
        elif d.get("covers_session") and d["covers_session"] == session_id:
            text = (f"{name} has no end time and covers the agents of the session it was "
                    f"typed in. That is this session. It stays in force until you type "
                    f"/compass:revoke {name}.")
        else:
            text = (f"{name} has no end time and covers the agents of the session it was "
                    f"typed in. That is not this session. Compass cannot tell whether that "
                    f"session is still open, so it covers that session's agents until you "
                    f"type /compass:revoke {name}.")
        lines.append(f"  {text} {tail}")
    if source == "clear" and any(not d.get("agent") for d in listed):
        lines.append("/clear started a new session. A delegation typed before /clear "
                     "without --agent does not cover this session. Type /compass:delegate "
                     "to cover it.")
    return "\n".join(lines)


def _project_of(task_dir):
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))


def _summary_text(rows):
    lines = [f"Compass: {len(rows)} approval(s) made under a delegation wait for your "
             f"review:"]
    for task_dir, task, record in rows:
        flag = (" - the agent approved a document it wrote in the same session"
                if _self_written(task, record) else "")
        lines.append(f"  {record.get('id')} - {_subject(record)}, issue "
                     f"{os.path.basename(task_dir)} ({_project_of(task_dir)}), by "
                     f"{record.get('approved_by_agent')} under {record.get('delegation')} "
                     f"at {record.get('timestamp')}{flag}")
    lines.append("Type /compass:approve to mark them reviewed, or /compass:reject <record id> "
                 "<reason> to overrule one.")
    return "\n".join(lines)


def review_summary(compass_dir):
    """The display-only summary of delegated approvals not yet reviewed, or ''.
    It never writes a record."""
    rows = unreviewed(compass_dir)
    return _summary_text(rows) if rows else ""


def _row_digest(task, record):
    """The digest of what the person is shown of one row, so a record changed
    after it was shown is not marked reviewed."""
    shown = [record.get("id"), _subject(record), record.get("approved_by_agent"),
             record.get("delegation"), str(record.get("timestamp")),
             _self_written(task, record)]
    return hashlib.sha256(json.dumps(shown).encode("utf-8")).hexdigest()


#: The shown list keeps this many summaries for each session: the latest, and the
#: one before it, because the prompt hook of a typed command can run after the
#: summary hook of the same prompt.
SHOWN_KEPT = 2


def _shown_path(store_compass, session_id):
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)
    return os.path.join(folder(store_compass), "shown", f"{safe}.json")


def _read_shown(store_compass, session_id):
    try:
        with open(_shown_path(store_compass, session_id), encoding="utf-8") as fh:
            body = json.load(fh)
    except (OSError, ValueError):
        return []
    entries = body.get("entries") if isinstance(body, dict) else None
    return [e for e in entries or [] if isinstance(e, dict)]


def summary_for_hook(project, session_id, prompt_id):
    """What a summary hook prints for the session `session_id`, and the record of
    what it showed: the store's `shown/<session>.json` gets one entry holding
    the prompt id, the time and each row's folder, issue, record id and digest.
    Nothing is written when there is nothing to show, or when the hook input
    names no session. A write that fails leaves the rows unrecorded, so the
    next summary shows them again."""
    compass_dir = os.path.join(project, ".compass")
    rows = unreviewed(compass_dir)
    if not rows:
        return ""
    if session_id:
        try:
            store = _store_compass(compass_dir)
            entries = _read_shown(store, session_id)[-(SHOWN_KEPT - 1):]
            entries.append({"prompt_id": prompt_id or "", "shown_at": _iso(_now()),
                            "records": [{"folder": folder, "issue": os.path.basename(folder),
                                         "id": record.get("id"),
                                         "digest": _row_digest(task, record)}
                                        for folder, task, record in rows]})
            path = _shown_path(store, session_id)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            atomic_io.atomic_write_text(path, json.dumps({"entries": entries}))
        except (OSError, TypeError):
            pass
    return _summary_text(rows)


def last_shown(compass_dir, session_id, prompt_id):
    """The latest summary shown in this session whose prompt id differs from
    `prompt_id`, or None. A summary shown for the prompt that holds the command
    does not count, whichever of the two hooks ran first."""
    store = _store_compass(compass_dir)
    if store is None or not session_id:
        return None
    for entry in reversed(_read_shown(store, session_id)):
        if entry.get("prompt_id", "") != (prompt_id or ""):
            return entry
    return None


def mark_reviewed(session, entry, held):
    """`/compass:approve` with no request pending: mark reviewed the rows of the
    summary `entry` that the session was shown, and only those whose record is
    still waiting and still shows what it showed (the digest). None when none is
    marked.

    `held` names the issue folders whose approval locks the caller holds,
    taken in one sorted order with the session's own (`approvals.lock_all`).
    Taking another lock here, while holding the session's own, let two
    sessions on two issues wait for each other for ever. A row outside `held`
    is left for the next `/compass:approve`; the review summary still shows
    it."""
    from compass_pkg.core import save_manifest
    from compass_pkg.prompt_approval import HookResult
    locked_dirs = {os.path.realpath(d) for d in held}
    by_folder = {}
    for item in (entry or {}).get("records") or []:
        by_folder.setdefault(item.get("folder"), []).append(item)
    stamp = _iso(_now())
    ids = []
    for folder_name, items in sorted(by_folder.items(), key=lambda kv: str(kv[0])):
        if not folder_name or os.path.realpath(folder_name) not in locked_dirs:
            continue
        try:
            task, path = load_manifest(folder_name)
        except CompassError:
            continue
        changed = False
        for item in items:
            record = next((r for r in task.get("evidence") or []
                           if isinstance(r, dict) and r.get("id") == item.get("id")), None)
            if _waiting(record) and _row_digest(task, record) == item.get("digest"):
                record.update(reviewed_by=session.approver, reviewed_at=stamp)
                ids.append(record["id"])
                changed = True
        if changed:
            save_manifest(task, path)
    if not ids:
        return None
    return HookResult(False, f"Compass: marked {len(ids)} delegated approval(s) reviewed by "
                             f"{session.approver}: {', '.join(ids)}.",
                      f"The person reviewed the delegated approvals {', '.join(ids)}.")


def overrule(session, args, where=""):
    """`/compass:reject <record id> <reason>`: overrule one approval made under
    a delegation. A check gets a `rejected` record, a document returns to
    draft, and a guardrail 5 sign-off gets an `approval-withdrawal` record.
    None of these reverses anything the agent already did."""
    from compass_pkg import approval_records
    from compass_pkg.core import save_manifest
    from compass_pkg.prompt_approval import HookResult, _send_back
    record_id, _, reason = args.partition(" ")
    reason = reason.strip()
    task, path = load_manifest(session.task_dir)
    evidence = [r for r in task.get("evidence") or [] if isinstance(r, dict)]
    record = next((r for r in evidence if r.get("id") == record_id), None)
    if record is None or record.get("via") != "delegation":
        raise _refused(f"{record_id} is not an approval made under a delegation on issue "
                       f"{session.slug}. /compass:reject <record id> overrules only those; "
                       f"answer a request with /compass:reject <n> <reason>.")
    if any(record_id in (r.get("overrules"), r.get("withdraws")) for r in evidence):
        raise _refused(f"{record_id} was already overruled.")
    subject = _subject(record)
    stamp = _iso(_now())
    record.update(reviewed_by=session.approver, reviewed_at=stamp)
    if record.get("type") == "human-approval" and approval_records.gives_g5(record):
        taken = {r.get("id") for r in evidence}
        number = 1
        while f"EV-WITHDRAWAL-{number}" in taken:
            number += 1
        written = f"EV-WITHDRAWAL-{number}"
        task.setdefault("evidence", []).append({
            "id": written, "type": WITHDRAWAL, "withdraws": record_id,
            "by": session.approver, "at": stamp, "reason": reason, "via": "prompt",
            "issue": session.slug, "generation": task.get("generation"),
            "session_id": session.session_id, "prompt_id": session.prompt_id})
        save_manifest(task, path)
    elif record.get("type") == "human-approval" and record.get("check"):
        provenance = {"via": "prompt", "host": "claude-code",
                      "session_id": session.session_id, "prompt_id": session.prompt_id,
                      "approver_source": session.approver_source, "overrules": record_id}
        if reason:
            provenance["reason"] = reason
        answer = approvals.Answer("check", record["check"], approval_records.REJECTED,
                                  session.approver, session.role,
                                  record.get("scope") or "", provenance)
        # Refuse before anything is saved, so a refusal writes nothing.
        approvals.record(session.task_dir, answer, save=False)
        save_manifest(task, path)
        written = ", ".join(approvals.record(session.task_dir, answer).evidence_ids)
    elif record.get("type") == "artifact-approval" and record.get("artifact"):
        save_manifest(task, path)
        _send_back(session, record["artifact"], reason)
        written = f"{record['artifact']} back to draft"
    else:
        raise _refused(f"{record_id} ({subject}) cannot be overruled with /compass:reject; "
                       f"reopen a decision with compass issue decision set.")
    said = f": {reason}" if reason else ""
    return HookResult(
        False,
        f"Compass: overruled {record_id} ({subject}) on issue {session.slug}{where} for "
        f"{session.approver}{said} - {written}. This records your disagreement; it does not reverse anything the "
        f"agent already did.",
        f"The person overruled {record_id} ({subject}){said}. Do not rely on that "
        f"approval; ask the person what should change.")
