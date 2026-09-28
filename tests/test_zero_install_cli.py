"""Scenario group A - the bare-interpreter path.

`TRC-A1` through `TRC-A7` all ask the same underlying question of a different
entry point: does it work on a machine that genuinely cannot import PyYAML
from anywhere on its own path? "Genuinely cannot" is the operative word - a
mere `python3 -S` is an approximation of absence, so the harness below builds
a real one with `python3 -m venv --without-pip` and *proves* the absence
before it proves anything else. If the precondition ever holds - if the
"bare" interpreter can import yaml - every test using it fails loudly rather
than passing on an interpreter that was never actually bare (DD-6).

`TRC-A3` through `TRC-A6` exercise the four shell surfaces that embed their own
Python reader (plus `TRC-A7` for the fifth, `scripts/multiagent.sh`) by prepending
the bare interpreter's `bin/` to `PATH` and running the script the way a
person on such a machine actually would - `python3` on `PATH` resolves to the
bare one, which is exactly how these scripts find Python in real life.
"""

# These tests assert the current file names; files written under older
# names still load (ADR-006).
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

# The bare-interpreter harness (BareInterpreter, the `bare_interpreter`
# fixture) lives in conftest.py - it is shared with
# tests/test_release_packaging.py (TRC-F6), which proves a first assessment from an
# unpacked release tarball on the same kind of proven-bare interpreter.

FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"
PRE_TOOL_HOOK = FRAMEWORK_ROOT / "hooks" / "pre-tool.sh"
STOP_HOOK = FRAMEWORK_ROOT / "hooks" / "stop.sh"
INTEGRATE_SH = FRAMEWORK_ROOT / "scripts" / "integrate.sh"
SWARM_SH = FRAMEWORK_ROOT / "scripts" / "multiagent.sh"
VALIDATE_SH = FRAMEWORK_ROOT / "scripts" / "validate.sh"

# Scoped to PyYAML, the dependency this issue removes - not to jsonschema,
# whose own "not installed, here is what it would add" note (TRC-F5) legally
# still says "pip install jsonschema" and must keep saying it unchanged.
_FORBIDDEN_PHRASES = ("pip install pyyaml", "is required but not installed")


# ---------------------------------------------------------------------------
# A minimal on-disk project, the way the bundled CLI expects to find one
# ---------------------------------------------------------------------------


def _make_bare_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    gov_dst = project / "governance"
    gov_dst.mkdir(parents=True)
    gov_src = FRAMEWORK_ROOT / "governance"
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copyfile(gov_src / name, gov_dst / name)
    for md in gov_src.glob("*.md"):
        shutil.copyfile(md, gov_dst / md.name)
    (project / ".compass" / "work").mkdir(parents=True)
    (project / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8")
    return project


def _run_cli(bare: BareInterpreter, project: Path, *args, extra_env=None):
    return subprocess.run(
        [str(bare.python_path), str(CLI_PATH), *args],
        cwd=str(project), capture_output=True, text=True,
        env=bare.env(extra_env), timeout=20,
    )


def _assert_no_install_instruction(result):
    combined = (result.stdout + result.stderr).lower()
    for phrase in _FORBIDDEN_PHRASES:
        assert phrase not in combined, (
            f"'{phrase}' found in output on a bare interpreter:\n{combined}")


# ---------------------------------------------------------------------------
# A first assessment completes with no Python package installed (`TRC-A1`)
# ---------------------------------------------------------------------------


def test_first_triage_completes_without_installing_a_package(bare_interpreter, tmp_path):
    project = _make_bare_project(tmp_path)
    slug = "new-issue"
    task_dir = project / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)

    # The judgement half of assessment - a person, or a session running
    # /compass:assess, records it. Writing manifest.yml directly here is exactly what a
    # session does; only the mechanical half runs through the CLI.
    with (task_dir / "manifest.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump({
            "task": slug,
            "created": "2026-08-10",
            "assessment": {
                "risk": "contained",
                "familiarity": "greenfield",
                "size": "small",
                "goal": "delivery",
            },
        }, fh, sort_keys=False)

    result = _run_cli(bare_interpreter, project,
                       "approach", "evaluate", "--issue", slug, "--write")
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_no_install_instruction(result)

    # The session's own writes - not CLI invocations - complete the record.
    (task_dir / "delivery-approach.md").write_text(
        "# Delivery approach\n\nComposed by `compass approach evaluate --write`.\n",
        encoding="utf-8")
    (project / ".compass" / "current-task").write_text(slug + "\n", encoding="utf-8")

    assert (task_dir / "manifest.yml").is_file()
    assert (task_dir / "delivery-approach.md").is_file()
    pointer = (project / ".compass" / "current-task").read_text(encoding="utf-8")
    assert pointer.splitlines() == [slug]

    # A second, ordinary CLI invocation on the same issue - ask what
    # comes next on this issue's route - also exits 0 on the bare
    # interpreter. (Not `issue lint`: jsonschema is a separate, optional
    # dependency, and its own "not installed" note is required to keep
    # printing unchanged by `TRC-F5` - it is not the instruction `TRC-A1` is
    # about.)
    next_result = _run_cli(bare_interpreter, project, "next", "--issue", slug)
    assert next_result.returncode == 0, next_result.stdout + next_result.stderr
    _assert_no_install_instruction(next_result)


