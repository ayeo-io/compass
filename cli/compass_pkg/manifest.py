#!/usr/bin/env python3
# =============================================================================
# compass_pkg.manifest - `compass ship-commit` and the manifest mutators
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library.
# =============================================================================

import argparse
import datetime
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile

# --- dependency check --------------------------------------------------------
# cli/compass_pkg/__init__.py already checked that the bundled copy resolves,
# or exited 3 naming the absolute path it checked, before this module's own
# code runs, so this is never anything but a normal import.
import yaml


import re as _re


import fnmatch
import re as _re
from compass_pkg import status_words
from compass_pkg.terminal import say
from compass_pkg.core import CompassError, find_compass_dir, find_governance, load_manifest, load_yaml, manifest_path, normalize_spine, now_iso, resolve_issue_dir, save_manifest
from compass_pkg.issue_layout import docs_dir_for
from compass_pkg.binding import changes_paths, declared_test_paths, _changes_id_at, _newest_bound_record
# The resolver `declared-tests-resolve` uses, so the verb accepts what the check accepts.
from compass_pkg.test_ids import _test_id_resolves, _test_is_skipped



# --- command: ship-commit -----------------------------------------------------
# `compass ship-commit`, the commit step of ship. An auto-fixing pre-commit
# hook can rewrite a staged file and abort the commit, so HEAD does not move
# and nothing reports it. So ship-commit:
#   (a) does a best-effort clean-first via the pre-commit framework when present;
#   (b) detects the no-op (HEAD unchanged), re-stages the hook's fixes, and retries once;
#   (c) ALWAYS checks that HEAD advanced and errors loudly if not.


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


def _refuse_stale_artifacts(task, task_dir):
    """With the capability `artifact-freshness` on, refuse to land while a
    document is stale. Nothing happens with the capability off, or for an
    issue whose configuration cannot be read, as before."""
    from compass_pkg import effective, freshness
    try:
        view = effective.view_or_legacy(task_dir)
    except Exception:  # noqa: BLE001 - no configuration, no capability
        return
    if not freshness.enabled(view):
        return
    try:
        text = freshness.refusal(freshness.evaluate(view, task, task_dir))
    except Exception as exc:  # noqa: BLE001 - a record that cannot be read must not land
        raise CompassError("compass ship-commit: refusing to land - artifact freshness "
                           "cannot be evaluated: %s" % exc)
    if text:
        raise CompassError(text)


def _refuse_unapproved_artifacts(task, task_dir):
    """Refuse to land while a registered document is not approved: run the
    blocking check `artifacts-approved` the way `compass check` runs it, and
    raise on a failure. A waiver that made it advisory prints one line and the
    land goes on. Nothing happens for an issue whose configuration does not
    declare the check."""
    from compass_pkg import artifact_status
    from compass_pkg.check_cmd import ADVISORY_FAILURE, _judge

    verdict = artifact_status.judged(task, task_dir, _judge)
    if verdict is None:
        return
    passed, detail = verdict
    if passed is ADVISORY_FAILURE:
        print("compass ship-commit: %s did not pass and is advisory, so the land goes on - %s"
              % (artifact_status.CHECK_ID, detail))
    elif not passed:
        raise CompassError(
            "compass ship-commit: refusing to land - the check %s failed: %s"
            % (artifact_status.CHECK_ID, detail))


def _apply_ship_exit(task, task_dir):
    """Approve the documents the ship stage owns, in the save that marks the
    issue done."""
    from compass_pkg import artifact_status, effective
    try:
        view = effective.view_or_legacy(task_dir)
    except Exception:  # noqa: BLE001 - no configuration, no human checks
        view = None
    artifact_status.stage_exit(task, view, artifact_status.STAGE_SHIP,
                               artifact_status.BY_SHIP_COMMIT, include_own=True, earlier=False)


# Files Compass writes itself that live outside any issue's directory. They
# belong in the commit that ships the issue they describe, but no author
# declares them as `changed_files` - the framework wrote them.
#
# A NAMED SET, deliberately not a `.compass/` prefix. A prefix would re-admit
# a sibling issue's artifacts, or a concurrent agent's in-progress work in the
# same tree, which is precisely the collision this scope check exists to stop.
FRAMEWORK_OWNED_PATHS = frozenset({
    ".compass/current-task",
})


def _land_scope(task, slug):
    """The paths a ship commit is allowed to contain.

    An issue's own `changed_files`, its artifact directory, its documents
    under `docs/compass/`, and the framework's own bookkeeping files above;
    when `changed_files` is not empty, the test files its scenarios declare
    too, as the stale-green check counts them, so the two checks agree on
    what the issue owns. An issue with no `changed_files` has no scope. Anything else in the commit belongs to someone else
    - a concurrent agent's edits, untracked scratch, or the unrelated files
    a repo-wide formatter just rewrote.
    """
    owned = {
        cf["path"] for cf in (task.get("changed_files") or [])
        if isinstance(cf, dict) and cf.get("path")
    }
    # ADR-006: an issue that has not said what it changes has no scope to
    # check. The declared tests widen a scope that exists; they do not
    # create one.
    if owned:
        owned |= set(declared_test_paths(task))
    return owned, f".compass/work/{slug}/"


def _docs_prefix(task, slug):
    """The issue's documents folder, as `issue_layout.docs_dir_for` names
    it - including the slug alone when the issue has no `created:`."""
    return docs_dir_for(task.get("created"), slug).rstrip("/") + "/"


def _out_of_scope(staged, owned, artifact_dir, docs_prefix=None):
    prefixes = tuple(p for p in (artifact_dir, docs_prefix) if p)
    return sorted(
        p for p in staged
        if p not in owned
        and p not in FRAMEWORK_OWNED_PATHS
        and not p.startswith(prefixes)
    )


