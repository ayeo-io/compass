"""The `atdd` skill teaches the example-first refinement chain (TRC-D1).
User stories remain refused as a per-role spec format (TRC-D2).

`bdd-specification` merged into `atdd` in 9.0.0 (#360): the chain is in
`skills/atdd/references/refinement-chain.md`, which `SKILL.md` names.

Serves: INT-8 (D1), INT-8+INT-11 (D2)
Spec:
  - skills/atdd/SKILL.md and its references must have a refinement-chain section
  - the chain: vague idea → concrete examples → acceptance criteria → at least one executable specification each
  - recommends specs that start with "should" and a ubiquitous language
  - must refuse user stories as a per-role spec format (TRC-D2)
  - ADR-004 reference: the shared artifact stays as BDD scenario in acceptance-criteria.md
"""
from __future__ import annotations
from pathlib import Path

SKILL_MD = Path(__file__).parent.parent / "skills" / "atdd" / "SKILL.md"

def _skill_text(skill_name):
    """Reads every file in the skill's directory and its `references/`. Long
    skills are split into parts that load on demand, so a guard that reads
    only SKILL.md reports moved content as missing."""
    import pathlib as _p
    d = _p.Path(__file__).parent.parent / "skills" / skill_name
    return "\n".join(sorted(
        p.read_text(encoding="utf-8")
        for p in [*d.glob("*.md"), *d.glob("references/*.md")]))



def test_skill_names_the_refinement_chain_file():
    """The chain is in a reference, so SKILL.md must name it or a session
    never reads it."""
    assert "references/refinement-chain.md" in SKILL_MD.read_text(encoding="utf-8")


def _read_skill() -> str:
    return _skill_text("atdd")


# --- `TRC-D1` tests ---

def test_bdd_spec_has_refinement_chain_section():
    """Must have a refinement-chain section (example-first)."""
    text = _read_skill()
    text_lower = text.lower()
    assert "refinement" in text_lower or "example-first" in text_lower or "refine" in text_lower, (
        "skills/atdd/ must contain an example-first refinement chain section. "
        f"Headings: {[l for l in text.splitlines() if l.startswith('#')]}"
    )


def test_refinement_chain_covers_vague_to_concrete():
    """The chain must go from vague idea → concrete examples."""
    text = _read_skill()
    text_lower = text.lower()
    assert "vague" in text_lower or "concrete examples" in text_lower, (
        "The refinement chain must describe moving from a vague idea to concrete examples."
    )


def test_refinement_chain_covers_examples_to_acceptance_criteria():
    """The chain must include acceptance criteria step."""
    text = _read_skill()
    text_lower = text.lower()
    assert "acceptance criteria" in text_lower or "acceptance criterion" in text_lower, (
        "The refinement chain must include an acceptance criteria step."
    )


def test_refinement_chain_covers_executable_spec():
    """The chain must lead to at least one executable specification."""
    text = _read_skill()
    text_lower = text.lower()
    assert "executable" in text_lower or "runnable" in text_lower, (
        "The refinement chain must mention executable specifications."
    )


def test_bdd_spec_recommends_should_prefix():
    """The section must recommend specs starting with 'should'."""
    text = _read_skill()
    text_lower = text.lower()
    assert '"should"' in text_lower or "'should'" in text_lower or "start with" in text_lower or "prefix" in text_lower, (
        "The atdd skill should recommend using 'should' as a scenario prefix/convention. "
        "Look for mentions of 'should' as a naming convention."
    )


def test_bdd_spec_mentions_ubiquitous_language():
    """The section must recommend a ubiquitous language used consistently."""
    text = _read_skill()
    text_lower = text.lower()
    assert "ubiquitous" in text_lower or "ubiquitous language" in text_lower, (
        "The atdd skill should mention ubiquitous language as a discipline."
    )


# --- `TRC-D2` tests ---

def test_bdd_spec_refuses_user_stories_as_spec_format():
    """User stories must be refused as a per-role spec format."""
    text = _read_skill()
    text_lower = text.lower()
    assert "user stor" in text_lower, (
        "skills/atdd/ must mention user stories (to refuse them as a per-role spec format). "
        "The refusal should be explicit."
    )
    # The skill must contain a refusal - words like "refused", "not", "reject"
    # near "user stories"
    lines = text.splitlines()
    user_story_context = []
    for i, line in enumerate(lines):
        if "user stor" in line.lower():
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            user_story_context.extend(lines[start:end])

    context_lower = " ".join(user_story_context).lower()
    assert any(word in context_lower for word in ["refus", "not a", "stays", "remain", "adr-004", "reject"]), (
        "The mention of user stories in skills/atdd/ must be in the context of refusing them. "
        f"Context found: {user_story_context}"
    )


def test_bdd_spec_shared_artifact_stays_bdd():
    """The acceptance-criteria.md artifact must remain the shared BDD
    artifact."""
    text = _read_skill()
    text_lower = text.lower()
    assert "acceptance-criteria.md" in text_lower, (
        "skills/atdd/ must confirm acceptance-criteria.md stays as the shared BDD artifact."
    )
