"""The mechanical half of the writing-style rewrite, enforced.

The writing-style audit records 2,928 findings across 474 files against the
standard in the maintainer's global `CLAUDE.md`. It is not itself part of
this repository's tracked tree - it lives under `docs/analysis/`, which is
gitignored, so it opens on the maintainer's machine and nowhere else. Nine
batches fix the 474 files it names; this module is what judges every one of
them, and what stops the prose drifting back afterwards.

Fourteen rules can be held mechanically - a sweep reads the tracked tree,
reports a file, a line and what it found, and is silent when the prose is
clean. Each sweep is proven able to fail before it is trusted: a breach is
planted in `tests/fixtures/writing-style/`, and the sweep must report it
before a zero from the real tree means anything (`PBW-E1`, `PBW-E2`).

The sweeps landed before the batches that used them, and each batch skipped
the paths it had not yet corrected through a per-batch list under
`tests/writing_style_pending/`. The last batch deleted the last list, so every
tracked path is judged now and the scaffolding is gone (`PBW-D1`, `PBW-F6`).

`RULES` is a registry, not fourteen hand-written test bodies: `PBW-E1` proves
every rule in it in one loop, so a fifteenth rule cannot be added unproven.
Each rule owns its own patterns and its own named exemptions - the classes of
prose this covers have nothing in common beyond the text a reader sees, so a
shared matcher would fit none of them well.
"""
from __future__ import annotations

import ast
import dataclasses
import io
import json
import os
import re
import subprocess
import sys
import tokenize
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable, Iterable

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "writing-style"
TERMINOLOGY_PATH = REPO_ROOT / "governance" / "terminology.yml"

# What `reader.prose_spans` treats as prose inside a YAML value: the keys
# whose value a reader or a printed message actually sees, not the machine
# contract a migration would rename. Read from `scripts/prose_keys.py`, the
# one place either half defines this list (finding 1, `review-dimensions.md`
# - two separately-written copies had already drifted once), so the
# behaviour comparison's YAML reader (`DD-3`) cannot disagree with this
# sweep about what prose is.
from scripts.prose_keys import PROSE_KEYS  # noqa: E402

# Files this issue does not touch, matched by exact path or by directory
# prefix (a trailing slash). `docs/system-spec.md` is derived and regenerated
# by `compass ship`; the two `cli/vendor/` paths are upstream code copied
# unmodified (DD-7 keeps `cli/vendor/README.md` out of this set, because
# Compass wrote it); `LICENSE` and `assets/` are out of scope.
#
# `docs/system-spec-archive.md` holds the spec's archived sections since the
# split, on the same ground.
# `docs/system-spec.md` is derived rather than excluded on some ground the
# sweeps could not state - it hides real findings, and the reason it is
# still right to exclude it is recorded here (finding 7,
# `review-dimensions.md`). Every sweep run directly over the file, bypassing
# this set, reports five kinds and no others: retired words (`PBW-A1`), bare
# codes (`PBW-A7`), word-table hits (`PBW-A2`), spellings (`PBW-A3`) and
# idioms (`PBW-A5`). The counts rise as issues land, because each one appends
# its scenario titles, so the kinds are what is pinned and the totals are
# not. At the time this was written they were 181, 53, 30, 12 and 10. They are overwhelmingly archived scenario titles -
# `task`, `task-architectural`, `lens`, `Land`, `Frame` and the rest - each  # vocabulary-scan: allow - naming the retired v1 words the excluded findings are made of, not using them
# on a line already ending `_(archived)_` - the same ground
# `governance/terminology.yml`'s `scan.exempt` already gives
# `architecture/decisions/`: a landed scenario's title is a historical
# record of what it was called when it ran, not a live claim a reader acts
# on today. `PBW-D8` proves the branch changes none of the excluded paths,
# which is the check this exclusion needs, not the ground for it.
EXCLUDED_PATHS: frozenset[str] = frozenset({
    "docs/system-spec.md",
    "docs/system-spec-archive.md",
    "cli/vendor/yaml/",
    "cli/vendor/LICENSE-PyYAML",
    "LICENSE",
    "assets/",
})


# ---------------------------------------------------------------------------
# The shapes every rule and every sweep share.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProseSpan:
    """One line of prose a rule may judge, with the file and kind it came
    from. A markdown line, a Python comment or docstring line, a shell
    comment, or a YAML/JSON prose value - never a printed string, an
    asserted string or a machine key."""

    path: str
    line: int
    text: str
    kind: str  # markdown | comment | docstring | yaml_value | json_value


@dataclass(frozen=True)
class Finding:
    """One rule-reported breach: the file, the line and what the rule found."""

    path: str
    line: int
    detail: str


@dataclass(frozen=True)
class Exemption:
    """A named, reasoned carve-out for one rule at one file. Never a widened
    pattern (`PBW-E3`) - the pattern stays the same for every other file."""

    path: str
    quote: str
    reason: str


@dataclass(frozen=True)
class Report:
    """One sweep's result: which rule ran, what it found, how many files
    were given to it, and how many of those it can actually report on - so a
    zero from an empty file set reads differently from a zero from clean
    prose (`PBW-E2`), and a zero from a rule with a narrow reach reads
    differently from a zero read against the whole repository (`PBW-E2`,
    finding 11, `review-dimensions.md`: a single repository-wide
    `files_scanned` overstated four rules' real reach by up to 60 times)."""

    rule_id: str
    findings: tuple[Finding, ...]
    files_scanned: int
    files_reachable: int

    def render(self) -> str:
        lines = [f"{self.rule_id}: {len(self.findings)} finding(s) over "
                 f"{self.files_reachable} file(s) it can report on "
                 f"({self.files_scanned} scanned)"]
        for finding in self.findings:
            lines.append(f"  {finding.path}:{finding.line}: {finding.detail}")
        return "\n".join(lines)


@dataclass(frozen=True)
class Rule:
    """One mechanical rule: its id, the scenario it satisfies, the finder
    that reads one span at a time, and the exemptions found in review.

    `reach` names which scanned files this rule could ever report on - most
    rules read every kind of span, so the default (`None`) counts a file the
    moment it yields one prose span of any kind. A rule scoped to a real
    path or a file type (`PBW-A1`, `PBW-A10`, `PBW-C3`, `PBW-C4`, `PBW-C5`)
    overrides it, so `Report.files_reachable` states that rule's own reach
    rather than the whole repository's."""

    id: str
    scenario: str
    find: Callable[[ProseSpan], list[Finding]]
    exemptions: tuple[Exemption, ...] = field(default_factory=tuple)
    reach: Callable[[str], bool] | None = None


# ---------------------------------------------------------------------------
# reader - what counts as prose, per file type. The one place that decides,
# so a rule cannot quietly read a different surface from its siblings.
# ---------------------------------------------------------------------------