def _stale_paths(task, task_dir, root, at_commit, judge_landed=False):
    """The issue files that differ, in `at_commit`, from what the newest
    bound green tested, as (record path, paths), or None when there is
    nothing to judge or nothing differs.

    It reuses the comparison `compass check` uses for a landed issue
    (`binding._check_landed`). `at_commit` is a tree or commit: the index's
    tree before a commit, the new commit after it, or `HEAD` for a land
    that makes no commit.

    A landed issue is not judged: its green was judged when it landed, and
    a later edit to one of its files belongs to later work. The exception
    is `judge_landed`: re-landing the issue itself at HEAD, after a review
    fix changed its files, moves `land_commit`, so the new landing must be
    a tree its newest green tested. Nothing is
    judged until every gate has passed, or when the newest record carries
    no `changes_id` - `compass check` does not judge those either.
    """
    if status_words.is_completed(task) and not judge_landed:
        return None
    gates = [g for g in task.get("gates") or [] if isinstance(g, dict)]
    if not gates or not all(g.get("status") == "pass" for g in gates):
        return None
    newest = _newest_bound_record(task, task_dir)
    if newest is None:
        return None
    record_path, record = newest
    then = record.get("changes_id")
    if not then:
        return None
    paths = changes_paths(task, record)
    now = _changes_id_at(root, at_commit, paths)
    if now is None or now == then:
        return None
    changed = [p for p in paths
               if _changes_id_at(root, then, [p]) !=
               _changes_id_at(root, at_commit, [p])]
    return record_path, changed


def _refuse_stale_green(task, task_dir, slug, root, at_commit,
                        judge_landed=False):
    """Refuse `ship-commit` when `at_commit` holds issue files that differ
    from what the newest bound green tested."""
    stale = _stale_paths(task, task_dir, root, at_commit, judge_landed)
    if stale is None:
        return
    record_path, changed = stale
    raise CompassError(
        "compass ship-commit: refusing to commit - %d of issue '%s's "
        "changed file(s) or declared test(s) changed after %s's green:\n  "
        "%s\n\nIf the tested version is on disk but not staged, stage it "
        "with `git add`. If the files changed after the green, re-run "
        "`compass tdd-green` on the same test command. Then ship again."
        % (len(changed), slug, record_path,
           "\n  ".join(changed) if changed
           else "(the issue's files - the exact path could not be narrowed)")
    )


# --- living system spec derivation (ADR-026) --------------------------------
# `ship-commit` is the one step that lands an issue and re-derives the living
# spec: only once an issue is actually marked landed, in a commit of its own,
# so the land commit itself stays bisectable and revertable on its own. A
# staged multiagent run integrates each wave through `integrate.sh` without
# landing the issue (ADR-025); `ship-commit` alone marks it landed, so
# deriving here - and only here - keeps a staged run from re-deriving the
# spec once per wave, ahead of verify.


def _derive_and_commit_living_spec(cwd, slug):
    """Re-derive docs/system-spec.md after `slug` has just landed, and
    commit it alone if it changed.

    Runs the same derivation as `compass _derive-system-spec --internal`
    (ADR-008). A derivation failure is reported in the returned note and
    does not undo the land - the land's own commit has already succeeded.
    """
    from compass_pkg.flow import derive_system_spec

    try:
        project_root = os.path.dirname(find_compass_dir())
    except CompassError:
        project_root = cwd

    try:
        derive_system_spec(project_root)
    except Exception as exc:
        return f"\n  living spec NOT re-derived: {exc}"

    from compass_pkg.flow import LIVING_SPEC_FILES
    rel_specs = [os.path.relpath(os.path.join(project_root, *rel.split("/")), cwd)
                 for rel in LIVING_SPEC_FILES]
    changed = _git(["status", "--porcelain", "--", *rel_specs], cwd).stdout.strip()
    if not changed:
        return "\n  living spec re-derived (no change)."

    # `-- rel_specs` scopes the commit to the spec and its archive alone. A
    # plain `git commit` commits everything staged - so anything else staged
    # at this moment (a hook's own side effect, or a leftover from elsewhere
    # in the same tree) would otherwise land in this commit too.
    _git(["--literal-pathspecs", "add", "--", *rel_specs], cwd)
    commit = _git(
        ["commit", "-m", f"Re-derive the living spec after {slug} landed",
         "--", *rel_specs], cwd
    )
    if commit.returncode != 0:
        log = ((commit.stdout or "") + (commit.stderr or ""))[-800:]
        return f"\n  living spec derived but its commit failed:\n{log}"
    return "\n  living spec re-derived and committed."