# ---------------------------------------------------------------------------
# No CLI verb exits on a missing dependency (`TRC-A2`)
# ---------------------------------------------------------------------------


def _public_subcommands(bare_interpreter, project) -> list[str]:
    result = _run_cli(bare_interpreter, project, "--help")
    assert result.returncode == 0, result.stdout + result.stderr
    import re
    m = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", result.stdout)
    assert m, result.stdout
    return sorted(m.group(1).split(","))


def test_no_subcommand_exits_with_missing_dependency_status(bare_interpreter, tmp_path):
    project = _make_bare_project(tmp_path)
    subcommands = _public_subcommands(bare_interpreter, project)
    assert subcommands, "compass --help reported no subcommands"

    failures = []
    for cmd in subcommands:
        result = _run_cli(bare_interpreter, project, cmd, "--help")
        combined = result.stdout + result.stderr
        if result.returncode == 3:
            failures.append(f"{cmd}: exited 3\n{combined}")
        for phrase in _FORBIDDEN_PHRASES:
            if phrase in combined.lower():
                failures.append(f"{cmd}: printed '{phrase}'\n{combined}")
    assert not failures, "\n---\n".join(failures)


# ---------------------------------------------------------------------------
# The pre-tool hook enforces `G2` rather than failing open (`TRC-A3`)
# ---------------------------------------------------------------------------


