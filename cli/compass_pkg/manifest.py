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

    An issue's own `changed_files`, its artifact directory, and the framework's
    own bookkeeping files above. Anything else in the commit belongs to someone
    else - a concurrent agent's edits, untracked scratch, or the unrelated
    files a repo-wide formatter just rewrote.
    """
    owned = {
        cf["path"] for cf in (task.get("changed_files") or [])
        if isinstance(cf, dict) and cf.get("path")
    }
    return owned, f".compass/work/{slug}/"


def _out_of_scope(staged, owned, artifact_dir):
    return sorted(
        p for p in staged
        if p not in owned
        and p not in FRAMEWORK_OWNED_PATHS
        and not p.startswith(artifact_dir)
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

    spec_path = os.path.join(project_root, "docs", "system-spec.md")
    rel_spec = os.path.relpath(spec_path, cwd)
    changed = _git(["status", "--porcelain", "--", rel_spec], cwd).stdout.strip()
    if not changed:
        return "\n  living spec re-derived (no change)."

    # `-- rel_spec` scopes the commit to the spec alone. A plain `git commit`
    # commits everything staged - so anything else staged at this moment (a
    # hook's own side effect, or a leftover from elsewhere in the same tree)
    # would otherwise land in this commit too.
    _git(["add", "--", rel_spec], cwd)
    commit = _git(
        ["commit", "-m", f"Re-derive the living spec after {slug} landed",
         "--", rel_spec], cwd
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
    for f in files:
        _git(["add", "--", f], cwd)

    # Nothing staged → explicit error, never a retry loop.
    if _git(["diff", "--cached", "--quiet"], cwd).returncode == 0:
        raise CompassError(
            "compass ship-commit: nothing staged to land. Stage the artifacts "
            "first (e.g. `git add <paths>`), then re-run."
        )

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
    try:
        _scope_dir = resolve_issue_dir(getattr(args, "task", None))
        _scope_task, _ = load_manifest(_scope_dir)
        slug = os.path.basename(str(_scope_dir).rstrip("/"))
        owned, artifact_dir = _land_scope(_scope_task, slug)
    except (CompassError, OSError, KeyError):
        pass

    staged_now = _git(["diff", "--cached", "--name-only"], cwd).stdout.split()

    # The scope check needs a declared scope. An issue with no `changed_files`
    # has not said what it owns, so there is nothing to check against and
    # refusing would break every issue that does not record them (ADR-006:
    # a new mechanism no-ops for projects that have not adopted it). The
    # re-stage below is still scoped in that case - it re-stages what was
    # staged, never the whole tree.
    stray = _out_of_scope(staged_now, owned, artifact_dir) if owned else []
    if stray:
        raise CompassError(
            "compass ship-commit: refusing to commit - "
            f"{len(stray)} staged path(s) are outside issue '{slug}'s declared "
            "scope:\n  " + "\n  ".join(stray[:20])
            + ("\n  ... and %d more" % (len(stray) - 20) if len(stray) > 20 else "")
            + "\n\nA ship commit contains the issue's `changed_files` and its "
            f"artifact directory ({artifact_dir}). If these paths belong to "
            "this issue, record them first:\n"
            "  compass changed-file add <path> --scenario TRC-<id>\n"
            "Otherwise unstage them (`git restore --staged <path>`) - they may "
            "belong to another issue or another agent working in this tree."
        )

    head_before = _git(["rev-parse", "HEAD"], cwd).stdout.strip()

    def _restage_owned():
        """Re-stage this issue's paths after a hook rewrote them.

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
        for path in sorted(set(staged_now) | set(files)):
            _git(["add", "--", path], cwd)
        if os.path.isdir(os.path.join(cwd, artifact_dir)):
            _git(["add", "--", artifact_dir], cwd)

    # (a) best-effort clean-first: only if the pre-commit framework is set up.
    if shutil.which("pre-commit") and os.path.isfile(
            os.path.join(cwd, ".pre-commit-config.yaml")):
        names = _git(["diff", "--cached", "--name-only"], cwd).stdout.split()
        if names:
            subprocess.run(["pre-commit", "run", "--files", *names],
                           cwd=cwd, capture_output=True, text=True)
            _restage_owned()  # re-stage what the hooks rewrote, scoped

    # First try at the commit.
    c1 = _git(["commit", "-m", msg], cwd)
    head_after = _git(["rev-parse", "HEAD"], cwd).stdout.strip()

    retried = False
    if head_after == head_before:
        # (b) the commit no-op'd - a hook likely auto-fixed and aborted. Stage
        # whatever it rewrote and retry exactly once, within the issue's scope.
        _restage_owned()
        retried = True
        if _git(["diff", "--cached", "--quiet"], cwd).returncode != 0:
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
                            "passed (%s).\n  The commit stands - shipping is a "
                            "record, not a rubber stamp. Clear the gates and "
                            "re-run, or set status by hand if this issue "
                            "genuinely lands unverified."
                            % (len(unmet), ", ".join(unmet)))
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
    if existing:
        scns = set(existing.get("scenarios") or [])
        scns.add(args.scenario)
        existing["scenarios"] = sorted(scns)
    else:
        cfs.append({"path": args.path, "scenarios": [args.scenario]})
    save_manifest(task, task_path)
    return say(args, f"compass changed-file add: {args.path} -> {args.scenario}.",
               path=args.path, scenario=args.scenario)


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
                f"({', '.join(unmet)}). Shipping is a record, not a rubber stamp. "
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
