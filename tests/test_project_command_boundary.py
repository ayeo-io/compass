"""Project commands are a trust boundary.

A project guardrail may declare `check: command-passes`, and `compass check`
runs what it declares. These tests pin the two conditions that now sit in front
of that execution, and the safer way to declare the work.

The two conditions are not equal, and the tests keep them unequal:

  * The **trust decision** is read from state the CI runner owns - the process
    environment, and the event payload whose path the environment names. A
    contribution cannot forge it. It is evaluated first.
  * The **opt-in** is read from `.compass/config.yml`, which any contribution
    can edit. It is evaluated second, and only for a contribution that was not
    already refused.

Scenario ids trace to project-commands-are-a-trust-boundary/
acceptance-criteria.md - group A (opt-in), group B (the refusal), group C (the
script form), group E (a disabled guardrail does not go quiet).
"""

# These tests read the per-check detail (name, PASS/FAIL, reason) that
# `compass check --verbose` prints.
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"


def _run_check(project_root: Path,
               extra_env: Optional[Dict[str, str]] = None,
               clear_ci: bool = True) -> subprocess.CompletedProcess:
    """Run `compass check` in a fixture project.

    The real environment is never mutated. `clear_ci` drops any CI variables
    the developer's own shell (or this suite's own CI run) happens to carry, so
    a test that means "a laptop" gets a laptop rather than whatever machine it
    is running on.
    """
    env = dict(os.environ)
    if clear_ci:
        for key in list(env):
            if key.startswith(("GITHUB_", "GITLAB_", "CIRCLE", "BUILDKITE")) \
                    or key in ("CI", "CONTINUOUS_INTEGRATION", "COMPASS_CONTRIBUTION_TRUST"):
                env.pop(key)
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(CLI_PATH), "check", "--verbose"],
        cwd=str(project_root), capture_output=True, text=True, env=env, timeout=60,
    )


def _fork_pr_env(tmp_path: Path) -> Dict[str, str]:
    """The environment GitHub gives a job running against a pull request that
    came from a fork. The head repository is not published as a variable - it
    exists only in the event payload the runner writes, which is why the
    payload is read at all.

    The payload goes in `runner/`, a sibling of the checkout, because that is
    where a real runner writes it - outside the tree the contribution can edit.
    A fixture that put it inside the project would make the containment test in
    this file fail for a reason that does not exist on a runner.
    """
    runner = tmp_path / "runner"
    runner.mkdir(exist_ok=True)
    payload = runner / "event.json"
    payload.write_text(json.dumps({
        "pull_request": {
            "head": {"repo": {"full_name": "outsider/compass", "fork": True}},
            "base": {"repo": {"full_name": "ayeo-io/compass"}},
        }
    }))
    return {
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REPOSITORY": "ayeo-io/compass",
        "GITHUB_EVENT_PATH": str(payload),
    }


def _make_project(tmp_path: Path,
                  project_guardrails: Optional[List[Dict[str, Any]]] = None,
                  config_extra: str = "",
                  risk: str = "critical") -> Path:
    """A minimal Compass project using the real shipped governance files.

    Built under `project/` rather than directly in tmp_path, so runner-owned
    state (the event payload) has somewhere to live outside the checkout.
    """
    tmp_path = tmp_path / "project"
    tmp_path.mkdir(parents=True, exist_ok=True)
    gov_dst = tmp_path / "governance"
    gov_dst.mkdir()
    gov_src = FRAMEWORK_ROOT / "governance"
    shutil.copyfile(gov_src / "routing-policy.yml", gov_dst / "routing-policy.yml")
    guardrails = yaml.safe_load((gov_src / "guardrails.yml").read_text())
    guardrails["project"] = project_guardrails if project_guardrails is not None else []
    (gov_dst / "guardrails.yml").write_text(yaml.safe_dump(guardrails, sort_keys=False))

    compass_dir = tmp_path / ".compass"
    task_dir = compass_dir / "work" / "test-task"
    task_dir.mkdir(parents=True)
    (task_dir / "evidence").mkdir()
    (compass_dir / "current-task").write_text("test-task\n")
    (compass_dir / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n" + config_extra)

    (task_dir / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0",
        "task": "test-task",
        "created": "2026-08-22",
        "status": "active",
        "assessment": {"risk": risk, "familiarity": "brownfield-mapped",
                       "size": "standard", "goal": "delivery"},
        "delivery_approach": "feature",
        "scenarios": [{"id": "TRC-X1", "intent": "INT-1",
                       "tests": ["tests/test_project_command_boundary.py::test_stub"]}],
        "changed_files": [],
        "evidence": [],
        "gates": [{"id": "verify.architecture", "status": "pending", "evidence": []}],
    }))
    return tmp_path


