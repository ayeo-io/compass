# compass_pkg.issue_page - the blocks of the issue page
"""The renderers of the issue page `docs/compass/<created>-<slug>/README.md` (ADR-051).

The page holds ten blocks, in the order a reader's questions come:

1. `header` - the issue, approach, state, stage, gates, owner and dates;
2. `ask` - what is asked and why, from `intent.md` or, without it, from the issue line and
   the scenario titles;
3. `decision-required` - the document that waits for a person, or that nothing does;
4. `acceptance` - each scenario's title with its result;
5. `related` - the issues this one links to and the issues that link to it;
6. `decisions` - design decisions, governance decisions and decisions taken;
7. `artifacts` - the documents with status, approver and what each stands for
   (rendered by `block_renderers`, which every document shares);
8. `traceability` - the Mermaid chart from intent to scenario to test to evidence;
9. `deliberately-omitted` - the documents left out on purpose, with the reason;
10. `follow-ups` - the follow-ups (rendered by `block_renderers`).

Every renderer is a pure function of a `render_inputs.RenderInputs` snapshot. The header
takes the facts it shares with the board from `issue_detail.detail`, called through the
module (ADR-051). Text copied from a record or a document goes through
`rendered_blocks.field`, `cell` or `neutralise`, so it cannot be read as markup.
"""
# DEPENDENCY: standard library (re); compass_pkg.render_inputs, rendered_blocks,
# issue_detail, project_scan, status_words, core.
from __future__ import annotations

import re

from compass_pkg import issue_detail, project_scan, status_words
from compass_pkg import rendered_blocks as rb
from compass_pkg.render_inputs import (CROSS, OWN, Part, code, md_link, relative_to)

#: The blocks a new issue page holds, in order.
PAGE_KINDS = ("header", "ask", "decision-required", "acceptance", "related", "decisions",
              "artifacts", "traceability", "deliberately-omitted", "follow-ups")

#: Past this many scenarios the flowchart shows one summary node per intent, so it
#: stays readable; the acceptance block still lists every scenario (#296).
CHART_SCENARIO_LIMIT = 25

NO_ASK = "No statement of the ask is recorded."
BOARD_NOTE = "To see this issue across the board, run `compass board render`."


# --- the header ------------------------------------------------------------

def _date(value):
    """`YYYY-MM-DD` from a stored date or timestamp, or None."""
    text = str(value or "").strip()
    return text[:10] if re.match(r"^\d{4}-\d{2}-\d{2}", text) else None


def header(inputs, doc_rel):
    task = inputs.task
    facts = issue_detail.detail(task, inputs.task_dir)
    state = facts.state
    reason = status_words.close_reason(task)
    if state == "done" and reason:
        state = "%s (%s)" % (state, reason)
    owner = task.get("owner")
    if not (isinstance(owner, str) and owner.strip()):
        owner = inputs.scan.owner() if inputs.scan is not None else None
    dates = ["Created: %s" % (_date(task.get("created")) or "not recorded")]
    if facts.state == "done" and _date(task.get("land_timestamp")):
        dates.append("Completed: %s" % _date(task.get("land_timestamp")))
    stage = rb.field(facts.stage) if facts.stage else "not recorded"
    lines = ["**%s** - %s - %s - stage %s - gates %d/%d" % (
        code(inputs.slug), rb.field(facts.approach), rb.field(state), stage,
        facts.gates_passed, facts.gates_total),
        "Owner: %s - %s" % (rb.field(owner) if owner else "not recorded", " - ".join(dates))]
    if facts.blocked:
        lines.append("Blocked: %s" % rb.field(facts.blocked))
    lines.append(BOARD_NOTE)
    return Part(OWN, lines)


# --- the ask ---------------------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(`{3,}|~{3,})")


def _fenced(lines):
    """The indexes of the lines inside a code fence that closes. A fence opener with
    no closing line is plain text, so unbalanced text cannot hide the headings
    after it."""
    inside, index = set(), 0
    while index < len(lines):
        opened = _FENCE.match(lines[index])
        if opened:
            marker = opened.group(1)
            for later in range(index + 1, len(lines)):
                closer = re.match(r"^\s*(`{3,}|~{3,})\s*$", lines[later])
                if closer and closer.group(1)[0] == marker[0] and len(closer.group(1)) >= len(marker):
                    inside.update(range(index, later + 1))
                    index = later
                    break
        index += 1
    return inside


