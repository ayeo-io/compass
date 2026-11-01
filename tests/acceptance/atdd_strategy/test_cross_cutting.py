"""Failure-mode scenarios of the four-layer acceptance strategy that cross groups.

The scenario `TRC-X2` guards every later item of the strategy: an issue assessed by compass
8.0.4, before the strategy shipped, gives the result 8.0.4 gives.
"""
from __future__ import annotations

from tests.acceptance.atdd_strategy import support


def test_trc_x2(tmp_path):
    """An issue created before the major version keeps passing."""
    project = support.older_issue_project(tmp_path / "repo")
    issue = support.Issue(project, "older")
    assert "acceptance_strategy" not in issue.manifest()
    code, document = issue.check()
    assert support.summary(code, document) == support.recorded("older-issue")
    assert not [r for r in support.rows(document) if r[0] in support.STRATEGY_CHECKS]
    notices = " ".join(document["notices"])
    notice = ("four-layer acceptance strategy (`S17`): does not apply - this issue was "
              "assessed before the strategy shipped")
    assert notice in notices, notices
    # The default view keeps the line budget of compass 8.0.4: the notice shows in
    # the full view and the JSON document only.
    assert "four-layer acceptance strategy" not in issue.run("check", "--issue", "older")[1]
    assert notice in issue.run("check", "--issue", "older", "--verbose")[1]
