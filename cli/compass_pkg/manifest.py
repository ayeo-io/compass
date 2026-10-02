#!/usr/bin/env python3
# =============================================================================
# compass_pkg.manifest - `compass ship-commit`, the manifest mutators and
# `compass issue set-status`
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
from compass_pkg.terminal import say
from compass_pkg.core import CompassError, find_compass_dir, find_governance, load_manifest, load_yaml, manifest_path, normalize_spine, now_iso, resolve_issue_dir, save_manifest
from compass_pkg.issue_layout import docs_dir_for
from compass_pkg.binding import changes_paths, declared_test_paths, _changes_id_at, _newest_bound_record



# --- command: ship-commit -----------------------------------------------------
# `compass ship-commit`, the commit step of ship. An auto-fixing pre-commit
# hook can rewrite a staged file and abort the commit, so HEAD does not move
# and nothing reports it. So ship-commit:
#   (a) does a best-effort clean-first via the pre-commit framework when present;
#   (b) detects the no-op (HEAD unchanged), re-stages the hook's fixes, and retries once;
#   (c) ALWAYS checks that HEAD advanced and errors loudly if not.


def _git(args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)


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


def _stale_paths(task, task_dir, root, at_commit):
    """The issue files that differ, in `at_commit`, from what the newest
    bound green tested, as (record path, paths), or None when there is
    nothing to judge or nothing differs.

    It reuses the comparison `compass check` uses for a landed issue
    (`binding._check_landed`). `at_commit` is a tree or commit: the index's
    tree before a commit, the new commit after it, or `HEAD` for a land
    that makes no commit.

    A landed issue is not judged: its green was judged when it landed, and
    a later edit to one of its files belongs to later work. Nothing is
    judged until every gate has passed, or when the newest record carries
    no `changes_id` - `compass check` does not judge those either.
    """
    if task.get("status") == "landed":
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


def _refuse_stale_green(task, task_dir, slug, root, at_commit):
    """Refuse `ship-commit` when `at_commit` holds issue files that differ
    from what the newest bound green tested."""
    stale = _stale_paths(task, task_dir, root, at_commit)
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
                dirty_or_missing.append(path)
        if dirty_or_missing:
            raise CompassError(
                f"compass ship-commit: nothing staged to land, and "
                f"{len(dirty_or_missing)} of '{head_slug}'s changed file(s) "
                "are uncommitted or missing from HEAD:\n  "
                + "\n  ".join(dirty_or_missing)
            )

        _refuse_stale_green(head_task, head_task_dir, head_slug, cwd,
                            at_commit="HEAD")

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
        head_task["status"] = "landed"
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
                        task["status"] = "landed"
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
    print(f"compass ship-commit: committed{suffix}. "
          f"HEAD {head_before[:8]} -> {head_after[:8]}" + landed_note)
    return 0


# --- commands: manifest mutators + gate pass ---------------------------------
# Manifest mutators, which own the schema so nobody hand-edits the YAML.
# `compass gate pass` marks a gate passed and checks the evidence type
# against `gate_evidence_requirements` as it writes, so a mismatch is caught
# before it is recorded, not discovered later at `compass check`.


def _load_gate_requirements():
    """Return (gate_evidence_requirements, known_evidence_types) from
    guardrails.yml. Empty/empty on any load failure."""
    try:
        g = load_yaml(os.path.join(find_governance(), "guardrails.yml"))
    except CompassError:
        return {}, set()
    return (g.get("gate_evidence_requirements") or {},
            set((g.get("evidence_types") or {}).keys()))


def cmd_gate_pass(args):
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    gates = task.get("gates") or []
    gate = next((g for g in gates
                 if isinstance(g, dict) and g.get("id") == args.gate_id), None)
    if gate is None:
        raise CompassError(
            f"compass gate pass: '{args.gate_id}' is not a gate in this issue "
            f"({[g.get('id') for g in gates]}). Has the route been evaluated?"
        )
    ev_ids = args.evidence or []
    if not ev_ids:
        raise CompassError("compass gate pass needs --evidence <id> [<id> ...]")
    registry = {e.get("id"): e for e in (task.get("evidence") or [])
                if isinstance(e, dict)}
    reqs, _known = _load_gate_requirements()
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
    return say(args, f"compass gate pass: {args.gate_id} -> pass "
                    f"(evidence: {', '.join(ev_ids)}).",
               gate=args.gate_id, status="pass", evidence=list(ev_ids))