def _sentinel_guardrail(sentinel: Path) -> List[Dict[str, Any]]:
    """A project guardrail whose command leaves a trace when it runs.

    Asserting on the check's message alone would not prove the command was
    skipped - only that the message said so. The sentinel is the difference
    between those two claims.
    """
    return [{
        "id": "F1",
        "name": "Fitness function",
        "statement": "A declared project command.",
        "checks": ["command-passes"],
        "params": {"command": f"touch {sentinel}"},
        "checked_at": ["verify"],
    }]


# ---------------------------------------------------------------------------
# Group B - the untrusted-context refusal. This is the security control.
# ---------------------------------------------------------------------------

def test_b1_untrusted_ci_context_refuses_the_command(tmp_path):
    """`TRC-B1`: a command is refused when the CI environment says the
    contribution is untrusted - here, a pull request from a fork.

    The project has opted in, so the opt-in is not what stops it.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="allow_project_commands: true\n",
    )

    result = _run_check(project, extra_env=_fork_pr_env(tmp_path))
    output = result.stdout + result.stderr

    assert not sentinel.exists(), (
        "the declared command executed on an untrusted contribution - the "
        "refusal did not stop it:\n" + output)
    assert "refus" in output.lower(), (
        "the check did not report a refusal, so a reader cannot tell the "
        "command was skipped on purpose:\n" + output)
    assert "fork" in output.lower(), (
        "the refusal did not name the signal that decided it:\n" + output)


def test_b2_repository_config_cannot_disable_the_refusal(tmp_path):
    """`TRC-B2`: the repository must not be able to switch the refusal off.

    The scenario the spec calls the one that decides whether this issue
    produces a boundary or a preference. The project opts in as loudly as it
    can; the refusal still holds, and the report says the opt-in was ignored
    rather than leaving a reader to guess why their setting did nothing.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra=("allow_project_commands: true\n"
                      "allow_untrusted_project_commands: true\n"),
    )

    result = _run_check(project, extra_env=_fork_pr_env(tmp_path))
    output = result.stdout + result.stderr

    assert not sentinel.exists(), (
        "a setting inside the repository switched the refusal off - this is a "
        "preference, not a boundary:\n" + output)
    assert "ignored" in output.lower(), (
        "the report did not say the project's attempt to permit the command "
        "was ignored:\n" + output)


