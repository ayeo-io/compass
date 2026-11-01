"""The adapted `atdd` skill and the chain it describes (issue `atdd-skill`).

| Scenario | What it checks |
|---|---|
| `TRC-001` | the header names the source and lists each adaptation, one per line |
| `TRC-002` | each stage lands on refine, implement or `verify`; no stage or gate moves |
| `TRC-003` | one line, one DSL call; who owns each layer |
| `TRC-004` | the pilot's spec extracts as compass 8.0.4 extracted it |
| `TRC-005` | three skills describe one chain |
| `TRC-006` | a quick fix that needs a new DSL method goes back to assess |
| `TRC-007` | the text passes the vocabulary scans, and a planted breach fails them |
| `TRC-008` | the review questions sit in one file, one heading per stage |
| `TRC-009` | stage 1 ends in a red that unlocks no code |

The work item is ayeo-io/compass-delivery#322 [Add the atdd skill adapted
to Compass stages], part of ayeo-io/compass-delivery#307 [Make the
four-layer acceptance test model a Compass strategy for client-observable
behavior]. These are text tests: the skill is read by agents, so the words
are the behavior.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SKILLS = ROOT / "skills"
ATDD = SKILLS / "atdd" / "SKILL.md"
STAGE_REVIEWS = SKILLS / "atdd" / "references" / "stage-reviews.md"
FIXTURES = ROOT / "tests" / "fixtures" / "atdd-strategy"
CHAIN_SKILLS = ("atdd", "bdd-specification", "tdd-discipline")

sys.path.insert(0, str(ROOT / "tests"))
import test_terminology as terminology  # noqa: E402
import us_english_words as us_english  # noqa: E402


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _flat(text: str) -> str:
    """Whitespace collapsed and lower case, so a phrase wrapped across two
    lines still matches."""
    return " ".join(text.split()).lower()


def _section(text: str, heading: str, level: str = "## ") -> str:
    """The body under the first heading of `level` that contains `heading`,
    up to the next heading of the same or a higher level."""
    lines = text.splitlines()
    depth = len(level.strip())
    for start, line in enumerate(lines):
        if line.startswith(level) and heading.lower() in line.lower():
            body = []
            for later in lines[start + 1:]:
                found = re.match(r"^(#+) ", later)
                if found and len(found.group(1)) <= depth:
                    break
                body.append(later)
            return "\n".join(body)
    raise AssertionError(f"no {level.strip()} heading containing {heading!r}")


# --- Scenario `TRC-001` ---

def test_trc_001_the_header_names_the_source_and_each_adaptation():
    text = _text(ATDD)
    body = text.split("\n---\n", 1)[1]
    header = body.split("\n## ", 1)[0]
    flat = _flat(header)
    assert "adapted from" in flat and "`atdd` skill" in flat and "jed72" in flat, (
        "the header does not name the source skill and its author")
    lines = header.splitlines()
    items = [n for n, line in enumerate(lines) if line.startswith("- ")]
    assert len(items) >= 8, f"the header lists {len(items)} adaptations"
    for n in items:
        after = lines[n + 1] if n + 1 < len(lines) else ""
        assert after == "" or after.startswith("- "), (
            f"an adaptation runs over two lines: {lines[n]!r} / {after!r}")
    adaptations = _flat("\n".join(lines[n] for n in items))
    for topic in ("stage 1 at refine", "stage-reviews.md", "one dsl call",
                  "quick fix", "spike", "failure mode", "never reads",
                  "github", "us english"):
        assert topic in adaptations, f"no adaptation names {topic!r}"


# --- Scenario `TRC-002` ---

def test_trc_002_the_map_loads_atdd_at_refine_implement_and_verify():
    runtime = _section(_text(SKILLS / "compass-runtime" / "SKILL.md"),
                       "Which agent and which skill")
    bullets = [_flat(b) for b in re.split(r"\n(?=- )", runtime)]
    [atdd] = [b for b in bullets if "`atdd`" in b]
    for stage in ("stage 1 at refine", "stage 2 at implement",
                  "stage 3 at verify"):
        assert stage in atdd, f"the map does not load atdd for {stage}"
    assert "a real client can observe" in atdd, (
        "the map does not say where the strategy applies")
    for command, stage in (("refine", "stage 1"), ("implement", "stage 2"),
                           ("verify", "stage 3")):
        setup = _flat(_section(_text(ROOT / "commands" / f"{command}.md"),
                               "Setup"))
        assert "`atdd`" in setup and stage in setup, (
            f"commands/{command}.md does not load atdd for {stage}")


# The route shapes at commit a74e968, written down so the check holds on a
# shallow clone where that commit was never fetched.
STAGES_AT_A74E968 = ["assess", "define", "refine", "plan", "breakdown",
                     "implement", "verify", "ship"]
GATES_AT_A74E968 = {
    "spike": ["spike.conclude"],
    "quick-fix": ["verify.correctness", "verify.governance",
                  "verify.traceability"],
    "regular": ["verify.correctness", "verify.governance",
                "verify.traceability", "verify.regression", "verify.clarity",
                "verify.security"],
    "hotfix": ["verify.correctness", "verify.governance",
               "verify.traceability", "verify.regression", "verify.security"],
    "full": ["verify.correctness", "verify.governance", "verify.traceability",
             "verify.regression", "verify.security", "verify.clarity"],
}


def _route_shapes(text: str) -> dict:
    shapes = yaml.safe_load(text)["route_shapes"]
    return {name: {"stages": shape["stages"], "gates": shape["gates"]}
            for name, shape in shapes.items()}


def test_trc_002_the_routing_stage_list_is_unchanged():
    now = _route_shapes(_text(ROOT / "governance" / "routing-policy.yml"))
    assert sorted(now) == sorted(GATES_AT_A74E968), "an approach was added or removed"
    for name, shape in now.items():
        assert list(shape["stages"]) == STAGES_AT_A74E968, f"{name}: a stage moved"
        assert shape["gates"] == GATES_AT_A74E968[name], f"{name}: a gate moved"
    old = subprocess.run(["git", "show", "a74e968:governance/routing-policy.yml"],
                         cwd=ROOT, capture_output=True, text=True)
    if old.returncode == 0:
        assert now == _route_shapes(old.stdout), (
            "a stage weight or gate differs from commit a74e968")


# --- Scenario `TRC-003` ---

def test_trc_003_one_line_one_dsl_call_and_who_owns_each_layer():
    layers = _flat(_section(_text(ATDD), "The layers"))
    assert "each given, when or then line maps to exactly one dsl call" in layers
    assert "any role can write a scenario" in layers
    assert "engineers own the dsl and the drivers" in layers


# --- Scenario `TRC-004` ---

def test_trc_004_the_pilot_spec_extracts_as_8_0_4_did(tmp_path):
    """The expected output was produced by compass 8.0.4 in this layout. It
    is a refusal: the pilot's gherkin fences have no `Scenario:` line."""
    issue = tmp_path / ".compass" / "work" / "atdd-hook-pilot"
    issue.mkdir(parents=True)
    (issue / "manifest.yml").write_text(
        "schema_version: '3.0'\nissue: atdd-hook-pilot\n"
        "created: '2026-10-26'\nscenarios: []\n", encoding="utf-8")
    shutil.copyfile(FIXTURES / "atdd-hook-pilot-acceptance-criteria.md.txt",
                    issue / "acceptance-criteria.md")
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPASS_")}
    result = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "bdd", "extract",
         "--issue", "atdd-hook-pilot", "--out", "out.feature"],
        cwd=tmp_path, capture_output=True, env=env, timeout=60)
    expected = (FIXTURES / "atdd-hook-pilot-extract-8.0.4.stderr").read_bytes()
    assert result.returncode == 1
    assert result.stdout == b""
    assert result.stderr == expected
    assert not (tmp_path / "out.feature").exists()


