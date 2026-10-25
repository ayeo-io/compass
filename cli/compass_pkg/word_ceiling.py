# compass_pkg.word_ceiling - the one word count and the catalogue's word limits
"""Count a document's words and read the word limit the catalogue gives it.

Every reader that compares a document with its word limit counts through
`count_words`, so an `issue lint` note and a `compass check` verdict cannot
disagree about the same text (ADR-067 decision 2).

The count is the number of whitespace-separated tokens in the visible text:
the lines inside each rendered block go (`rendered_blocks.masked_text`), and
so does every HTML comment, which takes the marker lines with it
(`doc_sections.visible`). Headings, prose, tables and code fences count.
Rendered text comes from records, so counting it would let a reassessment
change a verdict with no edit to the document.

`limit` reads `word_ceiling` from the issue's own catalogue. The field is an
obligation field: `artifact_kinds.entry` never fills it from the shipped
default, so a generation stored before it existed has no limit.
"""
# DEPENDENCY: compass_pkg.artifact_kinds, compass_pkg.doc_sections and
# compass_pkg.rendered_blocks, each imported inside the function that needs it.
# It imports no command module, so a check implementation can import it.
from __future__ import annotations


def count_words(text):
    """The number of words in `text`, counted from its visible text only."""
    from compass_pkg import doc_sections, rendered_blocks

    lines = doc_sections.visible(rendered_blocks.masked_text(text).split("\n"))
    return sum(len(line.split()) for line in lines)


def limit(view, kind, depth):
    """The word limit `view`'s catalogue gives `kind` at `depth`, or None when
    the kind, the field or the depth is absent."""
    from compass_pkg import artifact_kinds

    if depth is None:
        return None
    found = artifact_kinds.entry(view, kind)
    ceiling = (found or {}).get("word_ceiling")
    value = ceiling.get(depth) if isinstance(ceiling, dict) else None
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        return None
    return value
