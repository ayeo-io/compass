"""The voice audition becomes a standing strategy (issue voice-audition-standing).

The voice audition is a standing strategy: a permanent review dimension for
any change that writes prose, judged against a calibration sample (the
worked-example rewrite and the "Never stash across a worktree hop" section of
`skills/compass-runtime/SKILL.md`, where it moved when 9.0.0 removed the
worktree-multiagent skill). This file checks that the strategy
says so, and that the reviewer's clarity dimension points at it without
repeating it.

Kept separate from `test_human_voice.py` rather than added to it: that file's
traceability ids (TRC-A1..A4, B1..B3, C1..C3, D1, F3) belong to the
`human-voice` issue's own `acceptance-criteria.md`. This issue has its own
criteria and its own TRC ids; reusing the
same ids in the same file would make two different scenarios answer to one
traceability id, which breaks the very chain this strategy is about.

Criteria: the issue's acceptance criteria
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _range_is_readable(*revs) -> bool:
    """Are these commits in this checkout?

    False on a shallow clone, where the objects were never fetched. Used to
    skip a historical-range assertion rather than let a missing object read
    as a code defect.
    """
    for rev in revs:
        probe = subprocess.run(
            ["git", "cat-file", "-e", f"{rev}^{{commit}}"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if probe.returncode != 0:
            return False
    return True


STRATEGIES = REPO_ROOT / "governance" / "strategies.md"
# `commands/ship.md` carries the review the reviewer agent did until 9.0.0
# (ADR-090, ADR-092).
REVIEWER = REPO_ROOT / "commands" / "ship.md"
EVIDENCE_GATES = REPO_ROOT / "skills" / "evidence-gates" / "SKILL.md"

WORKED_EXAMPLE_PATH = "skills/compass-runtime/writing-voice-worked-example.md"
STASH_SECTION_PATH = "skills/compass-runtime/SKILL.md"
STASH_SECTION_HEADING = "Never stash across a worktree hop"

def _evidence_gates_text():
    """Reads every file in the skill's directory. Long skills are split into
    parts that load on demand, so a guard that reads only SKILL.md reports
    moved content as missing."""
    import pathlib as _p
    d = _p.Path(__file__).resolve().parent.parent / "skills" / "evidence-gates"
    return "\n".join(sorted(p.read_text(encoding="utf-8") for p in d.glob("*.md")))



def _flat(text: str) -> str:
    """Collapse every run of whitespace to one space.

    Phrase assertions here are about what the prose says, not about where
    its lines happen to wrap - `tests/test_human_voice.py` already learned
    this the hard way (see its own `_flat` docstring), so the fix is reused
    rather than re-broken.
    """
    return " ".join(text.split())


def _strategies_text() -> str:
    assert STRATEGIES.is_file(), "governance/strategies.md must exist"
    return STRATEGIES.read_text(encoding="utf-8")


def _strategy_entry() -> str:
    """The new strategy's own section, isolated from the rest of the file.

    Found by its heading naming "audition" rather than by body text, so a
    coincidental match elsewhere in the file (`S7`, the cold-reader strategy,
    already uses the word "permanent" in an unrelated sentence about commit
    trailers) cannot grab the wrong section.
    """
    text = _strategies_text()
    sections = re.split(r"(?m)^### ", text)
    for section in sections[1:]:
        heading = section.split("\n", 1)[0]
        if "audition" in heading.lower():
            return "### " + section
    return ""


# ---------------------------------------------------------------------------
# The strategy records permanence and the calibration sample (`TRC-A1`)
# ---------------------------------------------------------------------------

def test_trc_a1_strategy_states_permanence_and_names_the_calibration_sample():
    entry = _strategy_entry()
    assert entry, (
        "no strategy entry in governance/strategies.md states permanence - "
        "the audition must be recorded as not scoped to one cycle"
    )
    flat = _flat(entry)
    flat_lower = flat.lower()

    assert re.search(r"\bS\d+\b", entry.split("\n", 1)[0]), (
        "the strategy heading must carry an S-number, matching the file's "
        "existing numbering convention"
    )

    assert "does not lapse" in flat_lower or "not scoped to" in flat_lower, (
        "the strategy must say plainly that the audition is permanent, not "
        "tied to the cycle that introduced it"
    )
    assert "any change that writes prose" in flat_lower, (
        "the strategy must say it applies to any change that writes prose a "
        "future session will read or imitate"
    )
    assert "future session" in flat_lower, (
        "the strategy must say the prose is read or imitated by a future "
        "session, not just reviewed once"
    )

    assert WORKED_EXAMPLE_PATH in flat, (
        "the strategy must name the worked example as half of the "
        "calibration sample"
    )
    assert STASH_SECTION_PATH in flat, (
        "the strategy must name skills/compass-runtime/SKILL.md as the other "
        "half of the calibration sample"
    )
    assert STASH_SECTION_HEADING in flat, (
        "the strategy must name the specific section - "
        f"{STASH_SECTION_HEADING!r} - not just the file"
    )


# ---------------------------------------------------------------------------
# The strategy states its own test and its own failure mode (`TRC-A2`)
# ---------------------------------------------------------------------------

def test_trc_a2_strategy_states_its_test_and_its_failure_mode():
    entry = _strategy_entry()
    assert entry, "TRC-A1 must land before this scenario can"
    flat = _flat(entry)

    assert "read it aloud" in flat, (
        "the strategy must say reading the passage aloud is the test"
    )
    assert "colleague" in flat, (
        "the strategy must carry the same 'a colleague at your desk' bar "
        "the reference itself states, not a different test"
    )

    assert "shortens" in flat or "shortening" in flat, (
        "the strategy must name the failure mode: merely shortening "
        "form-speak"
    )
    assert "dropping" in flat or "drops" in flat, (
        "the strategy must say the failure mode is dropping facts, not just "
        "changing form"
    )
    assert "fails" in flat, (
        "the strategy must say plainly that this failure mode fails the "
        "audition"
    )

    assert "*Why a strategy and not a guardrail:*" in entry, (
        "the entry must carry the file's own 'Why a strategy and not a "
        "guardrail' convention"
    )
    assert "*Cross-reference:" in entry, (
        "the entry must carry the file's own cross-reference convention"
    )


# ---------------------------------------------------------------------------
# The reviewer's clarity dimension points at the strategy (`TRC-B1`)
# ---------------------------------------------------------------------------

def test_trc_b1_reviewer_and_evidence_gates_point_at_the_strategy_not_repeat_it():
    reviewer = REVIEWER.read_text(encoding="utf-8")
    gates = _evidence_gates_text()

    strategy_heading = _strategy_entry().split("\n", 1)[0].strip()
    match = re.search(r"`(S\d+)`", strategy_heading)
    assert match, "TRC-A1 must land before this scenario can"
    s_number = match.group(1)

    for name, text in (("commands/ship.md", reviewer),
                        ("skills/evidence-gates/SKILL.md", gates)):
        assert "governance/strategies.md" in text, (
            f"{name} must point the clarity dimension at governance/strategies.md"
        )
        assert s_number in text, (
            f"{name} must name the strategy's own number ({s_number}) so a "
            f"reader can find it without already knowing it exists"
        )
        # A pointer, not a restatement: neither surface should carry the
        # calibration sample's own paths - that text belongs in one place.
        assert WORKED_EXAMPLE_PATH not in text, (
            f"{name} must not repeat the calibration sample's path - point "
            f"at governance/strategies.md instead"
        )
        assert STASH_SECTION_HEADING not in text, (
            f"{name} must not repeat the calibration sample's section name"
        )


# ---------------------------------------------------------------------------
# No new gate, guardrail, CLI verb or vocabulary (`TRC-F1`)
# ---------------------------------------------------------------------------

def test_trc_f1_no_new_gate_guardrail_cli_verb_or_vocabulary():
    # Scoped to this issue's own committed range (4fb4cb5..6ecbbfd), not the
    # working tree against a moving HEAD - see test_human_voice.py's twin of
    # this check for why: a later issue legitimately touching cli/ (bundling
    # PyYAML) must not trip a check that is really about this issue's own,
    # already-landed commits.
    untouched = ["governance/guardrails.yml", "governance/terminology.yml", "cli/"]
    # A pinned range is only immutable if the history is present. CI checks
    # out a shallow clone, where these objects are absent and git exits 128,
    # so ask first rather than letting a missing object read as a failure.
    # The content assertions below need no history and run everywhere; they
    # are what carries this claim when the range cannot be read.
    if _range_is_readable("4fb4cb5", "6ecbbfd"):
        diff = subprocess.run(
            ["git", "diff", "--stat", "4fb4cb5", "6ecbbfd", "--", *untouched],
            cwd=REPO_ROOT, capture_output=True, text=True, check=True,
        )
        assert diff.stdout.strip() == "", (
            f"this issue must not touch guardrails.yml, terminology.yml, or "
            f"cli/:\n{diff.stdout}"
        )

    import yaml
    from check_set_files import view as shipped_view
    guardrails = shipped_view("guardrails.yml")
    assert len(guardrails["defaults"]) == 5

    reviewer = REVIEWER.read_text(encoding="utf-8")
    gates = _evidence_gates_text()
    for name, text in (("commands/ship.md", reviewer),
                        ("skills/evidence-gates/SKILL.md", gates)):
        assert "never an automatic gate failure" in text.lower(), (
            f"{name} must keep the clarity dimension assessed, never a gate"
        )
