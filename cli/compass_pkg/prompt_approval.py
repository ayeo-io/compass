# compass_pkg.prompt_approval - record an approval from a typed Claude Code command
"""Turn Claude Code's `UserPromptExpansion` hook input into a recorded answer
or a block (ADR-068, ADR-069). `hooks/prompt-approval.sh` runs it.

The hook acts only on the expansion of a plugin command a person typed:
`/compass:approve`, `/compass:reject`, `/compass:delegate` and
`/compass:revoke`. Any other input gives None, and the prompt passes on with
nothing recorded. For one of the four it refuses, writing nothing, when:

- the command file it serves does not set `disable-model-invocation: true`.
  The host measurement on Claude Code 2.1.300 (ADR-068) showed that a
  scheduled job fires the event for a command without
  the flag, so the flag is what keeps the model's scheduled jobs out;
- `CLAUDE_CODE_ENTRYPOINT` starts with `sdk-`, which a nested `claude -p`
  session reports (the owner's answer of 2026-10-15). IDE and desktop values
  were not measured, so only `sdk-` is refused;
- `/compass:approve` and `/compass:reject` find no request. A number names a
  pending request on the current issue of each worktree (this checkout's issue
  is `COMPASS_ISSUE`, then `.compass/current-task`, refusing a pointer another
  session moved; a worktree with no current issue is skipped). `--issue <slug>`
  names any issue in any worktree. A request that two issues hold, or a bare
  command with more than one request pending, is refused with the list. The
  command never guesses the most recently changed issue;
- no approver can be named, for the folder that holds the chosen request:
  `COMPASS_APPROVER`, else that project's `owner:`.
  The message names which of seven causes applies (`compass.yml` unreadable,
  `owner:` not text, `owner:` only in `.compass/config.yml`, the file above the
  project folder, the file missing in a worktree or elsewhere, no `owner:`);
- the input has no `prompt_id`, or a record already holds it, so one typed
  command is recorded once. `/compass:revoke` is exempt from the missing
  `prompt_id`: it only ends delegations, and a person can always end one.

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
    #: The common store's `.compass/` folder, for `/compass:delegate` and
    #: `/compass:revoke`, which name no issue (`task_dir` and `slug` are empty).
    compass_dir: str = ""
    #: The slug `--issue` named in `/compass:approve` or `/compass:reject`, or "".
    issue: str = ""


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
    if command in ("approve", "reject"):
        # The request is chosen first, across the worktrees, and only then are
        # the approver read and the locks taken (`_answer`).
        return _answer(session, env)
    from compass_pkg import delegations
    with approvals.lock_all([]):
        _refuse_used_prompt(session)
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
    if command in ("delegate", "revoke"):
        return _store_session(event, env, command, entrypoint, project, session_id)
    # No issue and no approver yet: both depend on which request is chosen, in
    # which worktree (`_answer`).
    issue, args = _split_issue_flag(
        command, " ".join(str(event.get("command_args") or "").split()))
    if command == "approve" and (args and not args.isdigit() or issue and not args):
        raise Refused(f"Compass: {_usage(command)} Nothing was written.")
    return Session(command, args, session_id, str(event.get("prompt_id") or ""), project,
                   "", "", "", "", "", entrypoint, compass_dir=compass_dir, issue=issue)


def _split_issue_flag(command, text):
    """`(slug, rest)`: the slug `--issue` names, which can stand anywhere in the
    words, and the other words. `--issue` with no value, given twice or with a
    value that is not one folder name is refused with both forms."""
    words, slug, rest, i = text.split(), "", [], 0
    while i < len(words):
        if words[i] == "--issue":
            if slug or i + 1 >= len(words) or words[i + 1].startswith("--") \
                    or not _one_segment(words[i + 1]):
                raise Refused(f"Compass: {_usage(command)} Nothing was written.")
            slug, i = words[i + 1], i + 2
            continue
        rest.append(words[i])
        i += 1
    return slug, " ".join(rest)


def _store_session(event, env, command, entrypoint, project, session_id):
    """The session of `/compass:delegate` and `/compass:revoke`. They name no
    issue. The delegation is kept in the common store, and the approver is
    read from the folder that holds it, whichever worktree the person typed
    in."""
    from compass_pkg import worktree_lookup
    store = worktree_lookup.common_store(project)
    if store.folder is None:
        raise Refused(f"Compass: {store.why_none}, so nothing was written.")
    approver, role, source = resolve_approver(store.project, env)
    return Session(command, " ".join(str(event.get("command_args") or "").split()),
                   session_id, str(event.get("prompt_id") or ""), project, "", "",
                   approver, role, source, entrypoint,
                   compass_dir=os.path.dirname(store.folder))


def _one_segment(slug):
    return bool(slug) and slug not in (".", "..") and "/" not in slug and "\\" not in slug


def _issue(compass_dir, env, session_id, strict=True):
    """The session's issue, as the pre-tool hook names it. Never a guess. With
    `strict` False, a pointer that is missing or names no issue gives None
    instead of a refusal, so a search across worktrees can skip the folder."""
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
        if not strict:
            return None
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


_SET_APPROVER = "or set COMPASS_APPROVER before starting Claude Code."


def _no_approver(lookup):
    """The refusal for the cause that no owner can be named. Only the cause
    `no-owner` says "no approver can be named"; the others name what is wrong
    and the real next step. Each stays under 60 words for a folder name of ordinary
    length. A hostile name of one-letter words is cut at `SHOWN_FOLDER_MAX` characters
    (240, so 120 words). That brings a message to 143 words (compass.yml missing) up
    to 273 words (compass.yml above, which shows two folder names), measured on a name
    of 400 one-letter words. The 60-word cap holds for ordinary names only."""
    records = approval_records
    # The folder names come from the disk, so they are cleaned and cut like the reason.
    cause, root = lookup.cause, records.shown_text(lookup.root, records.SHOWN_FOLDER_MAX)
    found_in = records.shown_text(lookup.found_in, records.SHOWN_FOLDER_MAX)
    if cause == records.CAUSE_UNREADABLE:
        text = (f"compass.yml in {root} cannot be read: {lookup.detail}. "
                f"Fix that file, {_SET_APPROVER}")
    elif cause == records.CAUSE_NOT_TEXT:
        text = (f"owner in compass.yml is {lookup.detail}, not text. "
                f'Quote it, for example owner: "123", {_SET_APPROVER}')
    elif cause == records.CAUSE_CONFIG_ONLY:
        text = ("The approver is read from compass.yml only, and owner is set only in "
                f".compass/config.yml. Add owner: <your id> to compass.yml, {_SET_APPROVER}")
    elif cause == records.CAUSE_FILE_ABOVE:
        text = (f"compass.yml is in {found_in}, but .compass is in {root}. Compass "
                f"reads compass.yml only from the folder that holds .compass. Copy it "
                f"there, {_SET_APPROVER}")
    elif cause == records.CAUSE_MISSING_IN_WORKTREE:
        text = (f"{root} is a git worktree with no compass.yml. A worktree holds only "
                f"tracked files, and git does not copy an untracked one. Copy compass.yml "
                f"into it, {_SET_APPROVER}")
    elif cause == records.CAUSE_MISSING:
        text = (f"There is no compass.yml in {root}. Add one with owner: <your id>, "
                f"{_SET_APPROVER}")
    else:
        return ("Compass: no approver can be named, so nothing was written. Add "
                f"`owner: <your id>` to compass.yml, {_SET_APPROVER}")
    return _plain(f"nothing was written. {' '.join(text.split())}")


def resolve_approver(task_dir, env):
    """`(name, role, source)`: `COMPASS_APPROVER` from the session's start-up
    environment, else the project's `owner:`. Refuses when neither names a
    person, and refuses the agent."""
    lookup = approval_records.owner_and_cause(task_dir)
    owner = lookup.owner
    named = " ".join(str(env.get(APPROVER_ENV) or "").split())
    if named:
        name, source = named, "environment"
    elif owner:
        name, source = owner, "owner"
    else:
        raise Refused(_no_approver(lookup))
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
    """One typed command is answered once: refuse an input with no
    `prompt_id`, which could not be told from a repeat, and a `prompt_id`
    already on a record or a closed request of the session's issue.
    `delegations.handle_delegate` compares the delegation files under its own
    lock."""
    if not session.prompt_id.strip():
        if session.command == "revoke":
            return
        raise Refused(f"Compass: Claude Code sent /compass:{session.command} with no prompt "
                      f"id, so Compass cannot tell it from a repeat of a command already "
                      f"answered. Nothing was written. Type the command again.")
    _refuse_replayed(session, [session.task_dir] if session.task_dir else [])


def _refuse_replayed(session, folders):
    """Refuse a `prompt_id` that a record or a closed request of any issue
    folder in `folders` already holds."""
    for task_dir in folders:
        try:
            task, _ = load_manifest(task_dir)
        except CompassError:
            continue
        for entry in task.get("evidence") or []:
            if isinstance(entry, dict) and entry.get("prompt_id") == session.prompt_id:
                raise Refused(f"Compass: this typed command was already answered "
                              f"({entry.get('id')}). Nothing more was written.")
        for req in approval_requests.closed(task_dir):
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


def _pending_in(task_dir, slug):
    """The pending requests of one issue. A request whose nonce a record already
    holds was answered and is closed now, since the record is written before
    the request is closed; one for another issue is
    never shown or recorded here."""
    held = _held_nonces(task_dir)
    pending, answered = [], set()
    for req in approval_requests.pending(task_dir):
        if req.get("nonce") in held:
            approval_requests.close(task_dir, req, "answered")
            answered.add(req["number"])
        elif req.get("issue") == slug:
            pending.append(req)
    return pending, answered


def _pending(session):
    return _pending_in(session.task_dir, session.slug)


def _usage(command):
    if command == "approve":
        return ("/compass:approve takes a pending request number, `/compass:approve <n>`, "
                "or the number and the issue, `/compass:approve <n> --issue <issue>`. "
                "With no argument it answers the one request pending in any worktree.")
    return ("/compass:reject takes an optional pending request number, then your reason: "
            "`/compass:reject <n> <reason>`, or with the issue "
            "`/compass:reject <n> <reason> --issue <issue>`.")


def _project_of(task_dir):
    """The project folder that holds an issue folder."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.normpath(task_dir))))


