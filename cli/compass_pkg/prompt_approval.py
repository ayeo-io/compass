# compass_pkg.prompt_approval - record an approval from a typed Claude Code command
"""Turn Claude Code's `UserPromptExpansion` hook input into a recorded answer
or a block (ADR-068, ADR-069). `hooks/prompt-approval.sh` runs it.

The hook acts only on the expansion of a plugin command a person typed:
`/compass:approve`, `/compass:reject`, `/compass:delegate` and
`/compass:revoke`. Any other input gives None, and the prompt passes on with
nothing recorded. For one of the four it refuses, writing nothing, when:

- the command file it serves does not set `disable-model-invocation: true`.
  U0 measured that a scheduled job fires the event for a command without
  the flag, so the flag is what keeps the model's scheduled jobs out;
- `CLAUDE_CODE_ENTRYPOINT` starts with `sdk-`, which a nested `claude -p`
  session reports (the owner's answer of 2026-10-15). IDE and desktop values
  were not measured, so only `sdk-` is refused;
- the session's issue cannot be named: `COMPASS_ISSUE`, then
  `.compass/current-task`, refusing a pointer another session moved. It never
  guesses the most recently changed issue;
- no approver can be named: `COMPASS_APPROVER`, else the project's `owner:`;
- a record already holds this input's `prompt_id`, so one typed command is
  recorded once.

`/compass:approve [n]` and `/compass:reject [n] <reason>` answer one pending,
current, shown request of the session's issue. Compass shows a request at the
end of the agent's turn (the Stop hook); the hook records a request only
while its digest equals the one shown. Each refusal names its cause, and the
block reason reaches the person only. A recorded answer goes through
`approvals.record`, the writer the terminal verb uses, and the request then
moves to `closed/` (ADR-068 decision 4; the design's record-then-close rule).

Every path holds the issue's approval lock, and any error blocks: the hook
fails closed.
"""
# DEPENDENCY: standard library (dataclasses, os, re); compass_pkg.
# approval_records, approval_requests, approvals, core, session_lease.
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from compass_pkg import approval_records, approval_requests, approvals
from compass_pkg.core import CompassError, load_manifest, save_manifest

HOST = "claude-code"
EVENT = "UserPromptExpansion"
COMMANDS = {"compass:approve": "approve", "compass:reject": "reject",
            "compass:delegate": "delegate", "compass:revoke": "revoke"}
FLAG = "disable-model-invocation"
ENTRYPOINT_ENV = "CLAUDE_CODE_ENTRYPOINT"
APPROVER_ENV, ROLE_ENV = "COMPASS_APPROVER", "COMPASS_APPROVER_ROLE"


@dataclass(frozen=True)
class HookResult:
    """What the hook prints: a block with its reason, or a recorded answer."""
    block: bool
    message: str
    context: str = ""

    def output(self):
        """The JSON object Claude Code reads from the hook's standard output."""
        if self.block:
            return {"decision": "block", "reason": self.message}
        body = {"systemMessage": self.message}
        if self.context:
            body["hookSpecificOutput"] = {"hookEventName": EVENT,
                                          "additionalContext": self.context}
        return body


class Refused(Exception):
    """A refusal: the prompt is blocked with this reason and nothing is written."""


@dataclass(frozen=True)
class Session:
    """What the hook knows about the typed command and where it applies."""
    command: str
    args: str
    session_id: str
    prompt_id: str
    project: str
    task_dir: str
    slug: str
    approver: str
    role: str
    approver_source: str
    entrypoint: str


def handle(event, env, plugin_root=None):
    """The hook's answer to one input, or None when the input is not ours."""
    if not _ours(event):
        return None
    try:
        return _handle(event, env, plugin_root)
    except Refused as exc:
        return HookResult(True, str(exc))
    except CompassError as exc:
        return HookResult(True, _plain(str(exc)))
    except Exception as exc:                                # noqa: BLE001 - fail closed
        return HookResult(True, f"Compass could not record this ({type(exc).__name__}: "
                                f"{exc}). Nothing was written.")


def _ours(event):
    return (isinstance(event, dict)
            and event.get("hook_event_name") == EVENT
            and event.get("expansion_type") == "slash_command"
            and event.get("command_source") == "plugin"
            and event.get("command_name") in COMMANDS)


def _plain(text):
    """A CLI refusal as the person reads it in the hook's message."""
    for verb in (approvals.VERB, approval_requests.VERB):
        text = text.replace(f"{verb}: ", "", 1)
    return f"Compass: {text}"


