"""The word list and the scans of the US English guard.

`US_FORMS` is the one table of British words and their US forms. `WORDS` is
its keys. The guard test, the CLI message pass and the 7.1.0 conversion
script all read this table, so a word is added in one place.

The list holds specific words, not a pattern, so a code identifier or a word
that GitHub spells itself (`cancelled`, `towards`) cannot be a hit. A word
matches whole and in any case: `behavioural` is a hit and `behaviourism` is
not.

An exemption is a marker on the line it covers, with a reason. The marker
covers its own line only, never a file.
"""
from __future__ import annotations

import ast
import io
import os
import re
import tokenize
from pathlib import Path

# British form -> US form. Keep one word to a line.
US_FORMS = {
    "behaviour": "behavior",
    "behaviours": "behaviors",
    "behavioural": "behavioral",
    "judgement": "judgment",
    "judgements": "judgments",
    "catalogue": "catalog",
    "catalogues": "catalogs",
    "initialise": "initialize",
    "initialised": "initialized",
    "initialising": "initializing",
    "initialisation": "initialization",
    "colour": "color",
    "colours": "colors",
    "labelled": "labeled",
    "labelling": "labeling",
    "normalise": "normalize",
    "normalised": "normalized",
    "recognise": "recognize",
    "recognised": "recognized",
    "honour": "honor",
    "honoured": "honored",
    "licence": "license",
    "spelt": "spelled",
    "organise": "organize",
    "organisation": "organization",
    "analyse": "analyze",
    "analysed": "analyzed",
    "centre": "center",
    "favour": "favor",
    "artefact": "artifact",
    "whilst": "while",
    "centrepiece": "centerpiece",
    "ageing": "aging",
    "authorise": "authorize",
    "authorises": "authorizes",
    "authorised": "authorized",
    "capitalisation": "capitalization",
    "capitalised": "capitalized",
    "characterisation": "characterization",
    "characterise": "characterize",
    "defence": "defense",
    "finalise": "finalize",
    "finalised": "finalized",
    "finalising": "finalizing",
    "honourable": "honorable",
    "honouring": "honoring",
    "honours": "honors",
    "initialises": "initializes",
    "modelling": "modeling",
    "neighbour": "neighbor",
    "normalisation": "normalization",
    "normaliser": "normalizer",
    "normalises": "normalizes",
    "normalising": "normalizing",
    "parameterised": "parameterized",
    "recognisable": "recognizable",
    "recognises": "recognizes",
    "rigour": "rigor",
    "sceptic": "skeptic",
    "serialisation": "serialization",
    "specialised": "specialized",
    "summarise": "summarize",
    "summarising": "summarizing",
    "utilise": "utilize",
    "utilises": "utilizes",
    "demoralising": "demoralizing",
    "destabilise": "destabilize",
    "destabilising": "destabilizing",
    "hypothesising": "hypothesizing",
    "parallelised": "parallelized",
    "parallelises": "parallelizes",
    "parametrisation": "parametrization",
    "reorganised": "reorganized",
    "reorganising": "reorganizing",
    "reprioritise": "reprioritize",
    "synthesise": "synthesize",
    "unlabelled": "unlabeled",
    "unrecognised": "unrecognized",
}
WORDS = tuple(US_FORMS)

# The marker covers its own line and needs a reason of at least one word.
MARKER = "us-english-scan: allow - "
NOT_NEEDED = "<exemption not needed>"

# Path prefixes the guard never reads: the frozen file classes. The
# file test_frozen_files_unchanged.py proves each class is unchanged.
EXCLUDED = (
    "governance/decisions/",
    "architecture/decisions/",
    "governance/presets/default@6",
    "governance/shipped-releases.tar.xz",
    "tests/fixtures/compat/",
    "cli/vendor",
)

# Lines that keep a British word on purpose in a file that cannot hold a
# marker, because JSON has no comment. Each entry is (file, a fragment of
# the line, the reason). It covers the lines that hold the fragment, in that
# file only; a test fails when an entry matches no line.
KEPT_LINES = (
    ("schemas/manifest.schema.json", '"judgement",',
     "the stored value of a re-assessment kind, which the CLI still reads until 8.0.0"),
    ("schemas/manifest.schema.json", "'judgement' is the old spelling",
     "names the stored value above, which keeps the old spelling until 8.0.0"),
)

