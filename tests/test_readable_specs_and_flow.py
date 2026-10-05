"""Acceptance tests for issue readable-specs-and-flow.

Each test_trc_* function asserts one scenario:
readable-specs-and-flow/acceptance-criteria.md.

Why these are regex assertions over markdown rather than unit tests: the
"production" change for most of this issue is the text of shipped templates,
skills, agents and commands. That is the same situation
tests/test_plugin_doc_drift.py is in, and these follow its approach. The
executable half of the issue (the `compass plan lint` subcommand) is tested
separately in tests/test_no_placeholders_check.py, where real unit tests are
possible.

These are still real tests: they run under `pytest tests/`, they fail when the
shipped text drifts, and `compass tdd-red` / `compass tdd-green` write typed
test-run evidence from them that the verify stage's gates accept.
"""

# These tests assert the current names (technical-design.md, intent.md).
# Older manifests and documents still load (ADR-006).
import re
import subprocess
import sys
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The archive these tests read: the tracked sample, or this checkout's own
# with COMPASS_FULL_ARCHIVE=1 (tests/archive.py).
sys.path.insert(0, str(ROOT / "tests"))
from archive import archive_root  # noqa: E402

SPEC_TEMPLATE = "templates/acceptance-criteria.md"
CLARIFICATIONS_TEMPLATE = "templates/requirements-review.md"
BDD_SKILL = "skills/bdd-specification/SKILL.md"
SPEC_AUTHOR = "agents/spec-author.md"


def _read(rel):
    return (ROOT / rel).read_text()


def _flat(text):
    """Collapse all runs of whitespace to single spaces, lowercased.

    Markdown here is hard-wrapped at ~80 columns, so a phrase like "do not
    write a review artifact" is routinely split across two lines. Matching
    against the raw text would make these tests fail on reflowing rather than
    on meaning.
    """
    return re.sub(r"\s+", " ", text).lower()


def _section(text, heading, level="## "):
    """Return the body of the markdown section introduced by `heading`.

    Ends at the next heading of the same level, or end of file.
    """
    start = text.find(level + heading)
    assert start >= 0, f"Section '{heading}' not found"
    after = text[start + len(level) + len(heading):]
    nxt = after.find("\n" + level)
    return after if nxt < 0 else after[:nxt]


# ---------------------------------------------------------------------------
# Group A - the spec Summary preamble
# ---------------------------------------------------------------------------

def test_trc_a1_summary_precedes_role_guide():
    """The Summary is the first thing a cold reader meets: it comes before the
    role-guide block, which in turn still comes before the intent-links table."""
    tpl = _read(SPEC_TEMPLATE)

    i_summary = tpl.find("## Summary")
    i_roles = tpl.find("## How each role reads this file")
    i_intent = tpl.find("## Intent links")

    assert i_summary >= 0, "No '## Summary' heading in the spec template"
    assert i_roles >= 0, "The role-guide block disappeared from the spec template"
    assert i_intent >= 0, "The intent-links table disappeared from the spec template"

    assert i_summary < i_roles, (
        "The Summary must come before the role-guide block - a cold reader wants "
        "what is being built before they want who reads it"
    )
    assert i_roles < i_intent, "The role-guide block must still precede the intent links"


def test_trc_a2_summary_has_three_named_fields():
    """The Summary carries exactly Goal, Approach, and Why now / what changes,
    in that order, each with a placeholder saying what to write."""
    body = _section(_read(SPEC_TEMPLATE), "Summary")

    positions = []
    for label in ("Goal", "Approach", "Why now / what changes"):
        m = re.search(r"\*\*" + re.escape(label) + r":\*\*", body)
        assert m, f"Summary field '{label}' not found in the template"
        positions.append(m.start())

    assert positions == sorted(positions), (
        "Summary fields must appear in the order Goal, Approach, "
        "Why now / what changes"
    )

    # Each field is followed by a {{...}} placeholder telling the author what to
    # write - an empty label would give the author nothing to work from.
    for label in ("Goal", "Approach", "Why now / what changes"):
        m = re.search(
            r"\*\*" + re.escape(label) + r":\*\*\s*\{\{.+?\}\}",
            body,
            re.DOTALL,
        )
        assert m, f"Summary field '{label}' has no {{{{placeholder}}}} guidance"