def _handle(event, env, plugin_root):
    command = COMMANDS[event["command_name"]]
    _require_flag(plugin_root or env.get("CLAUDE_PLUGIN_ROOT") or _framework_root(),
                  command)
    entrypoint = str(env.get(ENTRYPOINT_ENV) or "")
    if entrypoint.startswith("sdk-"):
        raise Refused(f"Compass: /compass:{command} was not typed in an interactive session "
                      f"(CLAUDE_CODE_ENTRYPOINT is {entrypoint}), so nothing was written. "
                      f"Type it in your own Claude Code session.")
    session = _session(event, env, command, entrypoint)
    with approvals.lock(session.task_dir):
        _refuse_used_prompt(session)
        if command == "approve":
            return _approve(session)
        if command == "reject":
            return _reject(session)
        from compass_pkg import delegations
        if command == "delegate":
            return delegations.handle_delegate(session)
        return delegations.handle_revoke(session)


def _framework_root():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _require_flag(plugin_root, command):
    path = os.path.join(plugin_root, "commands", f"{command}.md")
    front = {}
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        match = re.match(r"---\n(.*?)\n---\n", text, re.S)
        if match:
            import yaml
            front = yaml.safe_load(match.group(1)) or {}
    except (OSError, ValueError, Exception):               # noqa: BLE001 - fail closed
        front = {}
    if not (isinstance(front, dict) and front.get(FLAG) is True):
        raise Refused(f"Compass: commands/{command}.md does not set `{FLAG}: true`, so "
                      f"Compass cannot tell this command from one the model scheduled. "
                      f"Nothing was written. Reinstall the Compass plugin.")


def _project_root(cwd):
    cur = os.path.abspath(cwd or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, ".compass")):
            return cur
        if os.path.exists(os.path.join(cur, ".git")):
            return None
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _session(event, env, command, entrypoint):
    project = _project_root(event.get("cwd"))
    if project is None:
        raise Refused("Compass: this session is not in a Compass project (no .compass/ "
                      "folder above it), so nothing was written.")
    compass_dir = os.path.join(project, ".compass")
    session_id = str(event.get("session_id") or "")
    slug = _issue(compass_dir, env, session_id)
    approver, role, source = resolve_approver(os.path.join(compass_dir, "work", slug), env)
    return Session(command, " ".join(str(event.get("command_args") or "").split()),
                   session_id, str(event.get("prompt_id") or ""), project,
                   os.path.join(compass_dir, "work", slug), slug, approver, role, source,
                   entrypoint)


def _one_segment(slug):
    return bool(slug) and slug not in (".", "..") and "/" not in slug and "\\" not in slug


def _issue(compass_dir, env, session_id):
    """The session's issue, as the pre-tool hook names it. Never a guess."""
    work = os.path.join(compass_dir, "work")
    named = env.get("COMPASS_ISSUE")
    if named:
        if not _one_segment(named) or not os.path.isdir(os.path.join(work, named)):
            raise Refused(f"Compass: COMPASS_ISSUE names '{named}', which is not an issue "
                          f"here, so nothing was written.")
        return named
    pointer = os.path.join(compass_dir, "current-task")
    slug = ""
    if os.path.isfile(pointer):
        with open(pointer, encoding="utf-8") as fh:
            slug = fh.read().strip()
    if not _one_segment(slug) or not os.path.isdir(os.path.join(work, slug)):
        raise Refused("Compass: no issue is named for this session (.compass/current-task "
                      "is missing or names no issue), so nothing was written. Run "
                      "`compass issue use <slug>`, then type the command again.")
    if session_id:
        from compass_pkg import session_lease
        lease = session_lease.check(compass_dir, session_id, slug)
        if lease.startswith("moved:"):
            previous = lease[len("moved:"):]
            raise Refused(f"Compass: another session moved .compass/current-task from this "
                          f"session's issue '{previous}' to '{slug}', so nothing was written. "
                          f"Run `compass issue use <slug>` to say which issue you mean.")
    return slug


def resolve_approver(task_dir, env):
    """`(name, role, source)`: `COMPASS_APPROVER` from the session's start-up
    environment, else the project's `owner:`. Refuses when neither names a
    person, and refuses the agent."""
    owner = approval_records.project_owner(task_dir)
    named = " ".join(str(env.get(APPROVER_ENV) or "").split())
    if named:
        name, source = named, "environment"
    elif owner:
        name, source = owner, "owner"
    else:
        raise Refused("Compass: no approver can be named, so nothing was written. Add "
                      "`owner: <your id>` to compass.yml, or set COMPASS_APPROVER before "
                      "starting Claude Code.")
    try:
        name = approvals.approver_name(name)
    except CompassError as exc:
        raise Refused(_plain(str(exc)) + " Nothing was written.") from None
    if name == owner:
        role = "owner"
    else:
        role = " ".join(str(env.get(ROLE_ENV) or "").split()) or "approver"
    return name, role, source