def _find(listing, slug):
    """The folder of the issue `--issue` names, in any worktree, or a refusal
    that names the folders searched or both holders."""
    from compass_pkg import worktree_lookup
    try:
        return worktree_lookup.find_issue(listing, slug)
    except worktree_lookup.HeldTwice as exc:
        raise Refused(f"Compass: the issue '{slug}', named after --issue, is held by more "
                      f"than one worktree: {' and '.join(exc.folders)}. Compass cannot tell "
                      f"which one is meant. Nothing was written.") from None
    except worktree_lookup.NotFound as exc:
        note = f" {exc.note[0].upper()}{exc.note[1:]}." if exc.note else ""
        raise Refused(f"Compass: '{slug}', named after --issue, is in none of the work "
                      f"folders searched: {', '.join(exc.searched)}.{note} Nothing was "
                      f"written.") from None


def _every_issue_dir(listing):
    """Every issue folder of every worktree: the replay check reads them all."""
    from compass_pkg import delegations
    return [d for tree in listing.trees
            for d in delegations._issue_dirs(os.path.join(tree.project, ".compass"))]


def _candidates(session, env, listing):
    """`[(issue folder, slug)]` the number or bare command searches: the issue
    `--issue` names, else the current issue of each worktree. The current issue
    of this checkout keeps `COMPASS_ISSUE` and the session-lease refusal. A
    worktree with no current issue is skipped."""
    if session.issue:
        return [(_find(listing, session.issue), session.issue)]
    found = []
    for tree in listing.trees:
        compass_dir = os.path.join(tree.project, ".compass")
        if tree.is_this:
            slug = _issue(compass_dir, env, session.session_id, strict=False)
        else:
            try:
                with open(os.path.join(compass_dir, "current-task"), encoding="utf-8") as fh:
                    slug = fh.read().strip()
            except OSError:
                slug = ""
            if not _one_segment(slug) or not os.path.isdir(os.path.join(compass_dir, "work",
                                                                       slug)):
                slug = None
        if slug:
            found.append((os.path.join(compass_dir, "work", slug), slug))
    if not found and len(listing.trees) == 1:
        _issue(os.path.join(listing.trees[0].project, ".compass"), env, session.session_id)
    return found