def cmd_scenario_add(args):
    task_dir = resolve_issue_dir(args.task)
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


def cmd_changed_file_add(args):
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    cfs = task.setdefault("changed_files", [])
    existing = next((c for c in cfs
                     if isinstance(c, dict) and c.get("path") == args.path), None)
    # `--scenario` may be repeated: a file often serves several scenarios, and
    # every one given is recorded, merged with those already traced.
    given = args.scenario if isinstance(args.scenario, list) else [args.scenario]
    if existing:
        existing["scenarios"] = sorted(set(existing.get("scenarios") or []) | set(given))
    else:
        cfs.append({"path": args.path, "scenarios": sorted(set(given))})
    save_manifest(task, task_path)
    return say(args, f"compass changed-file add: {args.path} -> {', '.join(given)}.",
               path=args.path, scenario=given[-1], scenarios=given)


def cmd_evidence_add(args):
    task_dir = resolve_issue_dir(args.task)
    task, task_path = load_manifest(task_dir)
    _reqs, known = _load_gate_requirements()
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
               evidence_id=args.evidence_id, type=args.type, path=args.path)


def _annotate_gate_accepts(task_path):
    """Annotate each gate in the gates block with a `# accepts: [...]`
    comment naming its accepted evidence types (from guardrails.yml). A seeding
    nicety - yaml round-trips drop it, so it is re-applied after each
    `approach evaluate --write`."""
    reqs, _known = _load_gate_requirements()
    if not reqs:
        return
    try:
        with open(task_path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return
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
    with open(task_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")


# --- compass issue set-status -------------------------------------------------
# `compass issue set-status`: sets the lifecycle status, so nobody edits the
# manifest by hand.

TASK_STATUSES = ("active", "queued", "parked", "landed", "abandoned")

#: The two of those whose work is over. A finished issue's manifest records
#: what was true then, and re-validating it against a codebase that has moved
#: produces failures nobody can act on (ADR-006). The other three are issues
#: still in flight, whatever the board calls them - a check that scopes itself
#: to "not active" silently stops running on `queued` and `parked`.
TERMINAL_STATUSES = ("landed", "abandoned")


def cmd_task_set_status(args):
    status = args.status
    if status not in TASK_STATUSES:
        raise CompassError(
            f"compass issue set-status: '{status}' is not an issue status. "
            f"Permitted: {', '.join(TASK_STATUSES)}.\n"
            "  queued    - recorded as next up, not started\n"
            "  active    - in flight\n"
            "  parked    - stopped, phases so far still valid, can resume\n"
            "  landed    - shipping completed; only this grants living-spec eligibility\n"
            "  abandoned - will not resume"
        )

    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task, path = load_manifest(task_dir)

    # `ship-commit` refuses to write `landed` over gates that have not passed.
    # This command must not be an easier way to set the same field, or the
    # refusal is advice rather than a rule.
    if status == "landed":
        unmet = [g.get("id", "?") for g in (task.get("gates") or [])
                 if isinstance(g, dict) and g.get("status") != "pass"]
        if unmet:
            raise CompassError(
                f"compass issue set-status: refusing to mark '{task.get('issue')}' "
                f"landed - {len(unmet)} gate(s) have not passed "
                f"({', '.join(unmet)}). Landed means every gate passed. "
                "Clear the gates and re-run."
            )
        task["land_timestamp"] = now_iso()

    task["status"] = status
    reason = getattr(args, "reason", None)
    if status == "parked":
        if reason:
            task["parked_reason"] = reason
        task["parked_at"] = now_iso()
    elif reason:
        # `status_reason`, not `note`: the schema forbids undeclared keys,
        # and the name must say which transition it records, as
        # `parked_reason` does.
        task["status_reason"] = reason

    save_manifest(task, path)
    detail = f" ({reason})" if reason else ""
    return say(args, f"compass issue set-status: {task.get('issue')} -> "
                    f"{status}{detail}.",
               issue=task.get("issue"), status=status, reason=reason or None)