# One row for each file group. Each `live` field is on a line of its own, at
# least three lines from the next, so three units can switch three rows on
# without a merge conflict. A row that is not live is not scanned yet,
# because its files are not converted.
GROUPS = [
    {
        "name": "README",
        "paths": ["README.md"],
        "kind": "text",
        "live": True,
    },
    {
        "name": "adopter docs",
        "paths": [
            "docs/quickstart.md", "docs/five-minutes.md",
            "docs/install-smoke-test.md", "docs/releasing.md",
            "docs/release-notes.md", "docs/upgrade-6-0-0.md",
            "docs/upgrade-7-0-0.md", "docs/configuration.md",
            "docs/safety-contract.md", "docs/policy-lint.md",
            "docs/readiness.md", "docs/refusal-codes.md", "docs/glossary.md",
            "docs/policy-migrate.md", "docs/routing-deep-dive.md",
            "docs/roles-guide.md",
        ],
        "kind": "text",
        "live": True,
    },
    {
        "name": "house files",
        "paths": ["CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md"],
        "kind": "text",
        "live": True,
    },
    {
        "name": "review workflow",
        "paths": [".github/workflows/claude-review.yml"],
        "kind": "text",
        "live": True,
    },
    {
        "name": "skills",
        "paths": ["skills"],
        "kind": "text",
        "live": True,
    },
    {
        "name": "commands and agents",
        "paths": ["commands", "agents"],
        "kind": "text",
        "live": True,
    },
    {
        "name": "approaches and templates",
        "paths": ["approaches", "templates"],
        "kind": "text",
        "live": True,
    },
    {
        "name": "contract",
        "paths": ["compass-contract.md"],
        "kind": "text",
        "live": True,
    },
    {
        "name": "hooks, schemas and adapters",
        "paths": ["hooks", "schemas", "adapters"],
        "kind": "text",
        "live": True,
    },
    {
        "name": "cli string literals",
        "paths": ["cli/compass_pkg", "cli/compass"],
        "kind": "python",
        "live": True,
    },
    {
        "name": "cli help strings",
        "paths": ["cli/compass_pkg", "cli/compass"],
        "kind": "help",
        "live": True,
    },
]

_WORD = re.compile(r"\b(" + "|".join(sorted(WORDS, key=len, reverse=True)) + r")\b",
                   re.IGNORECASE)
_MARKER_START = re.compile(r"us-english-scan: allow")
_MARKER_FULL = re.compile(r"us-english-scan: allow - (?P<reason>.*)")
_REASON_WORD = re.compile(r"[A-Za-z0-9]")
_CLOSER = re.compile(r"(--!?>|\*/)\s*$")
_HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1")
_HELP_KEYWORDS = ("help", "description", "epilog", "usage")
_TEXT_SUFFIXES = (".md", ".yml", ".yaml", ".json", ".txt", ".sh", ".py", ".toml", ".html")


def _words_in(text):
    return [m.group(1).lower() for m in _WORD.finditer(text)]


def _valid_marker(text):
    """True when `text`, which starts at the marker, gives a reason."""
    found = _MARKER_FULL.match(text)
    if not found:
        return False
    return bool(_REASON_WORD.search(_CLOSER.sub("", found.group("reason"))))


def _resolve(lines, hits, markers, check_unused=True):
    """Apply the markers. `hits` is a list of (line, word); `markers` maps a
    line number to whether its marker gives a reason. A marker with a reason
    covers a hit on its own line. A marker on a line with no hit is itself a
    finding, unless `check_unused` is off because the scan reads only part of
    the file, so a marker may cover a string that scan does not read."""
    found = []
    hit_lines = {number for number, _ in hits}
    for number, word in hits:
        if markers.get(number):
            continue
        found.append((number, word, lines[number - 1]))
    for number in sorted(markers):
        if check_unused and number not in hit_lines:
            found.append((number, NOT_NEEDED, lines[number - 1]))
    return sorted(found, key=lambda hit: hit[0])


def scan_text(text, path=""):
    """Prose, YAML scalars and any other text: every line, read whole. The
    marker and its reason are not read, so a reason may quote an old word."""
    lines = text.split("\n")
    hits, markers = [], {}
    for number, line in enumerate(lines, 1):
        start = _MARKER_START.search(line)
        if start:
            markers[number] = _valid_marker(line[start.start():])
            line = line[:start.start()]
        hits += [(number, word) for word in _words_in(line)]
    return _resolve(lines, hits, markers)


