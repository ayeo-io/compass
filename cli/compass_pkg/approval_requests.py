# compass_pkg.approval_requests - `compass evidence request` and the request files
"""An agent asks a person for an approval with a request (ADR-068 decision 1).

`compass evidence request` takes the subject forms of `compass evidence
approve`, runs the same refusals (`approvals.record` with `save=False`), and
writes one request file:

    .compass/work/<slug>/approval-requests/pending/<n>.yml

A request holds facts the CLI derives - the issue, its generation and labels,
the subject, a document's digest - and the agent's description of the scope.
It also holds a single-use `nonce`, which the record that answers it copies.
A request for a waiver also holds `waiver`: the check and the reason the
waiver names when the request is written, which the person is shown and the
prompt hook compares with the manifest before it records the approval.
A request for the `specify` checkpoint of a path issue also holds `spec` and
`spec_sha256`: the spec's path and the digest of its bytes, which the prompt hook
compares with the file before it records the approval (ADR-095).
A request for the `specify`, `build` or `ship` checkpoint of a path issue, or the
`refine`, `implement` or `verify` checkpoint of an issue assessed before 9.0.0,
that the four-layer acceptance strategy applies to also holds `review`: the stage
it ends and the atdd skill's questions for it (`checkpoint_outcomes.review`).
When a request is answered, replaced or found stale it moves to `closed/<n>.yml`
with its `outcome`. A new request for a subject that already has a pending one
replaces it. Numbers are unique within the issue.

At the end of the agent's turn the Stop hook shows each unshown pending request
to the person (`shown_text`) and stamps `shown_at` and `shown_digest`. The
prompt hook records only a request whose digest still equals `shown_digest`.

A request is not evidence: no check reads one, and nothing here writes the
manifest. The pre-tool hook refuses the agent's edit tools on these files
(`approval-request-protected`); a process running as the same operating system
user can still write them, as ADR-068 decision 10 states.

On a host whose adapter has no person-only approval event, the adapter sets
`COMPASS_APPROVAL_CHANNEL=terminal`, and the verb prints the exact terminal
command for the person instead of the prompt to type. No code here reads an
adapter's name.
"""
# DEPENDENCY: standard library (hashlib, json, os, secrets, shlex, textwrap); compass_pkg.
# approvals, atomic_io, core, terminal.
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shlex
import textwrap

from compass_pkg import approval_records, approvals, atomic_io, launcher
from compass_pkg.core import (CompassError, issue_arg, load_manifest, load_yaml, now_iso,
                              resolve_issue_dir)
from compass_pkg.terminal import resolve_mode, say

FOLDER = "approval-requests"
PENDING, CLOSED = "pending", "closed"
REPLACED, STALE, APPROVED, REJECTED = "replaced", "stale", "approved", "rejected"
VERB = "compass evidence request"
#: The fields `shown_digest` covers: everything the person is shown, and the
#: nonce, so a request rewritten after it was shown no longer matches.
SHOWN_FIELDS = ("number", "issue", "generation", "form", "value", "scope", "labels",
                "document_digest", "requested_at", "nonce")
#: Set by an adapter whose host has no person-only approval event.
CHANNEL_ENV = "COMPASS_APPROVAL_CHANNEL"


def folder(task_dir, which=PENDING):
    return os.path.join(task_dir, FOLDER, which)


def _read(path):
    try:
        body = load_yaml(path)
    except CompassError:
        return None
    return body if isinstance(body, dict) else None


def _listed(task_dir, which):
    where = folder(task_dir, which)
    found = []
    if os.path.isdir(where):
        for name in os.listdir(where):
            stem, ext = os.path.splitext(name)
            if ext == ".yml" and stem.isdigit():
                body = _read(os.path.join(where, name))
                if body is not None and body.get("number") == int(stem):
                    found.append(body)
    return sorted(found, key=lambda r: r["number"])


def pending(task_dir):
    """The pending requests of the issue, by number."""
    return _listed(task_dir, PENDING)


def closed(task_dir):
    """The closed requests of the issue, by number."""
    return _listed(task_dir, CLOSED)


def _next_number(task_dir):
    numbers = [0]
    for which in (PENDING, CLOSED):
        where = folder(task_dir, which)
        if os.path.isdir(where):
            numbers += [int(os.path.splitext(n)[0]) for n in os.listdir(where)
                        if os.path.splitext(n)[0].isdigit()]
    return max(numbers) + 1


def _write(task_dir, which, request):
    where = folder(task_dir, which)
    os.makedirs(where, exist_ok=True)
    import yaml
    atomic_io.atomic_write_text(os.path.join(where, f"{request['number']}.yml"),
                                yaml.safe_dump(request, sort_keys=False))


def save(task_dir, request):
    """Rewrite a pending request, such as after it was shown."""
    _write(task_dir, PENDING, request)


