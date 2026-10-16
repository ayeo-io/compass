"""The pre-tool hook guards the project it is for, and nothing else.

Reported from the field (GitHub #57, filed against 2.0.0 and reproduced on
3.1.1). `is_enforced_path()` classified a path by extension and glob but never
checked the path was inside the project. The project-relative path is computed
only when the target happens to be under `PROJECT_DIR`; anywhere else `rel`
stayed absolute, and the extension rules fired regardless.

So any `.py`, `.ts` or `.go` file anywhere on the machine was treated as this
project's production code - a scratch file in a session temp directory, a
throwaway script in a detached worktree. Neither can reach `main` by any path.

The friction is not the point. The refusal told the author to write a failing
test or re-run assessment as a spike. For a file outside the project neither
is a coherent action. The only ways forward were to bypass the hook or
abandon the work. A guardrail issuing unactionable instructions teaches
people to look for the bypass, which is the behaviour it exists to prevent.

Scenario ids: see field-feedback-hook-scope-and-restage/acceptance-criteria.md.
"""
from __future__ import annotations

import json
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = ROOT / "hooks" / "pre-tool.sh"


def _project(tmp_path):
    """A project with an active issue and NO failing test on record."""
    root = tmp_path / "proj"
    work = root / ".compass" / "work" / "demo"
    work.mkdir(parents=True)
    (root / ".compass" / "config.yml").write_text("version: 1.0.0\n")
    (root / ".compass" / "current-task").write_text("demo\n")
    (work / "manifest.yml").write_text(
        'schema_version: "2.0"\ntask: demo\ncreated: "2026-08-14"\n'
        'status: active\ndelivery_approach: feature\n'
        'assessment:\n  risk: contained\n  familiarity: brownfield-mapped\n'
        '  size: small\n  goal: delivery\n  role: engineer\n  labels: []\n')
    (work / "delivery-approach.md").write_text("# Delivery approach\n")
    (work / "acceptance-criteria.md").write_text("# Acceptance criteria\n")
    return root


def _hook(root, target):
    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": str(target),
                                         "content": "x = 1\n"}})
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True,
        cwd=str(root), timeout=60,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "HOME": str(root), "CLAUDE_PROJECT_DIR": str(root)})


def test_ff_1_outside_the_project_is_allowed(tmp_path):
    root = _project(tmp_path)
    outside = tmp_path / "elsewhere" / "scratch_probe.py"
    outside.parent.mkdir(parents=True)

    r = _hook(root, outside)

    assert r.returncode == 0, (
        f"the hook blocked a file outside the project it governs "
        f"({outside}). It cannot reach main by any path, and the advice the "
        f"refusal gives is not actionable for it:\n{r.stdout}{r.stderr}")


def test_ff_2_inside_the_project_is_still_blocked(tmp_path):
    """The control.

    Without it, a containment check that answered "not ours" for everything
    would satisfy the outside-the-project scenario while switching
    enforcement off completely.
    """
    root = _project(tmp_path)
    inside = root / "src" / "app.py"
    inside.parent.mkdir(parents=True)

    r = _hook(root, inside)

    assert r.returncode == 2, (
        f"the hook allowed production code inside the project with no failing "
        f"test on record - red-before-green is no longer enforced anywhere:\n"
        f"{r.stdout}{r.stderr}")
    # Wording changed under `refusal-template`: refusals now open with
    # "Blocked:", not "Compass: BLOCKED -" (RTP-1's three-line shape).
    assert "Blocked:" in (r.stdout + r.stderr)


