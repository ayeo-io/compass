"""Acceptance tests for richer plans (issue executable-bdd-and-richer-plans).

The technical-design template carried five optional sections - a Summary
preamble, a sequence diagram, a structural diagram, named design patterns,
and illustrative code - each with its own rule for when it earns a place,
governed by a new `plan-authoring` skill.

The sections are OPTIONAL by design. A plan that uses all five on a one-line
change is worse than one that uses none: process weight is a cost. So these
tests check two things in tension - that the sections exist and are usable,
and that the template and skill tell an author when NOT to use them.

Every assertion below reads a shipped file. The precedent is
tests/test_plugin_doc_drift.py and tests/test_readable_specs_and_flow.py.

Spec: executable-bdd-and-richer-plans/acceptance-criteria.md (`TRC-C1`..`TRC-C6`).
"""

# These tests assert the current names (technical-design.md, intent.md).
# Older manifests and documents still load (ADR-006).
from __future__ import annotations

import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent.parent
# The plan-authoring skill went with the plan stage (ADR-092). Its rules moved
# to the governance-check skill, "Writing the design down", which keeps them in
# a file beside SKILL.md so the skill stays under its line ceiling.
PLAN_SKILL = ROOT / "skills" / "governance-check" / "writing-the-design.md"
WRITING_GUIDE = ROOT / "docs" / "writing-specs-and-plans.md"


def _headings(text):
    """All markdown headings, in document order."""
    return [m.group(0) for m in re.finditer(r"^#{1,4} .+$", text, re.M)]


def _section(text, pattern):
    """The body of the first heading matching `pattern`, up to the next heading
    of the same or higher level."""
    m = re.search(rf"^(#{{1,4}}) .*{pattern}.*$", text, re.M | re.I)
    assert m, f"no heading matching {pattern!r}"
    level = len(m.group(1))
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


# ---------------------------------------------------------------------------
# `TRC-C1` - the template offers the five optional sections
# ---------------------------------------------------------------------------

FIVE_SECTIONS = {
    "summary": r"Summary",
    "sequence diagram": r"[Ss]equence",
    "structural diagram": r"[Ss]tructur",
    "named patterns": r"[Pp]attern",
    "illustrative code": r"([Cc]ode|[Ss]hape)",
}


# `TRC-C1` to `TRC-C3` read the technical-design template, which 9.0.0
# deleted (ADR-091). The plan-authoring skill and the writing guide keep the
# five sections.


# ---------------------------------------------------------------------------
# `TRC-C4` - the planner's section choice scales with the delivery approach
# ---------------------------------------------------------------------------

def test_trc_c4_selection_rules_scale_by_route():
    assert PLAN_SKILL.is_file(), (
        "skills/governance-check/writing-the-design.md does not exist; the selection rules "
        "have no home a human writing a design by hand would find"
    )
    text = PLAN_SKILL.read_text(encoding="utf-8")

    # The path has no approaches (ADR-092): the rule scales with the evidence
    # row the issue owes instead of the 8.x quick fix, regular and full.
    express = _route_rule(text, "**The light row**")
    assert re.search(r"\b(none|no)\b", express, re.I), (
        f"the skill does not say a light-row change uses none of them: {express!r}")

    standard = _route_rule(text, "**The standard row**")
    assert re.search(r"\b(clarity|clarify|helps?|add)\b", standard, re.I), (
        f"the skill does not say a standard-row design uses the ones that help: "
        f"{standard!r}")

    expedition = _route_rule(text, "owes `architecture`**")
    assert re.search(r"\b(all|freely|every)\b", expedition, re.I), (
        f"the skill does not say a design that owes architecture may use all "
        f"of them: {expedition!r}")


def _route_rule(text, marker):
    """The line in the skill that states the rule for the bullet `marker`."""
    for line in text.splitlines():
        if marker in line:
            return line
    raise AssertionError(f"the skill never states the rule for {marker!r}")


# ---------------------------------------------------------------------------
# `TRC-C5` - a named pattern must come with a stated reason
# ---------------------------------------------------------------------------

def test_trc_c5_named_pattern_requires_reason():
    # The skill carries the rule, since that is where an author looks.
    skill = PLAN_SKILL.read_text(encoding="utf-8")
    assert re.search(r"\b(why|reason|earns?|justif)", skill, re.I), (
        "the governance-check skill does not require a reason per named pattern"
    )


# ---------------------------------------------------------------------------
# `TRC-C6` - the writing guide carries a worked plan
# ---------------------------------------------------------------------------

def test_trc_c6_writing_guide_has_worked_plan():
    text = WRITING_GUIDE.read_text(encoding="utf-8")

    worked = _section(text, r"worked plan")
    for name, pattern in FIVE_SECTIONS.items():
        assert re.search(pattern, worked), (
            f"the worked plan does not show the {name} section rendered"
        )

    # the diagrams in it are Mermaid
    assert "```mermaid" in worked, "the worked plan has no Mermaid diagram"
    assert re.search(r"sequenceDiagram", worked), (
        "the worked plan has no sequence diagram")
    assert re.search(r"(classDiagram|flowchart|graph )", worked), (
        "the worked plan has no structural diagram")

    # and PlantUML is documented as the fallback, not the default
    assert re.search(r"PlantUML", text), (
        "the guide never mentions PlantUML, so an author meeting a diagram "
        "Mermaid cannot express has nowhere to go"
    )
    plantuml_line = next(l for l in text.splitlines() if "PlantUML" in l)
    assert re.search(r"(fallback|cannot|can't|only when|reach for)", text, re.I), (
        f"PlantUML is not positioned as the exception: {plantuml_line!r}"
    )
