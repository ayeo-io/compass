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


# The review reads the review rules (#264). The rules and the CLI that
# prints them come from the base branch, so a pull request cannot change
# what it is reviewed against.

def _step(step_id):
    return next((s for s in _job()["steps"] if s.get("id") == step_id), None)


def test_a_rules_step_runs_before_the_review():
    ids = [s.get("id") for s in _job()["steps"]]
    assert "rules" in ids, ids
    assert ids.index("rules") < ids.index("review"), ids


def test_the_rules_and_the_cli_come_from_the_base_branch():
    run = _step("rules")["run"]
    assert 'git fetch --depth=1 origin "$BASE_REF"' in run, run
    assert "git worktree add" in run and "FETCH_HEAD" in run, run
    assert re.search(r'"\$BASE"/cli/compass policy review-rules', run), run
    assert '--rules "$BASE/governance/review-rules.yml"' in run, run
    assert "gh api --paginate" in run and "/pulls/$PR_NUMBER/files" in run, run


def test_the_rules_step_takes_pull_request_values_through_env_only():
    """A value the pull request controls never lands in the script text."""
    step = _step("rules")
    assert "${{" not in step["run"], step["run"]
    assert step["env"]["BASE_REF"] == "${{ github.base_ref }}"
    assert step["env"]["PR_NUMBER"] == "${{ github.event.pull_request.number }}"


def test_the_prompt_holds_the_rules_and_asks_for_rr_ids():
    prompt = _step("review")["with"]["prompt"]
    assert "${{ steps.rules.outputs.rules }}" in prompt, prompt
    assert "RR-" in prompt and "Do not flag" in prompt, prompt


def test_one_rules_file_and_no_swallowed_failure():
    """Only the base branch's rules file is read, and a failed call is not
    hidden: argparse keeps the last --rules, and `|| true` would turn a
    failure into an empty rule list."""
    run = _step("rules")["run"]
    assert run.count("--rules") == 1, run
    assert "|| true" not in run and "|| :" not in run, run
    assert "< <(" not in run, "a process substitution hides its exit status"


def test_the_output_delimiter_is_random():
    run = _step("rules")["run"]
    assert re.search(r'delim="RULES_\$\(openssl rand -hex 16\)"', run), run
    assert 'echo "rules<<$delim"' in run, run


def _run_rules_step(tmp_path, gh_body, changed):
    """Run the rules step's script with stub git, gh and python3."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("git", "exit 0"), ("gh", gh_body),
                       ("python3", "echo RULES-PRINTED; exit 0")):
        stub = bin_dir / name
        stub.write_text("#!/bin/sh\n" + body + "\n")
        stub.chmod(0o755)
    (tmp_path / "base" / "governance").mkdir(parents=True)
    (tmp_path / "base" / "governance" / "review-rules.yml").write_text("rules: []\n")
    out = tmp_path / "out.txt"
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "BASE_REF": "main", "PR_NUMBER": "1",
           "GITHUB_REPOSITORY": "o/r", "RUNNER_TEMP": str(tmp_path),
           "GITHUB_OUTPUT": str(out), "GH_TOKEN": "x", "CHANGED_FILES": changed}
    r = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", _step("rules")["run"]],
                       env=env, capture_output=True, text=True)
    return r, (out.read_text() if out.exists() else "")


def test_a_short_file_listing_fails_the_step(tmp_path):
    """The files API stops at 3,000 files without an error (#266). A listing
    shorter than the pull request's own count must fail the step."""
    r, out = _run_rules_step(tmp_path, "printf 'a.py\\nb.py\\n'", "3")
    assert r.returncode != 0, r.stdout + r.stderr
    assert "rules<<" not in out
    assert "listed 2 of 3" in r.stdout + r.stderr


@pytest.mark.parametrize("changed", ["", "abc"])
def test_a_missing_count_fails_the_step(tmp_path, changed):
    """A count the step cannot compare is a failure, not a pass."""
    r, out = _run_rules_step(tmp_path, "printf 'a.py\\nb.py\\n'", changed)
    assert r.returncode != 0, r.stdout + r.stderr
    assert "rules<<" not in out


def test_a_full_file_listing_prints_the_rules(tmp_path):
    """The guard does not refuse a listing that matches the count."""
    r, out = _run_rules_step(tmp_path, "printf 'a.py\\nb.py\\n'", "2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "RULES-PRINTED" in out


def test_the_changed_file_count_comes_through_env():
    step = _step("rules")
    assert step["env"]["CHANGED_FILES"] == "${{ github.event.pull_request.changed_files }}"


def test_a_failed_file_listing_fails_the_step(tmp_path):
    """A pull request over GitHub's diff size limit makes the listing fail.
    The step must then fail, not review with no rules."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("git", "exit 0"), ("gh", "echo 'HTTP 406' >&2; exit 1"),
                       ("python3", "echo SHOULD-NOT-RUN; exit 0")):
        stub = bin_dir / name
        stub.write_text("#!/bin/sh\n" + body + "\n")
        stub.chmod(0o755)
    out = tmp_path / "out.txt"
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "BASE_REF": "main", "PR_NUMBER": "1",
           "GITHUB_REPOSITORY": "o/r", "RUNNER_TEMP": str(tmp_path),
           "GITHUB_OUTPUT": str(out), "GH_TOKEN": "x"}
    r = subprocess.run(["bash", "-e", "-o", "pipefail", "-c", _step("rules")["run"]],
                       env=env, capture_output=True, text=True)
    assert r.returncode != 0, r.stdout + r.stderr
    assert not out.exists() or "rules<<" not in out.read_text()


def test_the_verdict_counts_a_blocking_rule():
    prompt = _step("review")["with"]["prompt"]
    assert re.search(r"blocking review rule", prompt), prompt