def sections(text):
    """`{lower-case heading: [lines]}` of a document, the lines of a section being those up
    to the next heading of its level or above."""
    lines = text.splitlines()
    fenced = _fenced(lines)
    heads = []
    for index, line in enumerate(lines):
        match = _HEADING.match(line)
        if match and index not in fenced:
            heads.append((index, len(match.group(1)), match.group(2).strip().lower()))
    out = {}
    for position, (index, level, name) in enumerate(heads):
        end = len(lines)
        for later_index, later_level, _ in heads[position + 1:]:
            if later_level <= level:
                end = later_index
                break
        out.setdefault(name, lines[index + 1:end])
    return out


def _trim(lines):
    kept = [x.rstrip() for x in lines]
    while kept and not kept[0].strip():
        kept.pop(0)
    while kept and not kept[-1].strip():
        kept.pop()
    # A line that is only an HTML comment is the template's instruction, not the ask. A
    # quoted marker is the author's text and stays (neutralised).
    return [x for x in kept
            if not re.match(r"^\s*<!--.*-->\s*$", x) or "compass:render" in x]


ASK_SECTIONS = (("Problem", "problem"), ("Desired outcome", "desired outcome"),
                ("Success signals", "success signals"), ("Non-goals", "non-goals"))

_ISSUE_LINE = re.compile(r"^\s*>?\s*\*\*Issue:\*\*\s*(.+?)\s*$", re.M)


def _issue_line(text):
    found = _ISSUE_LINE.search(text)
    if found:
        return found.group(1)
    body = sections(text).get("intent")
    if body:
        first = next((x.strip() for x in body if x.strip()), "")
        return re.sub(r"^INT-\d+:\s*", "", first) or None
    return None


def ask(inputs, doc_rel):
    found = sections(inputs.doc_text("intent"))
    lines = []
    for title, key in ASK_SECTIONS:
        body = _trim(found.get(key) or [])
        if body:
            lines += ["**%s**" % title, ""] + [rb.neutralise(x) for x in body] + [""]
    if lines:
        return Part(OWN, lines[:-1])
    issue = _issue_line(inputs.doc_text("delivery-approach"))
    titles = [s for s in inputs.list_of("scenarios") if s.get("title")]
    if issue:
        lines += ["**Issue**", "", rb.field(issue), ""]
    if titles:
        lines += ["**Scenarios**", ""] + ["- %s - %s" % (code(s.get("id", "?")), rb.field(s["title"]))
                                          for s in titles] + [""]
    return Part(OWN, lines[:-1] if lines else [NO_ASK])


# --- the decision required -------------------------------------------------

def decision_required(inputs, doc_rel):
    waiting = [a for a in inputs.list_of("artifacts") if a.get("status") == "awaiting-approval"]
    if not waiting:
        return Part(OWN, ["No decision required. Nothing is awaiting approval."])
    first = waiting[0]
    kind = rb.field(first.get("kind", "document"))
    reason = rb.field((first.get("reason") or "")).rstrip(".")
    lines = ["Approve the %s - %s. Run `compass evidence approve --artifact %s --approver "
             "<name> --role <role>`." % (kind, reason, kind.replace("`", "'"))]
    if first.get("path") and first.get("path") in {a.get("path") for a in inputs.list_of("artifacts")}:
        from compass_pkg.render_inputs import link
        shown = link(inputs, first["path"], doc_rel, first["path"])
        if shown:
            lines += ["", "**Read:** " + shown]
    return Part(OWN, lines)


# --- the acceptance --------------------------------------------------------

def passed(inputs, scenario_id):
    return ("green", scenario_id) in inputs.records or ("acceptance", scenario_id) in inputs.records


def acceptance(inputs, doc_rel):
    scenarios = inputs.list_of("scenarios")
    if not scenarios:
        return Part(OWN, ["No scenarios recorded yet."])
    done = sum(1 for s in scenarios if passed(inputs, str(s.get("id", "?"))))
    lines = ["Acceptance: %d of %d scenarios passed" % (done, len(scenarios)), ""]
    for s in scenarios:
        sid = str(s.get("id", "?"))
        lines.append("- %s - %s - %s" % (code(sid), rb.field(s.get("title", "")),
                                         "passed" if passed(inputs, sid) else "not yet passed"))
    return Part(OWN, lines)


