"""Regression tests for six release-blocking defects that shipped with only a
manual check behind them.

Each fix below was checked by hand at the time - a temp project built, a
command run, the output read - and then had nothing left on disk that would
notice it breaking again. That is the shape of defect this repository keeps
finding in itself: a correct outcome with no standing assertion behind it. Each
test here was confirmed to fail against the pre-fix version of its file, so it
detects the defect rather than merely describing it.

Covered:
  SCN-01  scripts/validate.sh must not fail on untracked files
  SCN-02  the hook must enforce inside a repo whose own path contains "test"
  SCN-03  scripts/multiagent.sh must not copy evidence/ or .red into a worktree
  SCN-08  the CI workflow must install Python before running a Python tool
  SCN-10  a spike must still report an owed follow-up
  SCN-11  `compass ship-commit` must refuse to mark landed over unpassed gates
  SCN-12  `compass issue receipt` must not print "landed cleanly" over pending gates
  SCN-13  `compass analyze` must not report 0 findings after listing findings
"""

# These tests read the per-check detail (name, PASS/FAIL, reason) that
# `compass check --verbose` prints.
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"


# ---------------------------------------------------------------------------
# Helpers - a minimal Compass project on disk
# ---------------------------------------------------------------------------

def _task_yml(slug: str, *, gates: list, status: str = "active", **extra) -> str:
    task = {
        "schema_version": "1.1",
        "task": slug,
        "created": "2026-08-04",
        "status": status,
        "assessment": {
            "risk": "contained", "familiarity": "greenfield",
            "size": "small", "intent": "delivery", "urgency": "none",
            "role": "engineer", "labels": [],
        },
        "delivery_approach": "standard", "topology": "solo", "policy_rules_fired": [],
        "stages": {}, "evidence": [], "gates": gates, "scenarios": [],
        "changed_files": [], "claims": [], "follow_ups": [], "reassessments": [],
        "friction": [],
    }
    task.update(extra)
    return yaml.safe_dump(task, sort_keys=False)


@pytest.fixture
def project(tmp_path):
    """A Compass project with the framework's own governance/ copied in."""
    root = tmp_path / "proj"
    (root / ".compass" / "work" / "t").mkdir(parents=True)
    shutil.copytree(ROOT / "governance", root / "governance")
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    (root / ".compass" / "current-task").write_text("t\n")
    return root


def _compass(project_root: pathlib.Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(project_root), capture_output=True, text=True, timeout=60,
    )


PENDING_GATES = [
    {"id": "verify.correctness", "status": "pending", "evidence": []},
    {"id": "verify.governance", "status": "pending", "evidence": []},
]


# ---------------------------------------------------------------------------
# SCN-12 - a pending gate is not a clean land
# ---------------------------------------------------------------------------

def test_receipt_does_not_report_a_clean_land_over_pending_gates(project):
    """The receipt is the audit artifact - what someone reads instead of
    re-deriving the issue. It printed "Verdict: landed cleanly" for an issue
    whose every gate was pending with no evidence at all, because the pending
    branch set neither the failure flag nor the caveat flag."""
    (project / ".compass" / "work" / "t" / "manifest.yml").write_text(
        _task_yml("t", gates=PENDING_GATES, status="landed",
                  land_timestamp="2026-08-04T00:00:00Z")
    )
    result = _compass(project, "issue", "receipt", "--issue", "t")
    verdict = [l for l in result.stdout.splitlines() if "Verdict:" in l]
    assert verdict, f"no verdict line in the receipt:\n{result.stdout}"
    assert "cleanly" not in verdict[0], (
        f"a receipt with two pending, unevidenced gates reported {verdict[0]!r}"
    )


# ---------------------------------------------------------------------------
# SCN-11 - ship-commit must not write `landed` over unpassed gates
# ---------------------------------------------------------------------------

def test_land_commit_refuses_to_mark_landed_with_unpassed_gates(project):
    """`status: landed` is what the receipt, `compass flow`, and the rework scan
    all read. Writing it while gates are pending backdates a claim that the work
    cleared its gates."""
    task_path = project / ".compass" / "work" / "t" / "manifest.yml"
    task_path.write_text(_task_yml("t", gates=PENDING_GATES))

    # ship-commit makes a git commit, so the project has to be a repo.
    for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.com"),
                 ("config", "user.name", "T"), ("add", "-A"),
                 ("commit", "-q", "-m", "init")):
        subprocess.run(["git", "-C", str(project), *args], check=True,
                       capture_output=True, text=True)
    (project / "src.py").write_text("x = 1\n")
    subprocess.run(["git", "-C", str(project), "add", "src.py"], check=True,
                   capture_output=True, text=True)

    result = _compass(project, "ship-commit", "-m", "land it", "--issue", "t")
    written = yaml.safe_load(task_path.read_text())
    assert written.get("status") != "landed", (
        "land-commit marked a task landed with two pending gates:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert "verify.correctness" in combined, (
        f"the refusal must name the gates that have not passed:\n{combined}"
    )


