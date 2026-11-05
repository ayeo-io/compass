#!/usr/bin/env python3
# =============================================================================
# compass_pkg.tdd - `compass tdd-red` and `compass acceptance`, and the helpers
# `compass tdd-green` (compass_pkg.tdd_green) shares with them
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
import uuid
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
from compass_pkg import project_settings
from compass_pkg.core import CompassError, find_upwards, load_manifest, manifest_path, now_iso, resolve_issue_dir, save_manifest
from compass_pkg.manifest_store import load_file as load_manifest_file
from compass_pkg import pytest_report
from compass_pkg.acceptance_strategy import LOOPS
from compass_pkg.binding import declared_test_paths, ids_for
from compass_pkg.red_first import (
    ACCEPTANCE_KINDS as _ACCEPTANCE_KINDS, content_digest as _content_digest, record_stem)



# --- commands: tdd-red / tdd-green ------------------------------------------

# Exit-code-masking integrity for piped test commands.
# A command wrapped in `bash -c '... | tail'` returns the LAST pipeline stage's
# exit code (tail = 0), masking an inner test failure as a false green. Three
# layered signals defend against it:
#   1. inject `set -o pipefail` into bash/zsh wrappers so a mid-pipeline
#      failure propagates;
#   2. warn when the wrapped script is a top-level pipe ending in a
#      pager/filter;
#   3. cross-check output for a known-runner fail-token even on a zero exit.
_PIPE_FILTER_CMDS = {"tail", "head", "grep", "cat", "less", "more", "tee", "sort",
                     "uniq", "wc", "awk", "sed"}
_PIPEFAIL_SHELLS = {"bash", "zsh"}


def _shell_wrapper_script(cmd):
    """If cmd is a shell wrapper (`bash -c <script>` / `sh -c <script>` / zsh),
    return (shell_basename, script_index, script). Else (None, None, None)."""
    if len(cmd) >= 3 and cmd[1] == "-c":
        base = os.path.basename(cmd[0])
        if base in ("bash", "sh", "zsh", "dash"):
            return base, 2, cmd[2]
    return None, None, None


def _final_pipe_filter(script):
    """If `script` is a top-level pipe (not `||`) whose final stage's command is
    a pager/filter, return that command's name. Else None."""
    if "|" not in script:
        return None
    # split on a single | that is not part of '||'
    parts = _re.split(r"(?<!\|)\|(?!\|)", script)
    if len(parts) < 2:
        return None
    last = parts[-1].strip()
    if not last:
        return None
    first_tok = last.split()[0]
    base = os.path.basename(first_tok)
    return base if base in _PIPE_FILTER_CMDS else None


def _output_fail_token(out):
    """Return a recognised runner fail-token if the output shows a failure,
    even on a zero exit. Conservative - only strong, runner-specific patterns,
    so a passing run ('0 failed', '5 passed') is never flagged."""
    patterns = [
        r"\b[1-9]\d* failed\b",        # pytest:  "1 failed"
        r"(?m)^FAILED\b",              # pytest -v line, generic
        r"(?m)^--- FAIL",             # go test
        r"(?m)^FAIL\b",               # go test summary
        r"\bFAILURES!\b",             # junit-style
    ]
    for pat in patterns:
        m = _re.search(pat, out)
        if m:
            return m.group(0).strip()
    return None


def _run_test(cmd, env=None, with_stderr=False):
    """Run a test command and return (exit_code, combined_output, warnings), and
    stderr on its own last when `with_stderr` is set.

    Hardens against pipeline exit-code masking (R2): pipefail is injected into
    bash/zsh `-c` wrappers; a pager/filter final stage raises a warning.
    """
    warnings = []
    run_cmd = list(cmd)
    shell, idx, script = _shell_wrapper_script(cmd)
    if script is not None:
        filt = _final_pipe_filter(script)
        if filt:
            warnings.append(
                f"pipe-masking risk: the exit code reflects the last pipeline "
                f"stage ({filt}), not your test. "
                + (f"`set -o pipefail` was injected so a mid-pipeline failure "
                   f"still propagates." if shell in _PIPEFAIL_SHELLS else
                   f"this {shell} wrapper cannot take `set -o pipefail` safely - "
                   f"the inner failure may be masked.")
            )
        if shell in _PIPEFAIL_SHELLS and "pipefail" not in script:
            run_cmd[idx] = "set -o pipefail\n" + script
    proc = subprocess.run(run_cmd, capture_output=True, text=True,
                          env={**os.environ, **env} if env else None)
    out = (proc.stdout or "") + (proc.stderr or "")
    if with_stderr:
        return proc.returncode, out, warnings, proc.stderr or ""
    return proc.returncode, out, warnings


