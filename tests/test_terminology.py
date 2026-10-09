"""The v2 vocabulary freeze, enforced.

`governance/terminology.yml` is the frozen v2 vocabulary: every term with its
exact meaning, the banned v1 words, and the scan config naming which
user-facing surfaces are checked. This file is the mechanical half of that
freeze - the same shape as `tests/test_house_style.py`, which enforces the
repository's writing style: these are invariants of this repository's own
prose, never a check an adopting project runs.

Three groups of checks:

1. Well-formedness. The vocabulary file exists, parses, and every entry
   carries the fields that make it usable: a meaning per term, a replacement
   and a context per ban, and the three scan lists.
2. Scanner precision, proven by fixtures. Each ban is enforced as one or more
   tuned regexes, not a bare word. `tests/fixtures/terminology/` holds two
   files: one planting every banned usage (each must be flagged), one reusing
   the same words innocently (none may be flagged). The context notes in the
   vocabulary file are the intent; the patterns here are the executable form;
   the fixtures prove the two agree. Pattern tuning lives here, beside the
   fixtures, and accumulates as rename slices clean their surfaces.
3. The ratchet. A surface still listed in `pending_surfaces` may carry banned
   terms without failing, so CI stays green while the rename is in flight. A
   surface absent from that list must be clean, forever. The pending list may
   only ever shrink: the committed baseline below is the high-water mark, and
   a rename slice's definition of done includes removing its surface from
   both the vocabulary file and that baseline in the same diff.

Docstrings cite the acceptance criteria they satisfy by TRC id; the criteria
live in this issue's archived spec, indexed in its `manifest.yml` (machine state,
exempt from the vocabulary scan during the transition).
"""
from __future__ import annotations

import ast
import os
import re
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent
TERMINOLOGY_PATH = REPO_ROOT / "governance" / "terminology.yml"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "terminology"
FIXTURE_BANNED = FIXTURE_DIR / "banned_usage.md"
FIXTURE_INNOCENT = FIXTURE_DIR / "innocent_usage.md"

# Directory noise never worth scanning, whatever the surface list says.
PRUNE_DIRS = {
    ".git", "__pycache__", ".ruff_cache", ".pytest_cache", ".mypy_cache",
    ".idea", ".vscode", "node_modules", "dist", "build",
}

MAX_REPORTED = 40