def cmd_land_commit(args):
    import shutil
    cwd = os.getcwd()
    msg = args.message
    # A long message comes from a file, so it never needs a shell fallback
    # around this verb, which would lose the HEAD check below (#120).
    if getattr(args, "message_file", None):
        try:
            with open(args.message_file, encoding="utf-8") as fh:
                msg = fh.read()
        except OSError as exc:
            raise CompassError(f"compass ship-commit: cannot read the message "
                               f"file {args.message_file}: {exc.strerror}")
        if not msg.strip():
            raise CompassError(f"compass ship-commit: the message file "
                               f"{args.message_file} is empty.")
    files = getattr(args, "files", None) or []

    # Confirm we are in a git work tree.
    inside = _git(["rev-parse", "--is-inside-work-tree"], cwd)
    if inside.returncode != 0:
        raise CompassError("compass ship-commit: not inside a git repository.")

    # Stage any explicitly named paths.
    # A name is a name, not a pattern: `x[1].txt` must not stage `x1.txt`.
    for f in files:
        _git(["--literal-pathspecs", "add", "--", f], cwd)

    # Nothing staged. A multiagent issue reaches ship time with every file it
    # changed already committed by the integration merges - by DPR-7's last
    # line, that is not an error: land it at HEAD, with no new commit, once
    # its gates have passed and its declared files are genuinely there,
    # clean. Every other case refuses as before, naming which condition
    # failed.
    if _git(["diff", "--cached", "--quiet"], cwd).returncode == 0:
        if not getattr(args, "task", None):
            raise CompassError(
                "compass ship-commit: nothing staged to land, and no issue "
                "was named. Stage the artifacts first (e.g. `git add "
                "<paths>`), then re-run - or pass --issue <slug> if that "
                "issue's work is already committed."
            )
        try:
            head_task_dir = resolve_issue_dir(args.task)
            head_task_path = manifest_path(head_task_dir)
            head_task = normalize_spine(load_yaml(head_task_path))
        except CompassError as exc:
            raise CompassError(
                f"compass ship-commit: nothing staged to land, and issue "
                f"'{args.task}' could not be resolved ({exc})."
            )
        head_slug = os.path.basename(str(head_task_dir).rstrip("/"))
        unmet = [g.get("id", "?") for g in (head_task.get("gates") or [])
                 if isinstance(g, dict) and g.get("status") != "pass"]
        if unmet:
            raise CompassError(
                f"compass ship-commit: nothing staged to land, and "
                f"{len(unmet)} gate(s) on '{head_slug}' have not passed "
                f"({', '.join(unmet)})."
            )
        declared = [cf.get("path") for cf in (head_task.get("changed_files") or [])
                    if isinstance(cf, dict) and cf.get("path")]
        dirty_or_missing = []
        for path in declared:
            status = _git(["status", "--porcelain", "--", path], cwd).stdout.strip()
            if status:
                dirty_or_missing.append(path)
                continue
            in_head = _git(["cat-file", "-e", f"HEAD:{path}"], cwd).returncode == 0
            if not in_head:
                # Clean, absent from HEAD and absent from disk: a deletion
                # that is already committed. A path that was never
                # committed fails the same test, but git reports it only
                # when it exists on disk, so it is told apart by history.
                if not os.path.lexists(os.path.join(cwd, path)) and _git(
                        ["log", "-1", "--format=%H", "--", path],
                        cwd).stdout.strip():
                    continue
                dirty_or_missing.append(path)
        if dirty_or_missing:
            raise CompassError(
                f"compass ship-commit: nothing staged to land, and "
                f"{len(dirty_or_missing)} of '{head_slug}'s changed file(s) "
                "are uncommitted or missing from HEAD:\n  "
                + "\n  ".join(dirty_or_missing)
            )

        # Judged even when the issue is already landed: landing it again
        # here moves `land_commit` to HEAD, after a review fix, and HEAD's
        # files must be the ones its newest green tested.
        _refuse_stale_green(head_task, head_task_dir, head_slug, cwd,
                            at_commit="HEAD", judge_landed=True)
        _refuse_stale_artifacts(head_task, head_task_dir)
        _refuse_unapproved_artifacts(head_task, head_task_dir)

        # What HEAD itself added must be the issue's: a commit a git hook
        # widened, refused once, must not land when shipped again. Compared
        # with the first parent, so a multiagent merge lists what it merged.
        if _git(["rev-parse", "--verify", "-q", "HEAD^1"], cwd).returncode == 0:
            added = [n for n in _git(
                ["diff", "--name-only", "-z", "HEAD^1", "HEAD"],
                cwd).stdout.split("\0") if n]
            head_owned, head_artifacts = _land_scope(head_task, head_slug)
            stray_head = (_out_of_scope(
                added, head_owned, head_artifacts,
                _docs_prefix(head_task, head_slug)) if head_owned else [])
            if stray_head:
                head_short = _git(["rev-parse", "--short", "HEAD"],
                                  cwd).stdout.strip()
                raise CompassError(
                    f"compass ship-commit: refusing to land at HEAD - commit "
                    f"{head_short} holds {len(stray_head)} path(s) outside "
                    f"issue '{head_slug}'s declared scope:\n  "
                    + "\n  ".join(stray_head[:20])
                    + "\n\nIf they belong to this issue, trace them with "
                    "`compass changed-file add <path> --scenario <id>`. If "
                    f"{head_short} is not this issue's commit, land the issue "
                    "from a branch whose tip is its own commit, then ship "
                    "again.")

        head_id = _git(["rev-parse", "HEAD"], cwd).stdout.strip()
        _apply_ship_exit(head_task, head_task_dir)
        status_words.close(head_task, status_words.COMPLETED)
        head_task["land_timestamp"] = now_iso()
        head_task["land_commit"] = head_id
        save_manifest(head_task, head_task_path)
        landed_note = _derive_and_commit_living_spec(cwd, head_slug)
        print(
            f"compass ship-commit: every file '{head_slug}' changed is "
            f"already committed - landed at HEAD {head_id[:8]}, no new "
            "commit made." + landed_note
        )
        return 0

    # The issue's declared scope. Everything below re-stages against this
    # rather than against the whole tree: a ship commit must contain what the
    # issue says it changed, and nothing else. A whole-tree re-stage after a
    # repo-wide formatter would sweep unrelated files, including another
    # agent's uncommitted work, into the commit.
    # Best-effort: `ship-commit` has always worked in a repo with no issue
    # directory at all, and must keep doing so. Without an issue there is no
    # declared scope to check against - the re-stage below stays scoped either
    # way.
    owned, artifact_dir, slug = set(), "\0none", None
    docs_prefix = None
    try:
        _scope_dir = resolve_issue_dir(getattr(args, "task", None))
        _scope_task, _ = load_manifest(_scope_dir)
        slug = os.path.basename(str(_scope_dir).rstrip("/"))
        owned, artifact_dir = _land_scope(_scope_task, slug)
        docs_prefix = _docs_prefix(_scope_task, slug)
    except (CompassError, OSError, KeyError):
        pass

    def _judge_index():
        """Judge what is staged at this moment, which is what the next
        commit holds. Called right before each commit: the pre-commit step
        and the retry re-stage from disk, so a check made earlier would
        have judged a copy that is no longer the one committed."""
        if slug is None:
            return
        tree = _git(["write-tree"], cwd)
        if tree.returncode != 0 or not tree.stdout.strip():
            raise CompassError(
                "compass ship-commit: git could not write the staged tree, so "
                "the staged files cannot be checked against the green - "
                "nothing was committed.\n" + (tree.stderr or "").strip())
        _refuse_stale_green(_scope_task, _scope_dir, slug, cwd,
                            at_commit=tree.stdout.strip())
        _refuse_stale_artifacts(_scope_task, _scope_dir)
        _refuse_unapproved_artifacts(_scope_task, _scope_dir)
        # A pre-commit step can stage files too: check the scope again on
        # what is staged now.
        now = [n for n in _git(["diff", "--cached", "--name-only", "-z"],
                               cwd).stdout.split("\0") if n]
        stray_now = (_out_of_scope(now, owned, artifact_dir, docs_prefix)
                     if owned else [])
        if stray_now:
            raise CompassError(
                "compass ship-commit: refusing to commit - a hook staged "
                f"{len(stray_now)} path(s) outside issue '{slug}'s declared "
                "scope:\n  " + "\n  ".join(stray_now[:20])
                + "\n\nUnstage them (`git restore --staged <path>`), or, if "
                "they belong to this issue, trace them with `compass "
                "changed-file add <path> --scenario <id>`. Then ship again.")

    staged_now = [n for n in _git(["diff", "--cached", "--name-only", "-z"],
                                  cwd).stdout.split("\0") if n]

    # The scope check needs a declared scope. An issue with no `changed_files`
    # has not said what it owns, so there is nothing to check against and
    # refusing would break every issue that does not record them (ADR-006:
    # a new mechanism no-ops for projects that have not adopted it). The
    # re-stage below is still scoped in that case - it re-stages what was
    # staged, never the whole tree.
    stray = (_out_of_scope(staged_now, owned, artifact_dir, docs_prefix)
             if owned else [])
    if stray:
        raise CompassError(
            "compass ship-commit: refusing to commit - "
            f"{len(stray)} staged path(s) are outside issue '{slug}'s declared "
            "scope:\n  " + "\n  ".join(stray[:20])
            + ("\n  ... and %d more" % (len(stray) - 20) if len(stray) > 20 else "")
            + "\n\nA ship commit contains the issue's `changed_files`, the "
            "tests its scenarios declare, its artifact directory "
            f"({artifact_dir}) and its documents folder. If these paths belong to "
            "this issue, record them first:\n"
            "  compass changed-file add <path> --scenario TRC-<id>\n"
            "Otherwise unstage them (`git restore --staged <path>`) - they may "
            "belong to another issue or another agent working in this tree."
        )

    head_before = _git(["rev-parse", "HEAD"], cwd).stdout.strip()

    def _disk_hashes():
        """The disk content, as git would store it, of each staged path and
        each path named on the command line that is a regular file."""
        out = {}
        for path in sorted(set(staged_now) | set(files)):
            if os.path.isfile(os.path.join(cwd, path)):
                h = _git(["--literal-pathspecs", "hash-object", "--", path], cwd)
                out[path] = h.stdout.strip() if h.returncode == 0 else None
        return out

    def _restage_owned(since):
        """Re-stage this issue's paths after a hook rewrote them.

        Only a path whose disk content changed since `since` - the hashes
        taken before the hooks ran - is re-staged. Adding every staged path
        would put an unrelated disk edit over the tested copy the user
        staged.

        Never `git add -A`. The set is what was already staged for this land,
        plus the issue's artifact directory - so a hook that reformats fifty
        unrelated files cannot smuggle them into the commit, and neither can
        another agent working in the same tree.

        It deliberately does NOT re-add the issue's whole `changed_files:`
        list. That list names every file the issue will touch, including files
        belonging to commits not yet made - so on an issue landed as a
        sequence of commits, re-adding it would widen the current commit to
        the issue's whole declared scope. That can put a module's
        registration in a commit without the module: a commit that cannot
        be bisected or reverted, and that passes CI because CI builds only
        the branch tip.

        Recovering from a hook rewrite only needs what was already staged.
        """
        now = _disk_hashes()
        for path in sorted(now):
            if now[path] != since.get(path):
                _git(["--literal-pathspecs", "add", "--", path], cwd)
        if os.path.isdir(os.path.join(cwd, artifact_dir)):
            _git(["--literal-pathspecs", "add", "--", artifact_dir], cwd)

    before_hooks = _disk_hashes()

    # (a) best-effort clean-first: only if the pre-commit framework is set up.
    if shutil.which("pre-commit") and os.path.isfile(
            os.path.join(cwd, ".pre-commit-config.yaml")):
        names = [n for n in _git(["diff", "--cached", "--name-only", "-z"],
                                 cwd).stdout.split("\0") if n]
        if names:
            # A name starting with `-` would read as an option.
            names = ["./" + n if n.startswith("-") else n for n in names]
            subprocess.run(["pre-commit", "run", "--files", *names],
                           cwd=cwd, capture_output=True, text=True)
            _restage_owned(before_hooks)  # what the hooks rewrote, scoped

    # First try at the commit.
    _judge_index()
    before_commit = _disk_hashes()
    c1 = _git(["commit", "-m", msg], cwd)
    head_after = _git(["rev-parse", "HEAD"], cwd).stdout.strip()

    retried = False
    if head_after == head_before:
        # (b) the commit no-op'd - a hook likely auto-fixed and aborted. Stage
        # whatever it rewrote and retry exactly once, within the issue's scope.
        _restage_owned(before_commit)
        retried = True
        if _git(["diff", "--cached", "--quiet"], cwd).returncode != 0:
            _judge_index()
            _git(["commit", "-m", msg], cwd)
            head_after = _git(["rev-parse", "HEAD"], cwd).stdout.strip()

    # (c) ALWAYS check that HEAD advanced - the land's evidence is the moved HEAD.
    if head_after == head_before:
        log = ((c1.stdout or "") + (c1.stderr or ""))[-800:]
        raise CompassError(
            "compass ship-commit: HEAD did not advance"
            + (" after a retry" if retried else "")
            + " - the land did NOT happen. A pre-commit hook may be aborting "
            "the commit repeatedly; resolve it and re-run.\n"
            "--- commit output (tail) ---\n" + log
        )

    # Success. Mark the issue landed only now that HEAD is confirmed advanced -
    # AND only if its gates actually cleared.
    #
    # The tested-before-ship guardrail (`G1`) is checked at the verify stage
    # and at ship. `compass retro`, the living-spec
    # derivation and every cross-issue report read the status, so an issue
    # whose gates failed must not be recorded as landed.
    landed_note = ""
    if getattr(args, "task", None):
        try:
            task_dir = resolve_issue_dir(args.task)
            task_path = manifest_path(task_dir)
            if os.path.isfile(task_path):
                task = normalize_spine(load_yaml(task_path))
                if isinstance(task, dict):
                    unmet = [g.get("id", "?") for g in (task.get("gates") or [])
                             if isinstance(g, dict) and g.get("status") != "pass"]
                    if unmet:
                        landed_note = (
                            "\n  NOT marked landed: %d gate(s) have not "
                            "passed (%s).\n  The commit stands - landed means "
                            "every gate passed, not only that the commit "
                            "exists. Clear the gates and "
                            "re-run, or set status by hand if this issue "
                            "genuinely lands unverified."
                            % (len(unmet), ", ".join(unmet)))
                    elif owned and (stray_after := _out_of_scope(
                            [n for n in _git(
                                ["show", "--name-only", "-z", "--format=",
                                 head_after], cwd).stdout.split("\0") if n],
                            owned, artifact_dir, docs_prefix)):
                        # A git hook can stage a file during the commit
                        # itself, after the last scope check.
                        print(
                            f"compass ship-commit: committed"
                            f"{' (after one retry)' if retried else ''}. HEAD "
                            f"{head_before[:8]} -> {head_after[:8]}\n  NOT "
                            f"marked landed: a hook put path(s) outside the "
                            f"issue's declared scope in the commit:\n    "
                            + "\n    ".join(stray_after)
                            + "\n  Move them out of this commit, then ship "
                            "again.")
                        return 2
                    elif (stale := _stale_paths(task, task_dir, cwd,
                                                head_after)):
                        # A git hook can stage a file during the commit
                        # itself, after the last check.
                        _, changed = stale
                        print(
                            f"compass ship-commit: committed"
                            f"{' (after one retry)' if retried else ''}. HEAD "
                            f"{head_before[:8]} -> {head_after[:8]}\n  NOT "
                            f"marked landed: the commit holds issue file(s) "
                            f"that differ from what the green tested - a "
                            f"hook changed them during the commit:\n    "
                            + "\n    ".join(changed or ["(not narrowed)"])
                            + "\n  Re-run `compass tdd-green` on the "
                            "committed files, then `compass ship-commit "
                            f"--issue {os.path.basename(str(task_dir))}` - "
                            "or, on a quick fix, re-run `compass quick-fix "
                            "finish`.")
                        return 2
                    else:
                        _apply_ship_exit(task, task_dir)
                        status_words.close(task, status_words.COMPLETED)
                        task["land_timestamp"] = now_iso()
                        # The commit this issue landed in. A green is checked
                        # against its tree after HEAD has moved on.
                        task["land_commit"] = head_after
                        save_manifest(task, task_path)
                        landed_note = "\n  issue marked landed."
                        # ADR-026: ship-commit is the one step that derives
                        # the living spec, and only for an issue it has just
                        # marked landed.
                        landed_note += _derive_and_commit_living_spec(
                            cwd, os.path.basename(str(task_dir).rstrip("/")))
        except CompassError:
            pass  # status update is best-effort; the commit already succeeded

    suffix = " (after one retry)" if retried else ""
    if "issue marked landed" in landed_note:
        # ADR-031: every landing updates the delivery record, when the
        # project names one. A failed sync fails ship loudly: the commit
        # stands, but a record that silently stopped syncing is the loss
        # the record exists to prevent.
        from compass_pkg.core import docs_dir
        from compass_pkg.record import linked_worktree
        from compass_pkg.record import settings as record_settings
        from compass_pkg.record import sync as record_sync
        project_root = os.path.dirname(find_compass_dir())
        try:
            if record_settings(project_root) is not None:
                # A linked worktree holds only part of the record, so ship
                # syncs just this issue's folders from it.
                only = None
                if linked_worktree(project_root):
                    issue_dir = str(task_dir).rstrip("/")
                    only = [os.path.relpath(issue_dir, project_root),
                            docs_dir(issue_dir)]
                landed_note += f"\n  {record_sync(project_root, only=only)}."
        except Exception as exc:                        # noqa: BLE001
            print(f"compass ship-commit: committed{suffix}. "
                  f"HEAD {head_before[:8]} -> {head_after[:8]}" + landed_note)
            sys.stderr.write(
                f"compass ship-commit: the commit landed and the issue is "
                f"marked landed, but the delivery record did not sync: "
                f"{exc}\nFix the cause, then run `compass record sync` from "
                f"the main checkout.\n")
            return 2
    print(f"compass ship-commit: committed{suffix}. "
          f"HEAD {head_before[:8]} -> {head_after[:8]}" + landed_note)
    return 0


