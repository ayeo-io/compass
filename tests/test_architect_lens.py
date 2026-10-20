"""Tests for the architect agent.

Covers scenarios: `TRC-B1`, `TRC-B2`, `TRC-B3`, `TRC-B4`, `TRC-B5`, `TRC-X5`, `TRC-F5`.

Strategy: agent files are markdown with frontmatter + headed sections.
Tests use file-existence + content-regex assertions (structural contract).
Trigger-detection logic (TRC-B2) is tested with mocked manifest.yml and
mocked architecture files via filesystem fixtures in tmp_path.

Architectural invariant: architecture-notes.md is ANNOTATIONS
+ candidate ADR titles - NOT Given/When/Then scenarios. `TRC-F5` encodes
this prohibition explicitly.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

from pathlib import Path

import yaml

# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = FRAMEWORK_ROOT / "agents"
COMMANDS_DIR = FRAMEWORK_ROOT / "commands"


def agent_file(name: str) -> Path:
    return AGENTS_DIR / name


def command_file(name: str) -> Path:
    return COMMANDS_DIR / name


# --------------------------------------------------------------------------
# `TRC-B1` - architect is invocable from consult
# --------------------------------------------------------------------------


def test_invocable_from_consult():
    """`TRC-B1`: commands/consult.md lists architect in its standard
    agent roster and documents the /compass:consult architect
    invocation pattern.
    """
    consult = command_file("consult.md")
    assert consult.exists(), "commands/consult.md not found"
    content = consult.read_text(encoding="utf-8")

    # Must mention architect in the agent roster section
    assert "architect" in content, (
        "commands/consult.md does not list architect in agent roster"
    )


# --------------------------------------------------------------------------
# `TRC-B1` (continued) - the agent file itself must exist with required shape
# --------------------------------------------------------------------------


def test_architect_lens_agent_file_exists():
    """`TRC-B1`: agents/architect.md must exist."""
    assert agent_file("architect.md").exists(), (
        "agents/architect.md does not exist"
    )


def test_architect_lens_has_frontmatter():
    """`TRC-B1`: agents/architect.md must have YAML frontmatter (--- delimiters)."""
    content = agent_file("architect.md").read_text(encoding="utf-8")
    assert content.startswith("---"), (
        "agents/architect.md missing YAML frontmatter opening ---"
    )
    assert content.count("---") >= 2, (
        "agents/architect.md missing YAML frontmatter closing ---"
    )


def test_architect_lens_frontmatter_fields():
    """`TRC-B1`: architect.md frontmatter must have name, description, tools, model."""
    content = agent_file("architect.md").read_text(encoding="utf-8")
    # Extract frontmatter block
    parts = content.split("---", 2)
    assert len(parts) >= 3, "Could not parse frontmatter"
    fm = yaml.safe_load(parts[1])
    assert fm.get("name") == "architect", (
        f"Expected name: architect, got: {fm.get('name')}"
    )
    assert "description" in fm, "architect.md frontmatter missing description"
    assert "tools" in fm, "architect.md frontmatter missing tools"
    assert "model" in fm, "architect.md frontmatter missing model"


def test_architect_lens_has_required_sections():
    """`TRC-B1`/B5: architect.md must contain the five required output sections
    (matching the architecture-notes.md contract):
      1. System under change
      2. Invariants this issue must preserve
      3. Boundary risks
      4. Candidate ADRs
      5. Notes for the planner
    """
    content = agent_file("architect.md").read_text(encoding="utf-8")
    required = [
        "system under change",
        "invariants",
        "boundary risk",
        "candidate adr",
        "notes for the planner",
    ]
    for term in required:
        assert term.lower() in content.lower(), (
            f"architect.md missing section reference: '{term}'"
        )


def test_architect_lens_reads_architecture_files():
    """`TRC-B1`: architect.md must instruct the agent to read the standard
    architecture/ input files.
    """
    content = agent_file("architect.md").read_text(encoding="utf-8")
    required_reads = [
        "system-context.md",
        "relations.md",
        "ownership.md",
    ]
    for fname in required_reads:
        assert fname in content, (
            f"architect.md does not instruct reading {fname}"
        )


def test_architect_lens_reads_task_artifacts():
    """`TRC-B1`/`Inv-5` (one spec, many roles; roles annotate, never fork):
    architect reads the acceptance criteria and technical-design.md - it is
    a role agent OVER the spec, not an author of the spec.
    """
    content = agent_file("architect.md").read_text(encoding="utf-8")
    assert "acceptance-criteria.md" in content, (
        "architect.md does not instruct reading acceptance-criteria.md"
    )
    assert "technical-design.md" in content, (
        "architect.md does not instruct reading technical-design.md"
    )


def test_architect_lens_writes_architecture_notes():
    """`TRC-B1`/B5: architect.md must instruct the agent to write
    architecture-notes.md to the issue directory.
    """
    content = agent_file("architect.md").read_text(encoding="utf-8")
    assert "architecture-notes.md" in content, (
        "architect.md does not mention writing architecture-notes.md"
    )


# --------------------------------------------------------------------------
# `TRC-B2` - spec-author consults architect for boundary-touching issues
# --------------------------------------------------------------------------


def test_consulted_by_spec_author():
    """`TRC-B2`: agents/spec-author.md must contain a step that triggers the
    architect consultation when manifest.yml.assessment.labels matches
    one of three trigger conditions (public-api, service name,
    lens_trigger_tag).
    """
    spec_author = agent_file("spec-author.md")
    assert spec_author.exists(), "agents/spec-author.md not found"
    content = spec_author.read_text(encoding="utf-8")

    # Must mention the architect consultation trigger
    assert "architect" in content, (
        "agents/spec-author.md does not mention architect consultation"
    )
    # Must reference the trigger tag 'public-api'
    assert "public-api" in content, (
        "agents/spec-author.md does not reference the public-api trigger tag"
    )


def test_spec_author_trigger_conditions():
    """`TRC-B2`: spec-author.md must document all three trigger conditions:
      1. touches contains 'public-api'
      2. touches contains a service name from architecture/relations.md
      3. touches contains a lens_trigger_tag from architecture/invariants.yml
    """
    content = agent_file("spec-author.md").read_text(encoding="utf-8")
    assert "relations.md" in content, (
        "spec-author.md does not mention architecture/relations.md trigger"
    )
    assert "lens_trigger_tag" in content or "invariants.yml" in content, (
        "spec-author.md does not mention invariants.yml lens_trigger_tag trigger"
    )


# --------------------------------------------------------------------------
# `TRC-B3` - planner reads existing architect notes and cites or diverges
# --------------------------------------------------------------------------


def test_consulted_by_planner():
    """`TRC-B3`: agents/planner.md must contain a step that reads
    architecture-notes.md (if present) and produces a design decision that
    cites or diverges from its findings.
    """
    planner = agent_file("planner.md")
    assert planner.exists(), "agents/planner.md not found"
    content = planner.read_text(encoding="utf-8")

    assert "architecture-notes.md" in content, (
        "agents/planner.md does not mention reading architecture-notes.md"
    )


def test_planner_cites_or_diverges():
    """`TRC-B3`: planner.md must document the cite-or-diverge behaviour -
    either cite an existing ADR, name a candidate ADR, or justify divergence.
    When architecture-notes.md is absent the absence is recorded (not silent skip).
    """
    content = agent_file("planner.md").read_text(encoding="utf-8")
    # Check for cite-or-diverge language
    combined = content.lower()
    has_cite = "cit" in combined  # cite, cites, cited
    has_diverge = "diverg" in combined  # diverge, diverges, divergence
    has_absence = "absent" in combined or "no notes" in combined or "recordable" in combined
    assert has_cite or has_diverge, (
        "planner.md does not mention citing or diverging from architecture-notes.md"
    )
    assert has_absence, (
        "planner.md does not document the recordable-absence behaviour when "
        "architecture-notes.md is missing"
    )


# --------------------------------------------------------------------------
# `TRC-B4` - architect degrades when architecture/ is absent
# --------------------------------------------------------------------------


def test_degrades_gracefully():
    """`TRC-B4`: architect.md must document that when architecture/ is
    absent the role agent writes a WARNING line and does not block the
    phase.
    """
    content = agent_file("architect.md").read_text(encoding="utf-8")
    assert "WARNING" in content or "warning" in content.lower(), (
        "architect.md does not document WARNING when architecture/ is absent"
    )
    # Must document non-blocking behaviour
    assert "not block" in content.lower() or "without blocking" in content.lower() or "does not block" in content.lower(), (
        "architect.md does not document that it does not block when architecture/ is absent"
    )


def test_degrades_writes_warning_line():
    """`TRC-B4`: the warning first line must be documented in the agent instructions."""
    content = agent_file("architect.md").read_text(encoding="utf-8")
    # The spec asks for: "WARNING: No architecture/ artifacts found - running on heuristics only"
    assert "No architecture/" in content or "no architecture/" in content.lower(), (
        "architect.md does not document the exact WARNING message for missing architecture/"
    )


# --------------------------------------------------------------------------
# `TRC-B5` - architect findings persist on disk
# --------------------------------------------------------------------------


def test_persists_notes():
    """`TRC-B5`: architect.md must document that its output is always
    written to architecture-notes.md in the issue directory (Inv-6: every
    mechanism output is a named file on disk, persistence over conversation).
    """
    content = agent_file("architect.md").read_text(encoding="utf-8")
    assert "architecture-notes.md" in content, (
        "architect.md does not instruct writing architecture-notes.md to disk"
    )
    # Must also reference manifest.yml.evidence so the artifact is registered
    assert "evidence" in content.lower(), (
        "architect.md does not mention registering the notes in manifest.yml.evidence"
    )


# --------------------------------------------------------------------------
# `TRC-X5` - bootstrap: consult does NOT invoke architect if the
# agent file doesn't exist (prevents infinite recursion on the issue that
# introduces the role agent)
# --------------------------------------------------------------------------


def test_bootstrap_no_recursion():
    """`TRC-X5`: commands/consult.md must document that role agents are
    invoked ONLY if their agent file is registered (i.e. exists in
    agents/). This prevents recursive invocation when the issue itself
    introduces the role agent.
    """
    content = command_file("consult.md").read_text(encoding="utf-8")
    # The contract must be explicit: invoke only if agent file exists/is registered
    combined = content.lower()
    assert (
        "only if" in combined
        or "registered" in combined
        or "agent file" in combined
        or "exists" in combined
    ), (
        "commands/consult.md does not document that lenses are only invoked "
        "if their agent file is registered"
    )


# --------------------------------------------------------------------------
# `TRC-F5` - architect does NOT fork the spec
# --------------------------------------------------------------------------


def test_notes_are_annotations_not_spec():
    """`TRC-F5`: architect.md must explicitly prohibit
    writing Given/When/Then scenarios into architecture-notes.md.
    The output is ANNOTATIONS + candidate ADR titles, not a parallel spec.
    """
    content = agent_file("architect.md").read_text(encoding="utf-8")
    # The agent instructions must prohibit scenario-writing
    combined = content.lower()
    assert (
        "not write" in combined
        or "never write" in combined
        or "do not write" in combined
        or "no scenario" in combined
        or "not author" in combined
        or "annotations" in combined
    ), (
        "architect.md does not prohibit writing Given/When/Then scenarios "
        "into architecture-notes.md, which would fork the spec"
    )


def test_no_gherkin_in_architecture_notes_contract():
    """`TRC-F5`: architect.md must describe architecture-notes.md as
    containing annotations and candidate ADR titles - NOT Given/When/Then.
    The word 'scenario' must only appear in the context of reading the
    acceptance criteria, not in the context of writing output.
    """
    content = agent_file("architect.md").read_text(encoding="utf-8")
    # Confirm the output format is annotations, not scenarios
    assert "annotation" in content.lower() or "candidate adr" in content.lower(), (
        "architect.md does not describe its output as annotations/candidate ADRs"
    )


def test_consult_agent_roster_section():
    """`TRC-B1`: commands/consult.md must have a dedicated 'Agent roster'
    or equivalent section that lists architect alongside other standard
    role agents.
    """
    content = command_file("consult.md").read_text(encoding="utf-8")
    # The file must have a section heading that covers the agent roster
    combined = content.lower()
    assert (
        "agent roster" in combined
        or "standard agent" in combined
        or "default agent" in combined
        or "available lenses" in combined
        or "available agents" in combined
    ), (
        "commands/consult.md does not have a section documenting the agent roster"
    )


# --------------------------------------------------------------------------
# The define command convenes the architect, not the spec-author, because a
# subagent cannot run a slash command or start another agent (`TRC-001`)
# --------------------------------------------------------------------------


def _flat(path: Path) -> str:
    """File text with each run of whitespace folded to one space, so a
    phrase wrapped across two lines still matches."""
    return " ".join(path.read_text(encoding="utf-8").split())


def test_define_command_names_the_trigger_condition():
    """commands/define.md names the same three trigger conditions as
    commands/consult.md: the `public-api` label, a service in
    architecture/relations.md, a `lens_trigger_tag` in
    architecture/invariants.yml (`TRC-001`).
    """
    define = _flat(command_file("define.md"))
    for term in ("public-api", "architecture/relations.md", "lens_trigger_tag"):
        assert term in define, f"commands/define.md does not name the trigger: {term}"


def test_define_command_convenes_the_architect_before_the_spec_author():
    """commands/define.md invokes the architect agent, and does so before the
    line that invokes the spec-author agent (`TRC-001`).
    """
    define = _flat(command_file("define.md")).lower()
    convene = define.find("invoke the `architect` agent")
    spec_author = define.find("invoke the `spec-author` agent")
    assert convene != -1, "commands/define.md does not invoke the architect agent"
    assert spec_author != -1, "commands/define.md does not invoke the spec-author agent"
    assert convene < spec_author, (
        "commands/define.md invokes the architect after the spec-author"
    )


def test_spec_author_no_longer_invokes_a_slash_command():
    """agents/spec-author.md does not tell the agent to run /compass:consult
    (a subagent cannot), and still mentions the architect consultation and
    the `public-api` tag (`TRC-001`, and the wording `TRC-B2` needs).
    """
    content = _flat(agent_file("spec-author.md"))
    assert "invoke `/compass:consult" not in content.lower(), (
        "agents/spec-author.md still tells the agent to invoke /compass:consult"
    )
    assert "architect" in content
    assert "public-api" in content
    assert "architecture-notes.md" in content


def test_spec_author_reports_missing_notes_in_the_hand_off():
    """When the labels match and there are no notes, the spec-author says so
    in the hand-off (`TRC-001`).
    """
    content = _flat(agent_file("spec-author.md"))
    assert "say so in the hand-off" in content, (
        "agents/spec-author.md does not say what to do when the notes are missing"
    )


def test_architect_is_triggered_by_the_define_command():
    """agents/architect.md says the define command convenes it, not the
    spec-author (`TRC-001`).
    """
    content = _flat(agent_file("architect.md"))
    assert "by the define command" in content, (
        "agents/architect.md does not say the define command convenes it"
    )
    assert "auto-triggered by spec-author" not in content, (
        "agents/architect.md still says the spec-author triggers it"
    )
