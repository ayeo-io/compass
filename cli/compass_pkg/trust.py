#!/usr/bin/env python3
# =============================================================================
# compass - the contribution trust decision
# =============================================================================
# DEPENDENCY: standard library only (json, os), on purpose: the fewer things
# it touches, the easier it is to check that it reads nothing the
# contribution could have written.
# =============================================================================
"""Is the contribution this process is checking a trusted one?

A project guardrail may declare a command, and `compass check` runs it. That is
useful on a maintainer's branch and dangerous on a contribution nobody has
reviewed, so the command runs only when this module says the contribution is
not untrusted.

WHAT THIS MODULE IS ALLOWED TO READ, AND WHY IT MATTERS.
The answer has to rest on something the contribution cannot forge. The pull
request being judged can edit everything inside the checkout - and on a
GitHub `pull_request` event that includes the workflow file itself,
because the workflow runs from the pull request's own merge ref. So a value
passed through a workflow `env:` block is repository-controlled and useless
here, as is any project configuration file.

This module therefore reads only state the CI runner owns:

  * the process environment, and
  * the event payload at the path `GITHUB_EVENT_PATH` names, which the runner
    writes outside the checkout.

It reads nothing inside the project root, imports no project configuration, and
never calls find_compass_dir(). That is the property that makes the refusal a
boundary rather than a preference, and tests/test_project_command_boundary.py
enforces it.
"""
from __future__ import annotations

import json
import os

# The three answers. UNKNOWN is not a failure to decide - it is a real and
# common state (a developer's laptop has no CI signal at all), and it means
# something different depending on whether this is CI. See is_ci().
TRUSTED = "trusted"
UNTRUSTED = "untrusted"
UNKNOWN = "unknown"


# Generic "this is a build machine" markers. Deliberately provider-neutral:
# the point is to notice we are on CI at all, not to identify which one.
# Anything more specific belongs in contribution_trust(), not here.
_CI_MARKERS = ("CI", "CONTINUOUS_INTEGRATION", "BUILD_NUMBER", "BUILD_ID")


def _env(env):
    return os.environ if env is None else env


def is_ci(env=None):
    """True when a generic CI marker is present.

    Kept separate from the trust decision because UNKNOWN means two different
    things. On a laptop it means "nobody is contributing anything, run it". On
    a build machine it means "something is being checked and I cannot tell
    whose work it is", which is the case that has to refuse.
    """
    env = _env(env)
    return any(str(env.get(k, "")).strip().lower() not in ("", "0", "false")
               for k in _CI_MARKERS)


