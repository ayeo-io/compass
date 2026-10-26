"""The pre-tool hook refuses when it cannot check, and only then.

Executable specifications for the client-observable scenarios of
`tests/test_hook_failure_matrix.py` (HFM, CGS) and the hook scenarios of
`tests/test_directory_validator.py` (TRC-A3). Each Given, When or Then line
is one DSL call; the docstring holds the scenario as a person reads it.

The pilot is ayeo-io/compass-delivery#306, "Pilot the four-layer acceptance
test model on the pre-tool hook tests", in the project's private delivery
record.
"""
from __future__ import annotations

import pytest

#: The checks whose Python can fail on its own, each with the code path it
#: guards, as the person names them.
CHECKS = {
    "code globs": "packaging/app.cfg",
    "delivery approach": "src/app.py",
    "acceptance criteria": "src/app.py",
    "red record": "src/app.py",
}
PARTS = ("pre-tool-project.sh", "pre-tool-guards.sh", "pre-tool-targets.sh",
         "pre-tool-bash-writes.sh", "pre-tool-issue.sh", "pre-tool-checks.sh")


# --- every check passes --------------------------------------------------------------

@pytest.mark.parametrize("path", ["src/app.py", "packaging/app.cfg"])
def test_hfm_1_an_edit_whose_checks_all_pass_is_allowed(dsl, path):
    """
    Given a complete install
    And an opted-in project whose issue passes every check
    When the agent edits a code file
    Then the hook allows it
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.agent.edits(path)
    dsl.hook.confirmAllowed()


# --- a check that cannot run refuses -------------------------------------------------

@pytest.mark.parametrize("status", [1, 3])
@pytest.mark.parametrize("check", list(CHECKS))
def test_hfm_1_a_check_that_cannot_run_refuses_and_names_itself(dsl, check, status):
    """
    Given a complete install
    And an opted-in project
    And a python3 that fails for one check
    When the agent edits the file that check guards
    Then the hook refuses as reader-failed, naming the check
    And it says the check could not run
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.machine.hasPythonThatFailsFor(check, status=status)
    dsl.agent.edits(CHECKS[check])
    dsl.hook.confirmRefused(code="reader-failed", naming=check)
    dsl.hook.confirmRefusalSays("could not run")


def test_hfm_1_the_red_record_refusal_gives_its_cause(dsl):
    """
    Given a complete install
    And an opted-in project
    And a python3 that fails for the red record check
    When the agent edits a code file
    Then the refusal shows what python3 printed
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.machine.hasPythonThatFailsFor("red record", status=1)
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmRefusalSays("failing on purpose")


@pytest.mark.parametrize("path", ["src/app.py", "packaging/app.cfg"])
def test_hfm_2_with_no_python3_the_refusal_says_so(dsl, path):
    """
    Given a complete install
    And an opted-in project
    And a machine with no python3
    When the agent edits a code file
    Then the hook refuses as python-missing
    And it says python3 was not found on the PATH
    And it does not say the assessment did not complete
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.machine.hasNoPython()
    dsl.agent.edits(path)
    dsl.hook.confirmRefused(code="python-missing")
    dsl.hook.confirmRefusalSays("python3 was not found on the PATH")
    dsl.hook.confirmRefusalDoesNotSay("did not complete")


@pytest.mark.parametrize("check, attempt", [("delivery approach", 1),
                                            ("acceptance criteria", 2)])
def test_hfm_1_a_temporary_file_that_cannot_be_made_refuses(dsl, check, attempt):
    """
    Given a complete install
    And an opted-in project
    And a machine that cannot make a temporary file for one check
    When the agent edits a code file
    Then the hook refuses as reader-failed, naming the check
    And it says it could not make a temporary file
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.machine.cannotMakeTemporaryFile(attempt=attempt)
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmRefused(code="reader-failed", naming=check)
    dsl.hook.confirmRefusalSays("temporary file")


# --- the project's settings ----------------------------------------------------------

def test_hfm_3_settings_that_do_not_parse_refuse_and_name_the_fix(dsl):
    """
    Given a complete install
    And an opted-in project
    And its settings file does not parse
    When the agent edits a file its code globs would guard
    Then the hook refuses as config-invalid, naming the settings file as the fix
    And it does not tell the person to fix the install
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.project.hasSettingsThatDoNotParse()
    dsl.agent.edits("packaging/app.cfg")
    dsl.hook.confirmRefused(code="config-invalid", naming="the settings file")
    dsl.hook.confirmRefusalDoesNotSay("fix the install")