def test_trc_a3_summary_length_scales_by_route():
    """Length guidance is stated per delivery approach, so a quick fix's
    criteria do not get an initiative-sized preamble."""
    body = _section(_read(SPEC_TEMPLATE), "Summary")
    low = body.lower()

    assert "quick fix" in low, "Summary guidance does not mention the quick fix"
    assert "regular" in low, "Summary guidance does not mention the regular approach"
    assert re.search(r"(?m)^\s*full\s+-", low), "Summary guidance does not mention the full approach"

    assert re.search(r"one to two sentences|1-2 sentences", low), (
        "Quick-fix length target (one to two sentences per field) not stated"
    )
    assert "paragraph" in low, "Standard length target (ordinary paragraphs) not stated"
    assert "200 words" in low, "Expedition length ceiling (200 words per field) not stated"


def test_trc_a4_template_scenario_machinery_intact():
    """The Summary is additive: the scenario machinery it sits above is
    unchanged."""
    tpl = _read(SPEC_TEMPLATE)

    assert "| Intent id | Source | Statement |" in tpl, "Intent-links table lost"
    assert re.search(r"```gherkin\n.*?Given .*?When .*?Then .*?```", tpl, re.DOTALL), (
        "No Given/When/Then gherkin block left in the template"
    )
    assert re.search(r"traceability id:\s*TRC-", tpl), "Traceability id comments lost"
    assert "## Failure-mode scenarios" in tpl, "Failure-mode section lost"
    assert "## Coverage ledger" in tpl, "Coverage ledger lost"


def test_trc_a5_spec_author_and_skill_name_summary():
    """Both the agent that runs define and the skill it loads tell the author
    to write the Summary, and both name all three fields."""
    for rel in (SPEC_AUTHOR, BDD_SKILL):
        text = _read(rel)
        low = text.lower()

        assert "summary" in low, f"{rel} never mentions the Summary section"
        for label in ("goal", "approach", "why now"):
            assert label in low, f"{rel} does not name the Summary field '{label}'"


def test_trc_a6_dor_requires_filled_summary():
    """A filled Summary is a condition of leaving the requirements review -
    enforced by the Definition of Ready checklist, not by the CLI."""
    body = _section(_read(CLARIFICATIONS_TEMPLATE), "Gate")

    assert "definition of ready" in body.lower(), "Definition of Ready section not found"

    # Checklist items wrap over several lines - take each item up to the next
    # one (or the end of the section) so the whole item is matched, not line 1.
    items = re.split(r"^\s*- \[ \] ", body, flags=re.M)[1:]
    summary_items = [i for i in items if "summary" in i.lower()]
    assert summary_items, "No Definition of Ready item requiring the spec's Summary"

    item = _flat(summary_items[0])
    assert re.search(r"three fields|goal.*approach.*why now", item), (
        "The Definition of Ready item does not require all three Summary fields"
    )


# ---------------------------------------------------------------------------
# Group B - the spec-author's inline self-review
# ---------------------------------------------------------------------------

SELF_REVIEW_HEADING = "Self-review before the requirements review"


def _self_review():
    return _section(_read(BDD_SKILL), SELF_REVIEW_HEADING)


def test_trc_b1_self_review_lists_four_scans():
    """Exactly four scans. The case for an inline self-review over a subagent
    critic is that it stays cheap, so the list must not grow silently."""
    body = _self_review()
    items = re.findall(r"^\s*\d+\.\s+\*\*(.+?)\*\*", body, re.M)

    assert len(items) == 4, f"Expected exactly 4 scans, found {len(items)}: {items}"

    joined = " ".join(items).lower()
    for expected in ("placeholder", "orphan-intent", "untestable-then", "ambiguous-quantifier"):
        assert expected in joined, f"Scan '{expected}' missing from the self-review"


def test_trc_b2_each_scan_is_concrete():
    """Each scan says what it actually looks for. A scan named but not defined
    is a checklist item nobody can run."""
    body = _self_review()
    low = body.lower()

    assert "{{" in body, "Placeholder scan does not name the double-brace placeholder form"
    assert "int-" in low, "Orphan-intent scan does not reference INT-n ids"
    assert "it works" in low, "Untestable-Then scan gives no example phrase"
    assert "is correct" in low, "Untestable-Then scan gives only one example phrase"
    assert "quickly" in low, "Ambiguous-quantifier scan gives no example word"
    assert "most" in low, "Ambiguous-quantifier scan gives only one example word"
    assert "number" in low, (
        "Ambiguous-quantifier scan does not state the test - that no number is attached"
    )


def test_trc_b3_self_review_is_fix_inline():
    """Findings are fixed in place. The prohibitions are stated explicitly so
    the next contributor cannot read the silence as permission."""
    flat = _flat(_self_review())

    assert re.search(r"fix .{0,40}inline|inline.{0,40}fix", flat), (
        "The self-review does not say to fix findings inline"
    )
    assert "do not write a review artifact" in flat, (
        "The self-review does not rule out producing a separate review artifact"
    )
    assert "do not invoke" in flat, (
        "The self-review does not rule out invoking a reviewer agent"
    )