# --- commands: manifest mutators + gate pass ---------------------------------
# Manifest mutators, which own the schema so nobody hand-edits the YAML.
# `compass gate pass` marks a gate passed and checks the evidence type
# against `gate_evidence_requirements` as it writes, so a mismatch is caught
# before it is recorded, not discovered later at `compass check`.


def _load_gate_requirements(task_dir=None):
    """Return (gate_evidence_requirements, known_evidence_types): from the
    configuration `task_dir`'s issue runs against when it has a generation (or
    its project has a `compass.yml`), else from guardrails.yml. Empty/empty on
    any load failure of the file."""
    if task_dir is not None:
        from compass_pkg import effective
        view = effective.view_or_legacy(task_dir)
        if view is not None:
            return view.gate_requirements()
    try:
        g = load_yaml(os.path.join(find_governance(), "guardrails.yml"))
    except CompassError:
        return {}, set()
    return (g.get("gate_evidence_requirements") or {},
            set((g.get("evidence_types") or {}).keys()))


def _stale_page(task_dir):
    """`say` detail lines: the one stale-page reminder, or none."""
    from compass_pkg.dashboard import stale_page_reminder
    line = stale_page_reminder(task_dir)
    return [line] if line else None


def cmd_gate_pass(args):
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    gates = task.get("gates") or []
    gate = next((g for g in gates
                 if isinstance(g, dict) and g.get("id") == args.gate_id), None)
    if gate is None:
        raise CompassError(
            f"compass gate pass: '{args.gate_id}' is not a gate in this issue "
            f"({[g.get('id') for g in gates]}). Has the delivery approach been evaluated?"
        )
    ev_ids = args.evidence or []
    if not ev_ids:
        raise CompassError("compass gate pass needs --evidence <id> [<id> ...]")
    registry = {e.get("id"): e for e in (task.get("evidence") or [])
                if isinstance(e, dict)}
    reqs, _known = _load_gate_requirements(task_dir)
    accepted = reqs.get(args.gate_id)
    types_seen = set()
    for eid in ev_ids:
        entry = registry.get(eid)
        if not entry:
            raise CompassError(
                f"compass gate pass: evidence id '{eid}' is not in the issue's "
                f"evidence registry ({sorted(registry)}). Record it first with "
                f"`compass evidence add` (or `compass tdd-green` for a test-run)."
            )
        types_seen.add(entry.get("type"))
    if accepted and not (types_seen & set(accepted)):
        raise CompassError(
            f"compass gate pass: {args.gate_id} accepts evidence of type "
            f"{accepted}, but the evidence you gave is {sorted(types_seen)}. A "
            f"mechanical gate cannot be cleared with the wrong kind of evidence. "
            f"Point it at evidence of an accepted type."
        )
    gate["status"] = "pass"
    gate["evidence"] = list(ev_ids)
    save_manifest(task, task_path)
    # A pass of a `verify` gate is a record of the `verify` stage: it moves the
    # documents of earlier stages and the `verify` stage's own (ADR-050).
    from compass_pkg import artifact_status
    moved = (artifact_status.record_stage(
        task_dir, artifact_status.STAGE_VERIFY, artifact_status.BY_GATE_PASS,
        include_own=True) if _gate_stage(task_dir, args.gate_id) == artifact_status.STAGE_VERIFY
        else [])
    return say(args, f"compass gate pass: {args.gate_id} -> pass "
                    f"(evidence: {', '.join(ev_ids)}).",
               detail=(_stale_page(task_dir) or []) + artifact_status.moved_line(moved) or None,
               gate=args.gate_id, status="pass", evidence=list(ev_ids), moved=moved)