def _answered(candidates, numbers):
    """True when a candidate issue closed request `number` with an answer."""
    for task_dir, _ in candidates:
        closed = {r["number"]: r for r in approval_requests.closed(task_dir)}
        for number in numbers:
            if number in closed and closed[number].get("outcome") in (
                    "approved", "rejected", "answered"):
                return True
    return False


def _verb(session):
    return "/compass:approve" if session.command == "approve" else "/compass:reject"


def _form(session, number, slug):
    """The command that names one request of one issue."""
    if session.command == "approve":
        return f"/compass:approve {number} --issue {slug}"
    return f"/compass:reject {number} <reason> --issue {slug}"


def _row_text(task_dir, slug, request, numbered):
    lead = f"  {request['number']} - " if numbered else "  "
    scope = (f" (the agent's description: \"{request['scope']}\")"
             if request.get("scope") else "")
    return (f"{lead}issue {slug} ({_project_of(task_dir)}): "
            f"{approval_requests.subject_text(request)}{scope}")


def _choose_across(session, number, candidates, listing):
    """`(issue folder, slug, request)` for the one request the command names, or a
    refusal. A number names a pending request on a candidate issue; no number
    names the one request pending across them."""
    rows, answered = [], set()
    for task_dir, slug in candidates:
        pending, closed_now = _pending_in(task_dir, slug)
        rows += [(task_dir, slug, r) for r in pending]
        answered |= closed_now
    if number is not None:
        hits = [row for row in rows if row[2]["number"] == number]
        if len(hits) == 1:
            return hits[0]
        if hits:
            lines = [f"Compass: request {number} is pending on more than one issue; "
                     f"nothing was written. Choose one:"]
            lines += [_row_text(t, s, r, False) for t, s, r in hits]
            lines.append("Type " + " or ".join(_form(session, number, s)
                                               for _, s, _ in hits) + ".")
            raise Refused("\n".join(lines))
        if number in answered or _answered(candidates, [number]):
            raise Refused(f"Compass: request {number} was already answered. Nothing more "
                          f"was written.")
        if session.issue:
            task_dir = candidates[0][0]
            raise Refused(f"Compass: there is no pending request {number} on issue "
                          f"{session.issue} ({_project_of(task_dir)}). "
                          f"{_usage(session.command)} Nothing was written.")
        if len(listing.trees) > 1:
            searched = ", ".join(t.project for t in listing.trees)
            raise Refused(f"Compass: no worktree holds a pending request {number} on its "
                          f"current issue. Searched the worktrees at {searched}. To answer "
                          f"a request on another issue, name it: "
                          f"{_form(session, number, '<issue>')}. Nothing was written.")
        raise Refused(f"Compass: there is no pending request {number} on issue "
                      f"{candidates[0][1]}. {_usage(session.command)} Nothing was written.")
    if len(rows) == 1:
        return rows[0]
    if rows:
        lines = [f"Compass: {len(rows)} requests are waiting; nothing was written. "
                 f"Choose one:"]
        lines += [_row_text(t, s, r, True) for t, s, r in rows]
        lines.append("Type " + " or ".join(_form(session, r["number"], s)
                                           for _, s, r in rows) + ".")
        raise Refused("\n".join(lines))
    return None