def _stamp_identity(payload):
    """Give a record an identity, in place, and return (record_id, digest).

    TWO STAMPS, AND THEY ANSWER DIFFERENT QUESTIONS.

    `record_id` is unique to this write. It is what makes a registry entry able
    to say "the run I was created from", so a file replaced after it was cited
    is detectable. A digest cannot do this job on its own: `now_iso()` is
    second-resolution, so two runs of a fast command with identical output
    inside one second produce a byte-identical payload and the same digest.

    `content_digest` covers what was written. It catches the other failure - a
    record edited in place rather than replaced, which keeps its record_id.

    Neither is a claim about whether the run was honest. They establish only
    that the record a gate cites is the record that was written.
    """
    record_id = uuid.uuid4().hex[:16]
    payload["record_id"] = record_id
    payload.pop("content_digest", None)
    digest = _content_digest(payload)
    payload["content_digest"] = digest
    return record_id, digest


def _write_evidence(task_dir, name, payload):
    """Write one evidence record, stamped with its identity.

    Stamping happens here rather than in each caller so that every record gets
    an identity by construction - a caller cannot forget, and a caller added
    later inherits it.
    """
    _stamp_identity(payload)
    ev_dir = os.path.join(task_dir, "evidence")
    os.makedirs(ev_dir, exist_ok=True)
    path = os.path.join(ev_dir, name + ".json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    # also drop the full log next to it
    log_path = os.path.join(ev_dir, name + ".log")
    with open(log_path, "w", encoding="utf-8") as fh:
        fh.write(payload.get("_full_log", ""))
    # The digest of the bytes just written, for `sha256sum -c` (ADR-089).
    from compass_pkg import evidence_sums
    evidence_sums.record_written(task_dir, path)
    return path


def _resolve_scenario(task_dir, scenario):
    """Check a --scenario binding. A red/green that proves a test ran is
    weaker than one bound to the scenario it is evidence FOR - relevance, not
    just failure. The id must be in the manifest's scenarios, an empty list
    included: a red bound to a scenario nobody wrote would unlock code edits
    for acceptance that does not exist."""
    if not scenario:
        return None
    try:
        task, _ = load_manifest(task_dir)
    except CompassError:
        return scenario  # no manifest.yml yet - record the binding, can't check it
    ids = {s.get("id") for s in (task.get("scenarios") or []) if isinstance(s, dict)}
    if scenario not in ids:
        listed = (f"its scenarios are {sorted(ids)}" if ids
                  else "it has no scenarios yet")
        raise CompassError(
            f"--scenario '{scenario}' is not a scenario in this issue's "
            f"manifest.yml: {listed}. Add it first with `compass scenario add "
            f"{scenario} --title \"...\" --intent INT-1 --test <test file>`, "
            f"or bind to one that exists."
        )
    return scenario


# Coverage-floor neutralisation + the test_micro_command setting.
# The sanctioned verified-by kinds for an honest non-unit red.
_VERIFIED_BY_KINDS = {"regression", "e2e", "typecheck", "live"}


def _read_config(task_dir):
    """Load the settings of the project containing task_dir. {} on miss."""
    root = find_upwards(task_dir, ".compass") or task_dir
    return project_settings.lenient(root)


def settings_hint(task_dir, key, value=None):
    """A setting as advice shows it, naming the file the project's settings
    are read from: "`adoption: enforced` in compass.yml"."""
    root = find_upwards(task_dir, ".compass") or task_dir
    return project_settings.named(root, key, value)


def _micro_command(args, task_dir):
    """The command a TDD micro-run runs: the explicit `-- <cmd>` if given,
    else project.test_micro_command, else project.test_command."""
    if args.command:
        return list(args.command)
    proj = _read_config(task_dir).get("project") or {}
    cmd = proj.get("test_micro_command") or proj.get("test_command")
    if not cmd:
        return None
    import shlex
    return shlex.split(cmd)


def _is_pytest_command(cmd):
    """Does this command invoke pytest? Used for both the coverage flag and the
    exit-code reading below, since both are pytest-specific."""
    if not cmd:
        return False
    base = os.path.basename(str(cmd[0]))
    return base.startswith(("pytest", "py.test")) or "pytest" in cmd


def _pytest_cov_available():
    """Is pytest-cov actually loadable in the environment that will run pytest?

    `--cov-fail-under` is a pytest-cov flag, not a pytest one. Injecting it
    where the plugin cannot load makes pytest exit 4 (usage error) without
    running a single test. Projects legitimately disable plugin autoload -
    PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 is the standard cure for plugins that hang
    on init in clean environments - and there the flag is always rejected.
    """
    if os.environ.get("PYTEST_DISABLE_PLUGIN_AUTOLOAD"):
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("pytest_cov") is not None
    except Exception:
        return False


def _command_turns_cov_off(cmd):
    """Does the command itself stop pytest-cov loading?

    `_pytest_cov_available` reads the calling environment. A command can set
    the same variable for itself - `env PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
    python3 -m pytest`, which is how `make test` runs - or pass `-p no:cov`.
    Either way pytest rejects the flag and runs nothing, unless the command
    also loads the plugin by name with `-p pytest_cov`.
    """
    words = [str(c) for c in cmd]
    pairs = list(zip(words, words[1:]))
    if any(a == "-p" and b == "pytest_cov" for a, b in pairs) \
            or "-ppytest_cov" in words:
        return False
    if any(w.startswith("PYTEST_DISABLE_PLUGIN_AUTOLOAD=")
           and w.split("=", 1)[1] not in ("", "0") for w in words):
        return True
    return any(a == "-p" and b in ("no:cov", "no:pytest_cov") for a, b in pairs) \
        or "-pno:cov" in words or "-pno:pytest_cov" in words


def _neutralise_coverage(cmd):
    """For a recognised pytest micro-run, inject --cov-fail-under=0 so a
    project-wide coverage floor cannot refuse a passing targeted test. The
    micro-run is never the coverage gate - the full suite at the verify stage is. An
    explicit --cov-fail-under is preserved (the full-suite floor is respected);
    a non-pytest command is left untouched.

    The flag is added only when pytest-cov can actually load. Adding a flag the
    runner will reject turns a real test run into a usage error, which is a
    worse failure than the coverage floor this exists to work around.
    """
    if not cmd:
        return cmd
    if any("--cov-fail-under" in str(c) for c in cmd):
        return cmd
    if _is_pytest_command(cmd) and _pytest_cov_available() \
            and not _command_turns_cov_off(cmd):
        return list(cmd) + ["--cov-fail-under=0"]
    return cmd


# A non-zero exit does NOT mean "a test failed". A runner exits non-zero for
# reasons that mean the opposite - no test ran at all. Recording one of those as
# a red writes the .red marker, which hooks/pre-tool.sh treats as proof that a
# real failure was observed. A typo would then unlock a code edit.
#
# pytest: 1 = tests failed · 2 = interrupted · 3 = internal error
#         4 = usage error  · 5 = no tests collected
_NO_TEST_RAN_EXITS = {
    2: "it was interrupted before finishing (pytest exit 2)",
    3: "the runner hit an internal error (pytest exit 3)",
    4: "the runner rejected an argument (pytest exit 4, a usage error)",
    5: "no test was collected by that path (pytest exit 5)",
}


def _red_rejection_reason(code, command):
    """Why this exit must not be recorded as a red, or None if it may be.

    Only applied to commands recognisable as pytest, because these codes are
    pytest's. An unrecognised runner keeps the permissive behaviour: narrowing
    that would break every project using a runner Compass cannot identify.
    """
    if not _is_pytest_command(command):
        return None
    return _NO_TEST_RAN_EXITS.get(code)


def _silent_red_reason(out, command, task_dir):
    """Why a failing run of an unrecognised runner ran no test, or None.

    A real runner that fails prints why. A command that printed nothing and
    names none of the issue's declared test files - `false` is the one-word
    case - ran no test, and a red from it would unlock code edits on
    nothing. A command that prints and fails still records a red; the
    record keeps the command, so it can be read.
    """
    if out.strip():
        return None
    try:
        task, _ = load_manifest(task_dir)
    except CompassError:
        task = {}
    text = " ".join(command)
    if any(path in text for path in declared_test_paths(task)):
        return None
    return ("it printed nothing and names none of the issue's declared test "
            "files, so no test ran")


def _loop(args, task_dir):
    """The loop a red or green belongs to, from `--loop`. With no `--loop` it is
    `default_loop`. The parser refuses any other value; a caller that builds its own
    arguments is checked here."""
    loop = getattr(args, "loop", None) or default_loop(task_dir)
    if loop not in LOOPS:
        raise CompassError(f"--loop {loop!r} is not a loop; use one of: {', '.join(LOOPS)}")
    return loop


def default_loop(task_dir):
    """`outer` for a quick fix the four-layer acceptance strategy applies to, else
    `inner` (ADR-080). A quick fix has one scenario, and its declared test is that
    scenario's acceptance test, so its red and green are the outer loop. Whether the
    strategy applies is `acceptance_strategy.in_scope`, the one scope rule (ADR-079).
    A path issue (ADR-092) has no quick fix approach: the light evidence row that
    replaces it routes the strategy to `existing-dsl`, so that routing defaults to
    the outer loop."""
    from compass_pkg.acceptance_strategy import in_scope, stored
    from compass_pkg.path_stages import is_path_issue
    from compass_pkg.stable_ids import APPROACH_QUICK_FIX
    try:
        task, _ = load_manifest(task_dir)
    except (CompassError, OSError, ValueError):
        return "inner"
    if is_path_issue(task):
        if (stored(task) or {}).get("routing") != "existing-dsl":
            return "inner"
    elif not isinstance(task, dict) or task.get("delivery_approach") != APPROACH_QUICK_FIX:
        return "inner"
    return "outer" if in_scope(task, task_dir)[0] else "inner"


def _red_scenarios(args, task_dir, loop, verb="tdd-red"):
    """The scenarios one red or green run is bound to: `[]`, one, or several
    (ADR-081 for the red, ADR-085 for the green). Several, from a repeated
    `--scenario` or from `--every-scenario`, need the outer loop, which runs the
    whole suite once."""
    given = getattr(args, "scenario", None)
    given = [given] if isinstance(given, str) else list(given or [])
    if getattr(args, "every_scenario", False):
        if given:
            raise CompassError(f"compass {verb}: give --scenario or --every-scenario, not both.")
        task, _ = load_manifest(task_dir)
        given = [s["id"] for s in task.get("scenarios") or [] if isinstance(s, dict)
                 and s.get("id") and s.get("verifiable") != "narrative"]
        if not given:
            raise CompassError(f"compass {verb}: --every-scenario found no scenario in this "
                               "issue's manifest.yml. Add one with `compass scenario add`.")
    if len(given) > 1 or getattr(args, "every_scenario", False):
        if loop != "outer":
            raise CompassError(f"compass {verb}: one run binds several scenarios only for "
                               "the acceptance suite; add --loop outer.")
    return [_resolve_scenario(task_dir, s) for s in dict.fromkeys(given)]


def _unbound_scenarios(task_dir, scenarios, broken):
    """The scenarios of a run with no declared test that failed or errored in it,
    each with its declared tests."""
    task, _ = load_manifest(task_dir)
    tests = {s.get("id"): [t for t in s.get("tests") or [] if isinstance(t, str)]
             for s in task.get("scenarios") or [] if isinstance(s, dict)}
    return [(s, tests.get(s) or []) for s in scenarios
            if not any(pytest_report.covers(broken, t) for t in tests.get(s) or [])]


def cmd_tdd_red(args):
    task_dir = resolve_issue_dir(args.task)
    loop = _loop(args, task_dir)
    scenarios = _red_scenarios(args, task_dir, loop)
    several = len(scenarios) > 1 or bool(getattr(args, "every_scenario", False))
    scenario = scenarios[0] if scenarios else None
    verified_by = getattr(args, "verified_by", None)
    if verified_by and verified_by not in _VERIFIED_BY_KINDS:
        raise CompassError(
            f"compass tdd-red: --verified-by '{verified_by}' is not a recognized "
            f"kind. Allowed: {sorted(_VERIFIED_BY_KINDS)}. A verified-by red ties "
            f"the scenario's acceptance to a non-unit guard (a typecheck, an e2e "
            f"or regression suite, a live run) for changes with no natural unit red."
        )
    command = _micro_command(args, task_dir)
    if not command:
        raise CompassError("compass tdd-red needs a test command, e.g. "
                           "`compass tdd-red --scenario TRC-A1 -- pytest tests/test_x.py`"
                           " (or set %s)" % settings_hint(
                               task_dir, "project.test_micro_command"))
    command = _neutralise_coverage(command)
    # pytest's own report says which tests failed, however pytest is
    # started; see pytest_report.
    env, report, ours, before = pytest_report.with_report(command)
    tree_ids = ids_for(task_dir)   # the tree the test runs on, named before it runs
    code, out, warnings, stderr = _run_test(command, env, with_stderr=True)
    for w in warnings:
        sys.stderr.write(f"compass tdd-red: warning - {w}\n")
    excerpt = "\n".join(out.splitlines()[-25:])
    red_kind, heading, rejection, missing, broken = None, None, None, [], None
    ran_pytest = pytest_report.written(report, before)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(task_dir))))
    if code == 4 and loop == "outer" and not ran_pytest and _is_pytest_command(command):
        heading = pytest_report.DID_NOT_RUN
        rejection = pytest_report.exit_4_reason(stderr, project_root)
    elif code != 0 and (ran_pytest or _is_pytest_command(command)):
        red_kind, heading, rejection = pytest_report.judge(
            report if ran_pytest else None, code, project_root,
            _NO_TEST_RAN_EXITS, loop=loop)
        if ran_pytest:
            missing = pytest_report.missing_modules(report, project_root)
            broken = pytest_report.failed_tests(report)
    elif code != 0:
        # A runner Compass does not recognise, and no pytest report: the
        # exit code is all there is to go on, and the record says so.
        rejection = (_red_rejection_reason(code, command)
                     or _silent_red_reason(out, command, task_dir))
        heading = pytest_report.DID_NOT_RUN if rejection else None
        red_kind = None if rejection else "exit-code"
    if ours:
        try:
            os.remove(report)
        except OSError:
            pass
    if code == 0:
        raise CompassError(
            "compass tdd-red: the test command PASSED (exit 0) - there is no "
            "red to record. The TDD strategy is red-before-green: write a test that "
            "actually fails first.\n--- output (tail) ---\n" + excerpt
        )
    if heading == pytest_report.NO_TEST_FAILED:
        raise CompassError(
            "compass tdd-red: NO TEST FAILED - %s.\n"
            "A .red marker means a real, observed failure is on record; the "
            "pre-tool hook unlocks code edits on the strength of it. Make a "
            "test fail for the missing behavior, then try again.\n"
            "  command: %s\n--- output (tail) ---\n%s"
            % (rejection, " ".join(command), excerpt)
        )
    if rejection:
        raise CompassError(
            "compass tdd-red: the test command DID NOT RUN - %s. That is not a "
            "failing test, so there is no red to record.\n"
            "A .red marker means a real, observed failure is on record; the "
            "pre-tool hook unlocks code edits on the strength of it. Fix the "
            "command so the test actually runs, then try again.\n"
            "  command: %s\n--- output (tail) ---\n%s"
            % (rejection, " ".join(command), excerpt)
        )
    unbound = _unbound_scenarios(task_dir, scenarios, broken) \
        if several and broken is not None else []
    if unbound:
        raise CompassError(
            "compass tdd-red: no red is recorded - pytest's report shows no failed or "
            "errored test for: " + "; ".join(
                f"{s} (declares {', '.join(t) or 'no test'})" for s, t in unbound)
            + ". Each scenario of the run needs a declared test that failed.")
    from compass_pkg.acceptance_strategy import stage_one
    try:
        before_implement = stage_one(load_manifest(task_dir)[0], loop)
    except (CompassError, OSError, ValueError):
        before_implement = False    # no manifest: the red is implement's, as before
    payload = {
        "command": " ".join(command),
        # The argument list as given: two lists can join to the same text.
        "argv": list(command),
        "scenario": scenario,          # the scenario this red is evidence FOR
        "loop": loop,
        "exit_code": code,
        "passed": False,
        "timestamp": now_iso(),
        "log_excerpt": excerpt,
        "_full_log": out,
    }
    if verified_by:
        payload["verified_by"] = verified_by   # a sanctioned non-unit red
    if red_kind:
        payload["red_kind"] = red_kind         # "import": the module is not written yet
    if red_kind == "import" and missing:
        payload["missing_modules"] = missing
    if before_implement:
        payload["before_implement"] = True     # stage 1: no marker
    if several:
        payload.update(run_id=uuid.uuid4().hex[:16], scenarios_in_run=list(scenarios))
    _bind_to_tree(payload, tree_ids)
    # The binding and the loop decide the path, so one scenario's red cannot
    # overwrite another's, nor an inner red the outer one (ADR-082). One run
    # bound to several scenarios writes one record per scenario (plan Q14).
    ev_paths = [_write_evidence(task_dir, record_stem("red", one, loop),
                                dict(payload, scenario=one)) for one in scenarios or [None]]
    ev_path = ev_paths[0]
    payload.pop("_full_log", None)
    marker = os.path.join(task_dir, ".red")
    if before_implement:
        unlocked = ["stage 1  : a red before implement writes no .red marker, so code "
                    "edits stay refused (ADR-081)."]
    else:
        open(marker, "w").close()  # the hook reads this
        unlocked = [f"marker   : {marker}",
                    "           the pre-tool hook will now allow code edits."]
    bound = (f" (bound to {', '.join(scenarios)})" if scenarios
             else " (unbound - consider --scenario)")
    judged = ([("judged by exit code only: Compass does not recognize this "
                "runner, and it wrote no pytest report")]
              if red_kind == "exit-code" else [])
    return say(args,
               f"compass tdd-red: failing test recorded (exit {code}){bound}.",
               detail=judged + [f"evidence : {p}" for p in ev_paths]
                      + [x for x in [_scenario_line(task_dir, s) for s in scenarios] if x]
                      + unlocked,
               scenario=scenario, exit_code=code, evidence=ev_path,
               marker=None if before_implement else marker)


