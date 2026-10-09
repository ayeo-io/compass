"""The agent records friction it observed, apart from a person's.

Ship captures friction from signals the CLI computed and one optional line
from the person. `compass issue friction` lets the agent file a note during
the run under a strict bar: it names evidence in the issue folder
and a one-line fix, at most three per issue, never the same category and stage
twice. Agent notes are counted in their own column and never make a lesson on
their own. A note about a step a guardrail backs is accepted but reported as
such, because friction cannot change a guardrail.

Scenario ids: `TRC-001` to `TRC-005` (issue `agent-recorded-friction`).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "tests"))


def _compass(root: Path, *args):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=root,
                          capture_output=True, text=True)


def _manifest(root: Path, slug: str, friction=None) -> Path:
    d = root / ".compass" / "work" / slug
    (d / "evidence").mkdir(parents=True, exist_ok=True)
    (d / "evidence" / "red.log").write_text("1 failed\n", encoding="utf-8")
    data = {"schema_version": "2.0", "task": slug, "created": "2026-10-06",
            "status": "active"}
    if friction is not None:
        data["friction"] = friction
    (d / "manifest.yml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return d / "manifest.yml"


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    (root / ".compass" / "work").mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    return root


def _note(root, *extra, category="over-weight", stage="assess",
          observed="evidence/red.log", fix="Skip the second plan read on a quick fix"):
    args = ["issue", "friction", "--issue", "fix-a"]
    if category:
        args += ["--category", category]
    if stage:
        args += ["--stage", stage]
    if observed:
        args += ["--observed", observed]
    if fix is not None:
        args += ["--fix", fix]
    return _compass(root, *args, *extra)


def _friction(root, slug="fix-a"):
    path = root / ".compass" / "work" / slug / "manifest.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("friction") or []


# --- the note and its bar (`TRC-001`) ---

def test_trc_001_a_note_is_recorded_as_agent_friction(project):
    _manifest(project, "fix-a")
    result = _note(project)
    assert result.returncode == 0, result.stdout + result.stderr
    [entry] = _friction(project)
    assert entry["source"] == "agent"
    assert entry["category"] == "over-weight" and entry["stage"] == "assess"
    assert "phase" not in entry
    assert entry["evidence"] == "evidence/red.log"
    assert entry["proposed_change"] == "Skip the second plan read on a quick fix"


def test_trc_001_a_fourth_note_is_refused(project):
    _manifest(project, "fix-a")
    for stage in ("assess", "define", "implement"):
        assert _note(project, stage=stage).returncode == 0
    result = _note(project, stage="verify")
    assert result.returncode != 0
    assert "three" in result.stderr, result.stderr
    assert len(_friction(project)) == 3


def test_trc_001_the_same_category_and_stage_twice_is_refused(project):
    _manifest(project, "fix-a")
    assert _note(project).returncode == 0
    result = _note(project, fix="Another fix for the same thing")
    assert result.returncode != 0
    assert "over-weight" in result.stderr and "assess" in result.stderr, result.stderr
    assert len(_friction(project)) == 1


def test_trc_001_a_stored_note_keyed_phase_counts_as_the_same_stage(project):
    """A note a release before 6.0.0 stored with the old key is read as
    `stage`, so a second note for it is refused, and the save rewrites it."""
    _manifest(project, "fix-a", [{"phase": "assess", "category": "over-weight",
                                  "source": "agent", "evidence": "evidence/red.log",
                                  "proposed_change": "Skip the second plan read"}])
    result = _note(project, fix="Another fix for the same thing")
    assert result.returncode != 0
    assert "already recorded" in result.stderr, result.stderr
    other = _note(project, stage="define")
    assert other.returncode == 0, other.stderr
    assert [e["stage"] for e in _friction(project)] == ["assess", "define"]
    assert all("phase" not in e for e in _friction(project))


@pytest.mark.parametrize("change, words", [
    ({"fix": None}, "--fix"),
    ({"fix": "x" * 161}, "160"),
    ({"observed": "evidence/missing.log"}, "evidence/missing.log"),
])
def test_trc_001_a_note_without_its_evidence_or_fix_is_refused(project, change, words):
    _manifest(project, "fix-a")
    result = _note(project, **change)
    assert result.returncode != 0
    assert words in result.stdout + result.stderr, result.stdout + result.stderr
    assert _friction(project) == []


def test_trc_001_a_devlog_line_is_accepted_as_evidence(project):
    # Devlog lines carry no ids, so a note cites one by its line number.
    _manifest(project, "fix-a")
    devlog = project / ".compass" / "work" / "fix-a" / "devlog.md"
    devlog.write_text("# Devlog\n\nThe plan was read twice.\n", encoding="utf-8")
    assert _note(project, observed="devlog.md:3").returncode == 0
    assert _note(project, stage="define", observed="devlog.md:9").returncode != 0


# --- its own column (`TRC-002`) ---

def test_trc_002_retro_counts_agent_friction_apart(project):
    fix = "Skip the second plan read on a quick fix"
    for n in range(2):
        _manifest(project, f"person-{n}", [{"category": "over-weight", "source": "human",
                                            "observation": "slow", "proposed_change": fix}])
    for n in range(3):
        _manifest(project, f"agent-{n}", [{"category": "over-weight", "source": "agent",
                                           "stage": "plan", "evidence": "evidence/red.log",
                                           "proposed_change": fix}])
    result = _compass(project, "retro", "--friction", "--format", "json")
    agg = json.loads(result.stdout)
    assert agg["by_category"] == {"over-weight": 2}
    assert agg["agent_by_category"] == {"over-weight": 3}
    [cluster] = agg["below_threshold"] if agg["below_threshold"] else agg["recurring"]
    assert cluster["count"] == 2 and cluster["agent_count"] == 3, cluster
    text = _compass(project, "retro", "--friction").stdout
    assert "over-weight     : 2 | 3" in text, text


# --- never a lesson alone (`TRC-003`) ---

def _agent_row(fix):
    return {"category": "over-weight", "source": "agent", "stage": "plan",
            "evidence": "evidence/red.log", "proposed_change": fix}


def test_trc_003_agent_notes_alone_propose_no_lesson(project):
    fix = "Skip the second plan read on a quick fix"
    for n in range(3):
        _manifest(project, f"issue-{n}", [_agent_row(fix)])
    result = _compass(project, "retro", "--lessons")
    assert result.returncode == 0 and "no friction recurs" in result.stdout, result.stderr
    assert not (project / ".compass" / "lessons-pending.yml").exists()


def test_trc_003_one_person_entry_lets_the_agent_notes_count(project):
    fix = "Skip the second plan read on a quick fix"
    for n in range(2):
        _manifest(project, f"issue-{n}", [_agent_row(fix)])
    _manifest(project, "issue-2", [{"category": "over-weight", "source": "human",
                                    "observation": fix}])
    _compass(project, "retro", "--lessons")
    pending = yaml.safe_load((project / ".compass" / "lessons-pending.yml").read_text())
    assert [p["rule"] for p in pending["lessons"]] == [fix]


# --- guardrail notes (`TRC-004`) ---

def test_trc_004_a_guardrail_note_is_accepted_and_reported_as_such(project):
    _manifest(project, "fix-a")
    result = _note(project, fix="Let a quick fix skip the failing test first")
    assert result.returncode == 0, result.stderr
    assert "guardrail, not changeable by friction" in result.stdout
    [entry] = _friction(project)
    assert entry["guardrail"] is True


def test_trc_004_a_named_guardrail_flag_marks_the_note(project):
    _manifest(project, "fix-a")
    assert _note(project, "--guardrail", fix="Read the plan once").returncode == 0
    assert _friction(project)[0]["guardrail"] is True


def test_trc_004_guardrail_notes_never_count(project):
    fix = "Let a quick fix skip the failing test first"
    row = {**_agent_row(fix), "guardrail": True}
    for n in range(2):
        _manifest(project, f"issue-{n}", [row])
    _manifest(project, "issue-2", [{"category": "over-weight", "source": "human",
                                    "observation": fix}])
    result = _compass(project, "retro", "--lessons")
    assert result.returncode == 0 and "no friction recurs" in result.stdout, result.stderr
    assert not (project / ".compass" / "lessons-pending.yml").exists()
    agg = json.loads(_compass(project, "retro", "--friction", "--format", "json").stdout)
    assert agg["guardrail_notes"] == 2
    assert all(c["agent_count"] == 0 for c in agg["recurring"] + agg["below_threshold"])


# --- resident words (`TRC-005`) ---

def test_trc_005_the_instruction_is_at_most_40_resident_words():
    import test_instruction_volume as volume
    contract = (ROOT / "compass-contract.md").read_text(encoding="utf-8")
    paragraphs = [p for p in contract.split("\n\n") if "compass issue friction" in p]
    assert len(paragraphs) == 1, "the contract must carry one friction instruction"
    assert len(paragraphs[0].split()) <= 40, paragraphs[0]
    assert sum(volume._resident_breakdown().values()) <= volume.RESIDENT_CEILING


def test_trc_001_friction_capture_at_finish_keeps_agent_notes(project):
    # `quick-fix finish` and ship run the friction capture, which rebuilds the
    # derived entries; an agent note cannot be recomputed, so it must survive.
    _manifest(project, "fix-a")
    assert _note(project).returncode == 0
    result = _compass(project, "_friction-capture", "--internal", "--issue", "fix-a",
                      "--note", "the plan took too long")
    assert result.returncode == 0, result.stderr
    assert sorted(e["source"] for e in _friction(project)) == ["agent", "human"]


def test_trc_001_evidence_outside_the_issue_folder_is_refused(project, tmp_path):
    # The file exists, so only the containment check can refuse it.
    _manifest(project, "fix-a")
    outside = project / ".compass" / "work" / "outside.txt"
    outside.write_text("x\n", encoding="utf-8")
    link = project / ".compass" / "work" / "fix-a" / "evidence" / "link.log"
    link.symlink_to(outside)
    for observed in ("../outside.txt", str(outside), "evidence/link.log", "manifest.yml"):
        result = _note(project, observed=observed)
        assert result.returncode != 0, observed
    assert _friction(project) == []


@pytest.mark.parametrize("observed", ["devlog.md:", "evidence/bin.log:1"])
def test_trc_001_a_bad_line_citation_is_refused_without_a_traceback(project, observed):
    _manifest(project, "fix-a")
    folder = project / ".compass" / "work" / "fix-a"
    (folder / "devlog.md").write_text("# Devlog\n", encoding="utf-8")
    (folder / "evidence" / "bin.log").write_bytes(b"\xff\xfe\x00broken")
    result = _note(project, observed=observed)
    assert "Traceback" not in result.stderr, result.stderr
    if observed.endswith(":"):
        assert result.returncode != 0


def test_trc_001_a_fix_on_two_lines_is_refused(project):
    _manifest(project, "fix-a")
    result = _note(project, fix="line one\nline two")
    assert result.returncode != 0 and "one line" in result.stderr, result.stderr


def test_trc_003_a_person_fix_also_lets_the_agent_notes_count(project):
    # Person rows describe the problem in `observation` and the change in
    # `proposed_change`; an agent note names a change, so a person's matching
    # change is what backs it.
    fix = "Skip the second plan read on a quick fix"
    for n in range(3):
        _manifest(project, f"issue-{n}", [_agent_row(fix)])
    _manifest(project, "issue-p", [{"category": "over-weight", "source": "human",
                                    "observation": "planning was slow",
                                    "proposed_change": fix}])
    _compass(project, "retro", "--lessons")
    pending = yaml.safe_load((project / ".compass" / "lessons-pending.yml").read_text())
    assert [p["rule"] for p in pending["lessons"]] == [fix]


GUARDRAIL_NOTES = [
    "Let a quick fix skip the failing test first",
    "Skip TDD on docs-only changes",
    "Let a quick fix write the test after the code",
    "Drop the sign off step",
    "Auto-approved quick fixes need no review",
    "Skip the approvals on docs",
    "Drop the AC step",
    "Do not require a traced scenario",
    "skip the failing-test step",
]
OTHER_NOTES = [
    "Record the evidence path automatically in tdd-green",
    "Print a shorter stack trace on hook failure",
    "Show red text for errors in status",
    "Let the docs index link acceptance.md",
    "Skip the second plan read on a quick fix",
]


@pytest.mark.parametrize("fix, expected", [(f, True) for f in GUARDRAIL_NOTES]
                         + [(f, False) for f in OTHER_NOTES])
def test_trc_004_guardrail_notes_are_recognised_by_their_wording(fix, expected):
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.agent_friction import names_a_guardrail_step
    assert names_a_guardrail_step(fix) is expected


def test_trc_002_agent_only_clusters_are_not_below_threshold_items(project):
    for n in range(2):
        _manifest(project, f"agent-{n}", [_agent_row(f"agent fix {n}")])
    agg = json.loads(_compass(project, "retro", "--friction", "--format", "json").stdout)
    assert agg["below_threshold"] == [] and agg["recurring"] == []