def _gate_stage(task_dir, gate_id):
    """The stage the catalogue gives a gate, or None when it names none."""
    from compass_pkg import effective
    try:
        view = effective.view_or_legacy(task_dir)
    except Exception:                                   # noqa: BLE001
        view = None
    gates = (view.config.get("gates") if view is not None else None)
    if not isinstance(gates, dict):
        from compass_pkg.core import FRAMEWORK_ROOT
        try:
            doc = load_yaml(os.path.join(FRAMEWORK_ROOT, "governance", "presets", "default",
                                         "gates.yml"))
        except CompassError:
            return None
        gates = doc.get("gates") if isinstance(doc, dict) else None
    gate = (gates or {}).get(gate_id)
    return gate.get("stage") if isinstance(gate, dict) else None


# A file path with a directory and an extension, the shape the writing-style check treats
# as a reference to a file in the repository.
_TITLE_PATH = re.compile(r"(?:[\w.][\w-]*/)+[\w.-]+\.(?:md|py|yml|yaml|json|sh|feature)\b")


def _eval_ids(project_root):
    """Eval scenario and judge behaviour ids, where the project has evals."""
    ids = set()
    scen = os.path.join(project_root, "evals", "scenarios")
    if os.path.isdir(scen):
        ids |= {d for d in os.listdir(scen)
                if os.path.isfile(os.path.join(scen, d, "scenario.yml"))}
    judge = os.path.join(project_root, "evals", "judge.py")
    if os.path.isfile(judge):
        import ast
        try:
            tree = ast.parse(open(judge, encoding="utf-8").read())
        except (OSError, SyntaxError):
            tree = None
        for node in getattr(tree, "body", []):
            if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                    and any(isinstance(t, ast.Name) and t.id == "BEHAVIOURS"
                            for t in node.targets)):
                ids |= {k.value for k in node.value.keys
                        if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return ids


def slug_problem(project_root, slug):
    """Why an issue slug would break the living spec, or None. The spec
    lists every landed issue by slug and ships in the eval plugin copy,
    which must name no eval scenario or behaviour. A hyphen joins a slug's
    words, so it counts as a boundary here, unlike in a title (#382)."""
    for ident in sorted(_eval_ids(project_root)):
        if re.search(rf"(?<![A-Za-z0-9_]){re.escape(ident)}(?![A-Za-z0-9_])",
                     slug or ""):
            return (f"it names the eval scenario or behaviour {ident}; the living "
                    f"spec lists every landed issue by slug and ships in the eval "
                    f"plugin copy, which must name none. Pick a slug that "
                    f"describes the change instead.")
    return None


def title_problem(project_root, title):
    """Why a scenario title would break a check on docs/system-spec.md, or
    None. ship-commit copies titles into that file after the suite has run,
    so a title is checked here, when it is recorded (#283)."""
    for m in _TITLE_PATH.finditer(title or ""):
        if not os.path.exists(os.path.join(project_root, m.group(0))):
            return (f"it names the path {m.group(0)}, which does not exist; the living "
                    f"spec's check refuses a named file that is missing. Describe it "
                    f"instead.")
    for ident in sorted(_eval_ids(project_root)):
        if re.search(rf"(?<![\w-]){re.escape(ident)}(?![\w-])", title or ""):
            return (f"it names the eval scenario or behaviour {ident}; the living spec "
                    f"ships in the eval plugin copy, which must name none. Describe the "
                    f"run instead.")
    from compass_pkg import public_copy
    if public_copy.first_match(title, public_copy.USER_TIMING_PATTERNS):
        return ("it attaches a duration to a user's experience, which the living "
                "spec, as public copy, must not claim unmeasured. State the bound "
                "the test sets instead.")
    if public_copy.first_match(title, public_copy.OUTSIDE_USER_PATTERNS):
        return ("it claims an outside user's experience, which the living spec, "
                "as public copy, must not claim. Describe the behaviour instead.")
    return None


def cmd_scenario_add(args):
    task_dir = resolve_issue_dir(args.task)
    problem = title_problem(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.normpath(task_dir)))), args.title or "")
    if problem:
        raise CompassError(f"compass scenario add: title refused: {problem}")
    task, task_path = load_manifest(task_dir)
    scns = task.setdefault("scenarios", [])
    if any(isinstance(s, dict) and s.get("id") == args.scenario_id for s in scns):
        raise CompassError(
            f"compass scenario add: scenario '{args.scenario_id}' already "
            f"exists. Edit it directly if a change was intended."
        )
    scns.append({
        "id": args.scenario_id,
        "title": args.title or args.scenario_id,
        "intent": args.intent,
        "tests": list(args.test or []),
    })
    save_manifest(task, task_path)
    return say(args, f"compass scenario add: {args.scenario_id} added.",
               scenario=args.scenario_id, intent=getattr(args, "intent", None),
               tests=list(args.test or []))


