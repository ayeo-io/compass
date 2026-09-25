"""The multiagent protocol is one document a fresh session can follow, and
run 1 of it is on record.

`docs/multiagent-protocol.md` answers each step of a multiagent run: what the
orchestrator writes, what a builder may touch, the order of integration, what
happens on a conflict, and what the manifest records. The skill and the
orchestrator agent point to it first, and ADR-025 records why the printed
plan plus the recorded run is the interface.

Scenario ids: DPR-5 and DPR-6, in `acceptance-criteria.md` of issue
`dispatch-protocol`.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL = ROOT / "docs" / "multiagent-protocol.md"


def _flat(path):
    return " ".join(path.read_text(encoding="utf-8").split())


def _headings(path):
    return [line.lstrip("#").strip().lower()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")]


def _first_paragraph(path):
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    body = [b for b in re.split(r"\n\s*\n", text) if b.strip()
            and not b.lstrip().startswith("#")]
    return " ".join(body[0].split())


def test_dpr_5_the_protocol_has_a_section_for_every_step():
    headings = " | ".join(_headings(PROTOCOL))
    for needed in ("interface", "write each brief", "launch the builders",
                   "take the result", "review", "integrate",
                   "when a merge conflicts", "what the manifest records",
                   "issues this protocol closes"):
        assert needed in headings, (needed, headings)


def test_dpr_5_the_protocol_answers_the_rehearsal_gaps():
    text = _flat(PROTOCOL)
    # The builder's CLI is named as a full path, not a bare `compass`.
    assert "full path" in text and "bin/compass" in text
    # A result reaches the main checkout by a stated command, and is never
    # committed, so it cannot merge into the codebase.
    assert "cp <worktree>/result.md" in text
    assert "not** committed" in text
    # Conflicts confined to Compass's records do not stop integration.
    assert "keeps the base branch's copy" in text
    # Review frequency follows the risk.
    for risk in ("critical", "cross-cutting", "contained"):
        assert risk in text


def test_dpr_5_every_command_it_gives_runs_as_written():
    text = _flat(PROTOCOL)
    # Registering a document needs a status.
    assert "compass issue artifact <kind> --status draft --path <path>" in text
    # A repeated --finding keeps only the last, so each gets its own call.
    assert "one call per finding" in text
    # Only --attempt counts a try.
    assert "--brief <new brief> --attempt" in text
    # A brief is handed by its absolute path.
    assert "absolute" in text


def test_dpr_5_it_states_the_order_of_waves_and_a_failed_regression():
    headings = " | ".join(_headings(PROTOCOL))
    assert "the order of a run" in headings
    text = _flat(PROTOCOL).lower()
    assert "only after the wave before it has integrated" in text
    assert "the combined regression fails" in text
    assert "does not mark the issue landed" in text


def test_dpr_5_every_queued_multiagent_issue_has_a_fate():
    text = _flat(PROTOCOL)
    for slug in ("swarm-dispatch-is-a-protocol-not-a-script",
                 "multiagent-does-not-ask-where-documents-live",
                 "multiagent-cannot-stage-a-map-in-waves"):
        assert slug in text, slug


def test_dpr_5_the_skill_and_the_orchestrator_point_to_it_first():
    for path in (ROOT / "skills" / "worktree-multiagent" / "SKILL.md",
                 ROOT / "agents" / "orchestrator.md"):
        assert "docs/multiagent-protocol.md" in _first_paragraph(path), path


def test_dpr_5_an_adr_records_the_interface():
    adrs = list((ROOT / "architecture" / "decisions").glob("ADR-025-*.md"))
    assert len(adrs) == 1
    text = _flat(adrs[0]).lower()
    assert "status: accepted" in text
    assert "the printed plan and the recorded run are the interface" in text


def test_dpr_6_run_1_is_recorded_with_its_cost():
    runs = list((ROOT / "docs" / "compass").glob("*-dispatch-protocol-run-1.md"))
    assert len(runs) == 1, runs
    text = _flat(runs[0]).lower()
    for needed in ("wall-clock", "tokens", "conflicts", "rework", "improvis"):
        assert needed in text, needed
    # A published record carries no unfilled placeholder.
    raw = runs[0].read_text(encoding="utf-8")
    for placeholder in ("END_TIME", "FINAL_RESULT", "{{", "TODO", "TBD"):
        assert placeholder not in raw, placeholder