# ---------------------------------------------------------------------------
# The tuned ban patterns - the executable form of the `banned:` context notes.
#
# Keys are the exact `term` strings in governance/terminology.yml;
# test_every_ban_is_bound_to_a_pattern holds the two files in one-to-one
# correspondence. Each ban is pattern-plus-context, never a bare word: the
# fixture pair under tests/fixtures/terminology/ is the proof that each
# pattern catches the banned sense and tolerates the ordinary one.
# ---------------------------------------------------------------------------
BAN_PATTERNS: dict[str, list[re.Pattern]] = {
    # The v1 assess stage's own retired name, banned in its turn. `triage` as
    # an ordinary verb - sorting BETWEEN things by urgency, which is what
    # `compass flow` does - stays legal; the stage name and command do not.
    "Triage": [
        re.compile(r"/compass:triage\b"),
        # Capitalised, anywhere. Five narrower shapes stood here until
        # 2026-08-25 - `Triage phase|stage`, the two arrow forms, a heading, <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # and `during|at|before Triage` - and between them they caught NONE of <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # the 57 live occurrences across 30 shipped files, because the tree
        # writes it in table cells (`| Triage |`) and ordinary sentences <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # ("Triage reads the four dimensions"). This one pattern subsumes all <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # five and catches those: capital-T Triage is always the stage name. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        #
        # LOWERCASE `triage` IS NOT BANNED HERE. The ordinary verb - sorting
        # BETWEEN cases by urgency, which is what `compass flow` does - stays
        # legal, and the tree also still uses lowercase `triage` for the stage
        # in roughly 200 places. Separating those two senses needs reading, not
        # a regex; it is its own issue rather than a silent widening here.
        re.compile(r"\bTriage\b"),
    ],
    # A changed assessment. The command is /compass:assess --reassess and the
    # manifest key is `reassessments`, so the output says re-assessment too.
    # The ordinary verb "frame" is a different word and stays legal.
    "reframe / re-frame": [
        re.compile(r"\bre-?fram(?:e|es|ed|ing)\b", re.IGNORECASE),
    ],
    # The designer's command, which went back to /compass:design.
    "Wireframe": [
        re.compile(r"/compass:wireframe\b"),
        re.compile(r"\bWireframe\s+(?:phase|stage|command)\b"),
        re.compile(r"^#+\s+Wireframe\b", re.M),
    ],
    # The intake document. `prd.md` is the filename; "product requirements" as <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # ordinary prose stays legal.
    "PRD / prd.md": [
        re.compile(r"\bprd\.md\b"),
        re.compile(r"\btemplates/prd\b"),
        # The bare acronym, which the two patterns above never touched - so
        # 24 live occurrences survived, including `commands/intent.md`'s own
        # description line, the sentence a user reads in the slash-command
        # menu, which said the command captures intent "as a PRD" while <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # writing intent.md. Naming the document. "Product requirements" as
        # ordinary prose is still fine.
        re.compile(r"\bPRD\b"),
    ],
    # The v1 triage phase and its agent, as names and command. Ordinary
    # lowercase "frame" (the verb) stays legal.
    "Frame / the Needle": [
        re.compile(r"/compass:frame\b"),
        re.compile(r"\bFrame\s+phase\b"),
        re.compile(r"\bthe\s+Needle\b"),
        re.compile(r"\bFrame\s*(?:→|->)"),
        re.compile(r"(?:→|->)\s*Frame\b"),
        re.compile(r"^#+\s+Frame\b", re.M),
        # Tuned at the skills-prose review: the capitalised stage name
        # after a preposition ("during Frame,") is stage-name usage the <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # suffix forms above miss; lowercase "frame the problem" stays
        # legal.
        re.compile(r"\b(?:during|at|before|after|since|until)\s+Frame\b"),
        # --- the total ban -------------------------------------------------
        # Three designs were tried. Enumerating shapes caught 85 of 149 live
        # occurrences. Capitalisation caught 297 and still left 102 - after a
        # slash, inside parentheses, inside a longer bold run, possessive - and
        # the scan reported zero while all 102 sat there, which is the exact
        # failure this issue exists to repair, repeating inside its own repair.
        #
        # So: the capitalised name is banned outright on live surfaces, and the
        # legitimate uses carry an inline `vocabulary-scan: allow - <reason>`
        # marker naming why. There are few of them and each is nameable; an
        # allowlist is the only shape in which "no retired stage name survives"
        # is a property this check actually holds.
        #
        # Case-sensitive on purpose. Lowercase is ordinary English - you frame a
        # problem, a spike does not land production code - and stays legal
        # without a marker.
        re.compile(r"\bFrame\b"),
    ],
    # The four-dimension judgement. The plural is the v1 term of art;
    # singular "reading" (the ordinary gerund) stays legal.
    "reading / readings": [
        re.compile(r"\breadings\b", re.IGNORECASE),
        re.compile(r"\bdimension\s+reading\b", re.IGNORECASE),
    ],
    # The computed process shape. Ordinary "route" (a path somewhere)
    # stays legal; the file, the command, and the qualified process
    # senses do not.
    "route": [
        re.compile(r"\broute\.md\b"),
        re.compile(r"\broute\s+evaluate\b"),
        # Not preceded by a path separator: `src/api/routes/search.py` is a
        # web router directory, which is ordinary in almost any codebase.
        # The ban is about a Compass `routes/` directory at the top level. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        re.compile(r"(?<![\w/.-])routes?/"),
        # Case-insensitive on the qualifier: "**Reference route:**" is how a <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # heading writes it, and the lowercase-only pattern walked past every
        # one of them in the shipped examples.
        re.compile(
            r"\b(?:computed|reference|delivery|solo|swarm|"
            r"express|standard|expedition|hotfix|spike)\s+routes?\b",
            re.IGNORECASE,
        ),
        # Tuned at the skills-prose review, widened at the docs-prose
        # review: the compose/compute verb family on the process noun
        # (the thing composed or computed is the delivery approach);
        # "computed a route home" stays legal.
        # Present and progressive forms with either article; past tense
        # only with "the" - "computed a route home" is ordinary English.
        re.compile(r"\b(?:comput|compos)(?:es?|ing)\s+(?:the|a)\s+route\b"
                   r"|\b(?:computed|composed)\s+the\s+route\b"),
    ],
    # The v1 name for a quick fix. Capitalised only: "express delivery"
    # stays legal.
    "Express": [
        re.compile(r"\bExpress\b"),
    ],
    # The v1 name for an initiative-scale delivery. Capitalised only.
    "Expedition": [
        re.compile(r"\bExpedition\b"),
    ],
    # The v1 phase names, as names: command, "X phase", pipeline arrows,
    # headings. Ordinary lowercase verbs ("specify the format", "landing
    # gear") stay legal.
    "Specify / Clarify / Distribute / Land": [
        re.compile(r"/compass:(?:specify|clarify|distribute|land)\b"),
        re.compile(r"\b(?:Specify|Clarify|Distribute|Land)\s+phase\b"),
        re.compile(r"(?:→|->)\s*(?:Specify|Clarify|Distribute|Land)\b"),
        re.compile(r"\b(?:Specify|Clarify|Distribute|Land)\s*(?:→|->)"),
        re.compile(r"^#+\s+(?:Specify|Clarify|Distribute|Land)\b", re.M),
        # Tuned at the skills-prose review: the capitalised stage name
        # after a preposition or conjunction ("at Land", "and Land", <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # "during Specify") is stage-name usage the suffix forms miss; <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # lowercase ordinary verbs ("planes land") stay legal.
        re.compile(r"\b(?:during|at|before|after|since|until|and|into)\s+"
                   r"(?:Specify|Clarify|Distribute|Land)\b"),
        # Banned outright, like Frame above and for the same reason. See the <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # comment there for the two designs that were measured and rejected.
        re.compile(r"\b(?:Specify|Clarify|Distribute|Land)\b"),
    ],
    # The role-perspective concept, in any casing. Tuned at the
    # skills-prose slice: a hyphen-preceded "lens" is an agent identifier <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # (product-owner, architect, product-marketer) - machine vocabulary
    # that keeps its spelling until an agent-rename decision - and is no
    # longer flagged. The concept word alone still is.
    # The carve-out for a hyphen-preceded "lens" is gone: it existed only <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # while the agents were still called product-lens, marketing-lens and <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # architect-lens, and ADR-023 renamed them after their roles. The bare <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # pattern now catches the identifiers too, which is the point.
    "lens": [
        re.compile(r"\blens(?:es)?\b", re.IGNORECASE),
    ],
    # ADR-023. Three of these need a tuned pattern because the word has an
    # ordinary sense the ban must not touch; the rest are unambiguous.
    #
    # `stream`: the lookbehind is what makes `upstream` and `downstream` <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # invisible. Measured before the ban was written - 40 upstream/downstream
    # uses in scanned prose, 116 of the unit-of-work sense, and zero uses of
    # the data-flow sense ("event stream", "output stream"). So the lookbehind <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # is the whole of the ambiguity.
    "stream": [
        re.compile(r"(?<![a-z-])streams?\b", re.IGNORECASE),
    ],
    # `topology` and `ceremony` keep their ordinary senses, which is why the <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # ban entries say so; the patterns are plain because those senses do not
    # appear in this repository's prose.
    "swarm": [re.compile(r"\bswarms?\b", re.IGNORECASE)],
    "topology": [re.compile(r"\btopolog(?:y|ies)\b", re.IGNORECASE)],
    "charter": [re.compile(r"\bcharters?\b", re.IGNORECASE)],
    "ceremony": [re.compile(r"\bceremon(?:y|ies)\b", re.IGNORECASE)],
    "distillation": [re.compile(r"\bdistil(?:l)?(?:ation|ing|ed|s)?\b", re.IGNORECASE)],
    "coherence check": [re.compile(r"\bcoherence[- ]check", re.IGNORECASE)],
    "fitness function": [re.compile(r"\bfitness[- ]functions?\b", re.IGNORECASE)],
    "navigator": [re.compile(r"\bnavigators?\b", re.IGNORECASE)],
    "roundtable": [re.compile(r"\broundtables?\b", re.IGNORECASE)],
    "elicitation": [re.compile(r"\belicit(?:ation|ing|ed|s)?\b", re.IGNORECASE)],
    # The v1 risk dimension, prose or key form.
    "blast radius": [
        re.compile(r"\bblast[\s_-]radius\b", re.IGNORECASE),
    ],
    # The v1 familiarity dimension.
    "terrain": [
        re.compile(r"\bterrain\b", re.IGNORECASE),
    ],
    # The v1 size dimension. "order(s) of magnitude" is ordinary English <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # and stays legal.
    "magnitude": [
        re.compile(r"(?<!order of )(?<!orders of )\bmagnitude\b", re.IGNORECASE),
    ],
    # The v1 domain-tag mechanism. Ordinary "touches" (the verb) stays
    # legal; the underscored keys and the bare key-in-prose form do not.
    # (Code spans no longer shelter it: ADR-015 brought them into the scan
    # once ADR-014 removed the live v1 names. A genuine machine identifier
    # that must keep its spelling carries a `vocabulary-scan: allow` marker
    # with a reason.)
    "touches": [
        re.compile(r"\btouches?_(?:any|common)\b"),
        re.compile(r"\btouches:\s"),
    ],
    # The v1 word for owed follow-up work. The DoD tag and the manifest key
    # renamed with schema 2.0 ("(follow-up:" and "follow_ups:"); the CLI
    # verb renamed with the CLI-voice slice (`compass follow-up resolve`),
    # which re-tightened this ban to its final form - no tolerated
    # spelling remains. Ordinary "backfilled" (the plain verb, past tense)
    # stays legal.
    "backfill": [
        re.compile(r"\bbackfills?\b", re.IGNORECASE),
    ],
    # The v1 work-item noun in human-facing prose. Machine-state forms
    # stay legal during the transition: manifest.yml, current-task, --task, <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # issue-slug and friends.
    "task": [
        # The `--task` exemption is gone: it was there because --task was a <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # live flag spelling, and ADR-014 removed it. Prose teaching it now
        # teaches a flag that does not parse, so the ban should say so.
        #
        # NARROWED to the word meaning an issue. It is also one of the three
        # issue types (feature, bug or task), so the pattern lets it through
        # where a type is named: after "bug and", "bug or" or "bug," (the
        # list), after "type is", "type to" or "type:" (a type being set),
        # and before "type".
        re.compile(
            r"(?<!current-)(?<!<)(?<!bug and )(?<!bug or )(?<!bug, )"
            r"(?<!type is )(?<!type to )(?<!type: )"
            r"\btasks?\b(?!\.yml)(?![-_>])(?!\s+types?\b)",
            re.IGNORECASE,
        ),
    ],
    # Governance shorthand codes STANDING IN FOR the rule. "satisfy S2" tells <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # a reader nothing; "write the failing test first" does.
    #
    # A BACKTICKED code is exempt, because that is a cross-reference beside a
    # rule that has already been stated in full - the same shape as citing an
    # ADR by id. The range was `S[1-7]` while the file defined S1 to S12, so <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # every strategy added after S7 sat outside the ban meant to govern it; <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # widening it to `S\d+` without this exemption then flagged the pointers
    # that `S11` and `S12` need by test.
    #
    # The plain statement of the rule replaces the code. The ban's own context says
    # "codes may live in governance config" - governance/ is where they are
    # DEFINED, and a definition has to name the thing it defines. That
    # exemption is in TERM_SURFACE_EXEMPT below; it used to be implicit in
    # the scan not reading those files, which stopped being true when the
    # scan widened.
    "G1..G5 / S1..S14 codes, bare": [
        re.compile(r"(?<!`)\bG[1-5]\b(?!`)"),
        re.compile(r"(?<!`)\bS\d+\b(?!`)"),
    ],
    # The issue's machine-readable file, called the spine until ADR-022 renamed
    # it to the manifest. An actual backbone, or the spine of a book, is
    # ordinary English and must not fire - so the pattern needs a nearby
    # Compass structural word rather than matching the bare noun. A backticked
    # or quoted use is exempt: the migration table and the rename test both
    # have to name the old spelling to do their job.
    "spine / issue spine": [
        re.compile(r"(?<![`\"'])\bspines?\b(?![`\"'])"
                   r"(?=[^.\n]*\b(issue|manifest|task|record|artifact|evidence|"
                   r"gate|scenario|assessment|worktree|yml|machine-readable|stages|delivery approach|changed.files|key)\b)",
                   re.I),
        re.compile(r"\b(issue|task)[- ]spines?\b(?![`\"'])", re.I),
    ],
    # Structural metaphor only. "the seam of a garment" is ordinary English and
    # must not fire, so the patterns need a structural noun nearby rather
    # than matching the bare word. Both fixtures prove the pair: banned_usage.md
    # plants the structural forms, innocent_usage.md the ordinary ones.
    # A quoted or code-spanned use is exempt - the reader needs it to search.
    "seam / seams": [
        re.compile(r"(?<![`\"'])\bseams?\b(?![`\"'])"
                   r"(?=[^.\n]*\b(architect\w*|module|service|layer|boundar\w+|"
                   r"interface|component|code|system|surface|abstraction)\b)",
                   re.I),
        re.compile(r"\b(along|across|find|the natural|cut\w*)\s+(the\s+)?seams?\b"
                   r"(?![`\"'])", re.I),
    ],
    # The v1 intake artifact filename; v2 writes intent.md. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    "vacuous / vacuity / orthogonal / elide / salient": [
        # Plain-word rule: accurate but almost never used in ordinary speech,
        # so it costs a junior or mid engineer a lookup at the moment they are
        # reading a result. tests/test_plain_words.py holds the surface rule;
        # this binds the ban so the vocabulary and the scan agree.
        re.compile(r"(?i)\bvacuous\b"),
        re.compile(r"(?i)\bvacuit(?:y|ies)\b"),
        re.compile(r"(?i)\borthogonal(?:ly|ity)?\b"),
        re.compile(r"(?i)\belid(?:e|es|ed|ing)\b"),
        re.compile(r"(?i)\bsalient\b"),
    ],
    "brief.md": [
        re.compile(r"\bbrief\.md\b"),
    ],
    # The v1 acceptance-criteria artifact filename.
    "spec.feature.md": [
        re.compile(r"\bspec\.feature(?:\.md)?\b"),
    ],
}

# The ratchet's high-water mark: every surface still awaiting its rename
# slice as of the freeze. test_pending_list_only_ever_shrinks compares the
# vocabulary file's live `pending_surfaces` against this frozenset, so the
# live list can drop entries but never gain one. A rename slice removes its
# surface from the vocabulary file AND from here in the same diff, which is
# what makes the shrink visible in review.
# EMPTY since the second half of the docs-prose slice: the ratchet
# reached zero, and the shrink-only meta-test holds it there - a surface
# can never re-enter.
PENDING_BASELINE: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Loading and scanning
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _terminology() -> dict:
    """The parsed vocabulary file, loaded once per test session."""
    if not TERMINOLOGY_PATH.exists():
        pytest.fail(
            "governance/terminology.yml does not exist. It is the frozen v2 "
            "vocabulary; land it alongside this test (content spec: "
            "docs/proposals/terminology.yml)."
        )
    return yaml.safe_load(TERMINOLOGY_PATH.read_text(encoding="utf-8"))