def _source_tree_hash(project_root):
    """Compute a stable SHA-256 of the source tree under project_root.

    Covers all *.py, *.md, *.yml, *.yaml, *.json, *.toml files, ordered by
    their relative path (deterministic). Excludes the project root's own
    .compass/, and .git/, __pycache__/, .venv/, node_modules/ and evidence/
    directories at any depth.

    Returns a hex digest string. Performance target: < 200 ms on typical
    project trees (< 100 MB of source files).

    Hash is content + path, deterministic. Used by cmd_tdd_green to
    detect whether any source file changed between two invocations.
    """
    # `.compass/` is left out only at the project root, where it holds this
    # project's own records. One anywhere else - a worked example, a test
    # fixture, an eval seed - is source, and an edit to it is a change.
    # Test-tool caches are written by the runs themselves - a refactor's
    # baseline run creates pytest's cache folder - so counting them would
    # read a run as a change.
    _EXCLUDED_DIRS = {".git", "__pycache__", ".venv", "node_modules",
                      "evidence", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
    # `docs/compass/` is the tree id's own exclusion too (`binding._OUTSIDE_THE_TREE`): the
    # issue's documents live there, and an edit to one is not a change to the code the test
    # runs on. Without it a second identical green is not a rerun.
    _EXCLUDED_AT_ROOT = {".compass", os.path.join("docs", "compass")}
    _INCLUDED_EXTS = {".py", ".md", ".yml", ".yaml", ".json", ".toml"}

    h = hashlib.sha256()
    # Walk the tree in sorted order to be deterministic across file systems
    for root, dirs, files in os.walk(project_root):
        # Prune excluded directories in-place so os.walk skips them
        at_root = root == project_root   # os.walk yields the root first, as given
        here = os.path.relpath(root, project_root)
        dirs[:] = sorted(d for d in dirs if d not in _EXCLUDED_DIRS
                         and os.path.normpath(os.path.join(here, d)) not in _EXCLUDED_AT_ROOT)
        for fname in sorted(files):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in _INCLUDED_EXTS:
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, project_root)
            # Hash the relative path (so renames are detected) then content
            h.update(rel.encode("utf-8", errors="replace"))
            try:
                with open(full, "rb") as fh:
                    h.update(fh.read())
            except OSError:
                pass  # file disappeared mid-walk - skip it
    return h.hexdigest()