def _read_payload(path):
    """Parse the runner's event payload, or None if it cannot be trusted.

    Anything unreadable or unexpected yields None, and every caller treats None
    as a refusal. There is no shape of broken payload that yields a trusted
    answer.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _head_repo(payload):
    """The repository a pull request came FROM, or None.

    GitHub publishes no environment variable for this. GITHUB_REPOSITORY names
    the base repository - the one being contributed to - so comparing it with
    itself would never detect anything. The head repository exists only in the
    payload, which is why this module reads a file at all.
    """
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return None
    head = pr.get("head")
    if not isinstance(head, dict):
        return None
    repo = head.get("repo")
    if not isinstance(repo, dict):
        return None
    name = repo.get("full_name")
    return name if isinstance(name, str) and name else None


def contribution_trust(env=None, project_root=None):
    """Decide whether the contribution being checked is trusted.

    Returns (state, reason). `reason` is the sentence a refusal prints, and it
    always names the signal that decided it - a refusal a reader cannot explain
    is one they will switch off.

    THE RULE IS POSITIVE CONFIRMATION, AND THAT IS THE POINT.
    Asking "has anything told me this is untrusted?" is backwards on a
    `pull_request` event, where the workflow file comes from the contribution:
    a fork could blank GITHUB_EVENT_NAME and CI, look like a developer's
    laptop, and have its command run. Erasing a signal is easier than forging
    one.

    So a CI run must be positively confirmed as trusted or it refuses. The
    confirmation has to come from the runner's own event payload, which must be
    readable AND outside the checkout - a payload path pointing into the
    repository is something the contribution could have written, and is
    rejected rather than believed.

    `project_root` is passed in rather than resolved here, so this module never
    has to go looking through the repository for anything.
    """
    env = _env(env)

    # An explicit `untrusted` is honoured anywhere. It only ever makes the
    # answer stricter, so there is no incentive to forge it.
    declared = str(env.get("COMPASS_CONTRIBUTION_TRUST", "")).strip().lower()
    if declared == "untrusted":
        return UNTRUSTED, (
            "the environment declares this contribution untrusted "
            "(COMPASS_CONTRIBUTION_TRUST=untrusted)"
        )

    if env.get("GITHUB_ACTIONS"):
        return _github_trust(env, project_root)

    # An explicit `trusted` is taken only where Compass recognises no provider
    # and therefore has nothing to contradict it. This trusts whoever wired the
    # CI configuration. Where the contribution can edit that configuration, it
    # is trusting the contribution - which is why it is documented as such and
    # why no recognised provider consults it.
    if declared == "trusted":
        return TRUSTED, (
            "the environment declares this contribution trusted "
            "(COMPASS_CONTRIBUTION_TRUST=trusted) and Compass recognizes no "
            "CI provider here that could contradict it"
        )

    if is_ci(env):
        return UNKNOWN, (
            "this is a CI runner, but Compass could not establish that the "
            "contribution is trusted: it recognizes no provider here and no "
            "signal says the contribution is trusted. Set "
            "COMPASS_CONTRIBUTION_TRUST=trusted from the runner - not from a "
            "file in the repository - if this build is running your own work"
        )

    return UNKNOWN, "no signal establishes whether this contribution is trusted"


def _github_trust(env, project_root):
    """The trust decision on GitHub Actions, where the payload can answer it.

    Every path out of here is either a positive confirmation or a refusal.
    Nothing falls through to "probably fine".
    """
    payload_path = env.get("GITHUB_EVENT_PATH")
    if not payload_path:
        return UNTRUSTED, (
            "this is a GitHub Actions runner but GITHUB_EVENT_PATH is not set, "
            "so nothing can confirm where the contribution came from. A "
            "contribution can blank an environment variable, so an absent "
            "signal is treated as untrusted rather than as absent"
        )

    if project_root and _is_inside(payload_path, project_root):
        return UNTRUSTED, (
            f"the event payload at {payload_path} is inside the repository "
            f"checkout, so the contribution being judged could have written "
            f"it. The runner writes its payload outside the checkout"
        )

    payload = _read_payload(payload_path)
    if payload is None:
        return UNTRUSTED, (
            f"the event payload at {payload_path} could not be read as JSON, "
            f"so nothing confirms where the contribution came from"
        )

    event = env.get("GITHUB_EVENT_NAME") or ""
    base = env.get("GITHUB_REPOSITORY")
    head = _head_repo(payload)

    if event == "pull_request":
        if not head or not base:
            return UNTRUSTED, (
                "this is a pull request, but the payload does not name the "
                "repository it came from, so it cannot be confirmed as "
                "anything"
            )
        if head != base:
            return UNTRUSTED, (
                f"this pull request comes from a fork ({head}) rather than "
                f"from {base}, so the contribution has not been reviewed by "
                f"anyone with write access. A COMPASS_CONTRIBUTION_TRUST "
                f"setting cannot override this: on a pull request the "
                f"workflow file comes from the contribution itself"
            )
        return TRUSTED, (
            f"this pull request comes from {head} itself, so its author has "
            f"write access to the repository"
        )

    if event in ("push", "workflow_dispatch", "schedule", "merge_group"):
        return TRUSTED, (
            f"this is a {event} event on {base or 'this repository'}, which "
            f"only someone with write access can cause"
        )

    return UNTRUSTED, (
        f"this is a GitHub Actions run on event {event or '(unset)'}, which "
        f"Compass cannot confirm as trusted. An unrecognized or blanked event "
        f"name is treated as untrusted rather than as absent"
    )


def _is_inside(path, root):
    """Is `path` inside `root`? Resolved, so a symlink cannot walk out."""
    try:
        root = os.path.realpath(root)
        path = os.path.realpath(path)
    except (OSError, ValueError):
        return True    # cannot tell -> treat as inside, which refuses
    return path == root or path.startswith(root + os.sep)
