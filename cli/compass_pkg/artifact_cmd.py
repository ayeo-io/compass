#!/usr/bin/env python3
# =============================================================================
# compass - the commands that set and find an issue's documents
# =============================================================================
# `compass issue artifact set` records a document's status and path in the
# issue's registry, and `compass issue artifact-path` prints where a document
# is. The review page they once fed is gone: `compass issue render` writes the
# issue page (ADR-051).
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library. This module reaches it through compass_pkg.core.
# =============================================================================
"""Setting and finding the documents in an issue's registry."""
from __future__ import annotations

import os

from compass_pkg.core import (FOUND, CompassError, _registered_path, docs_dir, load_yaml,
                              manifest_path, resolve_artifact, resolve_issue_dir, save_manifest)

# The statuses a document can be in. `draft` is what routing seeds; the rest
# are decisions a person records with `compass issue artifact set`.
ARTIFACT_STATUSES = ("draft", "awaiting-approval", "approved", "superseded",
                     "omitted")


def cmd_issue_artifact_path(args):
    """`compass issue artifact-path <kind> [--round N]` - where a document is, one answer.

    The stages use it to learn where to write a document, and to learn the
    home of a kind the issue earned and has not written yet. The two hooks do
    not call it: each runs a short Python snippet that calls the resolver in
    `core` directly, so there is no second resolver in bash to disagree with
    the Python one about where a document lives.

    Exits non-zero and prints nothing when it is not there. A bash caller
    reads the exit code first; a plausible path for a missing document would
    let a hook conclude that assessment ran when it did not.

    A kind that repeats (`review-<n>.md`) answers with its latest round, or
    with the round `--round` names.
    """
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    kind = args.kind[:-3] if args.kind.endswith(".md") else args.kind
    asked = getattr(args, "round", None)
    state, path, reason = resolve_artifact(task_dir, kind, asked)
    if state != FOUND and asked is None:
        # A kind the issue earned and has not written yet: the verb names the home the
        # writer must use. The hooks ask the resolver, not this verb, so they still
        # read an unwritten record as absent.
        earned = _earned_home(task_dir, kind)
        if earned:
            print(earned)
            return 0
    if state != FOUND:
        raise CompassError(
            "%s%s: %s (%s)" % (kind, " round %d" % asked if asked else "", state, reason))
    print(path)
    return 0


def _earned_home(task_dir, kind):
    """The project-relative home of `kind` when the issue's registry holds an entry for
    it that names no path yet, else None. A kind that repeats has no one home."""
    from compass_pkg import artifact_kinds
    task = load_yaml(manifest_path(task_dir)) or {}
    held = [a for a in task.get("artifacts") or []
            if isinstance(a, dict) and a.get("kind") == kind and not a.get("path")
            and a.get("status") not in ("omitted", "superseded")]
    if not held:
        return None
    declared = artifact_kinds.entry(_view_or_none(task_dir), kind) or artifact_kinds.shipped().get(kind)
    if not declared or artifact_kinds.repeats(declared):
        return None
    return artifact_kinds.home(task_dir, declared)


def _view_or_none(task_dir):
    """The configuration view of the issue, or None when it has none or it
    cannot be read: an unreadable configuration records nothing and moves no
    document to a human check."""
    from compass_pkg import effective

    try:
        return effective.view_or_legacy(task_dir)
    except Exception:  # noqa: BLE001
        return None


def _own_digest(task, task_dir, entry):
    """The digest of the entry's file as it is now, read from the path the entry
    holds in memory, or None when there is no readable file."""
    from compass_pkg import freshness

    rel = entry.get("path")
    if not rel:
        found = freshness._digest(task, task_dir, entry.get("kind"))
        return None if found == freshness.UNREADABLE else found
    resolved, refused = _registered_path(task_dir, rel)
    if refused:
        return None
    from compass_pkg import review_records
    try:
        return review_records.file_digest(resolved)
    except OSError:
        return None


