# compass_pkg.approval_requests - `compass evidence request` and the request files
"""An agent asks a person for an approval with a request (ADR-068 decision 1).

`compass evidence request` takes the five subject forms of `compass evidence
approve`, runs the same refusals (`approvals.record` with `save=False`), and
writes one request file:

    .compass/work/<slug>/approval-requests/pending/<n>.yml

A request holds facts the CLI derives - the issue, its generation and labels,
the subject, a document's digest - and the agent's description of the scope.
It also holds a single-use `nonce`, which the record that answers it copies.
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
# approvals, atomic_io, core, old_names, terminal. artifact_cmd is imported inside the
# function that digests a document.
from __future__ import annotations

import hashlib
import json
import os
import secrets
import shlex
import textwrap

from compass_pkg import approval_records, approvals, atomic_io, old_names
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
    return hashlib.sha256(json.dumps(shown, sort_keys=True, default=str)
                          .encode("utf-8")).hexdigest()


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
    return "the decisions taken for you"


def _generation(request):
    value = request.get("generation")
    return "none" if value is None else value


def shown_text(request):
    """What Compass shows the person: the facts the CLI derived first, then
    the agent's words, marked as such."""
    labels = ", ".join(request.get("labels") or []) or "none"
    lines = [f"Compass: approval request {request['number']} - {subject_text(request)}",
             f"  issue {request.get('issue')}, generation {_generation(request)}, "
             f"labels: {labels}"]
    if request.get("document_digest"):
        lines.append(f"  document digest {str(request['document_digest'])[:12]}")
    if request.get("scope"):
        lines.append(f"  the agent's description: \"{request['scope']}\"")
    lines.append(f"  Type /compass:approve {request['number']} or /compass:reject "
                 f"{request['number']} <reason>.")
    return "\n".join(lines)


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
            shown.append(shown_text(mark_shown(task_dir, request)))
    return "\n".join(shown)


def document_digest(task_dir, task, kind):
    """The digest of a registered document's file as it is now, or None."""
    from compass_pkg import artifact_cmd
    entry = next((a for a in task.get("artifacts") or []
                  if isinstance(a, dict) and a.get("kind") == kind), None)
    return None if entry is None else artifact_cmd._own_digest(task, task_dir, entry)


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
               "document_digest": (document_digest(task_dir, task, value)
                                   if form == "artifact" else None),
               "requested_at": _now(),
               "nonce": secrets.token_hex(16)}
    for old in pending(task_dir):
        if same_subject(old, request):
            close(task_dir, old, REPLACED, replaced_by=request["number"])
    _write(task_dir, PENDING, request)
    return request


# --- the verb -------------------------------------------------------------------------

def _form_of(args):
    for form in ("check", "guardrail", "artifact", "checkpoint"):
        value = getattr(args, form, None)
        if value:
            return form, value
    return "decisions", None


def _terminal_command(request):
    """The exact `compass evidence approve` command for a person's terminal."""
    form, value = request["form"], request["value"]
    words = ["compass", "evidence", "approve", "--issue", request["issue"]]
    words += ["--decisions"] if form == "decisions" else [f"--{form}", value]
    words += ["--approver", "<you>", "--role", "<role>"]
    if request.get("scope"):
        words += ["--scope", request["scope"]]
    return " ".join(w if w in ("<you>", "<role>") else shlex.quote(w) for w in words)


def cmd_evidence_request(args):
    form, value = _form_of(args)
    scope = approvals.text(args.scope)
    answer = approvals.Answer(form, value, approval_records.APPROVED, None, "", scope)
    task_dir = resolve_issue_dir(args.task)
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
        tell = (f"Ask the person to type /compass:approve {request['number']} or "
                f"/compass:reject {request['number']} <reason>, and stop. Compass shows them "
                f"the request at the end of your turn; never record the approval yourself.")
    code = say(args, f"{VERB}: request {request['number']} written - {subject}.",
               detail=[f"request    : {os.path.join(folder(task_dir), str(request['number']))}.yml",
                       f"issue      : {request['issue']}, generation {_generation(request)}"],
               request=request["number"], form=form, value=value, scope=scope or None,
               issue=request["issue"], generation=request["generation"], next=tell,
               command=command)
    if resolve_mode(args) not in ("json", "quiet"):
        # Printed apart from the hand-off, which shortens long lines: the
        # command must reach the person whole.
        print(textwrap.fill(tell, 96, initial_indent="  ", subsequent_indent="  "))
        if command:
            print("    " + command)
    return code


def register(evidence_subs):
    """Add `request` to the `evidence` group."""
    p = evidence_subs.add_parser(
        "request", help="ask a person for an approval: write a pending request that Compass "
                        "shows them", allow_abbrev=False)
    form = p.add_mutually_exclusive_group(required=True)
    form.add_argument("--check", type=old_names.check_type, help="id of the human check")
    form.add_argument("--guardrail", metavar=approval_records.G5,
                      help="the sign-off of guardrail `G5`; needs --scope")
    form.add_argument("--artifact", metavar="KIND",
                      help="a document that reads awaiting-approval")
    form.add_argument("--decisions", action="store_true",
                      help="the decisions taken for the person")
    form.add_argument("--checkpoint", metavar="STAGE",
                      help="the hand-off of this checkpoint stage")
    issue_arg(p)
    p.add_argument("--scope", default="",
                   help="what the approval covers, in your words; required with --check and "
                        "--guardrail")
    p.set_defaults(func=cmd_evidence_request, output_kind="hand-off")
