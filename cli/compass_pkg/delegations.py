# compass_pkg.delegations - a person's standing approval for a named agent
"""Delegations of approvals to one named agent, for a stated time and scope
(ADR-069).

A delegation is a file, `.compass/delegations/DL-<n>.yml`, written only by the
prompt hook from a typed `/compass:delegate` (`handle_delegate`). No CLI verb
writes one. It names:

- one agent, exactly as Claude Code reports it, plugin prefix included
  (`compass:architect`), or `main` for the session's main agent; `any` is
  refused;
- an end time, required, in the future and at most 24 hours after creation;
- the issues it covers, each at the generation it had when the delegation was
  made (default: the session's issue);
- the forms it covers: `checks`, `documents`, `checkpoints`, `decisions`,
  `check:<id>`, and `g5` only when typed (default: the first four);
- optionally `labels` an issue must carry, and `max_uses`.

At most five are in force at once. A delegation that covers `g5` takes effect
only when the person types back a code the hook showed them in its block
message (`confirm`), because a prompt suggestion accepted with Tab lets the
model word the first command (U0; the owner's answer of 2026-10-15). Only a
hash of the code is stored.

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
import os
import re
import secrets

from compass_pkg import approvals, atomic_io
from compass_pkg.core import CompassError, load_manifest, load_yaml

FOLDER = "delegations"
MAX_HOURS = 24
MAX_IN_FORCE = 5
CONFIRM_MINUTES = 10
DEFAULT_FORMS = ("checks", "documents", "checkpoints", "decisions")
FORMS = ("g5",) + DEFAULT_FORMS
KEYWORDS = ("until", "on", "for", "labels", "max")
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


def ended(delegation, now=None):
    """Why a delegation is not in force, or None when it is."""
    now = now or _now()
    if delegation.get("revoked_at"):
        return f"{delegation.get('id')} was revoked at {delegation['revoked_at']}"
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
        when = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if when <= local:
            when += datetime.timedelta(days=1)
        return when
    try:
        when = datetime.datetime.fromisoformat(text)
    except ValueError:
        raise _refused(f"'{text}' is not an end time. Give one as HH:MM or "
                       f"YYYY-MM-DDTHH:MM.") from None
    return when if when.tzinfo else when.replace(tzinfo=local.tzinfo)


def parse(args, session, now):
    """The delegation `/compass:delegate <args>` asks for. Refuses anything
    outside the limits."""
    words = args.split()
    if not words:
        raise _refused("/compass:delegate needs an agent and an end time, such as "
                       "/compass:delegate compass:architect until 08:00.")
    agent, rest = words[0], words[1:]
    if agent.lower() == "any":
        raise _refused("a delegation names one agent; 'any' is refused, so that each "
                       "approval names who made it.")
    if agent in KEYWORDS or agent == "confirm":
        raise _refused("/compass:delegate needs the agent first, such as "
                       "/compass:delegate compass:architect until 08:00.")
    found = {}
    i = 0
    while i < len(rest):
        key = rest[i]
        if key not in KEYWORDS or i + 1 >= len(rest):
            if found.get("until") is not None and key not in KEYWORDS:
                raise _refused(f"the end time must be one value such as 08:00, not "
                               f"'{' '.join(rest[i - 1:])}'.")
            raise _refused(f"'{key}' is not part of /compass:delegate. It takes <agent> "
                           f"until <time> [on <issues>] [for <forms>] [labels <labels>] "
                           f"[max <n>].")
        found[key] = rest[i + 1]
        i += 2
    if "until" not in found:
        raise _refused("a delegation needs an end time: add until <HH:MM>, at most "
                       f"{MAX_HOURS} hours ahead.")
    until = _end_time(found["until"], now)
    if until <= now:
        raise _refused(f"the end time {_local(until)} has passed.")
    if until - now > datetime.timedelta(hours=MAX_HOURS):
        raise _refused(f"the end time {_local(until)} is more than {MAX_HOURS} hours "
                       f"ahead; a delegation lasts at most {MAX_HOURS} hours.")
    forms = found.get("for", ",".join(DEFAULT_FORMS)).split(",")
    for form in forms:
        if form not in FORMS and not re.fullmatch(r"check:[\w.-]+", form):
            raise _refused(f"'{form}' is not a form a delegation covers; use g5, checks, "
                           f"documents, checkpoints, decisions or check:<id>.")
    compass_dir = os.path.dirname(os.path.dirname(session.task_dir))
    issues = {}
    for slug in found.get("on", session.slug).split(","):
        task_dir = os.path.join(compass_dir, "work", slug)
        if not slug or "/" in slug or not os.path.isdir(task_dir):
            raise _refused(f"'{slug}' is not an issue in this project.")
        task, _ = load_manifest(task_dir)
        issues[slug] = task.get("generation")
    body = {"agent": agent, "delegated_by": session.approver, "role": session.role,
            "approver_source": session.approver_source, "created_at": _iso(now),
            "until": _iso(until), "issues": issues, "forms": forms}
    if found.get("labels"):
        body["labels"] = found["labels"].split(",")
    if found.get("max"):
        if not found["max"].isdigit() or int(found["max"]) < 1:
            raise _refused(f"max takes a whole number of approvals, not '{found['max']}'.")
        body["max_uses"] = int(found["max"])
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


def _confirmation(body):
    from compass_pkg.prompt_approval import HookResult
    until = _parse_iso(body["until"])
    issues = ", ".join(body["issues"])
    covers = _covers_words(body["forms"])
    if "g5" in body["forms"]:
        g5 = (f"{body['agent']} may sign off irreversible work, such as an archive "
              f"migration or a release tag, until {until.astimezone():%H:%M}")
    else:
        g5 = "not the guardrail 5 sign-off"
    extra = ""
    if body.get("labels"):
        extra += f"; only issues labelled {', '.join(body['labels'])}"
    if body.get("max_uses"):
        extra += f"; at most {body['max_uses']} approval(s)"
    return HookResult(
        False,
        f"Compass: {body['id']} lets {body['agent']} approve for {body['delegated_by']} "
        f"until {_local(until)} on {issues}: {covers}; {g5}{extra}. Type /compass:revoke "
        f"to end it early.",
        f"The person delegated approvals to {body['agent']} as {body['id']} until "
        f"{body['until']}, covering {covers} on {issues}. Only {body['agent']} may use "
        f"it, with `compass evidence approve ... --delegated --as {body['agent']}`.")


def handle_delegate(session):
    compass_dir = os.path.dirname(os.path.dirname(session.task_dir))
    now = _now()
    words = session.args.split()
    with _lock(compass_dir):
        if words[:1] == ["confirm"]:
            return _confirm(compass_dir, session, words[1] if len(words) > 1 else "", now)
        body = parse(session.args, session, now)
        if len(in_force(compass_dir, now)) >= MAX_IN_FORCE:
            raise _refused(f"five delegations are in force, the most allowed. Type "
                           f"/compass:revoke DL-<n> to end one first.")
        if "g5" in body["forms"]:
            code = secrets.token_hex(4)
            salt = secrets.token_hex(8)
            _write(_confirm_path(compass_dir, session.session_id),
                   {"session_id": session.session_id, "created_at": _iso(now),
                    "salt": salt, "code_hash": _hash(salt, code), "delegation": body})
            from compass_pkg.prompt_approval import Refused
            raise Refused(
                f"Compass: this delegation would let {body['agent']} sign off irreversible "
                f"work, such as an archive migration or a release tag, until "
                f"{_local(_parse_iso(body['until']))}. Nothing is written until you "
                f"confirm. To confirm, type /compass:delegate confirm {code} in this "
                f"session within {CONFIRM_MINUTES} minutes.")
        return _confirmation(_write_delegation(compass_dir, body))


def _confirm(compass_dir, session, code, now):
    path = _confirm_path(compass_dir, session.session_id)
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
    if len(in_force(compass_dir, now)) >= MAX_IN_FORCE:
        raise _refused("five delegations are in force, the most allowed.")
    os.remove(path)
    body = dict(waiting["delegation"], prompt_id=session.prompt_id)
    if _parse_iso(body["until"]) <= now:
        raise _refused("the end time of that delegation has passed.")
    return _confirmation(_write_delegation(compass_dir, body))


# --- /compass:revoke ------------------------------------------------------------------------

def handle_revoke(session):
    from compass_pkg.prompt_approval import HookResult
    compass_dir = os.path.dirname(os.path.dirname(session.task_dir))
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
    return HookResult(False, f"Compass: revoked {ids}; no agent may approve under "
                             f"{'it' if len(live) == 1 else 'them'} from now on.",
                      f"The person revoked {ids}. Do not run a delegated approval under "
                      f"{'it' if len(live) == 1 else 'them'}.")


# --- a delegated approval -------------------------------------------------------------------

def _labels(task):
    return set((task.get("assessment") or {}).get("labels") or [])


def _why_not(delegation, agent, slug, task, form, value, now):
    name = delegation.get("id")
    if delegation.get("agent") != agent:
        return None
    if delegation.get("created_via") != "prompt":
        return (f"{name} was not written by a typed /compass:delegate (created_via: "
                f"{delegation.get('created_via')})")
    reason = ended(delegation, now)
    if reason:
        return reason
    issues = delegation.get("issues") or {}
    if slug not in issues:
        return f"{name} covers {', '.join(issues) or 'no issue'}, not {slug}"
    if issues[slug] != task.get("generation"):
        return (f"{name} covers {slug} at generation {issues[slug]}, and it is at "
                f"generation {task.get('generation')}")
    forms = delegation.get("forms") or []
    if COVERS[form] not in forms and not (form == "check" and f"check:{value}" in forms):
        return f"{name} covers {_covers_words(forms)}, not {WORDS[COVERS[form]]}"
    if delegation.get("labels") and not (_labels(task) & set(delegation["labels"])):
        return f"{name} covers only issues labelled {', '.join(delegation['labels'])}"
    return ""


def authorise(task_dir, form, value, agent):
    """The delegation in force that lets `agent` record this approval.
    Raises CompassError naming why none does."""
    compass_dir = os.path.dirname(os.path.dirname(task_dir))
    slug = os.path.basename(os.path.normpath(task_dir))
    task, _ = load_manifest(task_dir)
    now = _now()
    reasons = []
    for delegation in all_delegations(compass_dir):
        why = _why_not(delegation, agent, slug, task, form, value, now)
        if why == "":
            return delegation
        if why:
            reasons.append(why)
    if not reasons:
        raise CompassError(f"{VERB}: no delegation in force names {agent}. Ask the person "
                           f"with `compass evidence request` and stop. Nothing was written.")
    raise CompassError(f"{VERB}: {'; '.join(reasons)}. Ask the person with `compass "
                       f"evidence request` and stop. Nothing was written.")


def record_use(task_dir, delegation, agent, done, subject):
    """Count the use on the delegation and write the devlog's audit line."""
    compass_dir = os.path.dirname(os.path.dirname(task_dir))
    path = os.path.join(folder(compass_dir), f"{delegation['id']}.yml")
    body = load_yaml(path)
    body["uses"] = int(body.get("uses") or 0) + 1
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
    return [os.path.join(work, name) for name in sorted(os.listdir(work))
            if os.path.isfile(os.path.join(work, name, "manifest.yml"))]


