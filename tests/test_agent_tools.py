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

# An agent has the Skill tool when its own text tells it to load a skill.
# Without the tool it searches the disk for SKILL.md or goes without: a
# usage audit on 16 October 2026 found 3 of 119 builder runs read
# `tdd-discipline`, and 3 failed with "No such tool available: Skill".
SKILL = {
    "builder": "it loads tdd-discipline before it writes a line, and "
               "evidence-gates for traceability.md",
    "orchestrator": "it loads worktree-multiagent before it does anything",
    "planner": "it loads plan-authoring and governance-check, and "
               "worktree-multiagent for the decomposition",
    "spec-author": "it loads bdd-specification, behavior-mapping on "
                   "brownfield ground, and evidence-gates for traceability",
    "reviewer": "it loads evidence-gates before it reviews",
    "verifier": "it loads evidence-gates before it starts",
    "router": "it loads adaptive-routing before it reads the dimensions",
    "product-owner": "it loads intent-interview for role-translation.md",
    "product-marketer": "it loads intent-interview for role-translation.md",
}
# The architect's text names no skill to load.
NO_SKILL = ("architect",)

# Monitor waits on a background command. A full suite outlasts one Bash
# call, and without Monitor the builder polls with `sleep N; cat`, which
# Claude Code refuses: the same audit found all 45 builder Monitor calls
# failed with "No such tool available".
MONITOR = {
    "builder": "it waits on a full test suite that runs in the background",
}


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
    """`spec-author` has a shell and never hand-edits the manifest (`TRC-001`)."""
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
    """An agent has a shell exactly when it runs compass verbs (`TRC-002`)."""
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
    """The define and plan commands allow Bash (`TRC-003`)."""
    text = (COMMANDS / f"{command}.md").read_text(encoding="utf-8")
    allowed = re.search(r"^allowed-tools: (.*)$", text, re.M).group(1)
    assert "Bash(compass *)" in [t.strip() for t in allowed.split(",")]


def _commands_that_restrict_tools():
    """Commands that declare `allowed-tools`, as (name, tools, flat body)."""
    found = []
    for path in sorted(COMMANDS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^allowed-tools: (.*)$", text, re.M)
        if match:
            tools = [t.strip() for t in match.group(1).split(",")]
            found.append((path.stem, tools, " ".join(text.split("---", 2)[2].split())))
    return found


@pytest.mark.parametrize(
    "name, tools, body",
    _commands_that_restrict_tools(),
    ids=[name for name, _, _ in _commands_that_restrict_tools()],
)
def test_commands_that_run_compass_verbs_list_bash(name, tools, body):
    """A command whose text names a `compass` verb must list Bash."""
    if re.search(r"`compass [a-z]", body):
        assert "Bash(compass *)" in tools, f"{name}: its text runs a compass verb, so it needs Bash"


def _skills_it_is_told_to_load(name):
    """The skills named in a sentence of the agent's text that says "load"."""
    _, text = _frontmatter(name)
    skills = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
    named = set()
    for sentence in re.split(r"(?<=[.!?:])\s", _flat(text.split("---", 2)[2])):
        if re.search(r"\bload\b", sentence, re.I):
            named |= set(re.findall(r"`([a-z-]+)`", sentence)) & skills
    return named


def test_every_agent_is_classified_for_the_skill_tool():
    on_disk = {p.stem for p in AGENTS.glob("*.md")}
    assert on_disk == set(SKILL) | set(NO_SKILL)


@pytest.mark.parametrize("name", sorted(SKILL) + list(NO_SKILL))
def test_agent_has_the_skill_tool_exactly_when_told_to_load_a_skill(name):
    """An agent told to load a skill has the Skill tool (`TRC-001`)."""
    told = _skills_it_is_told_to_load(name)
    if name in SKILL:
        assert told, f"{name} is in SKILL but its text loads no skill"
        assert "Skill" in _tools(name), f"{name}: {SKILL[name]}"
        return
    assert not told, f"{name} is told to load {sorted(told)}: move it to SKILL"
    assert "Skill" not in _tools(name)


@pytest.mark.parametrize("name", sorted(SHELL) + list(NO_SHELL))
def test_only_the_named_agents_have_monitor(name):
    """The builder has Monitor to wait on a long suite (`TRC-001`)."""
    if name in MONITOR:
        assert "Monitor" in _tools(name), f"{name}: {MONITOR[name]}"
    else:
        assert "Monitor" not in _tools(name), name


def test_the_builder_reads_before_it_edits_and_edits_with_the_file_tools():
    """Builders viewed files with sed, grep, cat or head and then called Edit:
    775 "File has not been read yet" errors in 156 of 315 runs (`TRC-001`)."""
    _, text = _frontmatter("builder")
    assert "## Editing files" in text
    section = text.split("## Editing files", 1)[1].split("\n## ", 1)[0]
    flat = _flat(section)
    assert "Open a file with Read before you change it" in flat
    assert "Change files with Edit or Write and an absolute path" in flat
    assert "`sed -i`" in flat
    assert "one plain command per Bash call" in flat
    assert text.index("## Editing files") < text.index(
        "## How you behave per delivery approach")


def test_the_orchestrator_description_says_what_it_is_not_for():
    """20 of 26 orchestrator runs planned or fixed one whole issue (`TRC-001`)."""
    fm, _ = _frontmatter("orchestrator")
    assert "Not for planning or building one issue" in fm["description"]
    assert "planner or builder" in fm["description"]