def _bind_to_tree(payload, tree_ids):
    """Name the tree this run tested, before the record is stamped, so the
    digest covers the name. The ids are taken before the test runs: a test
    that rewrites files must be recorded against the tree it ran on, not the
    one it left behind. Outside a git repository there are no ids. See
    binding.py."""
    payload.update(tree_ids)


def _scenario_line(task_dir, scenario):
    """`scenario : <acceptance criteria>:<line>` for the row that defines
    `scenario`, so a reader opens it with one click (#291), or None."""
    if not scenario:
        return None
    from compass_pkg.spec_location import spec_path
    from compass_pkg.terminal import relative_to_project
    path = spec_path(task_dir)
    try:
        # Rows inside a rendered block are the block's, not the scenario's
        # definition. The removed lines stay as empty lines, so the line number
        # is the line in the file.
        from compass_pkg import rendered_blocks
        text = rendered_blocks.read_masked(path, keep_lines=True)
        for n, line in enumerate(text.split("\n"), 1):
            if line.lstrip().startswith(f"| {scenario} |"):
                return f"scenario : {relative_to_project(path)}:{n}"
    except OSError:
        return None
    return None


def _upsert_test_run_evidence(task_dir, scenario, rel_path,
                             record_id=None, content_digest=None):
    """Append or update a test-run entry in manifest.yml's evidence registry.
    Same scenario -> update in place; new -> append. This is what makes the
    green visible to `compass check`, which reads the registry, not the file.

    The entry carries the identity of the record it was created from. That is
    what lets `evidence-identity-matches` later ask whether the file a gate
    cites is still the run this entry was made for. The stamps are passed in
    rather than re-read from the file: the record was just written, and
    re-reading it would leave a window in which what is registered is not what
    was recorded.
    """
    task_path = manifest_path(task_dir)
    if not os.path.isfile(task_path):
        return  # no manifest.yml - assess has not run; nothing to update
    try:
        task = load_manifest_file(task_path)
    except CompassError:
        return
    if not isinstance(task, dict):
        return
    reg = task.get("evidence") or []
    if not isinstance(reg, list):
        return
    existing = None
    # One entry per binding and loop: an outer-loop green (ADR-082) has its own.
    outer = rel_path.endswith(".outer.json")
    for e in reg:
        if (isinstance(e, dict) and e.get("type") == "test-run"
                and e.get("scenario") == scenario
                and str(e.get("path") or "").endswith(".outer.json") == outer):
            existing = e
            break
    if existing:
        existing["path"] = rel_path
        if record_id:
            existing["record_id"] = record_id
            existing["content_digest"] = content_digest
    else:
        base = (f"EV-T-{scenario}" if scenario else "EV-T") + ("-outer" if outer else "")
        used = {e.get("id") for e in reg if isinstance(e, dict)}
        ev_id, n = base, 1
        while ev_id in used:
            n += 1
            ev_id = f"{base}-{n}"
        entry = {"id": ev_id, "type": "test-run", "path": rel_path}
        if scenario:
            entry["scenario"] = scenario
        if record_id:
            entry["record_id"] = record_id
            entry["content_digest"] = content_digest
        reg.append(entry)
    task["evidence"] = reg
    save_manifest(task, task_path)