def test_b2_trust_module_reads_nothing_inside_the_project(tmp_path):
    """`TRC-B2`, the mechanism rather than the message.

    The refusal is unforgeable only because the module deciding it cannot read
    anything the contribution could have written. Asserting that from the
    outside - by watching every file the call opens - is stronger than reading
    the source and believing it.
    """
    import sys

    sys.path.insert(0, str(FRAMEWORK_ROOT / "cli"))
    from compass_pkg import trust

    project = _make_project(tmp_path, project_guardrails=[])
    # A file the contribution controls, sitting where a tempted implementation
    # would look for it.
    (project / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nallow_untrusted_project_commands: true\n")

    opened: list[str] = []

    def audit(event, args):
        if event == "open" and args and isinstance(args[0], (str, bytes)):
            path = args[0].decode() if isinstance(args[0], bytes) else args[0]
            opened.append(os.path.realpath(path))

    sys.addaudithook(audit)
    trust.contribution_trust(env=dict(_fork_pr_env(tmp_path)))

    project_root = os.path.realpath(str(project))
    inside = [p for p in opened if p.startswith(project_root + os.sep)]
    assert not inside, (
        "trust.py opened a file inside the project root, so the contribution "
        "being judged could influence the verdict: " + repr(inside))


def test_b5_unrecognised_ci_provider_is_refused(tmp_path):
    """`TRC-B5`: an unrecognised CI provider must be refused rather than
    trusted.

    A CI system Compass does not recognise looks like a laptop, so running
    the command there would trust every provider except GitHub.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="allow_project_commands: true\n",
    )

    result = _run_check(project, extra_env={
        "CI": "true",
        "SOME_UNKNOWN_CI": "1",   # a provider Compass has never heard of
    })
    output = result.stdout + result.stderr

    assert not sentinel.exists(), (
        "the command ran on a CI system Compass cannot identify - it failed "
        "open, which is the hole this scenario exists to close:\n" + output)
    assert "could not establish" in output.lower(), (
        "the refusal did not say that Compass could not establish the "
        "contribution is trusted:\n" + output)


def test_b3_explicit_untrusted_signal_is_honoured(tmp_path):
    """`TRC-B3`: detection must not depend on one CI provider.

    No generic CI marker is set here on purpose. This pins the explicit signal
    on its own, so the test still means something on a provider Compass has
    never heard of - and so it cannot quietly pass via the fail-closed rule
    that `TRC-B5` covers.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="allow_project_commands: true\n",
    )

    result = _run_check(project, extra_env={
        "COMPASS_CONTRIBUTION_TRUST": "untrusted",
    })
    output = result.stdout + result.stderr

    assert not sentinel.exists(), (
        "the explicit untrusted signal was ignored, so the refusal only works "
        "on providers Compass has been taught:\n" + output)
    assert "untrusted" in output.lower(), (
        "the refusal did not name the signal that decided it:\n" + output)


def test_b4_local_run_is_not_untrusted(tmp_path):
    """`TRC-B4`: an ordinary local run must not be treated as untrusted.

    The spec calls this "the failure that would make people switch the whole
    thing off". It passes the moment the fail-closed rule is written correctly,
    so it never had a natural red - it is a guard against a specific wrong
    implementation, and it is proved by mutation instead. See
    evidence/mutation-proofs.md.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="allow_project_commands: true\n",
    )

    result = _run_check(project, extra_env={})   # a laptop: no CI variables
    output = result.stdout + result.stderr

    assert sentinel.exists(), (
        "a developer running compass check on their own machine was treated "
        "as untrusted - this is the failure that makes people turn the "
        "feature off:\n" + output)


# ---------------------------------------------------------------------------
# Group A - running a project command is opt-in. This defends against
# accidents and defaults, not against an attacker; group B is the control.
# ---------------------------------------------------------------------------

def test_a1_command_does_not_run_without_opt_in(tmp_path):
    """`TRC-A1`: a project command must not run unless the project has opted
    in, and the check reports that rather than passing quietly."""
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="",              # no opt-in recorded
    )

    result = _run_check(project, extra_env={})
    output = result.stdout + result.stderr

    assert not sentinel.exists(), (
        "a declared command ran with no opt-in recorded:\n" + output)
    assert "allow_project_commands" in output, (
        "the report did not name the setting that enables project commands, "
        "so a reader cannot act on it:\n" + output)


def test_a2_opted_in_project_runs_its_command(tmp_path):
    """`TRC-A2`: a project that has opted in has its command run, and the
    command's exit code decides whether the check passes."""
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="allow_project_commands: true\n",
    )
    result = _run_check(project, extra_env={})
    assert sentinel.exists(), (
        "an opted-in project did not have its command run:\n"
        + result.stdout + result.stderr)

    # The other half: a command that fails must fail the check, or the opt-in
    # bought a check that cannot fail.
    failing = _make_project(
        tmp_path / "second",
        project_guardrails=[{
            "id": "F1", "name": "Fitness function",
            "statement": "A declared project command.",
            "checks": ["command-passes"], "params": {"command": "exit 3"},
            "checked_at": ["verify"],
        }],
        config_extra="allow_project_commands: true\n",
    )
    out = _run_check(failing, extra_env={})
    combined = out.stdout + out.stderr
    assert "exited 3" in combined, (
        "a project command exited 3 and the check did not report the failure, "
        "so the exit code is not deciding anything:\n" + combined)


