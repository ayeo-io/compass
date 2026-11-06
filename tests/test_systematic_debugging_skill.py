"""The systematic-debugging skill (issue phase-2-skills-check-and-cli-split).

`--reassess` exists for a misjudged assessment. This skill gives the signal
to notice one: three failed fixes in a row mean the framing is wrong, not
that a fourth fix is needed.

These assertions are over prose, which is the weakest kind of scenario Compass
writes - a skill can satisfy every regex and still be useless. What they can
enforce is that the method is present, ordered, actionable, and reachable from
the place the failure actually happens.

Spec: phase-2-skills-check-and-cli-split/acceptance-criteria.md (`TRC-A1`..`A3`).
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "systematic-debugging" / "SKILL.md"


def _body(path):
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if len(parts) >= 3 else text


def test_trc_a1_the_skill_should_state_a_method_in_order():
    assert SKILL.is_file(), "skills/systematic-debugging/SKILL.md does not exist"
    body = _body(SKILL)

    phases = [
        ("root cause", r"root[- ]cause"),
        ("pattern analysis", r"pattern"),
        ("single hypothesis", r"hypothesis"),
        ("fix via a failing test", r"failing test"),
    ]
    positions = {}
    for label, pattern in phases:
        m = re.search(pattern, body, re.I)
        assert m, f"the skill never mentions {label}"
        positions[label] = m.start()

    order = [label for label, _ in phases]
    actual = sorted(order, key=lambda l: positions[l])
    assert actual == order, (
        f"the phases are out of order.\n  expected: {order}\n  found   : {actual}")

    # each phase must say what the engineer DOES, not only name itself.
    # A heading followed by nothing actionable is a list, not a method.
    for label, pattern in phases:
        idx = positions[label]
        window = body[idx:idx + 700]
        assert re.search(r"\b(read|run|write|compare|instrument|state|add|check|"
                         r"reproduce|design|watch)\b", window, re.I), (
            f"the {label} phase names itself but says nothing the engineer does")


def test_trc_a2_three_failed_fixes_should_send_the_engineer_back_to_frame():
    body = _body(SKILL)

    m = re.search(r"three", body, re.I)
    assert m, "the skill has no three-failed-fixes escape clause"
    window = body[max(0, m.start() - 400):m.start() + 900]

    assert re.search(r"stop|halt|do not", window, re.I), (
        "the escape clause does not tell the engineer to stop fixing")
    assert re.search(r"fram|architect|route", window, re.I), (
        "the escape clause does not point at the framing as the suspect")
    assert re.search(r"--reassess", body), (
        "the skill never names `/compass:assess --reassess` as the mechanism - "
        "without it the escape clause is advice with no next step")


def test_trc_a3_the_skill_should_be_reachable_from_where_the_failure_happens():
    # its own description says when it triggers
    front = SKILL.read_text(encoding="utf-8").split("---")[1]
    assert re.search(r"description:", front), "no description in the frontmatter"
    assert re.search(r"fail", front, re.I), (
        "the description does not say the skill triggers on a failure, so "
        "nothing tells a reader when to load it")

    # and the build guidance points at it, because that is where a test goes red
    pointers = [ROOT / "commands" / "go.md",
                ROOT / "skills" / "tdd-discipline" / "SKILL.md"]
    naming = [p for p in pointers
              if "systematic-debugging" in p.read_text(encoding="utf-8")]
    assert naming, (
        "neither commands/go.md nor skills/tdd-discipline names "
        "systematic-debugging. A skill nobody is told to load at the moment of "
        "failure is a file, not a method.")