def _shown(session, request):
    """The request as Compass shows the person, with the `--issue` form when
    another worktree's current issue holds a request with the same number."""
    return approval_requests.shown_text(request, approval_requests.same_number_elsewhere(
        session.task_dir, request["number"]))


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
        raise Refused(_shown(session, shown)
                      + f"\nNothing was written yet: this is what you are answering. Type "
                        f"{verb} again to answer it.")
    if request.get("shown_digest") != approval_requests.digest(request):
        shown = approval_requests.mark_shown(session.task_dir, request)
        raise Refused("Compass: the request changed after it was shown to you. As it "
                      "reads now:\n" + _shown(session, shown)
                      + f"\nNothing was written. Type {verb} again to answer it as it "
                        f"reads now.")


# --- approve and reject -----------------------------------------------------------------

def _parse_number(args):
    first, _, rest = args.partition(" ")
    if first.isdigit():
        return int(first), rest.strip()
    return None, args


def _answer(session, env):
    """`/compass:approve` and `/compass:reject`. The request is chosen first,
    across the worktrees (`_choose_across`). The approver is read from the folder
    that holds it, and only then are its locks taken, with a second check that
    the request is still the one chosen."""
    import dataclasses

    from compass_pkg import worktree_lookup
    _refuse_used_prompt(session)
    listing = worktree_lookup.list_worktrees(session.project)
    _refuse_replayed(session, _every_issue_dir(listing))
    if session.command == "approve":
        number = int(session.args) if session.args else None
        reason = ""
    else:
        number, reason = _parse_number(session.args)
        if number is None and reason.startswith("EV-"):
            return _overrule(session, env, listing, reason)
    candidates = _candidates(session, env, listing)
    chosen = _choose_across(session, number, candidates, listing)
    if chosen is None:
        if session.command == "approve" and not session.issue:
            return _review(session, env, listing)
        where = (f"issue {session.issue}" if session.issue
                 else "the current issue of any worktree" if len(listing.trees) > 1
                 else f"issue {candidates[0][1]}")
        raise Refused(f"Nothing is waiting for your approval on {where}. Nothing was "
                      f"written.")
    task_dir, slug, request = chosen
    approver, role, source = resolve_approver(task_dir, env)
    chosen_session = dataclasses.replace(session, task_dir=task_dir, slug=slug,
                                         approver=approver, role=role,
                                         approver_source=source)
    where = f", folder {_project_of(task_dir)}" if len(listing.trees) > 1 else ""
    with approvals.lock_all([task_dir]):
        _refuse_used_prompt(chosen_session)
        pending, _ = _pending_in(task_dir, slug)
        again = next((r for r in pending if r["number"] == request["number"]
                      and r.get("nonce") == request.get("nonce")), None)
        if again is None:
            raise Refused(f"Compass: request {request['number']} on issue {slug} was "
                          f"answered or changed while Compass checked it. Nothing was "
                          f"written; type the command again.")
        if session.command == "approve":
            return _approve(chosen_session, again, where)
        return _reject(chosen_session, again, reason, where)