def _record_freshness(view, task, task_dir, entry):
    """Stamp the entry with the digests of its file and its upstream, whatever
    the capability `artifact-freshness` says: recording is always on and only
    the refusals are opt-in. The lines to show; none when nothing changed."""
    from compass_pkg import freshness

    if not freshness.stamp(view, task, task_dir, entry):
        return []
    upstream = sorted(entry.get("upstream") or {})
    return ["freshness: digest recorded"
            + (" against %s" % ", ".join(upstream) if upstream else "")]


def _refuse_unreadable(task, task_dir, kind):
    """With the capability `artifact-freshness` on, refuse to register a
    document that, or an upstream that, exists and cannot be read. Nothing is
    saved: a status stored with no digest would leave the document untracked."""
    from compass_pkg import effective, freshness

    try:
        view = effective.view_or_legacy(task_dir)
    except Exception:  # noqa: BLE001 - an unreadable configuration records nothing
        return
    found = freshness.unreadable(view, task, task_dir, kind)
    if found:
        raise CompassError(
            "%s cannot be read, so its digest cannot be recorded. Make the file "
            "readable and register the document again." % ", ".join(found))


#: The close-out decisions a spike records (`spike-conclusion-present` reads them).
SPIKE_DECISIONS = ("discard", "graduate-to-delivery", "defer")
SPIKE_EVIDENCE_ID = "EV-SPIKE-CONCLUSION"
NEXT_FLAG = "--next-issue"


def _label(entry):
    """A document's name for a message: its kind, and the round of a kind that
    repeats."""
    rnd = entry.get("round")
    return "%s round %d" % (entry.get("kind"), rnd) if isinstance(rnd, int) else str(entry.get("kind"))


def _entry_id(kind, rnd=None):
    base = "ART-" + kind.upper().replace("-", "_")
    return "%s-%d" % (base, rnd) if rnd else base


def _refuse_home(task_dir, kind, spec, rel):
    """Refuse a path that is not the one home of `kind`: the issue's documents
    folder and the kind's filename. Returns the round of a kind that repeats."""
    import posixpath

    from compass_pkg import artifact_kinds

    folder = docs_dir(task_dir)
    given = posixpath.normpath(rel.replace(os.sep, "/"))
    if artifact_kinds.repeats(spec):
        rnd = artifact_kinds.round_of(spec, posixpath.basename(given))
        if rnd is not None and posixpath.dirname(given) == folder:
            return rnd
    elif given == artifact_kinds.home(task_dir, spec):
        return None
    pattern = artifact_kinds.repeats(spec)
    raise CompassError(
        "%r is not where %s lives. A %s is kept in the issue's documents folder as %s%s - "
        "write it there and register that path."
        % (rel, kind, kind, artifact_kinds.home(task_dir, spec),
           ", where <n> is the round, counted from 1 (a filename like review-1.md)"
           if pattern else ""))


def _decision_arguments(args, kind):
    """The validated `(decision, next_issue)` of `--decision`, or `(None, None)`.
    Refuses before anything is written."""
    decision = getattr(args, "decision", None)
    next_issue = getattr(args, "next_issue", None)
    if decision is None and next_issue is None:
        return None, None
    if kind != "spike-conclusion":
        raise CompassError(
            "--decision and %s record how a spike closes, so they apply to "
            "spike-conclusion only, not to %r." % (NEXT_FLAG, kind))
    if decision is None:
        raise CompassError("%s goes with --decision graduate-to-delivery." % NEXT_FLAG)
    if decision not in SPIKE_DECISIONS:
        raise CompassError(
            "--decision %r is not a way a spike closes. The decisions are: %s."
            % (decision, ", ".join(SPIKE_DECISIONS)))
    if decision == "graduate-to-delivery" and not (next_issue or "").strip():
        raise CompassError(
            "--decision graduate-to-delivery needs %s <slug>, the delivery issue "
            "the spike graduates to. Graduation is a fresh assessment, not a merge." % NEXT_FLAG)
    if next_issue and decision != "graduate-to-delivery":
        raise CompassError("%s goes with --decision graduate-to-delivery only." % NEXT_FLAG)
    return decision, (next_issue or "").strip() or None


