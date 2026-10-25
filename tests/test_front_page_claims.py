"""The facts the front page states hold in the code.

`README.md`, `docs/index.md` and `docs/quickstart.md` are the first text a
plugin-directory reviewer and a new adopter read. A renamed command or
approach, or a changed count, leaves them stating something that is no longer
true, and nothing else checks them for it (delivery-record #261, #138). This
checks only what a machine can decide: command names, approach and stage
names, and counts. Whether a prose claim holds is decided by the claim audit,
not here.

The scenarios, `TRC-002` to `TRC-004`, are in
front-page-plain-english/acceptance-criteria.md.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
FRONT_PAGE = ("README.md", "docs/index.md", "docs/quickstart.md")
PRESET = ROOT / "governance" / "presets" / "default"

_NUMBERS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
            "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_SLASH = re.compile(r"/compass:([a-z][a-z-]*)")
_VERB = re.compile(r"`compass ([a-z][a-z-]*)")
_APPROACH = re.compile(r"\b(?:the|a|an) ([a-z][a-z-]*(?: fix)?) approach\b", re.I)
_COUNT = re.compile(r"\b(one|two|three|four|five|six|seven|eight|nine|ten) "
                    r"(guardrails|stages|approaches)\b", re.I)
# Words that stand before "approach" without naming one.
_NOT_A_NAME = {"delivery", "computed", "final", "same", "first", "lighter",
               "heavier", "heavy", "light", "chosen", "whole", "new", "other",
               "right", "technical", "different", "given", "this", "that"}


def _truth() -> dict:
    gates = yaml.safe_load((PRESET / "gates.yml").read_text(encoding="utf-8"))["gates"]
    stages = yaml.safe_load((PRESET / "stages.yml").read_text(encoding="utf-8"))["stages"]
    approaches = yaml.safe_load(
        (PRESET / "approaches.yml").read_text(encoding="utf-8"))["approaches"]
    help_text = subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), "--help"],
                               capture_output=True, text=True, timeout=60).stdout
    verbs = set(re.search(r"\{([a-z,_-]+)\}", help_text).group(1).split(","))
    return {
        "commands": {p.stem for p in (ROOT / "commands").glob("*.md")},
        "verbs": verbs,
        "approaches": set(approaches),
        "counts": {
            "guardrails": sum(1 for k, v in gates.items()
                              if v.get("kind") == "guardrail" and k.startswith("G")),
            "stages": len(stages),
            "approaches": len(approaches),
        },
    }


def problems(text: str, truth: dict) -> list[str]:
    """Each fact in `text` that the code contradicts."""
    found = []
    for name in sorted(set(_SLASH.findall(text))):
        if name not in truth["commands"]:
            found.append(f"/compass:{name} has no file in commands/")
    for verb in sorted(set(_VERB.findall(text))):
        if verb not in truth["verbs"]:
            found.append(f"compass {verb} is not a CLI verb")
    for name in sorted({m.lower() for m in _APPROACH.findall(text)}):
        key = name.replace(" ", "-")
        if name in _NOT_A_NAME or key in truth["approaches"]:
            continue
        found.append(f"the {name} approach is not an approach in the policy")
    for word, what in _COUNT.findall(text):
        stated, actual = _NUMBERS[word.lower()], truth["counts"][what.lower()]
        if stated != actual:
            found.append(f"{word} {what}, but the policy has {actual}")
    return found


@pytest.fixture(scope="module")
def truth():
    return _truth()


@pytest.mark.parametrize("rel", FRONT_PAGE)
def test_trc_002_every_named_command_exists(rel, truth):
    """Scenario `TRC-002`: each slash command and CLI verb the page names
    exists."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    bad = [p for p in problems(text, truth) if "commands/" in p or "CLI verb" in p]
    assert not bad, f"{rel}: {bad}"


