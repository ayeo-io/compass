"""The vocabulary the hook specifications are written in.

Each method is one Given, When or Then line. Set-up methods start `has`,
actions use the agent's verb and checks start `confirm`. The DSL fills in
defaults, aliases the identifiers a scenario names, and passes each call to
the driver. It makes no check itself: every `confirm` is the driver's.
"""
from __future__ import annotations

from tests.acceptance.hooks.alias import Aliases
from tests.acceptance.hooks.drivers import driver_for
from tests.acceptance.hooks.drivers.base import HOOK_PARTS  # noqa: F401  (for the specifications)

#: The issue a scenario works on when it names none.
DEFAULT_ISSUE = "matrix"
#: The code globs an opted-in project declares when a scenario names none.
DEFAULT_CODE_GLOBS = ("packaging/**",)


class _Part:
    def __init__(self, driver, alias):
        self._driver = driver
        self._alias = alias


class Install(_Part):
    """The Compass install the hook runs from."""

    def isComplete(self):
        self._driver.hasCompleteInstall()

    def isMissing(self, part):
        self._driver.hasInstallMissing(part)

    def hasUnreadable(self, part):
        self._driver.hasInstallWithUnreadable(part)


class Project(_Part):
    """The project the agent works in."""

    def isOptedIn(self, issue=DEFAULT_ISSUE, code_globs=DEFAULT_CODE_GLOBS):
        self._driver.hasOptedInProject(self._alias(issue), list(code_globs))

    def isGuestRepository(self):
        self._driver.hasGuestRepository()

    def hasNoIssues(self):
        self._driver.hasProjectWithNoIssues()

    def hasSettingsThatDoNotParse(self):
        self._driver.hasSettingsThatDoNotParse()

    def hasCodeGlobsOfTheWrongShape(self, value):
        self._driver.hasSettingsWithCodeGlobs(value)

    def hasUnreadableSettings(self):
        self._driver.hasUnreadableSettings()

    def hasIssueWithNoApproachRecord(self, issue=DEFAULT_ISSUE):
        self._driver.hasIssueWithNoApproachRecord(self._alias(issue))


class Machine(_Part):
    """The machine the hook runs on: its tools, not Compass's own code."""

    def hasNoPython(self):
        self._driver.hasNoPython()

    def hasPythonThatFailsFor(self, check, status=1):
        self._driver.hasPythonThatFailsFor(check, status)

    def cannotMakeTemporaryFile(self, attempt=1):
        self._driver.cannotMakeTemporaryFile(attempt)


class Agent(_Part):
    """What the agent asks to do. Each action is one tool call the hook sees."""

    def edits(self, path="src/app.py"):
        self._driver.edits(path)

    def reads(self, path="notes.txt"):
        self._driver.reads(path)

    def runs(self, command):
        self._driver.runs(command)


class Hook(_Part):
    """What the person sees the hook do."""

    def confirmAllowed(self):
        self._driver.confirmAllowed(silently=False)

    def confirmAllowedSilently(self):
        self._driver.confirmAllowed(silently=True)

    def confirmRefused(self, code, naming=None):
        self._driver.confirmRefused(code, naming)

    def confirmRefusalSays(self, text):
        self._driver.confirmRefusalSays(text)

    def confirmRefusalDoesNotSay(self, text):
        self._driver.confirmRefusalDoesNotSay(text)


class Dsl:
    """One per scenario, with its own workspace and its own aliases."""

    def __init__(self, workspace, client):
        alias = Aliases()
        driver = driver_for(workspace, client)
        self.install = Install(driver, alias)
        self.project = Project(driver, alias)
        self.machine = Machine(driver, alias)
        self.agent = Agent(driver, alias)
        self.hook = Hook(driver, alias)
