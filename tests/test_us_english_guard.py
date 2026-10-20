"""The cheap US English guard (issue language-key-and-us-english).

`tests/us_english_words.py` holds the word list and the scan functions. This
file checks that the list is one constant, that each scan reads what it must
and ignores what it must, that a planted British word fails in each file
group, and that an exemption marker works on its own line only.

The guard is live for every file group: the shipped prose, the hooks,
schemas and adapters, the CLI string literals and the `--help` text. A
row's `live` field turns its scan off only while its files are not
converted.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import us_english_words as words  # noqa: E402
import test_frozen_files_unchanged as frozen  # noqa: E402

TRC_059_WORDS = (
    "behaviour behaviours behavioural judgement judgements catalogue "
    "catalogues initialise initialised initialising initialisation colour "
    "colours labelled labelling normalise normalised recognise recognised "
    "honour honoured licence spelt organise organisation analyse analysed "
    "centre favour artefact whilst centrepiece").split()

# A real CLI file with no British word in a string literal, for "the
# unchanged file passes" on a live row.
CLEAN_CLI_FILE = "cli/compass_pkg/atomic_io.py"


def _first(folder, pattern):
    return sorted(p.relative_to(ROOT).as_posix()
                  for p in (ROOT / folder).glob(pattern))[0]


def _plant(path, how):
    """The text of a repository file with one planted line, and the number
    of that line."""
    text = (ROOT / path).read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    return text + how + "\n", text.count("\n") + 1


def test_trc_059():
    """The list is one constant, holds the 32 words and bans no valid word."""
    assert len(TRC_059_WORDS) == 32
    assert isinstance(words.WORDS, tuple)
    assert set(TRC_059_WORDS) <= set(words.WORDS)
    assert len(set(words.WORDS)) == len(words.WORDS), "a word is listed twice"
    for banned_not in ("cancelled", "towards"):
        assert banned_not not in words.WORDS
    for word in words.WORDS:
        assert word.isalpha() and word == word.lower(), \
            f"{word!r} is not a plain lower-case word, so it may be an identifier"
    # Each word has its US form, so unit 8 and the 7.1.0 script read one table.
    assert set(words.US_FORMS) == set(words.WORDS)
    assert all(words.US_FORMS[w] != w for w in words.WORDS)
    # One place: no other test or tool file repeats the list.
    for other in sorted((ROOT / "tests").glob("*.py")):
        if other.name in ("us_english_words.py", "test_us_english_guard.py"):
            continue
        text = other.read_text(encoding="utf-8")
        assert not ("centrepiece" in text and "judgements" in text
                    and "initialising" in text), f"{other.name} repeats the list"


@pytest.mark.parametrize("word", TRC_059_WORDS)
def test_trc_059_every_form_is_found_whole_and_in_any_case(word):
    """Each listed form is a hit alone and in capitals, and not inside a
    longer word."""
    assert [h[1] for h in words.scan_text(f"a {word} here")] == [word]
    assert [h[1] for h in words.scan_text(word.upper())] == [word]
    assert words.scan_text(f"a {word}ism here") == []
    assert words.scan_text(f"xx{word}") == []
    assert words.scan_text(f"{word}_name = 1") == []


def test_trc_059_behavioural_is_a_hit_and_behaviourism_is_not():
    assert words.scan_text("behavioural") != []
    assert words.scan_text("behaviourism") == []


# The eight rows of the planted-breach scenario: (name, file, kind, planted line).
ROWS = [
    ("README.md", "README.md", "text", "This line holds behaviour."),
    ("a skill", _first("skills", "*/SKILL.md"), "text", "This line holds behaviour."),
    ("a command", _first("commands", "*.md"), "text", "This line holds behaviour."),
    ("a template", _first("templates", "*.md"), "text", "This line holds behaviour."),
    ("CLAUDE.md", "CLAUDE.md", "text", "This line holds behaviour."),
    ("a printed message", "cli/compass_pkg/atomic_io.py", "python",
     'print("the behaviour of it")'),
    ("an argparse help string", "cli/compass_pkg/atomic_io.py", "help",
     'parser.add_argument("--x", help="the behaviour of it")'),
    ("a line of session-start.sh", "hooks/session-start.sh", "text",
     'echo "the behaviour of it"'),
]


@pytest.mark.parametrize("name,path,kind,line", ROWS, ids=[r[0] for r in ROWS])
def test_trc_060(name, path, kind, line):
    """A planted `behaviour` in a copy fails and names the file, the line and
    the word; the unchanged clean sample passes."""
    planted, number = _plant(path, line)
    hits = words.scan_source(path, planted, kind)
    assert (path, number, "behaviour", line) in hits, hits
    report = words.render(hits)
    assert f"{path}:{number}" in report and "behaviour" in report
    clean = {"text": "A clean line of prose.\n",
             "python": 'print("a clean message")\n',
             "help": 'parser.add_argument("--x", help="a clean help")\n'}[kind]
    assert words.scan_source(path, clean, kind) == []


def test_trc_060_the_unchanged_live_files_pass():
    """The unchanged clean CLI file passes the two live Python rows."""
    text = (ROOT / CLEAN_CLI_FILE).read_text(encoding="utf-8")
    assert words.scan_source(CLEAN_CLI_FILE, text, "python") == []
    assert words.scan_source(CLEAN_CLI_FILE, text, "help") == []


def test_trc_060_a_shell_line_is_found_in_a_quoted_string_not_a_comment():
    src = '#!/bin/sh\n# the behaviour in a comment\necho "the behaviour"\nx=1\n'
    assert [h[0] for h in words.scan_shell(src)] == [3]
    heredoc = "cat <<'EOF'\nthe colour\nEOF\nbehaviour=1\n"
    assert [h[0] for h in words.scan_shell(heredoc)] == [2]


PY = {
    "a printed message with colour": ('print("the colour")\n', [("colour", 1)]),
    "an argparse help string with behaviour": (
        'p.add_argument("--x", help="the behaviour")\n', [("behaviour", 1)]),
    "a docstring with behaviour": (
        '"""The behaviour."""\ndef f():\n    """The behaviour."""\n'
        'class C:\n    """The behaviour."""\n', []),
    "a comment with behaviour": ("x = 1  # the behaviour\n# the behaviour\n", []),
    "the identifier catalogue_spec": ("catalogue_spec = 1\n", []),
    "the identifier BEHAVIOURS": ("BEHAVIOURS = 1\ndef behaviour(): pass\n", []),
    "a part of an f-string": ('x = f"the {v} colour"\n', [("colour", 1)]),
    "an f-string expression name": ('x = f"the {colour}"\n', []),
    "a string that is not the first statement": (
        'def f():\n    """Doc."""\n    "the colour"\n', [("colour", 3)]),
    "a word on a later line of a multi-line string": (
        'x = """one\ntwo colour\n"""\n', [("colour", 2)]),
}


@pytest.mark.parametrize("name", sorted(PY))
def test_trc_061(name):
    """The scan reads string literals, not docstrings, comments or names."""
    source, expected = PY[name]
    assert [(h[1], h[0]) for h in words.scan_python(source)] == expected


MARK = "us-english-scan: allow - "


def _python_codes(source):
    return [(h[0], h[1]) for h in words.scan_python(source)]


def test_trc_062_a_marker_with_a_reason_covers_its_line():
    assert _python_codes(f'x = "judgement"  # {MARK}quotes the old form\n') == []
    assert words.scan_text(f"the judgement <!-- {MARK}old form -->\n") == []
    assert words.scan_shell(f'echo "judgement" # {MARK}old form\n') == []


def test_trc_062_a_comment_ended_by_bang_closer_is_read_like_one_ended_by_dashes():
    """A browser ends an HTML comment at `--!>` as well as `-->`."""
    assert words.scan_text(f"the judgement <!-- {MARK}old form --!>\n") == []
    bare = words.scan_text(f"the judgement <!-- {MARK}--!>\n")
    assert [(h[0], h[1]) for h in bare] == [(1, "judgement")]
    after = words.scan_text(f"the judgement <!-- {MARK}old form --!>\nthe colour\n")
    assert [(h[0], h[1]) for h in after] == [(2, "colour")]


def test_trc_062_a_marker_with_no_reason_fails():
    for line in (f'x = "judgement"  # {MARK.strip()}\n',
                 'x = "judgement"  # us-english-scan: allow\n',
                 f'x = "judgement"  # {MARK}   \n'):
        hits = _python_codes(line)
        assert (1, "judgement") in hits, (line, hits)


def test_trc_062_a_marker_covers_its_own_line_only():
    source = f'# {MARK}old form\nx = "judgement"\n'
    assert (2, "judgement") in _python_codes(source)
    text = f"<!-- {MARK}old form -->\nthe judgement\n"
    assert (2, "judgement") in [(h[0], h[1]) for h in words.scan_text(text)]


def test_trc_062_a_marker_at_the_top_that_claims_the_file_is_ignored():
    source = f'# {MARK}whole file\nx = "judgement"\ny = "colour"\n'
    found = [h[0] for h in words.scan_python(source)]
    assert 2 in found and 3 in found
    text = f"<!-- {MARK}whole file -->\nthe judgement\nthe colour\n"
    found = [h[0] for h in words.scan_text(text)]
    assert 2 in found and 3 in found


def test_trc_062_a_marker_on_a_line_with_no_listed_word_fails():
    hits = words.scan_python(f'x = "fine"  # {MARK}no word here\n')
    assert [(h[0], h[1]) for h in hits] == [(1, words.NOT_NEEDED)]
    hits = words.scan_text(f"a fine line <!-- {MARK}no word here -->\n")
    assert [(h[0], h[1]) for h in hits] == [(1, words.NOT_NEEDED)]


def test_trc_062_a_word_only_in_the_reason_does_not_make_a_marker_needed():
    hits = words.scan_text(f"a fine line <!-- {MARK}the old word judgement -->\n")
    assert [h[1] for h in hits] == [words.NOT_NEEDED]


def test_trc_062_marker_text_inside_a_python_string_is_not_a_marker():
    source = f'x = "judgement {MARK}reason"\n'
    assert (1, "judgement") in _python_codes(source)


def test_trc_063():
    """A planted word in each excluded class reports nothing; a path outside
    them reports it."""
    for prefix in words.EXCLUDED:
        path = prefix if not prefix.endswith("/") else prefix + "planted.md"
        for kind in ("text", "python", "help"):
            body = 'print("the behaviour")\n' if kind != "text" else "the behaviour\n"
            assert words.scan_source(path, body, kind) == [], (path, kind)
    assert words.scan_source("docs/x.md", "the behaviour\n", "text") != []
    assert words.scan_source("governance/decisions2/x.md", "the behaviour\n", "text") != []
    assert words.scan_source("governance/presets/default/x.yml", "the behaviour\n",
                             "text") != []


def test_trc_063_a_group_walk_skips_the_excluded_folders(tmp_path):
    for prefix in words.EXCLUDED:
        target = tmp_path / prefix
        if prefix.endswith("/") or prefix in ("cli/vendor", "governance/presets/default@6"):
            target.mkdir(parents=True, exist_ok=True)
            target = target / "planted.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('print("the behaviour")\n', encoding="utf-8")
    group = {"name": "walk", "paths": ["cli", "governance", "architecture", "tests"],
             "kind": "python", "live": True}
    assert words.scan_group(group, tmp_path) == []
    (tmp_path / "cli" / "real.py").write_text('print("the behaviour")\n', encoding="utf-8")
    assert [h[0] for h in words.scan_group(group, tmp_path)] == ["cli/real.py"]


def test_trc_063_the_exclusion_list_equals_the_frozen_classes():
    assert sorted(words.EXCLUDED) == sorted(frozen.FROZEN_PATHS)


def test_a_group_is_scanned_only_when_live(tmp_path):
    (tmp_path / "a.md").write_text("the behaviour\n", encoding="utf-8")
    group = {"name": "x", "paths": ["a.md"], "kind": "text", "live": False}
    assert words.scan_group(group, tmp_path) == []
    group["live"] = True
    assert [h[:3] for h in words.scan_group(group, tmp_path)] == [("a.md", 1, "behaviour")]


def test_groups_have_one_row_for_each_file_group_of_the_scenario():
    names = [g["name"] for g in words.GROUPS]
    assert len(names) == len(set(names)) == 11
    for group in words.GROUPS:
        assert set(group) == {"name", "paths", "kind", "live"}
        assert group["kind"] in ("text", "python", "help")
    assert [g["name"] for g in words.GROUPS if not g["live"]] == []


def test_each_live_field_is_on_its_own_line_three_lines_apart():
    """Three units flip three rows in one file without a merge conflict."""
    lines = (ROOT / "tests" / "us_english_words.py").read_text(encoding="utf-8").splitlines()
    numbers = [i for i, line in enumerate(lines, 1) if re.match(r'\s*"live":', line)]
    assert len(numbers) == len(words.GROUPS)
    assert all(b - a >= 3 for a, b in zip(numbers, numbers[1:])), numbers


ENTRIES = [(g["name"], entry) for g in words.GROUPS for entry in g["paths"]]
PLANTED = {"python": 'print("the behaviour of it")',
           "help": 'parser.add_argument("--x", help="the behaviour of it")'}


def _first_scanned_file(group, entry):
    """The first file that a scan of this path entry reads."""
    one = dict(group, paths=[entry])
    python = group["kind"] in ("python", "help")
    for target in words._files(one, ROOT):
        rel = target.relative_to(ROOT).as_posix()
        if python and not (rel.endswith(".py") or rel == "cli/compass"):
            continue
        if not python and not rel.endswith(words._TEXT_SUFFIXES):
            continue
        return rel
    raise AssertionError(f"{entry} holds no scanned file")


@pytest.mark.parametrize("name,entry", ENTRIES, ids=[f"{n}: {e}" for n, e in ENTRIES])
def test_a_planted_breach_fails_each_live_group_and_a_marker_clears_it(name, entry, tmp_path):
    """A British word planted in a copy of a file of each live path entry is
    found by the group scan. The same line with a marker and a reason is not."""
    group = next(g for g in words.GROUPS if g["name"] == name)
    assert group["live"], f"{name} is not live"
    rel = _first_scanned_file(group, entry)
    copy = tmp_path / rel
    copy.parent.mkdir(parents=True, exist_ok=True)
    text = (ROOT / rel).read_text(encoding="utf-8")
    copy.write_text(text, encoding="utf-8")
    one = dict(group, paths=[entry])
    assert words.scan_group(one, tmp_path) == [], f"{rel} is not clean"
    line = PLANTED.get(group["kind"])
    if line is None:
        line = 'echo "the behaviour of it"' if rel.endswith(".sh") else "This line holds behaviour."
    if rel.endswith(".py") or rel == "cli/compass":
        line = PLANTED.get(group["kind"], 'print("the behaviour of it")')
    planted = text if text.endswith("\n") else text + "\n"
    number = planted.count("\n") + 1
    copy.write_text(planted + line + "\n", encoding="utf-8")
    hits = words.scan_group(one, tmp_path)
    assert (rel, number, "behaviour") == hits[-1][:3], hits
    marked = line + ("  # " if rel.endswith((".sh", ".py")) or rel == "cli/compass" else "  <!-- ")
    marked += words.MARKER + "planted for the test"
    marked += "" if rel.endswith((".sh", ".py")) or rel == "cli/compass" else " -->"
    copy.write_text(planted + marked + "\n", encoding="utf-8")
    assert words.scan_group(one, tmp_path) == [], words.render(words.scan_group(one, tmp_path))


NINE_GROUPS = [
    ("README.md", ["README.md"]),
    ("the adopter docs", ["docs/quickstart.md", "docs/five-minutes.md", "docs/install-smoke-test.md",
                          "docs/releasing.md", "docs/release-notes.md", "docs/upgrade-6-0-0.md",
                          "docs/upgrade-7-0-0.md", "docs/configuration.md", "docs/safety-contract.md",
                          "docs/policy-lint.md", "docs/readiness.md", "docs/refusal-codes.md",
                          "docs/glossary.md", "docs/policy-migrate.md", "docs/routing-deep-dive.md",
                          "docs/roles-guide.md"]),
    ("the house files", ["CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md", "SECURITY.md"]),
    ("the review workflow", [".github/workflows/claude-review.yml"]),
    ("skills", ["skills"]),
    ("commands and agents", ["commands", "agents"]),
    ("approaches and templates", ["approaches", "templates"]),
    ("the contract", ["compass-contract.md"]),
    ("hooks, schemas and adapters", ["hooks", "schemas", "adapters"]),
]


def _covering_group(path):
    for group in words.GROUPS:
        if group["kind"] == "text" and any(
                path == entry or path.startswith(entry + "/") for entry in group["paths"]):
            return group
    return None


@pytest.mark.parametrize("name,paths", NINE_GROUPS, ids=[n for n, _ in NINE_GROUPS])
def test_trc_033(name, paths):
    """Scenario id: `TRC-033` in language-key-and-us-english/acceptance-criteria.md

    Each of the nine surface groups has a live row, and its files hold no
    word of the list outside a marked line. A planted word in a file of the
    group is reported."""
    assert [g["name"] for g in words.GROUPS if not g["live"]] == []
    for path in paths:
        group = _covering_group(path)
        assert group is not None and group["live"], f"no live row covers {path}"
        assert (ROOT / path).exists(), path
        one = dict(group, paths=[path])
        hits = words.scan_group(one, ROOT)
        assert hits == [], words.render(hits)
    # A planted word in a copy of the first file of the group is a hit.
    first = next(f for f in words._files(dict(_covering_group(paths[0]), paths=[paths[0]]), ROOT)
                 if f.suffix in (".md", ".yml", ".sh", ".json"))
    rel = first.relative_to(ROOT).as_posix()
    line = 'echo "the behaviour"' if rel.endswith(".sh") else "This line holds behaviour."
    planted, number = _plant(rel, line)
    assert (rel, number, "behaviour") == words.scan_source(rel, planted, "text")[-1][:3]


def test_trc_034(tmp_path):
    """Scenario id: `TRC-034` in language-key-and-us-english/acceptance-criteria.md

    A guide line that names `judgement` as the old form carries the marker
    with a reason, and the lines around it are still scanned."""
    guide = (ROOT / "docs" / "upgrade-7-0-0.md").read_text(encoding="utf-8")
    lines = guide.splitlines()
    index = next(i for i, ln in enumerate(lines) if "| kind | `judgement` |" in ln)
    assert MARK in lines[index] and lines[index].split(MARK, 1)[1].split("-->")[0].strip()
    assert words.scan_text(guide, "docs/upgrade-7-0-0.md") == []
    # Without the marker the line is a hit; with a marker and no reason it is too.
    bare = lines[index].split("<!--")[0].rstrip()
    assert [h[:2] for h in words.scan_text(bare)] == [(1, "judgement")]
    assert words.scan_text(bare + "  <!-- " + MARK.rstrip(" -") + " -->") != []
    # The marker covers its own line only: a word on the line after is a hit.
    around = "\n".join(lines[index - 1:index + 1]) + "\nThe behaviour here.\n"
    assert [h[0] for h in words.scan_text(around)] == [3]
    # The older guide holds no word either.
    old = (ROOT / "docs" / "upgrade-6-0-0.md").read_text(encoding="utf-8")
    assert words.scan_text(old, "docs/upgrade-6-0-0.md") == []


def test_trc_038(tmp_path):
    """Scenario id: `TRC-038` in language-key-and-us-english/acceptance-criteria.md

    Every heading of a template is in US English, and a project that sets
    another language gets the same headings, with a body written in German
    under them left alone."""
    headings = []
    for template in sorted((ROOT / "templates").rglob("*.md")):
        for number, line in enumerate(template.read_text(encoding="utf-8").splitlines(), 1):
            if line.startswith("#"):
                headings.append((template.relative_to(ROOT).as_posix(), number, line))
    assert len(headings) > 40
    for path, number, line in headings:
        assert words.scan_text(line) == [], f"{path}:{number}: {line}"
    # The fixed headings the CLI writes into the living spec (the `###` headings
    # of that page are issue names, which are identifiers).
    spec = (ROOT / "docs" / "system-spec.md").read_text(encoding="utf-8")
    fixed = [ln for ln in spec.splitlines() if ln.startswith(("# ", "## "))]
    assert fixed and words.scan_text("\n".join(fixed)) == []

    import test_generation_store as store
    shown = []
    for language in (None, "de"):
        root = tmp_path / (language or "plain")
        root.mkdir()
        cfg = {"schema": 1} if language is None else {"schema": 1, "language": language}
        store._project(root, compass_yml=cfg)
        assert store._evaluate_write(root)[0] == 0
        code, out, err = store._run(root, "issue", "template", "show", "requirements-review",
                                    "--issue", store.SLUG)
        assert code == 0, out + err
        german = out.rstrip("\n") + "\n\nDer deutsche Text unter der Ueberschrift.\n"
        shown.append([ln for ln in german.splitlines() if ln.startswith("#")])
    assert shown[0] == shown[1] and shown[0]


def test_a_kept_line_of_a_json_file_is_covered_in_that_file_and_that_line_only():
    """JSON has no comment, so the schema lines that keep `judgement` sit in
    KEPT_LINES, each with a reason. The same line elsewhere is a hit."""
    path = "schemas/manifest.schema.json"
    for kept, fragment, reason in words.KEPT_LINES:
        assert reason.strip() and len(reason.split()) > 1
        text = (ROOT / kept).read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if fragment in ln]
        assert lines, f"the entry {fragment!r} matches no line of {kept}"
        assert words.scan_text("\n".join(lines))
        assert words.scan_source(kept, "\n".join(lines) + "\n", "text") == []
        assert words.scan_source("schemas/other.schema.json", lines[0] + "\n", "text") != []
    planted = '              "judgement",\n              "the behaviour of it",\n'
    hits = words.scan_source(path, planted, "text")
    assert [h[2] for h in hits] == ["behaviour"], hits


@pytest.mark.parametrize("group", words.GROUPS, ids=[g["name"] for g in words.GROUPS])
def test_group(group):
    """A live group holds no word outside an exempt line. A group that is
    not live yet is skipped, and its paths exist."""
    for path in group["paths"]:
        assert (ROOT / path).exists(), path
    hits = words.scan_group(group, ROOT)
    if not group["live"]:
        assert hits == []
        return
    assert hits == [], words.render(hits)