def test_trc_b4_self_review_complements_clarify():
    """The self-check adds to the requirements review; it does not stand in
    for it."""
    low = _self_review().lower()

    assert "review still runs" in low, (
        "The self-review does not state that the requirements review still "
        "runs on the regular approach and above"
    )
    assert "regular" in low, (
        "The self-review does not name the approaches the requirements "
        "review still runs on")


def test_trc_b5_express_self_check_recorded_in_devlog():
    """Where the requirements review collapses, the self-check is the QA -
    so it goes on disk, not into the conversation (`S4`, persistence over
    conversation)."""
    low = _self_review().lower()

    assert "quick-fix" in low or "quick fix" in low, ("The self-review says nothing about the quick fix")
    assert "devlog.md" in low, (
        "The self-review does not require recording the Express self-check in devlog.md"
    )


# ---------------------------------------------------------------------------
# Group C - the no-placeholders plan check (documentation half)
# ---------------------------------------------------------------------------

GOVERNANCE_SKILL = "skills/governance-check/SKILL.md"


def test_trc_c2b_skill_names_command_and_note():
    """The planner has to know what to run, and what a hit means."""
    flat = _flat(_read(GOVERNANCE_SKILL))

    assert "compass plan lint" in flat, (
        "The governance-check skill does not name the command the planner runs"
    )
    assert re.search(r"note,? (rather than|not) a (stop|block)", flat), (
        "The skill does not state that a reported hit is a note rather than a stop"
    )


def test_trc_c3_check_sits_in_strategies_walk():
    """The check is judgement, so it belongs in the strategies walk. Putting it
    under the guardrails walk would make it look like it is cleared with
    evidence, which is exactly the conflation the two-walk split prevents."""
    text = _read(GOVERNANCE_SKILL)

    i_strategies = text.find("## Walk 2 - the strategies")
    i_routing = text.find("## Walk 3 - the routing policy")
    i_check = text.lower().find("compass plan lint")

    assert i_strategies >= 0 and i_routing >= 0, "The governance walks were renamed"
    assert i_check >= 0, "The no-placeholders check is not in the skill at all"
    assert i_strategies < i_check < i_routing, (
        "The no-placeholders check must be described under Walk 2 (strategies, "
        "assessed as judgement), not under Walk 1 (guardrails, cleared with "
        "evidence)"
    )


def test_trc_c4_guardrail_count_stays_five():
    """ADR-002: the framework grows by adding artifacts, not rules. A
    sixth guardrail would dilute the concept."""
    import yaml

    gy = yaml.safe_load((ROOT / "governance/guardrails.yml").read_text())

    def _walk_ids(node, found):
        if isinstance(node, dict):
            gid = node.get("id")
            if isinstance(gid, str) and re.fullmatch(r"G\d+", gid):
                found.add(gid)
            for v in node.values():
                _walk_ids(v, found)
        elif isinstance(node, list):
            for v in node:
                _walk_ids(v, found)
        return found

    ids = _walk_ids(gy, set())
    assert ids == {"G1", "G2", "G3", "G4", "G5"}, (
        f"Expected exactly G1-G5 in guardrails.yml, found {sorted(ids)}"
    )

    prose = _read("governance/guardrails.md")
    assert not re.search(r"\bG6\b", prose), "A sixth guardrail appeared in guardrails.md"


def test_trc_c6_no_gate_or_floor_added():
    """The check stays advisory on every delivery approach: no floor
    promotes it, and no delivery-approach shape lists it as a gate."""
    import yaml

    rp = yaml.safe_load((ROOT / "governance/routing-policy.yml").read_text())

    floors = rp["routing_guardrails"].get("floors", [])
    for floor in floors:
        gate = floor.get("add_gate", "")
        assert "placeholder" not in str(gate).lower(), (
            f"Floor {floor.get('id')} promotes the no-placeholders check to a gate"
        )

    for shape_name, shape in rp["route_shapes"].items():
        for gate in shape.get("gates", []):
            assert "placeholder" not in gate.lower(), (
                f"Route shape '{shape_name}' lists a no-placeholders gate"
            )


# ---------------------------------------------------------------------------
# Group D - the phase hand-off prompts
# ---------------------------------------------------------------------------

HANDOFF_HEADING = "## Hand-off"

