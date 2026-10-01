"""The automatic Claude review must stay review-only.

`.github/workflows/claude-review.yml` runs Claude on every pull request.
It holds a repository secret and posts to the pull request, so three things
must stay true: every action is pinned to a commit, the job's token cannot
write to the repository's contents, and no tool it may use can commit or
push.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "claude-review.yml"


def _job():
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return data["jobs"]["review"]


def test_every_action_is_pinned_to_a_commit():
    uses = [step["uses"] for step in _job()["steps"] if "uses" in step]
    assert uses
    for ref in uses:
        assert re.search(r"@[0-9a-f]{40}$", ref), f"{ref} is not pinned to a commit"


def test_the_token_cannot_write_contents():
    permissions = _job()["permissions"]
    assert permissions.get("contents") == "read", permissions


def test_no_allowed_tool_can_commit_or_push():
    step = next(s for s in _job()["steps"]
                if "claude-code-action" in s.get("uses", ""))
    allowed = re.search(r'--allowedTools "([^"]+)"', step["with"]["claude_args"]).group(1)
    tools = [t.strip() for t in allowed.split(",")]
    for tool in tools:
        assert not re.search(r"\bgit\b|Write|Edit|push|commit", tool), tool
    assert any(t.startswith("Bash(gh pr comment") for t in tools), tools
