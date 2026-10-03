#!/usr/bin/env python3
# =============================================================================
# compass - the terminal output contract
# =============================================================================
# Every line a person reads comes through here. A verb passes the PIECES of
# what it wants to say - the outcome, the artifact to read, the items, the
# concerns - and this module decides how they render in the mode the user
# asked for.
#
# WHY PIECES AND NOT STRINGS. A filter that wraps stdout and counts lines after
# the fact can only truncate. It cannot re-order, cap a list at three and say
# how many were hidden, move a line to --verbose, or emit JSON, because you
# cannot recover structure from prose that has already been flattened.
#
# TWO CONTRACTS, NOT ONE RULE.
#   hand-off - a verb that ends a stage or renders a verdict. One screen.
#   report   - a verb somebody runs deliberately to GET detail, like
#              `calibration` or `terminology`. Keeps every finding, but opens
#              with a summary they can stop at. Cutting a report to twelve
#              lines removes the reason to run it.
#
# DEPENDENCY: none. This module is Python 3 standard library only - json, os,
# sys and re. It is the one CLI module that touches no third-party code at all;
# the YAML parser the rest of the package uses travels inside the plugin, so
# there is nothing to install either way.
#
# ADR-017 IS ENFORCED STRUCTURALLY, NOT BY INSTRUCTION. An identifier is a key,
# not jargon: attach its meaning, never delete the id. A twelve-line budget
# creates constant pressure to drop "(RP-FLOOR-001, floor)" from a line to save
# room. So this module drops WHOLE LINES and has no code path that edits the
# interior of a line it keeps - the pressure has nowhere to act.
# =============================================================================
"""Rendering what a person reads, in the mode they asked for."""
from __future__ import annotations

import json
import os
import re
import sys

# The budget, and why each number is what it is.
HANDOFF_LINES = 12       # where a reader stops scrolling
QUIET_HANDOFF_LINES = 5  # a hand-off with nothing to decide
REPORT_SUMMARY_LINES = 5
MAX_WIDTH = 100          # a line budget alone is met by joining lines
MAX_ITEMS = 3            # "at most three key choices and three concerns"

MODES = ("quiet", "summary", "verbose", "json")
DEFAULT_MODE = "summary"

MODE_FLAGS = ("--quiet", "--summary", "--verbose", "--json", "--evidence-out")


class _NothingToCheckHere:
    """A guard that was handed nothing. Not a pass.

    Truthy would make an empty input clear the guard; falsey would make it read
    as a breach. It is neither, and callers compare against the sentinel.

    DELIBERATELY DISTINCT from the sentinel in check_results.py, and named and
    repr'd so the two cannot be mistaken for each other. That one is TRUTHY -
    it subclasses int, because a check function returns it where a pass would
    go. This one is FALSEY, because `over_budget` returns a list of findings
    and an empty result must not read as findings.
    """

    def __bool__(self):
        return False

    def __repr__(self):
        return "NOTHING_TO_CHECK(terminal)"


NOTHING_TO_CHECK = _NothingToCheckHere()


def add_mode_flags(parser):
    """Attach the five mode flags to one leaf parser.

    A flag the verb ALREADY declares is left alone. `approach evaluate --json`
    shipped before this contract existed and sets its own attribute; ADR-006
    makes that public surface, so the walk defers to it rather than colliding
    with it. `resolve_mode` reads both spellings, so the verb still ends up in
    JSON mode either way.
    """
    have = {o for a in parser._actions for o in a.option_strings}
    g = parser.add_argument_group("output")
    if "--quiet" not in have:
        g.add_argument("--quiet", dest="_mode", action="store_const", const="quiet",
                       help="errors and the decision hand-off only")
    if "--summary" not in have:
        g.add_argument("--summary", dest="_mode", action="store_const",
                       const="summary", help="the default human view")
    if "--verbose" not in have:
        g.add_argument("--verbose", dest="_mode", action="store_const",
                       const="verbose", help="diagnostic detail")
    if "--json" not in have:
        g.add_argument("--json", dest="_mode", action="store_const", const="json",
                       help="machine consumer")
    if "--evidence-out" not in have:
        g.add_argument("--evidence-out", metavar="PATH",
                       help="write raw capture to PATH instead of printing it")
    return parser


