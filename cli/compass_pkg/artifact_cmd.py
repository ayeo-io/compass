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
    """`compass issue artifact-path <kind>` - where a document is, one answer.

    Exists for the two hooks. They are shell and cannot import the resolver.
    A second resolver in bash would come to disagree with the Python one
    about where a document lives.

    Exits non-zero and prints nothing when it is not there. A bash caller
    reads the exit code first; a plausible path for a missing document would
    let a hook conclude that assessment ran when it did not.
    """
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    kind = args.kind[:-3] if args.kind.endswith(".md") else args.kind
    state, path, reason = resolve_artifact(task_dir, kind)
    if state != FOUND:
        raise CompassError(
            "%s: %s (%s)" % (kind, state, reason))
    print(path)
    return 0


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


def cmd_issue_artifact(args):
    """`compass issue artifact set <kind> --status <s> [--reason ...]`.

    Refuses a kind the issue never earned, the way `tdd-red --scenario`
    refuses a scenario id that is not in the manifest - a status set on a document
    nobody asked for is a typo that would otherwise be stored as a decision.

    An omission MUST carry a reason. Without one, a document deliberately
    dropped and a document nobody got to look the same on the page, and telling
    those apart is the reason the registry exists.
    """
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    path = manifest_path(task_dir)
    task = load_yaml(path)
    arts = [a for a in (task.get("artifacts") or []) if isinstance(a, dict)]

    entry = next((a for a in arts if a.get("kind") == args.kind), None)
    if entry is None:
        earned = ", ".join(sorted(a.get("kind", "?") for a in arts)) or "none"
        raise CompassError(
            "%r is not a document this issue earned (it earned: %s). The "
            "artifact set is computed from the assessment - re-run "
            "`compass approach evaluate --write`, or re-assess with "
            "`/compass:assess --reassess` if the work really changed shape."
            % (args.kind, earned))

    if args.status == "omitted" and not (args.reason or "").strip():
        raise CompassError(
            "omitting %r needs --reason. An omission with no reason is "
            "indistinguishable from a document nobody got to, and telling "
            "those apart is the whole point of recording it." % args.kind)

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
        entry["path"] = rel.replace(os.sep, "/")

    if args.status != "omitted":
        _refuse_unreadable(task, task_dir, args.kind)
    from compass_pkg import artifact_status, freshness

    view = _view_or_none(task_dir)
    digest_now = _own_digest(task, task_dir, entry)
    rewound = artifact_status.register(task, view, entry, args.status, digest_now)
    if (args.reason or "").strip() and not rewound:
        entry["reason"] = args.reason.strip()
    task["artifacts"] = arts
    # Saved before the digest is read: the digest resolves the document through
    # the registry on disk.
    save_manifest(task, path)
    recorded = _record_freshness(view, task, task_dir, entry)
    moved = []
    if entry.get("path") and entry.get("status") in (
            artifact_status.DRAFT, artifact_status.AWAITING, artifact_status.APPROVED):
        moved = artifact_status.stage_exit(
            task, view, artifact_status.owning_stage(view, args.kind),
            artifact_status.BY_ARTIFACT_SET)
        # A document the `verify` stage owns, registered after a `verify` gate
        # passed, is approved now: that pass was the stage's record.
        if (artifact_status.owning_stage(view, args.kind) == artifact_status.STAGE_VERIFY
                and entry.get("status") == artifact_status.DRAFT
                and artifact_status.verify_record_exists(task, view)):
            moved += artifact_status.stage_exit(
                task, view, artifact_status.STAGE_VERIFY, artifact_status.BY_ARTIFACT_SET,
                include_own=True, earlier=False)
    save_manifest(task, path)
    from compass_pkg.terminal import say

    return say(args, "compass issue artifact set: %s -> %s" % (args.kind, entry["status"]),
               detail=["reason: %s" % entry.get("reason", "(none recorded)")]
               + recorded + artifact_status.moved_line(moved),
               kind=args.kind, status=entry["status"],
               reason=entry.get("reason"), approved_by=entry.get("approved_by"),
               approved_at=entry.get("approved_at"), moved=moved)
