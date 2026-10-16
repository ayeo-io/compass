"""multiagent.sh reads the worktree cap from the manifest (`assessment.risk`,
`policy_rules_fired`), not from delivery-approach.md prose (which
false-positives on 'did-not-fire' audit notes), and counts only subtasks
that get a worktree.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
SWARM = FRAMEWORK_ROOT / "scripts" / "multiagent.sh"


def _git(cwd, *a):
    return subprocess.run(["git", *a], cwd=str(cwd), capture_output=True, text=True)


def _repo(tmp_path):
    d = tmp_path / "repo"
    d.mkdir()
    _git(d, "init", "-q")
    _git(d, "config", "user.email", "t@e")
    _git(d, "config", "user.name", "t")
    (d / "f").write_text("x")
    _git(d, "add", "-A")
    _git(d, "commit", "-q", "-m", "init")
    cfg = d / ".compass"
    (cfg / "work").mkdir(parents=True)
    (cfg / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\nswarm:\n  worktree_root: ../wt\n  max_worktrees: 6\n")
    return d


def _task(d, slug, *, risk=None, capped=False, readings=True):
    td = d / ".compass" / "work" / slug
    td.mkdir(parents=True, exist_ok=True)
    body = {"task": slug}
    if readings:
        rd = {"familiarity": "brownfield-mapped", "size": "large", "intent": "delivery"}
        if risk:
            rd["risk"] = risk
        body["assessment"] = rd
    fired = ("- id: RP-CAP-001\n  kind: cap\n" if capped else "")
    import yaml
    (td / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False) +
                                 ("fired_guardrails:\n" + fired if fired else "fired_guardrails: []\n"))
    return td


def _route(td, prose=""):
    (td / "delivery-approach.md").write_text("# Route\n\n" + prose + "\n")


def _map(td, slug, n_streams, *, extra_nonworktree=False):
    rows = ["# Distribution Map", "", "## 3. mapping", ""]
    for i in range(1, n_streams + 1):
        rows.append(f"| stream-{i} | U{i} | TRC-{i} | compass/{slug}/stream-{i} |")
    if extra_nonworktree:
        rows.append(f"| stream-int | integration/verify - not a parallel worktree | - | n/a |")
    (td / "distribution-map.md").write_text("\n".join(rows) + "\n")


def _run(repo, slug):
    return subprocess.run(["bash", str(SWARM), slug, "--dry-run"],
                          cwd=str(repo), capture_output=True, text=True)


# did-not-fire prose that the OLD grep false-positived on:
_PROSE = "RP-CAP-001 (`blast_radius: critical`) - not matched; blast radius is contained."


@pytest.mark.parametrize("ceiling,requested,risk,exit_code,cap", [
    (2, 3, "contained", 1, 2),
    (2, 2, "contained", 0, 2),
    (9, 7, "contained", 1, 6),
    (10**50, 7, "contained", 1, 6),
    (5, 2, "critical", 1, 1),
    (None, 3, "contained", 0, 6),
])
def test_stored_issue_ceiling_limits_provisioning(tmp_path, ceiling, requested, risk, exit_code, cap):
    import yaml
    repo = _repo(tmp_path)
    td = _task(repo, "stored", risk=risk)
    with (td / "manifest.yml").open("a") as stream:
        stream.write(yaml.safe_dump({"subtask_ceiling": ceiling}))
    _route(td)
    _map(td, "stored", requested)
    result = _run(repo, "stored")
    assert result.returncode == exit_code, result.stdout + result.stderr
    if exit_code:
        assert f"cap is {cap}" in result.stderr
        assert "WOULD create worktree" not in result.stdout
    else:
        assert f"route cap {cap}" in result.stdout


@pytest.mark.parametrize("ceiling", [0, -1, True, "2"])
def test_invalid_stored_issue_ceiling_refuses(tmp_path, ceiling):
    import yaml
    repo = _repo(tmp_path)
    td = _task(repo, "invalid", risk="contained")
    with (td / "manifest.yml").open("a") as stream:
        stream.write(yaml.safe_dump({"subtask_ceiling": ceiling}))
    _route(td)
    _map(td, "invalid", 1)
    result = _run(repo, "invalid")
    assert result.returncode != 0
    assert "subtask_ceiling" in result.stderr
    assert "WOULD create worktree" not in result.stdout


def test_did_not_fire_note_caps_to_one_today(tmp_path):
    """`TRC-R4-1` (regression guard): a delivery-approach.md 'did-not-fire'
    note quoting `blast_radius: critical` no longer collapses the cap - the
    assessment is contained, so multiagent.sh provisions the worktrees."""
    repo = _repo(tmp_path)
    td = _task(repo, "t1", risk="contained")
    _route(td, _PROSE)
    _map(td, "t1", 5)
    r = _run(repo, "t1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "but the cap is 1" not in (r.stdout + r.stderr), r.stdout + r.stderr


def test_cap_from_readings_ignores_prose(tmp_path):
    """`TRC-R4-2`: the cap honours `assessment.risk` (contained → full cap),
    not the critical token in delivery-approach.md prose."""
    repo = _repo(tmp_path)
    td = _task(repo, "t2", risk="contained")
    _route(td, _PROSE)
    _map(td, "t2", 5)
    r = _run(repo, "t2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "route cap 6" in (r.stdout + r.stderr), r.stdout + r.stderr


def test_critical_reading_caps_to_one(tmp_path):
    """`TRC-R4-3`: a genuinely critical issue (RP-CAP-001 fired) still caps to 1."""
    repo = _repo(tmp_path)
    td = _task(repo, "t3", risk="critical", capped=True)
    _route(td, "blast radius is critical")
    _map(td, "t3", 4)
    r = _run(repo, "t3")
    assert r.returncode != 0, r.stdout + r.stderr
    assert "4 subtasks but the cap is 1" in (r.stdout + r.stderr), r.stdout + r.stderr


def test_non_worktree_stream_excluded_from_count(tmp_path):
    """`TRC-R4-4`: a subtask marked 'not a parallel worktree' is not counted
    towards the cap."""
    repo = _repo(tmp_path)
    td = _task(repo, "t4", risk="critical", capped=True)   # cap = 1
    _route(td, "critical")
    _map(td, "t4", 1, extra_nonworktree=True)   # 1 worktree + 1 integration row
    r = _run(repo, "t4")
    assert r.returncode == 0, r.stdout + r.stderr   # counted worktrees = 1 <= cap 1


def test_missing_readings_errors_not_silent_cap(tmp_path):
    """`TRC-R4-F1`: absent `assessment.risk` is a hard error - never a silent
    cap=1 and never a fall back to grepping delivery-approach.md prose."""
    repo = _repo(tmp_path)
    td = _task(repo, "t5", risk=None)   # assessment present but no risk
    _route(td, _PROSE)
    _map(td, "t5", 3)
    r = _run(repo, "t5")
    assert r.returncode != 0, r.stdout + r.stderr
    combined = r.stdout + r.stderr
    assert "blast_radius" in combined or "manifest.yml" in combined, combined
