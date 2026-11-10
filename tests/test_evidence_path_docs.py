"""Published surfaces describe where a TDD record is actually written.

`compass tdd-green --scenario` `TRC-x` writes `evidence/green-<scenario>.json`.
A run with no binding writes `evidence/green.json`. Both are real; naming
only the second is what misleads, because the skills tell you to bind.

THE GUARD CHECKS THE CLAIM, NOT THE FILE. The shared path is still exactly what
an unbound run writes, so forbidding it would force the documentation to stop
naming a real thing. The rule is:

    where a text claims a verb WRITES the shared record, the claim must be
    qualified as the unbound case.

**The guard checks each claim, not each file:** a file-level rule stays
green once a corrected file contains the bound form anywhere, even where
the unqualified claim is reintroduced elsewhere in the same file.

The window is the matching line plus one either side, because this repository's
prose is hard-wrapped and a qualifier routinely lands on the next line.

What it still cannot do: a qualified claim can still describe the behaviour
incorrectly. This catches an unqualified claim, not a wrong one.

Scenario ids trace to docs-describe-the-old-evidence-path/
acceptance-criteria.md.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent

# Where published surfaces live. Derived by walking these rather than listing
# files: a hardcoded list is a second thing to keep in step with the repository,
# and its failure mode is silent - a file added later is simply never read.
import sys as _sys
import pathlib as _pathlib
_sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent / "cli"))
from compass_pkg.core import is_issue_document as _own_archive

#: An issue's own documents, at `docs/compass/<created>-<slug>/` since
#: `compass migrate` moved them out of `.compass/work/`. They describe the
#: evidence path in force when they were written, so enforcing today's
#: wording over them would report their historical wording as a defect.

PUBLISHED_DIRS = ["docs", "commands", "agents", "skills", "examples", "ci",
                  "templates", "architecture", "governance"]
PUBLISHED_FILES = ["CLAUDE.md", "README.md", "AGENTS.md"]
SUFFIXES = {".md", ".yml", ".yaml"}

# Analysis and proposals are working notes, not published surfaces, and they
# quote historical output on purpose - including the very defect this issue
# fixes. Reading them would make the guard fail on an accurate record.
EXCLUDE_PARTS = {"analysis", "proposals", "node_modules", "__pycache__"}

SHARED = re.compile(r"evidence/(?:green|red|acceptance)\.json")

# A claim that a verb produces the record, rather than a passing mention.
WRITES = re.compile(r"\b(writes?|wrote|records?|recorded|produces?)\b", re.IGNORECASE)

# What makes such a claim correct: it is talking about the unbound case, or it
# names the bound form alongside.
QUALIFIED = re.compile(
    r"evidence/(?:green|red|acceptance)-"      # the bound filename itself
    r"|<scenario>"                             # the bound filename, generalised
    r"|unbound"                                # the case the shared path IS
    r"|no binding"
    r"|when not"
    r"|the binding decides"                    # the rule, named
    r"|scenario-bound",                        # the rule, described
    re.IGNORECASE,
)

BOUND = QUALIFIED   # kept for the tests that only ask "is the bound form named"


def names_shared_without_bound(text: str) -> bool:
    """Does this text CLAIM a verb writes the shared record, unqualified?

    Checked per claim rather than per file. The window is the matching line
    plus one either side: the prose here is hard-wrapped, so a qualifier
    routinely lands on the following line and a line-only window would report
    a correct sentence as broken.
    """
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if not SHARED.search(line):
            continue
        window = "\n".join(lines[max(0, i - 1):i + 2])
        if WRITES.search(window) and not QUALIFIED.search(window):
            return True
    return False


def _published_surfaces() -> Dict[str, str]:
    found: Dict[str, str] = {}
    paths: List[Path] = []
    for d in PUBLISHED_DIRS:
        root = REPO_ROOT / d
        if root.is_dir():
            paths.extend(p for p in root.rglob("*")
                         if p.suffix in SUFFIXES
                         and not _own_archive(p.relative_to(REPO_ROOT)))
    paths.extend(REPO_ROOT / f for f in PUBLISHED_FILES)
    for p in paths:
        if not p.is_file():
            continue
        if EXCLUDE_PARTS & set(p.parts):
            continue
        found[str(p.relative_to(REPO_ROOT))] = p.read_text(encoding="utf-8")
    return found


def _cli_sources() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for p in [REPO_ROOT / "cli" / "compass", *(REPO_ROOT / "cli" / "compass_pkg").glob("*.py")]:
        if p.is_file():
            out[str(p.relative_to(REPO_ROOT))] = p.read_text(encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Group A - the prose says what is written
# ---------------------------------------------------------------------------

def test_a1_no_surface_claims_the_shared_path_unconditionally():
    """`TRC-A1`: no published surface names the shared record without ever
    mentioning the bound one."""
    surfaces = _published_surfaces()
    assert surfaces, (
        "no published surfaces were collected - this guard is reading nothing, "
        "which is how a check quietly stops covering what it names")

    offenders = sorted(name for name, text in surfaces.items()
                       if names_shared_without_bound(text))
    assert not offenders, (
        "these surfaces name the shared evidence record and never mention the "
        "scenario-bound one, so a reader binding a run (which the skills tell "
        "them to do) will look in the wrong place:\n  " + "\n  ".join(offenders))


def test_a2_docs_state_the_binding_rule():
    """`TRC-A2`: the documentation for the green verb states which record a bound
    run writes and which an unbound run writes.

    Removing a false claim is not the same as making the true one available.
    `commands/go.md` and `skills/compass-runtime/SKILL.md` no longer explain the
    green verb (ADR-099: `finish` records the green), and the reference text went
    to `skills/evidence-gates/red-green-records.md`, which must state the rule.
    """
    name = "skills/evidence-gates/red-green-records.md"
    text = (REPO_ROOT / name).read_text(encoding="utf-8")
    assert "tdd-green" in text, f"{name} no longer explains the green verb"
    assert BOUND.search(text), (
        f"{name} explains the green verb but never mentions the "
        f"scenario-bound record, so a reader is told nothing about where "
        f"their evidence went")


def test_a3_worked_example_matches_what_runs():
    """`TRC-A3`: a transcript shows the path a reader will actually see.

    A transcript that disagrees with the screen is worse than no transcript,
    because a reader trusts it over their own output.
    """
    for name in ("docs/quickstart.md", "docs/five-minutes.md"):
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        if not SHARED.search(text):
            continue
        assert BOUND.search(text), (
            f"{name} shows a transcript naming the shared record without "
            f"showing what a bound run produces")


# ---------------------------------------------------------------------------
# Group B - the description stays correct
# ---------------------------------------------------------------------------

def test_b1_guard_catches_a_reintroduced_claim():
    """`TRC-B1`: the guard fails when a surface reintroduces the old claim.

    Tested against the checker directly rather than by editing a real file, so
    the guard's own logic is pinned rather than the corpus's current state. A
    guard written after its defect was fixed passes on first run and
    establishes nothing until something is broken in front of it.
    """
    reintroduced = "Then `compass tdd-green` writes `evidence/green.json`."
    assert names_shared_without_bound(reintroduced), (
        "the guard does not catch the exact claim this issue exists to remove")

    # The shared path is legitimate when the bound form is also present.
    corrected = ("`compass tdd-green --scenario TRC-1` writes "
                 "`evidence/green-TRC-1.json`; an unbound run writes "
                 "`evidence/green.json`.")
    assert not names_shared_without_bound(corrected), (
        "the guard flags text that correctly describes both forms - it is "
        "banning the path rather than requiring the pair")

    # And it must not fire on text that mentions neither.
    assert not names_shared_without_bound("nothing about evidence here")

    # The case a file-level rule misses: a file that has ALREADY been
    # corrected contains the bound form somewhere, so the old claim can be
    # reintroduced anywhere else in it and a file-level check stays green.
    # The claim has to be caught where it is made.
    already_corrected_then_rebroken = (
        "`compass tdd-green` writes `evidence/green.json`.\n"
        "\n"
        "Elsewhere in this file: a bound run writes `evidence/green-TRC-1.json`.\n")
    assert names_shared_without_bound(already_corrected_then_rebroken), (
        "the guard misses a claim reintroduced into a file that was already "
        "corrected - it is checking the file, not the claim")


# ---------------------------------------------------------------------------
# Group C - the repeated banner
# ---------------------------------------------------------------------------

def test_c1_cli_banner_describes_what_is_written():
    """`TRC-C1`: every CLI module's banner says something true about the records
    the TDD verbs write.

    One text, copied into thirteen modules. Reading all of them rather than a
    sample is the point - a sample is how twelve stay wrong.
    """
    sources = _cli_sources()
    assert sources, "no CLI sources collected - this guard is reading nothing"

    offenders = sorted(name for name, text in sources.items()
                       if names_shared_without_bound(text))
    assert not offenders, (
        "these CLI modules describe the TDD verbs as writing the shared record "
        "and never mention the bound one:\n  " + "\n  ".join(offenders))
