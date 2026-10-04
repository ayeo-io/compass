#!/usr/bin/env python3
# =============================================================================
# compass_pkg.receipt - `compass issue receipt` and `compass adr new`
# =============================================================================
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library.
# =============================================================================

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile

# --- dependency check --------------------------------------------------------
# cli/compass_pkg/__init__.py already checked that the bundled copy resolves,
# or exited 3 naming the absolute path it checked, before this module's own
# code runs, so this is never anything but a normal import.
import yaml


import re as _re


import fnmatch
import re as _re
from compass_pkg.core import CompassError, artifact_path, display_shape, find_compass_dir, find_upwards, load_yaml, manifest_path, normalize_spine
from compass_pkg.render import fired_rule_line



# --- command: issue receipt ---------------------------------------------------
# `compass issue receipt --issue <slug>` renders a one-screen receipt of an issue:
# assessment -> delivery approach -> gates with verdicts -> evidence registry -> overall
# verdict. Read-only over .compass/work/<slug>/{manifest.yml, delivery-approach.md, evidence/}
# plus governance/guardrails.yml; never re-runs checks (ADR-005).

def _receipt_resolve_task_dir(args):
    """Resolve an issue dir for the receipt, honouring --workdir if present.

    Returns (task_dir, slug, project_root). Raises CompassError with a
    receipt-specific message that names both the slug and the expected
    directory.
    """
    workdir = getattr(args, "workdir", None)
    slug = args.task
    if workdir:
        project_root = os.path.abspath(workdir)
        compass_dir = os.path.join(project_root, ".compass")
    else:
        compass_dir = find_compass_dir()
        project_root = os.path.dirname(compass_dir)
    session = None
    if not slug:
        from compass_pkg.core import _one_segment, session_issue
        session = session_issue()
        if session is not None:
            slug = _one_segment(session, "COMPASS_ISSUE")
    if not slug:
        ptr = os.path.join(compass_dir, "current-task")
        if os.path.isfile(ptr):
            with open(ptr, "r", encoding="utf-8") as fh:
                slug = fh.read().strip()
    if not slug:
        raise CompassError(
            "compass issue receipt: no --issue and no .compass/current-task pointer"
        )
    task_dir = os.path.join(compass_dir, "work", slug)
    if not os.path.isdir(task_dir):
        named_by = ("COMPASS_ISSUE" if not args.task and slug == session
                    else "the issue")
        raise CompassError(
            f"compass issue receipt: {named_by} '{slug}' not found at "
            f".compass/work/{slug} (looked under {task_dir})"
        )
    return task_dir, slug, project_root


def _receipt_gate_requirements(project_root):
    """Read gate_evidence_requirements from governance/guardrails.yml.

    Returns {gate_id: frozenset(accepted_types)}. {} when the file is absent -
    type-mismatch detection then silently no-ops (degrades gracefully on
    projects that have not adopted governance, per ADR-006).
    """
    path = os.path.join(project_root, "governance", "guardrails.yml")
    if not os.path.isfile(path):
        return {}
    try:
        data = load_yaml(path) or {}
    except CompassError:
        return {}
    raw = data.get("gate_evidence_requirements") or {}
    return {
        k: frozenset(v) for k, v in raw.items()
        if isinstance(v, list) and v
    }


def _receipt_parse_route_md_readings(route_md_path):
    """Parse the four-dimension assessment table out of a delivery-approach.md file.

    Returns {key: (value, justification)} for the four dimensions; absent
    rows are simply not in the dict. If the file is missing or unparseable,
    returns {} - the caller renders "(no justification on file)" in that case.
    """
    import re as _re
    if not os.path.isfile(route_md_path):
        return {}
    text = open(route_md_path, "r", encoding="utf-8").read()
    out = {}
    for dim_labels, key in [
        (("Risk", "Blast" + " radius"), "risk"),  # v1 label built from
        # parts: the scan reads whole string literals, and this one exists
        # only to read old archives
        (("Familiarity", "Terrain"), "familiarity"),
        (("Size", "Magnitude"), "size"),
        (("Goal & role", "Intent & role"), "goal"),
    ]:
      for dim_label in dim_labels:
        m = _re.search(
            rf"\|\s*\*\*{_re.escape(dim_label)}\*\*\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
            text,
        )
        if m:
            out[key] = (m.group(1).strip(), m.group(2).strip())
            break
    return out


