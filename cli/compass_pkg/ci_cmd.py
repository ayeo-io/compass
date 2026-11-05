# compass_pkg.ci_cmd - `compass ci`, the full mechanical gate suite
"""`compass ci`: policy lint, then issue lint and check for every issue.

It moved out of `analyze.py` when 9.0.0 removed `compass analyze` (ADR-091).
"""
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/, through core.load_yaml.
from __future__ import annotations

import datetime
import os
import subprocess

from compass_pkg import status_words
from compass_pkg.check_cmd import cmd_check
from compass_pkg.core import (COMPASS_SCHEMA_VERSION, COMPASS_VERSION, CompassError, exit_for_mode,
                              find_compass_dir, load_mode, load_yaml, manifest_path, mode_banner,
                              resolve_issue_dir)
from compass_pkg.governance import cmd_policy_lint
from compass_pkg.policy import cmd_task_lint

__all__ = ["cmd_ci"]


# --- command: ci ------------------------------------------------------------
# The full mechanical gate suite, for CI / pre-merge. It is a convenience: it
# just runs the checks that already exist - `policy lint`, then `issue lint`
# and `check` for every issue under .compass/work/ - and aggregates the exit
# codes. CI integration is genuinely this small: run `compass ci`, honour the
# exit code. See ci/README.md.

def _issue_manifest(slug):
    """The issue's manifest, or {} if it cannot be read.

    An unreadable manifest is not treated as not started: it falls through to
    the checks, which report the problem properly rather than skipping it.
    """
    try:
        manifest = load_yaml(os.path.join(resolve_issue_dir(slug), "manifest.yml"))
    except Exception:
        return {}
    return manifest if isinstance(manifest, dict) else {}


def _gate_checks_wait(manifest):
    """True for an issue held back or closed without being delivered. It has
    no acceptance criteria yet, or never will, so the gate checks have
    nothing to read."""
    return bool(status_words.is_held(manifest)
                or (status_words.close_reason(manifest)
                    and not status_words.is_completed(manifest)))


def _git_out(cwd, *args):
    """The output of a git command, or None when it fails."""
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _landed_before(slug, cwd, ref, ref_time):
    """True only when the issue's landing is known to be before `ref`.

    `land_commit` is placed by git ancestry. An issue without it, such as
    one landed before `ship-commit` wrote the field, is placed by
    `land_timestamp` against the ref's commit time. Anything that cannot be
    placed counts as after, so it is checked:
    checking too much costs time, and checking too little hides a failure.
    """
    try:
        manifest = load_yaml(os.path.join(resolve_issue_dir(slug), "manifest.yml"))
    except Exception:
        return False
    if not isinstance(manifest, dict):
        return False
    commit = manifest.get("land_commit")
    if isinstance(commit, str) and commit:
        r = subprocess.run(["git", "merge-base", "--is-ancestor", commit, ref],
                           cwd=cwd, capture_output=True, text=True)
        return r.returncode == 0
    stamp = manifest.get("land_timestamp")
    try:
        landed = datetime.datetime.fromisoformat(str(stamp))
        return landed < ref_time
    except (TypeError, ValueError):
        return False