@pytest.mark.parametrize("rel", FRONT_PAGE)
def test_trc_003_names_and_counts_match_the_policy(rel, truth):
    """Scenario `TRC-003`: each approach the page names exists, and each count
    of guardrails, stages or approaches equals the policy's."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    bad = [p for p in problems(text, truth) if "approach" in p or "policy has" in p]
    assert not bad, f"{rel}: {bad}"


def test_trc_004_a_planted_wrong_fact_is_reported(truth):
    """Scenario `TRC-004`: the check fails on a wrong command, approach and
    count, so a passing run means something."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    planted = (text + "\nRun /compass:frobnicate, or `compass frobnicate`. The "
               "medium approach applies. Six guardrails hold.\n")
    found = problems(planted, truth)
    assert any("/compass:frobnicate" in p for p in found), found
    assert any("compass frobnicate" in p for p in found), found
    assert any("the medium approach" in p for p in found), found
    assert any("Six guardrails" in p for p in found), found


def test_trc_002_the_repository_map_names_every_agent_and_hook():
    """Scenario `TRC-002`: the README's map of the repository lists each
    agent and each hook script, so a reader does not miss one."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    block = text.split("## What the repository contains", 1)[1].split("```", 2)[1]
    flat = " ".join(block.split())
    missing = [p.stem for p in (ROOT / "agents").glob("*.md") if p.stem not in flat]
    missing += [p.name for p in (ROOT / "hooks").glob("*.sh") if p.name not in flat]
    assert not missing, f"the README's repository map leaves out {missing}"


@pytest.mark.parametrize("rel", FRONT_PAGE)
def test_trc_003_versions_match_the_code(rel):
    """Scenario `TRC-003`: the Python floor and the shipped default's major
    version the page states are the ones the code uses. The default has its
    own version, which can lag the CLI's: CLI 8.0.0 ships default 7."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    preset = yaml.safe_load((PRESET / "preset.yml").read_text(encoding="utf-8"))
    major = str(preset["version"]).split(".")[0]
    for found in re.findall(r"compass:default@(\d+)", text):
        assert found == major, f"{rel} names compass:default@{found}; this is {major}"
    floor = re.search(r"Python (3\.\d+) or later",
                      (ROOT / "hooks" / "session-start.sh").read_text(encoding="utf-8"))
    for stated in re.findall(r"needs Python ([0-9.]+)", text):
        assert stated.rstrip(".") == floor.group(1), (
            f"{rel} says Compass needs Python {stated}; the floor is {floor.group(1)}")
    assert not re.search(r"needs Python 3(?![.\d])", text), (
        f"{rel} says Compass needs Python 3 with no floor")


# A paragraph that makes an absolute claim about guardrails or approvals.
_ABSOLUTE = re.compile(r"\b(every|never|cannot|always|only way|no assessment)\b", re.I)
_SUBJECT = re.compile(r"\bguardrails?\b|\bapprov(?:al|e)s?\b", re.I)


@pytest.mark.parametrize("rel", ("README.md", "docs/index.md"))
def test_trc_001_each_guarantee_links_the_safety_contract(rel):
    """Scenario `TRC-001`: a sentence on the front page that promises
    something absolute about guardrails or approvals sits in a paragraph that
    links the safety contract, where the limit of the promise is stated. This
    checks that a reader can find the limit, not that the wording is true; the
    claim audit decides that. The quickstart is a walkthrough, so its claims
    are left to the audit."""
    text = (ROOT / rel).read_text(encoding="utf-8")
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    bad = []
    for para in re.split(r"\n\s*\n", text):
        if para.lstrip().startswith(("#", "|", "<")) or "safety-contract.md" in para:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", " ".join(para.split())):
            if _ABSOLUTE.search(sentence) and _SUBJECT.search(sentence):
                bad.append(sentence[:100])
    assert not bad, f"{rel}: these sentences promise without the limit: {bad}"


def test_trc_001_the_explainer_states_the_readme_guardrail_sentence():
    """Scenario `TRC-001`: the image under the README's opening repeats its
    guardrail sentence, so the picture cannot keep a claim the text dropped."""
    svg = (ROOT / "assets" / "compass-explainer.svg").read_text(encoding="utf-8")
    line = re.search(r'class="guard"[^>]*>([^<]+)<', svg).group(1)
    readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
    assert line.replace("Five default guardrails", "Five guardrails").rstrip(".") in readme, (
        f"the explainer says {line!r}, which the README does not")
