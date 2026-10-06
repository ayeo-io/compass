#!/usr/bin/env python3
# =============================================================================
# compass_pkg.bdd - `compass bdd extract` and `compass bdd verify`
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
from compass_pkg.checks import _spec_sha256
from compass_pkg.terminal import say
from compass_pkg.core import CompassError, artifact_path, find_upwards, load_yaml, manifest_path, normalize_spine, now_iso, resolve_issue_dir
from compass_pkg.tdd import _read_config, _run_test, settings_hint



# --- command: bdd extract ----------------------------------------------------
# Lifts the Gherkin out of an issue's acceptance-criteria.md into a plain
# .feature file a real BDD runner (pytest-bdd, cucumber-js, behave, godog) can
# execute. This is what turns the scenario-to-test link from a convention an
# engineer maintains into a fact a runner establishes.

# A Compass scenario in acceptance-criteria.md always looks like this:
#
#   ### Scenario: <title>
#   <!-- traceability id: TRC-A1 · serves: INT-1 -->
#
#   ```gherkin
#   Scenario: <title>
#     Given ...
#   ```
#
# THE ANCHOR IS THE TRACEABILITY COMMENT, NOT THE FENCE. Compass documents
# contain illustrative Gherkin that is not an acceptance criterion (a proposal
# showing what a scenario looks like, this very comment block). Extracting every
# ```gherkin fence would turn those illustrations into scenarios. Requiring the
# traceability comment means only real, id-carrying scenarios are extracted.
# Accept any uppercase id prefix. The template uses TRC- and the examples
# under examples/ use SCN-, and accepting only one would reject a valid
# document with a message that blames the document.
_TRC_COMMENT_RE = re.compile(
    r"<!--\s*traceability id:\s*(?P<trc>[A-Z][A-Z0-9]*-[A-Za-z0-9_]+)\b.*?-->",
    re.S)
_SCENARIO_HEADING_RE = re.compile(r"^###\s+Scenario:\s*(?P<title>.+?)\s*$")
_FENCE_OPEN_RE = re.compile(r"^\s*```+\s*gherkin\s*$", re.I)
_FENCE_CLOSE_RE = re.compile(r"^\s*```+\s*$")
_GHERKIN_STEP_RE = re.compile(
    r"^\s*(Given|When|Then|And|But|\*)\s+\S", re.I)
_GHERKIN_SCENARIO_RE = re.compile(r"^\s*Scenario:\s*(?P<title>.+?)\s*$")


class ParsedScenario(object):
    """One extracted scenario, with enough context to report a good error."""

    __slots__ = ("trc_id", "heading_title", "fence_title", "steps", "line_no")

    def __init__(self, trc_id, heading_title, fence_title, steps, line_no):
        self.trc_id = trc_id
        self.heading_title = heading_title
        self.fence_title = fence_title
        self.steps = steps
        self.line_no = line_no


def scan_spec_markdown(text):
    """Parse acceptance-criteria.md into ParsedScenario records, in document order.

    Only a gherkin fence introduced by a `traceability id:` comment is picked
    up; everything else in the document is prose. Returns [] when the document
    contains no such fence - the caller decides whether that is an error.
    """
    lines = text.splitlines()
    out = []
    pending_heading = None       # most recent "### Scenario:" title
    pending_trc = None           # most recent traceability id
    pending_line = 0

    i = 0
    while i < len(lines):
        line = lines[i]

        m = _SCENARIO_HEADING_RE.match(line)
        if m:
            pending_heading = m.group("title")
            pending_line = i + 1
            i += 1
            continue

        m = _TRC_COMMENT_RE.search(line)
        if m:
            pending_trc = m.group("trc")
            i += 1
            continue

        if _FENCE_OPEN_RE.match(line):
            body = []
            i += 1
            while i < len(lines) and not _FENCE_CLOSE_RE.match(lines[i]):
                body.append(lines[i])
                i += 1
            i += 1                                  # step past the closing fence
            if pending_trc is None:
                # An illustration, not a scenario. Deliberately ignored - see
                # the note on the anchor above.
                pending_heading = None
                continue
            fence_title = None
            steps = []
            for b in body:
                sm = _GHERKIN_SCENARIO_RE.match(b)
                if sm and fence_title is None:
                    fence_title = sm.group("title")
                    continue
                if b.strip():
                    steps.append(b.strip())
            out.append(ParsedScenario(
                trc_id=pending_trc,
                heading_title=pending_heading,
                fence_title=fence_title,
                steps=steps,
                line_no=pending_line or i,
            ))
            pending_trc = None
            pending_heading = None
            continue

        i += 1

    return out


