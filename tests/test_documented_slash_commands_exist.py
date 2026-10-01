"""Every slash command a shipped document names is one that exists (issue
stale-command-names-in-shipped-prose).

Every slash command a shipped document names must exist, because the
vocabulary scan bans retired *stage words* and does not read slash-command
spellings inside code spans, and `tests/test_documented_commands_exist.py`
reads `compass <verb>`, never `/compass:<name>`, so neither guard catches
one. `skills/compass-runtime/writing-voice.md` showed `/compass:build`,
`/compass:land` and `/compass:clarify` in its worked examples, all three <!-- vocabulary-scan: allow - names the retired commands this test proves are gone -->
removed at 3.0.0. It is the file every agent loads before writing a devlog
entry, a requirements review or a line of dialogue, so sessions copied
their voice from examples naming commands that did not exist.

Scenario ids: `TRC-A1`, `TRC-B1`, `TRC-F1` in
stale-command-names-in-shipped-prose/acceptance-criteria.md
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS = REPO_ROOT / "commands"

DOC_GLOBS = ("commands/*.md", "skills/*/*.md", "agents/*.md", "docs/*.md",
             "governance/*.md", "approaches/*.md", "templates/**/*.md")
NAMED_DOCS = ("CLAUDE.md", "AGENTS.md", "README.md", "compass-contract.md")

# Surfaces where naming a removed command is the job, not the defect.
#
# `architecture/decisions/` is not globbed above at all: a decision record
# keeps the words it was decided in (ADR-022), so an ADR describing a removal
# necessarily names what was removed.
#
# `docs/system-spec.md` is derived from landed scenarios and marks archived
# entries as such. `docs/glossary.md` is derived from the vocabulary, whose
# ban entries must name the word they retire.
SKIP_NAMES = {"system-spec.md", "system-spec-archive.md", "glossary.md"}

# A removed command may be named where the naming IS the service: the upgrade
# table telling a broken caller what to type instead.
ALLOWED = {
    "docs/releasing.md": "the upgrade table names each removed command beside "
                         "its replacement",
}


def _documents():
    out = [REPO_ROOT / n for n in NAMED_DOCS]
    for pat in DOC_GLOBS:
        out += sorted(REPO_ROOT.glob(pat))
    return [p for p in out
            if p.is_file()
            and p.name not in SKIP_NAMES
            and str(p.relative_to(REPO_ROOT)) not in ALLOWED]


def _slash_mentions():
    """Every (document, line, command-name) a shipped document names.

    A blockquote is skipped. `skills/compass-runtime/writing-voice.md` shows
    "Before:" passages quoted verbatim from archived devlogs, with their text
    hash-checked against the real file by
    `tests/test_human_voice.py::test_trc_a2_every_pair_quotes_a_real_archive_passage`.
    Those quotes name the commands that existed when they were written, and
    rewriting one to satisfy this check would falsify the record - which is
    what that hash guard exists to catch.

    Quoting a command is not teaching it. What this guard is for is prose that
    tells a reader to RUN something.
    """
    found = []
    for path in _documents():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "vocabulary-scan: allow" in line:
                continue
            if line.lstrip().startswith(">"):
                continue
            for m in re.finditer(r"/compass:([a-z][a-z-]*)", line):
                found.append((path, n, m.group(1)))
    return found


# ---------------------------------------------------------------------------
# `TRC-A1` - no shipped document names a slash command that does not exist
# ---------------------------------------------------------------------------

def test_no_shipped_document_names_a_slash_command_that_does_not_exist():
    live = {p.stem for p in COMMANDS.glob("*.md")}
    assert live, "no command files found, so this checks nothing"

    missing = []
    for path, n, name in _slash_mentions():
        if name not in live:
            rel = path.relative_to(REPO_ROOT)
            missing.append(f"{rel}:{n}: /compass:{name}")

    assert not missing, (
        "these documents name a slash command that does not exist:\n  "
        + "\n  ".join(sorted(set(missing)))
        + f"\n\nCommands that do exist: {', '.join(sorted(live))}"
        + "\nA worked example is copied, so an example naming a removed "
          "command teaches the removed command.")


# ---------------------------------------------------------------------------
# `TRC-B1` - the safety contract names one start version
# ---------------------------------------------------------------------------

def test_the_safety_contract_names_one_start_version():
    body = (REPO_ROOT / "docs" / "safety-contract.md").read_text(encoding="utf-8")

    claims = re.findall(
        r"(?:contract )?applies from (?:Compass |version )?(\d+\.\d+\.\d+)",
        body)
    assert claims, (
        "docs/safety-contract.md no longer says which version the contract "
        "applies from, so a reader cannot tell what it covers - and this "
        "check is now passing over nothing")
    assert len(set(claims)) == 1, (
        f"docs/safety-contract.md states more than one start version: "
        f"{sorted(set(claims))}. A contract that gives two answers about its "
        f"own scope answers neither.")


# ---------------------------------------------------------------------------
# `TRC-F1` - a guard that reads no commands is refused
# ---------------------------------------------------------------------------

def test_a_guard_that_reads_no_commands_is_refused():
    docs = _documents()
    assert len(docs) >= 40, (
        f"only {len(docs)} shipped documents were gathered - the globs have "
        f"stopped matching and the check above reads almost nothing")

    mentions = _slash_mentions()
    assert len(mentions) >= 20, (
        f"only {len(mentions)} slash-command mentions were read out of "
        f"{len(docs)} documents. The pattern has stopped matching, and a "
        f"check that inspects nothing reports clean exactly like one that "
        f"found nothing wrong")

    # And the live set is real, or every mention above would be reported.
    live = {p.stem for p in COMMANDS.glob("*.md")}
    assert "assess" in live and "ship" in live, (
        f"the command directory no longer holds the commands this project "
        f"runs on: {sorted(live)}")