def _read(path: Path) -> str | None:
    """File text, or None when the file is binary or has gone away."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


INLINE_CODE_RE = re.compile(r"`[^`]+`")


_YAML_KEY_RE = re.compile(r"^\s*-?\s*[\w.\-/]+\s*:")
_YAML_INLINE_KEY_RE = re.compile(r"(?<![\w.\-/])[\w.\-/]+\s*:")


def _scan_units(path: Path) -> list[tuple[int, str]]:
    """The (line number, text) pairs the scanner checks for one file.

    Two surfaces get less than full text, for the same reason: the scan
    measures what a surface *teaches*, not what the machinery is now
    named. `cli/compass` contributes only its Python string literals. In
    markdown, fenced code blocks and inline code spans are machine
    identifiers - a backticked `/compass:frame` names a command that really <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    is still called that during the transition - so markdown contributes
    prose only. The rename slices tighten this by making the old names
    disappear from the machinery itself; until then, prose must be clean v2
    vocabulary and live v1 names appear only as code.
    """
    text = _read(path)
    if text is None:
        return []
    if path == REPO_ROOT / "cli" / "compass" or path.suffix == ".py":
        # Python surfaces contribute USER-FACING string literals only.
        # Tightened when the surface widened to cli/compass_pkg/ at the
        # CLI-voice slice, with two deliberate exclusions:
        #   - docstrings: they teach the developer reading the source, not
        #     the user at the terminal; the scan measures what the CLI
        #     *says*, and a docstring is never printed.
        #   - literals with no whitespace: a single token is a machine
        #     identifier (a manifest key, a filename, a flag), not prose.
        # Before this, cli/compass was pending and the scan never ran
        # against it, so no enforcement is loosened by the exclusions.
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return list(enumerate(text.splitlines(), 1))
        docstrings: set[int] = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if (isinstance(node, (ast.Module, ast.FunctionDef,
                                  ast.AsyncFunctionDef, ast.ClassDef))
                    and body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
        units = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if id(node) in docstrings or " " not in node.value:
                    continue
                for offset, line in enumerate(node.value.splitlines()):
                    units.append((node.lineno + offset, line))
        return units
    if path.suffix == ".md":
        # Full text, code spans and fenced blocks included. Both used to be
        # stripped, and the reason was real at the time: a backticked
        # `/compass:frame` named a command that really was still called that <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # during the transition. ADR-014 removed those names at the major
        # version, so the exclusion had nothing left to protect - and it was
        # hiding a quickstart that told new users to run a command which no
        # longer exists, fourteen times, on a scanned surface. See ADR-015.
        return list(enumerate(text.splitlines(), 1))
    if path.suffix == ".sh":
        # A shell script's prose is its comments AND the messages it prints,
        # and both matter here - the hook's stderr is the most user-facing
        # text Compass has. So: full text, minus the embedded Python.
        #
        # The hooks run Python through `compass_python - <<'PYEOF'`, and that
        # block is code, not prose: `task = yaml.safe_load(...)` is a variable <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        # name. Scanning it would flag correct code and teach the next author
        # to work around the guard rather than with it.
        units, in_python, delim = [], False, ""
        for lineno, line in enumerate(text.splitlines(), 1):
            if not in_python:
                # ONLY a heredoc handed to a Python interpreter. Matching any
                # uppercase delimiter would also swallow a `cat >&2 <<EOF`
                # message in a hook - user-facing text this scan must read.
                m = re.search(r"<<'?([A-Z_]{2,})'?\s*$", line.rstrip())
                if m and re.search(r"\bpython3?\b|compass_python", line):
                    in_python, delim = True, m.group(1)
                    continue
            else:
                if line.strip() == delim:
                    in_python = False
                continue
            units.append((lineno, line))
        return units
    if path.suffix == ".json":
        # A JSON schema's prose is its `description` and `title` values -
        # the text a validation error quotes back at a user, and the closest
        # thing the schema has to documentation. Keys and enum values are the
        # machine contract and are renamed with a migration, not a sweep.
        units = []
        for lineno, line in enumerate(text.splitlines(), 1):
            if '"description"' in line or '"title"' in line:
                units.append((lineno, line))
        return units
    if path.suffix in (".yml", ".yaml"):
        # Values ARE scanned - that is the inversion (PX-1, PX-2 in
        # terminology.yml). A `rationale:` value is printed verbatim to the
        # terminal by `compass approach evaluate`, so it is prose whatever
        # file it lives in; reading only the comments is how "checked before
        # Land" reached a screen past a green scan. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
        #
        # Exempt, by declared exemption: the comment (PX-1 - the parser
        # discards it) and the key itself (PX-2 - machine contract, renamed by
        # migration). So each line contributes its value, with the key and any
        # trailing comment removed.
        units = []
        for lineno, line in enumerate(text.splitlines(), 1):
            # The allow marker lives in a comment, and comments are exempt -
            # so the marker line has to be emitted anyway or the exemption
            # mechanism cannot see it. Emitting it is safe: the marker text
            # carries no banned word, and _scan_files consumes the line as a
            # marker rather than scanning it.
            if ALLOW_MARKER_RE.search(line):
                units.append((lineno, line))
                continue
            body = line.split("#", 1)[0]
            m = _YAML_KEY_RE.match(body)
            value = body[m.end():] if m else body
            # PX-2 again, for nested keys: `stages: { frame: light, ... }`
            # carries its keys inline, and those are the same machine contract
            # as a key on its own line. A key is always the token immediately
            # before a colon, so blanking that shape removes them.
            value = _YAML_INLINE_KEY_RE.sub(" ", value)
            if value.strip():
                units.append((lineno, INLINE_CODE_RE.sub(" ", value)))
        return units
    # The DEFAULT IS TO SCAN. A file type with no rule above contributes every
    # line. A position is excluded by being declared in
    # terminology.yml `scan.position_exemptions`, never by falling through.
    return list(enumerate(text.splitlines(), 1))


def _NAMED_SURFACES() -> set:
    """Surfaces named as individual files rather than directories."""
    return {s for s in _terminology()["scan"]["surfaces"]
            if not s.endswith("/")}


# --- region exemptions ------------------------------------------------------
# A file can be scanned while some of its lines are not. `banned:` must name
# every retired term - that is what a ban is - so scanning it whole would flag
# the vocabulary file for doing its job, and exempting the FILE would stop
# scanning the glossary's prose, which is the half a reader learns from.
# Declared in terminology.yml's `scan.exempt_regions`, each with a reason.

def _region_exempt_linenos(rel: str, lines: list) -> set:
    """1-based line numbers inside a declared exempt region of `rel`.

    A region is a top-level YAML block: it starts at `<name>:` in column zero
    and runs to the next line in column zero.
    """
    exempt = set()
    for entry in _terminology()["scan"].get("exempt_regions") or []:
        if str(entry.get("path")) != str(rel):
            continue
        wanted = set(entry.get("blocks") or [])
        current = None
        for lineno, line in enumerate(lines, 1):
            if line[:1].strip() and not line.startswith(("#", " ", "\t")):
                current = line.split(":", 1)[0].strip()
            if current in wanted:
                exempt.add(lineno)
    return exempt


def _surface_files(surface: str) -> list[Path]:
    """Every scannable file a surface entry names.

    A trailing slash means a directory, scanned recursively. `governance/`
    contributes only its prose (`*.md`): its YAML files legitimately carry
    machine identifiers, and the vocabulary file itself names every banned
    term by necessity.
    """
    root = REPO_ROOT / surface
    if not surface.endswith("/"):
        return [root] if root.is_file() else []
    if not root.is_dir():
        return []
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if PRUNE_DIRS & set(path.parts):
            continue
        if (surface == "governance/" and path.suffix != ".md"
                and str(path.relative_to(REPO_ROOT)) not in _NAMED_SURFACES()):
            # `governance/` contributes its prose; its YAML files legitimately
            # carry machine identifiers. A YAML file that IS named as its own
            # surface is scanned - otherwise the directory entry silently
            # cancels the explicit one, which is how terminology.yml stayed
            # unscanned while sitting inside a scanned surface.
            continue
        files.append(path)
    return files


# A line may name a retired term when naming it IS the job - reading an old
# archive, quoting historical output verbatim, or documenting the rename
# itself. Such a line carries the marker below, and the marker needs a
# reason after the colon, so an exemption is a sentence somebody wrote rather
# than a switch somebody flipped.
#
#     grep -rn "vocabulary-scan: allow" .      # every exemption, enumerable
#
# ADR-015 is explicit that this is the resolution for a legitimate case, and
# equally explicit that quietly widening the scan is not.
# A banned term may be legitimate on a specific surface. Not a loophole: each
# entry implements a context note already written in the ban itself, and the
# list is short enough to read.
TERM_SURFACE_EXEMPT = {
    # The guardrails and strategies are where G1..G5 and S1..S14 are defined. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # A definition names the thing it defines; banning the code here would
    # mean governance could not label its own rules.
    # governance/ DEFINES the codes; schemas/ describes the fields that
    # carry them, which is the same act one layer down - a schema saying
    # "the shipped default guardrails (G1-G5)" is naming what it validates. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    #
    # NARROWED from the whole of governance/ to its machine-readable files
    # (issue plain-language-3-2-0, design decision `DD-9`). A policy file's
    # `when: {risk: critical}` clause cannot gloss its own ids, so those stay
    # exempt. governance/strategies.md is different: it is prose a contributor
    # reads, and it is where this project states the rule about bare codes -
    # so the prefix made the one file the rule could not reach the one file
    # stating it. The identical bare code in agents/reviewer.md was caught in
    # under a minute while the copy in strategies.md was not.
    #
    # The .md files under governance/ are scanned. A deliberate illustration of
    # the wrong form carries a `vocabulary-scan: allow` marker and a reason,
    # which is enumerable by grep; a path prefix is not.
    "G1..G5 / S1..S14 codes, bare": (
        "governance/guardrails.yml", "governance/routing-policy.yml",
        "governance/terminology.yml", "governance/signals.yml",
        "schemas/", "architecture/",
    ),
    # writing-voice.md teaches by quoting this repository's own archive
    # verbatim, and tests/test_human_voice.py hashes those quotations against
    # the archived files. Its retired stage names are inside quotations of
    # sessions that really said them; editing one would falsify the quote,
    # and the quote guard fails the build if anyone tries. Exempt at file
    # granularity rather than per line because an inline marker breaks the
    # before/after parsing that same guard depends on.
    # scripts/verify-archive-quotes.py holds the quoted spans it verifies. The
    # retired name in one of them is what the archived file actually says, and
    # a sweep rewrote it - so the script briefly checked a sentence nobody had
    # written, and its own guard failed within seconds. Exempt at file
    # granularity because Python surfaces contribute string literals only, so
    # an inline marker in a comment is invisible to the scanner.
    "Specify / Clarify / Distribute / Land": (
        "skills/compass-runtime/writing-voice.md",
        "scripts/verify-archive-quotes.py",),
    "Frame / the Needle": ("skills/compass-runtime/writing-voice.md",),
    # The rename to `manifest` (ADR-022, "The issue record is a manifest").
    # writing-voice.md quotes archived sessions that used the old word and
    # tests/test_human_voice.py hashes those quotations against the archived
    # files, so editing one falsifies the quote. cli/migrate-map.yml must name
    # both spellings or nothing could migrate, and the decision record has to
    # say what it renamed and why.
    "spine / issue spine": (
        "skills/compass-runtime/writing-voice.md",
        "cli/migrate-map.yml",
        "architecture/decisions/ADR-022-the-issue-record-is-a-manifest.md",
    ),
    # ADR-004's decision IS the word - it is titled "one spec, many lenses" - <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # so the record keeps it (ADR-023). The broad "architecture/" prefix this
    # replaced was only needed while the agents were still called *-lens. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # A file that merely CITES the record carries a line-level
    # `vocabulary-scan: allow` marker instead - see
    # skills/bdd-specification/refinement-chain.md. A file-wide entry would
    # also excuse a future prose use of the word in that file, silently, and
    # the marker is greppable where a path prefix is not.
    "lens": ("architecture/decisions/ADR-004-one-spec-many-lenses.md",),
    # writing-voice.md quotes archived devlogs verbatim and names real issue
    # directories. tests/test_human_voice.py hashes those quotations against
    # the archived files, so editing one falsifies the quote - the same reason
    # `spine / issue spine` is exempt there.
    "stream": ("skills/compass-runtime/writing-voice.md",),
    "swarm": ("skills/compass-runtime/writing-voice.md",),
    # ADR-009 is titled "fitness functions are project guardrails"; same rule. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    # skills/evidence-gates/architecture-checks.md cites the filename and
    # quotes the title verbatim, and carries a line-level marker on each - the
    # same reason as "lens" above. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    "fitness function": (
        "architecture/decisions/ADR-009-fitness-functions-are-project-guardrails.md",
    ),
}


# Imported rather than defined: see tests/allow_marker.py for why a letter
# is required and why three copies of this rule drifted apart.
from allow_marker import ALLOW_MARKER_RE  # noqa: E402


def _scan_files(files: list[Path]) -> list[str]:
    """Every banned-term hit across `files`.

    Each hit names the file, line, banned term, and the pattern that
    matched, so a failure is actionable without re-running anything.
    """
    hits = []
    for path in files:
        rel = path.relative_to(REPO_ROOT)
        region_exempt = _region_exempt_linenos(
            str(rel), path.read_text(encoding="utf-8",
                                     errors="replace").splitlines())
        allowed_next = False
        in_allowed_block = False
        for lineno, line in _scan_units(path):
            if lineno in region_exempt:
                continue
            if in_allowed_block:
                # Runs to the closing fence. A quoted transcript is exempt as
                # a block because rewriting any line of it would make it a
                # transcript of something that never happened.
                if line.lstrip().startswith("```"):
                    in_allowed_block = False
                continue
            if ALLOW_MARKER_RE.search(line):
                # Covers the marker's own line and the one after it. Shell and
                # markdown often cannot carry a trailing comment on the line
                # that needs the exemption, so the marker sits above it.
                allowed_next = True
                continue
            if allowed_next:
                allowed_next = False
                if line.lstrip().startswith("```"):
                    in_allowed_block = True
                continue
            for term, patterns in BAN_PATTERNS.items():
                if str(rel).startswith(TERM_SURFACE_EXEMPT.get(term, ())):
                    continue
                for pattern in patterns:
                    if pattern.search(line):
                        hits.append(
                            f"{rel}:{lineno}: banned '{term}' "
                            f"(pattern {pattern.pattern!r}): {line.strip()[:80]}"
                        )
    return hits


def _enforced_hits(scan_cfg: dict) -> list[str]:
    """The hits that fail the build under a scan config.

    Surfaces in `pending_surfaces` are skipped - that is the ratchet's
    tolerance. Files under an `exempt` path are skipped wherever they
    appear - history stays honest.
    """
    exempt = tuple(scan_cfg.get("exempt", []))
    hits = []
    for surface in scan_cfg["surfaces"]:
        if surface in scan_cfg["pending_surfaces"]:
            continue
        files = [
            f for f in _surface_files(surface)
            if not str(f.relative_to(REPO_ROOT)).startswith(exempt)
        ]
        hits.extend(_scan_files(files))
    return hits


def _report(hits: list[str], rule: str) -> str:
    shown = "\n".join("  " + h for h in hits[:MAX_REPORTED])
    more = ""
    if len(hits) > MAX_REPORTED:
        more = f"\n  ... and {len(hits) - MAX_REPORTED} more"
    return f"{len(hits)} vocabulary violation(s).\n{rule}\n{shown}{more}"


# ---------------------------------------------------------------------------
# Well-formedness of the vocabulary file
# ---------------------------------------------------------------------------

def test_vocabulary_file_parses_with_three_sections():
    """governance/terminology.yml parses and carries terms, banned,
    and scan - the glossary, the bans, and what the scan covers (`TRC-A1`)."""
    cfg = _terminology()
    assert isinstance(cfg, dict), "terminology.yml must parse to a mapping"
    assert cfg.get("version"), "terminology.yml must declare a version"
    assert isinstance(cfg.get("terms"), dict) and cfg["terms"], (
        "terminology.yml needs a non-empty terms: mapping"
    )
    assert isinstance(cfg.get("banned"), list) and cfg["banned"], (
        "terminology.yml needs a non-empty banned: list"
    )
    assert isinstance(cfg.get("scan"), dict), (
        "terminology.yml needs a scan: mapping"
    )


ADR_041 = (REPO_ROOT / "architecture" / "decisions" /
           "ADR-041-the-configuration-vocabulary.md")


def _adr_041_terms() -> list[tuple[str, str]]:
    """`(term, definition)` for each bullet under "These terms join the
    vocabulary:" in the accepted decision record."""
    text = ADR_041.read_text(encoding="utf-8")
    block = text.split("**These terms join the vocabulary:**", 1)[1]
    block = block.split("\n\n", 2)[1] if block.startswith("\n\n") else block
    return re.findall(r"^- \*\*([^*]+)\*\*: (.+)$", block, re.M)