def _read(path: Path) -> str | None:
    """A file's text, or None when it is binary or has gone since git listed it."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _markdown_spans(rel: str, text: str) -> list[ProseSpan]:
    """Every line, with a fenced block's contents and a blockquote line
    blanked rather than dropped - so a reported line number stays true."""
    spans: list[ProseSpan] = []
    in_fence = False
    fence_char = ""
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        fence = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence:
            if not in_fence:
                in_fence, fence_char = True, fence.group(1)[0]
            elif stripped[0] == fence_char:
                in_fence = False
            spans.append(ProseSpan(rel, lineno, "", "markdown"))
            continue
        if in_fence or re.match(r"^\s*>", line):
            spans.append(ProseSpan(rel, lineno, "", "markdown"))
            continue
        spans.append(ProseSpan(rel, lineno, line, "markdown"))
    return spans


def _python_spans(rel: str, text: str) -> list[ProseSpan]:
    """Comments from `tokenize`, docstrings from `ast`. Never another string
    literal - a printed message or an assertion is not what this module
    checks, and the behaviour comparison (`DD-3`) is what proves neither
    changed."""
    spans: list[ProseSpan] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                spans.append(ProseSpan(rel, tok.start[0],
                                        tok.string.lstrip("#").strip(),
                                        "comment"))
    except (tokenize.TokenizeError, IndentationError, SyntaxError):
        pass
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return spans
    docstring_ids = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                               ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            doc = body[0].value
            docstring_ids.add(id(doc))
            for offset, line in enumerate(doc.value.splitlines()):
                spans.append(ProseSpan(rel, doc.lineno + offset, line, "docstring"))
    return spans


def _shell_spans(rel: str, text: str) -> list[ProseSpan]:
    """`#` comment text only - never a command line, so a printed message a
    hook emits through `cat >&2 <<EOF` is out of reach the same way a Python
    string literal is."""
    spans: list[ProseSpan] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = re.search(r"(?:^|\s)#(.*)$", line)
        if match:
            spans.append(ProseSpan(rel, lineno, match.group(1), "comment"))
    return spans


_YAML_KEY_RE = re.compile(r"^(\s*-?\s*)([\w.\-]+)\s*:\s?(.*)$")


def _yaml_comment_spans(rel: str, text: str) -> list[ProseSpan]:
    """Whole-line `#` comments. An inline comment after a value is rare in
    this tree's YAML and is left to the value-side walk below, which already
    reads the value itself."""
    spans: list[ProseSpan] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            spans.append(ProseSpan(rel, lineno, stripped[1:], "comment"))
    return spans


def _scalar_span(node: "yaml.ScalarNode", rel: str, spans: list[ProseSpan]) -> None:
    start = node.start_mark.line + 1
    for offset, line in enumerate(str(node.value).splitlines()):
        spans.append(ProseSpan(rel, start + offset, line, "yaml_value"))


def _walk_yaml_node(node, rel: str, spans: list[ProseSpan]) -> None:
    """Depth-first walk of a composed YAML node tree, collecting the value of
    every `PROSE_KEYS` key at any depth. Composing rather than a line regex
    is what makes a folded or literal block scalar (`description: >`) read
    correctly - the parser already knows where the value starts and ends.

    A prose key's value can be a scalar or a sequence of scalars (a
    `biases:` list of tie-breakers) - both are read. A sequence item that is
    itself a mapping (`- name: x`) is left alone: its keys are values, not
    prose, the same distinction `scripts/compare-behaviour.py`'s blanking
    draws. Finding 1, `review-dimensions.md`: before this, only the scalar
    shape was read, so a prose sequence item was silently skipped."""
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            is_prose_key = (isinstance(key_node, yaml.ScalarNode)
                             and key_node.value in PROSE_KEYS)
            if is_prose_key and isinstance(value_node, yaml.ScalarNode):
                _scalar_span(value_node, rel, spans)
            elif is_prose_key and isinstance(value_node, yaml.SequenceNode):
                for item in value_node.value:
                    if isinstance(item, yaml.ScalarNode):
                        _scalar_span(item, rel, spans)
                    # else: a mapping item's keys are values, not prose.
            else:
                _walk_yaml_node(value_node, rel, spans)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _walk_yaml_node(item, rel, spans)


def _yaml_spans(rel: str, text: str) -> list[ProseSpan]:
    """`#` comment text, plus the values of `PROSE_KEYS` keys at any depth.
    Never another value - a machine enum naming a retired-word compound
    stays out of reach, the same protection `PBW-D1` already holds for
    identifiers."""
    spans = _yaml_comment_spans(rel, text)
    try:
        node = yaml.compose(text)
    except yaml.YAMLError:
        return spans
    if node is not None:
        _walk_yaml_node(node, rel, spans)
    return spans


_JSON_DESCRIPTION_RE = re.compile(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _json_spans(rel: str, text: str) -> list[ProseSpan]:
    """`description` values only - the text a validation error quotes back,
    and the closest thing a schema has to documentation."""
    spans: list[ProseSpan] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = _JSON_DESCRIPTION_RE.search(line)
        if match:
            spans.append(ProseSpan(rel, lineno, match.group(1), "json_value"))
    return spans


def _spans_for_file(path: Path) -> list[ProseSpan]:
    rel = str(path.relative_to(REPO_ROOT))
    text = _read(path)
    if text is None:
        return []
    suffix = path.suffix
    if suffix == ".py":
        return _python_spans(rel, text)
    if suffix == ".md":
        return _markdown_spans(rel, text)
    if suffix in (".yml", ".yaml"):
        return _yaml_spans(rel, text)
    if suffix == ".json":
        return _json_spans(rel, text)
    if suffix == ".sh" or suffix == "":
        # A dotfile or an extensionless script such as Makefile or
        # .gitignore reads the same way a shell script does: a `#` comment
        # is prose, a command line is not.
        return _shell_spans(rel, text)
    return []


def prose_spans(paths: Iterable[Path]) -> list[ProseSpan]:
    """Every span a rule may read, across every path given."""
    spans: list[ProseSpan] = []
    for path in paths:
        spans.extend(_spans_for_file(path))
    return spans


# ---------------------------------------------------------------------------
# The file set - git's own tracked tree, minus the excluded paths and the
# pending lists still in force.
# ---------------------------------------------------------------------------

def _git_ls_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT,
                          capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def _is_excluded(rel: str) -> bool:
    for excluded in EXCLUDED_PATHS:
        if excluded.endswith("/"):
            if rel == excluded.rstrip("/") or rel.startswith(excluded):
                return True
        elif rel == excluded:
            return True
    return False


_FIXTURE_PREFIX = "tests/fixtures/writing-style/"

# Other frameworks' own records. An eval scenario lays a `seed_R1/`
# or `seed_R3/` overlay over its seed for a session under that
# framework, in the words that framework writes. Compass's writing rules must
# not rewrite them, and an allow marker would appear in the text the session
# reads, so every file in such an overlay is left out.
_OTHER_FRAMEWORKS_OVERLAYS = ("/seed_R1/", "/seed_R3/")


def _is_other_frameworks_record(rel: str) -> bool:
    return rel.startswith("evals/scenarios/") and any(
        part in rel for part in _OTHER_FRAMEWORKS_OVERLAYS)


def scanned_paths() -> list[Path]:
    """Every tracked path, minus `EXCLUDED_PATHS`, minus this mechanism's own
    planted-breach fixtures. The fixtures are not on `EXCLUDED_PATHS` - that
    set is the audit's own five paths - but they plant a breach on purpose
    (`PBW-E1`) and every sweep's own per-rule test would otherwise see them as
    a real, unfixed finding."""
    return [REPO_ROOT / rel for rel in _git_ls_files()
            if not _is_excluded(rel)
            and not rel.startswith(_FIXTURE_PREFIX)
            and not _is_other_frameworks_record(rel)]


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------

def _is_exempt(rule: Rule, span: ProseSpan) -> bool:
    return any(ex.path == span.path and ex.quote in span.text
               for ex in rule.exemptions)


def run_sweep(rule: Rule, paths: Iterable[Path]) -> Report:
    path_list = list(paths)
    findings: list[Finding] = []
    spans_seen: set[str] = set()
    for span in prose_spans(path_list):
        spans_seen.add(span.path)
        if _is_exempt(rule, span):
            continue
        findings.extend(rule.find(span))
    # A file only counts once it yields a prose span - the baseline every
    # rule needs - and, if the rule names its own narrower `reach`, once it
    # also clears that.
    files_reachable = sum(
        1 for p in path_list
        if str(p.relative_to(REPO_ROOT)) in spans_seen
        and (rule.reach is None or rule.reach(str(p.relative_to(REPO_ROOT)))))
    return Report(rule_id=rule.id, findings=tuple(findings),
                  files_scanned=len(path_list),
                  files_reachable=files_reachable)


# ---------------------------------------------------------------------------
# RULES - one entry per mechanical rule. PBW-E1 iterates this registry, so a
# rule that is not in it is not proven and does not run.
# ---------------------------------------------------------------------------

RULES: dict[str, Rule] = {}


def _register(rule: Rule) -> Rule:
    RULES[rule.id] = rule
    return rule


# ---------------------------------------------------------------------------
# PBW-A1 - no retired v1 word survives in prose, a comment or a test docstring
# ---------------------------------------------------------------------------

# Reused rather than copied (DD-1): `tests/test_terminology.py` already holds
# the tuned, fixture-proven pattern for every banned term. A second copy
# would be a second list to correct, which is exactly what `S14` refuses.
from test_terminology import BAN_PATTERNS  # noqa: E402

# The one definition of the per-line scan exemption marker (allow_marker.py),
# reused for the same reason BAN_PATTERNS is: a retired-word citation that
# governance/terminology.yml's own scan already accepts - a real command name
# retired at a major version, quoted so a reader whose script broke can find
# the row that fixes it - is not a fresh breach for this sweep to invent a
# second opinion about. This module checks the marker only on the span's own
# line: every citation it now guards carries an inline marker in the
# same table cell or sentence, not a marker on a preceding line.
from allow_marker import ALLOW_MARKER_RE  # noqa: E402

# The four reasons the terminology scan misses most retired words
# (audit 5.1) are surface gaps this module's reader already closes: it reads
# comments, it reads tests/, and its patterns are not narrowed to a single
# capitalised form. One gap is not a surface gap but a pattern gap - a
# hyphenated compound naming the retired unit-of-work word or the retired
# work-item word, the two forms the audit names by example - and that is
# what this table widens, term by term, rather than by loosening every
# pattern in BAN_PATTERNS.
HYPHEN_WIDENING: dict[str, tuple[re.Pattern, ...]] = {
    "stream": (re.compile(r"\b[a-z]+-streams?\b", re.IGNORECASE),),
    "task": (re.compile(r"\btask-[a-z]+\b", re.IGNORECASE),),
}

# tests/fixtures/terminology/ plants every banned word on purpose, to prove
# test_terminology.py's own patterns catch it (PBW-D2). This sweep reads the
# same tree and would otherwise report the same fixtures a second time for
# no reason - a structural exclusion for the one directory that exists to
# hold banned words, not a per-quote exemption for prose believed correct.
_RETIRED_WORD_STRUCTURAL_SKIP = "tests/fixtures/terminology/"

# governance/terminology.yml's own `scan.exempt` already excuses
# architecture/decisions/ - "ADRs may quote v1 terms" - because ADR-023
# rules that an accepted record keeps the words it was decided in. The
# retired-word rule honours the same exemption its own governance already
# grants; the idiom rule (PBW-A5) does not, because an ADR's idiom is
# ordinary prose, not the vocabulary the decision was made in.
_ADR_VOCABULARY_SKIP = "architecture/decisions/"

_TERMINOLOGY_PATH_STR = "governance/terminology.yml"
# terminology.yml's own `scan.exempt_regions` already names these five
# top-level blocks as the ones that "carry every retired word by
# necessity" - a ban must name the term it retires, and a rename table must
# name both spellings. PBW-D2 holds the retired-word and idiom sweeps to
# that same exemption for this one file, computed from the blocks'
# real line spans rather than a line range that would go stale on edit.
_TERMINOLOGY_EXEMPT_BLOCKS = frozenset(
    {"banned", "retired_machine_names", "retired_machine_name_exempt", "scan",
     "retired_in_output"})


def _leading_banner_start(lines: list[str], key_line_index: int) -> int:
    """The first line of the `# ===...` banner immediately above a key, or
    the key's own line index when there is no such banner. `blocks:` in
    `governance/terminology.yml`'s own `scan.exempt_regions` names a region
    by its key, but the key never explains itself - the comment banner
    directly above it does, and that banner exists BECAUSE the block below
    needs the retired words it names. Stopping the exempt range at the key
    line would flag the explanation and exempt only the list it explains."""
    i = key_line_index
    while i > 0 and (lines[i - 1].strip() == "" or lines[i - 1].lstrip().startswith("#")):
        i -= 1
    return i


@lru_cache(maxsize=1)
def _terminology_exempt_line_ranges() -> tuple[tuple[int, int], ...]:
    path = REPO_ROOT / _TERMINOLOGY_PATH_STR
    if not path.is_file():
        return ()
    text = path.read_text(encoding="utf-8")
    node = yaml.compose(text)
    if not isinstance(node, yaml.MappingNode):
        return ()
    lines = text.splitlines()
    ranges = []
    for key_node, value_node in node.value:
        if (isinstance(key_node, yaml.ScalarNode)
                and key_node.value in _TERMINOLOGY_EXEMPT_BLOCKS):
            start = _leading_banner_start(lines, key_node.start_mark.line)
            ranges.append((start + 1, value_node.end_mark.line + 1))
    return tuple(ranges)


def _in_terminology_exempt_block(span: ProseSpan) -> bool:
    if span.path != _TERMINOLOGY_PATH_STR:
        return False
    return any(start <= span.line <= end
               for start, end in _terminology_exempt_line_ranges())


def _find_retired_word(span: ProseSpan) -> list[Finding]:
    if span.path.startswith(_RETIRED_WORD_STRUCTURAL_SKIP):
        return []
    if ALLOW_MARKER_RE.search(span.text):
        return []
    if span.path.startswith(_ADR_VOCABULARY_SKIP):
        return []
    if _in_terminology_exempt_block(span):
        return []
    findings = []
    for term, patterns in BAN_PATTERNS.items():
        widened = tuple(patterns) + HYPHEN_WIDENING.get(term, ())
        for pattern in widened:
            match = pattern.search(span.text)
            if match:
                findings.append(Finding(
                    span.path, span.line,
                    f'retired word "{match.group(0)}" ({term})'))
                break
    return findings


_register(Rule(
    "PBW-A1", "No retired v1 word survives in prose, a comment "
    "or a test docstring", _find_retired_word,
    exemptions=(
        # PBW-F7's <!-- absorbed: "..." --> markers quote a merge-base
        # sentence verbatim so a reader can see what the rewrite carried
        # forward - the same reason ADR quotes and voice-tells fixtures are
        # exempt elsewhere in this file. HTML comments are not blanked by
        # _markdown_spans, so the quoted retired word is read as prose
        # unless named here.
        Exemption(
            "templates/architecture/decisions/ADR-004-lens-first-planner-second.md",
            "lens annotates), and parallel (both",
            "an absorbed-into marker quoting the merge-base sentence "
            "verbatim, per PBW-F7 - not a v1-vocabulary use of \"lens\"."),
        Exemption(
            "templates/architecture/decisions/ADR-004-lens-first-planner-second.md",
            "no lens consultation applied",
            "the same absorbed-into marker mechanism as the entry above, "
            "for the sentence naming the pre-rename note text."),
        Exemption(
            "docs/compass/2026-08-27-sdd-loop-spike.md",
            "cross-task-architectural-integrity",
            "the real slug of a filed, landed issue - an identifier "
            "(section 4), not a v1-vocabulary use of \"task\""),
        Exemption(
            "tests/test_route_selection.py",
            "cross-task-architectural-integrity",
            "the real slug of a filed, landed issue - an identifier "
            "(section 4), not a v1-vocabulary use of \"task\" - the same "
            "exemption already carried for this slug in "
            "docs/compass/2026-08-27-sdd-loop-spike.md."),
        Exemption(
            "docs/compass/2026-08-27-sdd-loop-spike.md",
            "task-reviewer-prompt.md",
            "the literal filename of a file inside the R1 "
            "repository, cited so the reference stays openable - not "
            "this project's vocabulary"),
        Exemption(
            "templates/architecture/decisions/README.md",
            "ADR-004-lens-first-planner-second.md",
            "the ADR's real, tracked filename, linked from the index row - "
            "an identifier (section 4), not a v1-vocabulary use of \"lens\". "
            "The row's own title reads \"Architect First Planner Second\"."),
        Exemption(
            "skills/compass-runtime/writing-voice.md",
            "cross-task-architectural-integrity/devlog.md",
            "the real slug of a past, archived issue - the \"Source:\" "
            "line names which issue an archive quote came from. Section "
            "4's verbatim-quote protection covers this citation the same "
            "way it covers the quote: renaming the slug would misattribute "
            "it to an issue that never existed."),
        Exemption(
            "skills/compass-runtime/writing-voice.md",
            "swarm-script-strips-markdown/devlog.md",
            "the real slug of a past, archived issue - the same protected "
            "citation as the cross-task-architectural-integrity exemption "
            "above."),
        Exemption(
            "tests/test_swarm_script_parser.py",
            "Spec: swarm-script-strips-markdown/acceptance-criteria.md",
            "the real slug of a past, archived issue - the same protected "
            "citation as the cross-task-architectural-integrity exemption "
            "above."),
        # Two of terminology.yml's `not:` entries name a retired word on a
        # simple scalar line, with the "vocabulary-scan: allow" marker on a
        # real YAML comment line above it - a separate span this sweep
        # reads, so each needs its own named exemption. Three other `not:`
        # entries use a folded `>` block instead, where that same marker
        # text sits inside the value (not a real comment - `#` has no
        # special meaning there), so it folds into the one span this sweep
        # reads for the whole field and `ALLOW_MARKER_RE` already matches
        # it directly - no named exemption needed for those three, and none
        # is listed here.
        Exemption("governance/terminology.yml",
                   "A 'task' - that word survives only as machine state",
                   "a not: field naming the retired word on purpose."),
        Exemption("governance/terminology.yml",
                   "v1 called this a 'backfill', with states 'owed'",
                   "a not: field naming the retired word on purpose."),
        # docs/glossary.md is DERIVED from governance/terminology.yml by
        # `compass _derive-glossary`, so a `not:` field that has to name a
        # retired word reappears here verbatim. The source entries already
        # carry their own exemptions; the derived copy is a separate path and
        # needs its own. Fixing these would mean editing a generated file,
        # which the drift guard reverts, or removing the ban's own statement
        # of what it bans.
        Exemption("docs/glossary.md",
                   "v1 called this a 'backfill', with states 'owed' and 'paid'",
                   "the derived text of terminology.yml's follow-up `not:` "
                   "field, which cannot say what the term is NOT without "
                   "naming the retired word."),
        Exemption("docs/glossary.md",
                   "A 'task' - that word survives only as machine state",
                   "the derived text of terminology.yml's issue `not:` "
                   "field, same reason as the entry above."),
        Exemption(
            "cli/compass_pkg/analyze.py",
            'records write "full, streams unbounded by policy"',
            "quotes what an archived 1.x record literally says, already "
            "marked '# vocabulary-scan: allow', which this sweep does not "
            "read."),
        Exemption(
            "cli/compass_pkg/core.py",
            "retired `task` key still load through this row",
            "documents the retired key SPINE_KEY_MAP maps forward, the same "
            "purpose terminology.yml's own `not:` fields serve."),
        Exemption(
            "cli/compass_pkg/core.py",
            "multiagent work, and fan out \"independent subtasks\"; "
            "`topology` and",
            "documents the two retired words this map reads for back-compat, "
            "the same purpose terminology.yml's own `not:` fields serve."),
        Exemption(
            "cli/compass_pkg/core.py",
            "`stream` were Compass-only words for both",
            "documents the two retired words this map reads for back-compat, "
            "the same purpose terminology.yml's own `not:` fields serve."),
        Exemption(
            "cli/compass_pkg/core.py",
            "Evidence types. ADR-023 renamed `coherence-check` to "
            "`consistency-check`;",
            "documents the retired evidence type this map reads for "
            "back-compat, the same purpose terminology.yml's own `not:` "
            "fields serve."),
        Exemption(
            "cli/compass_pkg/core.py",
            "Friction categories. ADR-023 retired `ceremony`, and the enum "
            "holds",
            "documents the retired word this map reads for back-compat, the "
            "same purpose terminology.yml's own `not:` fields serve."),
        Exemption(
            "cli/compass_pkg/analyze.py",
            "Extract the reference route name from delivery-approach.md",
            "the function reads the literal 1.x field `**Reference "
            "route:**`, which route.md wrote before the v2 rename; the "
            "docstring names the field it searches for."),
        Exemption(
            "cli/compass_pkg/analyze.py",
            "Looks for: **Reference route:** Express",
            "quotes the literal 1.x field and a real 1.x route name, the "
            "text the regex searches an old document for."),
        Exemption(
            "cli/compass_pkg/test_ids.py",
            "governance/strategies.md carries S7",
            "a worked example of a sentence that merely mentions a file, "
            "inside quotes - prose, not a path reference, so S7 here names "
            "nothing and needs no meaning."),
        Exemption(
            "cli/migrate-map.yml",
            "ADR-023 retired `ceremony`",
            "documents which retired word the data rows below map away "
            "from, the same purpose terminology.yml's own `not:` fields "
            "serve - this file is data exempt from the vocabulary scan and "
            "must name retired words on purpose (audit note on this file)."),
        Exemption(
            "cli/compass_pkg/migrate.py",
            "the same document: `brief.md` and `prd.md` both become "
            "`intent.md`",
            "names the real v1 filenames this migration function reads - "
            "the module's whole purpose is v1-to-v2 filename mapping, the "
            "same reason migrate-map.yml's data rows name retired words."),
        Exemption(
            "cli/compass_pkg/landed_by.py",
            "and `backfills-paid` still apply",
            "backfills-paid is the real check id in "
            "the `checks` block of governance/guardrails.yml, an identifier - the audit notes "
            "the `backfills:` key is an identifier and stays; this is the "
            "same class of identifier."),
        Exemption(
            "cli/compass_pkg/checks.py",
            'in preference to task.get("task") which may be a',
            "quotes the real dict lookup at line 669 below, over the "
            "legacy `task` root key normalize_spine reads - an identifier, "
            "not prose."),
        Exemption(
            "cli/compass_pkg/receipt.py",
            'Records written before ADR-023 say "Topology"',
            "documents the retired label a pre-ADR-023 record literally "
            "carries, so this reader can still parse it - the same "
            "back-compat reading terminology.yml's own not: fields and the "
            "stream-N exemptions above cover."),
        Exemption(
            "cli/compass_pkg/receipt.py",
            '"Topology" (ADR-006)',
            "documents the retired label a pre-ADR-023 record literally "
            "carries, so this reader can still parse it."),
        Exemption(
            "tests/test_process_impact.py",
            "tasks: list of (slug, created, landed, route, n_gates, "
            "repairs|None).",
            "documents the function's real parameter name `tasks` (an "
            "identifier, section 4), not a v1-vocabulary use of the word - "
            "the parameter and every call site in this file use that name."),
        Exemption(
            "tests/test_no_deprecation_stubs.py",
            "`--task` and `--reading` were tolerated alongside `--issue` and",
            "names the real, retired CLI flag spelling `--task` this test "
            "asserts still fails - an identifier (section 4), not a "
            "v1-vocabulary use of the word."),
        Exemption(
            "tests/test_plain_words.py",
            'time, and "vacuous"/"vacuity" is accurate and almost never used in ordinary',  # plain-words: allow - the exemption quotes the offending sentence verbatim, which is how a substring sweep tells it from an ordinary use
            "the file's own subject is banning these words, so the "
            "docstring has to name them to explain the rule - the same "
            "exception the banned block itself gets."),
        Exemption(
            "tests/test_plain_words.py",
            "codes. An unexplained term is a defect whether it is `G5` or `vacuity`, and",  # plain-words: allow - the exemption quotes the offending sentence verbatim, which is how a substring sweep tells it from an ordinary use
            "the same naming-the-banned-word exception as the docstring "
            "line above."),
        Exemption(
            "tests/test_rework_scan.py",
            "`TRC-D2`: file added by task-a and deleted by task-b is reported.",
            "task-a and task-b are the real fixture directory names "
            "write_task_yml() writes (section 4, identifiers), not a "
            "v1-vocabulary use of the word."),
        Exemption(
            "tests/test_rework_scan.py",
            "`TRC-D4`: migration added in task-a and a drop migration added in task-b is reported.",
            "the same fixture directory names as the exemption above."),
        Exemption(
            "tests/test_rework_scan.py",
            "task-b is 10 days later - outside the window",
            "the same fixture directory name as the exemptions above."),
        Exemption(
            "tests/test_printed_output_vocabulary.py",
            "only layer 2 catches, and `Land` capitalised is a prose form that only",
            "a verbatim quote of the defect this test checks for - the "
            "capitalised retired stage name the prose scan must still "
            "catch, not live prose use of it."),
        Exemption(
            "tests/test_public_surface_truth.py",
            'user meeting "has Frame run?" is being told to run a stage that does not',
            "a verbatim quote of the class of defect this test checks for, "
            "not live prose use of a retired stage name."),
        Exemption(
            "tests/test_hook_fails_closed.py",
            "cli/vendor/yaml moved away  -> exit 3, zero bytes on both streams",
            "'streams' names stdout/stderr, an ordinary English use, not "
            "the retired v1 word for a subtask - the word-table row "
            "matches the plural bare word regardless of sense."),
        Exemption(
            "tests/test_prompt_layer.py",
            "The intake names `intent-elicitation` as the second target; no skill has ever",
            "quotes the specific proposed-but-never-built skill name "
            "`intent-elicitation`, not a live use of the retired word "
            "\"elicitation\"."),
        Exemption(
            "tests/test_record_keeping_integrity.py",
            "The defect: `task['friction'] = entries` discarded the first note.",
            "a verbatim quote of the real defective line "
            "(cli/compass_pkg/calibration.py:411, a local variable named "
            "`task`), not a v1-vocabulary use of the word."),
        Exemption(
            "tests/test_governance_drift_noop.py",
            "approach, gates, topology and fired guardrails against what the fixture",
            "names the fixture's real `topology` dict key the assertions "
            "below read (`expect[\"topology\"]`, `got[\"topology\"]`), not "
            "the abstract concept the word table retires - renaming the "
            "prose here would contradict the code two lines down."),
        Exemption(
            "tests/test_g5_trigger.py",
            "removed a committed default credential, read `blast_radius: critical`",
            "a literal quote of the manifest field the incident actually "
            "read at the time, kept in backticks by the audit's own "
            "ruling (batch 8, tests/test_g5_trigger.py note: "
            "\"`blast_radius: critical` in backticks stays\")."),
        Exemption(
            "tests/test_g5_trigger.py",
            "`blast_radius`, so the delivery approach stayed heavy",
            "the same literal field-name quote as the exemption above, "
            "continued onto its own wrapped line."),
        Exemption(
            "tests/test_route_selection.py",
            "swarm=8",
            "one of the literal keys of `RETIRED_ORCHESTRATION_CEILING` "
            "(cli/compass_pkg/core.py), itself marked "
            "\"vocabulary-scan: allow\" as the retired words archived "
            "manifests carry (ADR-006) - not a live use of the word."),
        Exemption(
            "tests/test_release_invariants.py",
            "Deliberately still named task.yml, and deliberately still "
            "keyed `task:`.",
            "the literal filename and key of a fixture kept under its "
            "pre-rename shape on purpose (ADR-006, ADR-022) - the test "
            "exists to prove this old shape still loads, so the name "
            "cannot be reworded without breaking the point of the test."),
        Exemption(
            "tests/test_human_voice.py",
            "retired stage name. `--task` no longer parses (ADR-014 removed",
            "names the real, retired CLI flag spelling `--task` this test "
            "asserts a teaching artifact must not use - an identifier "
            "(section 4), not a v1-vocabulary use of the word."),
        Exemption(
            "tests/analyze/test_analyze_core.py",
            "'Clarify: full' but manifest.yml says",
            "quotes the literal v1-shaped fixture content _write_route_md "
            "writes and the fixture's own dict keys assert on - an "
            "identifier of the test data (section 4), not prose use of "
            "the word."),
        Exemption(
            "tests/analyze/test_analyze_core.py",
            "delivery-approach.md says Clarify: full (disagrees with",
            "the same literal fixture-content quote as the entry above, "
            "in the comment right before the phases dict it describes."),
        Exemption(
            "tests/fixtures/rework-scan/add-then-delete-pair/"
            "task-adds-handler/task.yml", "Fixture: task-adds-handler",
            "the real, on-disk directory name of this fixture pair "
            "(section 4), not a v1-vocabulary use of the word."),
        Exemption(
            "tests/fixtures/rework-scan/add-then-delete-pair/"
            "task-adds-handler/task.yml",
            "task-removes-handler/task.yml",
            "the real, on-disk path of the sibling fixture (section 4), "
            "not a v1-vocabulary use of the word."),
        Exemption(
            "tests/fixtures/rework-scan/add-then-delete-pair/"
            "task-removes-handler/task.yml", "Fixture: task-removes-handler",
            "the real, on-disk directory name of this fixture pair "
            "(section 4), not a v1-vocabulary use of the word."),
        Exemption(
            "tests/fixtures/rework-scan/add-then-delete-pair/"
            "task-removes-handler/task.yml",
            "task-adds-handler/task.yml",
            "the real, on-disk path of the sibling fixture (section 4), "
            "not a v1-vocabulary use of the word."),
        Exemption(
            "tests/fixtures/self-architecture/hypothetical-framework-task/"
            "route.md", "hypothetical-framework-task (fixture)",
            "the real, on-disk directory name of this fixture (section 4), "
            "not a v1-vocabulary use of the word."),
        Exemption(
            "tests/plain_language_check.py", "the G5 guard kicked in",
            "the module's own worked example of the wrong form the check "
            "exists to catch, same protection as the PBW-A7 exemption for "
            "this line."),
        Exemption(
            "tests/test_schema_2.py",
            "no route.md, spec.feature.md, brief.md, clarifications.md, or",
            "names the exact retired filenames the test's own old_names "
            "set checks are absent - an identifier list (section 4), not "
            "prose use of the words."),
        Exemption(
            "tests/plain_language_check.py",
            "G5 fired, which means a human signs off",
            "the module's own worked example of the wrong form the check "
            "exists to catch, same protection as the PBW-A7 exemption for "
            "this line."),
        Exemption(
            "tests/test_status_vocabulary.py", "tasks: {slug: issue-dict}",
            "names the real parameter `tasks` this helper takes (section 4), "
            "not a v1-vocabulary use of the word."),
        Exemption(
            "tests/test_swarm_cap.py", "note quoting `blast_radius: critical`",
            "quotes the literal fixture string `_PROSE` verbatim, a "
            "regression fixture for an old-format audit note (section 4), "
            "not a v1-vocabulary use of the word."),
        Exemption(
            "tests/test_swarm_script_parser.py",
            "Match the \"stream-1: WOULD create worktree",
            "quotes the literal regex pattern on the next line verbatim - "
            "an identifier (section 4), not a v1-vocabulary use of the "
            "word."),
        Exemption(
            "tests/test_tdd_red_integrity.py", "not a red (TRC-G1)",
            "the scenario id TRC-G1 contains G1 as a substring by "
            "coincidence - an identifier (section 4), not a reference to "
            "the guardrail."),
        Exemption(
            "tests/test_tdd_red_integrity.py", "not a red (TRC-G2)",
            "the scenario id TRC-G2 contains G2 as a substring by "
            "coincidence - an identifier (section 4), not a reference to "
            "the guardrail."),
        Exemption(
            "tests/test_tdd_red_integrity.py", "still a red (TRC-G3)",
            "the scenario id TRC-G3 contains G3 as a substring by "
            "coincidence - an identifier (section 4), not a reference to "
            "the guardrail."),
        Exemption(
            "tests/analyze/test_analyze_core.py",
            "the slug `unframed-task` contains it",
            "the literal, hyphenated slug this test's fixture uses - an "
            "identifier (section 4), not a v1-vocabulary use of the word; "
            "the sentence's own point is that the retired-looking substring "
            "is coincidental."),
    ),
    # Finding 11, `review-dimensions.md`: this rule's own two file-level
    # skips, mirrored from `_find_retired_word` - a file inside either is
    # never a candidate, whatever it yields.
    reach=lambda path: (not path.startswith(_RETIRED_WORD_STRUCTURAL_SKIP)
                         and not path.startswith(_ADR_VOCABULARY_SKIP)),
))


# ---------------------------------------------------------------------------
# PBW-A2 - the shorter word stands where the word is not an identifier
# ---------------------------------------------------------------------------

# The audit's own found-candidates table (section 5.2) - the longer word or
# words on the left, the plain replacement on the right. Each row becomes one
# pattern with verb-form flexibility, matching the shape of the audit's own
# `git grep` example rather than a bare word.
WORD_TABLE: tuple[tuple[tuple[str, ...], str], ...] = (
    (("verify", "validate"), "check"),
    (("require",), "need"),
    (("attempt",), "try"),
    (("provide", "supply"), "give"),
    (("perform", "execute"), "do"),
    (("modify", "alter"), "change"),
    (("currently", "presently"), "now"),
    (("previously", "prior to"), "before"),
    (("ensure",), "make sure"),
    (("indicate", "denote"), "show"),
    (("utilise", "leverage", "employ"), "use"),
    (("in order to",), "to"),
    (("sufficient",), "enough"),
    (("obtain", "acquire"), "get"),
)


def _verb_pattern(word: str) -> str:
    """One word's alternation, widened for its common verb forms. A phrase
    (a space inside it) has no verb forms and is matched exactly."""
    if " " in word:
        return re.escape(word)
    if word.endswith("y") and word[-2:-1] not in "aeiou":
        return re.escape(word[:-1]) + r"(?:y|ies|ied|ying)"
    return re.escape(word) + r"(?:s|es|ed|ing)?"


_WORD_TABLE_PATTERNS: dict[tuple[str, ...], re.Pattern] = {
    words: re.compile(r"\b(?:" + "|".join(_verb_pattern(w) for w in words) + r")\b",
                       re.IGNORECASE)
    for words, _ in WORD_TABLE
}


def _word_table_exempt(text: str, match: re.Match) -> bool:
    """The identifiers PBW-A2 names: a gate id (`verify.analyze`), a
    backticked or code-spanned reference, a slash command
    (`/compass:verify`), and "the verify stage" - the one place the stage
    name, not the verb, is what the sentence means."""
    start, end = match.span()
    if start > 0 and text[start - 1] in "`/:":
        return True
    if text[end:end + 1] == ".":
        return True
    if re.match(r"\s+stage\b", text[end:end + 8], re.IGNORECASE):
        return True
    return False


def _find_word_table(span: ProseSpan) -> list[Finding]:
    findings = []
    for words, replacement in WORD_TABLE:
        pattern = _WORD_TABLE_PATTERNS[words]
        for match in pattern.finditer(span.text):
            if _word_table_exempt(span.text, match):
                continue
            findings.append(Finding(
                span.path, span.line,
                f'"{match.group(0)}" -> "{replacement}"'))
    return findings


# CLAUDE.md and AGENTS.md each carry the maintainer's own "Use the shorter
# word" reference table - the rule's documentation, not prose that breaks the
# rule. Its rows name the very words the rule retires, so the table cannot
# pass this sweep by rewording (PBW-F4 refuses a rewrite that would). Each
# row is its own named exemption (PBW-E3): the quote is the whole row, so a
# later row sharing one short word from an earlier row cannot exempt
# unrelated prose elsewhere in the same file.
#
# The maintainer's table has 18 rows; `WORD_TABLE` above mechanically checks
# 14 of them. "facilitate", "subsequently", "due to the fact that" and "with
# regard to" are documented but not enforced, so this sweep never reports
# their row and an exemption for it would be dead on arrival - finding 9,
# `review-dimensions.md`, found four such dead pairs (each row, both files)
# and removed them rather than leave them to accumulate.
_SHORTER_WORD_TABLE_ROWS: tuple[str, ...] = (
    "| utilise, leverage | use |",
    "| obtain, acquire | get |",
    "| provide, supply | give |",
    "| indicate, denote | show |",
    "| validate | check |",
    "| modify, alter | change |",
    "| require | need |",
    "| ensure | make sure |",
    "| perform, execute | do |",
    "| attempt | try |",
    "| sufficient | enough |",
    "| currently | now |",
    "| prior to | before |",
    "| in order to | to |",
)

_SHORTER_WORD_TABLE_EXEMPTIONS: tuple[Exemption, ...] = tuple(
    Exemption(path, row,
              "the \"Use the shorter word\" table names the retired word as "
              "documentation of the rule, not as prose that breaks it")
    for path in ("CLAUDE.md", "AGENTS.md")
    for row in _SHORTER_WORD_TABLE_ROWS
)

_register(Rule(
    "PBW-A2", "The shorter word stands where the word is not an "
    "identifier", _find_word_table,
    exemptions=_SHORTER_WORD_TABLE_EXEMPTIONS + (
        Exemption(
            "docs/five-minutes.md", "## 5. Verify and ship",
            "\"Verify\" here is the stage name, in the same heading form "
            "as \"1. Assess the work\", \"2. Define acceptance\" and "
            "\"4. Implement with evidence\" above it - an identifier "
            "(section 4), not the verb the word table retires"),
        Exemption(
            "docs/releasing.md", "## Supply-chain stance",
            "\"supply chain\" is the standard security term for this "
            "section's subject, not the verb \"supply\" the word table "
            "retires"),
        Exemption(
            "docs/security.md", "supply-chain requirements",
            "\"supply chain\" is the standard security term, not the verb "
            "\"supply\" the word table retires"),
        Exemption(
            "ci/README.md", "supply-chain stance",
            "the same standard security term as the docs/security.md "
            "exemption above."),
        Exemption(
            "ci/github-actions.yml", "supply-chain stance",
            "the same standard security term as the docs/security.md "
            "exemption above."),
        Exemption(
            ".github/workflows/compass.yml", "supply-chain stance",
            "the same standard security term as the docs/security.md "
            "exemption above."),
        Exemption(
            "compass-contract.md", "7. verify",
            "\"verify\" here is the stage name, one word per line in the "
            "stage list, in the same form as \"1. assess\" and \"6. "
            "implement\" beside it - an identifier (section 4), not the "
            "verb the word table retires"),
        Exemption(
            "docs/methodology.md", "| `/compass:verify` | Verify |",
            "\"Verify\" is the stage name in the stage-mapping table's own "
            "column, beside \"Assess\", \"Define\" and \"Plan\" - an "
            "identifier (section 4), not the verb the word table retires"),
        Exemption(
            "docs/quickstart.md", "### Verify",
            "\"Verify\" here is the stage name, in the same heading form as "
            "the \"### Assess\", \"### Define\" and \"### Implement\" "
            "headings in the same walkthrough - an identifier (section 4), "
            "not the verb the word table retires"),
        Exemption(
            "docs/quickstart.md", "verify, ship -",
            "\"verify\" here is one stage name in a list of stage names "
            "(implement, verify, ship) - an identifier (section 4), not "
            "the verb the word table retires"),
        Exemption(
            "tests/test_command_renames.py",
            "implement, verify, ship; the designer entry point is design;",
            "\"verify\" is one stage name in the list of eight pipeline "
            "commands, the same shape as the docs/quickstart.md exemption "
            "above; found while fixing batch 7, not by the audit."),
        Exemption(
            "tests/test_command_renames.py",
            "point. It inlines assess, define, implement, verify and ship for a small,",
            "\"verify\" is one stage name in a list of stage names, the "
            "same shape as the docs/quickstart.md exemption above; found "
            "while fixing batch 7, not by the audit."),
        Exemption(
            "docs/routing-deep-dive.md", "but verify also runs the",
            "\"verify\" is the stage name here, matching \"feature\" and "
            "the other lowercase reference-shape names beside it - an "
            "identifier (section 4), not the verb the word table retires"),
        Exemption(
            "docs/routing-deep-dive.md", "[refine, verify, ship]",
            "the literal `never_skip` policy value quoted from "
            "the `RP-FLOOR-001` floor in governance/routing-policy.yml - an identifier (section "
            "4), not the verb the word table retires"),
        Exemption(
            "docs/routing-deep-dive.md", "not skipped; verify and ship",
            "\"verify\" is the stage name in a list of stage names, "
            "matching \"ship\" beside it - an identifier (section 4), "
            "not the verb the word table retires"),
        Exemption(
            "docs/routing-deep-dive.md", "*before* verify and never verify",
            "\"verify\" is the stage name, twice - an identifier "
            "(section 4), not the verb the word table retires"),
        Exemption(
            "docs/routing-deep-dive.md",
            "**Verify** runs **at full weight",
            "\"Verify\" is the stage name, bold as one item in the "
            "stage-by-stage list beside \"Plan\", \"Breakdown\", "
            "\"Implement\" and \"Ship\" - an identifier (section 4), "
            "not the verb the word table retires"),
        Exemption(
            "skills/adaptive-routing/composition.md", "**Verify** - which "
            "review dimensions",
            "one label in a parallel bulleted list of pipeline-stage names "
            "(Define, Refine, Plan, Breakdown, Implement, Verify, Ship) - "
            "the stage name, not the verb."),
        Exemption(
            "skills/evidence-gates/review-dimensions.md",
            'as "verified"',
            "the word being quoted is the point of the sentence: it names "
            "the stronger claim a reader wrongly hears in a gate that only "
            "promises \"traceable\". Replacing the quoted word erases the "
            "contrast the sentence exists to make."),
        Exemption(
            "skills/compass-runtime/writing-voice.md",
            "do not perform the process",
            "the pinned principle line, verbatim - "
            "tests/test_human_voice.py:138 asserts this exact string "
            "(PRINCIPLE), and the audit's own per-file entry for this file "
            "lists it under \"Pinned\", to keep as it stands."),
        Exemption(
            "skills/evidence-gates/architecture-checks.md", "RP-REQUIRE-003",
            "a real routing-policy rule id (governance/routing-policy.yml, "
            "`RP-REQUIRE-003`) - the match lands mid-identifier on the "
            "\"REQUIRE\" substring, not the standalone verb the word table "
            "means to catch."),
        Exemption(
            "tests/analyze/test_analyze_core.py", "RP-REQUIRE-001",
            "the same rule-id false match as RP-REQUIRE-003 above, for the "
            "auth floor this test's fixture triggers."),
        Exemption(
            "tests/test_spine_records_the_truth.py", "RP-REQUIRE-003 adds",
            "the same rule-id false match as RP-REQUIRE-003 above, for the "
            "fitness-check floor this test's fixture triggers."),
        Exemption(
            "skills/evidence-gates/architecture-checks.md", "RP-REQUIRE-004",
            "the same rule-id false match as RP-REQUIRE-003 above, for the "
            "sibling rule."),
        Exemption(
            "templates/rollback-plan.md", "RP-REQUIRE-006",
            "the same rule-id false match as RP-REQUIRE-003 above, for the "
            "migrations floor."),
        Exemption(
            "templates/threat-model.md", "RP-REQUIRE-005",
            "the same rule-id false match as RP-REQUIRE-003 above, for the "
            "auth/payments/personal-data floor."),
        Exemption(
            "templates/technical-design.md", "RP-REQUIRE-005",
            "the same rule-id false match as RP-REQUIRE-003 above, for the "
            "auth/payments/personal-data floor."),
        Exemption(
            "templates/technical-design.md", "RP-REQUIRE-006",
            "the same rule-id false match as RP-REQUIRE-003 above, for the "
            "migrations floor."),
        Exemption(
            "schemas/routing-policy.schema.json", "RP-REQUIRE-003",
            "the same rule-id false match as the skills/evidence-gates "
            "exemption above, quoted here as the schema's own example "
            "waiver id."),
        Exemption(
            "cli/compass_pkg/routing.py",
            "calling it a floor is the same conflation the RP-REQUIRE ids "
            "were",
            "RP-REQUIRE is a real routing-policy id prefix - the match "
            "lands mid-identifier on the \"REQUIRE\" substring, the same "
            "false match as the architecture-checks.md exemption above."),
        Exemption(
            "cli/compass_pkg/routing.py",
            "introduced to end - and it would print \"[RP-REQUIRE-003] "
            "floor:\"",
            "RP-REQUIRE-003 is a real rule id, quoted as the literal "
            "printed text this comment explains."),
        Exemption(
            "skills/quick-fix/SKILL.md", "--verified-by",
            "a real CLI flag (`cli/compass:246,258`, `dest=\"verified_by\"`) "
            "- the match lands mid-flag-name on the \"verified\" substring, "
            "not the standalone verb the word table means to catch."),
        Exemption(
            "tests/test_acceptance_verb.py", "--verified-by",
            "the same real CLI flag false match as skills/quick-fix/SKILL.md "
            "above; found while fixing batch 7, not by the audit."),
        Exemption(
            "skills/tdd-discipline/no-natural-red.md", "terraform validate",
            "a third-party command's real name (Terraform's own CLI verb), "
            "not the English verb the word table means to catch - Compass "
            "does not own or spell this identifier."),
        Exemption(
            "cli/compass_pkg/tdd.py", "The sanctioned verified-by kinds",
            "names the `--verified-by` flag's accepted values - the match "
            "lands mid-flag-name on the \"verified\" substring, not the "
            "standalone verb the word table means to catch."),
        Exemption(
            "cli/compass_pkg/tdd.py", "terraform validate`, a schema parse",
            "a third-party command's real name (Terraform's own CLI verb), "
            "not the English verb the word table means to catch."),
        Exemption("approaches/README.md", "but verify adds the security",
                   "names the Verify stage, not the verb."),
        Exemption("approaches/composition-reference.md",
                   "**Verify** - which review dimensions",
                   "names the Verify stage, not the verb."),
        Exemption("approaches/composition-reference.md",
                   "Regular, but Verify also runs",
                   "names the Verify stage, not the verb."),
        Exemption("approaches/regular.md",
                   "| Verify | **Two review points**",
                   "names the Verify stage, not the verb."),
        Exemption("approaches/hotfix.md",
                   "All Verify gates, no exceptions",
                   "names the Verify stage and the Verify gate, not the verb."),
        Exemption("approaches/hotfix.md",
                   "Full Verify gate. Review dimensions",
                   "names the Verify gate, not the verb."),
        Exemption("approaches/hotfix.md", "never Verify itself",
                   "names the Verify stage, not the verb."),
        Exemption("approaches/hotfix.md",
                   "Compress the Verify gate. The stages before Verify are "
                   "compressed; Verify is",
                   "names the Verify gate and stage, not the verb."),
        Exemption("approaches/full.md",
                   "| Verify | **All gates, all dimensions.**",
                   "names the Verify stage, not the verb."),
        Exemption("approaches/quick-fix.md", "| Verify | Light gate",
                   "names the Verify stage, not the verb."),
        Exemption("approaches/quick-fix.md",
                   "One review point, at Verify, clearing three gates",
                   "names the Verify stage, not the verb."),
        Exemption("approaches/rubric.md", "Owns the Verify gate",
                   "names the Verify gate, not the verb."),
        Exemption("approaches/spike.md", "| Verify | **= Conclude.**",
                   "names the Verify stage, not the verb."),
        Exemption("architecture/ownership.md", "(verify → ship gate)",
                   "names the Verify stage, not the verb."),
        Exemption("architecture/system-context.md",
                   "implement → verify → ship",
                   "names the Verify stage, not the verb."),
        Exemption("ci/README.md", "verify time - it does not",
                   "names the Verify stage, not the verb."),
        Exemption("examples/README.md", "Verify is a short note",
                   "names the Verify stage, not the verb."),
        Exemption("examples/README.md", "uncompressed* Verify gate",
                   "names the Verify gate, not the verb."),
        Exemption(
            "examples/bdd-adapters/behave/docs/compass/"
            "2026-08-03-reset-password/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "names the Verify stage in the coverage ledger's own column "
            "header, not the verb."),
        Exemption(
            "examples/bdd-adapters/cucumber-js/docs/compass/"
            "2026-08-03-reset-password/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "the same coverage-ledger column header as the behave copy."),
        Exemption(
            "examples/bdd-adapters/godog/docs/compass/"
            "2026-08-03-reset-password/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "the same coverage-ledger column header as the behave copy."),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/docs/compass/"
            "2026-08-03-reset-password/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "the same coverage-ledger column header as the behave copy."),
        Exemption(
            "examples/feature-api-change/.compass/work/"
            "rate-limit-search-endpoint/devlog.md",
            "13:10 - Verify",
            "a devlog entry heading naming the Verify stage, not the verb."),
        Exemption(
            "examples/feature-api-change/docs/compass/"
            "2026-04-21-rate-limit-search-endpoint/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "the same coverage-ledger column header as the bdd-adapters "
            "exemption above."),
        Exemption(
            "examples/feature-api-change/docs/compass/"
            "2026-04-21-rate-limit-search-endpoint/delivery-approach.md",
            "| Verify | Full - one gate",
            "names the Verify stage in the per-stage weight table, not the "
            "verb."),
        Exemption(
            "examples/feature-api-change/docs/compass/"
            "2026-04-21-rate-limit-search-endpoint/delivery-approach.md",
            "gate at Verify (the feature's",
            "names the Verify stage, not the verb."),
        Exemption(
            "examples/hotfix-regression/.compass/work/"
            "search-crash-on-empty-filter/devlog.md",
            "10:40 - Verify",
            "a devlog entry heading naming the Verify stage, not the verb."),
        Exemption(
            "examples/hotfix-regression/.compass/work/"
            "search-crash-on-empty-filter/devlog.md",
            "Full Verify - not compressed",
            "names the Verify stage, not the verb."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "the same coverage-ledger column header as the bdd-adapters "
            "exemption above."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/delivery-approach.md",
            "reviewed the Verify gate",
            "names the Verify gate, not the verb."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/delivery-approach.md",
            "permitted Verify deferral",
            "names the Verify stage, not the verb."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/delivery-approach.md",
            "| Verify | Full |",
            "names the Verify stage in the per-stage weight table, not the "
            "verb."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/delivery-approach.md",
            "full Verify gate - five review",
            "names the Verify gate, not the verb."),
        Exemption(
            "examples/initiative-new-subsystem/.compass/work/"
            "notifications-subsystem/devlog.md",
            "14:50 - Verify",
            "a devlog entry heading naming the Verify stage, not the verb."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "the same coverage-ledger column header as the bdd-adapters "
            "exemption above."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/delivery-approach.md",
            "| Verify | All gates, all dimensions",
            "names the Verify stage in the per-stage weight table, not the "
            "verb."),
        Exemption(
            "examples/quick-fix-typo/.compass/work/"
            "fix-timeout-error-message/devlog.md",
            "09:27 - Verify",
            "a devlog entry heading naming the Verify stage, not the verb."),
        Exemption(
            "examples/quick-fix-typo/.compass/work/"
            "fix-timeout-error-message/devlog.md",
            "light Verify output",
            "names the Verify stage, not the verb."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "the same coverage-ledger column header as the bdd-adapters "
            "exemption above."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/delivery-approach.md",
            "| Verify | Light |",
            "names the Verify stage in the per-stage weight table, not the "
            "verb."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/delivery-approach.md",
            "1 (at Verify)",
            "names the Verify stage, not the verb."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/verification-note.md",
            "its Verify is light",
            "names the Verify stage, not the verb."),
        Exemption(
            "examples/spike-technical-unknown/docs/compass/"
            "2026-05-12-pdf-export-library-viability/delivery-approach.md",
            "| Verify | = **Conclude**",
            "names the Verify stage in the per-stage weight table, not the "
            "verb."),
        Exemption(
            "schemas/signals.schema.json",
            "reviewer agent at verify - judgement",
            "the JSON mirror of the already-exempted governance/signals.yml "
            "line above - names the Verify stage, not the verb."),
        Exemption(
            "templates/acceptance-criteria.md",
            "Passes as acceptance (verify)",
            "names the Verify stage in the coverage ledger's own column "
            "header, not the verb - every example's copy of this table is "
            "exempted the same way above."),
        Exemption(
            "templates/delivery-approach.md",
            "| Verify | {{gate count}}",
            "names the Verify stage in the per-stage weight table, not the "
            "verb."),
        Exemption(
            "templates/devlog.md",
            "Implement | Verify}}",
            "names the Verify stage in a placeholder list of stage names, "
            "not the verb."),
        Exemption(
            "templates/launch-readiness.md",
            "passed at Verify?",
            "names the Verify stage, not the verb."),
        Exemption(
            "templates/launch-readiness.md",
            "failed at Verify}}",
            "names the Verify stage, not the verb."),
        Exemption(
            "templates/verification-report.md",
            "the Verify output",
            "names the Verify stage, not the verb."),
        Exemption("governance/guardrails.md",
                   "Checked at Verify and again at ship time",
                   "names the Verify stage, not the verb."),
        Exemption("governance/guardrails.md",
                   "`verifier` and `reviewer` agents** at Verify",
                   "names the Verify stage, not the verb."),
        Exemption("governance/signals.yml",
                   "reviewer agent at Verify - judgement",
                   "names the Verify stage, not the verb."),
        Exemption("governance/guardrails.yml", "compass bdd verify",
                   "compass bdd verify is a CLI verb, not the plain verb."),
        Exemption(
            "tests/fixtures/receipt-fixture-project/governance/guardrails.yml",
            "compass bdd verify",
            "a verbatim copy of governance/guardrails.yml, restored after an "
            "earlier commit wrongly trimmed it to dodge this sweep - same "
            "text, same reason as the governance/guardrails.yml exemption "
            "above: compass bdd verify is a CLI verb, not the plain verb."),
        Exemption("cli/compass_pkg/bdd.py", "and `compass bdd verify`",
                   "compass bdd verify is a CLI verb, not the plain verb."),
        Exemption("cli/compass_pkg/bdd.py", "compass bdd verify -- <run",
                   "compass bdd verify is a CLI verb, not the plain verb."),
        Exemption("cli/compass_pkg/checks.py", "written by `compass bdd verify`",
                   "compass bdd verify is a CLI verb, not the plain verb."),
        Exemption("tests/test_bdd_optin_noop.py", "compass bdd verify",
                   "compass bdd verify is a CLI verb, not the plain verb; "
                   "found while fixing batch 7, not by the audit."),
        Exemption("tests/test_stream_c_no_new_checks_or_gates.py",
                   "reading the record `compass bdd verify` writes",
                   "compass bdd verify is a CLI verb, not the plain verb."),
        Exemption("tests/test_workflow_pins.py",
                   "the same supply-chain stance",
                   "\"supply chain\" is the established compound noun, not "
                   "the verb \"supply\" the word table retires."),
        Exemption("governance/guardrails.yml", "checked_at: [verify]",
                   "an example YAML value inside a comment, not the verb."),
        Exemption("governance/guardrails.yml", "attempts: <int>",
                   "attempts: <int> names the evidence field, not the verb "
                   "\"attempt\"."),
        Exemption("governance/presets/default/checks.yml", "compass bdd verify",
                   "compass bdd verify is a CLI verb, not the plain verb; the "
                   "preset copies the check text from governance/guardrails.yml."),
        Exemption("governance/presets/default/checks.yml", "attempts: <int>",
                   "attempts: <int> names the evidence field, not the verb "
                   "\"attempt\"; the preset copies the check text from "
                   "governance/guardrails.yml."),
        Exemption("governance/presets/default/evidence-types.yml", "attempts: <int>",
                   "attempts: <int> names the evidence field, not the verb "
                   "\"attempt\"; the preset copies the type text from "
                   "governance/guardrails.yml."),
        Exemption("governance/presets/default/vocabulary.yml", "verify",
                   "the display name of the verify stage, not the verb; the "
                   "file holds display names only."),
        Exemption(
            "tests/fixtures/receipt-fixture-project/governance/guardrails.yml",
            "checked_at: [verify]",
            "a verbatim copy of governance/guardrails.yml, restored after an "
            "earlier commit wrongly trimmed it to dodge this sweep - same "
            "text, same reason as the governance/guardrails.yml exemption "
            "above: an example YAML value inside a comment, not the verb."),
        Exemption(
            "tests/fixtures/receipt-fixture-project/governance/guardrails.yml",
            "attempts: <int>",
            "a verbatim copy of governance/guardrails.yml, restored after an "
            "earlier commit wrongly trimmed it to dodge this sweep - same "
            "text, same reason as the governance/guardrails.yml exemption "
            "above: attempts: <int> names the evidence field, not the verb "
            "\"attempt\"."),
        # The first half of a hyphenated compound noun about a chain of
        # suppliers is not the plain verb the word table replaces with
        # "give". The exemption function does not check for a hyphen right
        # after the match.
        Exemption("architecture/decisions/ADR-013-vendored-third-party-code.md",
                   "it is a supply-chain",
                   "\"supply\" opens the compound noun \"supply-chain\", "
                   "not the verb."),
        # An id prefix (ADR-016) reuses the spelling of the plain verb the
        # word table replaces with "need". The match is the second half of
        # the hyphenated identifier, so the backtick before its first half
        # does not sit immediately before the match.
        Exemption("architecture/decisions/"
                   "ADR-016-id-codes-are-part-of-the-frozen-vocabulary.md",
                   "They become `RP-REQUIRE-*`",
                   "RP-REQUIRE is an id prefix, not the verb."),
        Exemption("architecture/decisions/"
                   "ADR-016-id-codes-are-part-of-the-frozen-vocabulary.md",
                   "define `RP-FLOOR` and `RP-REQUIRE` honestly",
                   "RP-REQUIRE is an id prefix, not the verb."),
        Exemption("architecture/decisions/README.md",
                   "RP-REQUIRE-001/002, verify.analyze",
                   "RP-REQUIRE is an id prefix, not the verb."),
        Exemption("architecture/system-context.md",
                   "added by `RP-REQUIRE-003` and `RP-REQUIRE-004`",
                   "RP-REQUIRE is an id prefix, not the verb."),
        Exemption("tests/test_verify_fitness_route_promotion.py",
                   "When cross-cutting fires RP-REQUIRE-003, it appears in "
                   "fired_guardrails.",
                   "RP-REQUIRE is an id prefix, not the verb."),
        Exemption("tests/test_verify_fitness_route_promotion.py",
                   "When touches fires RP-REQUIRE-004, it appears in "
                   "fired_guardrails.",
                   "RP-REQUIRE is an id prefix, not the verb."),
        Exemption("governance/routing-policy.yml",
                   "six of the entries below carry RP-REQUIRE ids",
                   "RP-REQUIRE is an id prefix, not the verb."),
        Exemption("governance/strategies-rationale.md",
                   "[RP-REQUIRE-003] requirement:",
                   "RP-REQUIRE is an id prefix, not the verb; this is a "
                   "quoted literal string a test matched."),
        Exemption("tests/test_id_prefix_glossary.py",
                   'printed "[RP-REQUIRE-003] floor:" on screen',
                   "RP-REQUIRE is an id prefix, not the verb; a quote of "
                   "the CLI's actual printed output."),
        Exemption("governance/terminology.yml",
                   "the result. RP-REQUIRE attaches a gate",
                   "RP-REQUIRE is an id prefix, not the verb."),
        Exemption("docs/glossary.md",
                   "the result. RP-REQUIRE attaches a gate",
                   "the derived text of the same terminology.yml line - "
                   "RP-REQUIRE is an id prefix, not the verb the word table "
                   "retires."),
        Exemption("tests/test_artifact_registry.py",
                   "`RP-REQUIRE-003` already adds",
                   "RP-REQUIRE-003 is a policy rule id, not the verb the "
                   "word table retires; found while fixing batch 7, not by "
                   "the audit."),
        Exemption("tests/test_allow_marker_needs_a_reason.py",
                   "(allow-marker-supplies-its-own-reason)",
                   "the issue's own slug, an identifier (section 4), not "
                   "the verb the word table retires; found while fixing "
                   "batch 7, not by the audit."),
        Exemption("tests/test_fresh_eyes_verify_sweeps.py",
                   "(issue fresh-eyes-verify-sweeps)",
                   "the issue's own slug, an identifier (section 4), not "
                   "the verb the word table retires; found while fixing "
                   "batch 7, not by the audit."),
        Exemption("tests/test_allow_marker_needs_a_reason.py",
                   "allow-marker-supplies-its-own-reason/acceptance-criteria.md",
                   "the issue's own slug, an identifier (section 4), not "
                   "the verb the word table retires; found while fixing "
                   "batch 7, not by the audit."),
        Exemption(
            "scripts/verify-archive-quotes.py",
            "verify against the primary",
            "restates strategy S9's own defining sentence "
            "(governance/strategies.md: 'Verify against the primary record "
            "for the claim'); the audit's human review ruled this instance "
            "keeps the word (section 9, batch 6, scripts/verify-archive-"
            "quotes.py note on L27-28)."),
        Exemption(
            "templates/architecture/relations.md",
            "A change that modifies a",
            "an absorbed-into marker quoting the merge-base sentence "
            "verbatim, per PBW-F7 - not a new use of the retired word."),
        Exemption(
            "tests/test_governance_drift.py",
            "that considered RP-REQUIRE-003 and rejected it",
            "the same rule-id false match as the RP-REQUIRE exemptions "
            "above - RP-REQUIRE is an id prefix, not the verb."),
        Exemption(
            "tests/test_plugin_doc_drift.py",
            "/ `compass tdd-green` write typed test-run evidence the verify gates accept.",
            "names the verify stage's gates, the same identifier-adjacent "
            "use as \"All Verify gates\" in approaches/hotfix.md."),
        Exemption(
            "tests/test_pre_tool_hook.py",
            "A red recorded with `tdd-red --verified-by` (`TRC-R8-1`, `TRC-R8-2` hook",
            "names the real `--verified-by` CLI flag (cli/compass_pkg/"
            "tdd.py), an identifier, not the verb the word table retires."),
        Exemption(
            "tests/test_pre_tool_hook.py",
            "verified-by red plugs into.",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_pre_tool_hook.py",
            "hook blocks a production edit - the gap a verified-by red exists to fill",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_pre_tool_hook.py",
            "-2 (hook side): a recorded red (the .red marker a verified-by red",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_pre_tool_hook.py",
            "a verified-by red drops this marker",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_tdd_evidence.py",
            "`--verified-by` - instead of about the evidence layout.",
            "names the real `--verified-by` CLI flag (cli/compass_pkg/"
            "tdd.py), an identifier, not the verb the word table retires."),
        Exemption(
            "tests/test_tdd_evidence.py",
            "First-class `--verified-by` red (`R8`, `TRC-R8-2`..`R8-6`; "
            "`R8-1` hook part in test_pre_tool_hook)",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_tdd_evidence.py",
            "The green carries the `--verified-by` kind forward and binds the",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_tdd_evidence.py",
            "No smuggling - a passing command with no --verified-by records no red",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_tdd_evidence.py",
            "An unrecognised `--verified-by` kind is refused with the allowed set",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_tdd_evidence.py",
            "A `--verified-by` red still needs the guard to genuinely fail",
            "the same `--verified-by` flag name as the exemption above."),
        Exemption(
            "tests/test_printed_output_vocabulary.py",
            "RP-REQUIRE-001/002 both add verify.analyze and RP-REQUIRE-003/004 both add",
            "the same rule-id false match as the RP-REQUIRE exemptions "
            "above - RP-REQUIRE is an id prefix, not the verb."),
        Exemption(
            "tests/test_release_invariants.py",
            "added by the RP-REQUIRE-003 and RP-REQUIRE-004 floors.",
            "the same rule-id false match as the RP-REQUIRE exemptions "
            "above - RP-REQUIRE is an id prefix, not the verb."),
        Exemption(
            "tests/test_release_invariants.py",
            "RP-REQUIRE-003 and RP-REQUIRE-004 are present and use "
            "add_gate: verify.architecture.",
            "the same rule-id false match as the RP-REQUIRE exemptions "
            "above - RP-REQUIRE is an id prefix, not the verb."),
        Exemption(
            "tests/test_release_invariants.py",
            "A landed issue's test-run evidence (no attempts field) must "
            "still clear `G4`",
            "\"attempts\" names the literal `attempts` field on a TDD "
            "evidence record (cli/compass_pkg/tdd.py), an identifier, not "
            "the verb the word table retires."),
        # tests/test_terminology.py:866's test_banned_usage_in_fixture_is_flagged
        # needs every ban in governance/terminology.yml to hit at least
        # one line in this file, so a word-table match here is the same
        # planted vocabulary PBW-D2 protects, not prose to fix. Audit
        # section 9 (batch 9) reads this file line by line and lists one
        # finding, a narrative sentence; the rest is deliberate.
        Exemption(
            "tests/fixtures/terminology/banned_usage.md",
            "The dimensions were scored during Frame, checked at verify and Land",
            "planted vocabulary for governance/terminology.yml's ban list "
            "(PBW-D2), not prose."),
        Exemption(
            "tests/test_scenarios_are_executable.py",
            "a record written by `compass bdd verify`",
            "the real CLI subcommand `compass bdd verify` "
            "(cli/compass:148) - an identifier, not the verb the word "
            "table retires."),
    ),
))


# ---------------------------------------------------------------------------
# PBW-A3 - the spelling is British
# ---------------------------------------------------------------------------

# Four named forms (audit 5.3), each with the British spelling it becomes.
# "analyse/analyze" needs its own exemption logic below - the verb
# `compass analyze`, the gate `verify.analyze` and the module `analyze.py`
# keep the American spelling because they are identifiers, not prose.
_SPELLING_PATTERNS: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"\btoward\b", re.IGNORECASE), "towards"),
    (re.compile(r"\bmodeling\b", re.IGNORECASE), "Modelling"),
    (re.compile(r"\blabeled\b", re.IGNORECASE), "labelled"),
)

_ANALYZE_RE = re.compile(r"\banalyz(e|es|ed|ing|ation|ations)\b", re.IGNORECASE)


def _analyze_exempt(text: str, match: re.Match) -> bool:
    start, end = match.span()
    before = text[max(0, start - 9):start]
    if before.rstrip().endswith("compass"):
        return True
    if text[start - 1:start] in "`/.":  # a code span, a slash command, or
        return True                     # the qualified gate id verify.analyze
    if text[end:end + 3] == ".py":
        return True
    return False


def _find_spelling(span: ProseSpan) -> list[Finding]:
    findings = []
    for pattern, replacement in _SPELLING_PATTERNS:
        for match in pattern.finditer(span.text):
            findings.append(Finding(
                span.path, span.line,
                f'"{match.group(0)}" -> "{replacement}"'))
    for match in _ANALYZE_RE.finditer(span.text):
        if _analyze_exempt(span.text, match):
            continue
        replacement = match.group(0).replace("z", "s")
        findings.append(Finding(
            span.path, span.line,
            f'"{match.group(0)}" -> "{replacement}"'))
    return findings


_register(Rule(
    "PBW-A3", "The spelling is British", _find_spelling,
    exemptions=(
        # The quoted title below is the real, external organisation's own
        # name (threatmodelingmanifesto.org), spelt with the American form in
        # its own title. Respelling it would misquote the name, the same
        # protection section 4 gives a verbatim quote or an identifier.
        Exemption("cli/compass_pkg/borrowed_docs.py",
                   "The threat model asks the Threat Modeling Manifesto's",
                   "the manifesto's own name, spelt as it spells itself; "
                   "not the ordinary word."),
        Exemption("cli/compass_pkg/borrowed_docs.py",
                   "The Threat Modeling Manifesto names the failure",
                   "the manifesto's own name, spelt as it spells itself; "
                   "not the ordinary word."),
        Exemption("tests/test_stream_c_no_new_checks_or_gates.py",
                   "Modeling Manifesto's named",
                   "the manifesto's own name, spelt as it spells itself; "
                   "not the ordinary word."),
        # An evidence-id prefix carries the gate's own American spelling as
        # a machine identifier, not the ordinary word it is spelt like. The
        # exemption function recognises a backtick right before the match,
        # but the backtick here opens two segments earlier, so the
        # identifier is not caught. Swapping the one lowercase letter that
        # separates the two spellings is a no-op in the all-caps form
        # (only a lowercase instance matches), which is why the sweep's own
        # reported replacement reads identical to the original.
        Exemption("architecture/decisions/"
                   "ADR-007-conditional-gate-promotion-via-floors.md",
                   "EV-ANALYZE-ADVISORY",
                   "evidence-id prefix, a machine identifier."),
        # The same no-op case as the ADR-007 exemption above: this line names
        # the evidence-id prefix the fixture globs for, a machine
        # identifier, not the ordinary word.
        Exemption("tests/analyze/test_analyze_core.py",
                   "the `EV-ANALYZE-` prefix",
                   "evidence-id prefix, a machine identifier - same case as "
                   "the ADR-007 exemption above."),
        # Disagrees with the audit's finding for this line. The manifesto
        # this file quotes is the real, external body's own name, spelt
        # with the American form of the word - confirmed by the domain it
        # names two lines below, threatmodelingmanifesto.org, which uses
        # the same spelling. Changing the spelling would misname the source
        # the file instructs the reader not to reword.
        Exemption("templates/threat-model.md",
                   "Threat Modeling",
                   "the real name of the external manifesto this file "
                   "quotes, confirmed by threatmodelingmanifesto.org's own "
                   "spelling two lines below; not the ordinary word."),
        Exemption("cli/compass_pkg/analyze.py",
                   "id prefix `EV-ANALYZE-<task>-<ts>`",
                   "evidence-id prefix, a machine identifier - the same "
                   "class as the ADR-007 exemption above."),
        Exemption("cli/compass_pkg/analyze.py",
                   "id prefix `EV-ANALYZE-ADVISORY-<task>-<ts>`",
                   "evidence-id prefix, a machine identifier."),
        Exemption("cli/compass_pkg/analyze.py",
                   "Gate-clearing: type=consistency-check, prefix "
                   "EV-ANALYZE-<task>-<ts>",
                   "evidence-id prefix, a machine identifier."),
        Exemption("cli/compass_pkg/analyze.py",
                   "Advisory:      type=command-output,  prefix "
                   "EV-ANALYZE-ADVISORY-<task>-<ts>",
                   "evidence-id prefix, a machine identifier."),
        Exemption("cli/compass_pkg/analyze.py",
                   "--- command: analyze ---",
                   "names the CLI verb `compass analyze`, an identifier "
                   "(section 4 rule 1), not the ordinary word."),
        Exemption("cli/compass_pkg/receipt.py",
                   'is worse than a bare one: "EV-ANALYZE-signup-email-va...',
                   "evidence-id prefix, a machine identifier, inside a "
                   "worked example of a truncated one."),
        Exemption("cli/compass_pkg/receipt.py",
                   "`EV-ANALYZE-<slug>-<timestamp>` runs to 51 characters",
                   "evidence-id prefix, a machine identifier."),
        Exemption("tests/test_identifier_expansion.py",
                   "EV-ANALYZE-signup-email-va",
                   "the same evidence-id-prefix machine identifier as the "
                   "ADR-007 exemption above, truncated mid-token by the "
                   "docstring it illustrates."),
        # The same no-op case as the ADR-007 exemption above: R3's own
        # real command name, hyphenated, so the backtick right before the
        # match opens two segments earlier and the identifier is not caught.
        Exemption("evals/harness.py",
                   "`R3-analyze`",
                   "R3's own real command name, a machine identifier "
                   "- same case as the ADR-007 exemption above."),
        Exemption("tests/test_eval_harness.py",
                   "`R3-implement`, `R3-analyze`",
                   "R3's own real command name, a machine identifier "
                   "- same case as the ADR-007 exemption above."),
    ),
))


# ---------------------------------------------------------------------------
# PBW-A4 - "artifact" is the only spelling
# ---------------------------------------------------------------------------

# The one exception to British English (audit section 7): "artifact" matches
# the manifest key `artifacts:`, the verb `compass issue artifact` and the
# evidence type `artifact`, so the prose is spelled to match the identifier.
_ARTEFACT_RE = re.compile(r"\bartefacts?\b", re.IGNORECASE)


def _find_artefact(span: ProseSpan) -> list[Finding]:
    return [Finding(span.path, span.line, f'"{match.group(0)}" -> "artifact"')
            for match in _ARTEFACT_RE.finditer(span.text)]


_register(Rule("PBW-A4", '"artifact" is the only spelling', _find_artefact))


# ---------------------------------------------------------------------------
# PBW-A5 - no idiom from the table survives
# ---------------------------------------------------------------------------

# The maintainer's global CLAUDE.md table (audit 5.5), one row per idiom.
# The row below for the sign-of-a-problem sense excludes the kept two-word
# form ("code" plus that word); the row for the goes-out-of-date sense
# carries no such exception - the audit's keep list does not name it.
IDIOM_TABLE: tuple[tuple[str, str], ...] = (
    ("full citizens", "fully supported, or name what they support"),
    ("backbone", "name the function or module everything else calls"),
    ("blast radius", "what a failure affects"),
    ("load-bearing", "name what depends on it"),
    ("escape hatch", "override, opt-out"),
    ("nudge", "prompt, remind"),
    ("knobs?", "setting, settings"),
    ("accretes", "adds"),
    ("substrate", "name the layer or file underneath"),
    ("stapled on", "added separately"),
    ("cry wolf", "report false failures"),
    ("belt and braces", "a second check"),
    ("front door", "entry point"),
    ("rubber stamp", "approval without a check"),
    ("theatre", "a check that catches nothing"),
    ("safety net", "name the check"),
    ("papercuts", "small irritations"),
    ("smell", "sign of a problem"),
    ("rots?", "goes out of date"),
    ("pay back the process weight", "do the follow-up work skipped earlier"),
    ("what's in the box", "what it contains"),
)

_IDIOM_PATTERNS: tuple[tuple[re.Pattern, str], ...] = tuple(
    (re.compile(r"\b" + pattern + r"\b", re.IGNORECASE), replacement)
    for pattern, replacement in IDIOM_TABLE
)


def _idiom_exempt(path: str, text: str, match: re.Match) -> bool:
    """"code smell" is the one kept phrase this table would otherwise flag -
    every other kept term (drift, stale, ratchet, in flight, lightweight) is
    simply absent from IDIOM_TABLE, so no pattern exists to exempt it from.
    One idiom-table entry names a retired v1 risk dimension too; inside
    architecture/decisions/ it is always the dimension name an accepted
    record was decided in (ADR-023), never the idiom, so it takes the same
    exemption PBW-A1 already gives that directory."""
    if match.group(0).lower() in ("smell", "smells"):
        before = text[:match.start()].rstrip().lower()
        if before.endswith("code"):
            return True
    if (match.group(0).lower() == "blast radius"
            and path.startswith(_ADR_VOCABULARY_SKIP)):
        return True
    return False


def _find_idiom(span: ProseSpan) -> list[Finding]:
    if span.path.startswith(_RETIRED_WORD_STRUCTURAL_SKIP):
        # tests/fixtures/terminology/ plants every banned word on purpose
        # (PBW-D2), and one of the retired assessment-dimension words is also
        # on the idiom table above - the same structural skip PBW-A1 uses
        # applies here for the same reason.
        return []
    if _in_terminology_exempt_block(span):
        # PBW-D2: the same five blocks that must keep naming every banned
        # word also carry idiom-table words as part of what they ban or
        # rename - an idiom this table replaces, quoted inside a `context:`
        # explaining why a word was retired.
        return []
    findings = []
    for pattern, replacement in _IDIOM_PATTERNS:
        for match in pattern.finditer(span.text):
            if _idiom_exempt(span.path, span.text, match):
                continue
            findings.append(Finding(
                span.path, span.line,
                f'"{match.group(0)}" -> {replacement}'))
    return findings


_register(Rule(
    "PBW-A5", "No idiom from the table survives", _find_idiom,
    exemptions=(
        Exemption(
            "skills/compass-runtime/writing-voice.md",
            '"papercuts" | "what the hell is papercuts?"',
            "the term is the subject of the row, not the prose: the table "
            "quotes the jargon a cold reader stumbled on so the row can "
            "show its plain form beside it (\"a list of small "
            "irritations\", already given). Replacing it would delete the "
            "example the section exists to show, and "
            "tests/test_reply_shape_instructions.py:125-152 requires the "
            "literal word on its row."),
        Exemption(
            "templates/requirements-review.md",
            "> a knob.",
            "an absorbed-into marker quoting the merge-base sentence "
            "verbatim, per PBW-F7 - not a new use of the retired idiom."),
        Exemption(
            "tests/test_trace_rot_detection.py",
            "Scenarios: trace-rot-detection/acceptance-criteria.md",
            "the real slug of this issue - an identifier (section 4), not "
            "a v1-vocabulary use of the idiom \"rot\"."),
        Exemption(
            "tests/test_terminology.py",
            "An actual backbone, or the spine of a book, is",  # vocabulary-scan: allow - quotes test_terminology.py's own comment verbatim, which is how a substring sweep tells a deliberate mention from a live use
            "the ordinary-English sense the spine/issue-spine ban's own "  # vocabulary-scan: allow - quotes test_terminology.py's own comment verbatim, which is how a substring sweep tells a deliberate mention from a live use
            "comment gives as the example that must NOT fire - not a use "
            "of the idiom \"backbone\" this table retires."),
    ),
))


# ---------------------------------------------------------------------------
# PBW-A6 - no citation points at a path git does not distribute
# ---------------------------------------------------------------------------

# A repository-relative path to a real file, shaped generically rather than
# anchored to any particular top-level directory: one or more `segment/`
# groups (the first may open with a single dot, for a dotdir such as
# `.compass/`), ending in a filename with a recognised extension. Finding
# 10, `review-dimensions.md`: this used to open with a hard-coded
# `(?:docs/compass|\.compass/work)/` prefix, deciding by an enumerated list
# what was even worth asking git about - the thing PBW-A6's own scenario
# forbids ("resolves its judgement from git's own ignore rules, not from a
# hard-coded prefix list"). `docs/analysis/` and `docs/proposals/` are also
# gitignored (`.gitignore:6-7`) and this issue's own source document lives
# in the former; neither was ever a candidate. Every path-shaped citation of
# a real file is now offered to `git check-ignore`, which is where the real
# judgement already lived. Requiring an extension, the same shape PBW-A8's
# `_REFERENCE_RE` below uses, is deliberate: a bare directory mention such
# as ".compass/work/" names the convention, not one document a reader
# cannot open, and the widened prefix would otherwise turn every one of the
# hundreds of ordinary mentions of that convention into a reported citation.
_CITATION_RE = re.compile(
    r"`?((?:[\w.][\w-]*/)+[\w.-]+\.(?:md|py|yml|yaml|json|sh|feature))`?")


@lru_cache(maxsize=4096)
def _git_ignores(rel: str) -> bool:
    result = subprocess.run(["git", "check-ignore", "-q", rel], cwd=REPO_ROOT)
    return result.returncode == 0


def _find_citation(span: ProseSpan) -> list[Finding]:
    findings = []
    for match in _CITATION_RE.finditer(span.text):
        path = match.group(1).rstrip(".,;:'\"")
        if "<" in path or "*" in path:
            # A placeholder shape - the angle-bracket form
            # (docs/compass/<created>-<slug>/) or a shell-glob form
            # (.compass/work/*/) - names the convention, not one issue's
            # real document. A literal "*" is never a real filename, so
            # widening for it cannot mask a genuinely broken citation. git
            # check-ignore matches the literal string regardless, so this
            # is excluded rather than reported.
            continue
        if _git_ignores(path):
            findings.append(Finding(
                span.path, span.line,
                f'citation of "{path}", which git does not distribute'))
    return findings


_register(Rule(
    "PBW-A6", "No citation points at a path git does not distribute",
    _find_citation,
    exemptions=(
        Exemption(
            "docs/quickstart.md",
            ".compass/work/add-rate-limiting/manifest.yml",
            "the walkthrough's own hypothetical issue - it shows the "
            "reader where their own file will be, not a citation of a "
            "document that already exists in this repository"),
        # A path relative to the README's own directory, the same PBW-A8 gap
        # named for these four files above: git check-ignore is asked about
        # the literal string against the repository root, where the root
        # .gitignore's `/docs/compass/*/` pattern matches it - even though
        # the real file, nested under examples/<adapter>/, is tracked.
        Exemption(
            "examples/bdd-adapters/behave/README.md",
            "docs/compass/2026-08-03-reset-password/acceptance-criteria.md",
            "a path relative to this README's own directory; the real "
            "file, examples/bdd-adapters/behave/docs/compass/2026-08-03-"
            "reset-password/acceptance-criteria.md, is tracked."),
        Exemption(
            "examples/bdd-adapters/cucumber-js/README.md",
            "docs/compass/2026-08-03-reset-password/acceptance-criteria.md",
            "the same directory-relative path as the behave README's "
            "exemption above."),
        Exemption(
            "examples/bdd-adapters/godog/README.md",
            "docs/compass/2026-08-03-reset-password/acceptance-criteria.md",
            "the same directory-relative path as the behave README's "
            "exemption above."),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/README.md",
            "docs/compass/2026-08-03-reset-password/acceptance-criteria.md",
            "the same directory-relative path as the behave README's "
            "exemption above."),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/README.md",
            ".compass/work/reset-password/acceptance-criteria.feature",
            "a path relative to this README's own directory; the real "
            "file is generated at run time under examples/bdd-adapters/"
            "pytest-bdd/.compass/work/reset-password/, the same shape as "
            "this rule's docs/quickstart.md exemption above."),
        Exemption(
            "tests/test_archive_citations_resolve.py",
            ".compass/work/demo/technical-design.md",
            "the comment quotes a fixture path a test builds "
            "(`make_task([...])`), not a citation of a real record; found "
            "while fixing batch 7, not by the audit."),
        # Finding 10 narrowed `_CITATION_RE` to a real file (an extension is
        # required, the same shape as PBW-A8's `_REFERENCE_RE`), which is
        # also why the five bare-directory-mention exemptions that used to
        # sit here are gone: ".compass/work/" with nothing after it no
        # longer matches at all, so they excused nothing left to excuse.
        # `_CITATION_RE`'s extension alternation has no trailing word
        # boundary, though, so it still slices "x.pyc" down to the prefix
        # "x.py" it does recognise - the real filename in both sentences
        # below is the ".pyc" compiled-bytecode example a `.gitignore`
        # discussion worked through, not a citation of "x.py".
        Exemption(
            "governance/strategies-rationale.md", "tests/__pycache__/x.pyc",
            "the regex slices \".pyc\" down to \".py\"; the real filename "
            "is the compiled-bytecode example, not a citation."),
        Exemption(
            "tests/test_house_style.py", "tests/__pycache__/x.pyc",
            "the regex slices \".pyc\" down to \".py\"; the real filename "
            "is the compiled-bytecode example, not a citation."),
    ),
))


# ---------------------------------------------------------------------------
# PBW-A7 - a bare code carries its meaning or goes
# ---------------------------------------------------------------------------

_BARE_CODE_RE = re.compile(
    r"\b(?:G[1-5]|S\d+|TRC-\w+|DD-\d+|R\d+|MP-\d+|Inv-\d+|BR-\d+|AMB-\d+|"
    r"U-\d+|review finding \d+|probe \d+|slice \d+[a-z]?|Phase \d+)\b")

# architecture/decisions/README.md's Index and Principle-to-ADR tables are
# reference lookups keyed by id - the same shape as terminology.yml's own
# codes: section, where the code IS the row's key and its meaning sits in
# the adjacent cell. The "plain words, then the code in brackets" house
# form is a prose rule; a two-column table row is not prose in that sense.
# Narrowed to a row test, not a whole-file skip (finding 8,
# `review-dimensions.md`): every one of this rule's findings in this file is
# a table row today, so the row test costs nothing, and a future non-table
# bare code in this file is no longer silently exempt with it.
_BARE_CODE_TABLE_SKIP = "architecture/decisions/README.md"


# R1 to R9 are rival product codes. Their meaning is the product's name,
# which committed text must not carry
# (governance/decisions/2026-10-04-rival-names-never-committed.md), so no
# plain words can stand beside them; the convention is stated once in
# CLAUDE.md instead.
_RIVAL_CODE = re.compile(r"R[1-9]")


def _find_bare_code(span: ProseSpan) -> list[Finding]:
    findings = []
    for match in _BARE_CODE_RE.finditer(span.text):
        start = match.start()
        if _RIVAL_CODE.fullmatch(match.group(0)):
            continue
        # Already in the house form - "the plain words (`G5`)" - or a
        # backticked cross-reference beside a rule already stated in full.
        # Neither shape has the code opening the line: a lone backtick with
        # nothing before it is "code first, meaning after," the shape this
        # rule exists to refuse, not a house form to wave through. Finding
        # 6, `review-dimensions.md`: the old check skipped any single
        # preceding backtick, so it reported none of the 607 lines that
        # open with one - this is the corrected, narrower check.
        opens_the_line = start == 1 and span.text[0] == "`"
        if start > 0 and span.text[start - 1] in "(`" and not opens_the_line:
            continue
        if (span.path == _BARE_CODE_TABLE_SKIP
                and span.text.lstrip().startswith("|")):
            continue
        findings.append(Finding(
            span.path, span.line,
            f'bare code "{match.group(0)}" with no plain words beside it'))
    return findings


_register(Rule(
    "PBW-A7", "A bare code carries its meaning or goes", _find_bare_code,
    exemptions=(
        Exemption(
            "architecture/decisions/ADR-017-an-identifier-is-a-key-not-jargon.md",
            "the G5 guard kicked in",
            "a verbatim quote of the bad phrasing the ADR exists to fix; "
            "explaining it would destroy the example."),
        Exemption(
            "architecture/decisions/ADR-017-an-identifier-is-a-key-not-jargon.md",
            "what a G5 guard was",
            "restates the same verbatim quote."),
        Exemption(
            "tests/plain_language_check.py", "the G5 guard kicked in",
            "the module's own worked example of the wrong form the check "
            "exists to catch - the same protection as the ADR-017 "
            "exemptions above."),
        Exemption(
            "tests/plain_language_check.py",
            "G5 fired, which means a human signs off",
            "the module's own worked example of the wrong form the check "
            "exists to catch - the same protection as the ADR-017 "
            "exemptions above."),
        Exemption(
            "tests/fixtures/terminology/banned_usage.md",
            "Guardrail G1 and strategy S7 are cited by code in prose",
            "the fixture's own planted example of a bare code cited by "
            "code, not by this document - PBW-D2 protects it."),
        Exemption(
            "tests/test_terminology.py",
            '"satisfy S2" tells',
            "a deliberately bare code, the worked example of the failure "
            "mode this rule exists to catch - explaining it would destroy "
            "the example."),
        Exemption(
            "tests/test_terminology.py",
            "The range was `S[1-7]` while the file defined S1 to S12, so",
            "names the historical S-range this comment explains, the same "
            "worked-example protection as the ADR-017 exemptions above."),
        Exemption(
            "tests/test_terminology.py",
            "every strategy added after S7 sat outside the ban meant to govern it;",
            "names the historical S-range this comment explains, the same "
            "worked-example protection as the ADR-017 exemptions above."),
        Exemption(
            "tests/test_terminology.py",
            "The guardrails and strategies are where G1..G5 and S1..S14 are defined.",
            "governance/ DEFINES these codes; a definition names what it "
            "defines, the same reason architecture/decisions/README.md's "
            "table is exempt above."),
        Exemption(
            "tests/test_terminology.py",
            '"the shipped default guardrails (G1-G5)" is naming what it validates.',
            "a quoted example of a schema comment naming what it "
            "validates, the same reason as the exemption immediately "
            "above."),
        Exemption(
            "tests/test_terminology.py",
            "`governance/strategies.md` S10 - a guard is accepted on",
            "names the real strategy this test's own docstring cites by "
            "id, the same reason architecture/decisions/README.md's table "
            "is exempt above."),
        # The traceability id comment above every scenario is not prose a
        # reader loses meaning from - it is the machine-parsed marker
        # `cli/compass_pkg/bdd.py`'s extraction regex reads (bdd.py:137),
        # which needs the id to start immediately after the colon with no
        # backtick or other character in between. Wrapping it broke
        # `compass bdd extract`, caught by tests/test_bdd_adapters_all.py -
        # the marker is a real identifier (section 4), not a dangling
        # reference.
        Exemption(
            "templates/acceptance-criteria.md", "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "templates/ui-contract.md", "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "examples/bdd-adapters/behave/docs/compass/"
            "2026-08-03-reset-password/acceptance-criteria.md",
            "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "examples/bdd-adapters/cucumber-js/docs/compass/"
            "2026-08-03-reset-password/acceptance-criteria.md",
            "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "examples/bdd-adapters/godog/docs/compass/"
            "2026-08-03-reset-password/acceptance-criteria.md",
            "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/docs/compass/"
            "2026-08-03-reset-password/acceptance-criteria.md",
            "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "examples/feature-api-change/docs/compass/"
            "2026-04-21-rate-limit-search-endpoint/acceptance-criteria.md",
            "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/acceptance-criteria.md",
            "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/acceptance-criteria.md",
            "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/acceptance-criteria.md",
            "<!-- traceability id:",
            "the machine-parsed scenario-id marker `compass bdd extract` "
            "reads; see the comment above."),
        # That id's own meaning is not documented anywhere this sweep can
        # check, so it is quoted as originally written (test_pl_x3 in
        # tests/test_plain_language.py pins its presence) rather than
        # guessed at.
        Exemption(
            "architecture/decisions/ADR-015-the-vocabulary-scan-covers-code-positions.md",
            "`RCD-G5` needs that to be demonstrated",
            "RCD-G5's meaning is unverified; quoted as originally written, "
            "pinned by test_pl_x3."),
        Exemption(
            "architecture/decisions/ADR-015-the-vocabulary-scan-covers-code-positions.md",
            "mutation proof. `RCD-G5` needs the",
            "RCD-G5's meaning is unverified; quoted as originally written, "
            "pinned by test_pl_x3."),
        Exemption(
            "scripts/voice-tells.py", "TRC-F2",
            "found while building this sweep, not by the audit: the file is "
            "outside the audit's 474 files and outside every batch's "
            "pending list, so no batch owns the fix and this subtask cannot "
            "edit it (outside its own code surface). Filed separately as "
            "voice-tells-cites-trc-f2-with-no-plain-words."),
        Exemption(
            "docs/case-study-compass-rebuilt-itself.md",
            "--scenario TRC-G3",
            "the literal CLI command a person typed, inside backticks - "
            "rewording it to add plain words would misquote what was run"),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/tests/steps/"
            "test_reset_password_steps.py",
            '-k TRC-A2',
            "a literal CLI command example, inside backticks - rewording it "
            "to add plain words would misquote the command."),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/tests/steps/"
            "test_reset_password_steps.py",
            "--tags TRC-A2",
            "the same literal CLI command example, for a different runner."),
        Exemption(
            "examples/README.md", "--scenario TRC-001",
            "a literal CLI command example, inside backticks - rewording it "
            "to add plain words, or nesting a second backtick span inside "
            "it, would misquote the command."),
        Exemption(
            "examples/README.md", "evidence/green-TRC-001.json",
            "a literal filename example, inside backticks - the same "
            "reasoning as the CLI command exemption on this line."),
        Exemption(
            "examples/README.md", "evidence/red-TRC-001.json",
            "a literal filename example, inside backticks - the third on "
            "this page and the same reasoning as the two above. Added when "
            "fixups/clarity-findings merged: that branch repaired the "
            "nested backtick that had been hiding this one, so the quote "
            "only exists here post-merge."),
        Exemption(
            "templates/threat-model.md", "EV-T-TRC-B4",
            "a placeholder evidence id, inside backticks, built from the "
            "placeholder scenario id `TRC-B4` on the same row - not a real "
            "code pointing at meaning kept outside the file."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/verification-note.md",
            "evidence/green-TRC-001.json",
            "the real evidence filename `compass tdd-green` wrote for this "
            "issue's one real scenario, inside backticks - nesting a "
            "second backtick span inside it would break the filename."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/verification-note.md",
            "evidence/red-TRC-001.json",
            "the real evidence filename `compass tdd-red` wrote for this "
            "issue's one real scenario, inside backticks - nesting a "
            "second backtick span inside it would break the filename."),
        Exemption(
            "docs/quickstart.md", "`--scenario TRC-x`",
            "a placeholder scenario id, the same shape as `<test cmd>` "
            "elsewhere on this page - not a real code pointing at meaning "
            "kept outside the file"),
        Exemption(
            "templates/verification-report.md", "green-TRC-x.json",
            "the placeholder evidence filename `compass tdd-green` writes "
            "for a placeholder scenario id, the same shape as the "
            "docs/quickstart.md exemption above."),
        Exemption(
            "templates/devlog.md", "green-TRC-3.json",
            "the placeholder evidence filename `compass tdd-green` writes "
            "for a placeholder scenario id, the same shape as the "
            "docs/quickstart.md exemption above."),
        Exemption(
            "templates/manifest.yml", "TRC-001",
            "the one placeholder scenario id the file's five commented-out "
            "worked examples share (evidence, scenarios, changed_files, "
            "claims) - not a real code pointing at meaning kept outside "
            "the file, the same shape as the docs/quickstart.md exemption "
            "above."),
        Exemption(
            "governance/terminology.yml",
            "it prints 'G5 A human signs off",
            "a verbatim quote of `compass check`'s real printed output, "
            "itself the house-form example this ban describes."),
        Exemption(
            "templates/architecture/decisions/ADR-005-signals-yml-governance-file.md",
            "- Plan DD-1 (signals.yml as a separate file)",
            "an absorbed-into marker quoting the merge-base sentence "
            "verbatim, per PBW-F7 - the code is explained where it is "
            "used, not where this marker quotes it."),
        Exemption(
            "templates/architecture/relations.md",
            "(see TRC-B2).",
            "an absorbed-into marker quoting the merge-base sentence "
            "verbatim, per PBW-F7 - the code is explained where it is "
            "used (line 8, \"the scenario that added automatic "
            "triggering, `TRC-B2`\"), not where this marker quotes it."),
        Exemption(
            "cli/compass_pkg/analyze.py",
            "traceability id: TRC-A1",
            "a literal syntax example of the HTML comment the function "
            "parses, byte-identical to templates/acceptance-criteria.md's "
            "own example - not a pointer standing in for an explanation."),
        Exemption(
            "cli/compass_pkg/bdd.py",
            "traceability id: TRC-A1",
            "a literal syntax example of the HTML comment the extractor "
            "looks for, byte-identical to templates/acceptance-criteria.md's "
            "own example - not a pointer standing in for an explanation."),
        Exemption(
            "cli/compass_pkg/test_ids.py",
            "governance/strategies.md carries S7",
            "a worked example of a sentence that merely mentions a file, "
            "inside quotes - the point is that this text is prose, not a "
            "path reference, so S7 here names nothing and needs no meaning."),
        Exemption(
            "cli/compass_pkg/receipt.py",
            "Ids written by the CLI do (`EV-T-TRC-A1`)",
            "a real evidence-id shape this module itself generates and "
            "sorts on (`row[0].startswith(\"EV-T-\")` below) - not a "
            "dangling reference."),
    ),
))


# ---------------------------------------------------------------------------
# PBW-A8 - every file and command a comment names exists
# ---------------------------------------------------------------------------


# The first path segment may open with a single dot - `.compass/config.yml`
# is a real, hidden-directory path this repository has, not a relative-path
# marker, and the old pattern silently dropped the dot and checked the
# wrong (word-only) path for existence, reporting a false break on every
# reference to it. Later segments never carry a leading dot. Unlike PBW-A6's
# `_CITATION_RE`, this one needs a real filename to check for existence, so
# it stops at a recognised extension rather than swallowing a bare
# directory.
_REFERENCE_RE = re.compile(
    r"`?((?:[\w.][\w-]*/)+[\w.-]+\.(?:md|py|yml|yaml|json|sh|feature))`?")


def _reference_exempt(text: str, match: re.Match) -> bool:
    start = match.start()
    before = text[:start]
    # A URL - the path segment after the scheme is not repository-relative.
    return before.rstrip().endswith(("://", "http:", "https:")) or "://" in \
        text[max(0, start - 12):start]


@lru_cache(maxsize=1)
def _repo_top_level_names() -> frozenset[str]:
    """Every real top-level file or directory name, so a reference whose
    first segment is not one of these cannot be a repository-relative path
    at all."""
    return frozenset(p.name for p in REPO_ROOT.iterdir())


# The document names `<slug>/<document>.md` citations use (audit 5.7,
# commit 899d391) - a per-issue directory under the gitignored
# `docs/compass/`, cited by slug rather than by the path a reader's machine
# cannot open. Such a citation can never resolve in a shared tree by
# construction, so it is not the broken reference PBW-A8 exists to catch -
# `skills/compass-runtime/writing-voice.md`'s archive quotes cite six real
# past issues exactly this way.
_ISSUE_DOCUMENT_NAMES = frozenset({
    "intent.md", "acceptance-criteria.md", "requirements-review.md",
    "technical-design.md", "distribution-map.md", "manifest.yml",
    "delivery-approach.md", "verification-report.md", "devlog.md",
    "positioning.md", "launch-readiness.md", "ui-contract.md",
    "architecture-notes.md",
})


def _looks_like_issue_citation(path: str) -> bool:
    first_segment = path.split("/", 1)[0]
    document_name = path.rsplit("/", 1)[-1]
    return (first_segment not in _repo_top_level_names()
            and document_name in _ISSUE_DOCUMENT_NAMES)


def _looks_like_runtime_evidence(path: str) -> bool:
    """A path relative to the current issue's own `evidence/` directory
    (`.compass/work/<issue-slug>/evidence/...`, per `skills/compass-runtime/
    SKILL.md`'s "Where state lives" diagram) - written at run time, never
    committed at that bare location, so it is never on disk to find. A
    tracked example fixture's evidence lives nested under its own
    `.compass/work/<slug>/evidence/`, never at this top-level path, so the
    two cannot collide."""
    return path.split("/", 1)[0] == "evidence"


def _find_missing_reference(span: ProseSpan) -> list[Finding]:
    findings = []
    for match in _REFERENCE_RE.finditer(span.text):
        if _reference_exempt(span.text, match):
            continue
        path = match.group(1)
        if _looks_like_issue_citation(path) or _looks_like_runtime_evidence(path):
            continue
        if not (REPO_ROOT / path).exists() and not _exists_in_own_seed(span.path, path):
            findings.append(Finding(
                span.path, span.line, f'named path "{path}" does not exist'))
    return findings


def _exists_in_own_seed(file_path: str, path: str) -> bool:
    """An eval scenario's seed is its own small repository: a file in the
    scenario names paths relative to that seed, not to this repository."""
    parts = Path(file_path).parts
    if len(parts) < 3 or parts[:2] != ("evals", "scenarios"):
        return False
    return (REPO_ROOT / "evals" / "scenarios" / parts[2] / "seed" / path).exists()


def test_pbw_a8_a_scenario_path_resolves_only_in_its_own_seed():
    """The seed rule narrows the check to the scenario's own seed: a path
    that exists there is fine, and one that does not is still reported.
    The scenario is found at run time, so this file names none - a scenario
    id outside evals/ would reach the eval sessions' plugin copy."""
    for seed_test in sorted((REPO_ROOT / "evals" / "scenarios").glob("*/seed/tests/*.py")):
        if not (REPO_ROOT / "tests" / seed_test.name).exists():
            break
    else:
        pytest.skip("no seed test file with a name unique to its seed")
    scenario_file = str(seed_test.relative_to(REPO_ROOT))
    named = f"tests/{seed_test.name}"
    assert _exists_in_own_seed(scenario_file, named)
    assert not _exists_in_own_seed(scenario_file, "tests/no_such_seed_file.py")
    assert not _exists_in_own_seed("docs/five-minutes.md", named)
    # And the check itself still reports a path missing from the seed.
    missing = ProseSpan(scenario_file, 1, "See `tests/no_such_seed_file.py`.", "markdown")
    assert _find_missing_reference(missing)
    present = ProseSpan(scenario_file, 1, f"See `{named}`.", "markdown")
    assert not _find_missing_reference(present)


_register(Rule(
    "PBW-A8", "Every file and command a comment names exists",
    _find_missing_reference,
    exemptions=(
        Exemption(
            "docs/compass/2026-08-27-sdd-loop-spike.md", "R1",
            "every path under R1/ is inside the R1 "
            "repository, not this one - the file itself says so; the "
            "maintainer's names key holds that repository's address"),
        Exemption(
            "tests/fixtures/terminology/banned_usage.md",
            "Write the brief to `prd.md`, from `templates/prd.md`",
            "the fixture's own planted example of the retired filenames - "
            "PBW-D2 protects it; templates/prd.md is banned and never "
            "ships."),
        Exemption(
            "tests/test_terminology.py",
            "`src/api/routes/search.py` is a",
            "an illustrative example of an ordinary web-router directory "
            "this repository does not ship, not a real path reference - "
            "the comment's point is that the ban ignores it."),
        # PBW-A8's reference sweep resolves every path against the repository
        # root. Each of the five worked examples under examples/ narrates a
        # fictional application change, naming source and test files that
        # belong to the STORY's application, not to this repository - the same
        # way a textbook's code listing names a file that exists only in the
        # chapter. None of the five examples ships the application source it
        # narrates; only the Compass documents (devlog, delivery-approach,
        # technical-design, and the rest) are real, tracked files.
        Exemption(
            "examples/feature-api-change/.compass/work/"
            "rate-limit-search-endpoint/devlog.md",
            "src/api/middleware/rate_limit.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/feature-api-change/.compass/work/"
            "rate-limit-search-endpoint/devlog.md",
            "src/api/routes/search.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/feature-api-change/.compass/work/"
            "rate-limit-search-endpoint/devlog.md",
            "src/api/config.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/feature-api-change/docs/compass/"
            "2026-04-21-rate-limit-search-endpoint/technical-design.md",
            "src/api/middleware/rate_limit.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/feature-api-change/docs/compass/"
            "2026-04-21-rate-limit-search-endpoint/technical-design.md",
            "src/api/routes/search.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/feature-api-change/docs/compass/"
            "2026-04-21-rate-limit-search-endpoint/technical-design.md",
            "src/api/config.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/hotfix-regression/.compass/work/"
            "search-crash-on-empty-filter/devlog.md",
            "src/api/search/filter_compiler.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/delivery-approach.md",
            "tests/api/test_search.py",
            "a path relative to this issue's own directory - it resolves "
            "at examples/hotfix-regression/tests/api/test_search.py, "
            "which is tracked; the sweep checks every path against the "
            "repository root, the same gap the bdd-adapters exemptions "
            "above name."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/verification-report.md",
            "src/api/search/filter_compiler.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/distribution-map.md",
            "src/notifications/dispatch.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/distribution-map.md",
            "src/notifications/preferences.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/technical-design.md",
            "src/notifications/dispatch.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/technical-design.md",
            "src/notifications/store.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/technical-design.md",
            "src/notifications/api.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/technical-design.md",
            "src/notifications/preferences.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/verification-report.md",
            "tests/notifications/test_dispatch.py",
            "a path relative to this issue's own directory - it resolves "
            "at examples/initiative-new-subsystem/tests/notifications/"
            "test_dispatch.py, which is tracked."),
        Exemption(
            "examples/initiative-new-subsystem/docs/compass/"
            "2026-03-02-notifications-subsystem/verification-report.md",
            "tests/notifications/test_preferences.py",
            "a path relative to this issue's own directory - it resolves "
            "at examples/initiative-new-subsystem/tests/notifications/"
            "test_preferences.py, which is tracked."),
        Exemption(
            "examples/quick-fix-typo/.compass/work/"
            "fix-timeout-error-message/devlog.md",
            "src/api/upload.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/delivery-approach.md",
            "src/api/upload.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/verification-note.md",
            "tests/api/test_upload_errors.py",
            "a path relative to this issue's own directory - it resolves "
            "at examples/quick-fix-typo/tests/api/test_upload_errors.py, "
            "which is tracked."),
        Exemption(
            "examples/quick-fix-typo/docs/compass/"
            "2026-05-04-fix-timeout-error-message/verification-note.md",
            "src/api/upload.py",
            "the fictional application file the walkthrough narrates, not a "
            "file this repository ships."),
        Exemption(
            "docs/quickstart.md",
            ".compass/work/add-rate-limiting/manifest.yml",
            "the walkthrough's own hypothetical issue, not a real path in "
            "this repository - see the PBW-A6 exemption above for the "
            "same line"),
        Exemption(
            "tests/test_archive_citations_resolve.py",
            ".compass/work/demo/technical-design.md",
            "the comment quotes a fixture path a test builds, not a real "
            "path - see the PBW-A6 exemption above for the same line."),
        Exemption(
            "agents/architect.md", "architecture/invariants.yml",
            "a real, conditional artifact a consuming project supplies - "
            "`cli/compass_pkg/core.py`'s `_INVARIANTS_FILE` reads it \"if "
            "present\", and `tests/test_frame_loads_architecture.py` "
            "exercises both the present and absent case. Compass's own "
            "architecture/ does not ship one, which is correct, not a "
            "broken reference."),
        Exemption(
            "agents/spec-author.md", "architecture/invariants.yml",
            "the same conditional artifact reference as agents/architect.md."),
        Exemption(
            "commands/consult.md", "architecture/invariants.yml",
            "the same conditional artifact reference as agents/architect.md."),
        Exemption(
            "templates/architecture/ownership.md", "architecture/invariants.yml",
            "the same conditional artifact reference as agents/architect.md."),
        Exemption(
            "templates/architecture/relations.md", "architecture/invariants.yml",
            "the same conditional artifact reference as agents/architect.md."),
        Exemption(
            "templates/manifest.yml", "tests/api/test_ledger_export.py",
            "the template's own worked example of a scenarios: entry, not a "
            "file this repository ships - the same shape as the "
            "docs/quickstart.md exemptions above."),
        Exemption(
            "templates/manifest.yml", "src/api/ledger_export.py",
            "the template's own worked example of a changed_files: entry, "
            "not a file this repository ships."),
        Exemption(
            "examples/bdd-adapters/behave/README.md",
            "docs/compass/2026-08-03-reset-password/acceptance-criteria.md",
            "a path relative to this README's own directory - it resolves "
            "at examples/bdd-adapters/behave/docs/compass/2026-08-03-"
            "reset-password/acceptance-criteria.md, which is tracked; the "
            "sweep checks every path against the repository root."),
        Exemption(
            "examples/bdd-adapters/behave/README.md",
            "features/steps/reset_password_steps.py",
            "a path relative to this README's own directory - it resolves "
            "at examples/bdd-adapters/behave/features/steps/"
            "reset_password_steps.py, which is tracked."),
        Exemption(
            "examples/bdd-adapters/cucumber-js/README.md",
            "docs/compass/2026-08-03-reset-password/acceptance-criteria.md",
            "the same directory-relative path as the behave README's "
            "exemption above; it resolves under this adapter's own "
            "docs/compass/2026-08-03-reset-password/."),
        Exemption(
            "examples/bdd-adapters/godog/README.md",
            "docs/compass/2026-08-03-reset-password/acceptance-criteria.md",
            "the same directory-relative path as the behave README's "
            "exemption above; it resolves under this adapter's own "
            "docs/compass/2026-08-03-reset-password/."),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/README.md",
            "docs/compass/2026-08-03-reset-password/acceptance-criteria.md",
            "the same directory-relative path as the behave README's "
            "exemption above; it resolves under this adapter's own "
            "docs/compass/2026-08-03-reset-password/."),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/README.md",
            ".compass/work/reset-password/acceptance-criteria.feature",
            "a path relative to this README's own directory - it resolves "
            "at examples/bdd-adapters/pytest-bdd/.compass/work/"
            "reset-password/acceptance-criteria.feature, which is "
            "generated at run time, the same shape as the runtime-evidence "
            "exemption this rule already carries for a bare evidence/ path."),
        Exemption(
            "examples/bdd-adapters/pytest-bdd/README.md",
            "tests/steps/test_reset_password_steps.py",
            "a path relative to this README's own directory - it resolves "
            "at examples/bdd-adapters/pytest-bdd/tests/steps/"
            "test_reset_password_steps.py, which is tracked."),
        Exemption(
            "tests/test_architect_lens.py", "architecture/invariants.yml",
            "the same conditional artifact reference as agents/architect.md; "
            "found while fixing batch 7, not by the audit."),
        Exemption(
            "tests/test_frame_loads_architecture.py", "architecture/invariants.yml",
            "the same conditional artifact reference as agents/architect.md; "
            "found while fixing batch 7, not by the audit."),
        # writing-style-sweep-drops-the-leading-dot-on-a-dotdir-citation was
        # fixed at the source: `_REFERENCE_RE` above now allows a leading dot
        # on the first path segment, so a `.compass/config.yml` citation
        # checks the real path rather than the word-only one. The four named
        # exemptions this filed defect needed no longer find anything and
        # were dead (finding 9, `review-dimensions.md`); removed rather than
        # left to accumulate.
        # test_anthropic_aligned_names.py's own module docstring is a "Was |
        # Is" rename table (ADR-023): the five retired .md filenames it names
        # in the "Was" column no longer exist by design, the same shape as
        # the ADR-019 stub references below. Found while fixing batch 7, not
        # by the audit.
        Exemption("tests/test_anthropic_aligned_names.py", "agents/navigator.md",
                   "the rename table's own retired filename; historical."),
        Exemption("tests/test_anthropic_aligned_names.py", "agents/product-lens.md",
                   "the rename table's own retired filename; historical."),
        Exemption("tests/test_anthropic_aligned_names.py", "agents/marketing-lens.md",
                   "the rename table's own retired filename; historical."),
        Exemption("tests/test_anthropic_aligned_names.py", "agents/architect-lens.md",
                   "the rename table's own retired filename; historical."),
        Exemption("tests/test_anthropic_aligned_names.py", "commands/roundtable.md",
                   "the rename table's own retired filename; historical."),
        # These two stub files existed only for the 3.x cycle and were
        # removed at the next major version, per this ADR's own rule - a
        # historical reference, not a stale one.
        Exemption("architecture/decisions/"
                   "ADR-019-retired-names-carry-redirects-once-there-are-adopters.md",
                   "commands/triage.md",
                   "historical: removed at the next major version, as this "
                   "ADR's own rule says."),
        Exemption("architecture/decisions/"
                   "ADR-019-retired-names-carry-redirects-once-there-are-adopters.md",
                   "commands/wireframe.md",
                   "historical: removed at the next major version, as this "
                   "ADR's own rule says."),
        # The retired narrative-guard test module is the file this ADR
        # decides to delete; every mention of it names the file being
        # retired, not a live reference.
        Exemption("architecture/decisions/"
                   "ADR-021-a-release-narrative-guard-retires-with-its-release.md",
                   "tests/test_v1_2_narrative.py",
                   "the file this ADR retires; the citation is historical."),
        # The manifest schema's pre-rename filename was the schema's name
        # before this ADR renamed it; the citation describes the pre-rename
        # state on purpose.
        Exemption("architecture/decisions/ADR-022-the-issue-record-is-a-manifest.md",
                   "schemas/task.schema.json",
                   "names the schema's pre-rename filename; historical."),
        # A hypothetical example test in a commented-out sample entry - it
        # was never meant to exist.
        Exemption("governance/quarantine.yml",
                   "tests/api/test_export.py",
                   "a hypothetical example path in a commented-out sample."),
        Exemption("governance/strategies-rationale.md",
                   "tests/__pycache__/x.pyc",
                   "a hypothetical example path; the extension list stops "
                   "the match one character short of the real suffix."),
        Exemption("tests/test_docs_cite_live_tests.py",
                   "tests/test_v1_2_narrative.py",
                   "the retired test file this guard's own example names; "
                   "it does not exist on purpose - found while fixing "
                   "batch 7, not by the audit."),
        Exemption("tests/test_docs_cite_live_tests.py",
                   "tests/test_ledger_export.py",
                   "a worked-example path that was never meant to exist, "
                   "named by this file's own docstring as the contrast "
                   "case; found while fixing batch 7, not by the audit."),
        Exemption("tests/test_house_style.py",
                   "tests/__pycache__/x.pyc",
                   "the same hypothetical example path and the same "
                   "one-character-short match as the "
                   "governance/strategies-rationale.md exemption above."),
        Exemption("tests/test_hotfix_181_false_blocks.py",
                   ".github/workflows/ci.yml",
                   "a hypothetical example path illustrating the command "
                   "shape the hook must classify, not a citation of the "
                   "repository's real workflow file (.github/workflows/"
                   "compass.yml)."),
        Exemption("tests/test_install_plugin_detection.py",
                   ".claude/settings.json",
                   "the file install.sh writes into a --project temp "
                   "directory the test creates, not a path this repository "
                   "ships."),
        Exemption("tests/test_hook_guards_only_its_project.py",
                   "src/app.py",
                   "a hypothetical example path illustrating a relative "
                   "redirect target, not a file this repository ships."),
        Exemption("tests/test_migrate_to_docs_compass.py",
                   "commands/technical-design.md",
                   "the docstring's own point: this path does not exist - "
                   "it is the wrong rewrite the bug produced, named to "
                   "explain the defect."),
        Exemption("tests/test_pre_tool_hook.py",
                   '"src/app.py" to avoid this exemption.',
                   "the fixture target path the test creates under a temp "
                   "directory, not a file this repository ships."),
        Exemption("tests/test_pre_tool_hook.py",
                   '"src/app.py" - no "test" component anywhere in the path.',
                   "the same fixture target path as the exemption above."),
        # A rejected alternative's hypothetical path - it does not exist
        # because the alternative was never built, which is the point of
        # naming it in the Alternatives table.
        Exemption("architecture/decisions/ADR-008-cross-task-derived-artifacts.md",
                   ".compass/cache/system-spec.json",
                   "a rejected alternative's hypothetical path; it was "
                   "never built."),
        # The regex this rule matches on starts at `[\w]`, so it cannot
        # include a leading `.` or `$`. Each entry below names a real
        # citation the regex mis-slices, found while fixing batch 6
        # (`scripts/` and `hooks/`); none is a broken reference in the text.
        Exemption(
            "hooks/post-tool.sh", "claude/settings.json",
            "the regex does not match a leading '.'; the real path is "
            ".claude/settings.json, an adopter's own settings file."),
        Exemption(
            "hooks/post-tool.sh", "CLAUDE_PROJECT_DIR/hooks/post-tool.sh",
            "the regex does not match a leading '$'; "
            "$CLAUDE_PROJECT_DIR/hooks/post-tool.sh is a real path once the "
            "shell variable expands."),
        Exemption(
            "hooks/pre-tool.sh", "claude/settings.json",
            "the regex does not match a leading '.'; the real path is "
            ".claude/settings.json, an adopter's own settings file."),
        Exemption(
            "hooks/pre-tool.sh", "CLAUDE_PROJECT_DIR/hooks/pre-tool.sh",
            "the regex does not match a leading '$'; "
            "$CLAUDE_PROJECT_DIR/hooks/pre-tool.sh is a real path once the "
            "shell variable expands."),
        Exemption(
            "hooks/pre-tool.sh", "src/app.py",
            "an illustrative example path in a comment, not a citation of a "
            "file in this repository."),
        Exemption(
            "hooks/pre-tool.sh", "github/workflows/ci.yml",
            "a generic illustrative filename pair (with docker-compose.yml), "
            "not a citation of a file in this repository; kept per the "
            "audit's own replacement text."),
        Exemption(
            "hooks/stop.sh", "claude/settings.json",
            "the regex does not match a leading '.'; the real path is "
            ".claude/settings.json, an adopter's own settings file."),
        Exemption(
            "hooks/stop.sh", "CLAUDE_PROJECT_DIR/hooks/stop.sh",
            "the regex does not match a leading '$'; "
            "$CLAUDE_PROJECT_DIR/hooks/stop.sh is a real path once the "
            "shell variable expands."),
        Exemption(
            "scripts/install.sh", "claude/settings.json",
            "the regex does not match a leading '.'; the real path is "
            ".claude/settings.json (or ~/.claude/settings.json), the "
            "install destination, not a path this repository tracks."),
        Exemption(
            "scripts/integrate.sh", "lib/compass-python.sh",
            "a shellcheck `source=` directive, resolved relative to the "
            "sourcing file's own directory (scripts/), not to the "
            "repository root; the real file is scripts/lib/compass-python.sh."),
        Exemption(
            "scripts/multiagent.sh", "lib/compass-python.sh",
            "a shellcheck `source=` directive, resolved relative to the "
            "sourcing file's own directory (scripts/), not to the "
            "repository root; the real file is scripts/lib/compass-python.sh."),
        Exemption(
            "cli/compass_pkg/migrate.py", "commands/technical-design.md",
            "the path's non-existence is the point of the sentence - it "
            "names the wrong path a filename-only rewrite would produce, "
            "as a worked example of the bug this function avoids."),
    ),
))