def cmd_ci(args):
    import types
    mode = load_mode()
    print(f"compass ci - the full mechanical gate suite "
          f"(compass {COMPASS_VERSION}, schema {COMPASS_SCHEMA_VERSION})")
    print(f"{mode_banner(mode)}\n")
    failures = 0
    checked = 0
    skipped = 0

    since = getattr(args, "since", None)
    project = os.getcwd()
    ref_time = None
    if since:
        # A ref git cannot resolve must stop the run: carrying on would
        # check less than the caller asked for and still report a pass.
        try:
            project = os.path.dirname(find_compass_dir())
        except CompassError:
            pass
        commit = _git_out(project, "rev-parse", "--verify", "--quiet", f"{since}^{{commit}}")
        stamp = commit and _git_out(project, "log", "-1", "--format=%cI", commit)
        if not stamp:
            print(f"compass ci: --since {since} does not name a commit in this "
                  f"repository, so nothing was checked.")
            return 2
        ref_time = datetime.datetime.fromisoformat(stamp)
        print(f"Issues landed before {since} are linted only.\n")

    print("[1] governance policy")
    if cmd_policy_lint(types.SimpleNamespace()):
        failures += 1

    # The decisions ledger's history check needs a base ref to compare with
    # (ADR-027). Without --since it says so, rather than passing silently.
    from compass_pkg.decisions import LEDGER, history_problems
    ledger_root = project
    try:
        ledger_root = os.path.dirname(find_compass_dir())
    except CompassError:
        pass
    if os.path.isdir(os.path.join(ledger_root, LEDGER)):
        if since:
            problems = history_problems(ledger_root, commit)
            if problems:
                failures += 1
                print("\n[ledger] FAIL - an entry never changes:")
                for p in problems:
                    print(f"  {p}")
            else:
                print(f"\n[ledger] PASS - every entry at {since} is unchanged.")
        else:
            print("\n[ledger] history check skipped - pass --since <ref> to "
                  "compare governance/decisions/ with a base ref.")

    slugs = []
    try:
        work = os.path.join(find_compass_dir(), "work")
        if os.path.isdir(work):
            slugs = sorted(d for d in os.listdir(work)
                           if os.path.isfile(manifest_path(os.path.join(work, d))))
    except CompassError:
        pass

    if not slugs:
        print("\n  no issues under .compass/work/ - governance policy only.")
    for slug in slugs:
        print(f"\n[issue] {slug}")
        # The lint runs for every issue, whatever its stage. It checks the
        # manifest's own structure - schema version, required keys, vocabulary -
        # and a malformed manifest is malformed whether or not the work has
        # started. Skipping it would let a manifest the linter rejects pass
        # while the sweep reports clean. A generation built by another resolver
        # or schema major refuses that issue only, and the sweep goes on.
        from compass_pkg.effective import MajorRefusal
        try:
            if cmd_task_lint(types.SimpleNamespace(task=slug, file=None)):
                failures += 1
        except MajorRefusal as exc:
            print(f"  refused - {exc}")
            failures += 1
            skipped += 1
            continue

        # The generation the manifest names is the issue's configuration. A
        # broken one fails the sweep and its gate checks are not run, because
        # `compass check` refuses it; a leftover folder is only reported.
        from compass_pkg import effective
        gen_lines, gen_broken = effective.generation_report(resolve_issue_dir(slug))
        for gen_line in gen_lines:
            print(gen_line)
        if gen_broken:
            print("  gate checks skipped - the stored configuration is broken. "
                  "The manifest itself was still linted.")
            failures += 1
            skipped += 1
            continue

        # The gate checks are different. An issue that has not started has no
        # acceptance criteria and no evidence, correctly so - the framework
        # asks for work to be assessed early, and failing the sweep for
        # complying teaches people to stop. Skip those, name the issue, and
        # say why: an issue that vanished from the output would be worse than
        # one that failed, because nobody would know it was there.
        manifest = _issue_manifest(slug)
        if _gate_checks_wait(manifest):
            print(f"  gate checks skipped - status is '{status_words.stored(manifest)}', so the "
                  f"acceptance criteria and evidence a check looks for do "
                  f"not exist yet. The manifest itself was still linted.")
            skipped += 1
            continue
        # The resolved commit id, not the caller's string, reaches git.
        if since and status_words.is_completed(manifest) and _landed_before(slug, project, commit, ref_time):
            print(f"  gate checks skipped - landed before {since}. Run "
                  f"compass ci without --since to check it. The manifest "
                  f"itself was still linted.")
            skipped += 1
            continue
        print()
        # cmd_check applies the output mode itself. Call it and keep its exit
        # code, so ci can report which groups failed.
        checked += 1
        # Forward the caller's output mode, so `compass ci --verbose` gives
        # verbose check output. A CI log is the one place a reader cannot
        # re-run a command.
        # An issue whose configuration cannot be read (generation 0, say) is a
        # failure of that issue, reported, and the sweep goes on to the next.
        try:
            check_args = types.SimpleNamespace(
                task=slug, _mode=getattr(args, "_mode", None),
                evidence_out=getattr(args, "evidence_out", None),
                no_count=True)
            check_exit = cmd_check(check_args)
            # Advisory mode makes the exit code 0 whatever failed, so the
            # summary counts the failures cmd_check recorded instead.
            check_failed = check_exit or getattr(check_args, "failed_checks", 0)
        # A closed issue passes the lint above across a major, but `check` still refuses
        # it, so the refusal is reported here as that issue's failure.
        except (CompassError, MajorRefusal) as exc:
            print(f"  gate checks refused - {exc}")
            check_failed = 1
        if check_failed:
            failures += 1

    print("\n" + "=" * 60)
    if failures:
        print(f"compass ci: FAIL - {failures} check group(s) failed.")
    else:
        # The summary must say what ran and what was skipped: a CI reader
        # reads the summary line, not the skip lines above it.
        counted = f"{checked} issue(s) fully checked"
        if skipped:
            why = f"not in flight, or landed before {since}" if since else "not in flight"
            counted += f", {skipped} lint-only ({why})"
        print(f"compass ci: PASS - governance valid; every manifest lints clean; "
              f"{counted}.")
    return exit_for_mode(failures, mode)