def test_pre_tool_hook_enforces_acceptance_before_code_without_a_system_pyyaml(
        bare_interpreter, tmp_path):
    import json

    project = tmp_path / "hookproj"
    task_dir = project / ".compass" / "work" / "t"
    task_dir.mkdir(parents=True)
    (project / ".compass" / "current-task").write_text("t\n", encoding="utf-8")
    (task_dir / "delivery-approach.md").write_text("# Route\n", encoding="utf-8")
    (task_dir / ".red").write_text("", encoding="utf-8")
    with (task_dir / "manifest.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump({
            "schema_version": "1.1", "task": "t", "created": "2026-08-10",
            "assessment": {"risk": "contained", "familiarity": "greenfield",
                          "size": "small", "intent": "delivery"},
            "delivery_approach": "standard",
            "stages": {"specify": "full"},
            "scenarios": [],
        }, fh, sort_keys=False)

    payload = {"tool_name": "Edit",
               "tool_input": {"file_path": str(project / "src" / "app.py")}}
    env = bare_interpreter.env({"CLAUDE_PROJECT_DIR": str(project)})
    result = subprocess.run(
        ["bash", str(PRE_TOOL_HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, env=env, timeout=30)

    # Today this call is allowed on such a machine: the embedded reader
    # raises on the missing import, the hook exits silently, and the check
    # never runs. This scenario changes that, deliberately - it must now
    # refuse the edit, the same way it would on a machine with PyYAML.
    assert result.returncode == 2, result.stdout + result.stderr
    assert "acceptance-before-code" in result.stderr, result.stderr
    assert "acceptance-criteria.md" in result.stderr, result.stderr


# ---------------------------------------------------------------------------
# Integration records the landing rather than warning it could not (`TRC-A4`)
# ---------------------------------------------------------------------------


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, check=True)


def test_integrate_leaves_status_untouched_ship_commit_lands_without_a_system_pyyaml(
        bare_interpreter, tmp_path):
    """`integrate.sh` merges a wave and leaves the issue's status alone;
    `ship-commit` is the step that lands it and derives the living spec
    (ADR-026, `DPR-7`). Both run on the bare interpreter, so this still
    proves the zero-install claim for whichever step does the writing."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    base_branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(repo),
        capture_output=True, text=True, check=True).stdout.strip()

    slug = "swarmed-issue"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    with (task_dir / "manifest.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump({
            "task": slug, "created": "2026-08-10", "status": "active",
            "assessment": {"risk": "contained", "familiarity": "greenfield",
                          "size": "small"},
            "other_field": "must-survive-unchanged",
        }, fh, sort_keys=False)
    before_other_field = yaml.safe_load((task_dir / "manifest.yml").read_text())["other_field"]
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map\n\n## 3. mapping\n\n"
        f"| stream-1 | U1 | TRC-A1 | compass/{slug}/stream-1 |\n", encoding="utf-8")

    # integrate.sh refuses to run over a dirty working tree, so the issue
    # directory has to be committed on the base branch first - the same as a
    # real repository, where `.compass/work/` is an adopter's own tracked
    # audit trail (only this framework's own copy is gitignored).
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "open swarmed-issue")

    branch = f"compass/{slug}/stream-1"
    _git(repo, "checkout", "-q", "-b", branch)
    (repo / "stream-1-file.txt").write_text("stream work\n", encoding="utf-8")
    _git(repo, "add", "stream-1-file.txt")
    _git(repo, "commit", "-q", "-m", "stream-1 work")
    _git(repo, "checkout", "-q", base_branch)

    env = bare_interpreter.env()
    result = subprocess.run(
        ["bash", str(INTEGRATE_SH), slug, "--no-clean"], cwd=str(repo),
        capture_output=True, text=True, env=env, timeout=60)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "could not write status" not in (result.stdout + result.stderr), (
        result.stdout + result.stderr)

    after_integrate = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert after_integrate["status"] == "active", (
        "integrate.sh must not mark the issue landed - only ship-commit does "
        f"(ADR-026):\n{result.stdout}{result.stderr}")
    assert not (repo / "docs" / "system-spec.md").exists(), (
        "integrate.sh must not derive docs/system-spec.md - only "
        f"ship-commit does (ADR-026):\n{result.stdout}{result.stderr}")

    # The real workflow stages the verification report before shipping -
    # something of the issue's own has to be staged for ship-commit to land.
    (task_dir / "verification-report.md").write_text(
        "# Verification\n", encoding="utf-8")
    _git(repo, "add", "--", f".compass/work/{slug}/verification-report.md")

    ship_result = _run_cli(bare_interpreter, repo, "ship-commit", "-m",
                            "land it", "--issue", slug)
    assert ship_result.returncode == 0, ship_result.stdout + ship_result.stderr
    _assert_no_install_instruction(ship_result)

    written = yaml.safe_load((task_dir / "manifest.yml").read_text())
    assert written["status"] == "landed"
    assert "land_timestamp" in written
    assert written["other_field"] == before_other_field == "must-survive-unchanged"
    assert (repo / "docs" / "system-spec.md").is_file(), (
        "ship-commit must derive docs/system-spec.md once the issue lands "
        f"(ADR-026):\n{ship_result.stdout}{ship_result.stderr}")


# ---------------------------------------------------------------------------
# The session-end signal scan runs rather than returning empty (`TRC-A5`)
# ---------------------------------------------------------------------------


def test_stop_hook_scope_signal_runs_without_a_system_pyyaml(bare_interpreter, tmp_path):
    project = tmp_path / "stopproj"
    gov_dst = project / "governance"
    gov_dst.mkdir(parents=True)
    for f in (FRAMEWORK_ROOT / "governance").iterdir():
        if f.is_file():
            shutil.copyfile(f, gov_dst / f.name)

    slug = "chatty-issue"
    task_dir = project / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "delivery-approach.md").write_text(
        "# Route - chatty-issue\n\n> **Reference route:** standard\n", encoding="utf-8")
    (task_dir / "devlog.md").write_text(
        "2026-08-10: Started build\n"
        "more files than Plan estimated - had to touch core module\n",
        encoding="utf-8")
    with (task_dir / "manifest.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump({
            "task": slug, "created": "2026-08-10",
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                          "size": "small"},
            "route": "standard", "reframes": [],
        }, fh, sort_keys=False)
    (project / ".compass" / "current-task").write_text(slug, encoding="utf-8")

    env = bare_interpreter.env({"CLAUDE_PROJECT_DIR": str(project)})
    result = subprocess.run(
        ["bash", str(STOP_HOOK)], cwd=str(project), input="",
        capture_output=True, text=True, env=env, timeout=30)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "reframe" in result.stderr.lower(), result.stderr
    assert "/compass:assess --reassess" in result.stderr, result.stderr


# ---------------------------------------------------------------------------
# The repository check runs the policy lint rather than skipping it (`TRC-A6`)
# ---------------------------------------------------------------------------


def test_validate_runs_the_policy_lint_without_a_system_pyyaml(bare_interpreter):
    env = bare_interpreter.env()
    result = subprocess.run(
        ["bash", str(VALIDATE_SH)], cwd=str(FRAMEWORK_ROOT),
        capture_output=True, text=True, env=env, timeout=120)

    combined = result.stdout + result.stderr
    assert "skipped, not failed" not in combined, combined
    assert "PyYAML not installed" not in combined, combined
    for phrase in _FORBIDDEN_PHRASES:
        assert phrase not in combined.lower(), combined

    # `validate.sh` prints the phrase "compass policy lint" on all three of
    # its paths - PASS, "reported a problem", and "skipped". Asserting the
    # phrase therefore passed even when the lint had been skipped entirely,
    # which is the one outcome this test exists to rule out. Anchor on the
    # success branch, and check the exit code the earlier version never read.
    assert "compass policy lint  <- PASS" in combined, (
        f"the policy lint did not run and pass on a bare interpreter - the "
        f"phrase alone is printed on the skip path too:\n{combined}"
    )
    assert "skip compass policy lint" not in combined, (
        f"validate.sh skipped the policy lint rather than running it:\n"
        f"{combined}"
    )
    assert result.returncode == 0, (
        f"validate.sh exited {result.returncode} on a bare interpreter:\n"
        f"{combined}"
    )


# ---------------------------------------------------------------------------
# Preparing a multiagent breakdown reads the cap rather than refusing (`TRC-A7`)
# ---------------------------------------------------------------------------


def test_swarm_reads_the_cap_without_a_system_pyyaml(bare_interpreter, tmp_path):
    repo = tmp_path / "swarmrepo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    (repo / "f").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    slug = "swarm-issue"
    task_dir = repo / ".compass" / "work" / slug
    task_dir.mkdir(parents=True)
    (task_dir / "delivery-approach.md").write_text(
        "# Delivery approach - swarm-issue\n\n> **Reference shape:** initiative\n",
        encoding="utf-8")
    with (task_dir / "manifest.yml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump({
            "task": slug,
            "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                          "size": "large"},
            "fired_guardrails": [],
        }, fh, sort_keys=False)
    (task_dir / "distribution-map.md").write_text(
        "# Distribution Map\n\n## 3. mapping\n\n"
        f"| stream-1 | U1 | TRC-A7 | compass/{slug}/stream-1 |\n"
        f"| stream-2 | U2 | TRC-A7 | compass/{slug}/stream-2 |\n",
        encoding="utf-8")
    (repo / ".compass" / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\nswarm:\n  worktree_root: ../wt\n"
        "  max_worktrees: 6\n", encoding="utf-8")

    env = bare_interpreter.env()
    result = subprocess.run(
        ["bash", str(SWARM_SH), slug, "--dry-run"], cwd=str(repo),
        capture_output=True, text=True, env=env, timeout=30)

    combined = result.stdout + result.stderr
    assert "cannot read the cap from manifest.yml" not in combined, combined
    assert "fix manifest.yml" not in combined.lower(), combined
    assert result.returncode == 0, combined


# ---------------------------------------------------------------------------
# The bare-interpreter harness's fallback mode (W-1) - proving the isolation
# reaches every consumer, not only the harness's own precondition check
# ---------------------------------------------------------------------------


def test_fallback_wrapper_isolation_reaches_a_plain_python3_found_on_path(tmp_path):
    """`TRC-A3` through `TRC-A7` do not call `bare_interpreter.python_path`
    directly - they prepend its directory to PATH and let a shell script
    find a bare `python3` itself, the way hooks/*.sh and scripts/*.sh do in
    real use. The fallback mode's isolation has to survive exactly that
    indirection, or `DD-6`'s 'neither mode may skip' is violated silently: the
    precondition would pass (checked directly) while every real test using
    PATH lookup ran the ordinary interpreter underneath."""
    from conftest import _write_bare_fallback_wrapper

    wrapper_dir = tmp_path / "bare-fallback-bin"
    _write_bare_fallback_wrapper(wrapper_dir)

    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PATH"] = f"{wrapper_dir}{os.pathsep}{env.get('PATH', '')}"

    # Exactly what a shell script does: call the bare command name, resolved
    # by PATH lookup - not the wrapper's absolute path.
    which = subprocess.run(["which", "python3"], capture_output=True, text=True, env=env)
    assert which.stdout.strip() == str(wrapper_dir / "python3"), which.stdout

    result = subprocess.run(["python3", "-c", "import yaml"],
                            capture_output=True, text=True, env=env, timeout=10)
    assert result.returncode != 0, (
        f"a plain `python3` resolved via PATH could import yaml through the "
        f"fallback wrapper - the isolation did not reach a PATH lookup:\n"
        f"{result.stdout}{result.stderr}")
    assert "ModuleNotFoundError" in result.stderr, result.stderr


def test_fallback_wrapper_still_honours_pythonpath_for_the_clis_own_resolver(tmp_path):
    """The isolation must not be so total it breaks the thing under test:
    `cli/compass_pkg/__init__.py` resolves the bundled copy through
    PYTHONPATH, and the CLI legitimately needs that path to keep working on
    the fallback interpreter - only site-packages and user-site should be
    scrubbed, not every path a caller gives."""
    from conftest import _write_bare_fallback_wrapper

    wrapper_dir = tmp_path / "bare-fallback-bin"
    _write_bare_fallback_wrapper(wrapper_dir)

    env = dict(os.environ)
    env["PATH"] = f"{wrapper_dir}{os.pathsep}{env.get('PATH', '')}"
    env["PYTHONPATH"] = str(FRAMEWORK_ROOT / "cli")

    result = subprocess.run(
        ["python3", "-c", "import compass_pkg, yaml; print(yaml.__file__)"],
        capture_output=True, text=True, env=env, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "cli/vendor/yaml" in result.stdout, result.stdout
