"""Acceptance tests for richer plans (issue executable-bdd-and-richer-plans).

The technical-design template carries five optional sections - a Summary
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

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAN_TEMPLATE = ROOT / "templates" / "technical-design.md"
PLAN_SKILL = ROOT / "skills" / "plan-authoring" / "SKILL.md"
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


def test_trc_c1_template_offers_five_optional_sections():
    text = PLAN_TEMPLATE.read_text(encoding="utf-8")
    heads = "\n".join(_headings(text))

    for name, pattern in FIVE_SECTIONS.items():
        assert re.search(pattern, heads), (
            f"the plan template has no heading for the {name} section.\n"
            f"Headings found:\n{heads}"
        )

    # each of the five is marked optional in the template itself
    for name, pattern in FIVE_SECTIONS.items():
        body = _section(text, pattern)
        assert re.search(r"optional", body, re.I), (
            f"the {name} section is not marked optional; a reader would take "
            f"it as mandatory and pad every plan with it"
        )

    # the Summary comes before Approach, as it does in the spec template, so a
    # reader who has learned where to find it in one artifact finds it in both
    order = [h.lower() for h in _headings(text)]
    summary_at = next(i for i, h in enumerate(order) if "summary" in h)
    approach_at = next(i for i, h in enumerate(order) if "approach" in h)
    assert summary_at < approach_at, (
        f"Summary must precede Approach; got {order}"
    )


# ---------------------------------------------------------------------------
# `TRC-C2` - each optional section states its own inclusion rule
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,pattern", list(FIVE_SECTIONS.items()))
def test_trc_c2_each_section_states_inclusion_rule(name, pattern):
    body = _section(PLAN_TEMPLATE.read_text(encoding="utf-8"), pattern)

    # when to fill it in
    assert re.search(r"\b(include|use|reach for)\b.*\bwhen\b", body, re.I | re.S), (
        f"the {name} section never says when it should be filled in"
    )
    # and when to leave it out
    assert re.search(r"\b(omit|skip|leave (it )?out|do not (include|invoke)|none of)\b",
                     body, re.I | re.S), (
        f"the {name} section never says when to omit it - an optional section "
        f"that only says when to use it gets used every time"
    )


# ---------------------------------------------------------------------------
# `TRC-C3` - the existing sections survive unchanged
# ---------------------------------------------------------------------------

def test_trc_c3_existing_sections_survive():
    text = PLAN_TEMPLATE.read_text(encoding="utf-8")
    heads = "\n".join(_headings(text))

    for required in ["Approach", "Design decisions", "Governance check",
                     "Work units"]:
        assert re.search(re.escape(required), heads, re.I), (
            f"the pre-existing '{required}' section is gone from the template"
        )

    gate = _section(text, r"Gate")
    boxes = re.findall(r"^- \[ \] ", gate, re.M)
    assert len(boxes) >= 3, (
        f"the gate checklist lost items; expected at least its original 3, "
        f"found {len(boxes)}"
    )
    assert "distribution-map.md" in gate, "the gate no longer mentions the map"


# ---------------------------------------------------------------------------
# `TRC-C4` - the planner's section choice scales with the delivery approach
# ---------------------------------------------------------------------------

def test_trc_c4_selection_rules_scale_by_route():
    assert PLAN_SKILL.is_file(), (
        "skills/plan-authoring/SKILL.md does not exist; the selection rules "
        "have no home a human writing a plan by hand would find"
    )
    text = PLAN_SKILL.read_text(encoding="utf-8")

    express = _route_rule(text, "quick-fix")
    assert re.search(r"\b(none|no)\b", express, re.I), (
        f"the skill does not say a quick-fix plan uses none of them: {express!r}")

    standard = _route_rule(text, "regular")
    assert re.search(r"\b(clarity|clarify|helps?|add)\b", standard, re.I), (
        f"the skill does not say a feature plan uses the ones that help: "
        f"{standard!r}")

    # "full" is also a stage weight, so the rule is found by its bullet.
    expedition = next((line for line in text.splitlines() if "**full**" in line), "")
    assert re.search(r"\b(all|freely|every)\b", expedition, re.I), (
        f"the skill does not say an initiative plan may use all of them: "
        f"{expedition!r}")


def _route_rule(text, route):
    """The line in the skill that states the rule for `route`."""
    for line in text.splitlines():
        if re.search(rf"\b{route}\b", line):
            return line
    raise AssertionError(f"the skill never mentions the {route} route")


# ---------------------------------------------------------------------------
# `TRC-C5` - a named pattern must come with a stated reason
# ---------------------------------------------------------------------------

def test_trc_c5_named_pattern_requires_reason():
    body = _section(PLAN_TEMPLATE.read_text(encoding="utf-8"), r"[Pp]attern")

    assert re.search(r"\b(why|reason|earns?|justif)", body, re.I), (
        "the named-patterns section does not require a reason per pattern, so "
        "it invites pattern-name-dropping"
    )
    assert re.search(r"(cannot|can't|unable to) name|if you cannot", body, re.I), (
        "the section does not tell the author to omit it when no pattern can "
        "actually be named"
    )

    # the skill must carry the same rule, since that is where an author looks
    skill = PLAN_SKILL.read_text(encoding="utf-8")
    assert re.search(r"\b(why|reason|earns?|justif)", skill, re.I), (
        "the plan-authoring skill does not require a reason per named pattern"
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
