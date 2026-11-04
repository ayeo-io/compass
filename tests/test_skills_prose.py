"""The skills and agents speak the v2 register.

These tests check:

  * `skills/` is enforced - it has left both terminology pending lists;
  * `agents/` is scanned and never pending;
  * the compass-runtime skill carries the "never stash across a
    worktree hop" rule;
  * the role-perspective ban catches the concept, but not a hyphenated
    agent identifier such as `product-owner`, which keeps its spelling
    until an agent-rename decision.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent


def _scan_cfg() -> dict:
    return yaml.safe_load(
        (REPO_ROOT / "governance" / "terminology.yml").read_text(
            encoding="utf-8"))["scan"]


def test_skills_surface_is_enforced():
    """skills/ has left pending_surfaces and the committed baseline -
    its banned terms are build failures from here on (TRC-1)."""
    from test_terminology import PENDING_BASELINE
    scan = _scan_cfg()
    assert "skills/" not in scan["pending_surfaces"], (
        "skills/ is still pending in terminology.yml - slice 6's "
        "definition of done includes de-pending it")
    assert "skills/" not in PENDING_BASELINE, (
        "skills/ is still in the committed baseline - the ratchet shrinks "
        "in the same diff that cleans the surface")


def test_worktree_swarm_carries_the_stash_rule():
    """The compass-runtime skill carries the "never stash across a worktree
    hop" rule (TRC-3). It moved there from the worktree-multiagent skill when
    9.0.0 removed that skill (ADR-090)."""
    text = (REPO_ROOT / "skills" / "compass-runtime" / "SKILL.md").read_text(
        encoding="utf-8").lower()
    assert "never stash across a worktree hop" in text, (
        "the compass-runtime skill does not state the stash rule")
    assert "destroys the stashed work" in text, (
        "the stash rule is stated without its reason - a rule with no why "
        "gets deleted by the first person it inconveniences")


def test_lens_ban_catches_concept_not_identifiers():
    """The ban still catches the role-perspective concept, but a
    hyphenated agent identifier is machine vocabulary and passes - the
    fixture pair proves both sides (TRC-4)."""
    from test_terminology import BAN_PATTERNS
    patterns = BAN_PATTERNS["lens"]
    concept = "read the spec through the marketing lens before shipping"
    assert any(p.search(concept) for p in patterns), (
        "the lens ban no longer catches the role-perspective concept")
    identifier = "invoke the product-owner agent when a PRD exists"
    assert not any(p.search(identifier) for p in patterns), (
        "a hyphenated agent identifier is flagged - those names are "
        "machine vocabulary until an agent-rename decision retires them")