def _test_refusal(test_id, project_root):
    """Why `declared-tests-resolve` would fail this test id, or None."""
    resolves = _test_id_resolves(test_id, project_root)
    if resolves is False:
        return "does not resolve to a test on disk"
    if resolves and _test_is_skipped(test_id, project_root):
        return "resolves but is marked skipped, so it never runs"
    return None


def cmd_scenario_tests(args):
    """Replace the tests a scenario declares. It takes only ids that
    `declared-tests-resolve` accepts, so a wrong id is corrected here
    instead of by a hand edit of manifest.yml."""
    given = [t.strip() for t in (args.test or []) if t and t.strip()]
    if not given:
        raise CompassError("compass scenario tests set: give the scenario's tests with "
                           "--test <path::name> (repeatable).")
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    scn = next((s for s in (task.get("scenarios") or [])
                if isinstance(s, dict) and s.get("id") == args.scenario_id), None)
    if scn is None:
        known = sorted(s.get("id") for s in (task.get("scenarios") or [])
                       if isinstance(s, dict) and s.get("id"))
        raise CompassError(
            f"compass scenario tests set: '{args.scenario_id}' is not a scenario in this "
            f"issue's manifest.yml: its scenarios are {known}. Add it first with "
            f"`compass scenario add`.")
    project_root = os.path.dirname(find_compass_dir())
    refused = [f"{t} {why}" for t in given
               for why in [_test_refusal(t, project_root)] if why]
    if refused:
        raise CompassError(
            "compass scenario tests set: " + "; ".join(refused) + ". Name a test that "
            "exists, as `compass check` reads it (`path/to/test_file.py::test_name`).")
    previous = list(scn.get("tests") or [])
    scn["tests"] = given
    save_manifest(task, task_path)
    reason = " ".join(str(args.reason or "").split())
    devlog_path = os.path.join(task_dir, "devlog.md")
    if os.path.isfile(devlog_path):
        with open(devlog_path, "a", encoding="utf-8") as fh:
            fh.write(f"- {datetime.date.today().isoformat()}: scenario "
                     f"{args.scenario_id} tests changed from "
                     f"[{', '.join(previous) or 'none'}] to [{', '.join(given)}]"
                     f" (reason: {reason or 'none given'})\n")
    # A green is bound to the files the declared tests live in, so a test file
    # the last green did not cover leaves it stale: ship-commit refuses it.
    old_files = {t.split("::", 1)[0] for t in previous}
    new_files = sorted({t.split("::", 1)[0] for t in given} - old_files)
    detail = ([f"next : {', '.join(new_files)} is new to this scenario, so re-run "
               f"`compass tdd-green` before `compass ship-commit`, which refuses a "
               f"green recorded before it."] if new_files else None)
    noun = "test" if len(given) == 1 else "tests"
    return say(args, f"compass scenario tests set: {args.scenario_id} now declares "
                     f"{len(given)} {noun}.", detail=detail,
               scenario=args.scenario_id, issue=os.path.basename(task_dir),
               tests=given, previous=previous, reason=reason or None)