def _refuse_used_prompt(session):
    """One typed command is answered once: refuse a `prompt_id` already on a
    record or a closed request."""
    if not session.prompt_id:
        return
    task, _ = load_manifest(session.task_dir)
    for entry in task.get("evidence") or []:
        if isinstance(entry, dict) and entry.get("prompt_id") == session.prompt_id:
            raise Refused(f"Compass: this typed command was already answered "
                          f"({entry.get('id')}). Nothing more was written.")
    for req in approval_requests.closed(session.task_dir):
        if req.get("prompt_id") == session.prompt_id:
            raise Refused(f"Compass: this typed command was already answered (request "
                          f"{req['number']}). Nothing more was written.")


def provenance(session, request):
    return {"via": "prompt", "host": HOST, "session_id": session.session_id,
            "prompt_id": session.prompt_id, "request": request["number"],
            "nonce": request["nonce"], "approver_source": session.approver_source}


# --- choosing one request ----------------------------------------------------------------

def _held_nonces(task_dir):
    task, _ = load_manifest(task_dir)
    return {e.get("nonce") for e in task.get("evidence") or []
            if isinstance(e, dict) and e.get("nonce")}


def _pending(session):
    """The session's pending requests. A request whose nonce a record already
    holds was answered and is closed now, since the record is written before
    the request is closed; one for another issue is
    never shown or recorded here."""
    held = _held_nonces(session.task_dir)
    pending, answered = [], set()
    for req in approval_requests.pending(session.task_dir):
        if req.get("nonce") in held:
            approval_requests.close(session.task_dir, req, "answered")
            answered.add(req["number"])
        elif req.get("issue") == session.slug:
            pending.append(req)
    return pending, answered


def _usage(command):
    if command == "approve":
        return ("/compass:approve takes no argument or one pending request number, such "
                "as /compass:approve 2.")
    return ("/compass:reject takes an optional pending request number, then your reason, "
            "such as /compass:reject 2 the rollback plan is missing.")


def _choose(session, number):
    pending, answered = _pending(session)
    if number is not None:
        found = [r for r in pending if r["number"] == number]
        if found:
            return found[0]
        closed = {r["number"]: r for r in approval_requests.closed(session.task_dir)}
        if number in answered or (number in closed and closed[number].get("outcome")
                                  in ("approved", "rejected", "answered")):
            raise Refused(f"Compass: request {number} was already answered. Nothing more "
                          f"was written.")
        raise Refused(f"Compass: there is no pending request {number} on issue "
                      f"{session.slug}. {_usage(session.command)} Nothing was written.")
    if not pending:
        raise Refused(f"Nothing is waiting for your approval on issue {session.slug}. "
                      f"Nothing was written.")
    if len(pending) > 1:
        lines = [f"Compass: {len(pending)} requests are waiting on issue {session.slug}; "
                 f"nothing was written. Choose one:"]
        lines += [f"  {r['number']} - {approval_requests.subject_text(r)}"
                  + (f" (the agent's description: \"{r['scope']}\")" if r.get("scope") else "")
                  for r in pending]
        verb = "/compass:approve" if session.command == "approve" else "/compass:reject"
        lines.append("Type " + " or ".join(f"{verb} {r['number']}" for r in pending) + ".")
        raise Refused("\n".join(lines))
    return pending[0]


def _current(session, request):
    """Refuse a request that is stale, or that the person has not seen as it
    reads now; showing it is part of the refusal."""
    task, _ = load_manifest(session.task_dir)
    number = request["number"]
    if request.get("generation") != task.get("generation"):
        approval_requests.close(session.task_dir, request, approval_requests.STALE,
                                reason="the issue moved to another generation")
        raise Refused(f"Compass: request {number} was for generation "
                      f"{request.get('generation')}, and issue {session.slug} is at "
                      f"generation {task.get('generation')}. Nothing was written; the agent "
                      f"must ask again with compass evidence request.")
    if request.get("form") == "artifact":
        now_digest = approval_requests.document_digest(session.task_dir, task,
                                                       request.get("value"))
        if now_digest != request.get("document_digest"):
            approval_requests.close(session.task_dir, request, approval_requests.STALE,
                                    reason="the document changed")
            raise Refused(f"Compass: the document '{request.get('value')}' changed since "
                          f"the request. Nothing was written; the agent must ask again "
                          f"with compass evidence request.")
    verb = f"/compass:{session.command}"
    if not request.get("shown_at"):
        shown = approval_requests.mark_shown(session.task_dir, request)
        raise Refused(approval_requests.shown_text(shown)
                      + f"\nNothing was written yet: this is what you are answering. Type "
                        f"{verb} again to answer it.")
    if request.get("shown_digest") != approval_requests.digest(request):
        shown = approval_requests.mark_shown(session.task_dir, request)
        raise Refused("Compass: the request changed after it was shown to you. As it "
                      "reads now:\n" + approval_requests.shown_text(shown)
                      + f"\nNothing was written. Type {verb} again to answer it as it "
                        f"reads now.")