def validate_scenarios(scenarios, spec_path):
    """Return a list of human-readable problems. Empty list means valid.

    Collects instead of raising, so a document with three problems reports
    all three, each with its location.
    """
    problems = []
    if not scenarios:
        problems.append(
            "%s contains no Gherkin scenarios. A scenario is a '### Scenario:' "
            "heading, a '<!-- traceability id: SCN-... -->' comment (any uppercase id prefix), and a "
            "```gherkin fence - the comment is what marks a fence as a real "
            "scenario rather than an illustration." % spec_path)
        return problems

    seen = {}
    for s in scenarios:
        where = "%s:%d" % (spec_path, s.line_no)
        if s.fence_title is None:
            problems.append(
                "%s: %s - the gherkin fence has no 'Scenario:' line."
                % (where, s.trc_id))
            continue
        if s.heading_title is not None and s.heading_title != s.fence_title:
            problems.append(
                "%s: %s - the title drifts between the heading and the fence.\n"
                "  heading: %s\n  fence  : %s"
                % (where, s.trc_id, s.heading_title, s.fence_title))
        if not s.steps:
            problems.append(
                "%s: %s - the scenario has no steps." % (where, s.trc_id))
        else:
            bad = [st for st in s.steps if not _GHERKIN_STEP_RE.match(st)]
            if bad:
                problems.append(
                    "%s: %s - not valid Gherkin; a step must start with Given, "
                    "When, Then, And, or But.\n  offending line: %s"
                    % (where, s.trc_id, bad[0]))
        if s.trc_id in seen:
            problems.append(
                "%s: %s is used twice (also at line %d)."
                % (where, s.trc_id, seen[s.trc_id]))
        seen[s.trc_id] = s.line_no
    return problems