# --- Scenario `TRC-005` ---

@pytest.mark.parametrize("skill", CHAIN_SKILLS)
def test_trc_005_three_skills_describe_one_chain(skill):
    text = _flat(_text(SKILLS / skill / "SKILL.md"))
    assert "scenario, dsl, driver, unit tests" in text, (
        f"{skill} does not describe the chain in order")
    assert ("refine settles each implied failure mode with the person or "
            "descopes it") in text, f"{skill} lacks the refine rule"
    assert "implement adds no scenario the specification does not state" in text, (
        f"{skill} lacks the implement rule")


# --- Scenario `TRC-006` ---

def test_trc_006_a_new_dsl_method_sends_a_quick_fix_back_to_assess():
    section = _flat(_section(_text(ATDD), "Quick fix and hotfix", "### "))
    assert "reuse existing dsl methods only" in section
    assert "needs a new dsl method is re-assessed" in section
    assert "`/compass:assess --reassess`" in section
    spike = _flat(_section(_text(ATDD), "Spike", "### "))
    assert "suspends the strategy as it suspends strategy `s2`" in spike
    # A quick-fix session reads its command and nothing else, so the rule
    # must be there too.
    command = _flat(_text(ROOT / "commands" / "quick-fix.md"))
    assert "new dsl method" in command and "`/compass:assess --reassess`" in command


