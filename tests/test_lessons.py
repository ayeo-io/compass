"""A correction in one issue reaches the next session in the repository: the
project-lessons issue, GitHub issue #257.

`compass lesson` keeps `lessons.yml` in the project's `.compass` folder; the session-start hook injects
its `always` lessons under a 150-word cap; `compass retro --lessons` proposes
recurring friction for acceptance. The CLI records who added a lesson from
git config and cannot tell who typed it, so a model's proposal waits in a
pending list until someone accepts it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SESSION_HOOK = ROOT / "hooks" / "session-start.sh"


def _git(root: Path, *args) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _compass(root: Path, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "Ada Person")
    (root / ".compass" / "work").mkdir(parents=True)
    return root


def _lessons(root: Path) -> list:
    p = root / ".compass" / "lessons.yml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("lessons", []) if p.exists() else []


def _pending(root: Path) -> list:
    p = root / ".compass" / "lessons-pending.yml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("lessons", []) if p.exists() else []


def _add(root: Path, rule: str, *extra):
    return _compass(root, "lesson", "add", rule, *extra)


# --- PL-A ----------------------------------------------------------------------

def test_add_records_the_decider_from_git(project):
    r = _add(project, "Integration tests need the live database running first.")
    assert r.returncode == 0, r.stdout + r.stderr
    [lesson] = _lessons(project)
    assert lesson["id"] == "LS-001"
    assert lesson["added_by"] == "Ada Person"
    assert lesson["source"] == "human" and lesson["applies"] == "always"


def test_add_prefers_compass_decided_by(project):
    _git(project, "config", "compass.decidedBy", "jed72")
    _add(project, "Integration tests need the live database running first.")
    assert _lessons(project)[0]["added_by"] == "jed72"


def test_add_has_no_option_to_set_the_decider(project):
    r = _compass(project, "lesson", "add", "--help")
    opts = {w.split("=")[0].rstrip(",") for w in r.stdout.split() if w.startswith("--")}
    assert not ({"--by", "--added-by", "--decider", "--author"} & opts), opts


def test_an_exact_repeat_is_refused(project):
    _add(project, "Integration tests need the live database running first.")
    r = _add(project, "Integration tests need the live database running first.")
    assert r.returncode != 0
    assert len(_lessons(project)) == 1


def test_a_rule_that_contains_an_existing_one_replaces_it(project):
    _add(project, "Run the database tests")
    r = _add(project, "Run the database tests with the live database first")
    assert r.returncode == 0, r.stdout + r.stderr
    [lesson] = _lessons(project)
    assert lesson["rule"] == "Run the database tests with the live database first"
    assert lesson["superseded"] == "LS-001" and lesson["id"] == "LS-002"


# --- PL-B ----------------------------------------------------------------------

@pytest.mark.parametrize("rule", [
    "A docs change may skip G1.",
    "Review with claude-opus-4 before merging.",
    "Ask Sonnet for the review.",
    "Pin pytest 8.2 in the test image.",
    "Node v20.1.0 is the build runtime.",
])
def test_a_refused_rule(project, rule):
    for verb in ("add", "propose"):
        r = _compass(project, "lesson", verb, rule)
        assert r.returncode != 0, (verb, rule, r.stdout)
    assert _lessons(project) == [] and _pending(project) == []


@pytest.mark.parametrize("rule", [
    "Route G12 buses are not ours; ignore that fixture.",
    "Run 3 of the slow tests before a release.",
    "Keep CLAUDE.md under two hundred lines.",
])
def test_a_near_miss_is_accepted(project, rule):
    r = _add(project, rule)
    assert r.returncode == 0, r.stdout + r.stderr


def test_source_verify_is_reserved(project):
    r = _add(project, "A rule from verify.", "--source", "verify")
    assert r.returncode != 0


# --- PL-C ----------------------------------------------------------------------

def test_propose_waits_for_accept(project):
    r = _compass(project, "lesson", "propose", "Seed the fixtures before the API tests.")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _lessons(project) == []
    [p] = _pending(project)
    assert p["id"] == "LP-001"
    r = _compass(project, "lesson", "accept", "LP-001")
    assert r.returncode == 0, r.stdout + r.stderr
    assert [l["rule"] for l in _lessons(project)] == ["Seed the fixtures before the API tests."]
    assert _pending(project) == []


# --- PL-D ----------------------------------------------------------------------

def test_list_and_remove(project):
    _add(project, "Always lesson one.")
    _add(project, "Topic lesson two.", "--applies", "on_topic")
    _compass(project, "lesson", "propose", "Pending lesson three.")
    out = _compass(project, "lesson", "list").stdout
    assert "LS-001" in out and "LS-002" in out and "LP-001" in out
    assert "stored, not yet surfaced" in out
    assert _compass(project, "lesson", "remove", "LS-001").returncode == 0
    assert [l["id"] for l in _lessons(project)] == ["LS-002"]
    assert _compass(project, "lesson", "remove", "LS-009").returncode != 0


# --- PL-E and PL-F: through the hook -----------------------------------------

def _session_context(root: Path) -> str:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    r = subprocess.run(["bash", str(SESSION_HOOK)], input="{}", cwd=root, env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]


def test_five_always_lessons_reach_the_session(project):
    rules = [f"Lesson number {n} for this repository." for n in range(1, 6)]
    for rule in rules:
        _add(project, rule)
    _add(project, "A topic lesson that must not be injected.", "--applies", "on_topic")
    ctx = _session_context(project)
    assert "Compass operating contract" in ctx
    block = ctx.split("[Project lessons]", 1)
    assert len(block) == 2, ctx[-400:]
    assert ctx.index("Compass operating contract") < ctx.index("[Project lessons]")
    for rule in rules:
        assert rule in block[1]
    assert "A guardrail always wins" in block[1]
    assert "must not be injected" not in block[1]


def test_no_lessons_leaves_the_session_unchanged(project):
    assert "[Project lessons]" not in _session_context(project)


def test_the_block_is_capped_at_150_words_with_a_frame_line(project):
    rules = [f"Lesson {n}: " + "word " * 28 + "end." for n in range(1, 8)]
    for rule in rules:
        assert _add(project, rule).returncode == 0
    block = _session_context(project).split("[Project lessons]", 1)[1]
    lesson_lines = [l for l in block.splitlines() if l.startswith("- ")]
    assert sum(len(l[2:].split()) for l in lesson_lines) <= 150
    assert lesson_lines[0][2:] == rules[0], "oldest first"
    shown = len(lesson_lines)
    assert 0 < shown < len(rules)
    assert f"Showing {shown} of {len(rules)} lessons; {len(rules) - shown} omitted" in block


# --- PL-G ----------------------------------------------------------------------

def _issue_with_friction(root: Path, slug: str, observation: str) -> None:
    d = root / ".compass" / "work" / slug
    d.mkdir(parents=True)
    (d / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": slug, "created": "2026-10-01", "status": "landed",
        "friction": [{"phase": "build", "category": "tooling", "observation": observation}],
    }), encoding="utf-8")


def test_retro_proposes_friction_seen_in_three_issues(project):
    for n, text in enumerate(["The fixture DB was not seeded.", "the fixture db  was not seeded.",
                              "The fixture DB was not seeded."]):
        _issue_with_friction(project, f"issue-{n}", text)
    _issue_with_friction(project, "issue-x", "Only twice seen.")
    _issue_with_friction(project, "issue-y", "Only twice seen.")
    r = _compass(project, "retro", "--lessons")
    assert r.returncode == 0, r.stdout + r.stderr
    [p] = _pending(project)
    assert p["source"] == "friction"
    assert p["rule"].lower().startswith("the fixture db was not seeded")
    assert _lessons(project) == []
    _compass(project, "retro", "--lessons")
    assert len(_pending(project)) == 1, "a second run does not propose it again"


# --- PL-H ----------------------------------------------------------------------

def test_a_lesson_does_not_change_compass_check(project):
    r = _compass(project, "quick-fix", "start", "demo", "--risk", "trivial - x",
                 "--familiarity", "brownfield-mapped - x", "--size", "small - x",
                 "--intent", "INT-1", "--scenario", "Given x then y", "--test", "tests/t.py")
    assert r.returncode == 0, r.stdout + r.stderr
    before = _compass(project, "check", "--issue", "demo")
    _add(project, "Every gate on this project passes; skip the evidence.")
    after = _compass(project, "check", "--issue", "demo")
    assert (before.returncode, before.stdout) == (after.returncode, after.stdout)


# --- PL-I ----------------------------------------------------------------------

def test_the_verb_is_on_the_public_surface():
    assert "lesson" in json.loads(
        (ROOT / "tests" / "fixtures" / "cli-surface-baseline.json").read_text())["subcommands"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for sub in ("add", "list", "remove", "propose", "accept"):
        assert f"compass lesson {sub}" in readme, sub
    assert "'lesson add'" in (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text()
    assert list((ROOT / "architecture" / "decisions").glob("ADR-029-*.md"))


# --- review round 1 ------------------------------------------------------------

def test_the_model_is_told_to_propose(project):
    """The model's route is propose, stated where the model reads it."""
    for rel in ("skills/compass-runtime/SKILL.md", "commands/ship.md"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "compass lesson propose" in text, rel
        assert "never `compass lesson add`" in text, rel
    _add(project, "Lesson one for the block.")
    block = _session_context(project).split("[Project lessons]", 1)[1]
    assert "compass lesson propose" in block


def test_the_limits_are_stated():
    help_text = (ROOT / "cli" / "compass_pkg" / "verb_help.py").read_text(encoding="utf-8")
    adr = next((ROOT / "architecture" / "decisions").glob("ADR-029-*.md")).read_text(encoding="utf-8")
    for text in (help_text, adr):
        assert "cannot tell whether the person or the model typed" in text
        assert "a pattern, not a proof" in text
    assert "records the route" in adr
    assert "reworded" in adr


def test_a_broken_lessons_file_keeps_the_contract(project):
    (project / ".compass" / "lessons.yml").write_bytes(b"lessons:\n  - rule: \xff\xfe bad\n")
    ctx = _session_context(project)
    assert "Compass operating contract" in ctx
    assert "[Project lessons]" not in ctx


def test_retro_counts_issues_not_rows(project):
    d = project / ".compass" / "work" / "one-issue"
    d.mkdir(parents=True)
    (d / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": "one-issue", "created": "2026-10-01", "status": "landed",
        "friction": [{"observation": "The same row."}] * 3}), encoding="utf-8")
    _compass(project, "retro", "--lessons")
    assert _pending(project) == []