def test_a3_report_distinguishes_disabled_from_undeclared(tmp_path):
    """`TRC-A3`: the report distinguishes a declaration that was not run from
    there being nothing declared.

    Both run nothing. A reader who cannot tell them apart cannot tell whether
    their architecture checks are working.
    """
    sentinel = tmp_path / "unused"
    disabled = _make_project(
        tmp_path / "disabled",
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="",
    )
    undeclared = _make_project(tmp_path / "undeclared", project_guardrails=[])

    a = _run_check(disabled, extra_env={}).stdout
    b = _run_check(undeclared, extra_env={}).stdout

    def line(out):
        return next((l for l in out.splitlines() if "command-passes" in l), "")

    assert line(a) and line(b), "no command-passes line in one of the reports"
    assert line(a) != line(b), (
        "a project whose declared command was skipped reads identically to a "
        "project that declared nothing:\n  disabled:   " + line(a)
        + "\n  undeclared: " + line(b))
    assert "declares no guardrail" in line(b), (
        "the undeclared case stopped saying nothing was declared: " + line(b))
    assert "declares no guardrail" not in line(a), (
        "the disabled case claims nothing was declared, which is false - a "
        "guardrail was declared and skipped: " + line(a))


# ---------------------------------------------------------------------------
# Group E - an existing declaration does not go quiet.
# ---------------------------------------------------------------------------

def test_e1_disabled_guardrail_is_reported_every_run(tmp_path):
    """`TRC-E1`: a project whose command stops running is told which guardrail
    is affected and the one line that restores it."""
    sentinel = tmp_path / "unused"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="",
    )
    output = _run_check(project, extra_env={}).stdout

    # Scope to the command-passes line, because the section header also
    # names each guardrail.
    line = next((l for l in output.splitlines() if "command-passes" in l), "")
    assert line, "no command-passes line in the report:\n" + output

    assert "F1" in line, (
        "the command-passes line did not name the guardrail that is no longer "
        "being run, so a reader cannot tell which check went quiet:\n" + line)
    assert "allow_project_commands: true" in line, (
        "the command-passes line did not state the one line of configuration "
        "that restores the guardrail:\n" + line)


# ---------------------------------------------------------------------------
# Group C - a safer way to declare an architecture check.
# ---------------------------------------------------------------------------

def test_c1_script_form_runs_without_a_shell(tmp_path):
    """`TRC-C1`: a project can name a script instead of writing a shell string,
    and its arguments are passed as a list rather than interpolated.

    The proof that no shell was involved is the argument itself: a value
    containing shell metacharacters arrives at the script intact. Through a
    shell it would have been split, expanded, or executed.
    """
    project = _make_project(
        tmp_path,
        project_guardrails=[{
            "id": "F1", "name": "Fitness function",
            "statement": "A declared project script.",
            "checks": ["command-passes"],
            "params": {"script": "fitness.py", "args": ["a; touch pwned", "b c"]},
            "checked_at": ["verify"],
        }],
        config_extra="allow_project_commands: true\n",
    )
    # The script records exactly the arguments it received.
    (project / "fitness.py").write_text(
        "import sys, pathlib\n"
        "pathlib.Path('argv.txt').write_text(repr(sys.argv[1:]))\n")

    result = _run_check(project, extra_env={})
    output = result.stdout + result.stderr

    argv_file = project / "argv.txt"
    assert argv_file.exists(), (
        "the declared script did not run:\n" + output)
    assert argv_file.read_text() == repr(["a; touch pwned", "b c"]), (
        "arguments did not arrive intact, so they went through a shell: "
        + argv_file.read_text())
    assert not (project / "pwned").exists(), (
        "a shell metacharacter in an argument was executed - the script form "
        "is invoking a shell")