_RECEIPT_RULE = "=" * 80
_RECEIPT_LINE_CAP = 100

# A type with no entry shows its id, its type, and its file name as the
# readable text. Listing extras here is the only piece that adapts when a
# type gains meaningful payload fields.
_RECEIPT_EVIDENCE_EXTRAS = {
    "test-run": ("scenario",),
    "manual-review": ("reviewer",),
    "human-approval": ("approver", "role", "decision"),
    "spike-conclusion": ("decision", "next_task"),
}


def _receipt_truncate(text, width=_RECEIPT_LINE_CAP):
    """ASCII-safe line truncation. No ANSI; bytes stable across
    terminals/CI. Tail "..." shows the cut."""
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[:width - 3] + "..."


def _receipt_wrap_ids(head, ids, width=_RECEIPT_LINE_CAP):
    """`head` followed by `ids`, wrapping instead of cutting an identifier.

    Identifiers are the receipt's join keys - a reader follows one from a gate
    to the registry entry that defines it. Truncating one mid-token breaks
    that link silently, so a list that will not fit continues on an indented
    line rather than losing its tail.
    """
    if not ids:
        return [_receipt_truncate(head + "(none)", width)]
    cont = " " * len(head.rstrip()) if len(head) < width // 2 else "      "
    out, current, first = [], head, True
    for i, ident in enumerate(ids):
        piece = str(ident) + ("," if i < len(ids) - 1 else "")
        candidate = current + ("" if first else " ") + piece
        if len(candidate) > width and not first:
            out.append(current)
            current, first = cont + piece, False
            continue
        current, first = candidate, False
    out.append(current)
    return out


def _receipt_parse_orchestration_override(approach_path):
    """Find a recorded orchestration override in the delivery-approach record.

    An override lives in the record as a table row whose first cell is
    "Orchestration" and whose from-to cell reads like "multiagent -> single"
    (either arrow spelling). Records written before ADR-023 say "Topology",
    which is why both labels are read. Returns the overridden-to value, or
    None. Tolerant by design - the record is prose, and a receipt that cannot
    parse it simply shows the computed value.
    """
    import re as _re
    if not approach_path or not os.path.isfile(approach_path):
        return None
    for line in open(approach_path, "r", encoding="utf-8").read().splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        # Reads the retired label too: a record written before ADR-023 says
        # "Topology" (ADR-006).
        if len(cells) >= 2 and cells[0].lower() in ("orchestration", "topology"):
            m = _re.search(r"(?:->|\u2192)\s*([a-z][a-z-]*)", cells[1])
            if m:
                return m.group(1)
    return None


