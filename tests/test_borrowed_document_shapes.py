"""The two documents the routing policy names, and the shapes they borrowed.

`governance/routing-policy.yml` promises a threat model on auth, payments or
personal-data work, and a rollback plan on migrations. Each kind needs a
template, so an issue that earns the document has something to start from.

WHY THESE SHAPES AND NOT OURS. Both are borrowed from published sources rather
than invented, and the criteria quote them so a reviewer can check the
borrowing rather than the author's taste:

  the four questions   threatmodelingmanifesto.org
  threats -> scenarios ThoughtWorks Technology Radar, "evil user stories",
                       Adopt since Nov 2015
  rehearsed, not planned  SWEBOK v4 §6.3.3 - "a planned and rehearsed rollback
                       is done before a new version ... is deployed"
  keep it short        MADR's four-heading short form; Robert C. Martin's
                       First Law of Documentation

Scenario ids trace to
adaptive-artifact-composition/acceptance-criteria.md.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))

TEMPLATES = REPO_ROOT / "templates"
THREAT = TEMPLATES / "threat-model.md"
ROLLBACK = TEMPLATES / "rollback-plan.md"

# Measured, not felt: intent.md is 106 lines and technical-design.md - the largest, carrying
# six optional sections - is 223. 120 sits above intent.md and far below the
# design: room for a worked example, not for a form.
TEMPLATE_LINE_CAP = 120

# The Manifesto's four questions, verbatim. A paraphrase changes the
# standard and loses its authority.
FOUR_QUESTIONS = [
    "What are we working on?",
    "What can go wrong?",
    "What are we going to do about it?",
    "Did we do a good enough job?",
]


def _without_comments(text):
    """The template with its instructional comments removed.

    The comment blocks quote the sources, so a whole-file search finds
    "rehearsal", "scenario" and "evidence" whatever the headings say. A
    guard that searches the instructions is checking the thing that tells
    you what to write, not the thing you write.
    """
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _headings(text):
    return [l.lstrip("#").strip()
            for l in _without_comments(text).splitlines() if l.startswith("#")]


def _read(p):
    assert p.is_file(), (
        "%s does not exist, and the routing policy names its kind - so an "
        "issue that earns it is told it owes a document with nothing to start "
        "from" % p.relative_to(REPO_ROOT))
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Group A - the threat model produces work
# ---------------------------------------------------------------------------

def test_trc_a1():
    """`TRC-A1`: the template asks the four questions and no others."""
    text = _read(THREAT)
    headings = [l.lstrip("#").strip() for l in text.splitlines()
                if l.startswith("## ")]
    asked = [h for h in headings if h.endswith("?")]
    assert asked == FOUR_QUESTIONS, (
        "the threat model's questions are not the Manifesto's four, verbatim "
        "and in order. A paraphrase is a fork of a standard with none of its "
        "authority.\n  expected: %s\n  found:    %s" % (FOUR_QUESTIONS, asked))


def test_trc_a2():
    """`TRC-A2`: a threat with no scenario is reported, not admired.

    The Manifesto's named anti-pattern is "Admiration for the Problem" - a
    document that lists threats and mitigates none. The check answers it: a
    threat row must name a scenario id or say `risk accepted` with a reason.
    """
    from compass_pkg.borrowed_docs import _check_borrowed_documents_answered

    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="compass-threat-"))
    body = ("# Threat model\n\n## What can go wrong?\n\n"
            "| Threat | What are we going to do about it? |\n|---|---|\n"
            "| A forged token is accepted | TRC-B4 |\n"
            "| The audit log fills the disk | |\n")
    (tmp / "threat-model.md").write_text(body)

    ok, detail = _check_borrowed_documents_answered({}, str(tmp))
    assert ok is False, (
        "a threat with an empty answer was not reported, so the document can "
        "list threats and mitigate none:\n" + str(detail))
    assert "audit log" in detail, (
        "the finding does not name the unanswered threat: " + detail)
    assert "forged token" not in detail, (
        "a threat that names a scenario was reported as unanswered: " + detail)

    # `risk accepted` with a reason is a decision, not a gap.
    (tmp / "threat-model.md").write_text(body.replace(
        "| The audit log fills the disk | |",
        "| The audit log fills the disk | risk accepted - rotated by the platform |"))
    ok, detail = _check_borrowed_documents_answered({}, str(tmp))
    assert ok is True, (
        "an explicitly accepted risk was reported as unanswered:\n" + str(detail))


def test_trc_a3():
    """`TRC-A3`: the fourth question is answered by evidence, not self-grading."""
    text = _read(THREAT)
    body = _without_comments(text)
    i = body.index("## Did we do a good enough job?")
    section = body[i:]
    section = section[:section.index("\n## ")] if "\n## " in section[3:] else section
    low = section.lower()
    assert "evidence" in low, (
        "the fourth section does not point at evidence, so the only answer "
        "available is the author's opinion:\n" + section[:400])
    assert "scenario" in low, (
        "the fourth section does not ask which scenarios now cover the "
        "threats:\n" + section[:400])


# ---------------------------------------------------------------------------
# Group B - the rollback plan records a rehearsal
# ---------------------------------------------------------------------------

def test_trc_b1():
    """`TRC-B1`: the template asks when the rollback was last rehearsed."""
    text = _read(ROLLBACK)
    # A HEADING, not the word somewhere. The instructional comment quotes
    # SWEBOK, so searching the whole file for "rehears" passed even when the
    # heading had been renamed away.
    rehearsal = [h for h in _headings(text) if "rehears" in h.lower()]
    assert rehearsal, (
        "the rollback template has no section about the rehearsal. SWEBOK "
        "v4 6.3.3: 'a planned and rehearsed rollback is done before a new "
        "version of the software is deployed in production.' Headings found: "
        "%s" % _headings(text))
    assert any(w in rehearsal[0].lower() for w in ("when", "last", "date")), (
        "the rehearsal heading does not ask WHEN it happened, which is the "
        "difference between a record and a wish: " + rehearsal[0])


def test_trc_b2():
    """`TRC-B2`: the evidence type demands a rehearsal, and no type is added."""
    import yaml

    g = yaml.safe_load((REPO_ROOT / "governance" / "guardrails.yml")
                       .read_text(encoding="utf-8"))
    types = g["evidence_types"]
    desc = str(types["rollback-plan"]["description"]).lower()
    assert "rehears" in desc, (
        "the `rollback-plan` evidence type still describes a PLAN, which is "
        "the assertion this change exists to reject:\n  " + desc)
    # It must not merely QUOTE the word while still describing a plan - a
    # bare substring search passes on an opening clause that describes a
    # plan again, because the SWEBOK quote after it still says "rehearsed".
    assert "a recorded plan for reverting" not in desc, (
        "the description opens by describing a plan again. The quote that "
        "follows it does not change what the type demands:\n  " + desc)

    # The frozen set is unchanged - this amends a description, it does not add
    # a ninth near-synonym beside an existing type.
    expected = {"test-run", "command-output", "manual-review", "human-approval",
                "security-review", "migration-plan", "rollback-plan",
                "claim-review", "spike-conclusion", "consistency-check",
                "artifact",
                # 7.0.0 adds a person's approval of a document or a decision set (ADR-050).
                "artifact-approval"}
    assert set(types) == expected, (
        "the evidence type list changed. Adding a type is a decision (7.0.0 added "
        "artifact-approval, ADR-050); declare it in `expected` above:\n  added: %s\n  removed: %s"
        % (sorted(set(types) - expected), sorted(expected - set(types))))


def test_trc_b3():
    """`TRC-B3`: a rollback plan with no rehearsal is caught; neither file
    present reports nothing to check, not a pass."""
    from compass_pkg.check_results import NOTHING_TO_CHECK
    from compass_pkg.borrowed_docs import _check_borrowed_documents_answered

    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="compass-rollback-"))

    # Neither document. Most issues earn neither, and a guard that reports a
    # clean result for work it never looked at is the failure this repository
    # keeps finding.
    ok, detail = _check_borrowed_documents_answered({}, str(tmp))
    assert ok is NOTHING_TO_CHECK, (
        "an issue with neither document reported a real pass:\n" + str(detail))

    (tmp / "rollback-plan.md").write_text(
        "# Rollback plan\n\n## What breaks\n\nThe migration.\n\n"
        "## How we go back\n\n`make db-rollback`\n\n"
        "## When this was last rehearsed\n\nNot yet.\n")
    ok, detail = _check_borrowed_documents_answered({}, str(tmp))
    assert ok is False, (
        "a rollback plan recording no rehearsal was accepted:\n" + str(detail))
    assert "rollback-plan.md" in detail, (
        "the finding does not name the file: " + detail)

    (tmp / "rollback-plan.md").write_text(
        "# Rollback plan\n\n## What breaks\n\nThe migration.\n\n"
        "## How we go back\n\n`make db-rollback`\n\n"
        "## When this was last rehearsed\n\n"
        "2026-08-24, against a copy of production taken that morning. "
        "Restored in 4m12s; row counts matched.\n")
    ok, detail = _check_borrowed_documents_answered({}, str(tmp))
    assert ok is True, (
        "a rollback plan recording a real rehearsal was reported:\n" + str(detail))


# ---------------------------------------------------------------------------
# Group C - cross-cutting concerns are a design section
# ---------------------------------------------------------------------------

def _optional_sections(text):
    """Headings marked OPTIONAL in the design template."""
    out = []
    lines = text.splitlines()
    for i, l in enumerate(lines):
        if l.startswith("## "):
            window = "\n".join(lines[i + 1:i + 4])
            if "OPTIONAL" in window:
                out.append(l.lstrip("#").strip())
    return out


def test_trc_c1():
    """`TRC-C1`: the design template offers a cross-cutting concerns section."""
    text = (TEMPLATES / "technical-design.md").read_text(encoding="utf-8")
    names = _optional_sections(text)
    match = [n for n in names if "cross-cutting" in n.lower()]
    assert match, (
        "the design template has no cross-cutting concerns section. Design "
        "Docs at Google names security, privacy and observability as exactly "
        "that - sections of the design, not separate documents. Optional "
        "sections found: %s" % names)

    # The whole section, not a fixed window. A fixed-length window can stop
    # short of "observability" and report it missing when it is there - a
    # guard failing on its own arbitrary constant rather than on the code.
    i = text.index("## " + match[0])
    rest = text[i + 3:]
    end = rest.index("\n## ") if "\n## " in rest else len(rest)
    body = text[i:i + 3 + end].lower()
    for word in ("security", "observability"):
        assert word in body, (
            "the section does not name %r among the concerns it covers" % word)
    assert "include when" in body or "earns" in body, (
        "the section carries no rule for when it earns a place, which every "
        "other optional section does")
    assert "delete" in body or "omit" in body, (
        "the section does not say to delete it when unused - the template's "
        "own rule is that an empty optional section is worse than an absent one")


def test_trc_c2():
    """`TRC-C2`: the skill governing the optional sections knows about it.

    Asserts the set is NON-EMPTY and the expected size before comparing. Two
    empty sets are equal, and this repository has already shipped one guard
    that passed for exactly that reason.
    """
    template = (TEMPLATES / "technical-design.md").read_text(encoding="utf-8")
    skill = (REPO_ROOT / "skills" / "plan-authoring" / "SKILL.md").read_text(
        encoding="utf-8")

    names = _optional_sections(template)
    assert len(names) == 6, (
        "expected six optional sections in the design template, found %d: %s"
        % (len(names), names))

    missing = [n for n in names
               if n.split(" - ")[0].split(".")[-1].strip().lower()
               not in skill.lower()]
    assert not missing, (
        "the plan-authoring skill does not mention these optional sections, so "
        "the template offers something the skill does not govern - which is "
        "how an optional section becomes decoration:\n  "
        + "\n  ".join(missing))
    assert "five optional sections" not in skill.lower(), (
        "the skill still says FIVE optional sections while the template offers "
        "six - a count one contradicts the other on")


# ---------------------------------------------------------------------------
# Group D - the promise the policy already makes
# ---------------------------------------------------------------------------

def _policy_artifact_kinds():
    """Every artifact kind the routing policy names, found by walking it all.

    RECURSIVE ON PURPOSE. A fixed path such as `rules.floors_and_requirements`
    does not exist - the policy has no top-level `rules` key, and the
    artifact-adding rules live under `routing_guardrails.floors` - so a
    reader pinned to one path would report zero missing templates while some
    are missing. A scan that finds nothing must fail, not pass.
    """
    import yaml

    policy = yaml.safe_load((REPO_ROOT / "governance" / "routing-policy.yml")
                            .read_text(encoding="utf-8"))
    kinds, where = set(), {}

    def walk(node, trail):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("add_artifact", "require_artifact") and isinstance(v, str):
                    kind = v[:-3] if v.endswith(".md") else v
                    kinds.add(kind)
                    where.setdefault(kind, node.get("id") or " / ".join(trail))
                walk(v, trail + [str(k)])
        elif isinstance(node, list):
            for x in node:
                walk(x, trail)

    walk(policy, [])
    shape_kinds = set()
    for name, shape in (policy.get("route_shapes") or {}).items():
        for kind in (shape.get("artifacts") or {}):
            shape_kinds.add(kind)
            where.setdefault(kind, "the %s shape" % name)
    return kinds | shape_kinds, shape_kinds, where


def test_trc_d1():
    """`TRC-D1`: every kind the policy names has a template."""
    kinds, shape_kinds, where = _policy_artifact_kinds()

    assert shape_kinds, (
        "the scan found no artifact kinds on any shape, so it is reading the "
        "policy wrongly and would report a clean result whatever was missing")
    assert kinds >= shape_kinds, "the walk lost kinds the shapes declare"
    assert len(kinds) >= 8, (
        "the scan found only %d kinds (%s), which is fewer than the shapes and "
        "rules declare between them - it is not reading the whole policy"
        % (len(kinds), sorted(kinds)))

    missing = ["%s (named by %s)" % (k, where.get(k, "?"))
               for k in sorted(kinds)
               if not (TEMPLATES / ("%s.md" % k)).is_file()]
    assert not missing, (
        "the routing policy names these document kinds and no template exists, "
        "so an issue that earns one is told it owes a document with nothing to "
        "start from:\n  " + "\n  ".join(missing))


def test_trc_d3():
    """`TRC-D3`: both templates stay shorter than intent.md."""
    # THE CAP MUST BE ABLE TO FAIL. A budget so high nothing can exceed it
    # proves nothing, which is the shape this repository keeps finding.
    # Bounding it against the framework's own largest template makes an
    # over-wide cap fail here.
    design_lines = len((TEMPLATES / "technical-design.md").read_text(
        encoding="utf-8").splitlines())
    assert TEMPLATE_LINE_CAP < design_lines, (
        "the cap (%d) is not below technical-design.md (%d lines), so a borrowed "
        "four-heading document may be longer than the framework's own largest "
        "template and still pass" % (TEMPLATE_LINE_CAP, design_lines))
    over = []
    for p in (THREAT, ROLLBACK):
        n = len(_read(p).splitlines())
        if n > TEMPLATE_LINE_CAP:
            over.append("%s: %d lines" % (p.name, n))
    assert not over, (
        "these templates exceed the %d-line cap. Every source behind them "
        "argues for concision - MADR's four headings, Martin's First Law, "
        "Design Docs at Google on 1-3 page mini docs - and a template longer "
        "than this framework's own PRD has not borrowed it:\n  %s"
        % (TEMPLATE_LINE_CAP, "\n  ".join(over)))
