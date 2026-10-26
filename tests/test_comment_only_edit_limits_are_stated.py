"""The contract and the decision record state what the comment-only check misses.

The check is a comparison plus two lists of words. A reader who relies on it
must find, in `docs/safety-contract.md` and in the decision record, the cases
that it lets through and the unit that was dropped, and must not find a claim
about a shell-reading rule that this change does not contain.

Scenario ids: see hooks-comment-only-edits-and-prose/acceptance-criteria.md.
"""
from __future__ import annotations

import re
from pathlib import Path
from hook_text import hook_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "docs" / "safety-contract.md"
RECORD = (ROOT / "governance" / "decisions"
          / "2026-10-19-a-comment-only-edit-of-code-needs-no-failing-test.md")
HOOK = ROOT / "hooks" / "pre-tool.sh"

# Claims of a unit that is not in this change: reading the prose of a git
# message, a gh text or a heredoc body as data, and the claims that came with it.
NOT_IN_THIS_CHANGE = (
    "a shell never runs", "read again when a word", "mask_prose_data",
    "four data places", "the reading rule", "is not a write target",
    "the rest is read as before",
)


def _normal(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _section() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    parts = re.split(r"(?m)^### ", text)
    found = [p for p in parts if p.startswith("An Edit that changes only comments")]
    assert found, "docs/safety-contract.md has no section on the comment-only Edit"
    return " ".join(found[0].split())


def test_contract_states_the_limits_of_the_comment_only_check():
    """Scenario id: `TRC-064` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    section = _section()

    # The docstring rule is a word list, and what it misses.
    assert "docstring rule is a word list" in section
    for word in ("PLY", "click", "typer", "FastAPI"):
        assert word in section, word
    # The directive rule is a deny list, and the words added to it.
    assert "deny list" in section
    for word in ("nosemgrep", "gitleaks", "checkov", "lgtm", "NOSONAR", "codeql",
                 "yapf", "tfsec", "## template:"):
        assert word in section, word
    # A first line that a tool reads as a file type, which is not on the list.
    assert "`#cloud-config`" in section and "`#include`" in section
    # The encoding cookie.
    assert "encoding cookie" in section and "utf-7" in section
    # Template text, a symbolic link in a fixture folder, python3 and awk.
    assert "Helm" in section and "enforcement.code_globs" in section
    assert "symbolic link under `evals/*/seed/`" in section
    assert "judges the Edit as before" in section and "python3" in section
    assert "The hook uses awk" in section
    assert "tested on the awk of macOS only" in section and "Linux awk" in section


def test_contract_and_record_make_no_claim_of_the_dropped_unit():
    """Scenario id: `TRC-064` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    for path in (CONTRACT, RECORD):
        text = _normal(path)
        for claim in NOT_IN_THIS_CHANGE:
            assert claim not in text, f"{path.name} still says: {claim}"
    hook = hook_text(HOOK)
    assert "mask_prose_data" not in hook


def test_decision_record_states_the_limits_and_that_unit_d_was_dropped():
    """Scenario id: `TRC-065` in hooks-comment-only-edits-and-prose/acceptance-criteria.md"""
    text = _normal(RECORD)

    assert "Stated limits" in text
    for word in ("word list", "deny list", "PLY", "click", "FastAPI", "Helm",
                 "symbolic link under `evals/*/seed/`", "python3",
                 "The hook uses awk", "tested on the awk of macOS only",
                 "Linux awk", "encoding cookie", "utf-7", "## template: jinja"):
        assert word in text, word
    # Unit D: dropped after its own adversarial review, and where it went.
    assert "Unit D was dropped" in text
    assert "adversarial review" in text
    assert "GitHub issue #247" in text and "shell-grammar" in text