def test_c2_script_outside_the_project_is_refused(tmp_path):
    """`TRC-C2`: a script path that RESOLVES outside the project root is
    refused.

    Resolves, not reads-as-written: a symlink sitting inside the project and
    pointing out of it satisfies any check made on the literal string, which is
    why the comparison is made on the real path.
    """
    outside = tmp_path / "outside.py"
    outside.write_text("import pathlib; pathlib.Path('/tmp/escaped').write_text('x')\n")

    project = _make_project(
        tmp_path,
        project_guardrails=[{
            "id": "F1", "name": "Fitness function",
            "statement": "A declared project script.",
            "checks": ["command-passes"],
            "params": {"script": "innocent.py"},
            "checked_at": ["verify"],
        }],
        config_extra="allow_project_commands: true\n",
    )
    # Reads as a plain in-project path; resolves out of the project.
    os.symlink(str(outside), str(project / "innocent.py"))

    result = _run_check(project, extra_env={})
    output = result.stdout + result.stderr

    assert "innocent.py" in output, (
        "the refusal did not name the path it rejected:\n" + output)
    assert "outside the project" in output.lower(), (
        "the refusal did not say why the path was rejected:\n" + output)
    assert result.returncode != 0, (
        "a script resolving outside the project was not treated as a "
        "failure:\n" + output)


def test_c1_lint_accepts_the_script_form(tmp_path):
    """`TRC-C1`, the declaration's other half: `compass policy lint` must accept
    a guardrail that declares `script:` instead of `command:`, and must reject
    one that declares both."""
    project = _make_project(
        tmp_path,
        project_guardrails=[{
            "id": "F1", "name": "Fitness function",
            "statement": "A declared project script.",
            "checks": ["command-passes"],
            "params": {"script": "fitness.py"},
            "checked_at": ["verify"],
        }],
    )
    (project / "fitness.py").write_text("pass\n")

    lint = subprocess.run([sys.executable, str(CLI_PATH), "policy", "lint"],
                          cwd=str(project), capture_output=True, text=True, timeout=60)
    out = lint.stdout + lint.stderr
    assert "params.command` is missing" not in out, (
        "lint rejected a valid script-form declaration for having no "
        "`command`:\n" + out)

    both = _make_project(
        tmp_path / "both",
        project_guardrails=[{
            "id": "F1", "name": "Fitness function",
            "statement": "Both forms at once.",
            "checks": ["command-passes"],
            "params": {"script": "fitness.py", "command": "true"},
            "checked_at": ["verify"],
        }],
    )
    lint2 = subprocess.run([sys.executable, str(CLI_PATH), "policy", "lint"],
                           cwd=str(both), capture_output=True, text=True, timeout=60)
    out2 = lint2.stdout + lint2.stderr
    assert "both" in out2.lower(), (
        "lint accepted a guardrail declaring both `script` and `command`, "
        "which leaves the shell reachable through a precedence rule:\n" + out2)


