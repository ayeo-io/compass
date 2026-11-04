"""The architect perspective, as the consult and define commands state it.

Covers scenarios: `TRC-B1` and `TRC-001`. Before 9.0.0 this file also tested
the architect agent's file (`TRC-B2` to `TRC-B5`, `TRC-X5`, `TRC-F5`). 9.0.0 removed
the agent files (ADR-090): the session takes the architect's perspective
itself, so those tests left with the file they read.
"""
from __future__ import annotations

from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = FRAMEWORK_ROOT / "commands"


def command_file(name: str) -> Path:
    return COMMANDS_DIR / name


def _flat(path: Path) -> str:
    """File text with each run of whitespace folded to one space, so a
    phrase wrapped across two lines still matches."""
    return " ".join(path.read_text(encoding="utf-8").split())


def test_invocable_from_consult():
    """`TRC-B1`: commands/consult.md lists architect in its roster and
    documents the /compass:consult architect invocation pattern."""
    content = command_file("consult.md").read_text(encoding="utf-8")
    assert "| `architect` | `/compass:consult architect` |" in content
    assert "/compass:consult architect" in content


def test_consult_roster_section():
    """`TRC-B1`: commands/consult.md has a section that lists architect
    alongside the other role perspectives."""
    content = command_file("consult.md").read_text(encoding="utf-8")
    assert "## Perspective roster" in content
    roster = content.split("## Perspective roster", 1)[1].split("\n## ", 1)[0]
    for role in ("product-owner", "product-marketer", "architect", "planner", "reviewer"):
        assert f"`{role}`" in roster, role


def test_define_command_names_the_trigger_condition():
    """commands/define.md names the same three trigger conditions as
    commands/consult.md: the `public-api` label, a service in
    architecture/relations.md, a `lens_trigger_tag` in
    architecture/invariants.yml (`TRC-001`)."""
    define = _flat(command_file("define.md"))
    for term in ("public-api", "architecture/relations.md", "lens_trigger_tag"):
        assert term in define, f"commands/define.md does not name the trigger: {term}"


def test_define_command_takes_the_architect_perspective_before_the_scenarios():
    """commands/define.md takes the architect's perspective first, and writes
    architecture-notes.md, before the stage writes scenarios (`TRC-001`)."""
    define = _flat(command_file("define.md")).lower()
    first = define.find("take the architect's perspective first")
    notes = define.find("write `architecture-notes.md`")
    assert first != -1, "commands/define.md does not take the architect's perspective first"
    assert notes > first, "commands/define.md does not write architecture-notes.md after it"