def close(task_dir, request, outcome, reason="", **extra):
    """Move a pending request to `closed/` with its outcome. A request that is
    already closed is left as it is, so a second close changes nothing."""
    path = os.path.join(folder(task_dir, PENDING), f"{request['number']}.yml")
    if os.path.isfile(os.path.join(folder(task_dir, CLOSED), f"{request['number']}.yml")):
        if os.path.isfile(path):
            os.remove(path)
        return
    body = dict(request)
    body.update(outcome=outcome, closed_at=_now())
    if reason:
        body["reason"] = reason
    body.update({k: v for k, v in extra.items() if v is not None})
    _write(task_dir, CLOSED, body)
    if os.path.isfile(path):
        os.remove(path)


def _now():
    return now_iso().replace("+00:00", "Z")


def same_subject(a, b):
    return (a.get("form"), a.get("value")) == (b.get("form"), b.get("value"))


def digest(request):
    """The digest of what the person is shown of a request."""
    shown = {k: request.get(k) for k in SHOWN_FIELDS}
    # Covered only when present, so a request written before the field keeps its digest.
    if request.get("review"):
        shown["review"] = request["review"]
    if request.get("waiver"):
        shown["waiver"] = request["waiver"]
    if "spec_sha256" in request:
        shown.update(spec=request.get("spec"), spec_sha256=request.get("spec_sha256"))
    return hashlib.sha256(json.dumps(shown, sort_keys=True, default=str)
                          .encode("utf-8")).hexdigest()


def clean(text):
    """Text an agent wrote, as the person is shown it: no control, format or
    line-separator character, so an escape sequence cannot move the cursor
    over, or a direction override reorder, the line that names the subject.
    Unlike `approval_records.shown_text` it keeps the whole text."""
    text = "" if text is None else str(text)
    return approval_records.shown_text(text, limit=len(text))


def subject_text(request):
    """The subject in words, as Compass shows it."""
    form, value = request.get("form"), request.get("value")
    if form == "guardrail":
        return "guardrail 5 sign-off (irreversible work)"
    if form == "check":
        return f"human check '{value}'"
    if form == "artifact":
        return f"document '{value}'"
    if form == "checkpoint":
        return f"the {value} checkpoint"
    if form == "waiver":
        check = clean((request.get("waiver") or {}).get("check"))
        return f"waiver {value} of check '{check}' on this issue only"
    if form == "ship":
        return f"the ship approval of the change of issue {request.get('issue')}"
    return "the decisions taken for you"


def _generation(request):
    value = request.get("generation")
    return "none" if value is None else value


def _pointer_issue(project):
    """The issue a project's `.compass/current-task` names, or None."""
    try:
        with open(os.path.join(project, ".compass", "current-task"), encoding="utf-8") as fh:
            slug = fh.read().strip()
    except OSError:
        return None
    if not slug or slug in (".", "..") or "/" in slug or "\\" in slug:
        return None
    task_dir = os.path.join(project, ".compass", "work", slug)
    return task_dir if os.path.isdir(task_dir) else None


def same_number_elsewhere(task_dir, number, timeout=5):
    """True when the current issue of another worktree holds a pending request
    with this number, so `/compass:approve <n>` alone would be ambiguous and the
    person is given the `--issue` form."""
    from compass_pkg import worktree_lookup
    project = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(task_dir))))
    listing = worktree_lookup.list_worktrees(project, timeout=timeout)
    here = os.path.realpath(project)
    for tree in listing.trees:
        if os.path.realpath(tree.project) == here:
            continue
        other = _pointer_issue(tree.project)
        if other and any(r["number"] == number for r in pending(other)):
            return True
    return False


def shown_text(request, issue_form=False):
    """What Compass shows the person: the facts the CLI derived first, then
    the agent's words, marked as such. With `issue_form`, the commands name
    the issue."""
    labels = ", ".join(request.get("labels") or []) or "none"
    lines = [f"Compass: approval request {request['number']} - {subject_text(request)}",
             f"  issue {request.get('issue')}, generation {_generation(request)}, "
             f"labels: {labels}"]
    if request.get("document_digest"):
        lines.append(f"  document digest {str(request['document_digest'])[:12]}")
    if "spec_sha256" in request:
        lines.append(f"  the spec {clean(request.get('spec'))}, sha256 "
                     f"{str(request.get('spec_sha256') or 'none: no file')[:12]}")
    if request.get("scope"):
        lines.append(f"  the agent's description: \"{clean(request['scope'])}\"")
    if request.get("waiver"):
        lines.append(f"  the reason the waiver records: "
                     f"\"{clean(request['waiver'].get('reason'))}\"")
    lines += [f"  {line}" for line in review_lines(request)]
    flag = f" --issue {request.get('issue')}" if issue_form else ""
    if request.get("form") == "waiver":
        lines.append(f"  /compass:approve waiver {request.get('value')}{flag} also answers it.")
    lines.append(f"  Type /compass:approve {request['number']}{flag} or /compass:reject "
                 f"{request['number']} <reason>{flag}.")
    return "\n".join(lines)


