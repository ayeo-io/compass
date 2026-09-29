"""The hook must enforce `G2` (acceptance defined before it is built), not only
the strategy that serves `G1` (tested before it lands - no code reaches main
unless it traces to a declared test and a green test run is on record).

`hooks/pre-tool.sh` blocks a code edit until a failing test is on record -
strategy `S2` (red, green, refactor), in service of guardrail `G1`. Nothing
blocked a code edit when the delivery approach said `define: full` and no
requirements review existed, so guardrail `G2` had no enforcement at the
point where it could still be true.

The asymmetry is the point: `S2`, a *strategy*, got a real-time blocking hook.
`G2`, a *guardrail*, which by the framework's own conflict rule beats a
strategy, got a post-hoc report. `compass check` does catch it, at the
verify stage, after the code exists - which is the ordering `G2` exists to
prevent.

Only `define: full` triggers this, and routing-policy.yml gives that to
standard and initiative (`expedition`) only. A hotfix (reproduce-first) and a
spike (collapsed) are exempt by construction rather than by special case.

Scenarios: hook-enforces-g2/acceptance-criteria.md (SCN-A1..F2).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from conftest import write_red_record
import yaml

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"


def _project(*, specify="full", scenarios=0, red=True, spike=False,
             task_yml=True, broken_yml=False):
    root = Path(tempfile.mkdtemp(prefix="compass-fix-"))
    task_dir = root / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text("t\n")
    (task_dir / "delivery-approach.md").write_text("# Route\n")
    if red:
        write_red_record(task_dir)
    if spike:
        (task_dir / ".spike").write_text("")
    if broken_yml:
        (task_dir / "manifest.yml").write_text("phases: [this is not\n  valid: yaml\n")
    elif task_yml:
        (task_dir / "manifest.yml").write_text(yaml.safe_dump({
            "schema_version": "1.1", "task": "t", "created": "2026-08-06",
            "assessment": {"risk": "contained", "familiarity": "greenfield",
                         "size": "small", "intent": "delivery"},
            "delivery_approach": "standard",
            "stages": {"specify": specify},
            "scenarios": [{"id": f"SCN-{i}", "title": "s", "intent": "INT-1",
                           "tests": ["tests/test_x.py"]}
                          for i in range(1, scenarios + 1)],
        }, sort_keys=False))
    return root


def _run(project, target="src/app.py", tool="Edit"):
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    payload = {"tool_name": tool, "tool_input": {"file_path": str(project / target)}}
    return subprocess.run(["bash", str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True, env=env, timeout=30)


# ---------------------------------------------------------------------------
# Group A - `G2` is enforced where it can still be true
# ---------------------------------------------------------------------------

def test_scn_a1_full_specify_with_no_scenarios_blocks_a_code_edit():
    """The reporter's case: a red was on record, so `S2` was satisfied and
    every edit was allowed - while the delivery approach asked for a full
    define stage that never happened."""
    project = _project(specify="full", scenarios=0, red=True)
    try:
        result = _run(project)
        assert result.returncode == 2, (
            f"code was edited on a full-Specify route with no scenarios:\n"
            f"{result.stdout}{result.stderr}")
        assert "acceptance-before-code" in result.stderr, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_scn_a2_scenarios_present_allows_the_edit():
    project = _project(specify="full", scenarios=3, red=True)
    try:
        result = _run(project)
        assert result.returncode == 0, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


@pytest.mark.parametrize("specify", ["light", "collapsed", "reproduce-first"])
def test_scn_a3_routes_without_a_full_specify_are_unaffected(specify):
    """Quick fix (`express`, light), spike (collapsed) and hotfix
    (reproduce-first) are exempt by construction - a hotfix writes its
    reproduction before any requirements review."""
    project = _project(specify=specify, scenarios=0, red=True)
    try:
        result = _run(project)
        assert result.returncode == 0, (
            f"specify={specify} was blocked by the G2 check:\n{result.stderr}")
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_scn_a4_a_spike_suspends_the_g2_check_too():
    project = _project(specify="full", scenarios=0, red=False, spike=True)
    try:
        result = _run(project)
        assert result.returncode == 0, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


# ---------------------------------------------------------------------------
# Group B - the block has to be actionable
# ---------------------------------------------------------------------------

def test_scn_b1_the_message_names_the_guardrail_and_the_remedy():
    project = _project(specify="full", scenarios=0, red=True)
    try:
        err = _run(project).stderr
        assert "acceptance-before-code" in err and "acceptance-criteria.md" in err, err
        assert "scenarios" in err, err
        assert "/compass:assess --reassess" in err, (
            "a genuinely exploratory task should be told to re-assess - a Spike "
            "suspends G2:\n" + err)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_scn_b2_a_test_file_is_still_editable():
    """`G2` must not stop you writing the spec's tests, any more than `S2` does."""
    project = _project(specify="full", scenarios=0, red=False)
    try:
        result = _run(project, target="tests/test_app.py")
        assert result.returncode == 0, result.stderr
    finally:
        shutil.rmtree(project, ignore_errors=True)