def _waiting(record):
    return (isinstance(record, dict) and record.get("via") == "delegation"
            and record.get("type") in DELEGATED_TYPES and not record.get("reviewed_at"))


def unreviewed(compass_dir):
    """`[(task_dir, task, record)]` for each approval made under a delegation
    that the person has not marked reviewed, across the project's issues."""
    found = []
    for task_dir in _issue_dirs(compass_dir):
        try:
            task, _ = load_manifest(task_dir)
        except CompassError:
            continue
        found += [(task_dir, task, r) for r in task.get("evidence") or [] if _waiting(r)]
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


def review_summary(compass_dir):
    """The display-only summary of delegated approvals not yet reviewed, or ''.
    It never writes a record."""
    rows = unreviewed(compass_dir)
    if not rows:
        return ""
    lines = [f"Compass: {len(rows)} approval(s) made under a delegation wait for your "
             f"review:"]
    for task_dir, task, record in rows:
        flag = (" - the agent approved a document it wrote in the same session"
                if _self_written(task, record) else "")
        lines.append(f"  {record.get('id')} - {_subject(record)}, issue "
                     f"{os.path.basename(task_dir)}, by {record.get('approved_by_agent')} "
                     f"under {record.get('delegation')} at {record.get('timestamp')}{flag}")
    lines.append("Type /compass:approve to mark them reviewed, or /compass:reject <record id> "
                 "<reason> to overrule one.")
    return "\n".join(lines)


