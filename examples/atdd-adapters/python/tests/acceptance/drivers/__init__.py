"""The driver interface, and the names of the drivers the factory knows.

A driver is the only code that talks to the system, and it does so only the
way a real client does. It holds every check: a check passes by returning
and fails by raising `AssertionError` with what it expected and what it
found. The public methods are the interface the DSL calls. Each driver
implements only the protocol: `_request` asks the system to do one thing,
and `_listed` asks it which todos an account has in one state.
"""
from __future__ import annotations

import abc

#: The drivers the factory in conftest.py can choose. A name here whose
#: module does not exist yet is an error at setup in each scenario.
DRIVERS = ("api", "cli")


class SetupFailed(RuntimeError):
    """A Given the system refused, so the scenario cannot start."""


class TodoDriver(abc.ABC):
    def __init__(self, system):
        self.system = system
        self._refusal = None

    # --- the protocol, one per driver ---------------------------------------------

    @abc.abstractmethod
    def _request(self, action, email, name=None):
        """Ask the system to do `action` (account, add, complete or archive).
        Return None when it did, or the reason it gave when it refused."""

    @abc.abstractmethod
    def _listed(self, email, state):
        """The names of the account's todos in `state`, as the system lists them."""

    # --- Given --------------------------------------------------------------------

    def hasAccount(self, email):
        self._must("account", email)

    def hasOpen(self, email, name):
        self._must("add", email, name)

    def hasCompleted(self, email, name):
        self._must("add", email, name)
        self._must("complete", email, name)

    # --- When ---------------------------------------------------------------------

    def add(self, email, name):
        self._refusal = self._request("add", email, name)

    def complete(self, email, name):
        self._refusal = self._request("complete", email, name)

    def archive(self, email, name):
        self._refusal = self._request("archive", email, name)

    # --- Then ---------------------------------------------------------------------

    def confirmOpen(self, email, name):
        self._confirmListed(email, name, "open")

    def confirmCompleted(self, email, name):
        self._confirmListed(email, name, "completed")

    def confirmArchived(self, email, name):
        self._confirmListed(email, name, "archived")

    def confirmNotListed(self, email, name):
        for state in ("open", "completed", "archived"):
            listed = self._listed(email, state)
            if name in listed:
                raise AssertionError(
                    f"Expected no todo {name!r} for {email}, found it in {state}: {listed}")

    def confirmRefused(self, reason):
        if self._refusal is None:
            raise AssertionError(f"Expected a refusal saying {reason!r}, but the request was done")
        if reason not in self._refusal:
            raise AssertionError(f"Expected a refusal saying {reason!r}, got {self._refusal!r}")

    # --- shared steps -------------------------------------------------------------

    def _must(self, action, email, name=None):
        refusal = self._request(action, email, name)
        if refusal is not None:
            raise SetupFailed(f"{action} {email} {name or ''}: the system refused: {refusal}")

    def _confirmListed(self, email, name, state):
        listed = self._listed(email, state)
        if name not in listed:
            refused = f"; the last request was refused: {self._refusal}" if self._refusal else ""
            raise AssertionError(
                f"Expected {name!r} in the {state} todos of {email}, found {listed}{refused}")