def cmd_scenario_descope(args):
    """Record a failure mode the brief implies that no scenario covers, with
    the reason it is left out, so the verifier lists it (failure-modes-in-define)."""
    mode = " ".join(str(args.mode or "").split())
    reason = " ".join(str(args.reason or "").split())
    if not mode or not reason:
        raise CompassError("compass scenario descope: give the failure mode and, with "
                           "--reason, why no scenario covers it.")
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    modes = task.get("failure_modes_descoped")
    if not isinstance(modes, list):
        modes = task["failure_modes_descoped"] = []
    if any(isinstance(m, dict) and str(m.get("mode", "")).casefold() == mode.casefold()
           for m in modes):
        raise CompassError(f"compass scenario descope: '{mode}' is already recorded.")
    modes.append({"mode": mode, "reason": reason,
                  "recorded": datetime.date.today().isoformat()})
    save_manifest(task, task_path)
    return say(args, f"compass scenario descope: '{mode}' recorded as de-scoped. "
                     f"Verify lists it in the verification report.", mode=mode)


def _check_scenario_ids(task, ids, verb):
    """Refuse a scenario id the issue does not define, as `compass tdd-red`
    does. A trace stored an unknown id, or six ids quoted as one string,
    and only a later `compass check` reported it (#119)."""
    known = {s.get("id") for s in (task.get("scenarios") or [])
             if isinstance(s, dict)}
    listed = (f"its scenarios are {sorted(known)}" if known
              else "it has no scenarios yet")
    for sid in ids:
        if len(str(sid).split()) > 1:
            raise CompassError(
                f"compass {verb}: --scenario '{sid}' holds several ids in one "
                f"value; give --scenario once for each id.")
        if sid not in known:
            raise CompassError(
                f"compass {verb}: --scenario '{sid}' is not a scenario in this "
                f"issue's manifest.yml: {listed}. Add it first with `compass "
                f"scenario add`, or trace to one that exists.")


