"""docs/configuration.md documents the `language` setting.

Scenarios, in the acceptance criteria of the issue `language-key-and-us-english`:
the row and section (TRC-030), and the one CLAUDE.md sentence (TRC-031).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "configuration.md"
# The table in GitHub issue #241 ("Language codes for the docs") has 39 rows.
# The acceptance criteria say 38, a miscount: the guide copies the issue.
TAG_ROWS = 39
IANA ="https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry"


def _guide():
    return GUIDE.read_text(encoding="utf-8")


def _section(text):
    """The `language` section, from its heading to the next heading."""
    m = re.search(r"^### `language`\n(.*?)(?=^#{1,3} |\Z)", text, flags=re.M | re.S)
    assert m, "docs/configuration.md has no `language` section"
    return m.group(1)


def _tag_rows(section):
    return re.findall(r"^\| ([^|]+?) \| `([^`]+)` \|$", section, flags=re.M)


def _problems(text):
    problems = []
    row = re.search(r"^\| `language` \| [^|]+ \| a BCP 47 tag such as `?en-US`? "
                    r"\| unset: no instruction \|$", text, flags=re.M)
    if not row:
        problems.append("the Settings table has no language row")
    try:
        section = _section(text)
    except AssertionError:
        return problems + ["no language section"]
    rows = [r for r in _tag_rows(section) if r[0] != "Language"]
    if len(rows) != TAG_ROWS:
        problems.append(f"the tag table has {len(rows)} rows, not {TAG_ROWS}")
    if IANA not in section:
        problems.append("no link to the IANA registry")
    flat = " ".join(section.split())
    for note, pattern in {
        "bare language": r"bare language \(`de`\) is fine",
        "chinese": r"`zh-Hans` and `zh-Hant` for Chinese",
        "norwegian": r"Norwegian is `nb` or `nn`, not `no`",
        "hebrew": r"Hebrew is `he`, not `iw`",
        "unset": r"unset means no instruction|Unset means no instruction",
        "preset": r"preset cannot carry",
        "lint": r"`compass policy lint`",
    }.items():
        if not re.search(pattern, flat):
            problems.append(f"the section lacks the {note} note")
    old = re.search(r"What counts as a settings key in the old file:\*\*(.*?)\n- \*\*",
                    text, flags=re.S)
    if not old or "`language`" not in old.group(1):
        problems.append("the old-file settings list does not name language")
    return problems


def test_trc_030_the_guide_documents_the_language_setting():
    assert _problems(_guide()) == []


def test_trc_030_a_dropped_tag_row_fails_the_check():
    text = _guide()
    assert "| German (Germany) | `de-DE` |\n" in text
    planted = text.replace("| German (Germany) | `de-DE` |\n", "")
    assert any("38 rows" in p for p in _problems(planted)), _problems(planted)


def test_trc_031_exactly_one_sentence_mentions_claude_md():
    section = " ".join(_section(_guide()).split())
    sentences = re.split(r"(?<=[.!?])\s+", section)
    hits = [s for s in sentences if "CLAUDE.md" in s]
    assert len(hits) == 1, hits
    sentence = hits[0]
    assert "`CLAUDE.md` or `AGENTS.md`" in sentence, sentence
    assert re.search(r"names a language", sentence), sentence
    assert re.search(r"drop (?:it|that sentence)", sentence), sentence
    assert re.search(r"Compass never edits", sentence), sentence
    assert not re.search(r"wins|overrid|precedence|takes priority|follows|instead of",
                         sentence), sentence