# --- approve and reject -----------------------------------------------------------------

def _parse_number(args):
    first, _, rest = args.partition(" ")
    if first.isdigit():
        return int(first), rest.strip()
    return None, args


def _approve(session):
    number = None
    if session.args:
        if not session.args.isdigit():
            raise Refused(f"Compass: {_usage('approve')} Nothing was written.")
        number = int(session.args)
    elif not _pending(session)[0]:
        # Nothing is waiting: the command marks delegated approvals reviewed.
        from compass_pkg import delegations
        reviewed = delegations.mark_reviewed(session)
        if reviewed is not None:
            return reviewed
    request = _choose(session, number)
    _current(session, request)
    answer = approvals.Answer(request["form"], request.get("value"),
                              approval_records.APPROVED, session.approver, session.role,
                              request.get("scope") or "", provenance(session, request))
    done = approvals.record(session.task_dir, answer)
    approval_requests.close(session.task_dir, request, approval_requests.APPROVED,
                            evidence=done.evidence_ids, prompt_id=session.prompt_id,
                            session_id=session.session_id)
    subject = approval_requests.subject_text(request)
    ids = ", ".join(done.evidence_ids)
    return HookResult(
        False,
        f"Compass: recorded {ids} - {subject} approved by {session.approver} "
        f"(request {request['number']}, issue {session.slug}).",
        f"Compass recorded the person's approval of request {request['number']} "
        f"({subject}) as {ids}. Go on with the work that waited for it.")


def _reject(session):
    number, reason = _parse_number(session.args)
    if number is None and reason.startswith("EV-"):
        # A record id: overrule an approval made under a delegation (ADR-069).
        from compass_pkg import delegations
        return delegations.overrule(session, reason)
    request = _choose(session, number)
    _current(session, request)
    form, value = request["form"], request.get("value")
    subject = approval_requests.subject_text(request)
    # The approver must be one who may answer this subject.
    check = approvals.Answer(form, value, approval_records.APPROVED, session.approver,
                             session.role, request.get("scope") or "-")
    why = approvals.refusal(session.task_dir, check)
    if why:
        raise Refused(_plain(why))
    note = ""
    ids = []
    if form == "check":
        answer = approvals.Answer(form, value, approval_records.REJECTED, session.approver,
                                  session.role, request.get("scope") or "",
                                  dict(provenance(session, request),
                                       **({"reason": reason} if reason else {})))
        ids = approvals.record(session.task_dir, answer).evidence_ids
    elif form == "artifact":
        _send_back(session, value, reason)
    elif form == "guardrail":
        task, _ = load_manifest(session.task_dir)
        earlier = [e.get("id") for e in task.get("evidence") or []
                   if isinstance(e, dict) and e.get("type") == "human-approval"
                   and e.get("decision") == approval_records.APPROVED
                   and approval_records.gives_g5(e)]
        if earlier:
            note = (f" An earlier sign-off, {earlier[0]}, still stands: a rejection does not "
                    f"withdraw it.")
    approval_requests.close(session.task_dir, request, approval_requests.REJECTED,
                            reason=reason, evidence=ids or None,
                            prompt_id=session.prompt_id, session_id=session.session_id)
    said = f": {reason}" if reason else ""
    recorded = f" Recorded {', '.join(ids)}." if ids else ""
    return HookResult(
        False,
        f"Compass: {subject} rejected by {session.approver} (request {request['number']}, "
        f"issue {session.slug}){said}.{recorded}{note}",
        f"The person rejected request {request['number']} ({subject}){said}. Do not go on "
        f"with the work that waited for it; ask the person what should change.")


def _send_back(session, kind, reason):
    """Return a document to draft, holding the digest it was rejected at, so a
    later stage record leaves it in draft until the file changes."""
    from compass_pkg import artifact_status
    task, path = load_manifest(session.task_dir)
    entry = next(a for a in task.get("artifacts") or []
                 if isinstance(a, dict) and a.get("kind") == kind)
    entry["rejected_digest"] = approval_requests.document_digest(session.task_dir, task, kind)
    artifact_status.clear_approver(entry)
    entry.update(status=artifact_status.DRAFT, rejected_by=session.approver,
                 rejected_at=approvals._stamp(), rejected_reason=reason)
    save_manifest(task, path)


def load_event(text):
    """The hook input as a map, or an empty one."""
    import json
    try:
        body = json.loads(text)
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}