def cmd_changed_file_add(args):
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    cfs = task.setdefault("changed_files", [])
    existing = next((c for c in cfs
                     if isinstance(c, dict) and c.get("path") == args.path), None)
    # `--scenario` may be repeated: a file often serves several scenarios, and
    # every one given is recorded, merged with those already traced.
    given = args.scenario if isinstance(args.scenario, list) else [args.scenario]
    _check_scenario_ids(task, given, "changed-file add")
    if existing:
        existing["scenarios"] = sorted(set(existing.get("scenarios") or []) | set(given))
    else:
        cfs.append({"path": args.path, "scenarios": sorted(set(given))})
    save_manifest(task, task_path)
    return say(args, f"compass changed-file add: {args.path} -> {', '.join(given)}.",
               detail=_stale_page(task_dir),
               path=args.path, scenario=given[-1], scenarios=given)


def cmd_evidence_add(args):
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    if getattr(args, "scenario", None):
        _check_scenario_ids(task, [args.scenario], "evidence add")
    _reqs, known = _load_gate_requirements(task_dir)
    if known and args.type not in known:
        raise CompassError(
            f"compass evidence add: '{args.type}' is not a known evidence type "
            f"({sorted(known)})."
        )
    reg = task.setdefault("evidence", [])
    if any(isinstance(e, dict) and e.get("id") == args.evidence_id for e in reg):
        raise CompassError(
            f"compass evidence add: evidence id '{args.evidence_id}' already "
            f"exists. Use a fresh id."
        )
    # Check the file against its declared type here, not at `compass check`,
    # where the failure arrives out of context. Only types with a real shape
    # contract are checked; a manual review or an artifact can be any file.
    abs_path = args.path if os.path.isabs(args.path) else os.path.join(
        task_dir, args.path)
    if not os.path.exists(abs_path):
        raise CompassError(
            f"compass evidence add: no file at '{args.path}' (looked in "
            f"{task_dir}). Evidence is a record on disk - register it after the "
            f"file exists, or fix the path.")
    if args.type == "test-run":
        try:
            with open(abs_path, encoding="utf-8") as fh:
                json.load(fh)
        except (ValueError, OSError):
            raise CompassError(
                f"compass evidence add: '{args.path}' is not a run record. "
                f"`test-run` means the JSON that `compass tdd-green` writes "
                f"(command, exit_code, passed), because the tested-before-ship "
                f"checks read "
                f"those fields.\n"
                f"  For a raw log, use --type command-output.\n"
                f"  For a real run, record it with `compass tdd-green -- <cmd>` "
                f"and it registers itself.")

    entry = {"id": args.evidence_id, "type": args.type, "path": args.path}
    if getattr(args, "scenario", None):
        entry["scenario"] = args.scenario
    reg.append(entry)
    save_manifest(task, task_path)
    return say(args, f"compass evidence add: {args.evidence_id} "
                    f"({args.type}) added.",
               detail=_stale_page(task_dir),
               evidence_id=args.evidence_id, type=args.type, path=args.path)


def annotate_gate_accepts_text(text, requirements=None):
    """`text` (a manifest) with each gate in the gates block annotated with a
    `# accepts: [...]` comment naming its accepted evidence types: those of
    `requirements` when given (the configuration being committed), else from
    guardrails.yml. A seeding nicety - yaml round-trips drop it, so
    `approach evaluate --write` applies it to the text it is about to write."""
    reqs = requirements if requirements is not None else _load_gate_requirements()[0]
    if not reqs:
        return text
    lines = text.splitlines()
    out, in_gates = [], False
    for line in lines:
        if _re.match(r"^gates:\s*$", line):
            in_gates = True
            out.append(line)
            continue
        if in_gates and _re.match(r"^[A-Za-z_]", line):
            in_gates = False     # a new top-level key ends the gates block
        if in_gates:
            m = _re.match(r"^(\s*)-\s+id:\s*([^\s#]+)", line)
            if m:
                indent, gid = m.group(1), m.group(2)
                acc = reqs.get(gid)
                if acc:
                    out.append(f"{indent}# accepts: {acc}")
        out.append(line)
    return "\n".join(out) + "\n"



# The status setter, `compass issue status remove` and `compass issue blocked`
# are in cli/compass_pkg/status_cmd.py.
