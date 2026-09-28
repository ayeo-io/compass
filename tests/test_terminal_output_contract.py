"""The terminal output contract - what a person reads when they run a verb.

The terminal is a notification surface, not the artifact. A verb that ends a
stage or renders a verdict is a HAND-OFF and fits one screen; a verb somebody
runs deliberately to get detail is a REPORT and keeps its detail, but opens with
a summary they can stop at. Five flags choose how much they get.

Measured before any threshold here was written, on 2026-08-23:
  compass check          45 lines, 14 of them PASS lines, longest line 252 chars
  compass flow           156 lines
  compass approach evaluate   4 lines, one a raw Python dict
  208 print calls inside verb bodies, across 34 verbs
  37 test files asserting a literal string in stdout - 130 assertions

Scenario ids trace to
the-terminal-output-contract/acceptance-criteria.md.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from conftest import write_red_record

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))
CLI = REPO_ROOT / "cli" / "compass"

# The budget, and the reason each number is what it is.
HANDOFF_LINES = 12      # the proposal's number - where a reader stops scrolling
QUIET_HANDOFF_LINES = 5  # a hand-off with nothing to decide
REPORT_SUMMARY_LINES = 5
MAX_WIDTH = 100         # a line budget alone is met by joining lines


def _leaf_parsers():
    """Every leaf parser in the CLI tree, by its full command path.

    Recursive on purpose. The tree has 13 nested subparser groups under 47
    `add_parser` calls, so anything that walks only the top level reaches
    `issue` and misses `issue dashboard` entirely - which is exactly how a
    guard over this tree passes without checking most of it.
    """
    import argparse
    import importlib.util

    # `build_parser` lives in the `cli/compass` entry point, which has no .py
    # extension and is not importable by name. Loading it by path is how the
    # test reaches the real tree rather than a copy that could drift from it.
    spec = importlib.util.spec_from_loader(
        "compass_cli", importlib.machinery.SourceFileLoader("compass_cli", str(CLI)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    build_parser = mod.build_parser

    out = {}

    def walk(parser, path):
        subs = [a for a in parser._actions
                if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            out[" ".join(path)] = parser
            return
        for action in subs:
            for name, child in action.choices.items():
                walk(child, path + [name])

    walk(build_parser(), [])
    return out


# ---------------------------------------------------------------------------
# Group C - the modes
# ---------------------------------------------------------------------------

def test_trc_c1_every_verb_accepts_every_mode_flag():
    """The five mode flags reach every leaf verb (`TRC-C1`).

    The failure this prevents: a flag that works on four verbs and is silently
    ignored on the other thirty, which is worse than not having it.
    """
    flags = ["--quiet", "--summary", "--verbose", "--json", "--evidence-out"]
    leaves = _leaf_parsers()
    # A non-recursive walk reaches the thirteen group parsers by name and
    # stops, so it never sees anything nested. Naming a nested verb catches
    # that directly and does not go out of date as verbs are added, which a
    # bare count would. The floor is a second, cruder net.
    for nested in ("issue dashboard", "gate pass", "evidence add", "bdd verify"):
        assert nested in leaves, (
            "%r was not reached, so the walk over the parser tree is not "
            "recursing into nested subcommand groups. Found: %s"
            % (nested, sorted(leaves)))
    assert len(leaves) >= 30, (
        "only %d leaf verbs were found: %s" % (len(leaves), sorted(leaves)))

    missing = []
    for path, parser in sorted(leaves.items()):
        opts = {o for a in parser._actions for o in a.option_strings}
        for f in flags:
            if f not in opts:
                missing.append("%s: %s" % (path, f))
    assert not missing, (
        "these verbs do not accept a mode flag, so passing it there is either "
        "an error or silently ignored:\n  " + "\n  ".join(missing[:30]))


def test_trc_c1_every_verb_honours_the_flags_it_accepts(tail_project):
    """ACCEPTED is not HONOURED - the half of `TRC-C1` that was missing.

    The docstring above this test used to promise the verb "honours it rather
    than accepting and ignoring it", and the test checked only that argparse
    took the flag. So the parser attached five flags to all 47 leaves and about
    a third of the verbs ignored every one of them - the exact failure the
    scenario was written to prevent, passing a test written to prevent it.

    Run against verbs that were NOT converted by hand, because those are the
    ones a generic mechanism has to carry.
    """
    unconverted = [["issue", "lint"], ["policy", "lint"], ["next"]]
    for argv in unconverted:
        name = " ".join(argv)
        plain = subprocess.run([sys.executable, str(CLI), *argv],
                               cwd=str(tail_project), capture_output=True,
                               text=True, timeout=120)
        as_json = subprocess.run([sys.executable, str(CLI), *argv, "--json"],
                                 cwd=str(tail_project), capture_output=True,
                                 text=True, timeout=120)
        if plain.returncode != 0:
            continue          # the verb has nothing to say in this fixture
        assert as_json.stdout != plain.stdout, (
            "`compass %s --json` printed exactly what it prints without the "
            "flag, so the flag is accepted and ignored:\n%s"
            % (name, as_json.stdout[:200]))
        try:
            json.loads(as_json.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                "`compass %s --json` is not a JSON document (%s):\n%s"
                % (name, exc, as_json.stdout[:200]))

        out = tmp_capture = tail_project / ("cap-%s.txt" % name.replace(" ", "-"))
        ev = subprocess.run([sys.executable, str(CLI), *argv,
                             "--evidence-out", str(out)],
                            cwd=str(tail_project), capture_output=True,
                            text=True, timeout=120)
        assert ev.returncode == 0, ev.stdout + ev.stderr
        assert out.is_file(), (
            "`compass %s --evidence-out PATH` wrote no file, and its own help "
            "says it writes the capture to PATH" % name)


def test_trc_c6_every_verb_declares_which_contract_it_is_under():
    """Each verb declares hand-off or report; neither is not allowed (`TRC-C6`).

    A default is how the 35th verb quietly becomes whatever was easiest.
    """
    undeclared = []
    for path, parser in sorted(_leaf_parsers().items()):
        kind = parser.get_default("output_kind")
        if kind not in ("hand-off", "report"):
            undeclared.append("%s: %r" % (path, kind))
    assert not undeclared, (
        "these verbs do not declare an output kind beside their `func=`, so "
        "nothing says which contract binds them:\n  "
        + "\n  ".join(undeclared[:30]))


def test_trc_c2_quiet_prints_nothing_on_success():
    """--quiet is silent on an uneventful success; the exit code carries it (`TRC-C2`)."""
    from compass_pkg.terminal import Emitter

    e = Emitter(mode="quiet")
    e.hand_off(outcome="the policy was applied", read="technical-design.md")
    assert e.rendered() == "", (
        "--quiet printed on a plain success:\n" + e.rendered())

    e = Emitter(mode="quiet")
    e.hand_off(outcome="4 checks failed", read="verification-report.md",
               reply="approve | request changes", failed=True)
    assert e.rendered(), (
        "--quiet swallowed a failure, so a script's only signal is an exit "
        "code with no message")


def test_trc_c3_json_is_machine_only():
    """--json emits one JSON document and no prose (`TRC-C3`)."""
    from compass_pkg.terminal import Emitter

    e = Emitter(mode="json")
    e.hand_off(outcome="initiative", read="delivery-approach.md",
               items=["eight gates", "every stage full weight"])
    out = e.rendered()
    doc = json.loads(out)
    assert doc["outcome"] == "initiative"
    assert "eight gates" in doc["items"]


def test_trc_c3_existing_json_verb_keeps_its_keys(tmp_path):
    """`approach evaluate --json` already ships - the compatibility half of
    `TRC-C3`.

    ADR-006 makes backward compatibility non-negotiable within a major version,
    so this verb's existing keys are public surface. New keys may appear; none
    of these may be renamed or removed.
    """
    import yaml
    proj = tmp_path / "p"
    (proj / "governance").mkdir(parents=True)
    for f in ("routing-policy.yml", "guardrails.yml"):
        (proj / "governance" / f).write_text(
            (REPO_ROOT / "governance" / f).read_text())
    td = proj / ".compass" / "work" / "t"
    td.mkdir(parents=True)
    (proj / ".compass" / "current-task").write_text("t\n")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    (td / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "t", "created": "2026-08-23",
        "status": "active",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "standard", "goal": "delivery", "role": "engineer",
                       "labels": []},
        "delivery_approach": None, "stages": {}, "gates": [], "evidence": [],
        "scenarios": [], "changed_files": []}, sort_keys=False))

    r = subprocess.run([sys.executable, str(CLI), "approach", "evaluate", "--json"],
                       cwd=str(proj), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    doc = json.loads(r.stdout)
    # Taken from what the verb actually emitted before this change, not from
    # what a compatibility test would like the keys to be called. The first
    # version of this list guessed `final_route` and `phases`, which have
    # never existed - a compatibility assertion against invented names checks
    # nothing and would have failed for the wrong reason.
    for key in ("candidate_route", "candidate_via", "delivery_approach",
                "gates", "stages", "policy_rules_fired", "subtask_ceiling"):
        assert key in doc, (
            "`approach evaluate --json` lost the key %r, which shipped before "
            "this change and is public surface (ADR-006). Keys present: %s"
            % (key, sorted(doc)))


def test_trc_c5_verbose_adds_detail_without_relaxing_the_default():
    """--verbose is where detail goes, not where the contract is escaped (`TRC-C5`)."""
    from compass_pkg.terminal import Emitter

    def build(mode):
        e = Emitter(mode=mode)
        e.hand_off(outcome="4 checks failed", read="verification-report.md",
                   items=["a", "b", "c", "d", "e"],
                   detail=["why a matters", "why b matters"])
        return e.rendered()

    default, verbose = build("summary"), build("verbose")
    assert "why a matters" not in default, (
        "the default mode printed detail meant for --verbose")
    assert "why a matters" in verbose, ("--verbose did not add the detail")
    assert len(default.splitlines()) <= HANDOFF_LINES, (
        "the default mode broke its own budget:\n" + default)


def test_trc_c7_evidence_out_with_nothing_to_capture(tmp_path):
    """Accepted everywhere; writes nothing where there is nothing (`TRC-C7`).

    Not an error - a script passing the flag uniformly across a pipeline should
    not break on the verbs that happen to have nothing to say.
    """
    from compass_pkg.terminal import Emitter

    path = tmp_path / "capture.txt"
    e = Emitter(mode="summary", evidence_out=str(path))
    e.hand_off(outcome="nothing changed", read=None)
    assert not path.exists(), "a file was written for a verb that captured nothing"
    assert "nothing to capture" in e.rendered().lower(), (
        "the reader is not told why no file appeared:\n" + e.rendered())

    quiet = Emitter(mode="quiet", evidence_out=str(path))
    quiet.hand_off(outcome="nothing changed", read=None)
    assert quiet.rendered() == "", "--quiet printed the nothing-to-capture line"


def test_trc_c4_evidence_out_writes_the_capture(tmp_path):
    """Raw output is written and linked, never printed (`TRC-C4`)."""
    from compass_pkg.terminal import Emitter

    path = tmp_path / "capture.txt"
    raw = "===== 1283 passed, 7 skipped in 208.07s =====\n" + ("x" * 400)
    e = Emitter(mode="summary", evidence_out=str(path))
    e.report(summary=["the suite is green"], detail=["1283 passed"], capture=raw)

    written = path.read_text()
    assert raw in written, "the capture was not written to the path"
    assert written.endswith("\n"), (
        "the captured file does not end with a newline - it is a text file a "
        "person and a shell will both read")
    out = e.rendered()
    assert raw not in out, "the raw capture was printed as well as written"
    assert str(path) in out, (
        "the capture was written and not linked, so a reader cannot find it")


# ---------------------------------------------------------------------------
# Group A - the hand-off contract
# ---------------------------------------------------------------------------

def test_trc_a2_hand_off_states_outcome_artifact_and_reply():
    """Twelve lines of the wrong twelve things is not an improvement (`TRC-A2`)."""
    from compass_pkg.terminal import Emitter

    e = Emitter(mode="summary")
    e.hand_off(outcome="design ready for review",
               read=".compass/work/x/technical-design.md",
               reply="approve | request changes | ask a question")
    lines = e.rendered().splitlines()
    assert "design ready for review" in lines[0], (
        "the first line does not state the outcome:\n" + lines[0])
    body = "\n".join(lines)
    assert ".compass/work/x/technical-design.md" in body, "the artifact to read is missing"
    assert "approve" in body, "the reply being asked for is missing"


def test_trc_a3_hand_off_with_nothing_to_decide_is_shorter():
    """The common case - no invented decision, concern or reply (`TRC-A3`)."""
    from compass_pkg.terminal import Emitter

    e = Emitter(mode="summary")
    e.hand_off(outcome="the red is on record", read="evidence/red-TRC-A1.json")
    out = e.rendered()
    assert len(out.splitlines()) <= QUIET_HANDOFF_LINES, (
        "a hand-off with nothing to decide ran to %d lines:\n%s"
        % (len(out.splitlines()), out))
    assert "reply" not in out.lower(), (
        "a reply prompt was invented where nothing is being asked:\n" + out)

    # A NEXT STEP is rendered, and is not a reply. This field was declared in
    # the signature, written into the --json document, and never printed for a
    # person - so `approach evaluate` without --write said nothing about
    # nothing having been recorded. Nothing caught it because nothing asked.
    e2 = Emitter(mode="summary")
    e2.hand_off(outcome="nothing was recorded",
                next_step="re-run with --write to record it")
    step_out = e2.rendered()
    assert "re-run with --write" in step_out, (
        "a next step was accepted and never rendered:\n" + step_out)
    assert "reply" not in step_out.lower(), (
        "a next step was rendered as a decision the reader must answer:\n"
        + step_out)

    e3 = Emitter(mode="quiet")
    e3.hand_off(outcome="nothing was recorded",
                next_step="re-run with --write to record it")
    assert e3.rendered() == "", (
        "--quiet spoke for a next step, which is guidance rather than a "
        "decision being asked of anyone:\n" + e3.rendered())


def test_trc_a4_three_items_and_the_count_of_what_was_hidden():
    """A silent truncation reads as 'there were three' (`TRC-A4`).

    That is a claim the command never checked, and this repository has already
    found four checks that cleared by not looking.
    """
    from compass_pkg.terminal import Emitter

    e = Emitter(mode="summary")
    e.hand_off(outcome="7 findings", read="requirements-review.md",
               items=["one", "two", "three", "four", "five"],
               concerns=["c1", "c2", "c3", "c4"])
    out = e.rendered()
    assert "four" not in out.split("more")[0], "more than three items were shown"
    assert "2 more" in out or "and 2" in out, (
        "five items were cut to three and the reader is not told two were "
        "hidden, so the output claims there were three:\n" + out)
    assert "1 more" in out or "and 1" in out, (
        "four concerns were cut to three with no count of what was hidden:\n"
        + out)


def test_trc_a1_and_a5_a_hand_off_fits_one_screen_and_is_not_widened():
    """A line budget alone is met by joining lines (`TRC-A1` and `TRC-A5`
    together).

    Measured rather than supposed - `compass check`'s longest line today is 252
    characters, so 45 lines reflowed into 12 would satisfy a line count exactly
    and improve nothing.
    """
    from compass_pkg.terminal import Emitter

    long_path = ".compass/work/" + "a-long-directory-name/" * 8 + "technical-design.md"
    e = Emitter(mode="summary")
    e.hand_off(outcome="x" * 300, read=long_path,
               items=["z" * 300] * 5, concerns=["w" * 300] * 5,
               reply="approve | request changes")
    out = e.rendered()
    lines = out.splitlines()
    assert len(lines) <= HANDOFF_LINES, (
        "a hand-off ran to %d lines against a budget of %d:\n%s"
        % (len(lines), HANDOFF_LINES, out))

    # The path is exempt, and asserted rather than assumed - shortening a path
    # makes it unopenable, which fails at the thing the line exists for.
    assert long_path in out, (
        "the path was shortened to fit the width bound, so the reader cannot "
        "open it:\n" + out)

    prose = [l for l in lines if long_path not in l]
    too_wide = [l for l in prose if len(l) > MAX_WIDTH]
    assert not too_wide, (
        "%d prose line(s) exceed %d characters, so the line budget was met by "
        "making the lines longer:\n  %s"
        % (len(too_wide), MAX_WIDTH, "\n  ".join(l[:120] for l in too_wide)))


# ---------------------------------------------------------------------------
# Group B - the report contract
# ---------------------------------------------------------------------------

def test_trc_b1_report_opens_with_a_summary_and_b2_keeps_its_detail():
    """A report is not a hand-off (`TRC-B1` and `TRC-B2`).

    `compass calibration` and `compass terminology` exist to give detail.
    Cutting them to twelve lines would remove the reason to run them, so the
    hand-off budget must not reach them - and that has to be asserted, not
    assumed, because "twelve lines" is the kind of rule that spreads.
    """
    from compass_pkg.terminal import Emitter

    findings = ["finding %d" % i for i in range(40)]
    e = Emitter(mode="summary")
    e.report(summary=["40 findings across 12 files", "9 are new"],
             detail=findings)
    out = e.rendered()
    lines = out.splitlines()

    head = "\n".join(lines[:REPORT_SUMMARY_LINES])
    assert "40 findings" in head, (
        "the first %d lines do not state the finding, so a reader cannot stop "
        "there:\n%s" % (REPORT_SUMMARY_LINES, head))
    for f in findings:
        assert f in out, (
            "%r was dropped - the hand-off budget was applied to a report, "
            "which removes the reason to run it" % f)


# ---------------------------------------------------------------------------
# Group D - what compression must not cost
# ---------------------------------------------------------------------------

def test_trc_d1_compression_never_edits_the_inside_of_a_line():
    """An identifier is a key; attach its meaning, never
    delete the id (`TRC-D1`, ADR-017).

    A twelve-line budget creates constant pressure to drop `(RP-FLOOR-001,
    floor)` from a line to save room. The emitter drops whole lines and never
    edits the interior of one it keeps, so the pressure has nowhere to act.
    """
    from compass_pkg.terminal import Emitter

    # The fourth item is deliberately too long to fit. That is where the
    # pressure actually is: a short line keeps its id for free, and a line that
    # must be shortened is the one where dropping the trailing "(RP-...)" is
    # the tempting saving. A guard that only tests short lines never reaches
    # the case ADR-017 is about.
    items = ["Large work - full weight (RP-SHAPE-004, shape)",
             "Critical changes coordinate (RP-FLOOR-001, floor)",
             "Fitness checked before landing " + "and more " * 20
             + "(RP-REQUIRE-003, requirement)",
             "A fourth that will be cut (RP-ADV-001, advisory)"]
    e = Emitter(mode="summary")
    e.hand_off(outcome="initiative", read="delivery-approach.md", items=items)
    out = e.rendered()

    # A line is "kept" if any recognisable part of its prose reached the
    # output - the opening words, which shortening never touches.
    kept = [i for i in items if i.split(" (")[0][:25] in out]
    assert kept, "every item was dropped"
    assert any(len(i) > MAX_WIDTH for i in kept), (
        "every kept item was short enough to fit, so this ran without ever "
        "reaching the case it exists to check")

    for item in kept:
        rule_id = item.split("(")[-1].split(",")[0]
        assert rule_id in out, (
            "the line for %r was kept but its identifier %r was stripped to "
            "save room, which is the deletion ADR-017 forbids:\n%s"
            % (item.split(" (")[0][:40], rule_id, out))
        assert item.split(" (")[0][:25] in out, (
            "the identifier %r was kept but its meaning was stripped:\n%s"
            % (rule_id, out))


# ---------------------------------------------------------------------------
# Group E - the guard on the guard
# ---------------------------------------------------------------------------

def test_trc_e1_the_budget_guard_names_the_verb_it_caught():
    """An unactionable failure gets suppressed rather than fixed (`TRC-E1`)."""
    from compass_pkg.terminal import over_budget

    findings = over_budget({"issue dashboard": "\n".join("x" * 3 for _ in range(20))})
    assert findings, "a 20-line hand-off was not reported as over budget"
    text = " ".join(findings)
    assert "issue dashboard" in text, "the finding does not name the verb"
    assert "20" in text, "the finding does not give the actual line count"
    assert str(HANDOFF_LINES) in text, "the finding does not give the budget"


def test_trc_e2_the_budget_guard_can_fail_and_declines_an_empty_input():
    """The two ways a line-count check passes without looking (`TRC-E2`).

    A budget so high nothing breaches it, and an empty input that passes by
    having nothing to check. Both are asserted here because both have happened
    in this repository.
    """
    from compass_pkg.terminal import NOTHING_TO_CHECK, over_budget

    assert over_budget({"a verb": "\n".join(["line"] * (HANDOFF_LINES + 1))}), (
        "one line over the budget was not caught, so the budget is not being "
        "applied")
    assert not over_budget({"a verb": "\n".join(["line"] * HANDOFF_LINES)}), (
        "exactly the budget was reported as a breach")
    assert over_budget({"a verb": "x" * (MAX_WIDTH + 1)}), (
        "a single line of %d characters was not caught, so the width bound is "
        "not being applied and the budget can be met by joining lines"
        % (MAX_WIDTH + 1))
    assert over_budget({}) is NOTHING_TO_CHECK, (
        "an empty verb list reported a clean pass. A guard that is handed "
        "nothing and says 'all good' is how four checks in one release cleared "
        "without reading anything")


# ---------------------------------------------------------------------------
# U2 - `compass check` moves onto the contract
# ---------------------------------------------------------------------------
#
# The gate verdict is the most important hand-off in the pipeline, and today it
# spends 45 lines - 14 of them PASS lines nobody asked for - to say four things
# failed. Its failure format is four lines each: what failed, why it matters,
# how to fix it. Three failures is thirteen lines before the verdict, so the
# budget and that format cannot both survive untouched.
#
# The ruling, from the requirements review: `what` and `fix` stay in the
# default, `why` moves to --verbose. `fix` is what a person acts on; `why` is
# what convinces them it was worth acting on. When only one fits, keep the one
# that changes what they do next.

def _failing_issue(tmp_path):
    """A project whose issue fails several checks. Returns its root."""
    import yaml
    proj = tmp_path / "proj"
    (proj / "governance").mkdir(parents=True)
    for f in ("routing-policy.yml", "guardrails.yml"):
        (proj / "governance" / f).write_text(
            (REPO_ROOT / "governance" / f).read_text())
    td = proj / ".compass" / "work" / "t"
    td.mkdir(parents=True)
    (proj / ".compass" / "current-task").write_text("t\n")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    # No scenarios and no evidence: several checks fail, which is what this
    # needs. An issue that passes would exercise none of the failure path.
    (td / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "t", "created": "2026-08-24",
        "status": "active",
        "assessment": {"risk": "cross-cutting", "familiarity": "brownfield-mapped",
                       "size": "large", "goal": "delivery", "role": "engineer",
                       "labels": []},
        "delivery_approach": "initiative", "stages": {}, "gates": [],
        "evidence": [], "scenarios": [], "changed_files": []}, sort_keys=False))
    return proj


def _run_check(proj, *flags):
    r = subprocess.run([sys.executable, str(CLI), "check", *flags],
                       cwd=str(proj), capture_output=True, text=True, timeout=120)
    return r


def test_trc_a6_check_verdict_fits_and_keeps_its_guidance(tmp_path):
    """The gate verdict on one screen (`TRC-A6` with `TRC-A1`, `A2` and `A4`)."""
    proj = _failing_issue(tmp_path)
    r = _run_check(proj)
    out = r.stdout
    lines = [l for l in out.splitlines()]

    assert r.returncode != 0, "the fixture was meant to fail checks:\n" + out
    assert len(lines) <= HANDOFF_LINES, (
        "the gate verdict ran to %d lines against a budget of %d:\n%s"
        % (len(lines), HANDOFF_LINES, out))
    assert "FAIL" in lines[0], (
        "the first line does not state the outcome:\n" + lines[0])

    # `fix` survives; `why` moves to --verbose. Both asserted, because
    # "compressed" must not quietly mean "the guidance is gone".
    assert "fix" in out.lower(), (
        "the default view dropped the fix instruction, which is the part a "
        "person acts on:\n" + out)
    assert "why" not in out.lower(), (
        "the default view still carries the `why` text that was ruled to "
        "--verbose, so nothing was actually compressed:\n" + out)

    # PASS lines are the bulk of what a reader does not need.
    assert "PASS " not in out, (
        "individual PASS lines are still in the default view - they were 14 of "
        "the original 45 lines:\n" + out)

    # A truncation with no count reads as "there were three".
    # Lines that START with FAIL, not every occurrence of the word - the
    # verdict line begins "FAIL - 4 of 17 ..." and counting substrings made
    # this read one higher than the number of failures actually shown.
    shown = len([l for l in lines if l.startswith("FAIL ") and " - " not in l[:12]])
    assert shown <= 3, (
        "more than three failures were shown (%d):\n%s" % (shown, out))
    assert shown >= 1, ("no failure was shown at all:\n" + out)
    assert "more" in out.lower(), (
        "failures were cut to three with no count of what was hidden:\n" + out)

    # THE NUMBER IN THE VERDICT MUST EQUAL WHAT THE PAGE ACCOUNTS FOR.
    # The verdict counted check RUNS while the list below it was deduplicated
    # by name, so a header saying "5 failed" sat above three shown plus one
    # hidden - and when the duplicate happened to fall among the hidden ones,
    # the "... and N more" line vanished and a failure disappeared with nothing
    # saying anything had been cut. Asserting the arithmetic is what catches
    # that; asserting only that a marker exists does not.
    import re as _re
    stated = int(_re.search(r"FAIL - (\d+) of \d+", lines[0]).group(1))
    hidden_line = [l for l in lines if l.startswith("... and")]
    hidden = int(_re.search(r"and (\d+) more", hidden_line[0]).group(1)) if hidden_line else 0
    assert stated == shown + hidden, (
        "the verdict says %d check(s) failed, and the page accounts for %d "
        "(%d shown + %d hidden). Two numbers describing the same thing must "
        "come from the same set:\n%s" % (stated, shown + hidden, shown, hidden, out))


def test_trc_c5_check_verbose_keeps_everything(tmp_path):
    """--verbose is where the detail goes, not where the budget is lost (`TRC-C5`)."""
    proj = _failing_issue(tmp_path)
    verbose = _run_check(proj, "--verbose").stdout
    default = _run_check(proj).stdout

    assert "why" in verbose.lower(), "--verbose dropped the reason it matters"
    assert "PASS " in verbose, "--verbose dropped the passing checks"
    assert len(verbose.splitlines()) > len(default.splitlines()), (
        "--verbose produced no more than the default view")
    assert len(default.splitlines()) <= HANDOFF_LINES, (
        "the default view broke its budget:\n" + default)


def test_trc_c2_check_is_silent_when_it_passes(tmp_path):
    """--quiet on a clean run says nothing; the exit code carries it (`TRC-C2`)."""
    import yaml
    proj = _failing_issue(tmp_path)
    # A spike concludes with evidence rather than the delivery guardrails, so
    # it is the cheapest issue shape that can genuinely pass.
    td = proj / ".compass" / "work" / "t"
    manifest = yaml.safe_load((td / "manifest.yml").read_text())
    manifest["delivery_approach"] = "spike"
    manifest["evidence"] = [{"id": "EV-1", "type": "spike-conclusion",
                          "path": "evidence/conclusion.md",
                          "decision": "discard"}]
    (td / "manifest.yml").write_text(yaml.safe_dump(manifest, sort_keys=False))

    r = _run_check(proj, "--quiet")
    assert r.returncode == 0, (
        "the fixture was meant to pass:\n" + r.stdout + r.stderr)
    assert r.stdout.strip() == "", (
        "--quiet printed on a clean run:\n" + r.stdout)


def test_trc_c3_check_emits_json(tmp_path):
    """--json is one document and carries no prose (`TRC-C3`)."""
    proj = _failing_issue(tmp_path)
    r = _run_check(proj, "--json")
    doc = json.loads(r.stdout)
    assert doc["failed"] >= 1, doc
    assert isinstance(doc["checks"], list) and doc["checks"], doc
    one = doc["checks"][0]
    for key in ("name", "guardrail", "status", "detail"):
        assert key in one, "a check result is missing %r: %s" % (key, one)


def test_trc_d1_check_keeps_every_identifier(tmp_path):
    """The compressed verdict still names each check (`TRC-D1`, ADR-017).

    A check's name IS its identifier. Compressing the verdict must not leave a
    reader with "3 checks failed" and no way to know which.
    """
    proj = _failing_issue(tmp_path)
    out = _run_check(proj).stdout
    # EXCLUDING the verdict headline, which begins "FAIL - 5 of 17 ...". Its
    # own hyphen satisfied the `"-" in name` check below, so replacing every
    # per-failure line with "3 check(s) failed. Run with --verbose." - the
    # exact output this test forbids - passed. The two sibling tests already
    # carried this exclusion; this one did not.
    named = [l for l in out.splitlines()
             if l.strip().startswith("FAIL ") and " - " not in l[:12]]
    assert named, (
        "the verdict says checks failed and names none of them, so a reader "
        "cannot act on it:\n" + out)
    for line in named:
        name = line.split("FAIL ", 1)[1].split(":")[0].strip()
        assert name and "-" in name, (
            "a failure line does not carry the check's identifier: " + line)


def test_trc_a6_every_guidance_entry_has_a_one_line_fix():
    """The short fix is written, not derived (`TRC-A6`).

    The full `fix` strings run to 320 characters. Deriving a short form by
    cutting at the first sentence would produce something nobody read before it
    shipped, and it would change silently when the long text was edited. Each
    is written out, and a missing one fails rather than falling back.
    """
    from compass_pkg.check_cmd import CHECK_FNS, CHECK_GUIDANCE

    assert CHECK_GUIDANCE, "there is no guidance table to check"
    # Iterates CHECK_FNS, the checks that can actually FAIL - not
    # CHECK_GUIDANCE, which is the answer sheet. Walking the guidance table
    # meant a check with no entry at all was invisible to a test whose message
    # claims it covers them, and five of eighteen had none: their failures
    # printed with no `fix:` line under them.
    missing, too_long = [], []
    for name in sorted(CHECK_FNS):
        g = CHECK_GUIDANCE.get(name) or {}
        do = g.get("do")
        if not do:
            missing.append(name)
        elif len(do) > 90:
            too_long.append("%s: %d chars" % (name, len(do)))
    assert not missing, (
        "these checks have no one-line fix, so their failure in the default "
        "view would either overflow the budget or say nothing actionable:\n  "
        + "\n  ".join(missing))
    assert not too_long, (
        "these one-line fixes do not fit a line:\n  " + "\n  ".join(too_long))


def test_trc_a4_a_check_named_twice_is_not_listed_twice(tmp_path):
    """The hidden list names only what was not shown (`TRC-A4`).

    Found by reading the output, not by a test. Several checks are listed under
    more than one guardrail - `scenario-has-id-and-intent` runs under both
    "acceptance defined before it is built" and "traceability holds" - so a
    failing run produces two rows with the same name. The first version showed
    it in the top three AND named it again in "... and 2 more", which reads as
    the tool being confused about its own findings.
    """
    proj = _failing_issue(tmp_path)
    out = _run_check(proj).stdout
    shown = {l.split("FAIL ", 1)[1].split(":")[0].strip()
             for l in out.splitlines()
             if l.startswith("FAIL ") and " - " not in l[:12]}
    tail = [l for l in out.splitlines() if l.startswith("... and")]
    assert tail, "the fixture did not produce a hidden-count line:\n" + out
    for name in shown:
        assert name not in tail[0], (
            "%r was shown in full and named again as hidden:\n%s"
            % (name, out))


# ---------------------------------------------------------------------------
# U3 - the reports
# ---------------------------------------------------------------------------
#
# A report is run deliberately to GET detail, so the hand-off budget must not
# reach it. What it owes a reader is a summary they can stop at.
#
# These are written over EVERY verb that declares itself a report rather than
# over a list of four names, so a fifth report is covered the day it is
# declared instead of the day somebody remembers to add it here. The names are
# discovered from the parser, which is also where the declaration lives.

def _report_verbs():
    """Every verb that declares itself a report, from the parser tree."""
    return sorted(path for path, p in _leaf_parsers().items()
                  if p.get_default("output_kind") == "report"
                  and not path.startswith("_"))


# The reports that read an issue tree and produce enough output to be worth
# testing. `migrate` and the linters need an argument or a broken tree to say
# anything, so they are exercised by their own suites.
_LIVE_REPORTS = ["retro", "flow", "terminology", "analyze"]


@pytest.fixture(scope="module")
def report_project(tmp_path_factory):
    """A project with enough issues for a report to have something to report.

    These tests originally ran the verbs against REPO_ROOT itself, which has
    140 issues - in the author's working tree. `.compass/work/` is GITIGNORED,
    so a clean clone has none, and every one of these tests passed locally and
    failed in CI against "no issues found". A test that reads untracked local
    state is testing the machine it runs on.
    """
    import yaml

    proj = tmp_path_factory.mktemp("reports")
    (proj / "governance").mkdir()
    # terminology.yml too: `compass terminology` reads the project's copy, and
    # without it the verb says "not found" and these tests would assert against
    # an error message instead of a glossary.
    for f in ("routing-policy.yml", "guardrails.yml", "terminology.yml"):
        (proj / "governance" / f).write_text(
            (REPO_ROOT / "governance" / f).read_text())
    work = proj / ".compass" / "work"
    work.mkdir(parents=True)
    (proj / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n")

    # Enough issues, in enough states, that `flow` has more to say than a
    # hand-off budget would allow - which is the thing `TRC-B2` asserts.
    states = ["active", "queued", "queued", "parked", "landed", "abandoned"]
    for i in range(18):
        slug = "issue-%02d" % i
        d = work / slug
        d.mkdir()
        (d / "manifest.yml").write_text(yaml.safe_dump({
            "schema_version": "2.0", "task": slug, "created": "2026-08-24",
            "status": states[i % len(states)],
            "assessment": {"risk": "contained",
                           "familiarity": "brownfield-mapped",
                           "size": "standard", "goal": "delivery",
                           "role": "engineer", "labels": []},
            "delivery_approach": "feature", "stages": {"specify": "full"},
            "gates": [], "evidence": [], "scenarios": [], "changed_files": [],
        }, sort_keys=False))
    # `analyze` reads the current issue's artifacts, so one issue needs them.
    (proj / ".compass" / "current-task").write_text("issue-00\n")
    (work / "issue-00" / "delivery-approach.md").write_text("# Delivery approach\n")
    (work / "issue-00" / "acceptance-criteria.md").write_text(
        "# Spec\n\n## Summary\n\n**Goal:** something\n")
    return proj


def _repo_run(project, *argv):
    """Run a verb against the fixture project."""
    return subprocess.run([sys.executable, str(CLI), *argv],
                          cwd=str(project), capture_output=True, text=True,
                          timeout=180)


def test_trc_b1_every_live_report_opens_with_a_summary(report_project):
    """The first five lines say what was found (`TRC-B1`).

    A reader who has to scan 157 lines to learn there is nothing to do has been
    failed by the report.
    """
    for verb in _LIVE_REPORTS:
        r = _repo_run(report_project, verb)
        out = r.stdout
        assert out.strip(), "`compass %s` printed nothing" % verb
        # ONLY the summary: the lines before the first blank one. Reading the
        # first five lines of the whole report caught a section header like
        # "  IN PROGRESS (1)" instead - so a mutation that stripped every
        # number from the summary still passed, and this checked the detail
        # while claiming to check the summary.
        head = []
        for line in out.splitlines():
            if not line.strip():
                break
            head.append(line)
        assert head, "`compass %s` opens with blank lines" % verb
        assert len(head) <= REPORT_SUMMARY_LINES, (
            "`compass %s` opens with a %d-line summary, over the %d-line "
            "budget:\n%s" % (verb, len(head), REPORT_SUMMARY_LINES,
                             "\n".join(head)))
        # A summary states a quantity. Without one it is a title, and a title
        # is not something a reader can stop at.
        assert any(c.isdigit() for l in head for c in l), (
            "`compass %s` opens with no number in its first %d lines, so a "
            "reader cannot tell from the summary whether the detail needs "
            "reading:\n%s" % (verb, REPORT_SUMMARY_LINES, "\n".join(head)))


def test_trc_b2_a_report_keeps_all_of_its_detail(report_project):
    """The hand-off budget is not applied to a report (`TRC-B2`).

    Asserted against the LONGEST report this repository produces, because a
    budget applied by accident would show up there first.
    """
    default = _repo_run(report_project, "flow").stdout
    verbose = _repo_run(report_project, "flow", "--verbose").stdout
    assert len(default.splitlines()) > HANDOFF_LINES, (
        "`compass flow` was cut to a hand-off budget - it lists every "
        "issue, and cutting it to %d lines removes the reason to run it:\n%s"
        % (HANDOFF_LINES, default))
    assert len(verbose.splitlines()) >= len(default.splitlines()), (
        "--verbose produced less than the default view")


def test_trc_c2_a_report_under_quiet_is_the_summary_only(report_project):
    """--quiet keeps the finding, drops the detail (`TRC-C2` for a report).

    Not silence. A person who asked for a report asked for an answer; --quiet
    says they want it short, not that they want nothing.
    """
    for verb in _LIVE_REPORTS:
        quiet = _repo_run(report_project, verb, "--quiet").stdout
        default = _repo_run(report_project, verb).stdout
        assert quiet.strip(), (
            "`compass %s --quiet` printed nothing, so the answer the reader "
            "asked for was thrown away" % verb)
        assert len(quiet.splitlines()) <= REPORT_SUMMARY_LINES, (
            "`compass %s --quiet` ran to %d lines:\n%s"
            % (verb, len(quiet.splitlines()), quiet))
        assert len(quiet.splitlines()) < len(default.splitlines()), (
            "`compass %s --quiet` was no shorter than the default" % verb)


def test_trc_c3_every_live_report_emits_json(report_project):
    """--json is one document and carries no prose (`TRC-C3`)."""
    for verb in _LIVE_REPORTS:
        r = _repo_run(report_project, verb, "--json")
        try:
            doc = json.loads(r.stdout)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                "`compass %s --json` did not emit one JSON document (%s):\n%s"
                % (verb, exc, r.stdout[:400]))
        assert isinstance(doc, dict) and doc, (
            "`compass %s --json` emitted an empty document" % verb)


def test_trc_c6_the_report_list_is_not_empty():
    """Something actually declares itself a report - the other half of `TRC-C6`.

    If nothing did, every test above would iterate an empty list and pass
    without checking anything - and this repository has found four checks that
    cleared exactly that way.
    """
    verbs = _report_verbs()
    assert len(verbs) >= 4, (
        "only %d verbs declare themselves reports: %s" % (len(verbs), verbs))
    for v in _LIVE_REPORTS:
        assert v in verbs, (
            "`%s` is exercised by the tests above but no longer declares "
            "itself a report, so those tests are checking a hand-off against "
            "a report's contract. Declared reports: %s" % (v, verbs))


# ---------------------------------------------------------------------------
# U4 - the long tail, measured against the contract for real
# ---------------------------------------------------------------------------
#
# Everything above tests the emitter, or one verb at a time. Nothing yet runs
# EVERY hand-off verb and measures what actually reached the terminal, which is
# what `TRC-A1` and `TRC-A3` are about.
#
# The table below is the argv each verb needs to do its job. A verb
# that is in the parser and not in the table fails the coverage guard, so the
# next verb added has to be measured rather than quietly missed.

# Verbs excluded from the run, each with the reason. Kept short and named -
# an unexplained exclusion is how a guard stops covering things.
_TAIL_EXEMPT = {
    "_friction-capture": "private, and writes to the manifest as a side effect",
    "_migrate-archive": "private, and rewrites a whole work tree",
    "_derive-system-spec": "private, and writes a tracked doc",
    "_derive-glossary": "private, and writes a tracked doc",
    "migrate": "rewrites a work tree; its own suite covers its output",
    "ship-commit": "writes a git commit",
    "check": "measured by its own tests above, on a failing issue",
    "policy lint": "needs a governance tree of its own to say anything",
    "issue lint": "needs a malformed manifest to say anything",
    # Prints one bare path on stdout and nothing else, on purpose: the two
    # hooks read it in a command substitution, and a hand-off tail in the
    # middle of that would end up in the variable.
    "issue artifact-path": "prints a bare path for a shell caller to consume",
    "issue subtask add": "needs a git repository and a brief file the fixture does not create; test_subtask_record.py runs it, without measuring its output against this contract",
    "issue subtask update": "needs a recorded subtask the fixture does not create; test_subtask_record.py runs it, without measuring its output against this contract",
    "issue subtask package": "needs a git history to diff, which the fixture does not have; test_subtask_record.py runs it, without measuring its output against this contract",
    "plan lint": "needs a design with placeholders to say anything",
    "next": "advisory pointer; its own suite covers it",
    "rework-scan": "its own suite covers it",
    "follow-up resolve": "needs an owed follow-up planted first",
    "bdd verify": "needs a project BDD runner wired",
    "acceptance record": "needs an acceptance already started",
    "analyze": "a report, measured above",
    "retro": "a report, measured above",
    "flow": "a report, measured above",
    "terminology": "a report, measured above",
    # These say WHY the verb is not run here, not what kind it is - two of
    # these reasons used to say "a report" while `cli/compass` declared both
    # hand-offs, and nothing caught the contradiction.
    "ci": "runs the whole mechanical suite over every issue; too slow here, and "
          "its own suite covers it",
    "issue receipt": "renders a landed issue's record; needs a landed issue with "
                     "cleared gates to say anything",
}

_TAIL_ARGV = {
    # No prerequisites at all, which is the point of the verb: it runs before
    # a project exists. In this fixture one already does, so it takes the
    # already-initialised path.
    "init": ["init"],
    "approach evaluate": ["approach", "evaluate"],
    "issue dashboard": ["issue", "dashboard"],
    "issue set-status": ["issue", "set-status", "active"],
    "issue subtask next": ["issue", "subtask", "next"],
    # The artifact set is computed by the evaluator, so the fixture runs
    # `approach evaluate --write` first and this names a document the
    # assessment actually earned.
    "issue artifact": ["issue", "artifact", "acceptance-criteria",
                       "--status", "draft"],
    "scenario add": ["scenario", "add", "TRC-9", "--title", "a new one",
                     "--intent", "INT-1"],
    "changed-file add": ["changed-file", "add", "src/a.py", "--scenario", "TRC-1"],
    "evidence add": ["evidence", "add", "EV-9", "--type", "artifact",
                     "--path", "manifest.yml"],
    # The gate's accepted evidence type is checked at write time, so the
    # record this points at has to be a test-run, not the artifact above.
    "gate pass": ["gate", "pass", "verify.correctness", "--evidence", "EV-T"],
    "adr new": ["adr", "new", "a decision worth recording"],
    "bdd extract": ["bdd", "extract"],
    "acceptance start": ["acceptance", "start", "--kind", "validation",
                         "--", "true"],
    "tdd-red": ["tdd-red", "--scenario", "TRC-1", "--", "false"],
    "tdd-green": ["tdd-green", "--scenario", "TRC-1", "--", "true"],
}


def _with_flags(argv, *flags):
    """Insert mode flags BEFORE any `--`.

    `tdd-red -- false --json` puts `--json` inside the command being run, not
    on the verb. That is correct behaviour and a real trap for anyone scripting
    these verbs, so the tests place the flags where a person would have to.
    """
    argv = list(argv)
    if "--" in argv:
        i = argv.index("--")
        return argv[:i] + list(flags) + argv[i:]
    return argv + list(flags)


@pytest.fixture
def tail_project(tmp_path):
    """A project where every verb in the table can actually do its job."""
    import yaml

    proj = tmp_path / "tail"
    (proj / "governance").mkdir(parents=True)
    for f in ("routing-policy.yml", "guardrails.yml", "terminology.yml"):
        (proj / "governance" / f).write_text(
            (REPO_ROOT / "governance" / f).read_text())
    td = proj / ".compass" / "work" / "t"
    (td / "evidence").mkdir(parents=True)
    (proj / ".compass" / "current-task").write_text("t\n")
    (proj / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n")
    (td / "acceptance-criteria.md").write_text(
        "# Spec\n\n## Summary\n\n**Goal:** a thing\n\n"
        "### Scenario: a thing happens\n"
        "<!-- traceability id: TRC-1 - serves: INT-1 -->\n\n"
        "```gherkin\nScenario: a thing happens\n  Given a start\n"
        "  When it runs\n  Then it works\n```\n")
    (td / "delivery-approach.md").write_text("# Delivery approach - t\n")
    # `tdd-green` is measured with `--scenario` `TRC-1`, and a bound green needs
    # a red for the same binding. Written here so the verb reaches the output
    # this file is about rather than being refused before it prints anything.
    write_red_record(td, "TRC-1")
    (td / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "t", "created": "2026-08-24",
        "status": "active",
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "standard", "goal": "delivery",
                       "role": "engineer", "labels": []},
        "delivery_approach": "feature", "stages": {"specify": "full"},
        "gates": [{"id": "verify.correctness", "status": "pending",
                   "evidence": []}],
        "evidence": [], "scenarios": [{"id": "TRC-1", "intent": "INT-1",
                                       "title": "a thing happens",
                                       "tests": ["tests/t.py::a"]}],
        "changed_files": [],
    }, sort_keys=False))
    # A test-run record, because `gate pass verify.correctness` checks the
    # evidence TYPE at write time and refuses an artifact.
    (td / "evidence" / "green.json").write_text(
        '{"command": "true", "exit_code": 0}')
    subprocess.run([sys.executable, str(CLI), "evidence", "add", "EV-T",
                    "--type", "test-run", "--path", "evidence/green.json"],
                   cwd=str(proj), capture_output=True, text=True, timeout=60)
    # The artifact set is a routing output, so it has to be computed before a
    # document in it can have its status set.
    subprocess.run([sys.executable, str(CLI), "approach", "evaluate", "--write"],
                   cwd=str(proj), capture_output=True, text=True, timeout=60)
    return proj


def test_trc_c1_the_tail_table_covers_every_hand_off_verb():
    """A verb in the parser is measured, or exempt with a reason (`TRC-C1`).

    Without this, adding a verb quietly leaves it unmeasured, which is how
    this surface drifted in the first place.
    """
    hand_offs = {path for path, p in _leaf_parsers().items()
                 if p.get_default("output_kind") == "hand-off"}
    unmeasured = hand_offs - set(_TAIL_ARGV) - set(_TAIL_EXEMPT)
    assert not unmeasured, (
        "these hand-off verbs are neither measured against the contract nor "
        "exempt with a reason:\n  " + "\n  ".join(sorted(unmeasured)))
    assert len(_TAIL_ARGV) >= 10, (
        "only %d verbs are actually run, so most of this file's coverage is "
        "exemptions" % len(_TAIL_ARGV))


def test_trc_a1_and_a3_every_hand_off_verb_fits_its_budget(tail_project):
    """What actually reaches the terminal, measured (`TRC-A1` and `TRC-A3`).

    Each verb runs for real. A verb that exits non-zero is a FAILURE of this
    test, not a skip - a table entry with the wrong arguments would otherwise
    quietly stop measuring that verb.
    """
    from compass_pkg.terminal import over_budget

    outputs, broken = {}, []
    for verb, argv in sorted(_TAIL_ARGV.items()):
        r = subprocess.run([sys.executable, str(CLI), *argv],
                           cwd=str(tail_project), capture_output=True,
                           text=True, timeout=120)
        if r.returncode != 0:
            broken.append("%s -> exit %d: %s"
                          % (verb, r.returncode,
                             (r.stderr or r.stdout).strip().splitlines()[-1:]))
            continue
        outputs[verb] = r.stdout
    assert not broken, (
        "these verbs could not run, so they were not measured. Fix the argv in "
        "_TAIL_ARGV - a verb that cannot run is not a verb that passed:\n  "
        + "\n  ".join(broken))

    findings = over_budget(outputs)
    assert findings is not NOTHING_TO_CHECK_SENTINEL(), (
        "no verb output was collected at all")
    assert not findings, (
        "these verbs printed past the contract:\n  " + "\n  ".join(findings))


def NOTHING_TO_CHECK_SENTINEL():
    from compass_pkg.terminal import NOTHING_TO_CHECK
    return NOTHING_TO_CHECK


def test_trc_c2_the_tail_is_silent_under_quiet(tail_project):
    """A verb with nothing to decide prints nothing under --quiet (`TRC-C2`)."""
    noisy, broken = [], []
    for verb, argv in sorted(_TAIL_ARGV.items()):
        r = subprocess.run([sys.executable, str(CLI), *_with_flags(argv, "--quiet")],
                           cwd=str(tail_project), capture_output=True,
                           text=True, timeout=120)
        # A non-zero exit is a FAILURE, not a skip. Skipping it meant a verb
        # could ignore the flag AND fail, and be counted as fine - the sibling
        # test at the top of this group states that rule and enforces it; these
        # two broke it.
        if r.returncode != 0:
            broken.append("%s -> exit %d" % (verb, r.returncode))
        elif r.stdout.strip():
            noisy.append("%s printed %d line(s)"
                         % (verb, len(r.stdout.splitlines())))
    assert not broken, (
        "these verbs could not run under --quiet, so they were not measured:\n  "
        + "\n  ".join(broken))
    assert not noisy, (
        "--quiet is accepted by these verbs and ignored, which is worse than "
        "not having the flag:\n  " + "\n  ".join(noisy))


def test_trc_c3_the_tail_emits_json(tail_project):
    """--json is one document per verb, and carries no prose (`TRC-C3`)."""
    bad, broken = [], []
    for verb, argv in sorted(_TAIL_ARGV.items()):
        r = subprocess.run([sys.executable, str(CLI), *_with_flags(argv, "--json")],
                           cwd=str(tail_project), capture_output=True,
                           text=True, timeout=120)
        # Same rule as above: a non-zero exit is a failure of this test. `continue`
        # meant a verb printing "this is definitely not JSON" and exiting 1 passed.
        if r.returncode != 0:
            broken.append("%s -> exit %d" % (verb, r.returncode))
            continue
        try:
            doc = json.loads(r.stdout)
        except json.JSONDecodeError as exc:
            bad.append("%s: %s -- %r" % (verb, exc, r.stdout[:120]))
            continue
        if not isinstance(doc, dict) or not doc:
            bad.append("%s: not a non-empty object" % verb)
    assert not broken, (
        "these verbs could not run under --json, so they were not measured:\n  "
        + "\n  ".join(broken))
    assert not bad, (
        "--json is accepted by these verbs and does not produce one JSON "
        "document:\n  " + "\n  ".join(bad))
