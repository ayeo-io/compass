"""Each agent's tool list matches the compass steps its instructions run.

An agent without Bash cannot run a `compass` verb. When its stage still needs
one, the agent writes the result into `manifest.yml` by hand, and one unquoted
` #` in a value breaks the YAML for every command on the issue (GitHub #569).
These tests pin which agents have a shell, and why.
"""

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTS = ROOT / "agents"
COMMANDS = ROOT / "commands"

# An agent has Bash when its own instructions, or the stage command it owns,
# tell it to run a compass verb. The reason sits next to each entry.
SHELL = {
    "spec-author": "define and refine run scenario add, scenario descope, "
                   "issue artifact set, issue decision add, issue lint and next",
    "planner": "it runs compass plan lint and policy show; plan registers "
               "technical-design.md and records decisions",
    "architect": "it registers architecture-notes.md with issue artifact set "
                 "and records it with evidence add",
    "builder": "implement runs tdd-red and tdd-green",
    "verifier": "verify runs the scenarios and the full suite",
    "reviewer": "it runs compass review-rule list and reads subtask packages",
    "router": "assess runs approach evaluate",
    "orchestrator": "breakdown runs the worktree scripts",
}
# A perspective agent reviews and writes documents; the calling session runs
# any compass verb its entry point names.
NO_SHELL = ("product-owner", "product-marketer")


def _frontmatter(name):
    text = (AGENTS / f"{name}.md").read_text(encoding="utf-8")
    return yaml.safe_load(text.split("---", 2)[1]), text


def _tools(name):
    fm, _ = _frontmatter(name)
    return [t.strip() for t in fm["tools"].split(",")]


def _flat(text):
    return " ".join(text.split())


def test_every_agent_file_is_classified():
    on_disk = {p.stem for p in AGENTS.glob("*.md")}
    assert on_disk == set(SHELL) | set(NO_SHELL)


def test_spec_author_has_a_shell_and_never_hand_edits_the_manifest():
    """TRC-001."""
    assert "Bash" in _tools("spec-author")
    _, text = _frontmatter("spec-author")
    flat = _flat(text)
    for verb in ("compass scenario add", "compass scenario descope",
                 "compass issue decision add", "compass issue lint", "compass next"):
        assert verb in flat, verb
    assert "never edit `manifest.yml` by hand" in flat
    define = _flat((COMMANDS / "define.md").read_text(encoding="utf-8"))
    assert "compass scenario add" in define
    assert "Write the `scenarios:` block of `manifest.yml`" not in define


@pytest.mark.parametrize("name", sorted(SHELL) + list(NO_SHELL))
def test_agent_shell_access_matches_the_compass_steps_it_runs(name):
    """TRC-002."""
    tools = _tools(name)
    if name in SHELL:
        assert "Bash" in tools, f"{name}: {SHELL[name]}"
        return
    assert "Bash" not in tools
    _, text = _frontmatter(name)
    flat = _flat(text)
    # An agent with no shell must not be told to run a compass verb.
    assert not re.search(r"\brun `compass ", flat, re.I), name
    assert "the calling session runs it" in flat
    assert "never edit `manifest.yml` by hand" in flat


@pytest.mark.parametrize("command", ["define", "plan"])
def test_define_and_plan_commands_allow_bash(command):
    """TRC-003."""
    text = (COMMANDS / f"{command}.md").read_text(encoding="utf-8")
    allowed = re.search(r"^allowed-tools: (.*)$", text, re.M).group(1)
    assert "Bash" in [t.strip() for t in allowed.split(",")]