def _review(session, env, listing):
    """`/compass:approve` with nothing pending in any worktree: mark reviewed the
    delegated approvals that the latest summary shown in this session listed,
    before this command (`delegations.last_shown`). The issue and the approver
    are this checkout's. The issue lock of each shown row is taken with the
    session's own, in one sorted order, since holding the own lock while waiting
    for another let two sessions wait on each other."""
    import dataclasses

    from compass_pkg import delegations
    compass_dir = os.path.join(session.project, ".compass")
    slug = _issue(compass_dir, env, session.session_id)
    task_dir = os.path.join(compass_dir, "work", slug)
    approver, role, source = resolve_approver(task_dir, env)
    own = dataclasses.replace(session, task_dir=task_dir, slug=slug, approver=approver,
                              role=role, approver_source=source)
    entry = delegations.last_shown(compass_dir, session.session_id, session.prompt_id)
    held = [task_dir] + [item["folder"] for item in (entry or {}).get("records") or []
                         if item.get("folder")]
    with approvals.lock_all(held):
        _refuse_used_prompt(own)
        if _pending(own)[0]:
            raise Refused("Compass: a request was raised while Compass checked. Nothing was "
                          "written; type /compass:approve again.")
        reviewed = delegations.mark_reviewed(own, entry, held)
        if reviewed is not None:
            return reviewed
        if delegations.unreviewed(compass_dir):
            raise Refused("Compass: nothing was marked reviewed. The last summary shown in "
                          "this session before this command did not list any approval that "
                          "still waits. Nothing was written; the next summary lists them.")
    raise Refused(f"Nothing is waiting for your approval on issue {slug}. Nothing was "
                  f"written.")


def _overrule(session, env, listing, text):
    """`/compass:reject <record id> <reason>`: the issue is the one `--issue`
    names, else the one issue that holds a delegated approval with that id, in
    any worktree. Two holders are refused with the `--issue` form. With no
    holder, this checkout's current issue gives the refusal."""
    import dataclasses

    from compass_pkg import delegations
    record_id = text.partition(" ")[0]
    if session.issue:
        task_dir = _find(listing, session.issue)
    else:
        holders = []
        for folder in _every_issue_dir(listing):
            try:
                task, _ = load_manifest(folder)
            except CompassError:
                continue
            if any(isinstance(r, dict) and r.get("id") == record_id
                   and r.get("via") == "delegation" for r in task.get("evidence") or []):
                holders.append(folder)
        if len(holders) > 1:
            lines = [f"Compass: the record {record_id} is held by more than one issue; "
                     f"nothing was written. Choose one:"]
            lines += [f"  issue {os.path.basename(h)} ({_project_of(h)})" for h in holders]
            lines.append("Type " + " or ".join(
                f"/compass:reject {record_id} <reason> --issue {os.path.basename(h)}"
                for h in holders) + ".")
            raise Refused("\n".join(lines))
        if holders:
            task_dir = holders[0]
        else:
            compass_dir = os.path.join(session.project, ".compass")
            task_dir = os.path.join(compass_dir, "work",
                                    _issue(compass_dir, env, session.session_id))
    slug = os.path.basename(task_dir)
    approver, role, source = resolve_approver(task_dir, env)
    own = dataclasses.replace(session, task_dir=task_dir, slug=slug, approver=approver,
                              role=role, approver_source=source)
    where = f", folder {_project_of(task_dir)}" if len(listing.trees) > 1 else ""
    with approvals.lock_all([task_dir]):
        _refuse_used_prompt(own)
        return delegations.overrule(own, text, where)


def _approve(session, request, where=""):
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
        f"(request {request['number']}, issue {session.slug}{where}).",
        f"Compass recorded the person's approval of request {request['number']} "
        f"({subject}) as {ids}. Go on with the work that waited for it.")


def _reject(session, request, reason, where=""):
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
        f"issue {session.slug}{where}){said}.{recorded}{note}",
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

