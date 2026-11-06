"""The protocol driver interface, and the factory that picks a driver.

A driver is the only code that runs the hook and the only code that checks
what it did. It reaches the hook the way a real client does: Claude Code
sends a JSON event on standard input and reads the exit code and standard
error.

9.0.0 ships one client, Claude Code; the Codex adapter and its driver stay on
8.x (ayeo-io/compass-delivery#345, decision 5). The factory still takes a
client name, so a second client adds a driver and a name here and no
specification changes.
"""
from __future__ import annotations

import os
from typing import Protocol


class HookDriver(Protocol):
    """What the DSL can ask of a driver. Each set-up method builds part of a
    real install or project; each action runs the hook once; each `confirm`
    method returns when the check holds and raises AssertionError, with what
    it expected and what it found, when it does not."""

    # --- the install -------------------------------------------------------
    def hasCompleteInstall(self) -> None: ...
    def hasInstallMissing(self, part: str) -> None: ...
    def hasInstallWithUnreadable(self, part: str) -> None: ...

    # --- the project -------------------------------------------------------
    def hasOptedInProject(self, issue: str, code_globs: list) -> None: ...
    def hasGuestRepository(self) -> None: ...
    def hasProjectWithNoIssues(self) -> None: ...
    def hasSettingsThatDoNotParse(self) -> None: ...
    def hasSettingsWithCodeGlobs(self, value: str) -> None: ...
    def hasUnreadableSettings(self) -> None: ...
    def hasIssueWithNoApproachRecord(self, issue: str) -> None: ...

    # --- the machine -------------------------------------------------------
    def hasNoPython(self) -> None: ...
    def hasPythonThatFailsFor(self, check: str, status: int) -> None: ...
    def cannotMakeTemporaryFile(self, attempt: int) -> None: ...

    # --- what the agent does -----------------------------------------------
    def edits(self, path: str) -> None: ...
    def reads(self, path: str) -> None: ...
    def runs(self, command: str) -> None: ...

    # --- what the person sees ----------------------------------------------
    def confirmAllowed(self, silently: bool) -> None: ...
    def confirmRefused(self, code: str, naming: str | None) -> None: ...
    def confirmRefusalSays(self, text: str) -> None: ...
    def confirmRefusalDoesNotSay(self, text: str) -> None: ...


CLIENTS = ("claude-code",)


def clients():
    """The clients a run covers: all of them, or the one `COMPASS_HOOK_CLIENT` names."""
    chosen = os.environ.get("COMPASS_HOOK_CLIENT")
    return (chosen,) if chosen else CLIENTS


def driver_for(workspace, client) -> HookDriver:
    """A new driver for one scenario, in its own workspace folder."""
    if client == "claude-code":
        from tests.acceptance.hooks.drivers.claude_code import ClaudeCodeDriver
        return ClaudeCodeDriver(workspace)
    raise ValueError(f"COMPASS_HOOK_CLIENT is {client!r}; expected 'claude-code'")
