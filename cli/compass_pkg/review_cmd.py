# compass_pkg.review_cmd - `compass evidence review`
"""Record a judgement against a judged check.

The verb reads the check from the issue's effective view, digests the
check's declared inputs as they are now, writes the review record into the
issue's `evidence/` folder and registers it as `manual-review` evidence with
`check: <id>`. `compass check` then reads it through `review_records`.
"""
# DEPENDENCY: standard library (os, re); compass_pkg.atomic_io, core,
# effective, red_first, review_records, terminal.
from __future__ import annotations

import os
import re

import yaml

from compass_pkg import effective, review_records
from compass_pkg.atomic_io import atomic_write_text
from compass_pkg.core import (CompassError, load_manifest, now_iso, resolve_issue_dir,
                              save_manifest, issue_arg)
from compass_pkg.red_first import content_digest
from compass_pkg.terminal import say

VERDICTS = ("pass", "fail")


def parse_reviewer(text):
    """`{kind, id}` from `--reviewer`: `agent` or `agent:<session id>` is an
    agent session, any other value is a person's id."""
    text = " ".join(str(text or "").split())
    if not text:
        raise CompassError("compass evidence review: --reviewer must name who judged: "
                           "`agent`, `agent:<session id>` or a person's id.")
    if text == review_records.AGENT:
        return {"kind": "agent", "id": review_records.AGENT}
    if text.startswith(review_records.AGENT + ":"):
        session = text[len(review_records.AGENT) + 1:].strip()
        if not session:
            raise CompassError("compass evidence review: --reviewer 'agent:' names no "
                               "session; give `agent:<session id>` or `agent`.")
        return {"kind": "agent", "id": session}
    return {"kind": "person", "id": text}


def _check_of(view, check_id):
    if view is None:
        raise CompassError("compass evidence review: this issue has no configuration to "
                           "read its checks from. Run `compass approach evaluate --write`.")
    checks = view.config.get("checks") or {}
    check = checks.get(check_id)
    judged = sorted(name for name, body in checks.items()
                    if isinstance(body, dict) and body.get("kind") == "judged")
    if not isinstance(check, dict):
        known = f"the judged checks are {', '.join(judged)}" if judged else \
            "it configures no judged check"
        raise CompassError(f"compass evidence review: no such check '{check_id}' in this "
                           f"issue's configuration; {known}.")
    if check.get("kind") != "judged":
        raise CompassError(f"compass evidence review: '{check_id}' is a {check.get('kind')} "
                           f"check, not a judged check. Only a judged check takes a review.")
    return check


def _numbered(task, task_dir, check_id):
    """The next number for a record of the check: one that no evidence id and
    no file in `evidence/` already uses, and the evidence id for it."""
    taken = {e.get("id") for e in task.get("evidence") or [] if isinstance(e, dict)}
    number = 1 + len([e for e in task.get("evidence") or []
                      if isinstance(e, dict) and e.get("check") == check_id])
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", check_id)
    while (f"EV-REVIEW-{check_id}-{number}" in taken
           or os.path.exists(os.path.join(task_dir, f"evidence/review-{safe}-{number}.yml"))):
        number += 1
    return number, f"EV-REVIEW-{check_id}-{number}"


def cmd_evidence_review(args):
    check_id = args.check
    if args.verdict not in VERDICTS:
        raise CompassError(f"compass evidence review: the verdict must be one of "
                           f"{' or '.join(VERDICTS)}, not '{args.verdict}'.")
    reason = " ".join(str(args.reason or "").split())
    if not reason:
        raise CompassError("compass evidence review: --reason must say what was judged "
                           "and why; a verdict with no reason is not a review.")
    reviewer = parse_reviewer(args.reviewer)
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    check = _check_of(effective.view_or_legacy(task_dir), check_id)
    if not review_records.declared_inputs(check):
        raise CompassError(f"compass evidence review: '{check_id}' declares no inputs, so "
                           f"a review of it has nothing to stay current with. Add `inputs:` "
                           f"(artifact ids or evidence ids) to the check.")
    inputs = review_records.current_digests(check, task, task_dir)
    missing = [one for one, found in inputs.items() if found is None]
    if missing:
        raise CompassError(f"compass evidence review: {', '.join(missing)} cannot be found, "
                           f"so '{check_id}' cannot be reviewed. Write the document or "
                           f"register the evidence, then review again.")
    number, evidence_id = _numbered(task, task_dir, check_id)
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", check_id)
    path = f"evidence/review-{safe}-{number}.yml"
    record = {"schema": 1, "check": check_id, "issue": os.path.basename(os.path.normpath(task_dir)),
              "verdict": args.verdict, "reason": reason, "reviewer": reviewer}
    if args.scope:
        record["scope"] = " ".join(str(args.scope).split())
    record.update({"inputs": inputs, "generation": task.get("generation") or None,
                   "definition_digest": review_records.definition_digest(check),
                   "at": now_iso().replace("+00:00", "Z")})
    record["content_digest"] = content_digest(record)
    full = os.path.join(task_dir, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    if os.path.exists(full):
        raise CompassError(f"compass evidence review: {path} already exists; a record is "
                           f"never overwritten.")
    atomic_write_text(full, yaml.safe_dump(record, sort_keys=False))
    task.setdefault("evidence", []).append(
        {"id": evidence_id, "type": "manual-review", "path": path, "check": check_id})
    save_manifest(task, task_path)
    return say(args, f"compass evidence review: {check_id} - {args.verdict} recorded as "
                     f"{evidence_id}.",
               detail=[f"record : {path}"] + [f"input  : {one} {found}"
                                              for one, found in inputs.items()],
               check=check_id, verdict=args.verdict, evidence_id=evidence_id, path=path,
               reviewer=reviewer, scope=record.get("scope"), inputs=inputs,
               generation=record["generation"],
               definition_digest=record["definition_digest"], at=record["at"])


def register(evidence_subs):
    """Add `review` to the `evidence` group."""
    p = evidence_subs.add_parser(
        "review", help="record a judgement against a judged check")
    p.add_argument("check", help="id of the judged check")
    issue_arg(p)
    p.add_argument("--verdict", required=True, choices=VERDICTS,
                   help="what was judged: pass or fail")
    p.add_argument("--reason", required=True, help="what was read and why the verdict holds")
    p.add_argument("--reviewer", required=True,
                   help="who judged: `agent`, `agent:<session id>` or a person's id")
    p.add_argument("--scope", help="what the judgement covers (optional)")
    p.set_defaults(func=cmd_evidence_review, output_kind="hand-off")
