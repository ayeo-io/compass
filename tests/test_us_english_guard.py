"""The cheap US English guard (issue language-key-and-us-english).

`tests/us_english_words.py` holds the word list and the scan functions. This
file checks that the list is one constant, that each scan reads what it must
and ignores what it must, that a planted British word fails in each file
group, and that an exemption marker works on its own line only.

The guard is live for the CLI string literals and the `--help` text. The
other file groups have a row with `live` off until their files are
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
    assert words.scan_text(f"un{word}") == []
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
    live = sorted(g["name"] for g in words.GROUPS if g["live"])
    assert live == ["cli help strings", "cli string literals"]


def test_each_live_field_is_on_its_own_line_three_lines_apart():
    """Three units flip three rows in one file without a merge conflict."""
    lines = (ROOT / "tests" / "us_english_words.py").read_text(encoding="utf-8").splitlines()
    numbers = [i for i, line in enumerate(lines, 1) if re.match(r'\s*"live":', line)]
    assert len(numbers) == len(words.GROUPS)
    assert all(b - a >= 3 for a, b in zip(numbers, numbers[1:])), numbers


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