def scan_python(source, path="", help_only=False):
    """String literals only: not a docstring, a comment or a name. With
    `help_only`, only the strings of a `help=`, `description=`, `epilog=` or
    `usage=` argument, and every string of verb_help.py."""
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            first = node.body[0] if node.body else None
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                docstrings.add(id(first.value))
    allowed = None
    if help_only and not path.endswith("verb_help.py"):
        allowed = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and node.arg in _HELP_KEYWORDS:
                allowed.update(id(sub) for sub in ast.walk(node.value))
    lines = source.split("\n")
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in docstrings or (allowed is not None and id(node) not in allowed):
            continue
        for found in _WORD.finditer(node.value):
            number = node.lineno + node.value.count("\n", 0, found.start())
            hits.append((number, found.group(1).lower()))
    markers = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            start = _MARKER_START.search(token.string)
            if start:
                markers[token.start[0]] = _valid_marker(token.string[start.start():])
    return _resolve(lines, sorted(set(hits)), markers, check_unused=allowed is None)


def _shell_regions(lines):
    """The quoted strings and the heredoc bodies of a shell script, with the
    number of their line, and the comment on each line that has one."""
    strings, comments = [], {}
    quote = heredoc = None
    for number, raw in enumerate(lines, 1):
        if heredoc is not None:
            if raw.strip() == heredoc:
                heredoc = None
            else:
                strings.append((number, raw))
            continue
        piece, code, i = [], raw, 0
        while i < len(raw):
            char = raw[i]
            if quote:
                if char == "\\" and quote == '"':
                    piece.append(raw[i:i + 2])
                    i += 2
                    continue
                if char == quote:
                    quote = None
                    piece.append(" ")
                else:
                    piece.append(char)
            elif char == "\\":
                i += 2
                continue
            elif char in "\"'":
                quote = char
            elif char == "#" and (i == 0 or raw[i - 1] in " \t;"):
                comments[number] = raw[i:]
                code = raw[:i]
                break
            i += 1
        if piece:
            strings.append((number, "".join(piece)))
        if quote is None:
            start = _HEREDOC.search(code)
            if start:
                heredoc = start.group(2)
    return strings, comments


def scan_shell(source, path=""):
    """Quoted strings and the printed bodies of heredocs, not comment lines or
    command names. A marker in a comment, or in a heredoc line, covers the line."""
    lines = source.split("\n")
    strings, comments = _shell_regions(lines)
    hits, markers = [], {}
    for number, comment in comments.items():
        start = _MARKER_START.search(comment)
        if start:
            markers[number] = _valid_marker(comment[start.start():])
    for number, text in strings:
        start = _MARKER_START.search(text)
        if start and number not in comments:
            # A heredoc line carries its marker in the text itself.
            markers[number] = _valid_marker(text[start.start():])
            text = text[:start.start()]
        hits += [(number, word) for word in _words_in(text)]
    return _resolve(lines, sorted(set(hits)), markers)


def is_excluded(path):
    """True for a path in a frozen class, which the guard never reads."""
    path = str(path).replace(os.sep, "/")
    for entry in EXCLUDED:
        if entry.endswith("/"):
            if path.startswith(entry):
                return True
        elif path == entry or path.startswith(entry + "/"):
            return True
    return False


def scan_source(path, text, kind):
    """`(path, line, word, line text)` for each finding in `text`, read as the
    file `path` of a group of this kind. A frozen path reports nothing."""
    if is_excluded(path):
        return []
    if kind == "python":
        found = scan_python(text, path)
    elif kind == "help":
        found = scan_python(text, path, help_only=True)
    elif str(path).endswith(".sh"):
        found = scan_shell(text, path)
    elif str(path).endswith(".py"):
        found = scan_python(text, path)
    else:
        found = scan_text(text, path)
    return [(str(path), number, word, line) for number, word, line in found
            if not _kept_line(str(path), line)]


def _kept_line(path, line):
    return any(path == kept and fragment in line for kept, fragment, _ in KEPT_LINES)


def _files(group, root):
    root = Path(root)
    for entry in group["paths"]:
        target = root / entry
        if target.is_file():
            yield target
        else:
            for folder, names, files in os.walk(target):
                names[:] = sorted(n for n in names if n != "__pycache__")
                for name in sorted(files):
                    yield Path(folder) / name


def scan_group(group, root):
    """`(path, line, word, line text)` for each finding in the files of a live
    group under `root`. A group that is not live reports nothing."""
    if not group["live"]:
        return []
    found = []
    for target in _files(group, root):
        rel = target.relative_to(root).as_posix()
        python = group["kind"] in ("python", "help")
        if python and not (rel.endswith(".py") or rel == "cli/compass"):
            continue
        if not python and not rel.endswith(_TEXT_SUFFIXES):
            continue
        if is_excluded(rel):
            continue
        found += scan_source(rel, target.read_text(encoding="utf-8"), group["kind"])
    return found


def render(hits):
    """One line for each finding, naming the file, the line and the word."""
    return "\n".join(f"{path}:{number}: {word} - {line.strip()}"
                     for path, number, word, line in hits)