def test_vc7_every_term_the_accepted_decision_defines_is_in_the_glossary():
    """The accepted vocabulary decision says its terms join this file in the
    increment that builds the `vocabulary` catalogue, with the version bumped
    (ADR-012 rule 4) (`VC-7`)."""
    wanted = _adr_041_terms()
    assert len(wanted) >= 14, f"read only {len(wanted)} terms from the decision record"
    terms = _terminology()["terms"]
    glossary = (REPO_ROOT / "docs" / "glossary.md").read_text(encoding="utf-8")
    missing = [t for t, _ in wanted if t.replace(" ", "-") not in terms]
    assert not missing, f"terms the decision defines but terminology.yml lacks: {missing}"
    for term, _ in wanted:
        entry = terms[term.replace(" ", "-")]
        assert len(str(entry.get("means", "")).split()) >= 8, (
            f"{term}: the definition is too short to be one")
        assert term.replace(" ", "-") in glossary, f"{term}: not in docs/glossary.md"


def test_vc7_the_version_is_bumped_past_the_one_before_these_terms():
    m = re.fullmatch(r"2\.0\.0-pre(\d+)", str(_terminology()["version"]))
    assert m and int(m.group(1)) >= 16, (
        f"version {_terminology()['version']}: adding terms needs a bump past 2.0.0-pre15")


def test_every_term_states_its_meaning():
    """A term without a meaning is a name, not vocabulary (`TRC-A2`)."""
    missing = [
        name for name, entry in _terminology()["terms"].items()
        if not (isinstance(entry, dict) and str(entry.get("means", "")).strip())
    ]
    assert not missing, (
        f"terms without a means: field: {missing}. Every term carries its "
        "exact framework meaning; that is what makes the file a glossary."
    )


def test_every_ban_carries_replacement_and_context():
    """A ban without a replacement gives no way forward, and one
    without a context note bans the word rather than the usage (`TRC-A3`)."""
    broken = [
        entry.get("term", f"<entry {i}>")
        for i, entry in enumerate(_terminology()["banned"])
        if not (
            isinstance(entry, dict)
            and str(entry.get("term", "")).strip()
            and str(entry.get("replacement", "")).strip()
            and str(entry.get("context", "")).strip()
        )
    ]
    assert not broken, (
        f"banned entries missing term, replacement, or context: {broken}"
    )


def test_scan_config_declares_its_three_lists():
    """The scan section names what is checked (surfaces), what never
    is (exempt), and what is tolerated for now (pending_surfaces) (`TRC-A4`)."""
    scan = _terminology()["scan"]
    for key in ("surfaces", "exempt", "pending_surfaces"):
        value = scan.get(key)
        assert isinstance(value, list) and all(
            isinstance(item, str) and item for item in value
        ), f"scan.{key} must be a list of path strings"
    assert scan["surfaces"], "scan.surfaces must not be empty"