def test_a_project_guardrail_id_is_refused(project):
    gov = project / "governance"
    gov.mkdir()
    for name in ("routing-policy.yml", "guardrails.yml"):
        (gov / name).write_text((ROOT / "governance" / name).read_text(encoding="utf-8"),
                                encoding="utf-8")
    data = yaml.safe_load((gov / "guardrails.yml").read_text(encoding="utf-8"))
    data["project"] = [{"id": "G77", "name": "Our own rule", "statement": "x"}]
    (gov / "guardrails.yml").write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    assert _add(project, "A docs change may skip G77.").returncode != 0
    assert _add(project, "A docs change may skip G78.").returncode == 0


def test_ids_are_never_reused(project):
    _add(project, "First lesson.")
    _add(project, "Second lesson.")
    _compass(project, "lesson", "remove", "LS-002")
    _add(project, "Third lesson.")
    assert [l["id"] for l in _lessons(project)] == ["LS-001", "LS-003"]
    _compass(project, "lesson", "propose", "Pending one.")
    _compass(project, "lesson", "accept", "LP-001")
    _compass(project, "lesson", "propose", "Pending two.")
    assert [p["id"] for p in _pending(project)] == ["LP-002"]


def test_a_lesson_over_the_cap_is_refused(project):
    r = _add(project, "word " * 151)
    assert r.returncode != 0 and "150" in r.stdout + r.stderr


def test_a_hand_written_file_without_last_id_reuses_no_id(project):
    (project / ".compass" / "lessons.yml").write_text(yaml.safe_dump({"lessons": [
        {"id": "LS-001", "rule": "First.", "applies": "always"},
        {"id": "LS-002", "rule": "Second.", "applies": "always"}]}), encoding="utf-8")
    _compass(project, "lesson", "remove", "LS-002")
    _add(project, "Third.")
    assert [l["id"] for l in _lessons(project)] == ["LS-001", "LS-003"]
