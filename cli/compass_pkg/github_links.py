# compass_pkg.github_links - the GitHub repository and default branch of a checkout
"""The repository and default branch that a link to a file on GitHub points at.

It reads local git only: the `origin` remote's URL and git's record of origin's
default branch, so the result depends only on the refs on disk. Before 9.0.0 it
also rewrote the links of the issue page for a GitHub comment; 9.0.0 posts no
issue page (ADR-091).
"""
# DEPENDENCY: standard library (re, subprocess). Imported by pull_request_link.
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass

#: Seconds one `git` call may take, the same bound as a `gh` call.
_TIMEOUT = 15
_GITHUB = re.compile(r"^(?:https://(?:[^@/]+@)?github\.com/|ssh://git@github\.com/"
                     r"|git@github\.com:)([A-Za-z0-9-]+/[A-Za-z0-9._-]+?)(?:\.git)?/?$")
_HEAD_PREFIX = "refs/remotes/origin/"


@dataclass(frozen=True)
class LinkBase:
    repo: str | None      # "owner/name" of origin, when it is a github.com URL
    branch: str | None    # origin's default branch, from refs/remotes/origin/HEAD


def _git(args, project_root):
    try:
        done = subprocess.run(["git", *args], cwd=project_root, capture_output=True,
                              text=True, timeout=_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


def link_base(project_root):
    """The repository and default branch links point at, each None when git does not say."""
    url = (_git(["config", "--get", "remote.origin.url"], project_root) or "").strip()
    found = _GITHUB.match(url)
    head = (_git(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"], project_root)
            or "").strip()
    branch = head[len(_HEAD_PREFIX):] if head.startswith(_HEAD_PREFIX) else None
    return LinkBase(found.group(1) if found else None, branch or None)