# ---------------------------------------------------------------------------
# PBW-A9 - no sentence is left broken by an earlier find-and-replace
# ---------------------------------------------------------------------------

# Immediate repetition, allowing punctuation such as a bracket between the
# two occurrences - a word restated in brackets right after itself is this
# shape, one of the audit's own named passages (5.10).
_DOUBLED_WORD_RE = re.compile(r"\b(\w+)\b[\s(]+\1\b", re.IGNORECASE)

# The audit's own named passages (5.10) that a word-level check cannot see,
# because the repeated word is not adjacent to itself.
KNOWN_BROKEN_PHRASES: tuple[str, ...] = (
    "five roles read through five roles",
    "Architectural architecture checks",
    "agent multiagent",
    "delivery delivery approach",
)


def _find_doubled_word(span: ProseSpan) -> list[Finding]:
    findings = []
    for match in _DOUBLED_WORD_RE.finditer(span.text):
        findings.append(Finding(
            span.path, span.line, f'doubled text "{match.group(0)}"'))
    for phrase in KNOWN_BROKEN_PHRASES:
        if phrase.lower() in span.text.lower():
            findings.append(Finding(
                span.path, span.line, f'broken passage "{phrase}"'))
    return findings


_register(Rule(
    "PBW-A9", "No sentence is left broken by an earlier find-and-replace",
    _find_doubled_word,
    exemptions=(
        # The doubled-word pattern matches any repeated \w+ token, including
        # two adjacent numbers - a date immediately followed by a time whose
        # hour repeats the day is not a doubled English word, and rewording a
        # timestamp to dodge the pattern would be an edit for the sweep's own
        # convenience rather than for clarity.
        Exemption(
            "examples/hotfix-regression/.compass/work/"
            "search-crash-on-empty-filter/devlog.md",
            "2026-05-11 11:",
            "a date immediately followed by a time starting with the same "
            "number, not a doubled word."),
        Exemption(
            "examples/hotfix-regression/docs/compass/"
            "2026-05-11-search-crash-on-empty-filter/delivery-approach.md",
            "2026-05-11 11:",
            "a date immediately followed by a time starting with the same "
            "number, not a doubled word."),
    ),
))