def test_ff_2b_a_relative_path_is_still_guarded(tmp_path):
    """The second control, and the reason the fix resolves before comparing.

    A Bash redirect (`echo x > src/app.py`) yields a RELATIVE path. Comparing
    that against an absolute project directory answers "outside", so the
    obvious one-line containment check would have switched enforcement off for
    every redirect - the exact write the hook exists to catch.
    """
    root = _project(tmp_path)
    (root / "src").mkdir()

    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": "src/app.py",
                                         "content": "x = 1\n"}})
    r = subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True,
        cwd=str(root), timeout=60,
        env={"PATH": "/usr/bin:/bin:/usr/local/bin",
             "HOME": str(root), "CLAUDE_PROJECT_DIR": str(root)})

    assert r.returncode == 2, (
        f"a relative path inside the project was allowed - the containment "
        f"check compared it without resolving it first:\n{r.stdout}{r.stderr}")


# ---------------------------------------------------------------------------
# A variable set in the same Bash command (issue #172). A Bash write often
# names a scratch file through a variable the command sets, such as
# `S=/tmp/x && cat > $S/plant.ts`. Read literally and joined to the project
# root, `$S/plant.ts` was judged to be production code and refused: a usage
# audit counted 116 such refusals. The hook now expands a variable only when
# the command states its value for certain. Every other case must be refused
# exactly as before, because the hook is the red-before-green boundary.
#
# Commands are templates: {sc} is a scratch directory outside the project and
# {root} is the project.
# ---------------------------------------------------------------------------

def _bash_hook(root, command, extra_env=None):
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": command}})
    env = {"PATH": "/usr/bin:/bin:/usr/local/bin",
           "HOME": str(root), "CLAUDE_PROJECT_DIR": str(root)}
    env.update(extra_env or {})
    return subprocess.run(
        ["bash", str(HOOK)], input=payload, capture_output=True, text=True,
        cwd=str(root), timeout=60, env=env)


def _judge(tmp_path, template, extra_env=None):
    root = _project(tmp_path)
    scratch = tmp_path / "scratch"
    command = template.format(sc=scratch, root=root)
    return command, _bash_hook(root, command, extra_env)


@pytest.mark.parametrize("template", [
    pytest.param("S={sc}; mkdir -p $S && echo x > $S/plant.py", id="semicolon"),
    pytest.param("S={sc} && cat > $S/plant.py <<'EOF'\nprint(1)\nEOF",
                 id="and-heredoc"),
    pytest.param("S={sc}; echo x > ${{S}}/plant.py", id="braces"),
    pytest.param('S="{sc}"; echo x > $S/plant.py', id="double-quoted"),
    pytest.param("S='{sc}'; echo x > $S/plant.py", id="single-quoted"),
    pytest.param("export S={sc}; echo x > $S/plant.py", id="export"),
    pytest.param("S={sc}\necho x > $S/plant.py", id="newline"),
    pytest.param("F={sc}/plant.py; echo x > $F", id="whole-file"),
    pytest.param("S={sc}; T={sc}/t; echo x > $T/plant.py", id="second-variable"),
    pytest.param("S={sc}; echo x | tee $S/plant.py", id="tee"),
    pytest.param("S={sc}; cp /etc/hosts $S/plant.py", id="cp"),
    pytest.param("cd {root}; S={sc}; echo x > $S/plant.py", id="after-cd"),
    pytest.param("cd {root} && S={sc} && mkdir -p $S && echo x > $S/plant.py",
                 id="and-chain-after-cd"),
    pytest.param("export A=1 B=2; set -e; S={sc}; echo x > $S/plant.py",
                 id="after-plain-commands"),
    pytest.param('S={sc}; python3 -c "print((1))" > $S/plant.py',
                 id="call-with-double-parentheses"),
])
def test_ff_3_a_variable_set_in_the_command_is_expanded(tmp_path, template):
    """A scratch file named through the command's own variable is allowed
    (scenario `TRC-A1`)."""
    command, r = _judge(tmp_path, template)
    assert r.returncode == 0, (
        f"the hook refused a write to a scratch file outside the project, "
        f"named through a variable the command itself set:\n{command}\n"
        f"{r.stdout}{r.stderr}")