def render_feature(slug, scenarios, spec_rel_path):
    """Render the .feature text. Pure: no clock, no absolute paths, no randomness.

    Determinism is the point - the output is diffable and committable, and
    `compass bdd extract` run twice over an unchanged spec produces
    identical bytes.
    """
    lines = [
        "# Derived from %s by `compass bdd extract`." % spec_rel_path,
        "# Do not hand-edit - your edits are overwritten on the next extract.",
        "# Edit the source spec instead.",
        "",
        "Feature: %s" % slug,
        "",
    ]
    for s in scenarios:
        lines.append("  @%s" % s.trc_id)
        lines.append("  Scenario: %s" % s.fence_title)
        for step in s.steps:
            lines.append("    %s" % step)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def atomic_write(path, text):
    """Write via a temp file in the destination directory, then rename.

    A malformed spec must leave no partial output behind, and a crash mid-write
    must not corrupt a file a runner may already be reading. Rename within one
    directory is atomic on POSIX; writing in place is not.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".compass-bdd-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def default_extract_path(task_dir):
    """The zero-config output path for an extracted runnable feature file.

    Named for what it holds - the issue's acceptance criteria - and written
    into the issue directory so the verb works before a project has
    configured anything."""
    return os.path.join(task_dir, "acceptance-criteria.feature")


def _bdd_out_path(args, task_dir, slug):
    """Resolve where the .feature goes: --out, then config, then the issue dir.

    The issue directory is the zero-config default so the verb works before a
    project has edited anything (ADR-006); `project.bdd_features_dir` exists for
    adopters whose runner expects a conventional features/ directory.
    """
    explicit = getattr(args, "out", None)
    if explicit:
        return explicit
    proj = _read_config(task_dir).get("project") or {}
    features_dir = proj.get("bdd_features_dir")
    if features_dir:
        root = find_upwards(task_dir, ".compass") or task_dir
        if not os.path.isabs(features_dir):
            features_dir = os.path.join(root, features_dir)
        return os.path.join(features_dir, "%s.feature" % slug)
    return default_extract_path(task_dir)


_ZERO_COLLECTED = re.compile(
    r"\b0\s+(scenarios?|tests?|features?|steps?)\b|no tests ran|"
    r"collected 0 items|0 scenarios \(", re.I)
_SOME_COLLECTED = re.compile(
    r"\b([1-9]\d*)\s+(scenarios?|tests?)\b|collected ([1-9]\d*) item", re.I)


def _probe_collected(out, runner=""):
    """Did the tag actually bind to at least one scenario?

    The exit code alone is not enough: pytest exits 5 on an empty collection,
    but cucumber-js and behave exit 0 when a tag filter matches nothing.
    Trusting the exit code would report every scenario as bound for those two
    runners.

    So read the count the runner prints. An explicit zero is decisive; otherwise
    need a positive count. Silence is treated as "not collected", because the
    failure that matters here is a false pass.
    """
    # behave needs its own rule.
    # Its --dry-run summary ALWAYS opens "0 features passed, 0 failed, ..."
    # regardless of whether the tag matched, so the generic zero-match below
    # reads every behave probe as unbound. What distinguishes the two is the
    # `untested` count: a matched tag leaves scenarios untested (dry run), a
    # non-matching one leaves them merely skipped.
    if "behave" in (runner or "").lower():
        m = re.search(r"(\d+)\s+untested", out)
        return bool(m and int(m.group(1)) > 0)
    if _ZERO_COLLECTED.search(out):
        return False
    m = _SOME_COLLECTED.search(out)
    return bool(m and any(g and int(g) > 0 for g in m.groups()))


def _bdd_tag_selector(runner, command):
    """How to ask this runner to select one scenario tag, or None if unknown.

    Every runner Compass targets supports tag selection - that is why
    `compass bdd extract` writes tags rather than comments (see the extractor's
    note on the anchor). The flag differs per runner, so this maps the ones we
    know and returns None for the rest, which downgrades verification to a
    weaker method rather than guessing wrong.
    """
    joined = " ".join(command).lower()
    r = (runner or "").lower()
    if "pytest" in r or "pytest" in joined:
        return lambda tag: ["--collect-only", "-q", "-m", tag]
    if "cucumber" in r or "behave" in r:
        return lambda tag: ["--dry-run", "--tags", "@" + tag]
    # godog deliberately has NO selector. It is driven through `go test`, and
    # its -godog.* flags exist only if the suite calls BindCommandLineFlags -
    # which the idiomatic programmatic setup (and the adapter Compass ships)
    # does not. Probing it returns "flag provided but not defined", so every
    # tag would look unbound. Report "could not check" instead.
    return None


def cmd_bdd_verify(args):
    """compass bdd verify -- <run command> - run the BDD suite and record it.

    The producer half of `scenarios-are-executable`. This can depend on the
    project's BDD runner, because a project only runs it when it has one;
    `compass check` must not, which is why the two are separate commands.

    It records the spec's content hash alongside the scenario ids the runner
    reported, so a later check can tell whether the run still describes the
    spec it claims to check.
    """
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    task_yaml = normalize_spine(load_yaml(manifest_path(task_dir)) or {})
    proj = _read_config(task_dir).get("project") or {}
    command = list(getattr(args, "command", None) or [])
    if not command:
        declared = proj.get("bdd_run_command")
        if declared:
            command = shlex.split(declared)
    if not command:
        raise CompassError(
            "compass bdd verify needs a run command, e.g. `compass bdd verify "
            "-- pytest tests/` (or set %s)" % settings_hint(
                task_dir, "project.bdd_run_command"))

    code, out, _warnings = _run_test(command)

    # Which scenarios did the runner actually bind?
    #
    # Scraping stdout for TRC ids does not work: the tags `compass bdd
    # extract` writes become marks in the runner, and a normal run does not
    # print them.
    #
    # So ask the runner instead, using the tag selection the tags exist for:
    # collect (do not run) each tag in turn and see whether anything
    # matches. Collection is cheap, and this asks the exact question the check
    # needs - "is this scenario bound to something the runner can run?"
    scenario_ids = [s.get("id") for s in (task_yaml.get("scenarios") or [])
                    if isinstance(s, dict) and s.get("id")]
    seen, method = [], "tag-probe"
    selector = _bdd_tag_selector(proj.get("bdd_runner") or "", command)
    if selector:
        for sid in scenario_ids:
            probe = list(command) + selector(sid)
            probe_code, probe_out, _ = _run_test(probe)
            if probe_code == 0 and _probe_collected(
                    probe_out, proj.get("bdd_runner") or ""):
                seen.append(sid)
    else:
        # Unknown runner: fall back to scraping, and say so in the record so a
        # reader knows the result is weaker than a probe.
        method = "output-scrape"
        # Word-boundary match: a bare `in` reports SCN-1 as seen when only
        # SCN-10 was printed.
        seen = [s for s in scenario_ids
                if re.search(r"\b%s\b" % re.escape(s), out)]
        if not seen:
            # Nothing named at all. We cannot tell "no scenario bound" from
            # "this runner does not print scenario ids", and reporting the
            # first when it is the second accuses a passing suite.
            method = "unverified"
    seen = sorted(set(seen))

    payload = {
        "command": " ".join(command),
        "exit_code": code,
        "passed": code == 0,
        "timestamp": now_iso(),
        "spec_sha256": _spec_sha256(task_dir),
        "scenarios_seen": seen,
        "runner": proj.get("bdd_runner") or "unknown",
        "method": method,
        "log_excerpt": "\n".join(out.splitlines()[-25:]),
    }
    ev_dir = os.path.join(task_dir, "evidence")
    os.makedirs(ev_dir, exist_ok=True)
    path = os.path.join(ev_dir, "bdd-run.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")

    print(f"compass bdd verify: recorded {len(seen)} scenario(s) from the "
          f"runner (exit {code}).")
    print(f"  evidence : {path}")
    if code != 0:
        print("  note     : the suite did not pass. The record is still "
              "written - `scenarios-are-executable` reports which scenarios "
              "were accounted for, and `suite-passed` is what judges green.")
    return 0


def cmd_bdd_extract(args):
    """compass bdd extract - acceptance-criteria.md -> a runnable .feature file."""
    task_dir = resolve_issue_dir(getattr(args, "task", None))
    slug = os.path.basename(os.path.normpath(task_dir))
    spec_path = artifact_path(task_dir, "acceptance-criteria.md")
    if not os.path.isfile(spec_path):
        raise CompassError(
            "no acceptance criteria for issue '%s' - define them first (%s)"
            % (slug, spec_path))

    with open(spec_path, "r", encoding="utf-8") as fh:
        text = fh.read()

    scenarios = scan_spec_markdown(text)

    # Check everything before writing anything. This is what makes a failed
    # extract leave the filesystem exactly as it was.
    problems = validate_scenarios(scenarios, os.path.relpath(spec_path, os.getcwd()))
    if problems:
        sys.stderr.write("compass bdd extract: %d problem(s) found; nothing written.\n"
                         % len(problems))
        for p in problems:
            sys.stderr.write("  %s\n" % p)
        return 1

    out_path = _bdd_out_path(args, task_dir, slug)
    spec_rel = os.path.join(".compass", "work", slug, os.path.basename(spec_path))
    atomic_write(out_path, render_feature(slug, scenarios, spec_rel))
    # Print a sentence around the path: a bare string suits a shell pipeline,
    # not a person. --json carries the path alone, under a key.
    return say(args, "compass bdd extract: %d scenario(s) -> %s"
                     % (len(scenarios), out_path),
               path=out_path, scenarios=len(scenarios), spec=spec_rel)
