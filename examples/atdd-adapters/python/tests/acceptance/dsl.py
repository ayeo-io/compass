"""The vocabulary the todo specifications are written in.

Each method is one Given, When or Then line. Set-up methods start `has`,
actions use the person's own verb and checks start `confirm`. The DSL fills
in defaults, puts every account email through the alias helper and passes
the call on. It makes no check itself: each `confirm` is the driver's, and so
is each failure. A method here has the same name as the driver method it
calls.
"""
from __future__ import annotations

from tests.acceptance.alias import Aliases

#: The account a scenario works in when it names none.
DEFAULT_EMAIL = "user@example.com"


class _Scenario:
    """Who the scenario acts as: the account its latest Given made."""

    def __init__(self):
        self.account = None


class _Part:
    def __init__(self, driver, alias, scenario):
        self._driver = driver
        self._alias = alias
        self._scenario = scenario


class User(_Part):
    """The person who uses the todo service."""

    def hasAccount(self, email=DEFAULT_EMAIL):
        self._scenario.account = self._alias(email)
        self._driver.hasAccount(self._scenario.account)


class Todo(_Part):
    """The todos of the account the scenario acts as."""

    def hasOpen(self, name):
        self._driver.hasOpen(self._scenario.account, name)

    def hasCompleted(self, name):
        self._driver.hasCompleted(self._scenario.account, name)

    def add(self, name):
        self._driver.add(self._scenario.account, name)

    def complete(self, name):
        self._driver.complete(self._scenario.account, name)

    def archive(self, name):
        self._driver.archive(self._scenario.account, name)

    def confirmOpen(self, name):
        self._driver.confirmOpen(self._scenario.account, name)

    def confirmCompleted(self, name):
        self._driver.confirmCompleted(self._scenario.account, name)

    def confirmArchived(self, name):
        self._driver.confirmArchived(self._scenario.account, name)

    def confirmNotListed(self, name, owner=None):
        account = self._alias(owner) if owner else self._scenario.account
        self._driver.confirmNotListed(account, name)

    def confirmRefused(self, reason):
        self._driver.confirmRefused(reason)


class Dsl:
    """One per scenario, with its own aliases and its own account."""

    def __init__(self, driver):
        alias = Aliases()
        scenario = _Scenario()
        self.user = User(driver, alias, scenario)
        self.todo = Todo(driver, alias, scenario)