@pytest.mark.parametrize("template", [
    pytest.param("S={root}/src; echo x > $S/app.py", id="src"),
    pytest.param("S={root}; echo x > $S/src/app.py", id="root"),
    pytest.param("S={sc}; S={root}/src; echo x > $S/app.py", id="last-wins"),
])
def test_ff_4_a_variable_that_points_inside_the_project_is_still_blocked(
        tmp_path, template):
    """Expanding the variable must find the project, not lose it (scenario
    `TRC-A2`)."""
    command, r = _judge(tmp_path, template)
    assert r.returncode == 2, (
        f"a write into the project through a variable was allowed:\n"
        f"{command}\n{r.stdout}{r.stderr}")


@pytest.mark.parametrize("template", [
    pytest.param("S={sc}; echo x > src/app.py", id="redirect"),
    pytest.param("S={sc}; cp $S/a.py src/app.py", id="cp-from-scratch"),
    pytest.param("S={sc}; echo x | tee $S/log.txt src/app.py", id="tee-both"),
    pytest.param("S={sc}; echo x > $S/plant.py; echo y > src/app.py",
                 id="second-write"),
    pytest.param("S={sc}; cp $S/a.py src/app.py; ls $S", id="cp-then-command"),
])
def test_ff_5_a_project_write_beside_a_scratch_variable_is_still_blocked(
        tmp_path, template):
    """A scratch variable does not excuse the command's other writes
    (scenario `TRC-A3`)."""
    command, r = _judge(tmp_path, template)
    assert r.returncode == 2, (
        f"a guarded write was allowed because the command also set a scratch "
        f"variable:\n{command}\n{r.stdout}{r.stderr}")


@pytest.mark.parametrize("template, extra_env", [
    pytest.param("S=$(pwd)/src; echo x > $S/app.py", None,
                 id="command-substitution"),
    pytest.param("S=`pwd`/src; echo x > $S/app.py", None, id="backticks"),
    pytest.param("S=/$(echo {root})/src; echo x > $S/app.py", None,
                 id="substitution-after-slash"),
    pytest.param("echo x > $S/app.py", {"S": "{sc}"},
                 id="environment-scratch"),
    pytest.param("echo x > $S/app.py", {"S": "{root}/src"},
                 id="environment-project"),
    pytest.param("T={sc}; S=$T; echo x > $S/app.py", None,
                 id="another-variable"),
    pytest.param("S=${{HOME}}/src; echo x > $S/app.py", None,
                 id="built-from-home"),
    pytest.param("S=~/src; echo x > $S/app.py", None, id="tilde"),
    pytest.param("S=src; echo x > $S/app.py", None, id="relative"),
    pytest.param("S={sc}; echo x > $S/$T/app.py", None,
                 id="second-variable-in-the-rest"),
])
def test_ff_6_a_variable_the_command_does_not_state_is_not_expanded(
        tmp_path, template, extra_env):
    """A value from a substitution, the environment or another variable is
    unknown to the hook, so the target is judged inside the project, as it
    was before the expansion existed (scenario `TRC-F1`)."""
    root = _project(tmp_path)
    scratch = tmp_path / "scratch"
    command = template.format(sc=scratch, root=root)
    env = {k: v.format(sc=scratch, root=root)
           for k, v in (extra_env or {}).items()}
    r = _bash_hook(root, command, env)
    assert r.returncode == 2, (
        f"the hook expanded a variable whose value the command does not "
        f"state:\n{command}\nenv: {env}\n{r.stdout}{r.stderr}")


