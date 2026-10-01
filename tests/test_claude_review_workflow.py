"""The automatic Claude review must stay review-only.

`.github/workflows/claude-review.yml` runs Claude on every pull request.
It posts to the pull request, so three things must stay true: every action
is pinned to a commit, the job's token cannot write to the repository's
contents, and no tool it may use can commit or push. Its check is required
on `main` in place of a human approval, so a fourth: the job fails unless
Claude's verdict is PASS.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

import pytest
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


def test_the_review_authenticates_by_federation_with_no_stored_key():
    """The job swaps GitHub's OIDC token for a short-lived Anthropic token,
    so no API key or OAuth token is stored to leak or rotate."""
    step = next(s for s in _job()["steps"]
                if "claude-code-action" in s.get("uses", ""))
    inputs = step["with"]
    for key, var in (("anthropic_federation_rule_id", "ANTHROPIC_FEDERATION_RULE_ID"),
                     ("anthropic_organization_id", "ANTHROPIC_ORGANIZATION_ID"),
                     ("anthropic_service_account_id", "ANTHROPIC_SERVICE_ACCOUNT_ID"),
                     ("anthropic_workspace_id", "ANTHROPIC_WORKSPACE_ID")):
        assert inputs.get(key) == "${{ vars." + var + " }}", (key, inputs.get(key))
    assert "anthropic_api_key" not in inputs and "claude_code_oauth_token" not in inputs
    assert _job()["permissions"].get("id-token") == "write"
    assert "${{ secrets." not in WORKFLOW.read_text(encoding="utf-8")


def _verdict_step():
    steps = _job()["steps"]
    review = next(i for i, s in enumerate(steps)
                  if "claude-code-action" in s.get("uses", ""))
    later = [s for s in steps[review + 1:] if "run" in s]
    assert later, "no step after the review reads its verdict"
    return steps[review], later[0]


def test_the_review_returns_its_verdict_as_structured_output():
    """A verdict read from a field cannot be misread the way a comment can."""
    review, check = _verdict_step()
    args = review["with"]["claude_args"]
    schema = json.loads(re.search(r"--json-schema '([^']+)'", args).group(1))
    assert schema["required"] == ["verdict"], schema
    assert schema["properties"]["verdict"]["enum"] == ["PASS", "FAIL"], schema
    assert check["env"]["RESULT"] == (
        "${{ steps." + review["id"] + ".outputs.structured_output }}"), check["env"]


@pytest.mark.parametrize("result, passes", [
    ('{"verdict": "PASS"}', True),
    ('{"verdict": "FAIL"}', False),
    ("", False),
    ("{}", False),
    ("not json", False),
    ('{"verdict": "pass"}', False),
])
def test_the_job_fails_unless_the_verdict_is_pass(result, passes):
    """The review check is required on main, so it must be red on a FAIL
    and on a missing verdict, and green only on PASS."""
    _, check = _verdict_step()
    r = subprocess.run(["bash", "-c", check["run"]], env={**os.environ, "RESULT": result},
                       capture_output=True, text=True)
    assert (r.returncode == 0) == passes, (result, r.returncode, r.stdout, r.stderr)