def review_lines(request):
    """The stage review a checkpoint request holds, as lines: a heading, then
    one line per question. Empty when it holds no review."""
    review = request.get("review") or {}
    if not review.get("questions"):
        return []
    return ([f"the {review.get('stage')} review - answer each question with what you "
             f"checked:"] + [f"  - {q}" for q in review["questions"]])


def mark_shown(task_dir, request):
    """Stamp a pending request with the time and the digest it was shown at."""
    request = dict(request)
    request.update(shown_at=_now(), shown_digest=digest(request))
    save(task_dir, request)
    return request


def stop_message(compass_dir, env):
    """The Stop hook's message: each pending request of the session's issue
    that has not been shown, in Compass's words, stamped as shown. Empty when
    there is none or the issue cannot be named; the issue is `COMPASS_ISSUE`,
    else the pointer, and is never guessed."""
    work = os.path.join(compass_dir, "work")
    slug = (env.get("COMPASS_ISSUE") or "").strip()
    if not slug:
        try:
            with open(os.path.join(compass_dir, "current-task"), encoding="utf-8") as fh:
                slug = fh.read().strip()
        except OSError:
            return ""
    if not slug or "/" in slug or slug in (".", "..") or not os.path.isdir(
            os.path.join(work, slug)):
        return ""
    task_dir = os.path.join(work, slug)
    shown = []
    with approvals.lock(task_dir):
        for request in pending(task_dir):
            if request.get("shown_at") or request.get("issue") != slug:
                continue
            shown.append(shown_text(mark_shown(task_dir, request),
                                    same_number_elsewhere(task_dir, request["number"])))
    return "\n".join(shown)


def write(task_dir, form, value, scope):
    """Write a pending request for the subject and return it. A pending
    request for the same subject closes as `replaced`. The caller has run the
    refusals."""
    task, _ = load_manifest(task_dir)
    request = {"number": _next_number(task_dir),
               "issue": os.path.basename(os.path.normpath(task_dir)),
               "generation": task.get("generation"),
               "form": form, "value": value, "scope": scope,
               "labels": list((task.get("assessment") or {}).get("labels") or []),
               # No form names a document since 9.0.0 (ADR-091); the key stays so a
               # request reads as one written before.
               "document_digest": None,
               "requested_at": _now(),
               "nonce": secrets.token_hex(16)}
    if form == "waiver":
        from compass_pkg import waiver_records
        held = waiver_records.find(task, value) or {}
        request["waiver"] = {"check": held.get("check"), "reason": held.get("reason")}
    if form == "checkpoint":
        from compass_pkg import checkpoint_outcomes
        review = checkpoint_outcomes.review(task, task_dir, value)
        if review:
            request["review"] = review
        # The spec the person is asked to approve; the prompt hook refuses to
        # record when it changed after the request was shown (ADR-095).
        from compass_pkg import scenario_freeze
        request.update(scenario_freeze.fields(task, task_dir, value))
    for old in pending(task_dir):
        if same_subject(old, request):
            close(task_dir, old, REPLACED, replaced_by=request["number"])
    _write(task_dir, PENDING, request)
    return request


# --- the verb -------------------------------------------------------------------------

def _form_of(args):
    for form in ("check", "guardrail", "checkpoint", "waiver"):
        value = getattr(args, form, None)
        if value:
            return form, value
    if getattr(args, "ship", False):
        return "ship", None
    return "decisions", None


def _terminal_command(request):
    """The exact `compass evidence approve` command for a person's terminal."""
    form, value = request["form"], request["value"]
    words = ["evidence", "approve", "--issue", request["issue"]]
    words += [f"--{form}"] if form in ("decisions", "ship") else [f"--{form}", value]
    words += ["--approver", "<you>", "--role", "<role>"]
    if request.get("scope"):
        words += ["--scope", request["scope"]]
    word, _ = launcher.terminal_command()
    return " ".join([word] + [w if w in ("<you>", "<role>") else shlex.quote(w)
                              for w in words])