# ---------------------------------------------------------------------------
# PBW-A10 - a stated count matches the thing it counts
# ---------------------------------------------------------------------------

_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
    "twenty": 20,
}


def _as_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token.lower())


def _count_hooks() -> int:
    data = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text())
    commands = set()
    for entries in data["hooks"].values():
        for entry in entries:
            for hook in entry.get("hooks", []):
                commands.add(hook["command"].rsplit("/", 1)[-1])
    return len(commands)


def _count_releasing_version_locations() -> int:
    """The row count of step 1's own table - every `| ... | ... |` line
    between the header separator and the next blank line. Not every row
    opens with a backtick (the `docs/install-smoke-test.md` row opens with
    "The expected"), so the count is rows, not rows-that-start-with-code."""
    text = (REPO_ROOT / "docs" / "releasing.md").read_text()
    section = text.split("Bump the version", 1)[1].split("**And one more", 1)[0]
    rows = [line for line in section.splitlines()
            if line.strip().startswith("|") and "---" not in line]
    return len(rows) - 1  # the header row is not a location


def _count_methodology_commands() -> int:
    return len(list((REPO_ROOT / "commands").glob("*.md")))


def _count_terminology_exempt_files() -> int:
    """The file count the two path-PREFIX entries in `scan.exempt` hide
    between them - what the comment above that list calls "197 tracked
    files" (really 30). A single named file such as
    `templates/architecture/decisions/README.md` is a different kind of
    entry: it names one file rather than hiding a directory's worth, so it
    is not part of the count the comment is about."""
    tracked = set(_git_ls_files())
    total = 0
    for entry in yaml.safe_load(TERMINOLOGY_PATH.read_text())["scan"]["exempt"]:
        entry = str(entry)
        if entry in tracked:
            continue
        if entry.endswith("/"):
            total += len(subprocess.run(
                ["git", "ls-files", entry], cwd=REPO_ROOT,
                capture_output=True, text=True, check=True
            ).stdout.splitlines())
        else:
            directory, _, fragment = entry.rpartition("/")
            total += sum(1 for f in subprocess.run(
                ["git", "ls-files", directory + "/"], cwd=REPO_ROOT,
                capture_output=True, text=True, check=True
            ).stdout.splitlines() if fragment in f)
    return total