HANDOFF_PHASES = {
    "commands/define.md": "acceptance-criteria.md",
    "commands/refine.md": "requirements-review.md",
    "commands/plan.md": "technical-design.md",
}


def test_trc_d1_specify_handoff_prompt():
    """Define closes by inviting a cold-reader review: what was written, what
    to look for, and what happens on approval."""
    text = _read("commands/define.md")
    assert HANDOFF_HEADING in text, "commands/define.md has no Hand-off section"

    flat = _flat(_section(text, "Hand-off"))

    assert "acceptance-criteria.md" in flat, "The hand-off does not name the artifact written"

    for look_for in ("intent fidelity", "untestable", "failure mode", "ambiguous"):
        assert look_for in flat, (
            f"The Specify hand-off does not ask the reviewer to check '{look_for}'"
        )

    assert "refine" in flat, (
        "The Specify hand-off does not say what happens next once the reviewer approves"
    )


def test_trc_d2_clarify_and_plan_handoffs_symmetric():
    """The other two hand-offs do the same three jobs, so a reviewer meets the
    same shape at every phase boundary."""
    for rel, artifact in HANDOFF_PHASES.items():
        text = _read(rel)
        assert HANDOFF_HEADING in text, f"{rel} has no Hand-off section"

        flat = _flat(_section(text, "Hand-off"))

        assert artifact in flat, f"{rel}'s hand-off does not name {artifact}"
        assert re.search(r"look for|check|watch for", flat), (
            f"{rel}'s hand-off does not tell the reviewer what to look for"
        )
        assert re.search(r"next|approv|proceed", flat), (
            f"{rel}'s hand-off does not say what happens next"
        )


def test_trc_d3_handoff_prompt_defined_once():
    """The prompt is pipeline protocol, so it lives in commands/ only. Written
    into both the command and the agent it would be a value in two places, and
    the two would drift."""
    for path in (ROOT / "agents").glob("*.md"):
        text = path.read_text()
        assert HANDOFF_HEADING not in text, (
            f"{path.name} defines a Hand-off section - the prompt belongs in "
            "commands/, and the agent should refer to it instead"
        )

    # The two agents that own these phases point at the prompt without restating it.
    for rel in (SPEC_AUTHOR, "agents/planner.md"):
        flat = _flat(_read(rel))
        assert "hand-off" in flat, f"{rel} never refers to the phase hand-off prompt"


# ---------------------------------------------------------------------------
# Group E - the writing guide
# ---------------------------------------------------------------------------

GUIDE = "docs/writing-specs-and-plans.md"

GUIDE_EXAMPLES = ("Summary", "design decision", "scenario name", "work unit")


def _guide_example_sections():
    """Return the body of each '## Example N - ...' section in the guide."""
    text = _read(GUIDE)
    parts = re.split(r"^## Example \d+[^\n]*$", text, flags=re.M)[1:]
    return parts


def test_trc_e1_guide_has_four_worked_examples():
    """`S7` shown applied to four kinds of artifact. A strategy described but
    never demonstrated is the thing this guide exists to fix."""
    text = _read(GUIDE)
    headings = re.findall(r"^## Example \d+ - (.+)$", text, re.M)

    assert len(headings) == 4, (
        f"Expected 4 worked examples, found {len(headings)}: {headings}"
    )

    joined = " ".join(headings).lower()
    for kind in GUIDE_EXAMPLES:
        assert kind.lower() in joined, (
            f"No worked example for '{kind}'. Found: {headings}"
        )


def test_trc_e2_examples_are_before_and_after():
    """Each example shows the weak version beside the improved one, and says in
    one line what changed. Showing only the good version teaches recognition,
    not correction."""
    sections = _guide_example_sections()
    assert sections, "No '## Example N' sections found in the guide"

    for i, body in enumerate(sections, 1):
        flat = _flat(body)
        assert "**weak**" in flat or "weak:" in flat, (
            f"Example {i} does not show a weak version"
        )
        assert "**better**" in flat or "better:" in flat, (
            f"Example {i} does not show an improved version"
        )
        assert "what changed" in flat, (
            f"Example {i} does not say in one line what changed between them"
        )