@pytest.mark.parametrize("template", [
    pytest.param("S={sc}; S=src; echo x > $S/app.py", id="reassigned"),
    pytest.param("S={sc} && S={root}/src && echo x > $S/app.py",
                 id="reassigned-in-the-leading-statements"),
    pytest.param("S={sc}; cd {root}; S=src; echo x > $S/app.py",
                 id="reassigned-after-another-command"),
    pytest.param("S={sc}; S+=/../proj/src; echo x > $S/app.py", id="append"),
    pytest.param("S={sc}; read S < /dev/null; echo x > $S/app.py", id="read"),
    pytest.param("S={sc}; for S in src; do echo x > $S/app.py; done",
                 id="for-loop"),
    pytest.param("S={sc}; export S=src; echo x > $S/app.py", id="export-again"),
    pytest.param("S={sc}; unset S; echo x > $S/app.py", id="unset"),
    pytest.param("S={sc} true; echo x > $S/app.py", id="one-command-only"),
    pytest.param("false && S={sc}; echo x > $S/app.py", id="after-and"),
    pytest.param("(S={sc}); echo x > $S/app.py", id="subshell"),
    pytest.param("echo x > $S/app.py; S={sc}", id="assigned-after-use"),
    pytest.param('S={sc}; eval "$X"; echo x > $S/app.py', id="eval"),
    pytest.param("S={sc}; source ./env.sh; echo x > $S/app.py", id="source"),
    pytest.param("S={sc}; . ./env.sh; echo x > $S/app.py", id="dot"),
    pytest.param('S={sc}; V=S; printf -v "$V" src; echo x > $S/app.py',
                 id="printf-v"),
    pytest.param('S={sc}; V=S; declare "$V=src"; echo x > $S/app.py',
                 id="declare"),
    pytest.param('S={sc}; trap "$X" DEBUG; echo x > $S/app.py', id="trap"),
    pytest.param("S={sc}; V=S; (( $V = 1 )); echo x > $S/app.py",
                 id="arithmetic"),
    pytest.param("cd {root} && S={sc}; echo x > $S/app.py",
                 id="and-then-semicolon"),
    pytest.param("cd {root} && S={sc} && true; echo x > $S/app.py",
                 id="and-chain-broken-later"),
    pytest.param("cd {root} && S={sc} || echo x > $S/app.py", id="and-then-or"),
    pytest.param("readonly S; S={sc}; echo x > $S/app.py", id="read-only-first"),
    pytest.param("source ./env.sh; S={sc}; echo x > $S/app.py",
                 id="source-first"),
    pytest.param("trap x DEBUG; S={sc}; echo x > $S/app.py", id="trap-first"),
    pytest.param("if true; then S={sc}; fi; echo x > $S/app.py", id="in-if"),
    pytest.param("while false; do S={sc}; done; echo x > $S/app.py",
                 id="in-loop"),
    pytest.param("S={sc}; mkdir -p $S; read S; echo x > $S/app.py",
                 id="read-after-plain-command"),
    # A body longer than a pipe buffer: a check written as `printf | grep -q`
    # stops reading at the first match, printf dies of SIGPIPE, and under
    # pipefail the check reads as "no match" - which would expand.
    pytest.param("S={sc}; read S; echo x > $S/app.py; cat <<'E'\n"
                 + ("filler line\n" * 20000) + "E",
                 id="read-before-a-long-heredoc"),
])
def test_ff_7_a_variable_set_again_or_only_sometimes_is_not_expanded(
        tmp_path, template):
    """The value at the write is certain only when the command assigns the
    variable once, in a leading statement that always runs before the
    write, and nothing after can change it (scenario `TRC-F2`)."""
    command, r = _judge(tmp_path, template)
    assert r.returncode == 2, (
        f"the hook expanded a variable whose value at the write is not "
        f"certain:\n{command}\n{r.stdout}{r.stderr}")


@pytest.mark.parametrize("template", [
    pytest.param("S={sc}/../proj/src; echo x > $S/app.py", id="in-the-value"),
    pytest.param("S={sc}; echo x > $S/../proj/src/app.py", id="in-the-rest"),
])
def test_ff_8_a_parent_directory_step_is_not_expanded(tmp_path, template):
    """A `..` step must never reach the containment check from an expansion,
    because the check compares text. `{sc}/..` is the parent of the
    project directory, so these write into the project's src directory
    (scenario `TRC-F3`)."""
    command, r = _judge(tmp_path, template)
    assert r.returncode == 2, (
        f"a '..' step moved a write into the project past the containment "
        f"check:\n{command}\n{r.stdout}{r.stderr}")