# --- related ---------------------------------------------------------------

#: The order of the lines: the forward links, then the links others hold to this issue.
_ORDER = ("depends on", "depended on by", "parent", "child", "repairs", "follow-up target",
          "delivered by", "raised from", "repaired by", "follow-up from", "raised here")


def related(inputs, doc_rel):
    forward = project_scan.forward_links(inputs.task)
    back = inputs.scan.reverse.get(inputs.slug, []) if inputs.scan is not None else []
    rows = [(label, slug) for label, slug in forward + list(back) if slug != inputs.slug]
    rows.sort(key=lambda r: (_ORDER.index(r[0]), r[1]))
    lines, seen = [], set()
    for label, slug in rows:
        if (label, slug) in seen:
            continue
        seen.add((label, slug))
        scan = inputs.scan
        if scan is not None and slug in scan.manifests:
            lines.append("- %s: %s - %s" % (
                label, md_link(slug, relative_to(scan.page_rel(slug), doc_rel)),
                rb.field(scan.state_text(slug))))
        elif scan is not None and slug in scan.unreadable:
            lines.append("- %s: %s - unreadable" % (label, code(slug)))
        else:
            lines.append("- %s: %s - not found" % (label, code(slug)))
    return Part(CROSS, lines or ["None"])


# --- decisions -------------------------------------------------------------

_DD_HEADING = re.compile(r"^#{1,6}\s+(.*\bDD-(\d+)\b.*?)\s*$")
_ADR_ID = re.compile(r"\bADR-\d+\b")
#: The declared field: `Scope: project`, `- **Scope:** issue` or ``scope: `project` ``, the whole
#: line, with one of the two values. Prose that merely starts with the word is not a field.
_SCOPE = re.compile(r"^\s*(?:[-*+]\s+)?(?:\*\*)?[Ss]cope(?::\*\*|\*\*:|:)\s*`?(issue|project)`?\s*$")
GOVERNANCE_PREFIX = "- governance: "


def design_decisions(text):
    """`[(id, title, scope or None, [ADR ids])]` for each `DD-n` heading of a
    technical design, in the order it holds them."""
    lines = text.splitlines()
    fenced = _fenced(lines)
    heads = [(i, m) for i, line in enumerate(lines) for m in [_DD_HEADING.match(line)]
             if m and i not in fenced]
    out = []
    for position, (index, match) in enumerate(heads):
        end = len(lines)
        for later in range(index + 1, len(lines)):
            if re.match(r"^#{1,6}\s", lines[later]) and later not in fenced:
                end = later
                break
        body = lines[index + 1:end]
        title = re.sub(r"^`?DD-\d+`?\s*[-:–]*\s*", "", match.group(1)).strip()
        scope = None
        for line in body:
            got = _SCOPE.match(line)
            if got:
                scope = re.sub(r"[`*]", "", got.group(1)).strip()
                break
        adrs = list(dict.fromkeys(_ADR_ID.findall("\n".join(body))))
        out.append(("DD-" + match.group(2), title, scope, adrs))
    return out


def decisions(inputs, doc_rel):
    lines = []
    adrs = inputs.scan.adrs if inputs.scan is not None else {}
    for dd_id, title, scope, refs in design_decisions(inputs.doc_text("technical-design")):
        line = "- %s - %s" % (code(dd_id), rb.field(title))
        if scope:
            line += " - scope: %s" % rb.field(scope)
        links = [md_link(ref, relative_to("architecture/decisions/" + adrs[ref], doc_rel))
                 for ref in refs if ref in adrs]
        if links:
            line += " - " + ", ".join(links)
        lines.append(line)
    taken = inputs.list_of("decisions_taken")
    for d in taken:
        line = "- %s (%s) %s - %s" % (code(d.get("id", "?")), rb.field(d.get("status", "?")),
                                      rb.field(d.get("question", "")),
                                      rb.field(d.get("resolution", "")))
        if d.get("status") == "reopened" and d.get("reason"):
            line += " - reopened because: %s" % rb.field(d["reason"])
        lines.append(line)
    if inputs.scan is not None:
        for entry in inputs.scan.decisions_naming(inputs.slug):
            target = relative_to("governance/decisions/" + entry.file, doc_rel)
            lines.append("%s%s - %s" % (GOVERNANCE_PREFIX, md_link(entry.slug, target),
                                        rb.field(entry.title)))
    return Part(OWN, lines or ["None"], cross_prefix=GOVERNANCE_PREFIX)