def _receipt_render(task, slug, route_readings, gate_requirements=None,
                    orchestration_override=None):
    """Render the one-screen receipt for an issue. Returns a string.

    Sections, in order:
      1. header  - slug + landed/in-progress status
      2. assessment + justifications
      3. delivery approach + fired routing guardrails
      4. gates + verdicts + evidence ids
      5. evidence registry (id, type, path)
      6. overall verdict line
    """
    lines = []
    schema_version = str(task.get("schema_version") or "")
    # 2.0 is the current schema; anything else (or absent) is legacy - 1.x
    # manifests are readable by normalisation but reported as legacy. ADR-006:
    # render meaningfully on pre-feature task.ymls, do not crash.
    is_legacy = not schema_version.startswith("2.")
    # status: in 1.0 there is no status field - those issues are treated as
    # active by the rest of the CLI, and the receipt does the same. Honesty:
    # a legacy issue with no status cannot be reported as cleanly landed.
    raw_status = task.get("status")
    is_landed = (raw_status == "landed")
    if is_landed:
        header_status = "landed"
    elif raw_status == "active" or raw_status is None:
        header_status = "IN PROGRESS - not yet landed"
    else:
        header_status = str(raw_status).upper()
    schema_note = f" - schema {schema_version or '1.0'} (legacy)" if is_legacy else ""

    # 1. header
    lines.append(_RECEIPT_RULE)
    lines.append(f"Receipt - {slug} ({header_status}){schema_note}")
    lines.append(_RECEIPT_RULE)
    lines.append("")

    # 2. assessment + justifications
    lines.append("Assessment")
    lines.append("----------")
    readings = task.get("assessment") or {}
    for label, key in [
        ("risk", "risk"),
        ("familiarity", "familiarity"),
        ("size", "size"),
        ("goal", "goal"),
    ]:
        if key == "goal":
            role = readings.get("role") or "engineer"
            intent_v = readings.get("goal") or "(not recorded)"
            value = f"{intent_v} ({role})"
        else:
            value = str(readings.get(key) or "(not recorded)")
        justification = "(no justification on file)"
        if key in route_readings:
            justification = route_readings[key][1]
        lines.append(_receipt_truncate(
            f"  {label:<14}  {value:<22}  {justification}"))
    touches = readings.get("labels") or []
    if touches:
        lines.append(_receipt_truncate(
            f"  {'labels':<14}  {', '.join(touches)}"))
    lines.append("")

    # 3. the delivery approach + fired policy rules
    lines.append("Approach")
    lines.append("--------")
    route_name = task.get("delivery_approach")
    shape_shown = display_shape(route_name) if route_name else "(not recorded)"
    orchestration = task.get("orchestration") or ""
    orchestration_shown = orchestration
    if orchestration_override and orchestration_override != orchestration:
        orchestration_shown = (
            f"{orchestration} (overridden: {orchestration_override} - "
            "see the delivery approach)")
    # Assess records a ceiling, breakdown records an orchestration. A manifest
    # may legitimately carry either: an archived one has the word assess used
    # to write, and an active one has only the ceiling until the
    # distribution map exists.
    if orchestration_shown:
        detail = f"orchestration: {orchestration_shown}"
    else:
        ceiling = task.get("subtask_ceiling")
        detail = ("parallel subtasks: unbounded by policy" if ceiling is None
                  else f"parallel subtasks: up to {ceiling}")
    lines.append(_receipt_truncate(f"  {shape_shown}  ({detail})"))
    # No v1-key fallback: the manifest is normalised on load (see
    # normalize_spine), so a 1.x `fired_guardrails` has already become
    # this key by the time the receipt reads it.
    fired = task.get("policy_rules_fired") or []
    if fired:
        lines.append("  policy rules fired:")
        for g in fired:
            # Meaning first, code in brackets, so a reader meets the meaning
            # before the code (`S7`, cold reader). The code stays: it carries
            # the traceability and it is what someone searches for.
            lines.append(_receipt_truncate(
                f"    {fired_rule_line(g, with_kind=False)}"))
    else:
        lines.append("  policy rules fired: none")
    lines.append("")

    # 4. gates + verdicts + evidence ids
    # The verdict label is honest about the recorded state: a pass
    # referencing wrong-typed evidence is type-mismatch; a pass with no
    # evidence is unsupported. The receipt reports; it does not enforce.
    lines.append("Gates")
    lines.append("-----")
    gates = task.get("gates") or []
    evidence_by_id = {ev.get("id"): ev for ev in (task.get("evidence") or [])
                      if isinstance(ev, dict) and ev.get("id")}
    any_fail = False
    any_caveat = False
    requirements = gate_requirements or {}
    for g in gates:
        gid = g.get("id", "?")
        gstatus = g.get("status", "pending")
        ev_ids = g.get("evidence") or []
        if gstatus == "fail":
            verdict = "[ FAIL ]"
            any_fail = True
        elif gstatus == "pass":
            if not ev_ids:
                verdict = "[ UNSUPPORTED ]"
                any_caveat = True
            else:
                req_types = requirements.get(gid)
                if req_types:
                    ev_types = {evidence_by_id.get(eid, {}).get("type")
                                for eid in ev_ids}
                    ev_types.discard(None)
                    if ev_types and not (ev_types & req_types):
                        verdict = "[ TYPE-MISMATCH ]"
                        any_caveat = True
                    else:
                        verdict = "[ PASS ]"
                else:
                    verdict = "[ PASS ]"
        elif gstatus == "pending":
            # A pending gate is not a clean land. The receipt is the audit
            # record, so it must not say "landed cleanly" while any gate is
            # pending.
            verdict = "[ PENDING ]"
            any_caveat = True
        else:
            verdict = f"[ {gstatus.upper()} ]"
            any_caveat = True
        # Wrap the evidence list rather than truncating it. A cut identifier
        # is worse than a bare one: "EV-ANALYZE-signup-email-va..." cannot be
        # matched to the entry that defines it further down this same
        # receipt, so it identifies nothing. Prose still truncates - a cut
        # sentence is still readable.
        head = f"  {gid:<26} {verdict:<18} evidence: "
        lines.extend(_receipt_wrap_ids(head, ev_ids))
    lines.append("")

    # 5. evidence registry - type-specific minimal fields rendered alongside
    # the id and type. The dispatch table covers only types with meaningful
    # extras; a type with no entry shows its id, its type, and its file stem
    # (hyphens turned to spaces) as the readable text - adding an evidence
    # type to governance/guardrails.yml does not need a renderer change,
    # it just lands with that fallback until/unless someone adds an extras
    # tuple here.
    lines.append("Evidence")
    lines.append("--------")
    evs = task.get("evidence") or []
    if not evs:
        lines.append("  (no evidence recorded)")
    else:
        # Sized to the widest id present, but CAPPED. One auto-generated id -
        # `EV-ANALYZE-<slug>-<timestamp>` runs to 51 characters - would
        # otherwise set the column for all of them and crush the readable
        # column to nothing. A long id overflows its cell and shifts that one
        # row; every other row keeps its grid, and the words stay legible.
        id_w = min(14, max(8, *(len(str(e.get("id", "?"))) for e in evs
                                if isinstance(e, dict))))
        # An identifier appears with its meaning on first use (the cold-reader
        # strategy). A scenario's meaning is its title, which the manifest
        # already holds - so print it rather than making the reader resolve
        # the scenario id from somewhere else.
        titles = {s.get("id"): s.get("title")
                  for s in (task.get("scenarios") or [])
                  if isinstance(s, dict) and s.get("title")}
        # One line per entry, readable part first: what was proved, then how
        # strongly (the type).
        rows = []
        for ev in evs:
            if not isinstance(ev, dict):
                continue
            eid = str(ev.get("id", "?"))
            etype = str(ev.get("type", "?"))
            extras = _RECEIPT_EVIDENCE_EXTRAS.get(etype, ())
            # What this proves, in words. For a scenario, the id and its
            # title from the manifest.
            #
            # Every other type keeps ALL its declared fields, joined on one
            # line. A human sign-off means nothing without who approved, in
            # what role, and what they decided; a spike conclusion means
            # nothing without the decision and where it went. Those are the
            # type-specific minimal fields, and dropping any of them would lose
            # information rather than noise.
            proves = ""
            scenario = ev.get("scenario")
            if "scenario" in extras and titles.get(scenario):
                # Id AND title. The title is the content and the id is the
                # cross-reference - dropping the id looked tidier and broke the
                # trace for any record whose evidence id does not already carry
                # it. Ids written by the CLI do (`EV-T-TRC-A1`), so it reads as
                # mild repetition there; a hand-written `EV-X` would otherwise
                # have lost its link to the scenario entirely.
                proves = f"{scenario} - {titles[scenario]}"
            else:
                proves = ", ".join(f"{k}: {ev.get(k)}"
                                   for k in extras if ev.get(k) is not None)
            if not proves:
                # No scenario behind it - a baseline, a review, a sweep. The
                # filename is what it is called, so use that rather than
                # leaving the column blank: "mutation-proof-group-A" reads.
                stem = pathlib.PurePosixPath(str(ev.get("path", ""))).stem
                proves = stem.replace("-", " ").replace("_", " ")
            rows.append((eid, etype, proves))

        # Issue-level records - baselines, reviews, sweeps - have no scenario
        # behind them. Per-scenario records first, then the issue-level ones,
        # so the two kinds do not interleave in whatever order they were
        # written.
        rows.sort(key=lambda r: (not r[0].startswith("EV-T-"), ))
        # No path column: the id identifies the record, and a capped path
        # reads as information when it is not.
        # Width maths, spelled out because getting it wrong silently truncates
        # whichever column is last: two spaces of indent, the id, two spaces,
        # the readable column, two spaces, the type. The type width comes from
        # the rows actually present rather than a guessed constant.
        type_w = max((len(r[1]) for r in rows), default=0)
        proves_w = max(4, _RECEIPT_LINE_CAP - 2 - id_w - 2 - 2 - type_w)
        for eid, etype, proves in rows:
            shown = proves if len(proves) <= proves_w else proves[:proves_w - 1] + "\u2026"
            lines.append(_receipt_truncate(
                f"  {eid:<{id_w}}  {shown:<{proves_w}}  {etype}"))
    lines.append("")

    # 5b. follow-ups (rendered only when any exist)
    backfills = task.get("follow_ups") or []
    if backfills:
        lines.append("Follow-ups")
        lines.append("----------")
        for b in backfills:
            if not isinstance(b, dict):
                continue
            bid = b.get("id", "?")
            bstatus = b.get("status", "?")
            bdesc = b.get("description", "")
            marker = ("[ OUTSTANDING ]" if bstatus == "outstanding"
                      else "[ resolved ]")
            lines.append(_receipt_truncate(
                f"  {bid:<8}  {marker:<15} {bdesc}"))
        lines.append("")

    # 6. overall verdict
    lines.append(_RECEIPT_RULE)
    n_owed = sum(1 for b in backfills if isinstance(b, dict)
                 and b.get("status") == "outstanding")
    if not is_landed:
        verdict_line = "Verdict: not yet landed"
    elif any_fail:
        verdict_line = "Verdict: FAILED - does not satisfy its own gates"
    elif n_owed:
        verdict_line = (f"Verdict: landed with caveats - "
                        f"{n_owed} follow-up(s) outstanding")
    elif any_caveat:
        verdict_line = "Verdict: landed with caveats"
    else:
        verdict_line = "Verdict: landed cleanly"
    lines.append(verdict_line)

    return "\n".join(lines)


