"""Shipping does not refuse the framework's own bookkeeping.

`compass ship-commit` refuses to commit paths outside the issue's declared
scope - its `changed_files` plus its artifact directory. The check is
needed: a repo-wide auto-formatter plus a whole-tree re-stage once took a
real index from 23 files to 1,574, including a concurrent agent's
uncommitted work.

`.compass/current-task` sits outside the issue's directory and
`/compass:assess` writes it, so the scope check must allow it by name.

The allowance is a named list, never a prefix: anything under `.compass/`
would re-admit a sibling issue's artifacts into this issue's commit, which
is exactly what the check exists to stop.

Scenario ids: see the issue's acceptance criteria (group D).
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "cli"))

from compass_pkg import manifest                              # noqa: E402

TASK = {
    "task": "demo",
    "changed_files": [{"path": "src/app.py", "scenarios": ["SCN-1"]}],
}


def _scope():
    return manifest._land_scope(TASK, "demo")


def test_rcd_d1_current_task_pointer_in_scope():
    """The pointer /compass:assess writes must not be refused by the commit
    that ships it."""
    owned, artifact_dir = _scope()
    stray = manifest._out_of_scope(
        ["src/app.py", ".compass/current-task"], owned, artifact_dir)

    assert ".compass/current-task" not in stray, (
        "shipping refused .compass/current-task as outside the issue's "
        "declared scope. Compass writes that file itself at triage, so this "
        "blocks the commit on the framework's own output."
    )


def test_rcd_d1b_the_issues_own_artifacts_stay_in_scope():
    """The existing allowance must survive the widening."""
    owned, artifact_dir = _scope()
    stray = manifest._out_of_scope(
        ["src/app.py", ".compass/work/demo/technical-design.md"], owned, artifact_dir)

    assert stray == [], (
        f"the issue's own declared file or artifact directory was refused: "
        f"{stray}"
    )


def test_rcd_d2_unrelated_file_still_refused():
    """The control, and the reason the check exists at all.

    Without this, D1 passes against a change that allowed everything - which
    would re-open the case where a formatter's output ends up in the commit.
    """
    owned, artifact_dir = _scope()
    stray = manifest._out_of_scope(
        ["src/app.py", "src/unrelated.py", "vendor/generated.js"],
        owned, artifact_dir)

    assert "src/unrelated.py" in stray and "vendor/generated.js" in stray, (
        f"an undeclared source file was accepted into the issue's commit. "
        f"Refused: {stray}"
    )


def test_rcd_d2b_a_sibling_issues_artifacts_are_still_refused():
    """The widening must be a named list, not a `.compass/` prefix.

    A prefix would let another issue's artifacts - or another agent's
    in-progress work in the same tree - end up in this commit, which is the
    collision the scope check was built for.
    """
    owned, artifact_dir = _scope()
    # `demo-2` extends `demo`, which tests the trailing-slash boundary;
    # slugs that extend one another are common here (rehearsal-recordings
    # beside rehearsal-cli-defects).
    stray = manifest._out_of_scope(
        [".compass/work/demo-2/manifest.yml",
         ".compass/work/some-other-issue/manifest.yml"], owned, artifact_dir)

    assert stray == [".compass/work/demo-2/manifest.yml",
                     ".compass/work/some-other-issue/manifest.yml"], (
        "a sibling issue's artifacts were accepted into this issue's commit - "
        "the allowance widened to a prefix instead of a named set"
    )