def test_every_related_term_is_defined():
    """A `related:` reference to a term the file never defines is a
    dangling pointer in the glossary - the reader clicks through to nothing.
    Every referenced term must have its own entry (`TRC-A1`,
    v2-terminology-dangling-refs)."""
    terms = _terminology()["terms"]
    dangling = sorted({
        ref
        for entry in terms.values() if isinstance(entry, dict)
        for ref in (entry.get("related") or [])
        if ref not in terms
    })
    assert not dangling, (
        f"related: lists reference terms with no entry: {dangling}. "
        "Define each one under terms: or drop the reference."
    )


def test_pending_entry_must_name_a_scanned_surface():
    """A pending entry outside the surface list would never burn
    down - nothing would ever scan it, so nothing would ever demand its
    removal (`TRC-F1`)."""
    scan = _terminology()["scan"]
    strays = set(scan["pending_surfaces"]) - set(scan["surfaces"])
    assert not strays, (
        f"pending_surfaces entries not in surfaces: {sorted(strays)}. "
        "Pending is a subset of scanned; anything else is dead config."
    )


# ---------------------------------------------------------------------------
# Scanner precision, proven by fixtures
# ---------------------------------------------------------------------------

def test_every_ban_is_bound_to_a_pattern():
    """The vocabulary file and the pattern table stay in
    one-to-one correspondence, so a ban cannot be added without a pattern
    and a pattern cannot outlive its ban (`TRC-B1`, binding)."""
    banned_terms = {entry["term"] for entry in _terminology()["banned"]}
    bound_terms = set(BAN_PATTERNS)
    assert banned_terms == bound_terms, (
        f"unbound bans (add patterns here): {sorted(banned_terms - bound_terms)}; "
        f"orphan patterns (ban was dropped): {sorted(bound_terms - banned_terms)}"
    )


def test_banned_usage_in_fixture_is_flagged():
    """Every ban catches its planted usage in the banned fixture,
    and every hit names file, line, term, and pattern (`TRC-B1`)."""
    hits = _scan_files([FIXTURE_BANNED])
    assert hits, "the banned-usage fixture produced no hits at all"
    flagged_terms = {
        term for term in BAN_PATTERNS
        if any(f"banned '{term}'" in hit for hit in hits)
    }
    unflagged = set(BAN_PATTERNS) - flagged_terms
    assert not unflagged, (
        f"bans with no hit in tests/fixtures/terminology/banned_usage.md: "
        f"{sorted(unflagged)}. Either the pattern is too narrow or the "
        "fixture lacks a planted usage - plant one and make it catch."
    )
    for hit in hits:
        assert re.match(r"^tests/fixtures/terminology/banned_usage\.md:\d+: ", hit), (
            f"hit does not lead with file:line: {hit}"
        )


def test_every_ban_pattern_catches_something_in_the_fixture():
    """Every individual pattern is exercised, not just every ban.

    The check above asks whether each BAN fires on the fixture. A ban with six
    patterns passes it when one of them fires, so the other five can be dead -
    a regex that has never matched anything and never will. Ten were, when
    this was written, including `during|at|before Triage`. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    It is case-sensitive against a fixture line that says "During Triage". <!-- vocabulary-scan: allow - names the banned term this pattern retires -->

    That is the "check that cannot fail" shape: it reads as coverage and
    checks nothing. `governance/strategies.md` S10 - a guard is accepted on <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    a demonstrated failure, not on a passing test - and a pattern that has
    never matched has never demonstrated one.
    """
    text = FIXTURE_BANNED.read_text(encoding="utf-8")
    dead = [(term, pattern.pattern)
            for term, patterns in BAN_PATTERNS.items()
            for pattern in patterns
            if not pattern.search(text)]
    assert not dead, (
        "these patterns match nothing in tests/fixtures/terminology/"
        "banned_usage.md, so nothing proves they can fire. Plant the usage "
        "each one is meant to catch, or delete the pattern:\n  "
        + "\n  ".join("%s: %s" % (t, p) for t, p in dead))


def test_innocent_usage_is_not_flagged():
    """Ordinary English reuse of the banned words stays legal - a
    hit in the innocent fixture means a pattern is too broad (`TRC-B2`)."""
    hits = _scan_files([FIXTURE_INNOCENT])
    assert not hits, _report(
        hits,
        "Rule: bans are pattern-plus-context, not bare words. These lines "
        "use the words innocently and must not match; narrow the pattern in "
        "BAN_PATTERNS.",
    )


# ---------------------------------------------------------------------------
# The ratchet
# ---------------------------------------------------------------------------

def test_pending_surface_may_still_carry_banned_terms():
    """A surface still in pending_surfaces is tolerated, so CI stays
    green while its rename slice is unshipped (`TRC-C1`)."""
    fixture_surface = "tests/fixtures/terminology/"
    hits = _enforced_hits({
        "surfaces": [fixture_surface],
        "exempt": [],
        "pending_surfaces": [fixture_surface],
    })
    assert not hits, (
        "a pending surface was scanned as if enforced; the ratchet's "
        "tolerance is broken"
    )


def test_surface_removed_from_pending_must_be_clean():
    """Once a surface leaves pending_surfaces its banned terms are
    build failures, named by file, line, and pattern (`TRC-C2`)."""
    fixture_surface = "tests/fixtures/terminology/"
    hits = _enforced_hits({
        "surfaces": [fixture_surface],
        "exempt": ["tests/fixtures/terminology/innocent_usage.md"],
        "pending_surfaces": [],
    })
    assert hits, (
        "an enforced surface full of banned terms produced no hits; the "
        "scan is not scanning"
    )
    for hit in hits:
        assert re.match(r"^\S+:\d+: banned '.+' \(pattern ", hit), (
            f"hit is not actionable (needs file:line, term, pattern): {hit}"
        )


def test_exempt_path_is_never_scanned():
    """Exempt paths stay unscanned even inside an enforced surface,
    so proposals, analysis, decision records, and this test's own fixtures
    remain honest history (`TRC-F2`)."""
    fixture_surface = "tests/fixtures/terminology/"
    hits = _enforced_hits({
        "surfaces": [fixture_surface],
        "exempt": [fixture_surface],
        "pending_surfaces": [],
    })
    assert not hits, _report(
        hits, "Rule: a file under an exempt path never produces a hit."
    )


def test_pending_list_only_ever_shrinks():
    """The live pending list is a subset of the committed baseline (`TRC-C3`).

    Removing a surface (with the baseline edit in the same diff) is a rename
    slice finishing its job. Adding one means un-renaming a surface, and
    that is a recorded vocabulary decision, not an edit - the freeze gives
    vocabulary changes the same process weight as a decision record.
    """
    pending = set(_terminology()["scan"]["pending_surfaces"])
    grown = pending - PENDING_BASELINE
    assert not grown, (
        f"pending_surfaces gained entries: {sorted(grown)}. The ratchet only "
        "tightens; growing it requires editing PENDING_BASELINE in this "
        "file, which is a deliberate, reviewed act."
    )


def test_repository_scan_is_green():
    """The enforced scan over the real configuration passes (`TRC-C4`). It is
    green because `PENDING_BASELINE` is empty: every surface has had its
    rename slice, and cleaned surfaces stay clean.
    """
    hits = _enforced_hits(_terminology()["scan"])
    assert not hits, _report(
        hits,
        "Rule: a surface not in pending_surfaces must contain no banned v1 "
        "vocabulary (governance/terminology.yml, banned:). Use each ban's "
        "replacement; the context note says which usages are in scope.",
    )


# =============================================================================
# The scan reads code positions, not only prose (ADR-015)
# =============================================================================
# Three of the six defects in the 3.0.0 cycle hid in a position this scan
# covered but did not read. `cli/compass_pkg/` was a scanned surface the whole
# time; the scan skipped string literals with no whitespace, on the reasoning
# that a single token is a machine identifier rather than prose. That is
# exactly the shape of `task.get('route')` and `os.path.join(dir, "plan.md")`. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
#
# The fix is two questions rather than one loosened answer:
#   * what does a surface TEACH   -> the ban patterns, now reaching markdown
#                                    code spans and fenced blocks too
#   * what does the code USE      -> an exact list of retired identifiers,
#                                    read from governance/terminology.yml
#
# Spec: docs/system-spec.md (group G).

RETIRED_NAMES = {
    e["name"]: e["replacement"]
    for e in (_terminology().get("retired_machine_names") or [])
}
RETIRED_EXEMPT = {
    e["path"] for e in (_terminology().get("retired_machine_name_exempt") or [])
}


def _python_literals(path: Path):
    """Every string literal in a Python file except docstrings.

    Deliberately NOT filtered by whitespace. That filter is right for the
    prose scan - a printed sentence has spaces in it - and is precisely the
    hole this check exists to close.
    """
    text = _read(path)
    if text is None:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                              ast.ClassDef))
                and body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            docstrings.add(id(body[0].value))
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def _retired_name_hits() -> list[str]:
    """Retired machine identifiers used as identifiers, across scanned Python."""
    scan_cfg = _terminology()["scan"]
    exempt = tuple(scan_cfg.get("exempt", []))
    hits = []
    for surface in scan_cfg["surfaces"]:
        for path in _surface_files(surface):
            rel = str(path.relative_to(REPO_ROOT))
            if rel.startswith(exempt) or rel in RETIRED_EXEMPT:
                continue
            if path.suffix != ".py" and path != REPO_ROOT / "cli" / "compass":
                continue
            for lineno, value in _python_literals(path):
                if value in RETIRED_NAMES:
                    hits.append(
                        f"{rel}:{lineno}: {value!r} is retired - use "
                        f"{RETIRED_NAMES[value]!r}")
    return hits


