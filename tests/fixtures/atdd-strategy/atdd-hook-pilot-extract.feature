# Derived from .compass/work/atdd-hook-pilot/acceptance-criteria.md by `compass bdd extract`.
# Do not hand-edit - your edits are overwritten on the next extract.
# Edit the source spec instead.

Feature: atdd-hook-pilot

  @TRC-P1
  Scenario: the hook scenarios run as layered specifications
    Given the 16 hook scenarios in tests/acceptance/hooks/test_hook_refusals.py
    When the DSL and the specifications are searched
    Then the DSL holds 0 calls of assert, expect or should
    And every specification line is one DSL call
    And every scenario passes through the Claude Code driver

  @TRC-P2
  Scenario: the same specifications run through both hook clients
    Given the specifications
    When they run with COMPASS_HOOK_CLIENT=claude-code and with COMPASS_HOOK_CLIENT=codex
    Then every scenario passes under both, with 0 changes to the specifications

  @TRC-P3
  Scenario: a change to the hook's layout changes only the driver
    Given a planted change that moves one hook part to another folder
    When the acceptance suite is fixed for it
    Then only files under tests/acceptance/hooks/drivers/ change

  @TRC-P4
  Scenario: the suite runs in parallel and twice
    Given the acceptance suite
    When it runs on 4 parallel workers, and one scenario runs twice in a row
    Then all 3 runs give the same result, with 0 failures

  @TRC-P5
  Scenario: the note measures the result
    Given the moved tests and the old ones
    When a hook-layout refactor is counted against each
    Then the note gives the number of test files it touches before and after, and a recommendation for ayeo-io/compass-delivery#307