# ---------------------------------------------------------------------------
# A path is judged where it points, not how it is spelled
# (ayeo-io/compass-delivery-record#185). The containment check compared text,
# so `/tmp/../<project>/src/app.py`, a leading `//`, a `.` step or a
# different letter case reached a guarded file and was judged outside.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("template", [
    pytest.param("echo x > {sc}/../proj/src/app.py", id="dot-dot-into-project"),
    pytest.param("echo x > /tmp/..{root}/src/app.py", id="dot-dot-from-tmp"),
    pytest.param("echo x > /{root}/src/app.py", id="double-slash"),
    pytest.param("echo x > {root}/./src/app.py", id="dot-step"),
    pytest.param("echo x > {root}/src//app.py", id="inner-double-slash"),
    pytest.param("echo x > {upper}/src/app.py", id="letter-case"),
    pytest.param("S=/{root}; echo x > $S/src/app.py", id="double-slash-variable"),
    # A `..` after a part the hook cannot know - an unexpanded variable, a
    # substitution, `~` or a brace list - must not cancel that part: where
    # the path points is unknowable, so it is judged inside, as before.
    pytest.param("S=/tmp/x; echo x > $S/../..{root}/src/app.py",
                 id="dot-dot-after-unexpanded-variable"),
    pytest.param("echo x > $X/../src/app.py", id="dot-dot-after-environment-variable"),
    pytest.param("echo x > {root}/$X/../../x/src/app.py",
                 id="dot-dot-after-variable-inside-project"),
    pytest.param("echo x > ~/../..{root}/src/app.py", id="dot-dot-after-tilde"),
])
def test_ff_9_a_path_that_resolves_into_the_project_is_guarded(
        tmp_path, template):
    """A spelling of a path that resolves into the project is judged inside
    it (scenario `TRC-N1`)."""
    root = _project(tmp_path)
    command = template.format(sc=tmp_path / "scratch", root=root,
                              upper=str(root).upper())
    r = _bash_hook(root, command)
    assert r.returncode == 2, (
        f"a write into the project was judged outside it because of how "
        f"its path is spelled:\n{command}\n{r.stdout}{r.stderr}")


@pytest.mark.parametrize("spelling", [
    pytest.param("{sc}/../proj/src/app.py", id="dot-dot"),
    pytest.param("/{root}/src/app.py", id="double-slash"),
])
def test_ff_9b_an_edit_through_such_a_path_is_guarded(tmp_path, spelling):
    """The same holds for an Edit or Write call, which names its file
    (scenario `TRC-N1`)."""
    root = _project(tmp_path)
    r = _hook(root, spelling.format(sc=tmp_path / "scratch", root=root))
    assert r.returncode == 2, f"{r.stdout}{r.stderr}"


@pytest.mark.parametrize("template", [
    pytest.param("echo x > {root}/../elsewhere/app.py", id="steps-out"),
    pytest.param("echo x > {root}/src/../tests/test_app.py",
                 id="steps-into-tests"),
    pytest.param("echo x > {root}/src/../docs/notes.md", id="steps-into-docs"),
])
def test_ff_10_a_path_that_resolves_elsewhere_is_judged_there(
        tmp_path, template):
    """Resolving a path also finds a write that only looks guarded: one
    that steps out of the project, or into its tests or docs (scenario
    `TRC-N2`)."""
    root = _project(tmp_path)
    command = template.format(root=root)
    r = _bash_hook(root, command)
    assert r.returncode == 0, (
        f"a write that resolves outside the project, or to a test or a "
        f"document, was refused:\n{command}\n{r.stdout}{r.stderr}")