def test_trc_e3_guide_names_non_adoptions():
    """What Compass deliberately does not adopt, and why. An unstated boundary
    gets argued again; a stated one gets a decision to argue with."""
    flat = _flat(_read(GUIDE))

    # No subagent review loop, with the measured reason.
    assert "subagent" in flat, "The guide does not mention subagent review loops"
    assert re.search(r"25\s*(minutes|min)", flat), (
        "The guide does not give the measured overhead that argues against a "
        "subagent review loop"
    )

    # No user-story format, citing the ADR that refuses it.
    assert "user story" in flat or "user stories" in flat, (
        "The guide does not address the user-story format"
    )
    assert "adr-004" in flat, "The guide does not cite ADR-004 on the user-story format"

    # No single-audience persona declaration.
    assert re.search(r"junior engineer|single audience|one audience|persona", flat), (
        "The guide does not address declaring a single-audience persona"
    )
    assert "lens" in flat, (
        "The guide does not explain that the five-lens model replaces a single "
        "audience declaration"
    )

    # No bite-sized-tasks-with-exact-commands plan format.
    assert re.search(r"bite-sized|exact commands", flat), (
        "The guide does not address the bite-sized-tasks plan format"
    )


def test_trc_e4_guide_is_linked():
    """Reachable from where a reader looking for writing guidance would start."""
    readme = _read("README.md")
    assert "docs/writing-specs-and-plans.md" in readme, (
        "README.md does not link the writing guide"
    )


# ---------------------------------------------------------------------------
# Failure modes owned by this unit
# ---------------------------------------------------------------------------

def test_trc_f1_pre_existing_specs_still_pass():
    """Specs written before the Summary existed must not start failing.

    ADR-006 (backward compatibility is non-negotiable) is the reason the
    Summary is enforced by the Definition of Ready at the requirements
    review rather than by a check in `compass check`: a mechanical check
    over prose structure would fail every spec already on disk, and every
    adopter's too.
    """
    work = archive_root() / ".compass" / "work"
    if not work.is_dir():          # the issue directory is not shipped to adopters
        return

    # Specs were once a file beside the manifest; they are now
    # `acceptance-criteria.md` in the issue's documents folder.
    older = [
        p for p in sorted((archive_root() / "docs" / "compass")
                          .glob("*/acceptance-criteria.md"))
        if not p.parent.name.endswith("-readable-specs-and-flow")
    ]
    if not older:
        return

    # The test is only meaningful if these specs really do lack a Summary.
    without = [p for p in older if "## Summary" not in p.read_text()]
    assert without, (
        "No pre-existing spec lacks a Summary, so this test proves nothing. If "
        "every spec has been backfilled, delete it."
    )

    # Nothing mechanical may need the section. Check each issue that predates
    # this change individually, skipping the active issue: an issue
    # mid-implement has not recorded its green run yet, and asserting
    # otherwise would make this test fail for the duration of every future
    # issue.
    current = archive_root() / ".compass" / "current-task"
    in_flight = current.read_text().strip() if current.is_file() else ""

    failures = []
    not_startable = {"queued", "parked", "abandoned"}
    for path in sorted(work.glob("*/manifest.yml")):
        slug = path.parent.name
        if slug == in_flight:
            continue
        # Unstarted or stopped work has no green run by definition - same
        # reason the active issue is excluded.
        try:
            status = (yaml.safe_load(path.read_text()) or {}).get("status", "active")
        except Exception:
            status = "active"
        if status in not_startable:
            continue
        result = subprocess.run(
            [sys.executable, str(ROOT / "cli" / "compass"), "check", "--issue", slug],
            capture_output=True, text=True, timeout=120, cwd=str(archive_root()),
        )
        if result.returncode != 0:
            failures.append(f"--- {slug} ---\n{result.stdout[-1200:]}")

    assert not failures, (
        f"specs predating the Summary section ({len(without)} of them) must keep "
        "passing:\n" + "\n".join(failures)
    )


def test_trc_f2_placeholder_scan_covers_summary_fields():
    """The placeholder scan is what catches an unfilled Summary, so it has to
    say the Summary is in scope."""
    body = _self_review()

    m = re.search(
        r"\*\*placeholder scan\*\*(.+?)(?=^\s*\d+\.|\Z)", body, re.M | re.S | re.I
    )
    assert m, "Placeholder scan item not found"

    assert "summary" in _flat(m.group(1)), (
        "The placeholder scan does not name the Summary as in scope - an unfilled "
        "Goal field would pass unnoticed"
    )


def test_trc_f3_rationale_for_no_subagent_loop():
    """The reason there is no subagent critic is recorded, so it is a decision
    on the record rather than an omission someone later 'fixes'."""
    body = _self_review()
    low = body.lower()

    assert re.search(r"25\s*(minutes|min)", low), (
        "The measured overhead of a subagent review loop is not recorded"
    )
    assert "requirements review" in low, (
        "The rationale does not name the requirements review as the "
        "existing review")
    assert "reviewer" in low, (
        "The rationale does not name the reviewer agent at Verify as the existing review"
    )