def test_rcd_g1_python_single_token_literal_caught():
    """A retired identifier used as a literal is reported."""
    hits = _retired_name_hits()
    assert not hits, _report(hits, "retired machine names in code")


def test_rcd_g1b_the_check_can_see_a_planted_name(tmp_path):
    """The check is wired to something.

    A pass proves nothing unless the same code reports a name that IS there -
    the exact failure this whole cycle is about. Plants each retired name in
    a literal and needs it to be seen.
    """
    for name, replacement in RETIRED_NAMES.items():
        src = tmp_path / "planted.py"
        src.write_text(f'x = {name!r}\n', encoding="utf-8")
        found = [v for _, v in _python_literals(src) if v in RETIRED_NAMES]
        assert found == [name], (
            f"a literal {name!r} was not seen by the literal reader, so the "
            f"check would pass on code using it instead of {replacement!r}"
        )


def test_rcd_g2_markdown_code_span_and_fence_caught():
    """Markdown contributes its code spans and fenced blocks to the scan.

    Both were skipped while the retired names were still live: a backticked
    `/compass:frame` named a command that really was still called that. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    ADR-014 removed those, so the exclusion has no remaining justification.
    """
    import tempfile

    def _units(markdown: str) -> str:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sample.md"
            p.write_text(markdown, encoding="utf-8")
            return " ".join(text for _, text in _scan_units(p))

    assert "route evaluate" in _units("Run `compass route evaluate` first.\n"), (
        "markdown code spans are still stripped before scanning, so a retired "
        "name inside backticks cannot be caught"
    )
    assert "route evaluate" in _units("```\ncompass route evaluate\n```\n"), (
        "fenced blocks are still skipped, so a retired name inside one cannot "
        "be caught"
    )


def test_rcd_g3_hooks_surface_is_scanned():
    """hooks/ is on the scanned list.

    It never was, which is how `hooks/pre-tool.sh` told users "Frame has not <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
    run" through the entire v2 rename - the enforcement path itself teaching
    the retired vocabulary, on every block.
    """
    surfaces = _terminology()["scan"]["surfaces"]
    assert any(s.rstrip("/") == "hooks" for s in surfaces), (
        f"hooks/ is not a scanned surface, so the enforcement path's own "
        f"messages are unchecked. Surfaces: {surfaces}"
    )


def test_rcd_g4_archive_exempt_and_unedited():
    """The archive is exempt, and exempt is the only thing it ever is.

    Historical records are allowed to say what they said. A project whose
    selling point is an audit trail cannot rewrite its own audit trail to
    make a check pass.
    """
    # Asserted as "not scanned" rather than "exempt". The exemption excluded
    # nothing: `scan.exempt` is applied only to files gathered from
    # `scan.surfaces`, and the archive is under none of them - so the entry
    # read as protection that had been granted while granting none. What the
    # archive actually needs is to stay outside every scanned surface, and
    # that is what is checked.
    surfaces = _terminology()["scan"]["surfaces"]
    reachable = [s for s in surfaces
                 if ".compass/work/".startswith(s.rstrip("/") + "/")
                 or s.rstrip("/") == ".compass/work"]
    assert not reachable, (
        f"the issue archive is reachable from scanned surface(s) {reachable}, "
        f"so the scan would read it. Historical records are allowed to say "
        f"what they said - a project whose selling point is an audit trail "
        f"cannot rewrite its own audit trail to make a check pass"
    )


# ---------------------------------------------------------------------------
# The everyday-words list, as a thing a project author reads and configures.
# Issue plain-language-3-2-0, group B.
# ---------------------------------------------------------------------------

def _banned_entry(term_fragment: str) -> dict:
    for e in _terminology().get("banned") or []:
        if term_fragment in str(e.get("term", "")):
            return e
    raise AssertionError(f"no banned entry mentioning {term_fragment!r}")


def test_pl_b3_seam_ban_names_its_replacements():
    """A ban that does not say what to write instead is a scold (`TRC-B3`).

    The global rules already name the replacements; the entry has to carry them
    or a contributor who hits the ban has to go and find them.
    """
    entry = _banned_entry("seam")
    replacement = str(entry.get("replacement", "")).lower()
    for word in ("interface", "contract", "dependency injection", "boundary",
                 "extension point", "abstraction layer"):
        assert word in replacement, (
            f"the 'seam' ban does not offer {word!r} as a replacement. Its "
            f"replacement field reads: {entry.get('replacement')!r}"
        )
    context = str(entry.get("context", "")).lower()
    assert "structure" in context or "structural" in context, (
        "the ban must say it applies to code structure - the ordinary word is "
        "fine, and a ban that does not scope itself will be read as banning both"
    )


def test_pl_b4_quoted_term_exception_is_written_down():
    """The exception is a rule, not folklore in three context strings (`TRC-B4`).

    Without it written once, in the place a contributor configuring the list
    reads, someone paraphrases a string the reader needed to search.
    """
    doc = TERMINOLOGY_PATH.read_text(encoding="utf-8")
    low = doc.lower()
    # A cross-reference is not a statement. The first draft of this test passed
    # on the phrase appearing inside another ban's context, pointing at a rule
    # that did not exist - a presence check satisfied by a dangling reference.
    assert "quoted_term_exception" in _terminology(), (
        "terminology.yml has no `quoted_term_exception:` section of its own. A "
        "ban saying 'per the quoted-term exception below' is a dangling "
        "reference if there is nothing below. (Checked as a parsed key, not a "
        "substring: `quoted_term_exception_RENAMED` contains the substring and "
        "would have satisfied the first version of this assertion.)"
    )
    for phrase in ("quotation mark", "code span", "search"):
        assert phrase in doc, (
            f"the quoted-term exception does not mention {phrase!r} - it needs "
            f"to say how a quotation is recognised and why the word is kept"
        )


def _project_additions_text() -> str:
    """The comment block and the mapping that make up `project_additions`,
    from the heading rule to the mapping's last line. Comments carry most of
    the wording, so the parsed mapping alone would miss it."""
    lines = TERMINOLOGY_PATH.read_text(encoding="utf-8").splitlines()
    heading = next(i for i, line in enumerate(lines)
                   if line.startswith("# Project-specific additions"))
    end = next(i for i, line in enumerate(lines)
               if line.startswith("project_additions:"))
    while end + 1 < len(lines) and lines[end + 1].startswith("  "):
        end += 1
    return "\n".join(lines[heading - 1:end + 1])


def test_pl_b7_the_list_states_todays_behaviour_not_the_intended_one():
    """What ships says what is true now, not what is planned (`TRC-B7`, `VC-6`).

    The ruling is that the list ships as a default, extends per project and is
    never replaceable. A project adds display names through its `vocabulary`
    catalogue. Extending the banned list itself is still not supported: a
    project-local governance/ replaces the shipped defaults wholesale. Stating
    the end state in the present tense would be this issue committing the
    defect it exists to fix.
    """
    block = _project_additions_text()
    low = block.lower()
    assert "`vocabulary` catalogue" in low and "display name" in low, (
        "project_additions does not say a project adds display names through "
        "its `vocabulary` catalogue, so a project author will not know where "
        "their own words go"
    )
    assert "not supported yet" in low or "not yet supported" in low, (
        "project_additions does not say that extending the banned list is not "
        "supported yet, so a project author will assume it is"
    )
    assert "governance-merge-not-replace" in block, (
        "project_additions does not name the issue tracking ban-list "
        "extension, so a reader who wants it has nowhere to go"
    )
    assert "supported: false" not in block, (
        "project_additions still says project additions are unsupported as a "
        "whole, which is no longer true of display names"
    )
    # Only current behaviour: the format, the lookup and the collision check
    # exist, but nothing reads a project's compass.yml vocabulary yet.
    assert "no command reads" in low and "yet" in low, (
        "project_additions does not say that no command reads a project's "
        "names yet, so it claims more than this branch does"
    )
    value = yaml.safe_load(
        TERMINOLOGY_PATH.read_text(encoding="utf-8"))["project_additions"]["display_names"]
    assert "yet" in str(value) and "through_vocabulary_catalogue" != value, (
        f"display_names is {value!r}, which does not say the names are not read yet"
    )
    assert "block below" not in low, (
        "project_additions points at a scan block below it; `scan:` is above"
    )
    assert "collision" in low, (
        "project_additions does not say the collision check exists"
    )


# ---------------------------------------------------------------------------
# Display names in `vocabulary` catalogues (`VC-5`)
#
# A project's own words go in the `vocabulary` catalogue as display names and
# aliases. The line scan above gets only the markdown files of `governance/`
# (its YAML files are scanned by name, never wholesale), so a banned word in a
# display name or alias would pass it. These checks run the same ban patterns
# over the names themselves.
# ---------------------------------------------------------------------------

def _field_names(fields: yaml.MappingNode) -> list[yaml.ScalarNode]:
    """The string nodes of a `name` and an `aliases` in one mapping. A
    layer writes aliases as a list, or as `{add: [...]}` under `set:`."""
    found = []
    for key, value in fields.value:
        if key.value == "name" and isinstance(value, yaml.ScalarNode):
            found.append(value)
        elif key.value == "aliases" and isinstance(value, yaml.SequenceNode):
            found += value.value
        elif key.value == "aliases" and isinstance(value, yaml.MappingNode):
            found += [item for op, seq in value.value
                      if op.value == "add" and isinstance(seq, yaml.SequenceNode)
                      for item in seq.value]
    return [n for n in found
            if isinstance(n, yaml.ScalarNode) and n.tag == "tag:yaml.org,2002:str"]


