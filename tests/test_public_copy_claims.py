"""Public copy does not claim an outside user, or time one.

Two standing constraints meet here. Nobody outside this repository has used
Compass, so no shipped file must say or imply otherwise. And B2 - the
cold-user test that would have measured how long a first run takes - was
skipped by maintainer decision, so any duration attached to a user's
experience is unmeasured rather than merely unproven, and must not appear
in public copy.

ADR-013 breached both in one clause: its Context said the install "failed on
the machine of someone who had known Compass for ninety seconds", in the past
tense, which reads as a report of a real outside user and carries a timing
figure.

Scope note: this scans the files a reader can actually clone. `.compass/work/`
and `docs/proposals/` are gitignored, so what they say is working material
rather than public copy, and they are deliberately not scanned.

Scenario ids: see docs/system-spec.md (TRC-1, `TRC-2`).
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

# The phrase lists live in the CLI, so `compass scenario add` refuses a title
# that would fail this check once it reaches the living spec (issue #359).
from compass_pkg.public_copy import OUTSIDE_USER_PATTERNS, USER_TIMING_PATTERNS  # noqa: E402


def _public_prose_files() -> list[pathlib.Path]:
    """Tracked markdown a reader gets on clone, minus the gitignored trees."""
    tracked = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.split()
    return [
        ROOT / rel for rel in tracked
        if not rel.startswith(("docs/proposals/", "docs/analysis/", ".compass/"))
        and rel not in _TARGET_DOCUMENTS
    ]


# Documents whose job is to state targets that have NOT been reached.
# `docs/desired-state.md` D5 says a first-time user should reach a first
# shipped change in under fifteen minutes. That is the aspiration this
# repository is measured against, not a claim that it has been met - and D5
# is precisely the statement B2 would have tested and did not. Barring the
# sentence from the document that exists to hold it would delete the target
# rather than protect the claim.
_TARGET_DOCUMENTS = {"docs/desired-state.md"}


def _hits(text: str, patterns: list[str]) -> list[str]:
    found = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for pattern in patterns:
            if re.search(pattern, line, flags=re.IGNORECASE):
                found.append(f"{lineno}: {line.strip()[:90]}")
    return found


def test_trc_1_no_public_file_claims_an_outside_user():
    offenders = []
    for path in _public_prose_files():
        text = path.read_text(encoding="utf-8")
        for hit in _hits(text, OUTSIDE_USER_PATTERNS):
            offenders.append(f"{path.relative_to(ROOT)}:{hit}")
    assert not offenders, (
        "public copy states that someone outside this repository used "
        "Compass. Nobody has:\n  " + "\n  ".join(offenders)
    )


def test_trc_2_no_public_file_times_a_user():
    offenders = []
    for path in _public_prose_files():
        text = path.read_text(encoding="utf-8")
        for hit in _hits(text, USER_TIMING_PATTERNS):
            offenders.append(f"{path.relative_to(ROOT)}:{hit}")
    assert not offenders, (
        "public copy attaches a duration to a user's experience. B2 was "
        "skipped, so no such figure has been measured:\n  "
        + "\n  ".join(offenders)
    )


def test_the_checks_would_have_caught_the_defect_they_exist_for():
    """A guard that cannot fail proves nothing - so fail it on purpose.

    Uses ADR-013's actual pre-fix sentence rather than an invented one, so
    this asserts the patterns catch the real defect and not a strawman.
    """
    pre_fix = (
        "It failed on the machine of someone who had known Compass for "
        "ninety seconds, and it failed silently."
    )
    assert _hits(pre_fix, OUTSIDE_USER_PATTERNS), (
        "the outside-user patterns no longer catch the sentence they were "
        "written for"
    )
    assert _hits(pre_fix, USER_TIMING_PATTERNS), (
        "the timing patterns no longer catch the sentence they were written for"
    )


# ---------------------------------------------------------------------------
# The compensating check for the case study's scanner exemption
# ---------------------------------------------------------------------------

CASE_STUDY = ROOT / "docs" / "case-study-compass-rebuilt-itself.md"


def test_the_case_study_states_the_correction_rather_than_the_claim():
    """It is exempt from the install scanner, so guard the other direction.

    `tests/test_install_surface_no_pip.py` excludes this file because its
    subject is the retired instruction: it quotes `pip install pyyaml` as
    history and names "stdlib-only" to correct a premise the repository
    never actually held. That exemption would also let a later edit turn the
    correction into the claim, unnoticed. This asserts the correction is
    still there.
    """
    if not CASE_STUDY.is_file():
        return  # not yet written, or removed - nothing to guard

    flat = " ".join(CASE_STUDY.read_text(encoding="utf-8").split())
    assert "never claimed to be stdlib-only" in flat, (
        "the case study is exempt from the install-instruction scanner "
        "because it corrects the stdlib-only premise. If it no longer "
        "states that correction, the exemption is unearned"
    )


def test_the_case_study_says_what_a_reader_can_and_cannot_check():
    """It points at receipts, so it must be honest about which ones open.

    `.compass/work/`, `docs/proposals/` and `docs/analysis/` are all
    gitignored, so most of what the article draws on is not in a clone. An
    article arguing "here are the receipts" that does not say which receipts
    a reader can actually open is asking for the trust it claims to replace.
    """
    if not CASE_STUDY.is_file():
        return

    flat = " ".join(CASE_STUDY.read_text(encoding="utf-8").split())

    assert "gitignored" in flat, (
        "the article must name the fact that some of what it cites is not "
        "in a clone"
    )
    for public in ("THIRD-PARTY-NOTICES.md", "governance/terminology.yml"):
        assert public in flat, (
            f"the article should name {public} among the things a reader "
            f"can open, so the disclosure is a boundary rather than a shrug"
        )
    assert ".compass/work/" in flat, (
        "the article must name the archive it cannot show"
    )