def _count_landed_by_relaxes() -> int:
    from compass_pkg import landed_by
    return len(landed_by.LANDED_BY_RELAXES)


def _count_add_parser_calls() -> int:
    text = (REPO_ROOT / "cli" / "compass").read_text()
    return len(re.findall(r"\badd_parser\(", text))


@dataclass(frozen=True)
class _CountClaim:
    name: str
    file: str
    pattern: re.Pattern
    source: Callable[[], int]


COUNT_REGISTRY: tuple[_CountClaim, ...] = (
    _CountClaim("hooks", "docs/quickstart.md",
                re.compile(r"\b(\w+)\s+hooks?\b", re.IGNORECASE), _count_hooks),
    _CountClaim("hooks", "docs/security.md",
                re.compile(r"\b(\w+)\s+hooks?\b", re.IGNORECASE), _count_hooks),
    _CountClaim("hooks", "docs/safety-contract.md",
                re.compile(r"\b(\w+)\s+hooks?\b", re.IGNORECASE), _count_hooks),
    _CountClaim("hooks", "docs/install-smoke-test.md",
                re.compile(r"\b(\w+)\s+hooks?\b", re.IGNORECASE), _count_hooks),
    _CountClaim("version locations", "docs/releasing.md",
                re.compile(r"\b(\w+)\s+version locations?\b", re.IGNORECASE),
                _count_releasing_version_locations),
    _CountClaim("primary user commands", "docs/methodology.md",
                re.compile(r"\b(\w+)\s+primary user commands?\b", re.IGNORECASE),
                _count_methodology_commands),
    _CountClaim("tracked files", "governance/terminology.yml",
                re.compile(r"\b(\w+)\s+tracked files?\b", re.IGNORECASE),
                _count_terminology_exempt_files),
    _CountClaim("relaxed checks", "cli/compass_pkg/landed_by.py",
                re.compile(r"\bexactly the (\w+)\b", re.IGNORECASE),
                _count_landed_by_relaxes),
    _CountClaim("add_parser calls", "cli/compass_pkg/terminal.py",
                re.compile(r"\b(\w+)\s*`?\s*add_parser`?\s*calls?\b",
                           re.IGNORECASE),
                _count_add_parser_calls),
)


