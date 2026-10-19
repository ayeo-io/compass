"""The owning document of `compass policy migrate` describes `--undo`.

Issue `policy-migrate-undo`. These tests read `docs/policy-migrate.md` and
check it against the rules the command follows. They run no migration.

Scenario id: `TRC-040` in policy-migrate-undo/acceptance-criteria.md
Scenario id: `TRC-041` in policy-migrate-undo/acceptance-criteria.md
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
DOC = ROOT / "docs" / "policy-migrate.md"
HEADING = "## Going back with `--undo`"


def _section() -> str:
    """The text of the section on going back, up to the next heading."""
    text = DOC.read_text()
    assert HEADING in text, f"docs/policy-migrate.md has no section {HEADING!r}"
    body = text.split(HEADING, 1)[1]
    return re.split(r"\n## ", body, maxsplit=1)[0]


def test_TRC_040_the_document_no_longer_says_there_is_no_undo():
    """No line says that `--undo` does not exist, is missing or is not yet there."""
    denial = re.compile(
        r"\b(no|not|without|missing|lacks?|yet)\b[^.\n]*`--undo`"
        r"|`--undo`[^.\n]*\b(no|not|missing|yet|does not exist)\b",
        re.IGNORECASE,
    )
    hits = [
        line for line in DOC.read_text().splitlines()
        if "--undo" in line and denial.search(line)
    ]
    assert hits == [], f"the document still denies --undo: {hits}"


REQUIRED = {
    "dry run by default": "dry run",
    "--apply writes": "`--apply`",
    "the dry run refuses like --apply": "refuses in the same way",
    "digest checks": "digest",
    "edited compass.yml": "`compass.yml`",
    "state file": "`state.yml`",
    "marker with no digest": "no digest",
    "manual steps": "manual steps",
    "signed records": "signed record",
    "signed record count": "how many",
    "reads only .compass/work": ".compass/work/",
    "refuses with --words": "`--words`",
    "refuses with DIR": "`DIR`",
    "refuses with --i-have-a-copy": "`--i-have-a-copy`",
    "restores from legacy": "`.compass/legacy/`",
    "legacy folder kept": "keeps `.compass/legacy/`",
    "marker removed last": "`migration.yml` last",
    "state file only if the migration made it": "only if the migration made it",
    "a stopped undo resumes": "run again",
    "an edited compass.yml is refused": "edited `compass.yml`",
    "no override": "no override",
    "json mode": "`undo`",
    "json result ready": "`ready`",
    "json result undone": "`undone`",
}


@pytest.mark.parametrize("rule", sorted(REQUIRED))
def test_TRC_041_the_document_states_the_rules_of_undo(rule):
    """The section on going back names each rule of the command."""
    phrase = REQUIRED[rule]
    assert phrase.lower() in _section().lower(), (
        f"the section on going back does not state {rule!r} "
        f"(looked for {phrase!r})"
    )


def test_the_document_says_most_projects_with_a_waiver_are_refused():
    """The section warns that an approved waiver stub makes the undo refuse."""
    section = _section().lower()
    assert "most" in section and "waiver" in section
    assert "refuses them" in section


def test_the_flags_the_document_names_exist():
    """`--undo`, `--apply` and the other flags the document names are in the help."""
    help_text = subprocess.run(
        [sys.executable, str(CLI), "policy", "migrate", "--help"],
        capture_output=True, text=True, cwd=ROOT, check=False,
    )
    combined = help_text.stdout + help_text.stderr
    for flag in ("--undo", "--apply", "--words", "--i-have-a-copy"):
        assert flag in combined, f"{flag} is not in the help of policy migrate"
