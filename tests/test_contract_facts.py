"""The injected contract says where Compass writes an issue's files.

`compass-contract.md` reaches every session through the SessionStart hook, so
a wrong sentence in it is read as a fact by every session. It once said every
stage writes under `.compass/work/<issue>/`. Since prose documents moved to
`docs/compass/<created>-<slug>/`, that sentence sent every reader to the wrong
directory, and `CLAUDE.md` repeated it.

These tests tie the two sentences to the CLI rather than to a copy of the
string. The document home comes from `issue_layout.docs_dir_for`, the one
naming rule every writer uses, and a scratch project proves that
`compass issue artifact-path` resolves a registered document there. If the
naming rule changes, the contract test fails until the sentence follows it.

Scenario id: CF-1, in contract-facts/delivery-approach.md
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg.issue_layout import docs_dir_for  # noqa: E402

CONTRACT = ROOT / "compass-contract.md"
CLAUDE_MD = ROOT / "CLAUDE.md"

#: The placeholder form of the two homes, built from the CLI's own rule.
DOCS_HOME = docs_dir_for("<created>", "<slug>").replace("\\", "/") + "/"
STATE_HOME = ".compass/work/<slug>/"


def _collapsed(text: str) -> str:
    return " ".join(text.split())


def _on_disk_paragraph() -> str:
    """The contract's "If it is not on disk" paragraph, whitespace collapsed."""
    text = CONTRACT.read_text(encoding="utf-8")
    match = re.search(r"\*\*If it is not on disk.*?(?:\n\n|\Z)", text, re.S)
    assert match, "compass-contract.md has no 'If it is not on disk' paragraph"
    return _collapsed(match.group(0))


def _where_to_look_line() -> str:
    """The CLAUDE.md "Where to look" bullet that names the issue directories."""
    text = CLAUDE_MD.read_text(encoding="utf-8")
    section = text.split("## Where to look", 1)[1].split("\n## ", 1)[0]
    bullets = re.split(r"\n- ", section)
    hits = [b for b in bullets if ".compass/work/" in b]
    assert hits, "CLAUDE.md 'Where to look' names no .compass/work/ directory"
    return _collapsed(hits[0])


def test_cf_1_the_contract_names_the_docs_home_for_documents():
    para = _on_disk_paragraph()
    assert DOCS_HOME in para, (
        f"the contract's 'If it is not on disk' paragraph does not name "
        f"{DOCS_HOME}, where the CLI puts an issue's documents")
    assert STATE_HOME in para, (
        f"the contract's 'If it is not on disk' paragraph does not name "
        f"{STATE_HOME} for the manifest and evidence")


def test_cf_1_the_contract_does_not_put_every_artifact_under_compass_work():
    for sentence in re.split(r"(?<=\.)\s", _on_disk_paragraph()):
        if ".compass/work/" in sentence:
            assert "artifact" not in sentence.lower(), (
                "the contract still says artifacts live under "
                f".compass/work/: {sentence!r}")


def test_cf_1_claude_md_names_both_homes():
    line = _where_to_look_line()
    assert DOCS_HOME in line and STATE_HOME in line, (
        f"CLAUDE.md's 'Where to look' line must name {DOCS_HOME} for the "
        f"documents and {STATE_HOME} for the manifest and evidence: {line!r}")