# The files the registry already watches. A new counted claim inside one of
# THESE documents, about a thing the registry already tracks elsewhere in the
# same file, is scope creep the registry should have a row for. A mention of
# the same noun in a file the registry has never claimed - "the two hooks
# [that call this module]" in cli/compass_pkg/issue_layout.py, a different
# count of a different subset - is not: policing every noun the registry
# happens to share a word with, repository-wide, is the false-positive class
# `PBW-E3` warns against, not the drift `PBW-A10` exists to catch.
_REGISTRY_FILES = frozenset(row.file for row in COUNT_REGISTRY)


def _find_count_claim(span: ProseSpan) -> list[Finding]:
    if span.path not in _REGISTRY_FILES:
        return []
    findings = []
    # Several rows can share one pattern - four files all claim a hook count
    # with the identical "\b(\w+)\s+hooks?\b" regex. Matching every row against
    # every span would report this file's own correctly-registered claim as
    # belonging to the other three files' rows too. So: match each pattern at
    # most once per span, against the row registered for THIS file if one
    # exists, and only fall through to "no row for this file" when it does not.
    seen_patterns: set[re.Pattern] = set()
    for row in COUNT_REGISTRY:
        if row.pattern in seen_patterns:
            continue
        own_row = next(
            (r for r in COUNT_REGISTRY
             if r.pattern is row.pattern and r.file == span.path), None)
        for match in row.pattern.finditer(span.text):
            stated = _as_number(match.group(1))
            if stated is None:
                continue
            if own_row is None:
                findings.append(Finding(
                    span.path, span.line,
                    f'counted claim "{match.group(0)}" about "{row.name}" '
                    f'has no row in the registry for this file'))
                continue
            actual = own_row.source()
            if stated != actual:
                findings.append(Finding(
                    span.path, span.line,
                    f'"{match.group(0)}" states {stated}, the source counts '
                    f'{actual}'))
        seen_patterns.add(row.pattern)
    return findings


_register(Rule("PBW-A10", "A stated count matches the thing it counts",
               _find_count_claim,
               # Finding 11: `_find_count_claim` itself returns early unless
               # `span.path` is one of `_REGISTRY_FILES` - naming that here
               # too, rather than a wider guess, is what keeps this honest.
               reach=lambda path: path in _REGISTRY_FILES))


# ---------------------------------------------------------------------------
# PBW-B7 - no document holds a changelog, a version banner or a dated count
# ---------------------------------------------------------------------------

_DATED_COUNT_RE = re.compile(
    r"\b\d+\s*(?:->|→)\s*\d+\s+on\s+\d{4}-\d{2}-\d{2}\b")
_CHANGELOG_HEADING_RE = re.compile(
    r"^#+\s*(Changelog|Version History|Revision History)\b", re.I | re.M)


def _find_changelog(span: ProseSpan) -> list[Finding]:
    findings = []
    for match in _DATED_COUNT_RE.finditer(span.text):
        findings.append(Finding(
            span.path, span.line, f'dated count history "{match.group(0)}"'))
    if _CHANGELOG_HEADING_RE.match(span.text):
        findings.append(Finding(
            span.path, span.line, f'changelog heading "{span.text.strip()}"'))
    return findings


_register(Rule("PBW-B7", "No document holds a changelog, a version banner "
               "or a dated count", _find_changelog))


# ---------------------------------------------------------------------------
# PBW-C3 - a CLI module's header describes that module
# ---------------------------------------------------------------------------

# The three literal markers the entry point's copied header carries into
# every module under cli/compass_pkg/ (audit 5.6): the banner naming
# cli/compass itself, the orphaned DoD-checklist-regex comment with no regex
# after it, and the rework-scan comment, which belongs only in rework.py.
_ENTRY_POINT_BANNER = "compass - the Compass CLI"
_DOD_REGEX_MARKER = "Regex to match a DoD checklist item"
_REWORK_SCAN_MARKER = "command: rework-scan"


def _find_cli_module_header(span: ProseSpan) -> list[Finding]:
    if span.path == "cli/compass":
        return []  # the entry point's own header describes itself
    if not span.path.startswith("cli/compass_pkg/"):
        return []
    findings = []
    if _ENTRY_POINT_BANNER in span.text:
        findings.append(Finding(
            span.path, span.line,
            "module header still describes the entry point"))
    if _DOD_REGEX_MARKER in span.text:
        findings.append(Finding(
            span.path, span.line,
            "orphaned DoD-checklist-regex comment, with no regex after it"))
    if _REWORK_SCAN_MARKER in span.text and span.path != "cli/compass_pkg/rework.py":
        findings.append(Finding(
            span.path, span.line,
            "rework-scan comment survives outside rework.py"))
    return findings


_register(Rule("PBW-C3", "A CLI module's header describes that module",
               _find_cli_module_header,
               # Finding 11: mirrors `_find_cli_module_header`'s own two
               # early returns - `cli/compass` describes itself, and nothing
               # outside `cli/compass_pkg/` is a candidate at all.
               reach=lambda path: path.startswith("cli/compass_pkg/")))


# ---------------------------------------------------------------------------
# PBW-C4 - a copied block is fixed the same way in every file that holds it
# ---------------------------------------------------------------------------

# The blocks copied across test files (audit 5.6), matched by the
# distinctive phrase `git grep` finds each one by. The fifth is the
# stage-key rename's own copied block, missed by the first four and found
# by a second review reading `tests/derive/test_derive_system_spec.py:18-23`
# - the same shape as the vocabulary-rename block above it, for a different
# rename, and fixed the same way.
COPIED_BLOCK_MARKERS: tuple[str, ...] = (
    "vocabulary rename landed on 2026-08-25",
    "moved to --verbose",
    "moved next door",
    "only where they are looked for widened",
    "The stage keys moved on 2026-08-24",
)


def _find_copied_block(span: ProseSpan) -> list[Finding]:
    if not span.path.startswith("tests/"):
        return []
    findings = []
    for marker in COPIED_BLOCK_MARKERS:
        if marker in span.text:
            findings.append(Finding(
                span.path, span.line, f'copied block "{marker}" survives'))
    return findings


_register(Rule("PBW-C4", "A copied block is fixed the same way in every "
               "file that holds it", _find_copied_block,
               exemptions=(
                   Exemption(
                       "tests/test_writing_style.py",
                       "The stage keys moved on 2026-08-24",
                       "this rule's own test names the marker's exact "
                       "opening phrase to prove the marker catches it - not "
                       "a second live copy of the block."),
               ),
               # Finding 11: mirrors `_find_copied_block`'s own early
               # return - nothing outside `tests/` is a candidate.
               reach=lambda path: path.startswith("tests/")))


# ---------------------------------------------------------------------------
# PBW-C5 - a test docstring says what the file tests and cites its issue by
# slug
# ---------------------------------------------------------------------------

# The wrong form this rule refuses: docs/compass/<date>-<slug>/<doc>.md. The
# right form, <slug>/<doc>.md, has no docs/compass/ prefix and no date, so it
# never matches this pattern - nothing to exempt.
_OLD_STYLE_CITATION_RE = re.compile(
    r"\bdocs/compass/\d{4}-\d{2}-\d{2}-[\w-]+/[\w.-]+\b")


def _find_docstring_shape(span: ProseSpan) -> list[Finding]:
    if span.kind != "docstring" or not span.path.startswith("tests/"):
        return []
    findings = []
    for match in _OLD_STYLE_CITATION_RE.finditer(span.text):
        findings.append(Finding(
            span.path, span.line,
            f'citation "{match.group(0)}" is not in the <slug>/<document>.md '
            f'form'))
    for match in _BARE_CODE_RE.finditer(span.text):
        start = match.start()
        if _RIVAL_CODE.fullmatch(match.group(0)):
            continue
        if start > 0 and span.text[start - 1] in "(`":
            continue
        findings.append(Finding(
            span.path, span.line,
            f'bare code "{match.group(0)}" with no plain words beside it'))
    return findings


_register(Rule("PBW-C5", "A test docstring says what the file tests and "
               "cites its issue by slug", _find_docstring_shape,
               exemptions=(
                   Exemption(
                       "tests/plain_language_check.py",
                       "the G5 guard kicked in",
                       "the module's own worked example of the wrong form "
                       "the check exists to catch, same protection as the "
                       "PBW-A7 exemption for this line."),
                   Exemption(
                       "tests/plain_language_check.py",
                       "G5 fired, which means a human signs off",
                       "the module's own worked example of the wrong form "
                       "the check exists to catch, same protection as the "
                       "PBW-A7 exemption for this line."),
                   Exemption(
                       "tests/test_terminology.py",
                       "`governance/strategies.md` S10 - a guard is accepted on",
                       "names the real strategy this docstring cites by "
                       "id, same protection as the PBW-A7 exemption for "
                       "this line."),
               ),
               # Finding 11: mirrors `_find_docstring_shape`'s own guard -
               # only a `tests/*.py` file yields a `docstring`-kind span at
               # all, so nothing else is a candidate.
               reach=lambda path: (path.startswith("tests/")
                                    and path.endswith(".py"))))


