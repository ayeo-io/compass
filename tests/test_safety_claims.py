"""What Compass promises about itself matches what it can demonstrate.

Issue: claims-match-what-is-proved. Scenarios `TRC-B1` to `TRC-B4`, `TRC-D1`,
`TRC-D2` and `TRC-F2`.

The finding these cover, from an outside engineering review of 3.2.0: the
tested-before-ship promise reads as "the declared test ran", and what Compass
establishes is that the code declares a scenario, the scenario declares a test,
and some command exited zero. `_check_suite_passed` says so in its own comment.

Two separate jobs here. Narrow the wording so it stops overclaiming, and hold
the safety contract to naming a real mechanism behind every guarantee so it
cannot drift back.
"""

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "cli"))

CHECK_SET_YML = REPO_ROOT / "governance" / "check-set.yml"
GUARDRAILS_MD = REPO_ROOT / "governance" / "guardrails.md"
METHODOLOGY = REPO_ROOT / "docs" / "methodology.md"
CONTRACT = REPO_ROOT / "docs" / "safety-contract.md"

#: The sentence this issue removes. It appeared in three files, worded
#: identically, and it is the overclaim itself - kept here so the test can say
#: "not this" rather than only "something like that".
OVERCLAIM = "No code reaches main without a passing automated test it traces to"


def _g1_statement() -> str:
    """The tested-before-it-lands guardrail's statement (`G1`), read from the
    machine-readable file that owns it."""
    from check_set_files import view as shipped_view
    data = shipped_view("guardrails.yml")
    for g in (data.get("defaults") or []):
        if g.get("id") == "G1":
            return " ".join(str(g.get("statement", "")).split())
    raise AssertionError("G1 is not in governance/check-set.yml")


def _normalise(text: str) -> str:
    """Collapse whitespace and markdown emphasis so wording can be compared.

    The same sentence is a YAML block scalar in one file, a prose paragraph in
    another, and a numbered list item with backticks in the third. Comparing
    them raw would fail on formatting, which is not what any of these test.
    """
    text = text.replace("`", "").replace("**", "").replace("*", "")
    return " ".join(text.split())


# --- `TRC-B1` ---------------------------------------------------------------

def test_b1_tested_before_ship_promise_is_narrowed():
    """The promise says what a green record establishes (TRC-B1).

    A test-run record holds one exit code for one command. It does not
    enumerate the tests the command collected, so "a passing automated test it
    traces to" claims an execution relationship Compass never observes.
    """
    statement = _normalise(_g1_statement())

    assert OVERCLAIM.lower() not in statement.lower(), (
        "G1 still carries the sentence this issue exists to remove:\n"
        f"  {statement}")

    low = statement.lower()
    # It must still promise the traceable relationship, which is real...
    assert "trace" in low, (
        "the narrowed statement dropped the traceability half, which Compass "
        "does establish - this narrows the promise past what is true")
    # ...and it must say what is NOT observed, in words a reader meets here
    # rather than having to find in the source.
    assert "observe" in low or "does not establish" in low or "not verify" in low, (
        "the narrowed statement does not say what is left unproved. A promise "
        "that quietly omits its limit reads exactly like the old one")


def test_b1b_the_statement_points_at_where_the_stronger_guarantee_is_built():
    """A limit with no route out reads as a permanent one (TRC-B1)."""
    statement = _g1_statement().lower()
    assert "safety-contract" in statement or "safety contract" in statement, (
        "the statement does not point the reader at the contract that "
        "explains the limit in full")


# --- `TRC-B2` ---------------------------------------------------------------

def test_b2_promise_reads_the_same_in_all_three_files():
    """Correct every place at once, or a reader finds a contradiction
    (TRC-B2).

    The canonical wording lives in `G1`'s `statement:`. The two prose files must
    carry it. Reading it from the YAML rather than hardcoding it here keeps the
    sentence in one place instead of four.
    """
    canonical = _normalise(_g1_statement())
    # The first sentence is the promise; the rest of the statement may add the
    # pointer and the limit in whatever shape each file's prose wants.
    promise = canonical.split(".")[0].strip()
    assert len(promise) > 20, f"G1's statement is too short to be a promise: {promise!r}"

    for path in (GUARDRAILS_MD, METHODOLOGY):
        body = _normalise(path.read_text(encoding="utf-8"))
        assert promise.lower() in body.lower(), (
            f"{path.relative_to(REPO_ROOT)} does not carry the narrowed "
            f"promise from governance/guardrails.yml.\n"
            f"  expected to find: {promise}\n"
            f"Correct every place at once - a reader who finds the old wording "
            f"has no way to know which is current.")


def test_b2b_the_old_overclaim_is_gone_from_every_file():
    """The removal is checked, not assumed (TRC-B2)."""
    for path in (CHECK_SET_YML, GUARDRAILS_MD, METHODOLOGY, CONTRACT):
        body = _normalise(path.read_text(encoding="utf-8"))
        assert OVERCLAIM.lower() not in body.lower(), (
            f"{path.relative_to(REPO_ROOT)} still carries the overclaim")


# --- `TRC-F2` ---------------------------------------------------------------