# --- compass acceptance -----------------------------------------------------
# Config, docs and behaviour-preserving refactors have no natural
# behavioural red - the whole point of a refactor is that behaviour does not
# change. Without this verb, the only way past the hook for such a change is
# a red that asserts a string is in a file. That tests the implementation,
# not the behaviour, which the tdd-discipline skill warns against. This
# gives those changes a real signal.
#
# Two kinds, because the honest evidence differs:
#   validation - a validator command (`docker compose config`, `promtool check
#                rules`, `terraform validate`, a schema parse) must pass after
#                the change. There may be no meaningful "before" - a new rules
#                file has none - so no baseline is needed.
#   refactor   - a passing command must STILL pass, across a source tree that
#                demonstrably changed. Behaviour preservation is the contract,
#                so the baseline is needed and green-then-green with an
#                unchanged tree is refused: that is two runs, not a refactor.
#
# It writes `.acceptance`, never `.red`. `.red` means "a real failure was
# observed here" and is the framework's most honest artifact; overloading it
# would make it ambiguous.



def _acceptance_marker(task_dir):
    return os.path.join(task_dir, ".acceptance")


def _acceptance_state(task_dir):
    path = os.path.join(task_dir, "evidence", "acceptance-baseline.json")
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (OSError, ValueError):
        return {}