def test_pbw_a1_no_retired_word_in_prose_comments_or_docstrings():
    """The retired-word sweep is silent over every file not yet on a
    pending list. `PBW-A1`."""
    report = run_sweep(RULES["PBW-A1"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_a2_the_shorter_word_stands():
    """The word-table sweep is silent over every file not yet on a pending
    list. `PBW-A2`."""
    report = run_sweep(RULES["PBW-A2"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_a3_the_spelling_is_british():
    """The spelling sweep is silent over every file not yet on a pending
    list. `PBW-A3`."""
    report = run_sweep(RULES["PBW-A3"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_a4_artifact_is_the_only_spelling():
    """The spelling sweep reports no occurrence of the retired e-spelling.
    `PBW-A4`."""
    report = run_sweep(RULES["PBW-A4"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_a5_no_idiom_from_the_table():
    """The idiom sweep is silent over every file not yet on a pending list,
    and never fires on a kept term. `PBW-A5`."""
    report = run_sweep(RULES["PBW-A5"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_a6_no_citation_of_an_undistributed_path():
    """The citation sweep is silent over every file not yet on a pending
    list. `PBW-A6`."""
    report = run_sweep(RULES["PBW-A6"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_a6_resolves_every_path_shaped_citation_not_a_hard_coded_list():
    """Finding 10, `review-dimensions.md`: the old `_CITATION_RE` only
    offered `docs/compass/` and `.compass/work/` citations to
    `git check-ignore`, so a citation of a gitignored path under any other
    directory - this issue's own `docs/analysis/` source among them - was
    never a candidate. Every path-shaped citation is a candidate now."""
    span = ProseSpan(
        "t.md", 1,
        "see `docs/analysis/2026-09-11-writing-style-audit.md` for detail.",
        "markdown")
    findings = _find_citation(span)
    assert findings, (
        "a citation of a gitignored path outside the old two prefixes "
        "must be reported")
    assert "docs/analysis/2026-09-11-writing-style-audit.md" in findings[0].detail


# A high-water mark, in the same shape as the retired `PENDING_PATHS_HIGH_WATER`
# this issue already removed once every audited file was corrected - except
# this one was never audited. Narrowing `_find_bare_code` to what its own
# comment says (finding 6, `review-dimensions.md`) stopped it waving through
# every line that opens with a backticked bare code, and 507 of those predate
# this issue, spread across 87 files this issue's nine batches never touched -
# dominated by this repository's `TRC-*`-first test-docstring convention. That
# is a real, pre-existing defect, not a regression this fix introduces, and
# fixing 507 lines across 87 files is its own issue, filed by slug, not a
# review fixup to this mechanism. The mark may only fall, never rise: a new
# instance cannot hide inside it, and `_find_bare_code`'s own correctness is
# still proven directly, by the planted breach below and by `PBW-E1`'s fixture
# proof, neither of which this mark loosens.
PBW_A7_LINE_OPENING_BACKTICK_HIGH_WATER = 507


def test_pbw_a7_a_bare_code_carries_its_meaning():
    """The bare-code sweep is silent over every file not yet on a pending
    list, or on the finding-6 high-water mark above it. `PBW-A7`."""
    report = run_sweep(RULES["PBW-A7"], scanned_paths())
    assert len(report.findings) <= PBW_A7_LINE_OPENING_BACKTICK_HIGH_WATER, (
        f"PBW-A7 now reports {len(report.findings)}, above its high-water "
        f"mark of {PBW_A7_LINE_OPENING_BACKTICK_HIGH_WATER} - a new "
        f"line-opening bare code was added rather than fixed:\n"
        + report.render())
    assert report.files_scanned > 0


def test_pbw_a7_a_line_opening_backtick_is_not_the_house_form():
    """A backtick that opens the line is "code first, meaning after" - the
    shape `PBW-A7` exists to refuse - not the house form ("the plain words
    (`G5`)") and not a cross-reference beside a rule already stated. Finding
    6, `review-dimensions.md`: the old check skipped on any single preceding
    backtick, so it reported none of these."""
    opens_the_line = ProseSpan(
        "t.md", 1, "`S11` says measure before arguing.", "markdown")
    assert _find_bare_code(opens_the_line), (
        "a line-opening bare code must be reported")

    house_form = ProseSpan(
        "t.md", 1, "the plain words (`G5`).", "markdown")
    assert not _find_bare_code(house_form), (
        "the house form must stay exempt")

    house_form_list = ProseSpan(
        "t.md", 1, "(`TRC-B6`, `DD-4`) both apply.", "markdown")
    assert not _find_bare_code(house_form_list), (
        "a house-form list of codes must stay exempt")

    mid_sentence_citation = ProseSpan(
        "t.md", 1, "cites `governance/strategies.md` `S11` directly.", "markdown")
    assert not _find_bare_code(mid_sentence_citation), (
        "a backtick beside another citation, not opening the line, is "
        "unaffected by this narrowing")


def test_pbw_a7_the_readme_skip_is_a_row_test_not_a_whole_file_skip():
    """`_BARE_CODE_TABLE_SKIP` only exempts a table row in
    `architecture/decisions/README.md`, not the whole file. Finding 8,
    `review-dimensions.md`: every finding there today is a table row, so
    narrowing costs nothing - but a non-table bare code in that same file
    must still be caught."""
    table_row = ProseSpan(
        _BARE_CODE_TABLE_SKIP, 43,
        "| [ADR-001](ADR-001-x.md) | x | accepted | Inv-1 (readings) |",
        "markdown")
    assert not _find_bare_code(table_row), (
        "a table row in the exempted file must stay exempt")

    prose_line = ProseSpan(
        _BARE_CODE_TABLE_SKIP, 12,
        "`Inv-1` is not a table row here.", "markdown")
    assert _find_bare_code(prose_line), (
        "a non-table bare code in the exempted file must still be caught - "
        "the skip is a row test, not a whole-file skip")


def test_pbw_a8_every_named_file_and_command_exists():
    """The reference sweep is silent over every file not yet on a pending
    list. `PBW-A8`."""
    report = run_sweep(RULES["PBW-A8"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_a9_no_doubled_word_or_phrase():
    """The doubled-word sweep is silent over every file not yet on a
    pending list. `PBW-A9`."""
    report = run_sweep(RULES["PBW-A9"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_a10_a_stated_count_matches_its_source():
    """The count sweep is silent over every file not yet on a pending list -
    the registry's own claims are all in files pending at this stage.
    `PBW-A10`."""
    report = run_sweep(RULES["PBW-A10"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_b7_no_changelog_or_dated_count():
    """The changelog sweep is silent over every file not yet on a pending
    list. `PBW-B7`."""
    report = run_sweep(RULES["PBW-B7"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_c3_no_module_header_describes_the_entry_point():
    """The CLI-module-header sweep is silent over every module not yet on a
    pending list. `PBW-C3`."""
    report = run_sweep(RULES["PBW-C3"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_c4_no_copied_block_survives():
    """The copied-block sweep is silent over every file not yet on a
    pending list. `PBW-C4`."""
    report = run_sweep(RULES["PBW-C4"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_c5_a_docstring_states_its_behaviour_and_cites_by_slug():
    """The docstring-shape sweep is silent over every test file not yet on
    a pending list. `PBW-C5`."""
    report = run_sweep(RULES["PBW-C5"], scanned_paths())
    assert not report.findings, report.render()
    assert report.files_scanned > 0


def test_pbw_d2_no_ban_line_is_removed():
    """`governance/terminology.yml` still spells every word it bans, and the
    retired-word and idiom sweeps report nothing inside the `banned:` block
    or the terminology fixtures. `PBW-D2`."""
    terminology = yaml.safe_load(TERMINOLOGY_PATH.read_text(encoding="utf-8"))
    banned = terminology["banned"]
    assert banned, "the banned: block must not be emptied by this issue"
    for entry in banned:
        assert entry.get("term")
        assert entry.get("replacement")
        assert entry.get("context")
    # The retired-word rule's own structural skip is the mechanism: it never
    # reads governance/terminology.yml's banned: block (PROSE_KEYS does not
    # include `context`, `term` or `replacement`) or the terminology
    # fixtures, so both are naturally silent rather than exempted per-quote.
    fixture_dir = REPO_ROOT / "tests" / "fixtures" / "terminology"
    if fixture_dir.is_dir():
        fixture_paths = [REPO_ROOT / "tests" / "fixtures" / "terminology" / p.name
                          for p in fixture_dir.iterdir() if p.is_file()]
        report = run_sweep(RULES["PBW-A1"], fixture_paths)
        assert not report.findings, report.render()
        idiom_report = run_sweep(RULES["PBW-A5"], fixture_paths)
        assert not idiom_report.findings, idiom_report.render()


# ---------------------------------------------------------------------------
# PBW-E1, PBW-E2 - the sweeps can fail, and a zero is believed only after one
# ---------------------------------------------------------------------------

# Two rules are scoped to a specific real path (PBW-A10's registry, PBW-C3's
# cli/compass_pkg/ check) rather than to any file a fixture could live at, so
# their proof constructs the span directly instead of reading a fixture file.
# The text is the same text the matching fixture file states, so a reader
# checking the proof against the fixture sees the same breach either way.
_SYNTHETIC_BREACH_SPANS: dict[str, ProseSpan] = {
    "PBW-A10": ProseSpan(
        "docs/quickstart.md", 1,
        "Compass registers three hooks in this repository.", "markdown"),
    "PBW-C3": ProseSpan(
        "cli/compass_pkg/example.py", 3, "compass - the Compass CLI",
        "comment"),
}


def _fixture_spans_for(rule_id: str) -> list[ProseSpan]:
    if rule_id in _SYNTHETIC_BREACH_SPANS:
        return [_SYNTHETIC_BREACH_SPANS[rule_id]]
    matches = sorted(FIXTURE_DIR.glob(f"{rule_id.lower()}.*"))
    assert matches, f"no fixture file for {rule_id} under {FIXTURE_DIR}"
    return prose_spans(matches)


def test_pbw_e1_each_sweep_reports_a_planted_breach():
    """Every rule in `RULES` reports the breach planted for it, names the
    file and the line, and returns to silence once the breach is gone from
    the span it reads. `PBW-E1`."""
    proof: list[str] = []
    for rule_id, rule in sorted(RULES.items()):
        spans = _fixture_spans_for(rule_id)
        findings = [f for span in spans for f in rule.find(span)]
        assert findings, f"{rule_id} reported nothing over its own fixture"
        for finding in findings:
            assert finding.path and finding.line
        proof.append(f"{rule_id}: reported {len(findings)} over "
                     f"{[s.path for s in spans][0]}")
        # Silence on return: a span with the reported text removed is clean.
        for span in spans:
            span_findings = rule.find(span)
            if not span_findings:
                continue
            cleaned = ProseSpan(span.path, span.line, "", span.kind)
            assert not rule.find(cleaned), (
                f"{rule_id} still reports a blanked span - the pattern is "
                f"not reading the text it claims to")
    assert len(proof) == len(RULES) == 14, "\n".join(proof)


def test_pbw_e2_each_sweep_reports_the_files_it_scanned():
    """Every `Report` carries the number of files it scanned, so a zero from
    an empty file set reads differently from a zero from clean prose.
    `PBW-E2`. It also carries `files_reachable`, the rule's own real reach -
    finding 11, `review-dimensions.md`: a single `files_scanned: 543` for
    every rule overstated four rules' reach by up to 60 times, so a zero
    from `PBW-A10` (9 files it can ever report on) read as broad as a zero
    from a rule that reads the whole tree."""
    paths = scanned_paths()
    for rule in RULES.values():
        empty_report = run_sweep(rule, [])
        assert empty_report.files_scanned == 0
        assert empty_report.files_reachable == 0
        assert not empty_report.findings
        real_report = run_sweep(rule, paths)
        assert real_report.files_scanned > 0
        assert real_report.files_scanned == len(paths)
        assert 0 < real_report.files_reachable <= real_report.files_scanned


#: The rules whose reach grows with the tree, each with the test's own copy of
#: its reach condition and the number of files inside that reach that yield no
#: prose. The copy is independent of the rule's `reach`, so widening a rule's
#: reach fails the test. The no-prose count moves only when a file with no
#: docstring or comment enters the reach - rare, and worth a visible edit.
_GROWING_REACH = {
    "PBW-C3": (lambda path: path.startswith("cli/compass_pkg/"), 0),
    "PBW-C5": (lambda path: path.startswith("tests/") and path.endswith(".py"), 3),
    # 12 with tests/fixtures/next-golden.json, a golden file of command output;
    # 13 with tests/fixtures/archive-sample.tar.gz, the packed archive sample;
    # 14 with the packed routing baseline in tests/fixtures/compat/;
    # 15 with the check-verdict baseline beside it, which is plain JSON;
    # 59 with the 44 check-corpus case labels, which hold a verdict and one line;
    # 60 with tests/fixtures/classifier-json-example.json, plain JSON.
    "PBW-C4": (lambda path: path.startswith("tests/"), 60),
}

#: The rules whose reach is a fixed set of files, pinned exactly.
_FIXED_REACH = {"PBW-A10": 9}


def test_pbw_e2_four_rules_reach_fewer_files_than_the_repository_scans():
    """The four rules finding 11 measured - each reaches only the files its
    own `find` function can ever report on, not the whole scan.

    PBW-A10 reaches a fixed set of registry files, so its count is pinned.
    PBW-C3 reaches every module under `cli/compass_pkg/`, and PBW-C5 and
    PBW-C4 every test file, so each new file raised their pinned counts by
    one and failed this test after the commit that added it. Their expected
    reach is now the files their reach admits, less those that hold no prose:
    a new file with prose moves both sides, and the test stays green
    (`reach-counts-move-with-every-test`)."""
    paths = scanned_paths()
    rels = [str(p.relative_to(REPO_ROOT)) for p in paths]
    expected = dict(_FIXED_REACH)
    for rule_id, (admits, no_prose) in _GROWING_REACH.items():
        expected[rule_id] = sum(1 for rel in rels if admits(rel)) - no_prose
    for rule_id, reach in expected.items():
        report = run_sweep(RULES[rule_id], paths)
        assert report.files_reachable == reach, (
            f"{rule_id} reach drifted: expected {reach}, got "
            f"{report.files_reachable}. For a growing rule, a file with no "
            f"prose entered its reach, or its reach condition changed")
        assert report.files_reachable < report.files_scanned


def _planted(rel: str, text: str):
    """Write a file into the tree for one test, and return its path. The
    caller removes it; the name carries the process id so two runs cannot
    collide."""
    path = REPO_ROOT / rel
    assert not path.exists(), f"{rel} already exists; refusing to overwrite"
    path.write_text(text, encoding="utf-8")
    return path


def _with_planted(monkeypatch, *planted):
    real = scanned_paths()
    monkeypatch.setattr(sys.modules[__name__], "scanned_paths",
                        lambda: real + list(planted))


def test_pbw_e2_a_new_file_with_prose_leaves_the_reach_test_green(monkeypatch):
    """A new test file or CLI module is the ordinary case, and the reach test
    must not need a count raised for it (`reach-counts-move-with-every-test`)."""
    probe = f"_reach_probe_{os.getpid()}"
    files = [_planted(f"tests/{probe}.py", f'"""{probe}: a planted test."""\n'),
             _planted(f"cli/compass_pkg/{probe}.py",
                      f'"""{probe}: a planted module."""\n')]
    try:
        _with_planted(monkeypatch, *files)
        test_pbw_e2_four_rules_reach_fewer_files_than_the_repository_scans()
    finally:
        for f in files:
            f.unlink()


def test_pbw_e2_a_new_file_with_no_prose_fails_the_reach_test(monkeypatch):
    """A file in a rule's reach that yields no prose moves the pinned count,
    so it must fail and name the rule rather than pass unseen."""
    probe = f"_reach_probe_{os.getpid()}"
    empty = _planted(f"tests/{probe}.py", "")
    try:
        _with_planted(monkeypatch, empty)
        with pytest.raises(AssertionError, match="PBW-C5"):
            test_pbw_e2_four_rules_reach_fewer_files_than_the_repository_scans()
    finally:
        empty.unlink()


def test_pbw_e2_a_widened_reach_fails_the_reach_test(monkeypatch):
    rule = RULES["PBW-C5"]
    monkeypatch.setitem(RULES, "PBW-C5", dataclasses.replace(
        rule, reach=lambda path: path.startswith(("tests/", "docs/"))))
    with pytest.raises(AssertionError, match="PBW-C5"):
        test_pbw_e2_four_rules_reach_fewer_files_than_the_repository_scans()


def test_pbw_e3_every_exemption_names_a_file_and_a_reason():
    """Every exemption on every rule names the file, the quote and the
    reason - a widened pattern is not how a sweep clears a report.
    `PBW-E3`.

    Finding 9, `review-dimensions.md`: 6 of 430 exemptions quoted text that
    had since left the file entirely - stale, and undetected, because
    nothing checked that the quote was still there. A dead exemption is not
    a hole today; it is a hole waiting, ready to excuse a future occurrence
    nobody reviewed. This also fails when the quote is present but the rule
    would not report the span anyway - the fuller "dead" class review found
    35 of, on top of the 6 stale ones."""
    total = 0
    for rule in RULES.values():
        for exemption in rule.exemptions:
            total += 1
            assert exemption.path, f"{rule.id} exemption has no path"
            assert exemption.quote, f"{rule.id} exemption has no quote"
            assert len(exemption.reason) > 20, (
                f"{rule.id} exemption for {exemption.path} gives no real "
                f"reason")
    assert total >= 1, "at least the PBW-A7 exemption should exist by now"


def test_pbw_e3_every_exemption_is_still_needed():
    """A named exemption stops being needed for one of two reasons: the
    prose it quotes moved on (the quote is no longer in the file at all), or
    the rule was narrowed and would not report that span anyway. Either way
    the exemption is dead, and PBW-E3's own presence check above cannot see
    it - a path, a quote and a reason can all be well-formed and still
    describe nothing live. Finding 9, `review-dimensions.md`."""
    paths = scanned_paths()
    spans_by_path: dict[str, list[ProseSpan]] = {}
    for span in prose_spans(paths):
        spans_by_path.setdefault(span.path, []).append(span)

    dead: list[str] = []
    for rule in RULES.values():
        for exemption in rule.exemptions:
            file_spans = spans_by_path.get(exemption.path, [])
            matching = [s for s in file_spans if exemption.quote in s.text]
            if not matching:
                dead.append(
                    f"{rule.id} {exemption.path!r}: quote {exemption.quote!r} "
                    f"is not in the file's prose at all")
                continue
            if not any(rule.find(s) for s in matching):
                dead.append(
                    f"{rule.id} {exemption.path!r}: quote {exemption.quote!r} "
                    f"is present, but the rule reports nothing there - the "
                    f"exemption excuses nothing")
    assert not dead, "dead exemptions found:\n" + "\n".join(dead)


# ---------------------------------------------------------------------------
# PBW-E4 - no changed file's behaviour changes
# ---------------------------------------------------------------------------

COMPARE_BEHAVIOUR = REPO_ROOT / "scripts" / "compare-behaviour.py"


def _sandbox_repo(tmp_path) -> Path:
    repo = tmp_path / "sandbox"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
    return repo


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True)


def _run_compare(repo: Path, base: str, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(COMPARE_BEHAVIOUR), "--base", base, *extra],
        cwd=repo, capture_output=True, text=True)


def test_pbw_e4_the_behaviour_comparison_reports_a_planted_change(tmp_path):
    """`scripts/compare-behaviour.py` exits non-zero on a body change, exits
    0 on a docstring-only change, catches a changed printed string in a
    shell script, and still refuses a test file's behaviour change even
    when `--allow-pinned-test` names a different path. `PBW-E4`."""
    repo = _sandbox_repo(tmp_path)

    # Case 1: a docstring-only change in a Python file - exit 0.
    (repo / "mod.py").write_text('"""Old docstring."""\n\n\ndef f():\n    return 1\n')
    _commit(repo, "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True, check=True).stdout.strip()
    (repo / "mod.py").write_text('"""New docstring, rewritten."""\n\n\ndef f():\n    return 1\n')
    _commit(repo, "docstring only")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 2: a one-line body change plus a docstring rewrite - exit
    # non-zero, naming the file.
    (repo / "mod.py").write_text('"""Newer docstring."""\n\n\ndef f():\n    return 2\n')
    _commit(repo, "body change")
    result = _run_compare(repo, base)
    assert result.returncode != 0
    assert "mod.py" in result.stdout

    # Case 3: a changed printed string in a shell script - exit non-zero.
    (repo / "say.sh").write_text('#!/bin/sh\n# a comment\necho "old"\n')
    _commit(repo, "shell base")
    base2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout.strip()
    (repo / "say.sh").write_text('#!/bin/sh\n# a comment, reworded\necho "new"\n')
    _commit(repo, "shell changed")
    result = _run_compare(repo, base2)
    assert result.returncode != 0
    assert "say.sh" in result.stdout

    # Case 4: a behaviour change in a test file not named by
    # --allow-pinned-test - still refused.
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_thing.py").write_text(
        '"""Doc."""\n\n\ndef test_x():\n    assert 1 == 1\n')
    _commit(repo, "test base")
    base3 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout.strip()
    (repo / "tests" / "test_thing.py").write_text(
        '"""Doc, reworded."""\n\n\ndef test_x():\n    assert 2 == 2\n')
    _commit(repo, "test pin changed")
    result = _run_compare(
        repo, base3, "--allow-pinned-test",
        "tests/test_other.py=a different file, named to show the allowance "
        "is per path")
    assert result.returncode != 0
    assert "test_thing.py" in result.stdout

    # A path outside tests/ passed to --allow-pinned-test is refused.
    result = _run_compare(repo, base3, "--allow-pinned-test",
                           "src/mod.py=a stated reason does not help here")
    assert result.returncode != 0


def test_pbw_e4_a_comment_only_rewrite_that_moves_line_counts_is_not_a_change(
        tmp_path):
    """A comment-only edit that changes how many lines a comment block
    occupies exits 0, in shell and in YAML, and a real change in either still
    exits non-zero. `PBW-E4`.

    This is the shape that made the tool useless on batch 6: a stripper that
    replaces a comment with an empty line keeps one line per input line, so
    rewrapping a comment block changed the number of empty lines and the
    joined text differed with no command line changed. Nearly every rewrite
    this issue makes moves a comment's line count, so a tool that reports it
    reports on almost every batch.

    Markdown and JSON are covered here too. Neither can carry the defect -
    the markdown reader collects fenced lines and link targets rather than
    blanking prose, and the JSON reader compares parsed structures - and the
    two cases record that rather than leaving a later reader to re-derive it.
    """
    repo = _sandbox_repo(tmp_path)

    def _base() -> str:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                               capture_output=True, text=True,
                               check=True).stdout.strip()

    # Case 1: a shell comment block of three lines becomes one, and every
    # command line is byte-identical - exit 0.
    (repo / "run.sh").write_text(
        '#!/bin/sh\n# one\n# two\n# three\necho "x"\n')
    _commit(repo, "shell base")
    base = _base()
    (repo / "run.sh").write_text(
        '#!/bin/sh\n# one, two and three, said once\necho "x"\n')
    _commit(repo, "shell comment rewrapped")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 2: the same rewrap, plus a real command change - exit non-zero.
    (repo / "run.sh").write_text(
        '#!/bin/sh\n# one, two and three\n# said over two lines now\necho "y"\n')
    _commit(repo, "shell command changed too")
    result = _run_compare(repo, base)
    assert result.returncode != 0
    assert "run.sh" in result.stdout

    # Case 3: an extensionless shell script takes the same path.
    (repo / "hook").write_text('#!/bin/sh\n# a\n# b\nexit 0\n')
    _commit(repo, "hook base")
    base = _base()
    (repo / "hook").write_text('#!/bin/sh\n# a and b\nexit 0\n')
    _commit(repo, "hook comment rewrapped")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 4: a YAML whole-line comment reworded over a different number of
    # lines, with no value touched - exit 0.
    (repo / "conf.yml").write_text(
        "# the old note\n# spread over two lines\nthreshold: 5\n")
    _commit(repo, "yaml base")
    base = _base()
    (repo / "conf.yml").write_text(
        "# the new note, said on one line\nthreshold: 5\n")
    _commit(repo, "yaml comment rewrapped")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 5: a YAML trailing comment reworded, with no value touched -
    # exit 0.
    (repo / "conf.yml").write_text("threshold: 5  # the old note\n")
    _commit(repo, "yaml trailing base")
    base = _base()
    (repo / "conf.yml").write_text("threshold: 5  # a rather longer note\n")
    _commit(repo, "yaml trailing comment reworded")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 6: a real YAML value change, with the comment reworded too - exit
    # non-zero. The fix must not buy exit 0 by going blind.
    (repo / "conf.yml").write_text("threshold: 6  # a different note again\n")
    _commit(repo, "yaml value changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0
    assert "conf.yml" in result.stdout

    # Case 7: a YAML prose value whose line count changes - exit 0. The key
    # is in PROSE_KEYS, so its value is prose by the same list the sweeps use.
    (repo / "prose.yml").write_text(
        "description: >\n  one\n  two\nthreshold: 5\n")
    _commit(repo, "yaml prose base")
    base = _base()
    (repo / "prose.yml").write_text(
        "description: >\n  one two\nthreshold: 5\n")
    _commit(repo, "yaml prose rewrapped")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 8: markdown prose rewritten around an unchanged fenced block -
    # exit 0, and a changed fenced block still exits non-zero.
    (repo / "doc.md").write_text(
        "Old prose.\n\nMore old prose.\n\n```sh\necho hi\n```\n")
    _commit(repo, "md base")
    base = _base()
    (repo / "doc.md").write_text("New prose, shorter.\n\n```sh\necho hi\n```\n")
    _commit(repo, "md prose only")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr
    (repo / "doc.md").write_text("New prose.\n\n```sh\necho bye\n```\n")
    _commit(repo, "md fence changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0
    assert "doc.md" in result.stdout

    # Case 9: a JSON description reworded and the file reformatted - exit 0,
    # and a changed non-description value still exits non-zero.
    (repo / "data.json").write_text('{"description": "old words", "n": 1}')
    _commit(repo, "json base")
    base = _base()
    (repo / "data.json").write_text(
        '{\n  "description": "new and rather longer words",\n  "n": 1\n}')
    _commit(repo, "json description only")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr
    (repo / "data.json").write_text('{"description": "new words", "n": 2}')
    _commit(repo, "json value changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0
    assert "data.json" in result.stdout


def test_pbw_e4_a_quoted_hash_is_not_a_comment(tmp_path):
    """A `#` inside a quoted shell string is part of the command, so a change
    after it is reported. A real trailing comment is still stripped. `PBW-E4`.

    This was a false negative in the one tool whose purpose is proving that
    no behaviour changed: the comment stripper matched ` #` anywhere outside
    a comment's own syntax, so `echo "tag #alpha"` was cut to `echo "tag` and
    a change to the part after the hash compared equal. The direction matters
    more than the count - over-reporting costs a second look, while this
    missed the change the tool is run to catch.
    """
    repo = _sandbox_repo(tmp_path)

    def _base() -> str:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                               capture_output=True, text=True,
                               check=True).stdout.strip()

    # Case 1: a double-quoted hash, with the change after it - reported.
    (repo / "a.sh").write_text('#!/bin/sh\necho "tag #alpha"\n')
    _commit(repo, "quoted hash base")
    base = _base()
    (repo / "a.sh").write_text('#!/bin/sh\necho "tag #beta"\n')
    _commit(repo, "quoted hash changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "a.sh" in result.stdout

    # Case 2: a hash inside a sed substitution - reported.
    (repo / "b.sh").write_text('#!/bin/sh\nsed -i "s/ #a/ #b/" f\n')
    _commit(repo, "sed base")
    base = _base()
    (repo / "b.sh").write_text('#!/bin/sh\nsed -i "s/ #a/ #c/" f\n')
    _commit(repo, "sed changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "b.sh" in result.stdout

    # Case 3: a single-quoted hash - reported.
    (repo / "c.sh").write_text("#!/bin/sh\necho 'tag #alpha'\n")
    _commit(repo, "single quote base")
    base = _base()
    (repo / "c.sh").write_text("#!/bin/sh\necho 'tag #beta'\n")
    _commit(repo, "single quote changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr

    # Case 4: `$#` and `${#var}` are shell parameters, not comments - a
    # change to the line is reported.
    (repo / "d.sh").write_text('#!/bin/sh\necho "$# args ${#PATH} chars"\n')
    _commit(repo, "param base")
    base = _base()
    (repo / "d.sh").write_text('#!/bin/sh\necho "$# args ${#HOME} chars"\n')
    _commit(repo, "param changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr

    # Case 5: the fix must not over-correct. A genuine trailing comment,
    # reworded over a different length, is still stripped - exit 0. A
    # quoted hash on the same line stays part of the command.
    (repo / "e.sh").write_text(
        '#!/bin/sh\necho "tag #alpha"  # what this line does\n')
    _commit(repo, "trailing comment base")
    base = _base()
    (repo / "e.sh").write_text(
        '#!/bin/sh\necho "tag #alpha"  # a much longer note about the line\n')
    _commit(repo, "trailing comment reworded")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 6: an escaped hash outside quotes is part of the command.
    (repo / "f.sh").write_text('#!/bin/sh\nprintf %s a\\#alpha\n')
    _commit(repo, "escaped base")
    base = _base()
    (repo / "f.sh").write_text('#!/bin/sh\nprintf %s a\\#beta\n')
    _commit(repo, "escaped changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr


def test_pbw_e4_an_extensionless_file_is_read_by_its_shebang(tmp_path):
    """A file with no extension is dispatched on its shebang, so
    `#!/usr/bin/env python3` is read as Python and not as shell. `PBW-E4`.

    `cli/compass` is Python with a shebang and no extension, so the suffix
    test sent it to the shell reader. Batch 5 hit the false positive - "a
    command line changed" for a docstring rewrite - and checked the syntax
    trees by hand to prove nothing moved. The worse half is the other
    direction: a real change to a Python body in an extensionless entry point
    would be judged by a reader that cannot see a Python body at all, and
    would pass. `cli/compass` is the command every adopter runs.
    """
    repo = _sandbox_repo(tmp_path)

    def _base() -> str:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                               capture_output=True, text=True,
                               check=True).stdout.strip()

    # Case 1: an extensionless Python entry point, docstring only - exit 0.
    # The shell reader would see the changed line and report it.
    (repo / "entry").write_text(
        '#!/usr/bin/env python3\n"""Old summary."""\n\n\ndef f():\n    return 1\n')
    _commit(repo, "python entry base")
    base = _base()
    (repo / "entry").write_text(
        '#!/usr/bin/env python3\n"""New summary, rewritten at length."""\n'
        '\n\ndef f():\n    return 1\n')
    _commit(repo, "python entry docstring only")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 2: the same file, a changed statement - reported. This is the
    # direction the shell reader could not see.
    (repo / "entry").write_text(
        '#!/usr/bin/env python3\n"""New summary, rewritten at length."""\n'
        '\n\ndef f():\n    return 2\n')
    _commit(repo, "python entry body changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "entry" in result.stdout

    # Case 3: an extensionless bash entry point keeps the shell reader -
    # bin/compass's shape. A rewrapped comment block is not a change.
    (repo / "shim").write_text(
        '#!/usr/bin/env bash\n# one\n# two\nexec echo hi\n')
    _commit(repo, "bash shim base")
    base = _base()
    (repo / "shim").write_text(
        '#!/usr/bin/env bash\n# one and two, said once\nexec echo hi\n')
    _commit(repo, "bash shim comment rewrapped")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 4: the same bash file, a changed command - reported.
    (repo / "shim").write_text(
        '#!/usr/bin/env bash\n# one and two\nexec echo bye\n')
    _commit(repo, "bash shim command changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr

    # Case 5: a python3 shebang without `env`, and a bare `#!/bin/sh`.
    (repo / "direct").write_text(
        '#!/usr/bin/python3\n"""Doc."""\nx = 1\n')
    (repo / "posix").write_text('#!/bin/sh\n# note\necho hi\n')
    _commit(repo, "other shebang forms base")
    base = _base()
    (repo / "direct").write_text(
        '#!/usr/bin/python3\n"""Doc, reworded."""\nx = 1\n')
    (repo / "posix").write_text('#!/bin/sh\n# a different note\necho hi\n')
    _commit(repo, "other shebang forms, prose only")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 6: no extension and no shebang falls back to the shell reader,
    # which is what this repository's VERSION, Makefile, CODEOWNERS and
    # examples/.../current-task files need. A changed line is still reported.
    (repo / "VERSION").write_text("4.0.1\n")
    _commit(repo, "data file base")
    base = _base()
    (repo / "VERSION").write_text("4.0.2\n")
    _commit(repo, "data file changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr

    # Case 7: the false negative that made this worth fixing, rather than the
    # false positive that revealed it. The shell reader drops blank lines and
    # trailing whitespace, because neither carries behaviour in shell. Both
    # are content inside a Python string, so a change to printed text was
    # invisible. `cli/compass` holds four multi-line string constants, so this
    # was reachable in the command every adopter runs.
    (repo / "helptext").write_text(
        '#!/usr/bin/env python3\nBANNER = """line one\nline two\n"""\n')
    _commit(repo, "help text base")
    base = _base()
    (repo / "helptext").write_text(
        '#!/usr/bin/env python3\nBANNER = """line one\n\nline two\n"""\n')
    _commit(repo, "a blank line added to printed help text")
    result = _run_compare(repo, base)
    assert result.returncode != 0, (
        "a blank line inside a Python string constant changes what the "
        "command prints, and the shell reader could not see it:\n"
        + result.stdout + result.stderr)


def test_pbw_e4_a_prose_sequence_item_is_blanked_but_still_counted(tmp_path):
    """A prose sequence item under a `PROSE_KEYS` key can be reworded and
    rewrapped freely, but adding or removing one is reported. `PBW-E4`.

    `governance/routing-policy.yml`'s `biases:` holds free-text tie-breakers,
    and its own comment says they are not machine-evaluated. The reader
    blanked only scalar values, so batch 3 could not prove a rewording of them
    safe and correctly left the findings unfixed in a shipped governance file.

    Each item collapses to one marker rather than the whole list collapsing to
    one, so the item count is still compared. Rewording is prose; deleting a
    tie-breaker is not, and a reader would never see it go.
    """
    repo = _sandbox_repo(tmp_path)

    def _base() -> str:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                               capture_output=True, text=True,
                               check=True).stdout.strip()

    three = (
        "policy:\n"
        "  biases:\n"
        '    - "When size is unclear, estimate up - collapsing an easy\n'
        '       phase is cheaper than discovering it mid-Build."\n'
        '    - "A non-engineering role usually pulls the route heavier."\n'
        '    - "Prefer the lightest route that still clears every guardrail."\n'
        "  default_route: standard\n"
    )
    (repo / "p.yml").write_text(three)
    _commit(repo, "biases base")
    base = _base()

    # Case 1: all three reworded and rewrapped over different line counts,
    # same count of items - exit 0.
    (repo / "p.yml").write_text(
        "policy:\n"
        "  biases:\n"
        '    - "When the size is genuinely unclear, estimate up."\n'
        '    - "A non-engineering role in play usually pulls the route\n'
        '       heavier, and that is a bias rather than a floor."\n'
        '    - "Prefer the lightest route that clears every routing\n'
        '       guardrail and the gates that apply."\n'
        "  default_route: standard\n")
    _commit(repo, "biases reworded and rewrapped")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # Case 2: one item removed - reported. A deleted tie-breaker is a
    # content change, not a rewording.
    (repo / "p.yml").write_text(
        "policy:\n"
        "  biases:\n"
        '    - "When the size is genuinely unclear, estimate up."\n'
        '    - "A non-engineering role in play pulls the route heavier."\n'
        "  default_route: standard\n")
    _commit(repo, "one bias removed")
    result = _run_compare(repo, base)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "p.yml" in result.stdout

    # Case 3: a fourth item added - reported.
    (repo / "q.yml").write_text(three)
    _commit(repo, "q base")
    base_q = _base()
    (repo / "q.yml").write_text(three.replace(
        "  default_route: standard\n",
        '    - "A fourth tie-breaker nobody agreed."\n'
        "  default_route: standard\n"))
    _commit(repo, "a bias added")
    result = _run_compare(repo, base_q)
    assert result.returncode != 0, result.stdout + result.stderr

    # Case 4: a sequence under a key that is NOT prose - still compared, so
    # the extension cannot be used to hide a rule change.
    (repo / "r.yml").write_text(
        "checks:\n"
        "  - borrowed-documents-answered\n"
        "  - evidence-typed\n")
    _commit(repo, "r base")
    base_r = _base()
    (repo / "r.yml").write_text(
        "checks:\n"
        "  - borrowed-documents-answered\n"
        "  - evidence-untyped\n")
    _commit(repo, "a real check renamed")
    result = _run_compare(repo, base_r)
    assert result.returncode != 0, result.stdout + result.stderr

    # Case 5: a prose key whose value is empty and whose children are a
    # MAPPING, not a sequence - the children are values and stay compared.
    (repo / "s.yml").write_text(
        "name:\n"
        "  threshold: 5\n"
        "  enabled: true\n")
    _commit(repo, "s base")
    base_s = _base()
    (repo / "s.yml").write_text(
        "name:\n"
        "  threshold: 9\n"
        "  enabled: true\n")
    _commit(repo, "a nested value changed under a prose key")
    result = _run_compare(repo, base_s)
    assert result.returncode != 0, result.stdout + result.stderr


def test_pbw_e4_an_allowance_must_name_its_reason(tmp_path):
    """`--allow-pinned-test` takes `PATH=REASON`, prints both, and refuses an
    allowance with no reason or a path outside `tests/`. `PBW-E4`.

    An allowance with no stated reason is the same defect as a loosened
    matcher: the report goes quiet and nothing records why. Every batch of
    this issue needed one, because every batch edited this file to shrink the
    per-batch skip lists, and the stated reason is what kept that from
    becoming a habit nobody reads.
    """
    repo = _sandbox_repo(tmp_path)
    (repo / "tests").mkdir()
    (repo / "tests" / "test_mech.py").write_text(
        '"""Doc."""\n\n\ndef test_x():\n    assert 1 == 1\n')
    _commit(repo, "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True,
                           check=True).stdout.strip()
    (repo / "tests" / "test_mech.py").write_text(
        '"""Doc."""\n\n\ndef test_x():\n    assert 2 == 2\n')
    _commit(repo, "mechanism constant lowered")

    # Without an allowance the change is reported.
    result = _run_compare(repo, base)
    assert result.returncode != 0
    assert "test_mech.py" in result.stdout

    # With a reason: exit 0, and the output names the path and the reason.
    reason = "the high-water constant the plan requires this batch to lower"
    result = _run_compare(repo, base, "--allow-pinned-test",
                           f"tests/test_mech.py={reason}")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "tests/test_mech.py" in result.stdout
    assert reason in result.stdout, (
        "the recorded output must say why the path was excused:\n"
        + result.stdout)

    # No reason: refused, and the message says a reason is needed.
    result = _run_compare(repo, base, "--allow-pinned-test",
                           "tests/test_mech.py")
    assert result.returncode != 0
    assert "reason" in result.stdout.lower() + result.stderr.lower()

    # An empty reason is not a reason.
    result = _run_compare(repo, base, "--allow-pinned-test",
                           "tests/test_mech.py=")
    assert result.returncode != 0

    # A path outside tests/ is still refused, reason or not.
    result = _run_compare(repo, base, "--allow-pinned-test",
                           "src/mod.py=a stated reason does not help here")
    assert result.returncode != 0


def test_pbw_e4_a_yaml_comment_is_not_behaviour(tmp_path):
    """A whole-line `#` comment is the same prose position
    `tests/test_writing_style.py`'s `_yaml_spans` reads, so rewording one is
    not a behaviour change - but a `rationale:`-sibling key's real value
    still is. `PBW-E4`, `PBW-D2`."""
    repo = _sandbox_repo(tmp_path)
    (repo / "policy.yml").write_text(
        "# old comment explaining the rule below\n"
        "rule: keep\n")
    _commit(repo, "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True, check=True).stdout.strip()

    # Comment-only change - exit 0.
    (repo / "policy.yml").write_text(
        "# new comment, reworded for clarity\n"
        "rule: keep\n")
    _commit(repo, "comment reworded")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # The non-prose value changes too - exit non-zero, naming the file.
    (repo / "policy.yml").write_text(
        "# new comment, reworded for clarity\n"
        "rule: change\n")
    _commit(repo, "rule value changed")
    result = _run_compare(repo, base)
    assert result.returncode != 0
    assert "policy.yml" in result.stdout

    # governance/terminology.yml's own prose keys (means, not, context, why,
    # reason) are not the general PROSE_KEYS - rewording one is still not a
    # behaviour change.
    (repo / "terms.yml").write_text(
        "terms:\n"
        "  issue:\n"
        "    means: old wording about an issue\n"
        "    not: old wording about what it is not\n"
        "    related: [manifest]\n")
    _commit(repo, "terms base")
    base_terms = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                                 capture_output=True, text=True,
                                 check=True).stdout.strip()
    (repo / "terms.yml").write_text(
        "terms:\n"
        "  issue:\n"
        "    means: new wording, reworded entirely, about an issue\n"
        "    not: new wording, reworded entirely, about what it is not\n"
        "    related: [manifest]\n")
    _commit(repo, "terms reworded")
    result = _run_compare(repo, base_terms)
    assert result.returncode == 0, result.stdout + result.stderr

    # `appears_in` is a citation list, not a mapping value - a reader's aid
    # naming where an id shows up, printed by `compass terminology explain`
    # and nowhere read as a rule. `referent` is the same kind of field, a
    # one-line description printed alongside it. Correcting a stale filename
    # inside `appears_in` (the v1 `task.yml` renamed to `manifest.yml`) and
    # rewording `referent` are both not a behaviour change.
    (repo / "codes.yml").write_text(
        "codes:\n"
        "  TRC:\n"
        "    referent: One decision inside a single issue's design.\n"
        "    appears_in: [acceptance-criteria.md, \"task.yml scenarios[].id\"]\n")
    _commit(repo, "codes base")
    base_codes = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                                 capture_output=True, text=True,
                                 check=True).stdout.strip()
    (repo / "codes.yml").write_text(
        "codes:\n"
        "  TRC:\n"
        "    referent: One decision inside a single issue's technical design.\n"
        "    appears_in: [acceptance-criteria.md, \"manifest.yml scenarios[].id\"]\n")
    _commit(repo, "referent and appears_in corrected")
    result = _run_compare(repo, base_codes)
    assert result.returncode == 0, result.stdout + result.stderr

    # A multi-line folded block scalar under a PROSE_KEYS key: rewording
    # every continuation line is not a behaviour change...
    (repo / "block.yml").write_text(
        "checks:\n"
        "  a-check:\n"
        "    description: >\n"
        "      Old wording, spread\n"
        "      across two lines.\n"
        "    checks: [x]\n")
    _commit(repo, "block base")
    base2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout.strip()
    (repo / "block.yml").write_text(
        "checks:\n"
        "  a-check:\n"
        "    description: >\n"
        "      New wording entirely, now spread\n"
        "      across three\n"
        "      lines instead.\n"
        "    checks: [x]\n")
    _commit(repo, "block reworded")
    result = _run_compare(repo, base2)
    assert result.returncode == 0, result.stdout + result.stderr

    # ...but the sibling `checks:` list is still a real change.
    (repo / "block.yml").write_text(
        "checks:\n"
        "  a-check:\n"
        "    description: >\n"
        "      New wording entirely, now spread\n"
        "      across three\n"
        "      lines instead.\n"
        "    checks: [y]\n")
    _commit(repo, "block checks changed")
    result = _run_compare(repo, base2)
    assert result.returncode != 0
    assert "block.yml" in result.stdout

    # A run of whole-line comments collapsing from many short lines to
    # fewer, longer ones is still not a behaviour change.
    (repo / "comments.yml") .write_text(
        "# first old line\n"
        "# second old line\n"
        "# third old line\n"
        "rule: keep\n")
    _commit(repo, "comments base")
    base3 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout.strip()
    (repo / "comments.yml").write_text(
        "# one reworded comment covering the same ground\n"
        "rule: keep\n")
    _commit(repo, "comments collapsed")
    result = _run_compare(repo, base3)
    assert result.returncode == 0, result.stdout + result.stderr

    # An inline `#` comment trailing a plain sequence item - not under a
    # PROSE_KEYS key, so `_yaml_spans` reads it only via the whole-line
    # comment walk, which a trailing comment is not. Rewording, or even
    # deleting, the comment must still not read as a behaviour change: the
    # item itself (`agents/`) is untouched.
    (repo / "paths.yml").write_text(
        "exempt:\n"
        "  - agents/    # ten agent definitions, added clean at the freeze\n"
        "  - docs/\n")
    _commit(repo, "paths base")
    base4 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout.strip()
    (repo / "paths.yml").write_text(
        "exempt:\n"
        "  - agents/    # ten agent definitions, same shape as the others\n"
        "  - docs/\n")
    _commit(repo, "inline comment reworded")
    result = _run_compare(repo, base4)
    assert result.returncode == 0, result.stdout + result.stderr

    # Dropping the inline comment entirely - not reworded, gone - is the
    # same non-change: a comment carries no behaviour whether it is present,
    # reworded, or removed.
    (repo / "paths.yml").write_text(
        "exempt:\n"
        "  - agents/\n"
        "  - docs/\n")
    _commit(repo, "inline comment deleted")
    result = _run_compare(repo, base4)
    assert result.returncode == 0, result.stdout + result.stderr

    # ...but the item itself changing is still a real change.
    (repo / "paths.yml").write_text(
        "exempt:\n"
        "  - agents/    # ten agent definitions, same shape as the others\n"
        "  - skills/\n")
    _commit(repo, "item changed")
    result = _run_compare(repo, base4)
    assert result.returncode != 0
    assert "paths.yml" in result.stdout


def test_pbw_e4_a_reordered_table_row_is_not_behaviour(tmp_path):
    """A markdown table's rows carry links in document order; moving a row
    to fix a genuinely wrong position - `architecture/decisions/README.md`
    listed ADR-013 last instead of between ADR-012 and ADR-014 - moves its
    link in the extracted sequence too, even though every link target is
    byte-identical. A reader following any of the links lands in the same
    place regardless of row order, so this is not a behaviour change; a
    link actually retargeted, added, or removed still is. `PBW-E4`."""
    repo = _sandbox_repo(tmp_path)
    (repo / "index.md").write_text(
        "| [A](a.md) | first |\n"
        "| [B](b.md) | second |\n"
        "| [C](c.md) | third |\n")
    _commit(repo, "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True, check=True).stdout.strip()

    # Row C moves to its correct position between A and B - same three
    # links, different order on the page.
    (repo / "index.md").write_text(
        "| [A](a.md) | first |\n"
        "| [C](c.md) | third |\n"
        "| [B](b.md) | second |\n")
    _commit(repo, "row reordered")
    result = _run_compare(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr

    # A link actually retargeted is still a real change.
    (repo / "index.md").write_text(
        "| [A](a.md) | first |\n"
        "| [C](d.md) | third |\n"
        "| [B](b.md) | second |\n")
    _commit(repo, "link retargeted")
    result = _run_compare(repo, base)
    assert result.returncode != 0
    assert "index.md" in result.stdout


# ---------------------------------------------------------------------------
# PBW-F7 - a rewritten instruction still instructs the same behaviour
# ---------------------------------------------------------------------------

INSTRUCTION_INVENTORY = REPO_ROOT / "scripts" / "instruction-inventory.py"


def _run_inventory(repo: Path, base: str, out: Path,
                    *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(INSTRUCTION_INVENTORY), "--base", base,
         "--out", str(out), *extra],
        cwd=repo, capture_output=True, text=True)


def test_pbw_f7_every_sentence_maps_or_is_recorded_as_absorbed(tmp_path):
    """A sentence dropped from a rewritten instruction file with neither a
    mapped nor an absorbed-into row is a non-zero exit naming it; the same
    drop with an absorbed-into row on record is exit 0. `PBW-F7`."""
    repo = _sandbox_repo(tmp_path)
    out = tmp_path / "inventory-out"
    skill_dir = repo / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "# Example skill\n\n"
        "You must read the assignment before you start.\n"
        "You must write the failing test first.\n"
    )
    _commit(repo, "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True, check=True).stdout.strip()

    # Drop the second instruction with no mapping and no absorption record.
    (skill_dir / "SKILL.md").write_text(
        "# Example skill\n\n"
        "You must read the assignment before you start.\n"
    )
    _commit(repo, "drop a sentence")
    result = _run_inventory(repo, base, out)
    assert result.returncode != 0
    assert "write the failing test first" in (result.stdout + result.stderr)

    # Record the absorption and try again.
    (skill_dir / "SKILL.md").write_text(
        "# Example skill\n\n"
        "You must read the assignment before you start, and write the "
        "failing test first.\n"
        '<!-- absorbed: "You must write the failing test first." -->\n'
    )
    _commit(repo, "record the absorption")
    result = _run_inventory(repo, base, out)
    assert result.returncode == 0, result.stdout + result.stderr


def test_pbw_f7_a_marker_can_quote_a_sentence_that_ends_a_comment(tmp_path):
    """An absorbed-into marker can name a sentence containing `-->`, by
    escaping it as `--\\>`. `PBW-F7`.

    The sentence splitter breaks a multi-line HTML comment on its full stops,
    so the tail becomes a sentence carrying the closing `-->`. Two template
    sentences have that shape and neither could be declared absorbed:

    - the natural form satisfies the marker's pattern but holds two `-->`, so
      it is a malformed HTML comment - it closes at the first one and leaves
      `" -->` visible in the rendered template;
    - the escaped form is a well-formed comment with one `-->`, and was not
      understood, so it did not clear.

    Batch 4 was therefore left at exit 1 with no way to clear two genuinely
    absent sentences. A gate tool that cannot be cleared for a legitimate
    case teaches people to ignore its exit code, which is worse than the gate
    not existing.
    """
    repo = _sandbox_repo(tmp_path)
    skill = repo / "skills" / "example"
    skill.mkdir(parents=True)
    # A multi-line comment whose tail fragment is itself an instruction, the
    # shape templates/architecture/ownership.md has.
    skill.joinpath("SKILL.md").write_text(
        "# Example skill\n\n"
        "You must read the assignment before you start.\n\n"
        "<!-- Every row here must name its\n"
        "owning team before it can land. -->\n"
    )
    _commit(repo, "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True,
                           check=True).stdout.strip()
    out = tmp_path / "inv"
    fragment = "owning team before it can land. -->"

    # Dropped with no marker: refused, naming the fragment.
    skill.joinpath("SKILL.md").write_text(
        "# Example skill\n\n"
        "You must read the assignment before you start.\n")
    _commit(repo, "drop the comment")
    result = _run_inventory(repo, base, out)
    assert result.returncode != 0
    assert "owning team" in (result.stdout + result.stderr)

    # Declared absorbed with `-->` escaped as `--\>`: accepted, and the
    # marker is a well-formed HTML comment so nothing leaks into the page.
    # Quoted exactly as the splitter produces each sentence, which for the
    # head of a comment includes the opening `<!-- `. The absorbed path is an
    # exact match on purpose: a marker that paraphrases clears nothing.
    marker = ('<!-- absorbed: "<!-- Every row here must name its" -->\n'
               '<!-- absorbed: "owning team before it can land. --\\>" -->')
    assert marker.count("-->") == 2, (
        "two markers, one terminator each - the escaped tail contributes no "
        "`-->` at all, which is what keeps both comments well formed")
    skill.joinpath("SKILL.md").write_text(
        "# Example skill\n\n"
        "You must read the assignment before you start.\n"
        f"{marker}\n")
    _commit(repo, "declare both absorbed, the tail escaped")
    result = _run_inventory(repo, base, out)
    assert result.returncode == 0, result.stdout + result.stderr

    # An ordinary sentence with no `-->` still works unescaped.
    skill.joinpath("OTHER.md").write_text(
        "# Other\n\nYou must write the failing test first.\n")
    _commit(repo, "other base")
    base2 = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                            capture_output=True, text=True,
                            check=True).stdout.strip()
    skill.joinpath("OTHER.md").write_text(
        "# Other\n\nWrite the failing test first, always.\n"
        '<!-- absorbed: "You must write the failing test first." -->\n')
    _commit(repo, "ordinary absorbed marker")
    result = _run_inventory(repo, base2, out)
    assert result.returncode == 0, result.stdout + result.stderr


def test_pbw_f7_a_marker_is_not_itself_a_replacement_sentence(tmp_path):
    """A marker line cannot satisfy the mapped check for the sentence it
    quotes. `PBW-F7`.

    A marker holds its sentence verbatim, so it resembles that sentence more
    closely than anything else in the file. Left in the candidate pool, it
    fuzzy-matched above the 0.6 threshold and the sentence counted as MAPPED -
    which means writing a marker cleared the report whether or not the marker
    was understood, and whether or not any real sentence carried the meaning.
    Measured on the two real template sentences at 0.847 and 0.607.

    A gate that any marker clears is not a gate. The exact, unescaped
    absorbed path is the only way a marker may clear a sentence.
    """
    repo = _sandbox_repo(tmp_path)
    skill = repo / "skills" / "example"
    skill.mkdir(parents=True)
    skill.joinpath("SKILL.md").write_text(
        "# Example skill\n\n"
        "You must record the owning team before it can land.\n")
    _commit(repo, "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                           capture_output=True, text=True,
                           check=True).stdout.strip()
    out = tmp_path / "inv"

    # A marker quoting the sentence INEXACTLY. The absorbed path needs an
    # exact match, so this must not clear - and the marker must not clear it
    # by resembling it either.
    skill.joinpath("SKILL.md").write_text(
        "# Example skill\n\n"
        '<!-- absorbed: "You must record the owning team before it can '
        'land and ship." -->\n')
    _commit(repo, "a marker that misquotes the sentence")
    result = _run_inventory(repo, base, out)
    assert result.returncode != 0, (
        "a misquoted marker cleared the sentence, so any marker clears any "
        "sentence:\n" + result.stdout + result.stderr)

    # The same sentence quoted exactly does clear it.
    skill.joinpath("SKILL.md").write_text(
        "# Example skill\n\n"
        '<!-- absorbed: "You must record the owning team before it can '
        'land." -->\n')
    _commit(repo, "a marker that quotes the sentence exactly")
    result = _run_inventory(repo, base, out)
    assert result.returncode == 0, result.stdout + result.stderr


def test_pbw_d8_the_excluded_paths_are_out_of_every_sweep():
    """`docs/system-spec.md`, `cli/vendor/yaml/`, `cli/vendor/LICENSE-PyYAML`,
    `LICENSE` and `assets/` never appear in `scanned_paths()`, so no sweep in
    group A can report a finding inside them. `PBW-D8`.

    The pending-list ratchet that used to be checked here went with the
    lists: the last batch deleted the last one, so there is nothing left to
    hold pairwise disjoint or shrink-only."""
    scanned = {str(p.relative_to(REPO_ROOT)) for p in scanned_paths()}
    for excluded in EXCLUDED_PATHS:
        if excluded.endswith("/"):
            assert not any(p.startswith(excluded) for p in scanned), excluded
        else:
            assert excluded not in scanned, excluded
    assert scanned, "scanned_paths() must not be empty"


def test_pbw_d1_every_tracked_yaml_file_parses():
    """`_yaml_spans` catches `yaml.YAMLError` and silently falls back to
    whole-line comments only, so a YAML file that does not parse loses every
    `PROSE_KEYS` value the sweeps would otherwise read - and nothing says
    so. Finding 12, `review-dimensions.md`: `schemas/manifest.reference.yml`
    and `schemas/routing-policy.reference.yml` both failed to parse, on a
    `key:# comment` with no space between the colon and the `#`, which YAML
    reads as an unterminated key rather than a mapping entry with a trailing
    comment. Both are fixed; this is the guard against the next one."""
    unparseable = []
    for path in scanned_paths():
        if path.suffix not in (".yml", ".yaml"):
            continue
        rel = str(path.relative_to(REPO_ROOT))
        try:
            yaml.compose(_read(path) or "")
        except yaml.YAMLError as exc:
            unparseable.append(f"{rel}: {exc}")
    assert not unparseable, (
        "these tracked YAML files do not parse, so the sweeps silently "
        "read only their whole-line comments:\n" + "\n".join(unparseable))


#: The kinds of finding the excluded derived spec is allowed to contain, and
#: the ground the exclusion rests on: an archived scenario title is a record
#: of what a scenario was called when it ran. A sixth kind would not be that,
#: so it needs a reader before the exclusion still covers it.
SYSTEM_SPEC_KINDS = frozenset({
    "PBW-A1", "PBW-A2", "PBW-A3", "PBW-A5", "PBW-A7"})


def test_pbw_d8_system_spec_findings_are_the_recorded_kinds():
    """`docs/system-spec.md`'s exclusion names what it hides so a reader can
    check it rather than take it on trust (finding 7,
    `review-dimensions.md`).

    The kinds are pinned and the totals are not. Every landed issue appends
    its scenario titles to this derived file, so a total can only rise and a
    pinned total fails on the next issue to land rather than on anything
    being wrong. That is what happened first: this test pinned 286, the spec
    was re-derived at ship, one more word-table hit arrived with the new
    titles, and continuous integration failed on a number that was never the
    point. A sixth KIND is the thing worth stopping, because the exclusion's
    reasoning covers archived titles and nothing else."""
    spans = (_spans_for_file(REPO_ROOT / "docs" / "system-spec.md")
             + _spans_for_file(REPO_ROOT / "docs" / "system-spec-archive.md"))
    by_rule = {rid: len([f for s in spans for f in rule.find(s)])
               for rid, rule in RULES.items()}
    unexpected = {rid: n for rid, n in by_rule.items()
                  if n and rid not in SYSTEM_SPEC_KINDS}
    assert not unexpected, (
        f"docs/system-spec.md reports a kind of finding the exclusion's "
        f"reasoning does not cover: {unexpected}. The exclusion rests on "
        f"these being archived scenario titles; read the new findings before "
        f"widening it. Recorded kinds: {sorted(SYSTEM_SPEC_KINDS)}.")


def test_pbw_e1_prose_keys_are_the_one_shared_list():
    """`tests/test_writing_style.py` and `scripts/compare-behaviour.py` now
    read `PROSE_KEYS` from `scripts/prose_keys.py`, the same object either
    way - so the two halves cannot disagree about what prose is. Finding 1,
    `review-dimensions.md`: they did, over `biases`, until this module
    existed. `_yaml_spans` also reads a prose sequence item now, not only a
    scalar value, so a `biases:` list is not silently skipped either."""
    from scripts.prose_keys import PROSE_KEYS as SHARED_PROSE_KEYS
    assert PROSE_KEYS is SHARED_PROSE_KEYS, (
        "the sweep's PROSE_KEYS must be the shared module's own object, "
        "not a second copy that can drift from it again")
    assert "biases" in PROSE_KEYS

    text = (
        "routing_strategies:\n"
        "  biases:\n"
        '    - "We need to verify the Frame phase artefact."\n'
    )
    spans = _yaml_spans("governance/routing-policy.yml", text)
    joined = " ".join(s.text for s in spans)
    assert "Frame phase artefact" in joined, (
        "a biases: sequence item must be read as a prose span, not skipped "
        "the way a machine value is")


def test_pbw_c4_the_stage_key_rename_block_has_a_marker():
    """A second copied block, alongside the vocabulary-rename one
    `COPIED_BLOCK_MARKERS` already names: the stage-key rename explanation
    ("The stage keys moved on 2026-08-24 ... Re-pointed, not relaxed.")
    copied into `tests/derive/test_derive_system_spec.py`. Found by a second
    review, reading `tests/derive/test_derive_system_spec.py:18-23`: the
    check reported clean with an instance still on disk, because no marker
    named its opening phrase."""
    span = ProseSpan(
        "tests/derive/test_derive_system_spec.py", 18,
        "The stage keys moved on 2026-08-24 - `frame` -> `assess`",
        "comment")
    assert _find_copied_block(span), (
        "the stage-key rename block's opening phrase must be a named "
        "marker, the same as the vocabulary-rename block's")



def test_other_frameworks_records_are_left_out_and_nothing_else_is():
    """Files in another framework's overlay under `evals/scenarios/` are in
    that framework's own words, so no Compass writing rule reads them; every
    other file under `evals/scenarios/` is still scanned, and at least one
    overlay file exists, so the rule is not checking nothing."""
    scanned = {str(p.relative_to(REPO_ROOT)) for p in scanned_paths()}
    tracked = [r for r in _git_ls_files() if r.startswith("evals/scenarios/")]
    overlays = [r for r in tracked if _is_other_frameworks_record(r)]
    assert overlays, "no other framework's record is tracked"
    assert sorted(r for r in tracked if r not in scanned) == sorted(overlays)