def test_c3_shell_form_still_works_and_is_documented(tmp_path):
    """`TRC-C3`: the shell form keeps working, and the documentation says what
    it costs.

    Removing it would be a second break in one release for no safety gain -
    both forms sit behind the same opt-in and the same refusal.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),   # a shell string
        config_extra="allow_project_commands: true\n",
    )
    result = _run_check(project, extra_env={})
    assert sentinel.exists(), (
        "the shell form stopped working:\n" + result.stdout + result.stderr)

    guide = (FRAMEWORK_ROOT / "docs" / "security.md").read_text()
    # Collapse whitespace before matching. The guide is hard-wrapped, so a
    # phrase that is genuinely present can straddle a line break and fail a
    # plain substring test. This normalises the wrapping, not the phrase:
    # every word still has to be there, in order.
    prose = " ".join(guide.split())

    assert "script:" in guide, "the guide does not show the script form at all"
    # The cost has to be stated, not merely implied by showing two forms.
    assert "still runs a shell" in prose, (
        "the guide does not say that the command form runs a shell while the "
        "script form does not, so a reader has no reason to prefer either")


def test_b2_forged_trusted_signal_cannot_beat_fork_detection(tmp_path):
    """`TRC-B2`: a contribution cannot promote itself to trusted.

    On a `pull_request` event the workflow file comes from the pull
    request's own merge ref, so a fork can
    add anything to its `env:` block - including the signal Compass reads to
    decide trust. There is no way to tell that env var from one the runner set.

    So the signal must not be able to OVERRIDE a provider's own report. It may
    only ever make the answer stricter, never looser: an explicit `untrusted`
    is honoured anywhere, an explicit `trusted` is ignored once GitHub has
    already said this came from a fork.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="allow_project_commands: true\n",
    )

    env = _fork_pr_env(tmp_path)
    env["COMPASS_CONTRIBUTION_TRUST"] = "trusted"      # the forgery

    result = _run_check(project, extra_env=env)
    output = result.stdout + result.stderr

    assert not sentinel.exists(), (
        "a fork pull request promoted itself to trusted by setting an "
        "environment variable in the workflow file it controls:\n" + output)
    assert "fork" in output.lower(), (
        "the refusal did not name the fork, so the provider's own report was "
        "not what decided it:\n" + output)


def test_b2_clearing_the_environment_does_not_look_like_a_laptop(tmp_path):
    """`TRC-B2`: a contribution cannot get its command run by ERASING the
    signals rather than forging them.

    The deeper half of the same problem: a fork controls its own workflow
    file on a `pull_request` event, so it can blank `GITHUB_EVENT_NAME` and
    `CI` and present as a developer's laptop.

    The answer is to stop asking "has anything told me this is untrusted?" and
    start asking "has anything confirmed it is trusted?". An erased environment
    confirms nothing, so it refuses.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="allow_project_commands: true\n",
    )

    # The realistic shape of the attack: the runner still wrote its payload,
    # and the contribution blanked only the variables that name the event.
    # Sets a payload path so the test reaches the blanked-event-name branch,
    # not the no-payload branch.
    env = _fork_pr_env(tmp_path)
    env["GITHUB_EVENT_NAME"] = ""    # blanked by the contribution
    env["CI"] = ""                   # blanked by the contribution

    result = _run_check(project, extra_env=env)
    output = result.stdout + result.stderr

    assert not sentinel.exists(), (
        "a contribution ran its command by blanking the environment variables "
        "that would have identified it:\n" + output)
    assert "untrusted" in output.lower() or "refus" in output.lower(), (
        "the run was not reported as a refusal:\n" + output)

    # And the same with no payload path either, which must also refuse.
    sentinel.unlink(missing_ok=True)
    bare = _run_check(project, extra_env={
        "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "", "CI": ""})
    assert not sentinel.exists(), (
        "a contribution ran its command by blanking every signal, including "
        "the payload path:\n" + bare.stdout + bare.stderr)


def test_b2_event_payload_inside_the_checkout_is_refused(tmp_path):
    """`TRC-B2`: a payload the contribution could have written is not evidence.

    The runner writes its event payload outside the checkout. A path pointing
    back INTO the repository is either a mistake or a forgery, and neither is
    something to decide trust on.
    """
    sentinel = tmp_path / "the-command-ran"
    project = _make_project(
        tmp_path,
        project_guardrails=_sentinel_guardrail(sentinel),
        config_extra="allow_project_commands: true\n",
    )
    # A payload committed to the repository, claiming this is a same-repo PR.
    forged = project / "event.json"
    forged.write_text(json.dumps({
        "pull_request": {"head": {"repo": {"full_name": "ayeo-io/compass"}}}}))

    result = _run_check(project, extra_env={
        "CI": "true",
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_REPOSITORY": "ayeo-io/compass",
        "GITHUB_EVENT_PATH": str(forged),
    })
    output = result.stdout + result.stderr

    assert not sentinel.exists(), (
        "trust was decided from an event payload inside the checkout, which "
        "the contribution being judged could have written:\n" + output)