def cmd_acceptance_start(args):
    kind = args.kind
    if kind not in _ACCEPTANCE_KINDS:
        raise CompassError(
            f"compass acceptance start: '{kind}' is not an acceptance kind. "
            f"Allowed: {', '.join(_ACCEPTANCE_KINDS)}.\n"
            "  validation - a validator must pass after the change (config, "
            "manifests, schemas, docs that carry a checkable contract)\n"
            "  refactor   - a passing command must still pass afterwards, "
            "across a changed tree (behavior preservation)"
        )

    task_dir = resolve_issue_dir(getattr(args, "task", None))
    command = list(args.command or [])
    if not command:
        raise CompassError(
            "compass acceptance start: give the command after `--` - the "
            "validator to run, or the suite whose green you are preserving.")

    project_root = find_upwards(task_dir, ".compass") or task_dir
    payload = {
        "kind": kind,
        "command": " ".join(command),
        # The argument list as given: two lists can join to the same text.
        "argv": list(command),
        "declared_at": now_iso(),
        "tree_hash": _source_tree_hash(project_root),
    }

    if kind == "validation":
        # A validation stands in for a red, so it is declared before the
        # change. On a quick fix, `start` recorded the tree; a file changed
        # since then means the change came first. The scenario's own tests
        # may be written first. A refactor may write its characterisation
        # tests first too, so it is not checked here.
        from compass_pkg.start_state import changed_since_start
        try:
            task, _ = load_manifest(task_dir)
        except CompassError:
            task = {}
        keep = set(declared_test_paths(task))
        changed = changed_since_start(project_root, os.path.basename(task_dir), keep)
        if changed:
            more = (f"\n  and {len(changed) - 10} more" if len(changed) > 10 else "")
            raise CompassError(
                "compass acceptance start: these files changed after the "
                "quick fix started, before this acceptance was declared:\n  "
                + "\n  ".join(changed[:10]) + more
                + "\nA validation stands in for a failing test, so it is "
                "declared before the change. Undo the change, declare the "
                "acceptance, then make it again; or, if the change has a "
                "test that can fail, record a red with `compass tdd-red`.")

    if kind == "refactor":
        # The baseline IS the contract. Without a passing command to begin with
        # there is nothing to preserve, so this refuses rather than recording a
        # meaningless "before".
        code, out, _ = _run_test(_neutralise_coverage(command))
        excerpt = out[-2000:]
        if code != 0:
            raise CompassError(
                f"compass acceptance start: the baseline command FAILED "
                f"(exit {code}), so there is no passing behavior to preserve. "
                f"A refactor acceptance means 'this was green and still is'.\n"
                f"--- output (tail) ---\n{excerpt}")
        payload["baseline"] = {"passed": True, "exit_code": code,
                               "log_excerpt": excerpt}

    _write_evidence(task_dir, "acceptance-baseline", payload)
    with open(_acceptance_marker(task_dir), "w", encoding="utf-8") as fh:
        fh.write(kind + "\n")

    # The marker path gets a line to itself. A path followed by prose is a
    # line where neither half is usable: too long to read, and the path cannot
    # be copied without picking it back out of the sentence.
    _detail = ["baseline : PASSING - the same command must pass again after "
               "the change" if kind == "refactor"
               else "validator: " + payload["command"],
               f"marker   : {_acceptance_marker(task_dir)}",
               "           the pre-tool hook will now allow edits. `.red` is "
               "untouched",
               "           and still means a real failure was observed."]
    say(args, f"compass acceptance start: {kind} acceptance declared.",
        detail=_detail, kind=kind, command=payload.get("command"),
        marker=_acceptance_marker(task_dir))
    return 0