def attach_mode_flags(parser):
    """Add the five flags to every LEAF parser in the tree, recursively.

    Recursion is the whole job. The tree has thirteen nested subparser groups -
    `issue`, `bdd`, `gate`, `evidence`, `adr` and eight more - and the flags
    belong on every leaf. A walk that handles only the top level attaches the
    flags to `issue` and misses `issue dashboard` entirely, which is how a
    guard over this tree passes while checking a fraction of it.

    Returns the number of leaves reached, so a caller can tell "walked the
    tree" from "found nothing".

    THE OUTPUT KIND IS NOT SET HERE, and that asymmetry is deliberate. A flag
    must arrive without the verb's author doing anything, because forgetting it
    would make the flag silently useless on that verb. The hand-off/report
    declaration is the opposite: it is written at each `set_defaults(func=...)`
    so that a new verb which forgets it FAILS, rather than being defaulted into
    whichever contract was easiest. Deriving it from a list here would mean no
    verb could ever lack one, and that guard would be a check that cannot
    fail.
    """
    import argparse

    reached = 0

    def walk(p):
        nonlocal reached
        subs = [a for a in p._actions
                if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            add_mode_flags(p)
            reached += 1
            return
        for action in subs:
            for child in action.choices.values():
                walk(child)

    walk(parser)
    return reached


def resolve_mode(args):
    """The mode a verb should render in, from the parsed arguments.

    Reads the verb's own `--json` too, for the one verb that shipped with it
    before this contract existed. Its attribute is `json`, not `_mode`.
    """
    mode = getattr(args, "_mode", None)
    if mode in MODES:
        return mode
    if getattr(args, "json", False):
        return "json"
    return DEFAULT_MODE


def emitter_for(args):
    """The Emitter a verb should use, built from its own parsed arguments."""
    return Emitter(mode=resolve_mode(args),
                   evidence_out=getattr(args, "evidence_out", None))


_ID_TAIL = re.compile(r"\s*\(([A-Z][A-Z0-9-]*[0-9][^)]*)\)\s*$")


def _path_line(prefix, path):
    """A path is printed WHOLE, however long it is.

    Shortening a path makes it unopenable, and a link a reader cannot follow is
    worse than a line that is merely wide - one fails at the thing it exists
    for, the other is untidy. The width guard knows about this and exempts a
    line whose overflow is a single unbreakable token.
    """
    return "%s%s" % (prefix, relative_to_project(str(path).strip()))


def write_capture(path, capture):
    """Write raw output to PATH, so the terminal can link it instead.

    Errors are turned into CompassError, so a bad path such as
    `--evidence-out /nope/x.txt` gives a message, not a traceback.
    """
    from compass_pkg.core import CompassError

    try:
        d = os.path.dirname(os.path.abspath(path))
        if d and not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(capture if capture.endswith("\n") else capture + "\n")
    except OSError as exc:
        raise CompassError("could not write --evidence-out %s: %s" % (path, exc))
    return path


def _fit(text, prefix=""):
    """One line, never wider than the budget, with its identifier kept.

    Shortening happens to a single field's VALUE as it becomes a line, before
    anything is assembled - the compression step never edits a line it keeps.

    ADR-017 applies here too, and this is where it would quietly break. A rule
    line carries its id at the end - "Large work - full weight, plausibly
    parallel (RP-SHAPE-004, shape)". Cutting that to fit would drop the id and
    keep the prose, which is exactly the deletion the decision forbids. So a
    trailing identifier is lifted off, the prose is shortened, and the id is
    put back.
    """
    text = " ".join(str(text).split())
    room = MAX_WIDTH - len(prefix)
    if len(text) <= room:
        return prefix + text

    # A line that is long only because it carries one unbreakable token - a
    # path or a URL - is printed WHOLE. Shortening it makes the link
    # unopenable, which fails at the thing the line exists for.
    #
    # This check lives here, not at the call sites: the hand-off's Read line,
    # the report's summary, and the one-line `say()` all need it, and a rule
    # each caller must remember is a rule the next caller forgets.
    if _is_unbreakable(prefix + text, MAX_WIDTH):
        return prefix + text

    m = _ID_TAIL.search(text)
    if m:
        tail = " (%s)" % m.group(1)
        body = text[:m.start()].rstrip()
        keep = room - len(tail) - 1
        if keep > 8:
            return prefix + body[:keep] + "…" + tail
    return prefix + text[:max(1, room - 1)] + "…"


def _capped(values, label, where=None):
    """At most three, plus a line saying how many were not shown.

    The count line is not decoration. A silent truncation reads as "there were
    three", which is a claim the command never checked.

    `where` says where the rest are, so the three renderers give the same
    advice.
    """
    values = [v for v in (values or [])]
    shown = values[:MAX_ITEMS]
    lines = [_fit(v, "  - ") for v in shown]
    hidden = len(values) - len(shown)
    if hidden:
        lines.append(_fit("... and %d more %s - %s"
                          % (hidden, label, where or "run with --verbose"),
                          "  "))
    return lines


class Emitter:
    """Collects what a verb wants to say, and renders it in one mode."""

    def __init__(self, mode=DEFAULT_MODE, evidence_out=None, stream=None):
        self.mode = mode if mode in MODES else DEFAULT_MODE
        self.evidence_out = evidence_out
        self._out = []
        self._doc = None
        self._stream = stream

    # -- the two contracts --------------------------------------------------

    def hand_off(self, outcome, read=None, items=None, concerns=None,
                 reply=None, detail=None, failed=False, next_step=None):
        """A verb that ends a stage or renders a verdict. One screen."""
        if self.mode == "json":
            self._doc = {"outcome": outcome, "read": read,
                         "items": list(items or []),
                         "concerns": list(concerns or []),
                         "reply": reply, "next_step": next_step,
                         "failed": bool(failed)}
            return self

        # Concerns keep --quiet talking, so a policy-drift warning still
        # prints.
        if (self.mode == "quiet" and not failed and not reply
                and not concerns):
            # Nothing to decide and nothing went wrong. The exit code carries
            # it.
            self._note_no_capture(silent=True)
            return self

        lines = [_fit(outcome)]
        if read:
            lines.append(_path_line("Read: ", read))
        if items:
            lines.append("")
            lines.append("Key choices:")
            lines += _capped(items, "choices",
                             "see %s" % read if read else None)
        if concerns:
            lines.append("")
            lines.append("Pay attention to:")
            lines += _capped(concerns, "concerns",
                             "see %s" % read if read else None)
        if detail and self.mode == "verbose":
            lines.append("")
            lines += [_fit(d, "  ") for d in detail]
        if next_step:
            # A NEXT STEP is not a reply. A reply means a person is being asked
            # to decide; a next step is what to run. Telling them apart is what
            # lets --quiet be silent when nothing is being asked.
            lines.append("")
            lines.append(_fit(next_step, "Next: "))
        if reply:
            lines.append("")
            lines.append(_fit(reply, "Reply: "))

        self._out = lines
        # Add the no-capture note before the budget is applied, so it counts
        # against the twelve lines.
        self._note_no_capture()
        if self.mode != "verbose":
            self._out = _within(self._out, HANDOFF_LINES)
        return self

    def report(self, summary, detail=None, capture=None):
        """A verb somebody runs to GET detail. Summary first, detail in full.

        The hand-off budget is deliberately NOT applied here. Cutting a report
        to twelve lines removes the reason to run it.
        """
        if self.mode == "json":
            self._doc = {"summary": list(summary or []),
                         "detail": list(detail or [])}
            if capture is not None and self.evidence_out:
                self._write_capture(capture)
                self._doc["capture"] = self.evidence_out
            return self

        lines = [_fit(s) for s in (summary or [])][:REPORT_SUMMARY_LINES]
        if detail and self.mode != "quiet":
            lines.append("")
            lines += [_fit(d) for d in detail]

        if capture is not None:
            if self.evidence_out:
                self._write_capture(capture)
                lines.append("")
                lines.append(_path_line("Raw output: ", self.evidence_out))
            else:
                lines.append("")
                lines.append("Raw output not captured - pass --evidence-out "
                             "PATH to write it")
        self._out = lines
        return self

    # -- capture ------------------------------------------------------------

    def _write_capture(self, capture):
        write_capture(self.evidence_out, capture)

    def _note_no_capture(self, silent=False):
        """`--evidence-out` on a verb with nothing to capture.

        Not an error: a script that passes the flag uniformly across a pipeline
        should not break on the verbs that happen to have nothing to say.
        """
        if not self.evidence_out or silent or self.mode in ("quiet", "json"):
            return
        self._out.append(_path_line(
            "There was nothing to capture, so no file was written to ",
            self.evidence_out))

    # -- rendering ----------------------------------------------------------

    def rendered(self):
        if self.mode == "json":
            return json.dumps(self._doc or {}, indent=2)
        return "\n".join(self._out)

    def flush(self):
        mark_handled()
        text = self.rendered()
        if text:
            print(text, file=self._stream or sys.stdout)
        return text


def _within(lines, budget):
    """Fit to the budget by dropping WHOLE lines from the end.

    Never by editing a line it keeps - that is the ADR-017 rule made
    structural. Blank separators go first, because they cost a line and carry
    no meaning.
    """
    if len(lines) <= budget:
        return lines
    kept = [l for l in lines if l.strip()]
    if len(kept) <= budget:
        return kept
    return kept[:budget - 1] + ["... %d more line(s) not shown - run with "
                                "--verbose" % (len(kept) - budget + 1)]


def over_budget(outputs, budget=HANDOFF_LINES, width=MAX_WIDTH):
    """Which verbs printed past the contract, and by how much.

    `outputs` maps a verb's command path to what it actually printed. Returns a
    list of findings, each naming the verb, its count and its budget - an
    unactionable failure gets suppressed rather than fixed.

    An EMPTY input returns the sentinel, not an empty list. A guard handed
    nothing must not answer "all good".
    """
    if not outputs:
        return NOTHING_TO_CHECK
    findings = []
    for verb, text in sorted(outputs.items()):
        lines = text.splitlines() or [text]
        if len(lines) > budget:
            findings.append("%s printed %d lines against a budget of %d"
                            % (verb, len(lines), budget))
        # A line is only "too wide" if it could have been narrower. One that
        # is long because it carries a whole path is exempt: shortening a path
        # makes it unopenable, which fails at the thing the line exists for.
        wide = [l for l in lines
                if len(l) > width and not _is_unbreakable(l, width)]
        if wide:
            findings.append(
                "%s printed %d line(s) wider than %d characters (longest %d), "
                "so a line budget alone would be met by joining lines"
                % (verb, len(wide), width, max(len(l) for l in wide)))
    return findings


def _is_unbreakable(line, width):
    """Is this line long only because of one token that cannot be broken?

    A path or a URL. Everything before it must still fit the budget, so this
    exempts `Read: /very/long/path` and not a paragraph with a path in it.
    """
    parts = line.split()
    if not parts:
        return False
    longest = max(parts, key=len)
    if len(longest) <= 20:
        return False
    rest = len(line) - len(longest)
    if rest > width:
        return False
    # Match a real path or URL, not any long word with a slash. The width
    # guard uses this same predicate, so a wrong exemption would also hide
    # the line from the guard.
    if "://" in longest:
        return True
    return "/" in longest and (
        longest.startswith(("/", "./", "../", "~/"))
        or longest.count("/") >= 2
        or os.path.splitext(longest)[1] != "")


# =============================================================================
# Reports
# =============================================================================

class Report:
    """A verb that is run deliberately to GET detail.

    It collects a SUMMARY - what was found, in a few lines a reader can stop at
    - and named SECTIONS of rows. The hand-off budget is never applied: cutting
    a report to twelve lines removes the reason to run it.

    Rows may be plain strings or dicts. Dicts are what make `--json` a machine
    mode rather than prose in a wrapper, so a verb that has structure should
    pass it rather than pre-formatted lines.
    """

    def __init__(self, args, title=None):
        self.mode = resolve_mode(args)
        self.evidence_out = getattr(args, "evidence_out", None)
        self.title = title
        self._summary = []
        self._sections = []
        self._body = []
        self._extra = {}

    def summary(self, *lines):
        for l in lines:
            if l is not None:
                self._summary.append(str(l))
        return self

    def section(self, name, rows, render=None):
        """One named group. `render` turns a row into its display line."""
        self._sections.append((name, list(rows or []), render))
        return self

    def body(self, text):
        """Prose a verb already renders itself, kept as the report's detail.

        For a verb whose rendering is not worth restructuring yet: it still
        gets the right behaviour in every mode, and `data()` is what carries
        the machine-readable half. Prefer `section()` with dict rows where the
        structure already exists - a report whose JSON is only prose is a
        wrapper, not a machine mode.
        """
        self._body = [l for l in str(text).splitlines()]
        return self

    def data(self, **kw):
        """Extra machine-only fields for --json."""
        self._extra.update(kw)
        return self

    def _row_line(self, row, render):
        if render is not None:
            return render(row)
        if isinstance(row, dict):
            return "  ".join("%s=%s" % (k, v) for k, v in row.items())
        return str(row)

    def emit(self):
        mark_handled()
        if self.mode == "json":
            doc = {"summary": list(self._summary),
                   "sections": {name: rows for name, rows, _ in self._sections}}
            if self._body:
                doc["body"] = list(self._body)
            doc.update(self._extra)
            if self.title:
                doc["title"] = self.title
            print(json.dumps(doc, indent=2, default=str))
            return 0

        # A summary line carrying a path is printed WHOLE. Shortening it makes
        # the link unopenable, which fails at the thing the line exists for -
        # the same rule the hand-off applies.
        head = [l if _is_unbreakable(l, MAX_WIDTH) else _fit(l)
                for l in self._summary][:REPORT_SUMMARY_LINES]
        if self.mode == "quiet":
            # NOT silence. Somebody who asked for a report asked for an answer;
            # --quiet says they want it short, not that they want nothing.
            if head:
                print("\n".join(head))
            return 0

        out = list(head)
        if self.evidence_out:
            # The whole report goes to the file; the terminal keeps the
            # summary and a link.
            full = list(self._summary) + list(self._body)
            for name, rows, render in self._sections:
                full.append("")
                full.append("%s (%d)" % (name, len(rows)))
                full += ["  " + self._row_line(r, render) for r in rows]
            write_capture(self.evidence_out, "\n".join(full))
            out.append("")
            out.append(_path_line("Full detail written to: ", self.evidence_out))
            print("\n".join(out))
            return 0
        if self._body:
            out.append("")
            out += self._body
        for name, rows, render in self._sections:
            if not rows:
                continue
            out.append("")
            out.append("  %s (%d)" % (name, len(rows)))
            for row in rows:
                out.append("    %s" % self._row_line(row, render))
        print("\n".join(out))
        return 0


def _project_root():
    try:
        from compass_pkg.core import find_compass_dir
        return os.path.dirname(find_compass_dir())
    except Exception:  # noqa: BLE001 - outside a project, nothing to relativise
        return None


def _relative(text, root):
    from compass_pkg.render import relative_paths
    return relative_paths(text, root)


def relative_to_project(text):
    """`text` with absolute paths under the project made relative (#291), for
    the verbs that print rather than going through `say()`."""
    return _relative(text, _project_root())


def say(args, outcome, detail=None, read=None, reply=None, decision=False, **data):
    """One hand-off, from a verb that has a single thing to report.

    Most verbs are one line and a couple of details: "the record is written,
    here is where". This is that shape, so such a verb is one call rather than
    a hand-rolled Emitter.

    `**data` is the verb's real identifiers - the id it wrote, the path it
    wrote to, the status it set. They are what make `--json` a machine mode
    instead of the verb's prose in a wrapper, which is why this takes them
    rather than deriving them from the sentence.

    `decision=True` marks an outcome that survives `--quiet`, which is
    documented as "errors and the decision hand-off only". Use it when the run
    changed something in the user's repository that they would want to know
    about even when they asked for silence - `compass init` creating
    `.compass/` is the case it was added for. Progress and confirmations are
    not decisions; if in doubt it is not one.
    """
    mark_handled()
    mode = resolve_mode(args)
    if mode == "json":
        doc = {"outcome": outcome}
        doc.update({k: v for k, v in data.items() if v is not None})
        if detail:
            doc["detail"] = [str(d) for d in detail]
        if read:
            doc["read"] = read
        print(json.dumps(doc, indent=2, default=str))
        return 0
    if getattr(args, "evidence_out", None):
        write_capture(args.evidence_out,
                      "\n".join([str(outcome)] + [str(d) for d in (detail or [])]))
    # A person or the model reading this opens paths relative to the project
    # (#291). The --json mode above keeps this verb's data as given; verbs
    # that print their own lines are relativised where they print.
    root = _project_root()
    outcome = _relative(outcome, root)
    detail = [_relative(str(d), root) for d in (detail or [])]
    if mode == "quiet":
        if decision:
            # `--quiet` is "errors and the decision hand-off only", so a run
            # that changed something in the repository still says the one line
            # that says what. Details are progress; the outcome is the
            # decision.
            print(_fit(outcome))
            return 0
        # Nothing was decided and nothing went wrong. The exit code carries it.
        return 0
    lines = [_fit(outcome)]
    for d in (detail or []):
        # A detail that is a bare path keeps its whole length: a link a reader
        # cannot open fails at the thing it exists for.
        # The indent is applied either way, so a continuation line lines up
        # with the line it continues.
        text = str(d)
        lines.append("  " + text if _is_unbreakable("  " + text, MAX_WIDTH)
                     else _fit(text, "  "))
    if read:
        lines.append(_path_line("Read: ", read))
    if reply:
        lines.append(_fit(reply, "Reply: "))
    if getattr(args, "evidence_out", None):
        lines.append(_path_line("Written to: ", args.evidence_out))
    print("\n".join(lines))
    return 0


# Set by whichever renderer handled a run's mode. `main()` reads it to decide
# whether a verb rendered itself or still prints as it always did.
_HANDLED = {"mode": False}


def mark_handled():
    _HANDLED["mode"] = True


def was_handled():
    return _HANDLED["mode"]


def run_with_mode(args, fn):
    """Run a verb, and honour the output flags even if the verb does not.

    Every verb accepts --quiet, --json and --evidence-out, because they are
    attached to the whole parser tree at once. A verb that has not been
    converted would otherwise ACCEPT each of them and ignore it, which is worse
    than not offering the flag - the reader is told the tool did something it
    did not do.

    So: the verbs that render themselves say so, and anything else has its
    output captured here and shaped to the mode. The JSON this produces for an
    unconverted verb is that verb's own prose under an `output` key - honest
    about being prose, and not the same thing as the structured document a
    converted verb emits. Converting the rest is per-verb work, and this is
    what keeps the flag truthful until then.
    """
    import contextlib
    import io as _io

    _HANDLED["mode"] = False
    mode = resolve_mode(args)
    out_path = getattr(args, "evidence_out", None)
    if mode == "summary" and not out_path:
        return fn(args)                      # the ordinary path, untouched

    buf = _io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = fn(args)
    text = buf.getvalue()
    if _HANDLED["mode"]:
        sys.stdout.write(text)               # the verb handled it already
        return code

    if out_path:
        write_capture(out_path, text.rstrip("\n"))
    if mode == "json":
        print(json.dumps({"output": text.rstrip("\n").splitlines(),
                          "structured": False,
                          "note": "this verb has not been converted to the "
                                  "output contract; these are its own lines"},
                         indent=2))
        return code
    if mode == "quiet":
        if code:
            sys.stdout.write(text)           # a failure is never swallowed
        elif out_path:
            print(_path_line("Written to: ", out_path))
        return code
    sys.stdout.write(text)
    if out_path:
        print(_path_line("Written to: ", out_path))
    return code