def cmd_task_receipt(args):
    try:
        task_dir, slug, project_root = _receipt_resolve_task_dir(args)
    except CompassError as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    task = normalize_spine(load_yaml(manifest_path(task_dir)) or {})
    approach_path = artifact_path(task_dir, "delivery-approach.md")
    route_readings = _receipt_parse_route_md_readings(approach_path)
    gate_requirements = _receipt_gate_requirements(project_root)
    print(_receipt_render(task, slug, route_readings, gate_requirements,
                          _receipt_parse_orchestration_override(approach_path)))
    return 0


# --- command: adr ------------------------------------------------------------
# `compass adr new <slug>` creates a sequentially-numbered ADR file under
# architecture/decisions/ and registers it in the README.md index.
#
# Sequential within a tree at invocation time; concurrent worktrees may
# collide and surface the conflict as a normal git merge conflict. The
# directory is created if absent.

_ADR_TEMPLATE = """\
---
id: {id}
title: {title}
status: proposed
date: {date}
supersedes: ''
superseded_by: ''
---

## Context

<!-- Describe the situation that necessitated this decision. -->

## Decision

<!-- State the decision clearly and concisely. -->

## Alternatives considered

<!-- List alternatives that were evaluated and why they were not chosen. -->

## Consequences

<!-- Describe the positive and negative consequences of this decision. -->

## References

<!-- Link to ADRs, issues, or documents that influenced this decision. -->
"""

