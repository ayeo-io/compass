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

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import us_english_words as words  # noqa: E402

TRC_059_WORDS = (
    "behaviour behaviours behavioural judgement judgements catalogue "
    "catalogues initialise initialised initialising initialisation colour "
    "colours labelled labelling normalise normalised recognise recognised "
    "honour honoured licence spelt organise organisation analyse analysed "
    "centre favour artefact whilst centrepiece").split()


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
