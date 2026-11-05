"""Reshaping an ingested brief into intent.md - the rules, made checkable.

The maintainer's instruction was "never take it verbatim, ask questions where
needed", so Compass rewrites someone else's document. That is the whole value
and the whole danger: an invented non-goal reads exactly like a decided one,
and a reader cannot tell them apart afterwards.

The rule: **every statement in intent.md traces to the source or to a
recorded answer, and there is no third origin** - and this file is where it
is held. The skill teaches the discipline; the check below is what makes the
discipline checkable rather than aspirational.

Scenario ids: ING-B1..B4 in
ingest-an-existing-brief/acceptance-criteria.md
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "cli"))

import compass_pkg  # noqa: E402,F401
from compass_pkg.core import CompassError  # noqa: E402

SKILL = REPO_ROOT / "skills" / "intent-interview" / "SKILL.md"


def _issue(tmp_path, sections, elicitation, intent_body, source="# src\n\nA.\n"):
    """An issue that has been ingested and reshaped, ready to validate."""
    work = tmp_path / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (tmp_path / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (work / "intent-source.md").write_text(source, encoding="utf-8")
    (work / "intent.md").write_text(intent_body, encoding="utf-8")
    (work / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "demo", "created": "2026-08-25",
        "status": "active",
        "intent_source": {
            "origin": "brief.md", "scheme": "file", "sha256": "0" * 64,
            "ingested_at": "2026-08-25T00:00:00+00:00",
            "snapshot": "intent-source.md",
            "sections": sections,
            "elicitation": elicitation,
        },
    }, sort_keys=False))
    return work


# ---------------------------------------------------------------------------
# ING-B3 - nothing is invented. The rule, held mechanically.
# ---------------------------------------------------------------------------

def test_ing_b3_a_section_with_no_recorded_origin_is_refused(tmp_path):
    """The rule's whole point: a statement nobody made must not pass.

    This is the failure the rule exists for - a plausible non-goal, written
    because it sounded right. It reads exactly like a decided one, so nothing
    but a recorded origin can tell them apart.
    """
    from compass_pkg.ingest import validate_intent_origins

    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"}],
        elicitation=[],
        intent_body="## Problem\n\nSearch is slow.\n\n"
                    "## Non-goals\n\nWe will not rebuild the index.\n")

    ok, detail = validate_intent_origins(str(work))
    assert not ok, "a section with no recorded origin was accepted"
    assert "non-goals" in detail.lower(), detail


def test_ing_b3b_an_answer_origin_must_name_an_answer_that_exists(tmp_path):
    """`from: answer` pointing at nothing is the same failure in another form.

    Without this, the origin record becomes a formality: write `from: answer`
    beside anything and the check clears. A citation is only as good as the
    thing it points at - the same rule the archive-citation guard holds.
    """
    from compass_pkg.ingest import validate_intent_origins

    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"},
                  {"name": "non-goals", "from": "answer", "answer_id": "Q9"}],
        elicitation=[{"id": "Q1", "question": "what is out?", "answer": "the index"}],
        intent_body="## Problem\n\nA.\n\n## Non-goals\n\nNot the index.\n")

    ok, detail = validate_intent_origins(str(work))
    assert not ok
    assert "Q9" in detail, detail


def test_ing_b3c_a_declined_question_may_not_be_cited_as_an_answer(tmp_path):
    """An unanswered question is not a source of material.

    The sharpest version of the rule. The question was asked, the person
    declined - and material appearing under that section anyway is invention
    with a record, which is worse than invention without one because it
    looks audited.
    """
    from compass_pkg.ingest import validate_intent_origins

    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"},
                  {"name": "non-goals", "from": "answer", "answer_id": "Q1"}],
        elicitation=[{"id": "Q1", "question": "what is out?", "answer": None}],
        intent_body="## Problem\n\nA.\n\n## Non-goals\n\nNot the index.\n")

    ok, detail = validate_intent_origins(str(work))
    assert not ok
    assert "declin" in detail.lower() or "unanswered" in detail.lower(), detail


def test_ing_b3d_a_fully_traced_document_passes(tmp_path):
    """The control. Without it, a check that refused everything would pass
    all three tests above while making the feature unusable."""
    from compass_pkg.ingest import validate_intent_origins

    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"},
                  {"name": "non-goals", "from": "answer", "answer_id": "Q1"}],
        elicitation=[{"id": "Q1", "question": "what is out?",
                      "answer": "rebuilding the index"}],
        intent_body="## Problem\n\nSearch is slow.\n\n"
                    "## Non-goals\n\nRebuilding the index.\n")

    ok, detail = validate_intent_origins(str(work))
    assert ok, detail


# ---------------------------------------------------------------------------
# ING-B4 - declining every question still produces a document
# ---------------------------------------------------------------------------

def test_ing_b4_a_declined_section_says_so_and_the_document_stands(tmp_path):
    """Declining every question must still produce a document.

    Someone in a hurry, or without the answers to hand, still needs to start.
    A section they declined is recorded as unanswered and says so in words -
    which is a finished document, not an unfinished one.
    """
    from compass_pkg.ingest import validate_intent_origins

    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"},
                  {"name": "non-goals", "from": "unanswered", "answer_id": "Q1"}],
        elicitation=[{"id": "Q1", "question": "what is out?", "answer": None}],
        intent_body="## Problem\n\nSearch is slow.\n\n## Non-goals\n\n"
                    "No non-goals were stated in the source, and none were "
                    "supplied when asked.\n")

    ok, detail = validate_intent_origins(str(work))
    assert ok, detail


def test_ing_b4b_an_unanswered_section_may_not_hide_behind_tbd(tmp_path):
    """`TBD` and "asked, declined" are different states.

    `TBD` reads as "someone will get to this": an unfinished placeholder. A section that was asked about and
    deliberately left open is finished - and only one of the two is true.
    """
    from compass_pkg.ingest import validate_intent_origins

    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"},
                  {"name": "non-goals", "from": "unanswered", "answer_id": "Q1"}],
        elicitation=[{"id": "Q1", "question": "what is out?", "answer": None}],
        intent_body="## Problem\n\nA.\n\n## Non-goals\n\nTBD\n")

    ok, detail = validate_intent_origins(str(work))
    assert not ok
    assert "tbd" in detail.lower(), detail


def test_ing_b1_the_document_is_reshaped_not_copied(tmp_path):
    """ING-B1: intent.md must not be the snapshot under another name.

    The cheapest way to satisfy every other rule here is to copy the source
    verbatim - every statement traces, trivially. That is exactly what the
    maintainer ruled out, so it is refused.
    """
    from compass_pkg.ingest import validate_intent_origins

    body = "## Problem\n\nSearch is slow.\n"
    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"}],
        elicitation=[],
        intent_body=body,
        source=body)

    ok, detail = validate_intent_origins(str(work))
    assert not ok, "intent.md is byte-identical to the source and was accepted"
    assert "identical" in detail.lower() or "verbatim" in detail.lower(), detail


def test_ing_b2_the_skill_requires_asking_rather_than_writing_tbd():
    """ING-B2: the discipline itself, which no validator can hold.

    A validator can refuse `TBD`. It cannot make anyone ASK - so that half
    lives in the skill, and this checks the skill says it. Weak evidence, and
    named as such: prose can satisfy a regex and still teach nothing.
    """
    assert SKILL.is_file(), "no intent-interview skill"
    text = SKILL.read_text(encoding="utf-8").lower()

    for needle, why in (
            ("one question at a time", "the questioning discipline P0-C specifies"),
            ("tbd", "the rule against writing TBD instead of asking"),
            ("decline", "the person's right to decline every question"),
            ("invent", "the rule that nothing is invented")):
        assert needle in text, (
            "the skill does not mention %s (%s)" % (needle, why))


def test_ing_b2b_the_skill_steps_aside_when_intake_already_exists():
    """The interview loop must not annoy an experienced user who arrives
    with a finished intent.md: it must step aside instantly when intake
    already exists. A loop that interrogates someone who already has a
    complete document is the failure mode, not a thorough one.
    """
    text = SKILL.read_text(encoding="utf-8").lower()
    assert "step aside" in text or "steps aside" in text, (
        "the skill does not say it steps aside when the source already "
        "carries what the template asks for")


# ---------------------------------------------------------------------------
# ING-C2 - the reshaping is auditable
# ---------------------------------------------------------------------------

def test_ing_c2_the_record_shows_which_parts_came_from_the_conversation(tmp_path):
    """ING-C2: a reader can tell source material from answered material.

    Because the content was rewritten, the source's hash no longer proves
    anything about the output. What makes a reshaped document trustworthy is
    the record of what was asked and what was answered - so the record has to
    be readable as an answer to "where did this sentence come from?", not just
    present.
    """
    from compass_pkg.ingest import describe_intent_origins

    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"},
                  {"name": "non-goals", "from": "answer", "answer_id": "Q1"},
                  {"name": "success signals", "from": "unanswered",
                   "answer_id": "Q2"}],
        elicitation=[{"id": "Q1", "question": "What is deliberately out?",
                      "answer": "Rebuilding the index."},
                     {"id": "Q2", "question": "How will you know it worked?",
                      "answer": None}],
        intent_body="## Problem\n\nSearch is slow.\n\n## Non-goals\n\n"
                    "Rebuilding the index.\n\n## Success signals\n\n"
                    "Asked, and not supplied.\n")

    report = describe_intent_origins(str(work))

    assert "problem" in report and "the source" in report
    assert "Q1" in report and "What is deliberately out?" in report, (
        "the question that produced a section is not in the report, so a "
        "reader cannot see where the material came from:\n" + report)
    assert "Rebuilding the index." in report, (
        "the ANSWER is not in the report - the question alone does not show "
        "what was contributed:\n" + report)
    assert "Q2" in report and "not supplied" in report.lower(), (
        "a declined question is missing, so the report reads as though it was "
        "never asked:\n" + report)


def test_ing_c2b_the_report_says_when_there_is_nothing_to_audit(tmp_path):
    """An authored intent.md is not a failure, and must not read as one.

    Most issues have no ingested brief at all. A report that renders an empty
    table for them trains a reader to skip it.
    """
    from compass_pkg.ingest import describe_intent_origins

    work = tmp_path / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(
        'schema_version: "2.0"\ntask: demo\ncreated: "2026-08-25"\n')
    (work / "intent.md").write_text("## Problem\n\nWritten here.\n")

    report = describe_intent_origins(str(work))
    assert "authored" in report.lower(), report
    assert "|" not in report, "an empty audit table was rendered anyway"


def test_ing_e1_the_report_never_claims_compass_supplied_material_is_vouched(tmp_path):
    """ING-E1: the gate reports origin, and cannot report a pass on invention.

    The structural guarantee, asserted rather than trusted: `ORIGINS` has no
    value meaning "Compass wrote it", so there is no state the report could
    describe as vouched-for-but-unsourced. If a later change adds one, this
    fails - which is the point, because that change is exactly the one that
    would quietly undo ING-B3.
    """
    from compass_pkg.ingest import ORIGINS

    assert set(ORIGINS) == {"source", "answer", "unanswered"}, (
        "the set of origins changed. Every one must be a HUMAN origin - if a "
        "value meaning 'Compass wrote it' has been added, the invention rule "
        "no longer holds and the fidelity gate would be vouching for material "
        "nobody supplied. Got: %s" % (ORIGINS,))


def test_ing_c2c_an_answered_question_no_section_uses_is_surfaced(tmp_path):
    """A contribution that did not reach the document must be visible.

    The quiet loss: someone was asked, they answered, and the answer never
    landed in a section. Reporting only that the question was asked hides what
    went missing - and the person who gave it will assume it is in there.
    """
    from compass_pkg.ingest import describe_intent_origins

    work = _issue(
        tmp_path,
        sections=[{"name": "problem", "from": "source"}],
        elicitation=[{"id": "Q7", "question": "Which slice ships first?",
                      "answer": "Latency only."}],
        intent_body="## Problem\n\nSearch is slow.\n")

    report = describe_intent_origins(str(work))
    assert "Q7" in report and "Latency only." in report, (
        "an answered question that no section uses is not surfaced with its "
        "answer, so the reader cannot see what was lost:\n" + report)