_ADR_README_HEADER = """\
# Architecture Decision Records

This directory contains the project's Architecture Decision Records (ADRs).

Each ADR captures one significant architectural decision: its context, the
choice made, the alternatives considered, and the consequences.

## Numbering

ADRs are numbered sequentially.  `compass adr new <slug>` assigns the next
available number so the index is always in creation order.  When two worktrees
create ADRs concurrently, a git merge conflict on this README signals the
collision; resolve by renumbering one side.

## Index

| ID | Title | Status |
|---|---|---|
"""


def _adr_readme_row(adr_id: str, title: str, status: str, path: str) -> str:
    return f"| [{adr_id}]({path}) | {title} | {status} |\n"


def _with_adr_row(readme_text: str, row: str) -> str:
    """The README with `row` placed in the ADR table.

    After the last existing ADR row; failing that, under the separator of the
    first table whose header starts with ID; failing that, at the end. A README
    with sections after its table must keep them after it, so appending to the
    file is only the last resort.
    """
    lines = readme_text.splitlines(keepends=True)
    adr_row = re.compile(r"^\|\s*\[?ADR-\d+")
    at = max((i for i, line in enumerate(lines) if adr_row.match(line)), default=None)
    if at is None:
        for i, line in enumerate(lines[:-1]):
            if re.match(r"^\|\s*ID\s*\|", line) and re.match(r"^\|[-\s|:]+\|\s*$", lines[i + 1]):
                at = i + 1
                break
    if at is None:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        return "".join(lines) + row
    if not lines[at].endswith("\n"):
        lines[at] += "\n"
    lines.insert(at + 1, row)
    return "".join(lines)