# ---------------------------------------------------------------------------
# Failure modes - an unreadable manifest must not block work
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs,label", [
    ({"task_yml": False}, "no manifest.yml at all"),
    ({"broken_yml": True}, "unparseable manifest.yml"),
])
def test_scn_f1_an_unreadable_spine_does_not_block(kwargs, label):
    """This check reads a file the hook did not need before. If it cannot be
    read the hook must fall back to its earlier behaviour, not invent a block -
    a false block on unreadable state trains people to bypass the hook."""
    project = _project(specify="full", scenarios=0, red=True, **kwargs)
    try:
        result = _run(project)
        assert result.returncode == 0, (
            f"blocked because of {label}:\n{result.stdout}{result.stderr}")
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_scn_f2_g2_is_checked_before_the_red():
    """With neither a spec nor a red, the `G2` message is the useful one: you
    cannot write a red for a scenario that does not exist yet."""
    project = _project(specify="full", scenarios=0, red=False)
    try:
        err = _run(project).stderr
        assert "acceptance-before-code" in err, (
            f"the red message won over the acceptance one:\n{err}")
    finally:
        shutil.rmtree(project, ignore_errors=True)


def _project_v2(*, define="full", scenarios=0, red=True):
    """An issue manifest in the CURRENT vocabulary.

    `_project` above writes `stages: {specify: ...}` - the v2 block name with
    the v1 stage key inside it. That mixture is what every test here was built
    on, so the hook reading the retired key looked correct for as long as no
    fixture used the current one.
    """
    root = Path(tempfile.mkdtemp(prefix="compass-g2-v2-"))
    task_dir = root / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text("t\n")
    (task_dir / "delivery-approach.md").write_text("# Delivery approach\n")
    if red:
        write_red_record(task_dir)
    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "t", "created": "2026-08-25",
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                       "size": "small", "goal": "delivery"},
        "delivery_approach": "feature",
        "stages": {"assess": "full", "define": define, "implement": "full"},
        "scenarios": [{"id": f"SCN-{i}", "title": "s", "intent": "INT-1",
                       "tests": ["tests/test_x.py"]}
                      for i in range(1, scenarios + 1)],
    }, sort_keys=False))
    return root


def test_scn_a4_g2_fires_on_a_spine_in_the_current_vocabulary():
    """The guardrail must read the stage key the framework writes today.

    The hook asked for `specify`, the key retired at the v2 freeze, so a manifest
    saying `define: full` with no scenarios was allowed. The migration
    tool this framework ships is what turns a directory from one to the other,
    so running `compass migrate --apply` silently switched guardrail `G2` off
    for every issue it touched.
    """
    project = _project_v2(define="full", scenarios=0, red=True)
    try:
        result = _run(project)
        assert result.returncode == 2, (
            "a full define stage with no scenarios was allowed: the guardrail "
            "is reading a stage key this framework no longer writes\n"
            + result.stdout + result.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def test_scn_a5_a_spine_with_scenarios_still_passes_in_the_current_vocabulary():
    """The control: reading the current key must not block everything.

    Without this, a hook that blocks whatever it is handed would satisfy the
    check above, which would pass while checking nothing.
    """
    project = _project_v2(define="full", scenarios=2, red=True)
    try:
        result = _run(project)
        assert result.returncode == 0, (
            "a full define stage WITH scenarios was blocked\n"
            + result.stdout + result.stderr)
    finally:
        shutil.rmtree(project, ignore_errors=True)
