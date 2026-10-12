#!/usr/bin/env python3
# =============================================================================
# compass - the two borrowed document shapes
# =============================================================================
# `threat-model.md` and `rollback-plan.md`, and the one check that reads them.
#
# Neither shape is ours. The threat model asks the Threat Modeling Manifesto's
# four questions (threatmodelingmanifesto.org) and answers each threat with a
# scenario id, which is the output form the ThoughtWorks Technology Radar names
# - "evil user stories" - and has had in Adopt since Nov 2015. The rollback
# plan records a REHEARSAL rather than a plan: SWEBOK v4 §6.3.3 needs "a
# planned and rehearsed rollback" before a deploy. Dave Farley's answer to
# rollback is a mechanism you exercise rather than a document you write.
#
# It lives here rather than in checks.py because it reads those two templates
# and nothing else in checks.py touches them - the same reason `render_check.py`
# holds the check that the rendered blocks are current.
#
# DEPENDENCY: the resolver in compass_pkg.core, plus os and re from the
# standard library. It asks the resolver where each document is rather than
# joining a filename to the issue directory, because both may live under
# `docs/compass/<created>-<slug>/`. The YAML parser the rest of the package
# uses travels inside the plugin, so there is nothing to install either way.
# =============================================================================
"""Reading the threat model and the rollback plan for what each is for."""
from __future__ import annotations

import os
import re

from compass_pkg.check_results import NOTHING_TO_CHECK
from compass_pkg.core import artifact_path

# The shape the two borrowed templates write, and what "answered" means in
# each. A scenario id or an explicit accepted risk answers a threat; a
# rehearsal that happened answers a rollback.
_TRC_ID = re.compile(r"\bTRC-[A-Za-z0-9-]+\b")
_RISK_ACCEPTED = re.compile(r"risk\s+accepted", re.IGNORECASE)
#: A date in the section. The template asks for "a date, a target, an outcome,
#: a duration", and the date is the part that separates a record from an
#: intention: "we rehearsed it" with no date is a claim.
_REHEARSAL_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

#: A section that OPENS by denying the rehearsal. Read the opening statement
#: only. A section that records a real rehearsal uses these words in other
#: roles, such as a column headed "Planned", or a count of "none". Failing on
#: those teaches the author to reword around the guard.
_DENIES_REHEARSAL = re.compile(
    r"\b(not\s+yet|never\s+rehearsed|no\s+rehearsal|tbd|todo|n/?a|pending)\b",
    re.IGNORECASE)


def _opening_claim(section):
    """The section's first real statement, ignoring HTML comments and blanks.

    The template's guidance lives in a comment block, and it contains the words
    an author is told to write when the rehearsal has NOT happened. Reading it
    as the claim would fail every document written from the template.
    """
    text = re.sub(r"<!--.*?-->", " ", section, flags=re.S)
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith(("|", "#")):
            return line
    return ""


def _check_borrowed_documents_answered(task, task_dir):
    """The threat model and the rollback plan are answered, not just written.

    Both fail the same way - a section written and left unanswered - so one
    check reads whichever exists rather than two checks reading one each.

    A `TRC-` scenario id, or `risk accepted` with a reason, answers a THREAT.
    The Threat Modeling Manifesto names the failure this prevents: "Admiration
    for the Problem", a document that lists threats and mitigates none.

    A rehearsal that happened answers a ROLLBACK. SWEBOK v4 §6.3.3: "a
    planned and rehearsed rollback is done before a new version of the software
    is deployed in production." A rollback nobody has run is a guess, and a
    guess recorded as a plan is the assertion the evidence-not-assertion
    guardrail (`G4`) rejects.

    NEITHER FILE PRESENT RETURNS THE SENTINEL, NOT A PASS. Most issues earn
    neither document, and a guard must not report a pass for work it never
    looked at.
    """
    threat = artifact_path(task_dir, "threat-model.md")
    rollback = artifact_path(task_dir, "rollback-plan.md")
    if not os.path.isfile(threat) and not os.path.isfile(rollback):
        return NOTHING_TO_CHECK, ("neither a threat model nor a rollback plan "
                                  "on this issue - the assessment earned "
                                  "neither, so there is nothing to read")

    findings, read = [], []

    if os.path.isfile(threat):
        read.append("threat-model.md")
        for row in _table_rows(threat):
            # A threat row is `| threat | answer |`. The answer column is the
            # one that has to carry a scenario id or an accepted risk.
            if len(row) < 2:
                continue
            name, answer = row[0], " ".join(row[1:])
            if not name or _is_table_furniture(name):
                continue
            if _TRC_ID.search(answer) or _RISK_ACCEPTED.search(answer):
                continue
            findings.append(
                "threat-model.md: %r names no scenario and no accepted risk"
                % _fit_threat(name))

    if os.path.isfile(rollback):
        read.append("rollback-plan.md")
        section = _section_after(rollback, "rehears")
        if section is None:
            findings.append(
                "rollback-plan.md: no section records when the rollback was "
                "rehearsed")
        elif (not section.strip()
                or _DENIES_REHEARSAL.search(_opening_claim(section))
                or not _REHEARSAL_DATE.search(section)):
            findings.append(
                "rollback-plan.md: the rehearsal section records no rehearsal "
                "- SWEBOK: a rollback is rehearsed before the deploy, and a "
                "plan nobody has run is a guess. Record the date you ran it, "
                "against what, and what happened")

    if findings:
        return False, "; ".join(findings)
    return True, "%s answered" % " and ".join(read)


def _is_table_furniture(cell):
    """A header cell or a separator row, not a threat."""
    c = cell.strip().strip("*").lower()
    return (not c) or set(c) <= set("-: ") or c in {
        "threat", "what can go wrong", "what are we going to do about it",
        "scenario", "evidence"}


def _fit_threat(name, width=60):
    name = " ".join(name.split())
    return name if len(name) <= width else name[:width - 1] + "…"


def _table_rows(path):
    """Markdown table rows as lists of cells. Template placeholders are
    skipped: `{{...}}` is an unfilled example, not somebody's threat."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("|") or "{{" in line:
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells:
                rows.append(cells)
    return rows


def _section_after(path, needle):
    """The body under the first heading containing `needle`, or None."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    body, found = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            if found:
                break
            found = needle.lower() in line.lower()
            continue
        if found and not line.strip().startswith("<!--"):
            body.append(line)
    if not found:
        return None
    # Drop the instructional comment block, which is not somebody's answer.
    joined = "\n".join(body)
    return re.sub(r"<!--.*?-->", "", joined, flags=re.S)
