"""The pre-tool hook judges a path issue by its own rule (ADR-092).

A path issue records `evidence_required` and no `stages:` map. Every path
issue owes scenarios, so the hook refuses a code edit until one is on record,
and the refusal names `compass scenario add`. An issue assessed before 9.0.0
keeps the `define: thorough` rule; `test_hook_enforces_g2.py` checks it.

Issue: ayeo-io/compass-delivery#351 [Replace the approaches and eight stages
with one four-stage path].
"""
from __future__ import annotations


def test_a_code_edit_on_a_path_issue_with_no_scenario_is_refused(dsl):
    """
    Given a complete install
    And an opted-in project whose issue is on the four-stage path
    And the issue has no scenario
    When the agent edits a code file
    Then the hook refuses as no-scenario
    And the refusal names compass scenario add
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.project.hasPathIssue(scenarios=0)
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmRefused("no-scenario")
    dsl.hook.confirmRefusalSays("compass scenario add")
    dsl.hook.confirmRefusalDoesNotSay("define: thorough")


def test_a_code_edit_on_a_path_issue_with_a_scenario_is_allowed(dsl):
    """
    Given a complete install
    And an opted-in project whose issue is on the four-stage path
    And the issue has a scenario and a red on record
    When the agent edits a code file
    Then the hook allows it
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.project.hasPathIssue(scenarios=1)
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmAllowed()