def _vocabulary_names(text: str) -> list[tuple[str, yaml.ScalarNode]]:
    """`(key, node)` for every display name and alias a layer holds: on the
    entry itself (a new entry, or `replace: true`) and under its `set:`.
    A node carries its own line, which is where a marker must sit; a YAML
    alias to a name is the anchored node, so a marker at the alias does not
    reach it."""
    root = yaml.compose(text)
    if not isinstance(root, yaml.MappingNode):
        return []
    names = []
    for key, section in root.value:
        if key.value != "vocabulary" or not isinstance(section, yaml.MappingNode):
            continue
        for entry_key, entry in section.value:
            if not isinstance(entry, yaml.MappingNode):
                continue
            groups = [entry] + [value for k, value in entry.value
                                if k.value == "set" and isinstance(value, yaml.MappingNode)]
            for group in groups:
                names += [(str(entry_key.value), node) for node in _field_names(group)]
    seen = set()
    return [(k, n) for k, n in names if not (id(n) in seen or seen.add(id(n)))]


def _vocabulary_name_hits(path: Path, root: Path) -> list[str]:
    """Banned-term hits in one file's display names and aliases.

    A name is exempt when a reasoned allow marker sits on the line where its
    YAML node starts or on the line before: the same per-line rule as prose,
    so `grep -rn "vocabulary-scan: allow"` still lists every exemption.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    hits = []
    for key, node in _vocabulary_names(text):
        line = node.start_mark.line
        if ALLOW_MARKER_RE.search(lines[line]) or (
                line > 0 and ALLOW_MARKER_RE.search(lines[line - 1])):
            continue
        for term, patterns in BAN_PATTERNS.items():
            if any(p.search(node.value) for p in patterns):
                hits.append(f"{path.relative_to(root)}:{line + 1}: {key}: banned "
                            f"'{term}' in the display name {node.value!r}")
    return hits


def _vocabulary_files(root: Path, surfaces: list[str]) -> list[Path]:
    """Tracked YAML files under `surfaces` that hold a top-level `vocabulary:`
    key. Discovery reads `git ls-files`, as the style tests do, so a file left
    untracked locally does not change the answer CI gets. A file that holds the
    key but does not parse fails here, naming the file."""
    import subprocess
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", *surfaces], cwd=root, check=True,
        capture_output=True, text=True).stdout.split("\0")
    files = []
    for rel in sorted(r for r in listed if r.endswith((".yml", ".yaml"))):
        path = root / rel
        text = path.read_text(encoding="utf-8")
        if not re.search(r"^vocabulary:", text, re.M):
            continue
        try:
            doc = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            pytest.fail(f"{rel}: holds a vocabulary key but is not valid YAML: {exc}")
        if isinstance(doc, dict) and isinstance(doc.get("vocabulary"), dict):
            files.append(path)
    return files


def _vocabulary_catalogue_hits(root: Path, surfaces: list[str]) -> list[str]:
    """Banned-term hits across every vocabulary catalogue under `surfaces`."""
    hits = []
    for path in _vocabulary_files(root, surfaces):
        hits += _vocabulary_name_hits(path, root)
    return hits


def _project_file(tmp_path: Path, vocabulary_text: str) -> Path:
    path = tmp_path / "compass.yml"
    path.write_text(vocabulary_text, encoding="utf-8")
    return path


def test_vc5_the_scan_config_names_where_vocabulary_catalogues_live():
    surfaces = _terminology()["scan"].get("vocabulary_surfaces")
    assert isinstance(surfaces, list) and surfaces and all(
        isinstance(s, str) and s for s in surfaces
    ), "scan.vocabulary_surfaces must list the paths whose vocabulary catalogues are scanned"


def test_vc5_a_banned_display_name_is_reported(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    name: Triage queue\n"
        "    aliases: [tests green]\n"
    ))
    hits = _vocabulary_name_hits(path, tmp_path)
    assert len(hits) == 1
    assert "Triage" in hits[0] and "checks.suite-passed" in hits[0]


def test_vc5_a_banned_alias_is_reported(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    name: Suite passed\n"
        "    aliases: [tests green, Triage]\n"
    ))
    assert len(_vocabulary_name_hits(path, tmp_path)) == 1


def test_vc5_clean_names_pass(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    name: Suite passed\n"
        "    aliases: [tests green, ci]\n"
    ))
    assert _vocabulary_name_hits(path, tmp_path) == []


def test_vc5_a_reasoned_marker_exempts_the_name_and_a_bare_one_does_not(tmp_path):
    reasoned = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    name: Suite passed\n"
        "    aliases: [Triage]  # vocabulary-scan: allow - the retired name an old script still passes\n"
    ))
    assert _vocabulary_name_hits(reasoned, tmp_path) == []
    above = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    name: Suite passed\n"
        "    # vocabulary-scan: allow - the retired name an old script still passes\n"
        "    aliases: [Triage]\n"
    ))
    assert _vocabulary_name_hits(above, tmp_path) == []
    bare = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    name: Suite passed\n"
        "    aliases: [Triage]  # vocabulary-scan: allow\n"
    ))
    assert len(_vocabulary_name_hits(bare, tmp_path)) == 1


def _git_repo(tmp_path: Path, tracked: dict, untracked: dict | None = None) -> Path:
    """A throwaway repository holding `tracked` files (path to text), with
    `untracked` ones beside them. Discovery reads `git ls-files`, so a file
    that is not tracked is not a vocabulary file as CI sees it."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    for files in (tracked, untracked or {}):
        for rel, text in files.items():
            target = tmp_path / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "--", *tracked], cwd=tmp_path, check=True)
    return tmp_path


def test_vc5_discovery_finds_a_tracked_vocabulary_catalogue_under_a_surface(tmp_path):
    repo = _git_repo(tmp_path, {
        "preset/vocabulary.yml": "vocabulary:\n  checks.x:\n    name: Triage queue\n",
        "preset/checks.yml": "checks:\n  x: {statement: Triage queue}\n",
    })
    hits = _vocabulary_catalogue_hits(repo, ["preset/", "absent/"])
    assert len(hits) == 1 and "vocabulary.yml" in hits[0]


def test_vc5_discovery_ignores_a_file_git_does_not_track(tmp_path):
    # rglob would find the untracked file locally and CI would not.
    repo = _git_repo(
        tmp_path,
        {"preset/vocabulary.yml": "vocabulary:\n  checks.x:\n    name: Fine\n"},
        {"preset/local.yml": "vocabulary:\n  checks.x:\n    name: Triage queue\n"})
    assert _vocabulary_catalogue_hits(repo, ["preset/"]) == []


def test_vc5_a_vocabulary_file_that_does_not_parse_fails_naming_the_file(tmp_path):
    repo = _git_repo(tmp_path, {
        "preset/vocabulary.yml": "vocabulary:\n  checks.x: [unclosed\n"})
    with pytest.raises(pytest.fail.Exception) as raised:
        _vocabulary_catalogue_hits(repo, ["preset/"])
    assert "preset/vocabulary.yml" in str(raised.value)


def test_vc5_a_banned_name_under_set_is_reported(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    set:\n"
        "      name: Triage queue\n"
    ))
    hits = _vocabulary_name_hits(path, tmp_path)
    assert len(hits) == 1 and "Triage" in hits[0]


def test_vc5_a_banned_alias_added_under_set_is_reported(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    set:\n"
        "      aliases:\n"
        "        add: [tests green, Triage]\n"
    ))
    assert len(_vocabulary_name_hits(path, tmp_path)) == 1


def test_vc5_a_banned_name_in_a_replacing_entry_is_reported(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    replace: true\n"
        "    name: Triage queue\n"
        "    aliases: [Triage]\n"
    ))
    assert len(_vocabulary_name_hits(path, tmp_path)) == 2


def test_vc5_a_marker_on_a_folded_names_first_line_exempts_it(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    # vocabulary-scan: allow - the retired name an old script still passes\n"
        "    name: >-\n"
        "      Triage\n"
        "      queue\n"
    ))
    assert _vocabulary_name_hits(path, tmp_path) == []


def test_vc5_a_marker_elsewhere_does_not_exempt_a_folded_name(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    name: >-\n"
        "      Triage\n"
        "      queue\n"
        "    # vocabulary-scan: allow - the retired name an old script still passes\n"
        "  checks.reviewed:\n"
        "    name: Reviewed\n"
    ))
    assert len(_vocabulary_name_hits(path, tmp_path)) == 1


def test_vc5_a_marker_at_a_yaml_alias_does_not_exempt_the_anchored_name(tmp_path):
    path = _project_file(tmp_path, (
        "vocabulary:\n"
        "  checks.suite-passed:\n"
        "    name: &retired Triage queue\n"
        "  checks.reviewed:\n"
        "    name: Reviewed\n"
        "    aliases: [*retired]  # vocabulary-scan: allow - the retired name an old script passes\n"
    ))
    hits = _vocabulary_name_hits(path, tmp_path)
    assert len(hits) == 1 and "checks.suite-passed" in hits[0]


def test_vc5_every_vocabulary_catalogue_in_the_repository_is_clean():
    surfaces = _terminology()["scan"]["vocabulary_surfaces"]
    hits = _vocabulary_catalogue_hits(REPO_ROOT, surfaces)
    assert not hits, _report(hits, "A display name or alias holds a banned term.")
    if (REPO_ROOT / "governance" / "presets").exists():
        # Once the shipped preset lands it holds a vocabulary file. If the
        # scan finds none, discovery is broken and this test would pass empty.
        assert _vocabulary_files(REPO_ROOT, surfaces), (
            "governance/presets/ exists but no vocabulary catalogue was found "
            "under the scan's vocabulary surfaces"
        )