# ---------------------------------------------------------------------------
# SCN-13 - the summary must agree with the findings above it
# ---------------------------------------------------------------------------

def test_analyze_summary_agrees_with_the_findings_it_listed(project):
    """In advisory mode the summary line was hardcoded to "PASS - 0 finding(s),
    consistency checks clean", so the command listed its findings and then
    denied having any - while the evidence JSON recorded the real count."""
    task_dir = project / ".compass" / "work" / "t"
    # Uses `stages=`: the base manifest already sets `stages: {}`, so a
    # `phases:` key is dropped as a retired duplicate.
    (task_dir / "manifest.yml").write_text(
        _task_yml("t", gates=[], stages={"define": "full"})
    )
    (task_dir / "delivery-approach.md").write_text("# Route - t\n")
    (task_dir / "acceptance-criteria.md").write_text("# Spec - t\n\n## Summary\n\n**Goal:** x\n")

    # The verdict is the first line and the findings are a counted section;
    # the two counts must match.
    import re as _re

    result = _compass(project, "analyze", "--issue", "t")
    lines = result.stdout.splitlines()
    section = [l for l in lines if _re.search(r"findings \((\d+)\)", l)]
    verdict = [l for l in lines if "compass analyze" in l]
    assert section and verdict, f"unexpected analyze output:\n{result.stdout}"

    listed = int(_re.search(r"findings \((\d+)\)", section[0]).group(1))
    # Tolerant of the word between the number and "finding(s)": the verdict
    # reads "1 coherence finding(s)" on the advisory path. The number and the
    # noun are what this test is about, not the adjective.
    _m = _re.search(r"(\d+)\s+(?:\w+\s+)?finding\(s\)", verdict[0])
    assert _m, ("the verdict does not state a finding count:\n" + verdict[0])
    stated = int(_m.group(1))
    assert listed > 0, "fixture produced no findings - the assertion would be empty"
    assert stated == listed, (
        f"analyze listed {listed} finding(s) and its verdict says {stated}: "
        f"{verdict[0]!r}"
    )


# ---------------------------------------------------------------------------
# SCN-01 - validate.sh must ignore files git does not track
# ---------------------------------------------------------------------------