def test_f2_narrowed_wording_does_not_soften_the_check():
    """The words get smaller; the machine does not (TRC-F2).

    The risk in a wording change is that someone reads the softer sentence as
    permission to soften the check. `G1`'s `checks:` list is what actually runs,
    and it must be untouched by this issue.
    """
    from check_set_files import view as shipped_view
    data = shipped_view("guardrails.yml")
    g1 = next(g for g in data["defaults"] if g.get("id") == "G1")

    expected = {"scenarios-have-tests", "declared-tests-resolve", "suite-passed",
                "changed-code-traces-to-scenario", "scenarios-are-executable"}
    assert set(g1.get("checks") or []) == expected, (
        "G1's checks list changed. This issue narrows the STATEMENT only - if "
        "the enforcement moved too, the wording change has quietly become a "
        "governance change and must stop.\n"
        f"  expected: {sorted(expected)}\n"
        f"  found   : {sorted(g1.get('checks') or [])}")


# --- `TRC-B3` ---------------------------------------------------------------

def test_b3_contract_states_the_evidence_limit():
    """The contract says what a green record does not establish (TRC-B3).

    It already has the right section for this - 'What Compass does NOT claim' -
    sitting next to the honest note about the hook failing open on shell
    commands. This is the same kind of admission and belongs beside it.
    """
    body = _normalise(CONTRACT.read_text(encoding="utf-8"))
    section = body.lower()

    assert "one exit code for one command" in section, (
        "the contract does not say what a test-run record actually holds")
    assert "which tests" in section or "which test" in section, (
        "the contract does not say the record leaves the collected tests "
        "unrecorded - which is the whole limit")
    # A record now names the tree it ran on (`evidence-binding`). The limit
    # that remains is who made the record, and the contract must say so.
    assert "tree_id" in section and "trusted runner" in section, (
        "the contract does not say what a record's tree id proves and what "
        "it does not")


# --- `TRC-B4`, `TRC-D1`, `TRC-D2` --------------------------------------------

from safety_contract_check import (  # noqa: E402
    EmptyContract, Problem, check, parse_backing, parse_guarantees,
)


def test_b4_every_guarantee_names_a_backing_mechanism():
    """Run against the real contract; it must come back clean (TRC-B4)."""
    problems = check(CONTRACT.read_text(encoding="utf-8"), str(REPO_ROOT))
    assert not problems, "\n".join(str(p) for p in problems)


def test_b4b_the_check_actually_inspected_something():
    """A clean result is only worth having if the parse found rows
    (TRC-B4).

    Paired with the test above on purpose. 'No problems' and 'no input' produce
    the same empty list, and this is the assertion that tells them apart.
    """
    text = CONTRACT.read_text(encoding="utf-8")
    assert len(parse_guarantees(text)) >= 5, "suspiciously few guarantees parsed"
    assert len(parse_backing(text)) >= 5, "suspiciously few backing rows parsed"


def test_d1_guarantee_without_backing_fails():
    """A guarantee nothing accounts for is reported by number (TRC-D1)."""
    text = CONTRACT.read_text(encoding="utf-8")
    n = max(parse_guarantees(text)) + 1
    # Anchored on the section heading by shape rather than by its exact
    # words. Pinning the version in it is what broke this check when the
    # contract's headings stopped carrying one.
    # Find the section after the guarantees by its shape, not its heading
    # text: the heading has changed twice.
    m = re.search(r"^## (?:What Compass.*does NOT claim|Deliberate limits).*$",
                   text, re.M)
    assert m, (
        "the contract has no limits section to plant before - it is the "
        "boundary this test plants a guarantee against")
    planted = (text[:m.start()]
               + f"{n}. **A guarantee nobody wrote a mechanism for.** Invented "
                 f"by a test.\n\n"
               + text[m.start():])

    problems = check(planted, str(REPO_ROOT))
    assert any(p.guarantee == n for p in problems), (
        f"a guarantee with no backing row was not reported. Found: "
        f"{[str(p) for p in problems]}")


def test_d2_missing_named_mechanism_fails():
    """A row naming a file that is not there is reported (TRC-D2)."""
    text = CONTRACT.read_text(encoding="utf-8")
    backing = parse_backing(text)
    n = min(backing)
    planted = text.replace(
        backing[n], " a mechanism in `docs/this-file-does-not-exist.md` ", 1)

    problems = check(planted, str(REPO_ROOT))
    assert any("this-file-does-not-exist" in p.detail for p in problems), (
        f"a backing row naming a missing file was not reported. Found: "
        f"{[str(p) for p in problems]}")


def test_d2b_a_row_naming_a_command_the_cli_lacks_fails():
    """The same for a command, since half the rows name one (TRC-D2)."""
    text = CONTRACT.read_text(encoding="utf-8")
    backing = parse_backing(text)
    n = min(backing)
    planted = text.replace(backing[n], " run `compass nonexistentverb` ", 1)

    problems = check(planted, str(REPO_ROOT))
    assert any("nonexistentverb" in p.detail for p in problems)


def test_d3_an_unparseable_contract_raises_rather_than_passing():
    """The design decision that keeps this from being a check that cannot fail.

    tests/test_version_guard_covers_every_location.py:12-15 names four checks
    that have shipped in this project and passed because they found nothing
    to inspect. Fed a contract with no guarantees, this one must refuse to
    answer rather than answer 'clean'.
    """
    with pytest.raises(EmptyContract):
        parse_guarantees("# Not a contract\n\nNothing here.\n")
    with pytest.raises(EmptyContract):
        parse_backing("# Not a contract\n\nNothing here.\n")
    with pytest.raises(EmptyContract):
        check("# Not a contract\n\nNothing here.\n", str(REPO_ROOT))