def cmd_acceptance_record(args):
    from compass_pkg import release_line
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    # A given release line is judged before the command runs, and stored only after
    # it passes, so a refused line or a failed run writes nothing (ADR-065).
    note = release_line.given(args, task_dir, "compass acceptance record")
    state = _acceptance_state(task_dir)
    if not state:
        raise CompassError(
            "compass acceptance record: no acceptance was declared for this "
            "issue. Run `compass acceptance start --kind validation|refactor -- "
            "<command>` first - the kind of acceptance is stated before the "
            "change, not chosen afterwards to fit what happened.")

    kind = state.get("kind")
    command = list(args.command or []) or state.get("command", "").split()
    if not command:
        raise CompassError("compass acceptance record: give the command after `--`.")

    if kind == "refactor" and " ".join(command) != state.get("command"):
        raise CompassError(
            f"compass acceptance record: this refactor was baselined on\n"
            f"  {state.get('command')}\n"
            f"but you ran\n  {' '.join(command)}\n"
            "A different command proves nothing about the baseline. Run the "
            "same one, or re-declare the acceptance.")

    project_root = find_upwards(task_dir, ".compass") or task_dir
    if kind == "refactor":
        if _source_tree_hash(project_root) == state.get("tree_hash"):
            raise CompassError(
                "compass acceptance record: the source tree has not changed "
                "since the baseline. Green then green with nothing changed in "
                "between is two runs, not a refactor - there is no behavior "
                "preservation to record.")

    tree_ids = ids_for(task_dir)   # the tree the test runs on, named before it runs
    code, out, warnings = _run_test(_neutralise_coverage(command))
    excerpt = out[-2000:]
    if code != 0:
        raise CompassError(
            f"compass acceptance record: the command FAILED (exit {code}) - "
            f"the acceptance is NOT recorded and the marker stays in place.\n"
            f"--- output (tail) ---\n{excerpt}")

    payload = {
        "kind": kind,
        "command": " ".join(command),
        # The argument list as given: two lists can join to the same text.
        "argv": list(command),
        "exit_code": code,
        "passed": True,
        "timestamp": now_iso(),
        "log_excerpt": excerpt,
        "scenario": getattr(args, "scenario", None),
        # When the acceptance was declared, from the baseline. suite-passed
        # counts an acceptance in place of a red only when it was declared
        # before the issue's first green - declared, not chosen afterwards.
        "declared_at": state.get("declared_at"),
    }
    if kind == "refactor":
        payload["baseline"] = state.get("baseline", {})
        payload["baseline"]["command"] = state.get("command")
    _bind_to_tree(payload, tree_ids)

    # The binding decides the path, as in cmd_tdd_green.
    scenario = getattr(args, "scenario", None)
    name = "acceptance"
    if scenario:
        name = "acceptance-" + scenario.replace("/", "_")
    ev_path = _write_evidence(task_dir, name, payload)
    rel_path = f"evidence/{name}.json"
    # Registered as `test-run` so the existing `G1` checks accept it: the point of
    # this verb is to remove the incentive to fake a red, which it only does if
    # the result counts.
    _upsert_test_run_evidence(task_dir, scenario, rel_path,
                              record_id=payload.get("record_id"),
                              content_digest=payload.get("content_digest"))
    release_line.store(task_dir, note, "compass acceptance record")
    marker = _acceptance_marker(task_dir)
    if os.path.exists(marker):
        os.remove(marker)

    print(f"compass acceptance record: {kind} acceptance recorded (exit {code}).")
    for w in warnings:
        print(f"  warning  : {w}")
    if kind == "refactor":
        print("  contract : the baselined command was green before the change "
              "and is green after, across a changed tree")
    from compass_pkg.terminal import relative_to_project
    print(f"  evidence : {relative_to_project(ev_path)}")
    print("  registry : manifest.yml `evidence:` updated with the test-run entry")
    print("  marker   : .acceptance cleared")
    return 0
