"""The owning doc names the verb that syncs a GitHub issue.

9.0.0 removed the issue page (ADR-091), so the docs no longer describe it. The verb
`compass issue github sync` is kept, and the docs must name it and record that it
replaced `compass issue labels sync`.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD_VERB = "compass issue labels sync"
NEW_VERB = "compass issue github sync"


def _flat(path):
    return " ".join((ROOT / path).read_text(encoding="utf-8").split())


def test_ipg_21_owning_doc_names_the_sync_verb():
    raw = (ROOT / "docs" / "github-labels.md").read_text(encoding="utf-8")
    doc = " ".join(raw.split())

    # The new verb is named, and the old one only in the single line that records its removal.
    assert NEW_VERB in doc
    removal = [line for line in raw.splitlines() if OLD_VERB in line]
    assert len(removal) == 1, removal
    assert "removed" in removal[0] and "7.0.0" in removal[0]

    # The walkthrough uses only the new verb.
    walkthrough = _flat("docs/github-labels-walkthrough.md")
    assert NEW_VERB in walkthrough
    assert "labels sync" not in walkthrough

    # The upgrade guide that renamed the verb names both.
    upgrade = _flat("docs/upgrade-7-0-0.md")
    assert OLD_VERB in upgrade and NEW_VERB in upgrade


def test_ipg_21_no_current_doc_describes_the_removed_issue_page():
    for name in ("docs/github-labels.md", "docs/security.md"):
        assert "github_labels.page" not in _flat(name), name
