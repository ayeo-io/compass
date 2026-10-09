"""The living spec lists the issues that were completed (issue
`vocabulary-and-cli-renames`, group H).

An issue feeds the spec when it is done with close reason `completed` and its
approach ships. The heading reads `### <slug> (completed <date>)`; the reader
of an older spec accepts `landed` and `completed`.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

SCENARIO = [{"id": "S-1", "title": "the first scenario", "intent": "INT-1"},
            {"id": "S-2", "title": "the second scenario", "intent": "INT-1"}]


def _issue(root, slug, approach="regular", scenarios=SCENARIO, **fields):
    task = root / ".compass" / "work" / slug
    task.mkdir(parents=True)
    body = {"schema_version": "3.0", "issue": slug, "created": "2026-10-01",
            "delivery_approach": approach, "scenarios": scenarios,
            "land_timestamp": "2026-10-08T09:00:00Z"}
    body.update(fields)
    (task / "manifest.yml").write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return task


def _derive(root):
    from compass_pkg import flow
    flow.derive_system_spec(str(root))
    return (root / "docs" / "system-spec.md").read_text(encoding="utf-8")


def test_vr_h1_a_completed_issue_appears_under_a_completed_heading(tmp_path):
    _issue(tmp_path, "the-issue", status="done", close_reason="completed")
    spec = _derive(tmp_path)
    assert "### the-issue (completed 2026-10-08)" in spec
    assert "`S-1` the first scenario" in spec and "`S-2` the second scenario" in spec
    assert "(landed" not in spec
    assert "each completed issue's manifest.yml" in spec


@pytest.mark.parametrize("reason,extra", [("not-planned", {}),
                                          ("duplicate", {"duplicate_of": "other"})])
def test_vr_h2_an_issue_closed_without_delivery_does_not_appear(tmp_path, reason, extra):
    _issue(tmp_path, "the-issue", status="done", close_reason=reason, **extra)
    assert "the-issue" not in _derive(tmp_path)


def test_vr_h3_a_completed_spike_does_not_appear(tmp_path):
    _issue(tmp_path, "the-spike", approach="spike", status="done", close_reason="completed")
    _issue(tmp_path, "the-fix", approach="quick-fix", status="done", close_reason="completed")
    spec = _derive(tmp_path)
    assert "the-spike" not in spec and "the-fix" in spec


@pytest.mark.parametrize("fields", [
    {}, {"status": "backlog"},
    {"subtasks": [{"id": "subtask-1"}]},
    {"subtasks": [{"id": "subtask-1"}], "gates": [{"id": "verify.x", "status": "pass"}]},
    {"artifacts": [{"kind": "acceptance-criteria", "path": "a.md", "status": "draft"},
                   {"kind": "requirements-review", "path": "r.md", "status": "draft"}]},
], ids=["no-status", "backlog", "in-progress", "in-review", "ready"])
def test_vr_h4_an_issue_not_closed_does_not_appear(tmp_path, fields):
    _issue(tmp_path, "the-issue", **fields)
    assert "the-issue" not in _derive(tmp_path)


def test_vr_h5_an_old_landed_manifest_appears_under_a_completed_heading(tmp_path):
    _issue(tmp_path, "the-old-issue", status="landed")
    spec = _derive(tmp_path)
    assert "### the-old-issue (completed 2026-10-08)" in spec
    assert "`S-1` the first scenario" in spec and "`S-2` the second scenario" in spec


def test_vr_h6_the_reader_finds_an_issue_under_either_heading_word():
    from compass_pkg import flow
    text = ("## Current Behaviour\n\n### old-one (landed 2026-08-01)\n\n- `A-1` x\n\n"
            "### new-one (completed 2026-10-01)\n\n- `B-1` y\n\n"
            "### third (finished 2026-10-02)\n")
    assert flow._issues_named(text) == {"old-one", "new-one"}


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.email=t@example.com", "-c", "user.name=t",
                           *args], cwd=cwd, capture_output=True, text=True, check=True)


def test_vr_h8_the_branch_filter_finds_an_issue_a_landed_heading_names(tmp_path):
    """A spec committed with `landed` headings still names its issues, so an
    issue whose land commit is on another branch is kept when it derives."""
    from compass_pkg import flow
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "system-spec.md").write_text(
        "### from-main (landed 2026-10-01)\n\n- `A-1` x\n\n"
        "### from-new (completed 2026-10-02)\n\n- `N-1` n\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "side")
    (tmp_path / "side.txt").write_text("x\n")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "side work")
    side = _git(tmp_path, "rev-parse", "HEAD").stdout.strip()
    _git(tmp_path, "checkout", "-q", "main")
    # The commit exists only on `side`, so it is not reachable from HEAD.
    _issue(tmp_path, "from-main", status="done", close_reason="completed", land_commit=side,
           scenarios=[{"id": "A-1", "title": "x", "intent": "INT-1"}])
    _issue(tmp_path, "from-new", status="done", close_reason="completed", land_commit=side,
           scenarios=[{"id": "N-1", "title": "n", "intent": "INT-1"}])
    _issue(tmp_path, "from-side", status="done", close_reason="completed", land_commit=side,
           scenarios=[{"id": "C-1", "title": "z", "intent": "INT-1"}])
    spec = _derive(tmp_path)
    assert "### from-main (completed" in spec, "named by a landed heading, so kept"
    assert "### from-new (completed" in spec, "named by a completed heading, so kept"
    assert "from-side" not in spec, "not named and not on this branch"
    assert flow._issues_named("### from-main (landed 2026-10-01)") == {"from-main"}


def test_vr_h8_the_missing_record_refusal_counts_a_completed_spike(tmp_path):
    from compass_pkg import flow
    from compass_pkg.core import CompassError
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "system-spec.md").write_text(
        "### the-spike (landed 2026-10-01)\n\n- `A-1` x\n", encoding="utf-8")
    _issue(tmp_path, "the-spike", approach="spike", status="done", close_reason="completed")
    flow.derive_system_spec(str(tmp_path))
    assert "the-spike" not in (tmp_path / "docs" / "system-spec.md").read_text(encoding="utf-8")
    (tmp_path / "docs" / "system-spec.md").write_text(
        "### gone (landed 2026-10-01)\n\n- `A-1` x\n", encoding="utf-8")
    with pytest.raises(CompassError):
        flow.derive_system_spec(str(tmp_path))


def test_vr_h7_an_archive_in_both_word_sets_keeps_the_same_issues_and_scenarios(tmp_path):
    """The shapes this repository's archive holds: issues landed in the old
    words, in the new words, spikes that carry no scenarios, and issues that
    never landed. Only the heading word and the header text change."""
    _issue(tmp_path, "a-landed", status="landed", land_timestamp="2026-09-01T00:00:00Z")
    _issue(tmp_path, "b-done", status="done", close_reason="completed",
           land_timestamp="2026-09-02T00:00:00Z")
    _issue(tmp_path, "c-spike", approach="spike", status="landed", scenarios=[])
    _issue(tmp_path, "d-spike-no-key", approach="spike", status="landed")
    (tmp_path / ".compass/work/d-spike-no-key/manifest.yml").write_text(
        yaml.safe_dump({"issue": "d-spike-no-key", "delivery_approach": "spike",
                        "status": "landed"}), encoding="utf-8")
    _issue(tmp_path, "e-abandoned", status="abandoned")
    _issue(tmp_path, "f-queued", status="queued")
    _issue(tmp_path, "g-active", status="active")
    spec = _derive(tmp_path)
    headings = [line for line in spec.splitlines() if line.startswith("### ")]
    assert headings == ["### a-landed (completed 2026-09-01)", "### b-done (completed 2026-09-02)"]
    assert spec.count("`S-1`") == 2 and spec.count("`S-2`") == 2


def _git_head_spec():
    shown = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:docs/system-spec.md"],
                           capture_output=True, text=True)
    return shown.stdout if shown.returncode == 0 else None


def test_vr_h7_this_repositorys_archive_derives_every_issue_and_scenario_the_spec_names(
        tmp_path):
    """Local only: the issue records are not committed, so a checkout without
    them skips this. Every issue and scenario the committed spec names is in
    the spec derived from the archive."""
    import re
    work = ROOT / ".compass" / "work"
    committed = _git_head_spec()
    if not work.is_dir() or not committed:
        pytest.skip("this checkout has no issue archive or no committed spec")
    (tmp_path / ".compass").mkdir()
    (tmp_path / ".compass" / "work").symlink_to(work)
    derived = _derive(tmp_path)
    heading = re.compile(r"^### (\S+) \((?:landed|completed) [0-9-]*\)$", re.M)
    scenario = re.compile(r"^- `([^`]+)`", re.M)

    def by_issue(text):
        found = {}
        for block in re.split(r"(?m)^(?=### )", text):
            m = heading.match(block.splitlines()[0]) if block.strip() else None
            if m:
                found[m.group(1)] = set(scenario.findall(block))
        return found

    before, after = by_issue(committed), by_issue(derived)
    missing = {slug: sorted(ids - after.get(slug, set())) for slug, ids in before.items()
               if ids - after.get(slug, set())}
    assert not missing, missing