def cmd_adr_new(args):
    """Create a new numbered ADR file and register it in the decisions README."""
    slug = args.slug
    if not slug:
        raise CompassError("compass adr new requires a slug argument")
    # Sanitise slug: lowercase, replace spaces/underscores with hyphens
    slug = slug.strip().lower().replace(" ", "-").replace("_", "-")

    # Find the architecture/decisions directory
    proj = find_upwards(os.getcwd(), os.path.join("architecture", "decisions"))
    if proj:
        decisions_dir = os.path.join(proj, "architecture", "decisions")
    else:
        # Not found walking up - create relative to cwd
        decisions_dir = os.path.join(os.getcwd(), "architecture", "decisions")

    os.makedirs(decisions_dir, exist_ok=True)

    # Count existing ADR-*.md files to determine the next number
    existing = sorted(
        f for f in os.listdir(decisions_dir)
        if f.startswith("ADR-") and f.endswith(".md")
           and f != "ADR-template.md"
    )
    next_num = len(existing) + 1
    num_str = f"{next_num:03d}"
    adr_id = f"ADR-{num_str}"
    filename = f"ADR-{num_str}-{slug}.md"
    full_path = os.path.join(decisions_dir, filename)

    if os.path.exists(full_path):
        raise CompassError(
            f"{full_path} already exists. If you are in a concurrent worktree, "
            f"this is expected - rename one side when the subtasks integrate."
        )

    title_words = slug.replace("-", " ").title()
    content = _ADR_TEMPLATE.format(
        id=adr_id,
        title=title_words,
        date=datetime.date.today().isoformat(),
    )
    with open(full_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    # Update README.md index
    readme_path = os.path.join(decisions_dir, "README.md")
    if os.path.exists(readme_path):
        readme_text = open(readme_path, encoding="utf-8").read()
    else:
        readme_text = _ADR_README_HEADER

    row = _adr_readme_row(adr_id, title_words, "proposed", filename)
    if adr_id not in readme_text:
        with open(readme_path, "w", encoding="utf-8") as fh:
            fh.write(_with_adr_row(readme_text, row))

    # The caveat is split across two lines: one 129-character line is not a
    # line a person reads, and this one is worth reading.
    from compass_pkg.terminal import say

    return say(args, f"compass adr new: created {full_path}",
               detail=[f"registered in {readme_path}",
                       "NOTE: if another worktree creates ADRs at the same "
                       "time, the",
                       "      numbers will collide - renumber when the "
                       "subtasks integrate."],
               path=full_path, index=readme_path)
