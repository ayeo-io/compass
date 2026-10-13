"""The owning doc says what the issue page sends to GitHub.

The page posts the issue's documents to everyone who can read the GitHub issue, so the
owning doc must say so, and must name the markers, the checks and the replacement verb.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD_VERB = "compass issue labels sync"
NEW_VERB = "compass issue github sync"


def _flat(path):
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def test_ipg_21_owning_doc_says_what_the_page_exposes():
    raw = (ROOT / "docs" / "github-labels.md").read_text(encoding="utf-8")
    doc = " ".join(raw.split())

    # One paragraph carries the audience statement and the reason for the default.
    paragraphs = [" ".join(p.split()) for p in raw.split("\n\n")]
    audience = [p for p in paragraphs
                if "audience" in p and "readers of the GitHub issue" in p and "off by default" in p]
    assert len(audience) == 1, audience

    # The switch, both markers, and when the body counts as empty.
    for needle in ("github_labels.page", "<!-- compass:issue-page -->",
                   "<!-- compass:issue-ask -->", "counts as empty"):
        assert needle in doc, needle

    # The three checks, what each refuses, and that a refusal is whole.
    for needle in ("rival product name", "private path", "credential",
                   "as it is posted", "refused whole"):
        assert needle in doc, needle

    # The name check depends on record.names_key; the first post without one says so.
    assert "record.names_key" in doc
    assert "only when `record.names_key` is set" in doc
    assert "first post" in doc and "standard error" in doc

    # A linked issue's page is refreshed by its own next sync; lint reports it meanwhile.
    assert "own next sync" in doc and "compass issue lint" in doc and "out of date" in doc

    # Links, size bound, record section, transport, waiting.
    for needle in ("(not on <branch>)", "size bound", "gh api", "standard input",
                   "15-second", "makes no call"):
        assert needle in doc, needle

    # The new verb is named, and the old one only in the single line that records its removal.
    assert NEW_VERB in doc
    removal = [line for line in raw.splitlines() if OLD_VERB in line]
    assert len(removal) == 1, removal
    assert "removed" in removal[0] and "7.0.0" in removal[0]

    # The walkthrough uses only the new verb.
    walkthrough = _flat("docs/github-labels-walkthrough.md")
    assert NEW_VERB in walkthrough
    assert "labels sync" not in walkthrough

    # The documents that describe what leaves the project say the same.
    security = _flat("docs/security.md")
    assert "issue page" in security and "reads no token" in security
    assert "refused whole" in security and "github_labels.page" in security
    upgrade = _flat("docs/upgrade-7-0-0.md")
    assert OLD_VERB in upgrade and NEW_VERB in upgrade and "github_labels.page" in upgrade