# --- Scenario `TRC-007` ---

def _skill_copy(tmp_path: Path) -> Path:
    for skill in CHAIN_SKILLS:
        shutil.copytree(SKILLS / skill, tmp_path / "skills" / skill,
                        ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def _terminology_hits(root: Path, monkeypatch) -> list[str]:
    monkeypatch.setattr(terminology, "REPO_ROOT", root)
    files = sorted(p for skill in CHAIN_SKILLS
                   for p in (root / "skills" / skill).rglob("*.md"))
    return terminology._scan_files(files)


def _us_english_hits(root: Path) -> list:
    [group] = [g for g in us_english.GROUPS if g["paths"] == ["skills"]]
    hits = us_english.scan_group(group, root)
    return [h for h in hits if Path(h[0]).parts[1] in CHAIN_SKILLS]


def _plant(root: Path, line: str) -> int:
    path = root / "skills" / "atdd" / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text + line + "\n", encoding="utf-8")
    return text.count("\n") + 1


@pytest.mark.parametrize("state", ["as shipped", "bare S2", "behaviour"])
def test_trc_007_the_new_text_passes_the_vocabulary_scans(state, tmp_path, monkeypatch):
    root = _skill_copy(tmp_path)
    if state == "as shipped":
        assert _terminology_hits(root, monkeypatch) == []
        assert _us_english_hits(root) == [], us_english.render(_us_english_hits(root))
        return
    if state == "bare S2":
        line = _plant(root, "Red comes first, as S2 says.")
        hits = _terminology_hits(root, monkeypatch)
        assert len(hits) == 1, hits
        assert hits[0].startswith(f"skills/atdd/SKILL.md:{line}: "), hits
        assert "codes, bare" in hits[0], hits
        return
    line = _plant(root, "The test checks the " + "behav" + "iour a client sees.")
    hits = _us_english_hits(root)
    assert [(h[0], h[1]) for h in hits] == [("skills/atdd/SKILL.md", line)], hits
    assert us_english.render(hits).startswith(f"skills/atdd/SKILL.md:{line}: ")


# --- Scenario `TRC-008` ---

def test_trc_008_stage_reviews_has_one_heading_per_stage():
    text = _text(STAGE_REVIEWS)
    headings = re.findall(r"^## (.+)$", text, re.M)
    assert len(headings) == 3, headings
    for heading, (number, stage) in zip(headings, ((1, "refine"),
                                                   (2, "implement"),
                                                   (3, "verify"))):
        assert f"stage {number}" in heading.lower() and stage in heading.lower(), heading
        questions = [line for line in _section(text, heading).splitlines()
                     if line.startswith("- ") and line.rstrip().endswith("?")]
        assert questions, f"no review question under {heading!r}"
    assert "references/stage-reviews.md" in _text(ATDD)


# --- Scenario `TRC-009` ---

def test_trc_009_the_stage_1_red_unlocks_no_code():
    text = _text(ATDD)
    stage_1 = _flat(_section(text, "Stage 1", "### "))
    for phrase in ("imports the driver inside a pytest fixture",
                   "setup error in the junit report",
                   "module-level import in `conftest.py`",
                   "exit 4", "refused",
                   "a red recorded at refine does not unlock production code"):
        assert phrase in stage_1, f"stage 1 does not say {phrase!r}"
    flat = _flat(text)
    assert "compass never reads or parses project test code" in flat
    assert "layering test" in flat