def test_hfm_3_a_shell_write_refusal_names_the_file_it_found(dsl):
    """
    Given a complete install
    And an opted-in project
    And its settings file does not parse
    When the agent runs a command that writes a file its code globs would guard
    Then the hook refuses, naming that file
    And it names no unknown target
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.project.hasSettingsThatDoNotParse()
    dsl.agent.runs("echo x > packaging/app.cfg")
    dsl.hook.confirmRefused(naming="packaging/app.cfg")
    dsl.hook.confirmRefusalDoesNotSay("Edit target: ?")


@pytest.mark.parametrize("value", ["'packaging/**'", "[1, 2]", "{a: b}"])
def test_cgs_1_code_globs_of_the_wrong_shape_refuse(dsl, value):
    """
    Given a complete install
    And an opted-in project
    And its code globs are not a list of strings
    When the agent edits a file
    Then the hook refuses as config-invalid, naming the settings file as the fix
    And it says the globs must be a list of strings
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.project.hasCodeGlobsOfTheWrongShape(value)
    dsl.agent.edits("packaging/app.cfg")
    dsl.hook.confirmRefused(code="config-invalid", naming="the settings file")
    dsl.hook.confirmRefusalSays("a list of strings")


def test_hfm_1_unreadable_settings_still_refuse(dsl):
    """
    Given a complete install
    And an opted-in project
    And it has no issues
    And its settings file cannot be read
    When the agent edits a code file
    Then the hook refuses
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.project.hasNoIssues()
    dsl.project.hasUnreadableSettings()
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmRefused()


# --- the issue's own records ---------------------------------------------------------

def test_hfm_4_a_missing_approach_record_is_reported_as_missing(dsl):
    """
    Given a complete install
    And an opted-in project
    And its issue has no delivery approach record
    When the agent edits a code file
    Then the hook refuses as no-delivery-approach, saying the record is missing
    And it does not say a check could not run
    """
    dsl.install.isComplete()
    dsl.project.isOptedIn()
    dsl.project.hasIssueWithNoApproachRecord()
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmRefused(code="no-delivery-approach", naming="has no delivery-approach.md")
    dsl.hook.confirmRefusalDoesNotSay("could not run")


# --- the install ---------------------------------------------------------------------

def test_hfm_1_a_missing_python_helper_refuses_in_a_project(dsl):
    """
    Given an install missing its Python helper
    And an opted-in project
    When the agent edits a code file
    Then the hook refuses, naming the helper
    """
    dsl.install.isMissing("compass-python.sh")
    dsl.project.isOptedIn()
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmRefused(naming="compass-python.sh")


def test_hfm_1_a_missing_python_helper_stays_silent_in_a_guest_repository(dsl):
    """
    Given an install missing its Python helper
    And a repository that never opted in
    When the agent edits a code file
    Then the hook allows it and says nothing
    """
    dsl.install.isMissing("compass-python.sh")
    dsl.project.isGuestRepository()
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmAllowedSilently()


def test_trc_a3_a_complete_install_allows_a_read_in_a_guest_repository(dsl):
    """
    Given a complete install
    And a repository that never opted in
    When the agent reads a file
    Then the hook allows it
    """
    dsl.install.isComplete()
    dsl.project.isGuestRepository()
    dsl.agent.reads()
    dsl.hook.confirmAllowed()


@pytest.mark.parametrize("part", PARTS)
def test_trc_a3_a_missing_part_refuses_every_call(dsl, part):
    """
    Given an install missing one part of the hook
    And a repository that never opted in
    When the agent reads a file
    Then the hook refuses as reader-failed, naming the part
    """
    dsl.install.isMissing(part)
    dsl.project.isGuestRepository()
    dsl.agent.reads()
    dsl.hook.confirmRefused(code="reader-failed", naming=part)


@pytest.mark.parametrize("part", PARTS)
def test_trc_a3_an_unreadable_part_refuses_every_call(dsl, part):
    """
    Given an install with one part of the hook it cannot read
    And a repository that never opted in
    When the agent reads a file
    Then the hook refuses as reader-failed, naming the part
    """
    dsl.install.hasUnreadable(part)
    dsl.project.isGuestRepository()
    dsl.agent.reads()
    dsl.hook.confirmRefused(code="reader-failed", naming=part)


@pytest.mark.parametrize("helper", ["compass-python.sh", "settings-files.sh"])
def test_trc_a3_an_unreadable_helper_still_refuses_a_code_edit(dsl, helper):
    """
    Given an install with a shared helper it cannot read
    And an opted-in project
    And it has no issues
    When the agent edits a code file
    Then the hook refuses
    """
    dsl.install.hasUnreadable(helper)
    dsl.project.isOptedIn()
    dsl.project.hasNoIssues()
    dsl.agent.edits("src/app.py")
    dsl.hook.confirmRefused()