def _lean_form(args):
    """With no form given, the approval the issue waits for next: the `specify`
    checkpoint while the scenarios owe a person's approval, then the `G5`
    sign-off, then the ship approval. Sets the form on `args`, and a scope for
    `G5`, which needs one. A session that left the form out was refused with
    the usage text (the 9.0.0 measurement)."""
    if any(getattr(args, name, None) for name in
           ("check", "guardrail", "checkpoint", "waiver", "decisions", "ship")):
        return
    from compass_pkg import scenario_freeze, ship_approval
    from compass_pkg.checks import _check_human_approval
    task_dir = resolve_issue_dir(args.task)
    task, _ = load_manifest(task_dir)
    owed = task.get("evidence_required") or []
    if scenario_freeze.owes_signoff(task) and not scenario_freeze.signed_off(task):
        args.checkpoint = "specify"
    elif "human-approval" in owed and _check_human_approval(task, task_dir)[0] is not True:
        args.guardrail = approval_records.G5
        slug = os.path.basename(os.path.normpath(task_dir))
        labels = ", ".join((task.get("assessment") or {}).get("labels") or [])
        args.scope = args.scope or f"the change of issue {slug}, labeled {labels}"
    elif ship_approval.owed(task):
        args.ship = True
    else:
        raise CompassError(f"{VERB}: this issue waits for no approval. No request was written.")


def cmd_evidence_request(args):
    _lean_form(args)
    form, value = _form_of(args)
    scope = approvals.text(args.scope)
    answer = approvals.Answer(form, value, approval_records.APPROVED, None, "", scope)
    task_dir = resolve_issue_dir(args.task)
    if form == "checkpoint" and value == "specify":
        # The lean path: the agent writes the scenarios in the acceptance
        # criteria only, so the manifest takes them from there before the
        # person is asked to approve them.
        from compass_pkg import lean
        from compass_pkg.core import save_manifest
        held, held_path = load_manifest(task_dir)
        if lean.sync_scenarios(held, lean.spec_of(task_dir)):
            save_manifest(held, held_path)
    with approvals.lock(task_dir):
        reason = approvals.refusal(task_dir, answer)
        if reason:
            raise CompassError(reason.replace(f"{approvals.VERB}: ", f"{VERB}: ", 1)
                               + " No request was written.")
        request = write(task_dir, form, value, scope)
    subject = subject_text(request)
    command = None
    if os.environ.get(CHANNEL_ENV) == "terminal":
        command = _terminal_command(request)
        tell = ("This host has no person-only approval event, so give the person this exact "
                "command for their own terminal, with no `!` prefix, and stop:")
    else:
        flag = (f" --issue {request['issue']}"
                if same_number_elsewhere(task_dir, request["number"]) else "")
        tell = (f"Ask the person to type /compass:approve {request['number']}{flag} or "
                f"/compass:reject {request['number']} <reason>{flag}, and stop. Compass "
                f"shows them the request at the end of your turn; never record the "
                f"approval yourself.")
    code = say(args, f"{VERB}: request {request['number']} written - {subject}.",
               detail=[f"request    : {os.path.join(folder(task_dir), str(request['number']))}.yml",
                       f"issue      : {request['issue']}, generation {_generation(request)}"],
               request=request["number"], form=form, value=value, scope=scope or None,
               issue=request["issue"], generation=request["generation"], next=tell,
               command=command,
               **({"review": request["review"]} if request.get("review") else {}))
    if resolve_mode(args) not in ("json", "quiet"):
        # Printed apart from the hand-off, which shortens long lines: the
        # command must reach the person whole, and so must each question.
        for line in review_lines(request):
            print("  " + line)
        print(textwrap.fill(tell, 96, initial_indent="  ", subsequent_indent="  "))
        if command:
            print("    " + command)
            hint = launcher.terminal_command()[1]
            if hint:
                print("  " + hint)
    return code


def register(evidence_subs):
    """Add `request` to the `evidence` group."""
    p = evidence_subs.add_parser(
        "request", help="ask a person for an approval: write a pending request that Compass "
                        "shows them", allow_abbrev=False)
    # The lean path: with no form, the request is for the approval the issue
    # waits for next (`_lean_form`).
    form = p.add_mutually_exclusive_group(required=False)
    form.add_argument("--check", help="id of the human check")
    form.add_argument("--guardrail", metavar=approval_records.G5,
                      help="the sign-off of guardrail `G5`; needs --scope")
    form.add_argument("--decisions", action="store_true",
                      help="the decisions taken for the person")
    form.add_argument("--checkpoint", metavar="STAGE",
                      help="the hand-off of this checkpoint stage: a path stage, or a "
                           "legacy one on an issue assessed before 9.0.0")
    form.add_argument("--waiver", metavar="W-N",
                      help="the approval of this waiver of the issue (compass waiver add)")
    form.add_argument("--ship", action="store_true",
                      help="the ship approval of the change of the issue, when no review of "
                           "its merged pull request gives it")
    issue_arg(p)
    p.add_argument("--scope", default="",
                   help="what the approval covers, in your words; required with --check and "
                        "--guardrail")
    p.set_defaults(func=cmd_evidence_request, output_kind="hand-off")
