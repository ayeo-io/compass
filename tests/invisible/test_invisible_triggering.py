"""Tests for invisible triggering (`TRC-C1`, `TRC-C2`, `TRC-C3`, `TRC-F3`).

These are static content-assertion tests. Invisible triggering is prompt-only
(no new hook code). The test strategy:
  - Read compass-contract.md and assert the intent-triggering rule paragraph
    is present.
  - Read each agent file and assert the supporting sentence is present.
  - Assert the rule does not instruct re-running assess when an already-
    assessed issue is active (TRC-F3 guard).
  - Assert the rule is additive (the existing "Never skip assessment" text
    still present and untouched).
  - #358 removed the sentence "Explicitly typing any Compass command always
    works" from the contract; `test_explicit_invocation_still_works` now
    checks the typed command is still named and not displaced.

Manual-verification note (behaviour at runtime, `TRC-C1` / `TRC-C3`):
  These tests check the static content that produces the agent behaviour.
  The runtime behaviour (an agent actually calling /compass:assess on
  natural-language intent) needs a live agent session; the manual-review
  record is in the gitignored issue archive.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# The rule lives in compass-contract.md, which the SessionStart hook
# injects, so it reaches an adopter's session too.
CONTRACT = REPO_ROOT / "compass-contract.md"

CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
AGENTS = {
    "spec-author": REPO_ROOT / "agents" / "spec-author.md",
    "planner":     REPO_ROOT / "agents" / "planner.md",
    "builder":     REPO_ROOT / "agents" / "builder.md",
    "orchestrator": REPO_ROOT / "agents" / "orchestrator.md",
}

# The paragraph that makes the agent run /compass:assess when a user
# states intent (DD-6).
DD6_HEADING = "**Trigger on intent, not on the command.**"
DD6_CONTENT = (
    "If someone describes work to build,\nchange or fix, assess first even "
    "if they never typed the command."
)

# The existing paragraph that must remain untouched (additive-only check)
EXISTING_PARAGRAPH = "**Never skip assessment.**"

# The phrase that must not appear as a reassessment trigger when an issue is
# already active (TRC-F3 guard: invisible triggering must not reassess an
# active issue)
RE_FRAME_TRIGGER_PHRASES = [
    "re-run /compass:assess",
    "re-frame the task",
    "run /compass:assess again",
    "invoke /compass:assess again",
]

# Supporting sentence that must appear in each agent description. Cut before
# "typed" - the sentence wraps there in the four agent files, and a raw
# substring check cannot cross the line break.
AGENT_TRIGGER_SENTENCE = (
    "Assess the work when the request describes it, not only when the "
    "command is"
)


class TestCLAUDEMdInvisibleTriggering:
    """compass-contract.md carries the intent-trigger rule
    (`TRC-C1` / `TRC-C2` / `TRC-C3`)."""

    def test_claude_md_exists(self):
        """CLAUDE.md must exist."""
        assert CLAUDE_MD.is_file(), f"CLAUDE.md not found at {CLAUDE_MD}"

    def test_intent_trigger_heading_present(self):
        """compass-contract.md must contain the intent-trigger heading
        (`TRC-C1` / `TRC-C3`, `DD-6`)."""
        content = CONTRACT.read_text(encoding="utf-8")
        assert DD6_HEADING in content, (
            f"compass-contract.md is missing the intent-trigger heading:\n  {DD6_HEADING!r}\n"
            "Add the DD-6 paragraph per plan.md §DD-6."
        )

    def test_intent_trigger_content_present(self):
        """compass-contract.md must contain the intent-trigger body
        (`TRC-C1` / `TRC-C3`, `DD-6`)."""
        content = CONTRACT.read_text(encoding="utf-8")
        assert DD6_CONTENT in content, (
            "compass-contract.md is missing the intent-trigger body text. "
            "Add the DD-6 paragraph per plan.md §DD-6."
        )

    def test_explicit_invocation_still_works(self):
        """The intent rule adds to the typed command and does not replace it
        (TRC-C2). #358 cut the sentence "Explicitly typing any Compass command
        always works" from the contract, because it describes Claude Code
        rather than a rule. What it protected is checked here instead: the
        contract still tells the agent to run `/compass:assess` itself, and
        the trigger applies "even if they never typed the command", so a
        typed command is not displaced."""
        content = CONTRACT.read_text(encoding="utf-8")
        assert "Run `/compass:assess` before a tool\ncall changes a file." in content, (
            "compass-contract.md must still name /compass:assess as the command "
            "to run (TRC-C2 / BR-011 additive-not-replacement)."
        )
        assert "even if they never typed the command" in content, (
            "The intent trigger must add to the typed command, not replace it "
            "(TRC-C2 / BR-011 additive-not-replacement)."
        )

    def test_existing_never_skip_frame_preserved(self):
        """The existing 'Never skip assessment' paragraph is untouched
        (TRC-C2)."""
        content = CONTRACT.read_text(encoding="utf-8")
        assert EXISTING_PARAGRAPH in content, (
            f"The existing paragraph {EXISTING_PARAGRAPH!r} is missing from "
            "CLAUDE.md. The DD-6 edit must be ADDITIVE - do not replace existing text."
        )

    def test_never_skip_frame_comes_before_trigger_rule(self):
        """The new rule is added AFTER the existing paragraph, not before."""
        content = CONTRACT.read_text(encoding="utf-8")
        existing_pos = content.find(EXISTING_PARAGRAPH)
        trigger_pos = content.find(DD6_HEADING)
        assert existing_pos != -1, "Existing 'Never skip Frame' paragraph not found."
        assert trigger_pos != -1, "Trigger heading not found."
        assert existing_pos < trigger_pos, (
            "The DD-6 trigger heading must appear AFTER the existing "
            "'Never skip Frame' paragraph. Current ordering is reversed."
        )


class TestCLAUDEMdNoReframe:
    """Invisible triggering must not instruct reassessing an active
    issue (TRC-F3)."""

    def test_no_re_frame_trigger_phrases(self):
        """compass-contract.md must not instruct re-running assess on an
        active issue (TRC-F3)."""
        content = CONTRACT.read_text(encoding="utf-8").lower()
        # Check around the intent-trigger paragraph specifically
        trigger_idx = content.find("trigger on intent, not on the command")
        if trigger_idx == -1:
            # If paragraph not yet there, the test for its presence will catch it
            return
        # Look at a window around the trigger paragraph (500 chars each side)
        window = content[max(0, trigger_idx - 100):trigger_idx + 500]
        for phrase in RE_FRAME_TRIGGER_PHRASES:
            assert phrase not in window, (
                f"TRC-F3 violation: the invisible-triggering paragraph must not "
                f"instruct re-running Frame when a task is already framed. "
                f"Found {phrase!r} near the trigger paragraph."
            )


# TestAgentDescriptionsTrigger read the agent files, which 9.0.0 removed (ADR-090).