def test_pl_c11_strategies_prose_is_not_path_exempt():
    """The bare-codes exemption covers definitions, not prose (`TRC-C11`).

    `governance/` is exempt because it DEFINES `G1`-`G5` and `S1`-`S14`, and a
    definition has to name what it defines. That holds for the machine-readable
    files. `strategies.md` is prose a contributor reads, and it is where this
    project writes the rule about bare codes - so a path exemption made the one
    file the rule could not reach the one file stating the rule.

    A deliberate illustration of the wrong form is handled per line, with the
    `vocabulary-scan: allow` marker and a written reason, which is greppable.
    A path prefix is not.
    """
    exempt = TERM_SURFACE_EXEMPT.get("G1..G5 / S1..S14 codes, bare", ())
    assert not any(e == "governance/" for e in exempt), (
        "the bare-codes ban still exempts all of governance/ by prefix, so "
        "governance/strategies.md is unscanned"
    )
    assert any("guardrails.yml" in e for e in exempt), (
        "the machine-readable governance files must stay exempt - a policy "
        "file's `when: {risk: critical}` clause cannot gloss its own ids"
    )
    from pathlib import Path as _P
    covered = [e for e in exempt if str(_P("governance/strategies.md")).startswith(e)]
    assert not covered, (
        f"governance/strategies.md is still covered by exemption(s) {covered}"
    )


# ---------------------------------------------------------------------------
# Issue public-docs-tell-the-truth - the retired stage names are banned
# outright, and the ban is only as good as what it can be shown to catch.
#
# Three designs were measured before this one. Enumerating shapes caught 85 of
# 149 live occurrences. Capitalisation caught 297 and left 102. Both reported
# clean over surfaces that were not clean, which is the failure the issue
# exists to repair. See the comment on the Frame patterns above. <!-- vocabulary-scan: allow - names the banned term this pattern retires -->
# ---------------------------------------------------------------------------

RETIRED_STAGES = ("Frame", "Specify", "Clarify", "Distribute", "Land")


def _sample_holder() -> Path:
    """This process's own folder for scan samples. One shared folder failed
    under parallel workers: each removes its folder when done, which removed
    it from under another worker still writing there (#371)."""
    return REPO_ROOT / f".pytest-vocab-tmp-{os.getpid()}"


def _scan_text(text: str, name: str = "sample.md") -> list[str]:
    """Run the scanner over a string by writing it to a temp markdown file."""
    # Inside the repository: _scan_files reports paths relative to REPO_ROOT
    # and raises on anything outside it. Under a dot-directory so no surface
    # glob picks the sample up while it exists.
    import tempfile
    holder = _sample_holder()
    holder.mkdir(exist_ok=True)
    d = tempfile.mkdtemp(dir=holder)
    try:
        p = Path(d) / name
        p.write_text(text, encoding="utf-8")
        return _scan_files([p])
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)
        try:
            holder.rmdir()
        except OSError:
            pass


def test_b1_label_shape_in_a_table_cell_is_caught():
    """The shape every approach document uses for its stage table (`TRC-B1`)."""
    for stage in RETIRED_STAGES:
        hits = _scan_text(f"| {stage} | Light but real. |\n")
        assert hits, f"a table cell holding only '{stage}' was not reported"


def test_b2_label_shape_in_a_bold_run_is_caught():
    """The other label form: `- **Specify** - how many scenarios` (`TRC-B2`). <!-- vocabulary-scan: allow - quotes the retired label form this test plants and checks the ban catches -->"""
    for stage in RETIRED_STAGES:
        hits = _scan_text(f"- **{stage}** - how many scenarios and how deep.\n")
        assert hits, f"a bold run holding only '{stage}' was not reported"


def test_b3_every_retired_stage_name_has_a_label_pattern():
    """Five names were retired together and are written alike (`TRC-B3`).

    Teaching the shape to one and not the rest is how the next four survive,
    so this asserts the ban covers all five rather than trusting that it does.
    """
    for stage in RETIRED_STAGES:
        assert _scan_text(f"| {stage} |\n"), (
            f"'{stage}' has no pattern for the label shape - it was retired "
            f"alongside the others and is written the same way")


def test_b5_sentence_shape_is_caught():
    """The shape found in the CLI's printed strings (`TRC-B5`).

    "has Frame run?", "a fresh Frame", "the next Land". These sit mid-sentence <!-- vocabulary-scan: allow - quotes the retired CLI strings this test plants and checks the ban catches -->
    and are the shape most likely to collide with ordinary English, which is
    why the tolerance test below matters as much as this one.
    """
    for text in ("The message asks: has Frame run?\n",
                 "Edits are overwritten on the next Land.\n",
                 "It becomes a fresh Frame, not a merge.\n"):
        assert _scan_text(text), f"mid-sentence stage name not reported: {text!r}"


def test_b4_scan_report_states_the_count():
    """A failure without a number cannot tell a real hit from a
    pattern that has started matching everything (`TRC-B4`)."""
    hits = _scan_text("| Frame |\n| Land |\n")
    report = _report(hits, "rule")
    assert str(len(hits)) in report.split("\n")[0], (
        f"the report's first line does not state how many were found: "
        f"{report.splitlines()[0]!r}")
    for h in hits:
        assert ":" in h and "banned" in h, (
            "a hit does not name file, line and term, so a failure is not "
            "actionable without re-running anything")


def test_c1_ordinary_verb_use_is_tolerated():
    """The ban is case-sensitive, and that is what keeps it usable (`TRC-C1`).

    You frame a problem, you specify behaviour, a spike does not land
    production code. Every one of those is correct English and stays legal
    without a marker.
    """
    for text in ("You do not understand the problem well enough to frame it yet.\n",
                 "A spike does not land production code.\n",
                 "You specify the format and then you clarify the edges.\n",
                 "The orchestrator will distribute the work.\n"):
        hits = _scan_text(text)
        stage_hits = [h for h in hits if any(s in h for s in RETIRED_STAGES)]
        assert not stage_hits, (
            f"ordinary lowercase English was reported as a retired stage "
            f"name:\n  {text!r}\n  {stage_hits}")


def test_c2_bold_sentence_opening_is_tolerated():
    """The one legitimate capitalised use, and how it is allowed (`TRC-C2`).

    `- **Land production code.**` is a sentence whose first word is capitalised <!-- vocabulary-scan: allow - quotes the one legitimate capitalised use this test plants and checks the marker permits -->
    by position. Under a total ban it IS reported, and the inline marker is how
    it is permitted - with a reason, in the file, where a reader meets it.
    """
    plain = _scan_text("- **Land production code.** The only exit is graduation.\n")
    assert plain, (
        "the total ban did not report a capitalised stage name. If this stops "
        "firing, the marker below is permitting something nothing objected to")

    marked = _scan_text(
        "- **Land production code.** <!-- vocabulary-scan: allow - ordinary "
        "verb opening a sentence -->\n")
    assert not marked, (
        "an inline allow marker with a reason did not permit the line - the "
        "allowlist is the only way a legitimate capitalised use can stay")


def test_c3_innocent_fixture_covers_every_retired_stage_name():
    """The tolerance fixture must grow with the patterns (`TRC-C3`).

    The project keeps a pair: one planting every banned usage, one reusing
    every word innocently. If the innocent one does not exercise a word, it
    certifies nothing about that word's pattern.
    """
    body = FIXTURE_INNOCENT.read_text(encoding="utf-8").lower()
    missing = [s for s in RETIRED_STAGES if s.lower() not in body]
    assert not missing, (
        f"the innocent-usage fixture never uses {missing} in an ordinary "
        f"sense, so nothing proves the ban tolerates them")
    assert not _scan_files([FIXTURE_INNOCENT]), (
        "the innocent-usage fixture reports violations - the patterns have "
        "become wide enough to fail the build on correct English")


def test_c4_clean_surfaces_stay_clean():
    """The residual-finding count, pinned to zero rather than to a count (`TRC-C4`).

    The requirements review pinned this to 35 files and the design corrected it
    to 36; both numbers described work in progress. Now that the sweep is done
    the honest pin is zero, and it is the number that stays true.
    """
    hits = _enforced_hits(_terminology()["scan"])
    assert not hits, _report(hits, "every live surface must be clean")


def test_d1_no_live_surface_carries_a_retired_stage_name():
    """297 occurrences repaired across 66 files (`TRC-D1`)."""
    for stage in RETIRED_STAGES:
        planted = _scan_text(f"The issue moves to {stage} next.\n")
        assert planted, (
            f"'{stage}' is no longer caught anywhere - the ban has been "
            f"weakened and the 297 repairs are unguarded")
    assert not _enforced_hits(_terminology()["scan"])


def test_d3_exempt_list_still_covers_history_and_no_live_surface():
    """History stays exempt, and the exemption stays narrow (`TRC-D3`).

    213 raw hits became 0 enforced mostly because decision records are exempt.
    That is correct - rewriting one would falsify an account of what was
    decided at the time - and it must not creep into covering a live surface.
    """
    exempt = _terminology()["scan"].get("exempt", [])
    assert "architecture/decisions/" in exempt, (
        "decision records are no longer exempt; a sweep would falsify them")

    live = ("approaches/", "skills/", "agents/", "commands/", "templates/",
            "docs/methodology.md", "docs/quickstart.md", "README.md")
    crept = [e for e in exempt if e in live]
    assert not crept, (
        f"the exempt list has grown to cover live surfaces: {crept}. That is "
        f"how a scan reports zero while the drift it exists to catch survives")


def test_glossary_prints_no_scanner_marker_and_gates_follow_the_approach():
    """The glossary reads as plain sentences, and two entries agree.

    A scan allowance sat inside three definitions, so the glossary printed
    the marker text. `quality-gate` also said the issue type decides which
    gates apply, which `issue-type` and the code contradict: the delivery
    approach and the label rules decide. `full` names the heaviest approach,
    not a stage mode.
    """
    glossary = (REPO_ROOT / "docs" / "glossary.md").read_text(encoding="utf-8")
    assert "vocabulary-scan" not in glossary, (
        "docs/glossary.md prints scanner marker text; keep the marker in a "
        "YAML comment above the line it exempts")
    terms = _terminology()["terms"]
    gate = " ".join(str(terms["quality-gate"]["means"]).split())
    assert "depends on the issue type" not in gate
    assert "delivery approach" in gate and "label" in gate
    approach = " ".join(str(terms["delivery-approach"]["means"]).split())
    assert "`full`" in approach and "thorough" in approach and "7.0.0" in approach