@contextlib.contextmanager
def _held():
    """The session's own issue: its approval lock is already held."""
    yield


def mark_reviewed(session):
    """`/compass:approve` with no request pending: mark every delegated approval
    reviewed. None when there is nothing to review."""
    from compass_pkg.core import save_manifest
    from compass_pkg.prompt_approval import HookResult
    compass_dir = os.path.dirname(os.path.dirname(session.task_dir))
    rows = unreviewed(compass_dir)
    if not rows:
        return None
    stamp = _iso(_now())
    ids = []
    for task_dir in sorted({row[0] for row in rows}):
        own = os.path.abspath(task_dir) == os.path.abspath(session.task_dir)
        with (_held() if own else approvals.lock(task_dir)):
            task, path = load_manifest(task_dir)
            for record in task.get("evidence") or []:
                if _waiting(record):
                    record.update(reviewed_by=session.approver, reviewed_at=stamp)
                    ids.append(record.get("id"))
            save_manifest(task, path)
    return HookResult(False, f"Compass: marked {len(ids)} delegated approval(s) reviewed by "
                             f"{session.approver}: {', '.join(ids)}.",
                      f"The person reviewed the delegated approvals {', '.join(ids)}.")


def overrule(session, args):
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
        save_manifest(task, path)
        provenance = {"via": "prompt", "host": "claude-code",
                      "session_id": session.session_id, "prompt_id": session.prompt_id,
                      "approver_source": session.approver_source, "overrules": record_id}
        if reason:
            provenance["reason"] = reason
        answer = approvals.Answer("check", record["check"], approval_records.REJECTED,
                                  session.approver, session.role,
                                  record.get("scope") or "", provenance)
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
        f"Compass: overruled {record_id} ({subject}) for {session.approver}{said} - "
        f"{written}. This records your disagreement; it does not reverse anything the "
        f"agent already did.",
        f"The person overruled {record_id} ({subject}){said}. Do not rely on that "
        f"approval; ask the person what should change.")