def test_validate_sh_ignores_untracked_files():
    """validate.sh scans markdown for references to scripts/ and hooks/ files and
    fails when one does not exist. It scanned the working tree, so any untracked
    file - a scratch note, a vendored copy, a build artifact - could fail the
    repo's own structural check. It now asks git what is tracked."""
    stray = ROOT / "stray-untracked-note.md"
    assert not stray.exists(), "fixture file already exists; refusing to overwrite"
    stray.write_text("See `scripts/definitely-not-a-real-script.sh` for details.\n")
    try:
        result = subprocess.run(
            ["bash", str(ROOT / "scripts" / "validate.sh")],
            cwd=str(ROOT), capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, (
            "an untracked markdown file failed validate.sh:\n"
            f"{result.stdout[-2000:]}\n{result.stderr[-2000:]}"
        )
    finally:
        stray.unlink()


# ---------------------------------------------------------------------------
# SCN-08 - a CI job that runs a Python tool must install Python first
# ---------------------------------------------------------------------------

def test_ci_jobs_that_run_python_set_up_python_first():
    """Two workflow jobs piped work through the compass CLI without an
    actions/setup-python step. They depended on whatever Python the runner image
    happened to ship, which is exactly the thing a pinned workflow exists to
    stop varying."""
    # The setup step must also come before the first step that runs Python:
    # a step that runs earlier still gets the runner image's interpreter.
    missing = []
    workflow_paths = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflow_paths, "no workflow files found"
    for workflow_path in workflow_paths:
        workflow_name = workflow_path.name
        workflow = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
        for name, job in workflow["jobs"].items():
            steps = job.get("steps", [])
            runs = [
                i for i, s in enumerate(steps)
                if "python" in str(s.get("run", "")) or "compass" in str(s.get("run", ""))
            ]
            sets_up = [
                i for i, s in enumerate(steps) if "setup-python" in str(s.get("uses", ""))
            ]
            if runs and (not sets_up or sets_up[0] > runs[0]):
                missing.append(f"{workflow_name}: {name}")
    assert not missing, (
        "these CI jobs run Python before or without actions/setup-python: "
        f"{missing}"
    )


# ---------------------------------------------------------------------------
# SCN-02 - enforcement must not switch itself off based on where you cloned
# ---------------------------------------------------------------------------

def test_hook_still_enforces_inside_a_repo_whose_path_contains_test(tmp_path):
    """The hook exempts test files by glob. Those globs were matched against the
    ABSOLUTE path, and `*test*` matches every ancestor directory too - so a
    repository under /Users/testuser/, or any path containing "latest", had
    red-before-green silently disabled for the entire tree while still
    reporting that it was on."""
    root = tmp_path / "latest-checkout" / "proj"      # "latest" contains "test"
    task_dir = root / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text("t\n")
    (task_dir / "delivery-approach.md").write_text("# Route\n")   # assessed, but no .red

    payload = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": str(root / "src" / "app.py")},
    })
    import os
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(root)
    result = subprocess.run(
        ["bash", str(ROOT / "hooks" / "pre-tool.sh")],
        input=payload, capture_output=True, text=True, env=env, timeout=30,
    )
    assert result.returncode == 2, (
        "the hook allowed a production edit with no red on record, because the "
        f"repository path contains 'test':\n{result.stdout}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# SCN-10 - a spike suspends the TDD strategy, not the follow-up ledger
# ---------------------------------------------------------------------------

def test_spike_route_still_reports_an_owed_backfill(project):
    """`compass check` returns early on a spike, because most delivery checks do
    not apply there. The owed-follow-up check was inside that early return, so a
    spike could carry an unpaid follow-up indefinitely and still report a clean
    check - and an unpaid follow-up is the one piece of debt Compass promises to
    keep visible."""
    task_dir = project / ".compass" / "work" / "t"
    (task_dir / "manifest.yml").write_text(_task_yml(
        "t", gates=[], route="spike",
        backfills=[{"id": "BF-001",
                    "description": "Promote the probe into a real scenario",
                    "status": "owed"}],
    ))
    (task_dir / "delivery-approach.md").write_text("# Route - t\n\nroute: spike\n")
    (task_dir / ".spike").write_text("")

    result = _compass(project, "check", "--verbose", "--issue", "t")
    combined = result.stdout + result.stderr
    assert "BF-001" in combined or "backfill" in combined.lower(), (
        f"a Spike with an owed backfill reported nothing about it:\n{combined}"
    )
    assert "FAIL" in combined, (
        f"an owed backfill did not fail the check on a Spike route:\n{combined}"
    )


# ---------------------------------------------------------------------------
# SCN-03 - a seeded worktree must not inherit someone else's red or evidence
# ---------------------------------------------------------------------------

def test_swarm_does_not_seed_evidence_or_the_red_marker(tmp_path):
    """`.red` is the marker the pre-tool hook reads to permit a production edit,
    and it means "a real failure was observed HERE". Copying it into a sibling
    worktree lets a builder edit production code on a red another builder
    recorded. evidence/ is the same argument: a green run belongs to the run
    that produced it."""
    seeding = pytest.importorskip("tests.test_swarm_seeding", reason="fixture module")
    repo = tmp_path / "proj"
    repo.mkdir()
    slug = seeding.SLUG
    git = seeding._git
    git(repo, "init", "-q", "-b", "main")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "T")
    (repo / ".gitignore").write_text("/.compass/work/\n/.compass/current-task\n")
    compass = repo / ".compass"
    task_dir = compass / "work" / slug
    task_dir.mkdir(parents=True)
    (compass / "config.yml").write_text(
        f"version: 1.0.0\nmode: enforced\nswarm:\n  worktree_root: \"{tmp_path / 'wt'}\"\n")
    (task_dir / "manifest.yml").write_text(seeding.TASK_YML)
    (task_dir / "delivery-approach.md").write_text("# Route\n")
    (task_dir / "distribution-map.md").write_text(seeding.MAP)
    (compass / "current-task").write_text(slug + "\n")

    # The state that must NOT travel: a recorded red and its evidence.
    (task_dir / ".red").write_text("")
    (task_dir / "evidence").mkdir()
    (task_dir / "evidence" / "red.json").write_text(json.dumps({"exit": 1}))

    (repo / "README.md").write_text("# demo\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "multiagent.sh"), slug],
        cwd=str(repo), capture_output=True, text=True, timeout=180,
    )
    worktrees = sorted((tmp_path / "wt").glob("*/.compass/work/" + slug))
    assert worktrees, (
        f"multiagent.sh created no seeded worktree:\n{result.stdout}\n{result.stderr}"
    )
    for wt_task in worktrees:
        assert not (wt_task / ".red").exists(), (
            f"{wt_task} inherited a .red marker recorded in another worktree"
        )
        assert not (wt_task / "evidence").exists(), (
            f"{wt_task} inherited evidence/ from another worktree"
        )
        assert (wt_task / "delivery-approach.md").exists(), (
            f"{wt_task} was not seeded at all - the assertions above are empty"
        )
