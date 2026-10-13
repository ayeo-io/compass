#!/usr/bin/env python3
# =============================================================================
# compass - project command policy
# =============================================================================
# Whether Compass runs a command a project guardrail declared, and where that
# command's script is allowed to live. Kept apart from checks.py, the check
# registry, so the policy can be read and changed on its own.
#
# This module reads the PROJECT's own configuration, which means everything it
# decides is repository-controlled. That is fine for what it does: it is a
# defence against accidents and defaults, not against an attacker. The security
# decision lives in trust.py, is read first, and reads nothing from here.
#
# DEPENDENCY: PyYAML, bundled at cli/vendor/yaml/ and pinned in
# THIRD-PARTY-NOTICES.md. cli/compass_pkg/__init__.py resolves it, and it is
# the only third-party code Compass ships; everything else is the Python 3
# standard library. This module reaches it only indirectly, through the shared
# config reader in compass_pkg.tdd.
# =============================================================================
"""Policy for running commands a project guardrail declares."""
from __future__ import annotations

import os
from dataclasses import dataclass

from compass_pkg import project_settings
from compass_pkg.tdd import _read_config
from compass_pkg.trust import UNKNOWN, UNTRUSTED, contribution_trust, is_ci


@dataclass(frozen=True)
class Permission:
    """Whether a project command may run here. `kind` is `allowed`,
    `untrusted` or `disabled`; `reason` is the trust reason for `untrusted`
    and the setting to change for `disabled`."""
    allowed: bool
    kind: str
    reason: str


def command_permission(project_root, opt_in_from=None, env=None):
    """May Compass run a command this project declares? One answer for
    `command-passes` and `compass readiness` (ADR-061), so the two cannot
    order the decision differently.

    The trust decision comes first and the opt-in is read only when trust
    allows: a contribution can turn the opt-in on, but it cannot change what
    the CI runner reports about where the contribution came from. UNKNOWN on
    a laptop is ordinary and runs; UNKNOWN on CI is refused, because Compass
    cannot tell whose work it is.

    `opt_in_from` is the folder the opt-in is looked up from (the issue folder
    for `command-passes`, which finds the project upwards from it); it
    defaults to the project root.
    """
    state, reason = contribution_trust(env=env, project_root=project_root)
    if state == UNKNOWN and is_ci(env):
        state = UNTRUSTED
    if state == UNTRUSTED:
        return Permission(False, "untrusted", reason)
    if not _project_commands_allowed(opt_in_from or project_root):
        return Permission(False, "disabled", project_settings.named(
            project_root, "allow_project_commands", "true"))
    return Permission(True, "allowed", "")


def _project_commands_allowed(task_dir):
    """Has this project opted in to running commands its guardrails declare?

    Default false. A settings key in compass.yml (or .compass/config.yml, in a
    project that has not moved), read through project_settings. It sits beside
    the checks it authorises, so a declaration can authorise itself in the same
    pull request; the trust decision below is the control, not this key.

    This is NOT a security control: the file is in the repository, so a
    contribution can set it. It defends against accidents and defaults. The
    security control is the trust decision in cli/compass_pkg/trust.py, which
    is read first and reads nothing this file could influence.
    """
    value = _read_config(task_dir).get("allow_project_commands", False)
    if isinstance(value, str):
        return value.strip().lower() in ("true", "yes", "1", "on")
    return bool(value)


def _contained_script(script, project_root):
    """Resolve a declared script path, or None if it escapes the project.

    The comparison is made on the REAL path - symlinks resolved - because a
    symlink sitting inside the project and pointing out of it satisfies any
    check made on the string as written. A path check a symlink defeats is not
    a boundary.
    """
    if not isinstance(script, str) or not script.strip():
        return None
    root = os.path.realpath(project_root)
    candidate = os.path.realpath(os.path.join(root, script))
    if candidate != root and not candidate.startswith(root + os.sep):
        return None
    if not os.path.isfile(candidate):
        return None
    return candidate