# --- the chart -------------------------------------------------------------

def _node(kind, *parts):
    """A Mermaid node id, prefixed by its kind so no id is a keyword such as
    `end` and an intent never collides with a scenario."""
    return kind + "_" + "_".join(re.sub(r"\W", "_", str(p)) for p in parts)


def _label(text):
    """A node label with the characters Mermaid would misread encoded."""
    return (str(text).replace("&", "#amp;").replace('"', "#quot;")
            .replace("<", "#lt;").replace(">", "#gt;").replace("\n", " "))


def chart_lines(scenarios, records):
    """The Mermaid flowchart from intent to scenario to test to evidence, as lines
    that begin with the code fence and end with its closing line. `records` is
    `{(kind, scenario): file name}`."""
    # The arrows are thick (`==>`): a rendered line may not hold the comment closer `-->`.
    out = ["```mermaid", "flowchart LR", "  classDef open stroke-dasharray: 4 4"]
    by_intent = {}
    for s in scenarios:
        intents = s.get("intent") or "no intent"
        for intent in intents if isinstance(intents, list) else [intents]:
            by_intent.setdefault(str(intent), []).append(s)
    seen = set()

    def edge(line):
        if line not in seen:
            seen.add(line)
            out.append(line)

    if len(scenarios) > CHART_SCENARIO_LIMIT:
        for intent, group in by_intent.items():
            proven = sum(1 for s in group if ("green", str(s.get("id"))) in records
                         or ("acceptance", str(s.get("id"))) in records)
            edge('  %s["%s"] ==> %s["%d scenarios, %d proven"]' % (
                _node("i", intent), _label(intent), _node("all", intent), len(group), proven))
    else:
        for intent, group in by_intent.items():
            for s in group:
                sid = str(s.get("id", "?"))
                green = records.get(("green", sid))
                proven = bool(green) or ("acceptance", sid) in records
                edge('  %s["%s"] ==> %s["%s"]%s' % (
                    _node("i", intent), _label(intent), _node("s", sid), _label(sid),
                    "" if proven else ":::open"))
                # A test node belongs to its scenario, so a test two scenarios share
                # cannot lead an open one to the other's evidence.
                for test in s.get("tests") or []:
                    tnode = _node("t", sid, test)
                    edge('  %s ==> %s["%s"]' % (_node("s", sid), tnode, _label(test)))
                    if green:
                        edge('  %s ==> %s["%s"]' % (tnode, _node("e", sid, green), _label(green)))
    out.append("```")
    return out


def traceability(inputs, doc_rel):
    scenarios = inputs.list_of("scenarios")
    if not scenarios:
        return Part(OWN, ["No scenarios recorded yet."])
    lines = chart_lines(scenarios, inputs.records)
    if inputs.unbound:
        lines += ["", "Not tied to a scenario: " + ", ".join(code(n) for n in inputs.unbound)]
    return Part(OWN, lines)


# --- deliberately omitted --------------------------------------------------

def deliberately_omitted(inputs, doc_rel):
    omitted = [a for a in inputs.list_of("artifacts") if a.get("status") == "omitted"]
    if not omitted:
        return Part(OWN, ["Nothing recorded as omitted."])
    return Part(OWN, ["- **%s** - %s" % (rb.field(a.get("kind", "?")),
                                         rb.field(a.get("reason") or "no reason recorded"))
                      for a in omitted])


RENDERERS = {
    "header": header,
    "ask": ask,
    "decision-required": decision_required,
    "acceptance": acceptance,
    "related": related,
    "decisions": decisions,
    "traceability": traceability,
    "deliberately-omitted": deliberately_omitted,
}