def _write_spike_record(task, task_dir, entry, decision, next_issue):
    """Write or update the one `spike-conclusion` evidence record that
    `spike-conclusion-present` reads, naming the registered document. The check
    stays as it is; this is the command that gives it the record it needs."""
    from compass_pkg.core import find_upwards

    if not entry.get("path"):
        raise CompassError(
            "--decision records the decision beside the document, so the document needs a "
            "path: pass --path with the spike conclusion's file.")
    root = find_upwards(os.path.abspath(task_dir), ".compass") or os.path.abspath(task_dir)
    named = os.path.relpath(os.path.join(root, entry["path"]), task_dir).replace(os.sep, "/")
    records = task.setdefault("evidence", [])
    record = next((e for e in records if isinstance(e, dict)
                   and e.get("type") == "spike-conclusion"), None)
    if record is None:
        record = {"id": SPIKE_EVIDENCE_ID, "type": "spike-conclusion"}
        records.append(record)
    record["path"] = named
    record["decision"] = decision
    if next_issue:
        record["next_task"] = next_issue
    else:
        record.pop("next_task", None)
    return record


def cmd_issue_artifact(args):
    """`compass issue artifact set <kind> --status <s> [--reason ...] [--round N]`.

    Refuses a kind the issue's catalogue does not declare, the way
    `tdd-red --scenario` refuses a scenario id that is not in the manifest - a
    status set on a document nobody could ask for is a typo that would
    otherwise be stored as a decision.

    A path must be the kind's one home, the issue's documents folder and the
    kind's filename. A kind that repeats (`review-<n>.md`) holds one entry per
    round; the round is read from the filename, and `--round` names an existing
    one when no path is given. With no round at all, the latest round is meant.

    An omission MUST carry a reason. Without one, a document deliberately
    dropped and a document nobody got to look the same on the page, and telling
    those apart is the reason the registry exists.

    `--decision` on the spike conclusion also writes the evidence record the
    check `spike-conclusion-present` reads.
    """
    from compass_pkg import artifact_kinds

    task_dir = resolve_issue_dir(getattr(args, "task", None))
    path = manifest_path(task_dir)
    task = load_yaml(path)
    arts = [a for a in (task.get("artifacts") or []) if isinstance(a, dict)]
    view = _view_or_none(task_dir)
    known = artifact_kinds.catalogue(view)
    spec = known.get(args.kind)
    held = [a for a in arts if a.get("kind") == args.kind]
    asked = getattr(args, "round", None)
    decision, next_issue = _decision_arguments(args, args.kind)

    if not held and spec is None:
        # A kind the issue's catalogue declares can be registered even when the
        # assessment did not earn it: a reviewer's review or a project's own
        # kind is a document nobody had to ask for. The typo guard is
        # membership of the catalogue.
        raise CompassError(
            "%r is not a kind this issue's catalogue declares (it declares: %s). "
            "A document the assessment earned is registered by `compass approach "
            "evaluate --write`; any other kind must be declared in the artifacts "
            "catalogue first." % (args.kind, ", ".join(sorted(known)) or "none"))
    repeating = (spec is not None and artifact_kinds.repeats(spec)) or any(
        isinstance(a.get("round"), int) for a in held)
    if asked is not None and not repeating:
        raise CompassError("%s does not repeat, so --round does not apply to it." % args.kind)
    if asked is not None and asked < 1:
        raise CompassError("--round counts from 1, not %d." % asked)

    rel = (getattr(args, "path", None) or "").strip()
    if rel:
        # Refused here rather than only at read time. The registry is an
        # ordinary file in the repository, so a path in it is data someone can
        # write; catching an escape when the entry is READ means the bad entry
        # is already recorded and the refusal arrives later, somewhere else.
        resolved, refused = _registered_path(task_dir, rel)
        if refused:
            raise CompassError(
                "%r resolves outside the project (%s). A registry path is "
                "measured from the project root, and an issue's document "
                "lives inside the repository - write it under %s and register "
                "that." % (rel, resolved, docs_dir(task_dir)))
    from_path = _refuse_home(task_dir, args.kind, spec, rel) if rel and spec is not None else None

    rnd = None
    if repeating:
        if from_path is not None and asked is not None and from_path != asked:
            raise CompassError(
                "--round %d does not match %s, which is round %d." % (asked, rel, from_path))
        rnd = from_path if from_path is not None else asked
        if rnd is None:
            latest = [a["round"] for a in held if isinstance(a.get("round"), int)]
            if not latest:
                raise CompassError(
                    "%s repeats, so name the round: pass --path with the round's file "
                    "(%s) or --round N." % (args.kind, artifact_kinds.filename(spec) if spec
                                            else args.kind + "-<n>.md"))
            rnd = max(latest)
        entry = next((a for a in held if a.get("round") == rnd), None)
    else:
        entry = held[0] if held else None
    if entry is None:
        entry = {"id": _entry_id(args.kind, rnd), "kind": args.kind, "status": "draft",
                 "reason": "registered by hand; no rule of the assessment asked for it"}
        if rnd is not None:
            entry["round"] = rnd
        arts.append(entry)

    if args.status == "omitted" and not (args.reason or "").strip():
        raise CompassError(
            "omitting %r needs --reason. An omission with no reason is "
            "indistinguishable from a document nobody got to, and telling "
            "those apart is the whole point of recording it." % args.kind)

    if rel:
        entry["path"] = rel.replace(os.sep, "/")
        # The Claude Code session that registered the document, so the review
        # summary can flag an agent that approves, under a delegation, a
        # document it wrote in the same session (ADR-069 decision 5).
        session = os.environ.get("CLAUDE_CODE_SESSION_ID")
        if session:
            entry["registered_session"] = session

    if args.status != "omitted":
        _refuse_unreadable(task, task_dir, args.kind)
    from compass_pkg import artifact_status, freshness

    digest_now = _own_digest(task, task_dir, entry)
    rewound = artifact_status.register(task, view, entry, args.status, digest_now)
    if (args.reason or "").strip() and not rewound:
        entry["reason"] = args.reason.strip()
    task["artifacts"] = arts
    if decision:
        _write_spike_record(task, task_dir, entry, decision, next_issue)
    # Saved before the digest is read: the digest resolves the document through
    # the registry on disk.
    save_manifest(task, path)
    recorded = _record_freshness(view, task, task_dir, entry)
    moved = []
    if entry.get("path") and entry.get("status") in (
            artifact_status.DRAFT, artifact_status.AWAITING, artifact_status.APPROVED):
        moved = artifact_status.stage_exit(
            task, view, artifact_status.owning_stage(view, args.kind),
            artifact_status.BY_ARTIFACT_SET, task_dir=task_dir)
        # A document the `verify` stage owns, registered once every `verify` gate
        # has passed, is approved now. Registered earlier, it reads `draft` and
        # the last `verify` gate pass moves it.
        if (artifact_status.owning_stage(view, args.kind) == artifact_status.STAGE_VERIFY
                and entry.get("status") == artifact_status.DRAFT
                and artifact_status.verify_gates_passed(task, view)):
            moved += artifact_status.stage_exit(
                task, view, artifact_status.STAGE_VERIFY, artifact_status.BY_ARTIFACT_SET,
                include_own=True, earlier=False, task_dir=task_dir)
    save_manifest(task, path)
    from compass_pkg.terminal import say

    detail = ["reason: %s" % entry.get("reason", "(none recorded)")]
    if decision:
        detail.append("spike conclusion recorded: %s%s" % (
            decision, " -> " + next_issue if next_issue else ""))
    return say(args, "compass issue artifact set: %s -> %s" % (_label(entry), entry["status"]),
               detail=detail + recorded + artifact_status.moved_line(moved),
               kind=args.kind, round=entry.get("round"), status=entry["status"],
               reason=entry.get("reason"), approved_by=entry.get("approved_by"),
               approved_at=entry.get("approved_at"), moved=moved)
