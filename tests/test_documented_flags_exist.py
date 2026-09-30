"""Every flag a shipped document teaches is one the CLI accepts (issue
reframe-is-documented-but-does-not-exist). <!-- vocabulary-scan: allow - names the retired flag and the issue that removed it -->

Every flag a shipped document teaches must parse, because a reader who
follows a documented flag the CLI rejects gets `unrecognized arguments` and
no way to tell whether the tool or the instruction is wrong.
`tests/test_documented_commands_exist.py` checks the verb; this checks the
flags, since six shipped surfaces once taught `--reframe`, a flag no <!-- vocabulary-scan: allow - names the retired flag and the issue that removed it -->
version of the CLI has ever parsed, and nothing objected.

Scenario ids: `TRC-A1`, `TRC-A2`, `TRC-F1` in
reframe-is-documented-but-does-not-exist/acceptance-criteria.md <!-- vocabulary-scan: allow - names the retired flag and the issue that removed it -->
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI = REPO_ROOT / "cli" / "compass"

# The surfaces a reader is taught from. `docs/system-spec.md` is derived and
# `docs/proposals/` is untracked planning, so neither teaches anyone anything.
DOC_GLOBS = ("commands/*.md", "skills/*/SKILL.md", "agents/*.md",
             "docs/*.md", "governance/*.md", "approaches/*.md",
             "templates/**/*.md")
NAMED_DOCS = ("CLAUDE.md", "AGENTS.md", "README.md", "compass-contract.md")
SKIP_NAMES = {"system-spec.md"}

# Flags every verb takes, added by the shared output-mode block rather than by
# any one parser. Checking these per verb would be noise.
GLOBAL_FLAGS = {"--help", "--quiet", "--summary", "--verbose", "--json",
                "--evidence-out", "--version"}

# A slash command is NOT a CLI verb, and its flags are its own: `/compass:assess
# --reassess` is read by the command, which then calls
# `compass approach evaluate --write --reason`. So a slash flag is checked
# against the command's own page rather than against any verb's --help -
# conflating the two makes every real slash flag look invalid.


def _documents():
    out = [REPO_ROOT / n for n in NAMED_DOCS]
    for pat in DOC_GLOBS:
        out += sorted(REPO_ROOT.glob(pat))
    return [p for p in out if p.is_file() and p.name not in SKIP_NAMES]


def _flags_a_verb_accepts(verb: str) -> set[str]:
    r = subprocess.run([sys.executable, str(CLI), *verb.split(), "--help"],
                       capture_output=True, text=True, timeout=60)
    return set(re.findall(r"(--[a-z][a-z0-9-]+)", r.stdout + r.stderr))


def _taught_flags():
    """Every (document, line, verb, flag) a shipped document teaches.

    Reads both `compass <verb> --flag` and `/compass:<stage> --flag`, because
    a reader types whichever the page shows them.
    """
    found = []
    for path in _documents():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "vocabulary-scan: allow" in line:
                continue
            for m in re.finditer(r"compass ([a-z][a-z-]*(?: [a-z][a-z-]*)?)"
                                 r"((?:\s+--[a-z][a-z0-9-]+)+)", line):
                verb, rest = m.group(1), m.group(2)
                for flag in re.findall(r"--[a-z][a-z0-9-]+", rest):
                    found.append((path, n, verb, flag))
    return found


# ---------------------------------------------------------------------------
# `TRC-A1` - no shipped document teaches a flag the CLI rejects
# ---------------------------------------------------------------------------

def _slash_flags():
    """Every (document, line, stage, flag) taught for a `/compass:<stage>`."""
    found = []
    for path in _documents():
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "vocabulary-scan: allow" in line:
                continue
            for m in re.finditer(r"/compass:([a-z-]+)((?:\s+--[a-z][a-z0-9-]+)+)", line):
                for flag in re.findall(r"--[a-z][a-z0-9-]+", m.group(2)):
                    found.append((path, n, m.group(1), flag))
    return found


def test_no_shipped_document_teaches_a_flag_the_cli_rejects():
    taught = _taught_flags()
    accepted: dict[str, set[str]] = {}
    bad = []

    for path, n, verb, flag in taught:
        if flag in GLOBAL_FLAGS:
            continue
        if verb not in accepted:
            accepted[verb] = _flags_a_verb_accepts(verb)
        if not accepted[verb]:
            # The verb itself does not resolve. That is
            # test_documented_commands_exist.py's job, not this one.
            continue
        if flag not in accepted[verb]:
            rel = path.relative_to(REPO_ROOT)
            bad.append(f"{rel}:{n}: `compass {verb}` does not accept {flag}")

    # Slash-command flags, checked against the command's own page - that page
    # is where the command's arguments are defined and where a reader looks
    # them up.
    for path, n, stage, flag in _slash_flags():
        page = REPO_ROOT / "commands" / f"{stage}.md"
        if not page.is_file():
            continue        # an unknown command is another guard's finding
        if flag not in page.read_text(encoding="utf-8"):
            rel = path.relative_to(REPO_ROOT)
            bad.append(f"{rel}:{n}: /compass:{stage} does not document {flag}")

    assert not bad, (
        "these documents teach a flag that is not accepted:\n  "
        + "\n  ".join(sorted(set(bad)))
        + "\nA reader who follows the instruction gets `unrecognized "
          "arguments` and cannot tell whether the tool or the page is wrong.")


# ---------------------------------------------------------------------------
# `TRC-A2` - nothing promises the retired spelling still works
# ---------------------------------------------------------------------------

def test_nothing_promises_the_retired_spelling_still_works():
    body = (REPO_ROOT / "commands" / "assess.md").read_text(encoding="utf-8")
    assert "--reassess" in body, (
        "commands/assess.md no longer documents `--reassess`, which is the "
        "flag the verb actually takes")
    assert "--reframe" not in body, (
        "commands/assess.md still names `--reframe`. The flag has never "
        "parsed in any version, so there is no retired spelling to accept - "
        "the sentence promising one was wrong when it was written")


# ---------------------------------------------------------------------------
# `TRC-F1` - a guard that reads no flags is refused
# ---------------------------------------------------------------------------

def test_a_guard_that_reads_no_flags_is_refused():
    """A lower bound, because `bad` is empty both when every flag is real
    and when the reader matched nothing at all."""
    docs = _documents()
    assert len(docs) >= 40, (
        f"only {len(docs)} shipped documents were gathered - the globs have "
        f"stopped matching and the check above is reading almost nothing")

    taught = _taught_flags() + _slash_flags()
    assert len(taught) >= 5, (
        f"only {len(taught)} documented flags were read out of {len(docs)} "
        f"documents - the pattern has stopped matching, and a check that "
        f"inspects nothing reports clean exactly like one that found nothing "
        f"wrong")

    # And the accepted-flag reader really reads something, or every flag above
    # would be skipped as "verb does not resolve". `--reason` is checked
    # rather than `--reassess`: `--reassess` is a SLASH-command argument that
    # `commands/assess.md` defines, and asserting it here would repeat the
    # confusion this guard was written to catch.
    accepted = _flags_a_verb_accepts("approach evaluate")
    assert "--reason" in accepted and "--write" in accepted, (
        f"`compass approach evaluate --help` no longer reports its own flags, "
        f"so the comparison above has nothing to compare against: "
        f"{sorted(accepted)}")
