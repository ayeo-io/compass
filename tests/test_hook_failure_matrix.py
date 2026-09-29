"""One failure rule for the pre-tool hook.

Inside an opted-in project, any enforcement check that cannot run exits 2 with
a message naming what could not run. Exit 1 is not a refusal: the runtime
treats it as a non-blocking error and lets the edit through. And a refusal
with the wrong reason - "assessment did not complete" when python3 is missing
- sends the user to the wrong fix.

The hook has four Python readers. A fake `python3` placed first on the PATH
fails only for the reader whose script holds a chosen line, and runs the real
interpreter for the others, so each reader can be failed on its own.

Scenario ids: HFM-1 to HFM-6, in the acceptance criteria of the issue
`hook-failure-matrix`.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SLUG = "matrix"

#: Each reader, a line only its script holds, and the name its refusal uses.
READERS = {
    "code_globs": ("fnmatch.fnmatch(path, g)", "enforcement.code_globs reader"),
    "approach": ("resolve_artifact(sys.argv[1]", "delivery-approach reader"),
    "acceptance": ('weight = stages.get("define"', "acceptance-criteria reader"),
    "red": ("verdict_line(sys.argv[1]", "red-record reader"),
}

MANIFEST = """schema_version: '2.0'
issue: matrix
created: '2026-09-24'
status: active
stages: {assess: full, define: full, implement: full}
scenarios:
- id: M-1
  intent: INT-1
  tests: [t]
"""

FAKE = """#!/usr/bin/env bash
# Fails only for the reader whose script holds $FAKE_FAIL_ON.
if [ "${1:-}" = "-" ]; then
  body="$(cat)"
  if [ -n "${FAKE_FAIL_ON:-}" ] && printf '%s' "$body" | grep -qF -- "$FAKE_FAIL_ON"; then
    echo "fake python3: failing on purpose" >&2
    exit "${FAKE_EXIT:-1}"
  fi
  printf '%s\\n' "$body" | REALPY "$@"
  exit $?
fi
exec REALPY "$@"
"""


def _red_record():
    payload = {"command": "pytest -q", "scenario": None, "exit_code": 1,
               "passed": False, "timestamp": "2026-09-24T00:00:00+00:00",
               "record_id": "fixture0000000000"}
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    payload["content_digest"] = "sha256:" + hashlib.sha256(body).hexdigest()
    return payload


@pytest.fixture
def install():
    """A copy of the hooks, their shell helper and the CLI package, with an
    issue whose every check passes. The path holds no "test", so the hook's
    test-file exemption does not fire."""
    root = Path(tempfile.mkdtemp(prefix="compass-mtx-"))
    for part in ("hooks", "scripts", "cli"):
        shutil.copytree(ROOT / part, root / part,
                        ignore=shutil.ignore_patterns("__pycache__"))
    compass = root / ".compass"
    task = compass / "work" / SLUG
    (task / "evidence").mkdir(parents=True)
    (compass / "current-task").write_text(SLUG)
    (compass / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n"
        "enforcement:\n  code_globs: ['packaging/**']\n")
    (task / "manifest.yml").write_text(MANIFEST)
    (task / "delivery-approach.md").write_text("# Approach\n")
    (task / "evidence" / "red.json").write_text(json.dumps(_red_record()))
    (task / ".red").write_text("")
    fake_bin = root / "fakebin"
    fake_bin.mkdir()
    fake = fake_bin / "python3"
    fake.write_text(FAKE.replace("REALPY", sys.executable))
    fake.chmod(0o755)
    yield root
    shutil.rmtree(root, ignore_errors=True)


def _no_python_path(root):
    """A PATH holding every tool in /usr/bin and /bin except python."""
    bare = root / "barebin"
    bare.mkdir(exist_ok=True)
    for d in ("/usr/bin", "/bin"):
        for name in os.listdir(d):
            if name.startswith("python") or (bare / name).exists():
                continue
            (bare / name).symlink_to(os.path.join(d, name))
    return str(bare)


def _hook(root, target, *, fail_on=None, status=1, path=None):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(root),
           "PATH": path or f"{root / 'fakebin'}:{os.environ['PATH']}"}
    if fail_on:
        env["FAKE_FAIL_ON"] = READERS[fail_on][0]
        env["FAKE_EXIT"] = str(status)
    event = json.dumps({"tool_name": "Edit",
                        "tool_input": {"file_path": str(root / target)}})
    return subprocess.run(["bash", str(root / "hooks" / "pre-tool.sh")],
                          input=event, capture_output=True, text=True,
                          timeout=120, env=env)


def _target(reader):
    return "packaging/app.cfg" if reader == "code_globs" else "src/app.py"


@pytest.mark.parametrize("target", ["src/app.py", "packaging/app.cfg"])
def test_hfm_1_the_control_every_check_passes(install, target):
    """Without this, a refusal below could come from the fixture, not the
    failed reader."""
    result = _hook(install, target)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("status", [1, 3])
@pytest.mark.parametrize("reader", list(READERS))
def test_hfm_1_every_reader_that_cannot_run_refuses_and_names_itself(
        install, reader, status):
    result = _hook(install, _target(reader), fail_on=reader, status=status)
    assert result.returncode == 2, (result.returncode, result.stderr)
    text = " ".join(result.stderr.split())
    assert READERS[reader][1] in text, text
    assert "could not run" in text, text


@pytest.mark.parametrize("target", ["src/app.py", "packaging/app.cfg"])
def test_hfm_2_with_no_python3_the_refusal_says_so(install, target):
    """Wording changed under `refusal-template`: the refusal is now the
    registry's `python-missing` rendering (RTP-3), not a reader-named
    message - so it no longer names the reader, and the pin below moved
    with it."""
    result = _hook(install, target, path=_no_python_path(install))
    assert result.returncode == 2, (result.returncode, result.stderr)
    text = " ".join(result.stderr.split())
    assert "python3 was not found on the PATH" in text, text
    assert "[python-missing]" in text, text
    assert "did not complete" not in text


def test_hfm_3_a_config_that_does_not_parse_does_not_unguard(install):
    """Wording changed under `refusal-template`: a bad `.compass/config.yml`
    now renders the registry's `config-invalid` code, not the reader's own
    name."""
    (install / ".compass" / "config.yml").write_text(
        "enforcement:\n  code_globs: [unclosed\n")
    result = _hook(install, "packaging/app.cfg")
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert "[config-invalid]" in " ".join(result.stderr.split())


def test_hfm_4_a_missing_approach_record_is_still_reported_as_missing(install):
    (install / ".compass" / "work" / SLUG / "delivery-approach.md").unlink()
    result = _hook(install, "src/app.py")
    assert result.returncode == 2
    text = " ".join(result.stderr.split())
    assert "has no delivery-approach.md" in text, text
    assert "could not run" not in text


def test_hfm_5_the_safety_contract_scopes_the_worktree_redirect_gap():
    text = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split()).lower()
    assert "inside a worktree" in text
    assert "the session's issue" in text


RETIRED = [
    (re.compile(r"\btriage\b", re.I), "triage"),
    (re.compile(r"MultiEdit"), "MultiEdit"),
    (re.compile(r"\bspecify: full\b"), "specify: full"),
]


def test_hfm_6_the_hooks_use_no_retired_word_or_tool_name():
    hits = []
    for script in sorted((ROOT / "hooks").glob("*.sh")):
        for n, line in enumerate(script.read_text(encoding="utf-8").splitlines(), 1):
            # The acceptance check still reads the retired `specify` key from
            # archived manifests, and its comment says so; that is a key, not
            # a stage name in prose.
            if "retired `specify" in line or 'stages.get("specify")' in line:
                continue
            for pattern, word in RETIRED:
                if pattern.search(line):
                    hits.append(f"{script.name}:{n}: {word}")
    assert not hits, "\n".join(hits)


# ---------------------------------------------------------------------------
# Review findings: steps outside the four readers that still exited 1, and
# refusals that pointed at the wrong fix.
# ---------------------------------------------------------------------------

FAKE_MKTEMP = """#!/usr/bin/env bash
# Fails on the Nth call, counted in $FAKE_MKTEMP_COUNTER; otherwise real mktemp.
n=$(( $(cat "$FAKE_MKTEMP_COUNTER" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$FAKE_MKTEMP_COUNTER"
if [ "$n" -eq "${FAKE_MKTEMP_FAIL:-0}" ]; then
  echo "fake mktemp: failing on purpose" >&2
  exit 1
fi
exec /usr/bin/mktemp "$@"
"""


@pytest.mark.parametrize("call, reader", [(1, "delivery-approach reader"),
                                          (2, "acceptance-criteria reader")])
def test_hfm_1_a_temporary_file_that_cannot_be_made_refuses(install, call, reader):
    fake = install / "fakebin" / "mktemp"
    fake.write_text(FAKE_MKTEMP)
    fake.chmod(0o755)
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(install),
           "PATH": f"{install / 'fakebin'}:{os.environ['PATH']}",
           "FAKE_MKTEMP_COUNTER": str(install / "mktemp-count"),
           "FAKE_MKTEMP_FAIL": str(call)}
    event = json.dumps({"tool_name": "Edit",
                        "tool_input": {"file_path": str(install / "src/app.py")}})
    result = subprocess.run(["bash", str(install / "hooks" / "pre-tool.sh")],
                            input=event, capture_output=True, text=True,
                            timeout=120, env=env)
    assert result.returncode == 2, (result.returncode, result.stderr)
    text = " ".join(result.stderr.split())
    assert reader in text and "temporary file" in text, text


def test_hfm_1_an_unreadable_config_does_not_turn_a_refusal_into_exit_1(install):
    shutil.rmtree(install / ".compass" / "work")
    config = install / ".compass" / "config.yml"
    config.chmod(0)
    try:
        result = _hook(install, "src/app.py")
    finally:
        config.chmod(0o644)
    assert result.returncode == 2, (result.returncode, result.stderr)


def test_hfm_1_a_missing_python_helper_refuses_in_a_project(install):
    (install / "scripts" / "lib" / "compass-python.sh").unlink()
    result = _hook(install, "src/app.py")
    assert result.returncode == 2, (result.returncode, result.stderr)
    assert "compass-python.sh" in result.stderr


def test_hfm_1_a_missing_python_helper_stays_silent_in_a_guest_repo(install):
    (install / "scripts" / "lib" / "compass-python.sh").unlink()
    shutil.rmtree(install / ".compass")
    result = _hook(install, "src/app.py")
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert result.stderr == ""


def test_hfm_3_a_broken_config_names_the_config_as_the_fix(install):
    (install / ".compass" / "config.yml").write_text(
        "enforcement:\n  code_globs: [unclosed\n")
    result = _hook(install, "packaging/app.cfg")
    text = " ".join(result.stderr.split())
    assert "fix .compass/config.yml and retry" in text, text
    assert "Fix the install" not in text


def test_hfm_3_a_bash_refusal_names_the_file_it_found(install):
    (install / ".compass" / "config.yml").write_text(
        "enforcement:\n  code_globs: [unclosed\n")
    event = json.dumps({"tool_name": "Bash", "tool_input": {
        "command": "echo x > packaging/app.cfg"}})
    result = subprocess.run(["bash", str(install / "hooks" / "pre-tool.sh")],
                            input=event, capture_output=True, text=True,
                            timeout=120, env={**os.environ,
                                              "CLAUDE_PROJECT_DIR": str(install)})
    assert result.returncode == 2
    assert "Edit target: ?" not in result.stderr
    assert "packaging/app.cfg" in result.stderr


def test_hfm_1_the_red_reader_refusal_gives_its_cause(install):
    result = _hook(install, "src/app.py", fail_on="red", status=1)
    assert "fake python3: failing on purpose" in result.stderr


def test_hfm_5_the_contract_names_the_absolute_path_gap():
    text = " ".join((ROOT / "docs" / "safety-contract.md")
                    .read_text(encoding="utf-8").split())
    assert "absolute path" in text
    assert "outside the project" in text


# ---------------------------------------------------------------------------
# `code-globs-as-a-string`: a value of the wrong shape is a config the reader
# cannot read. As a string, the reader walked it one character at a time, so
# `*` guarded every path and nothing said the value was wrong.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["'packaging/**'", "[1, 2]", "{a: b}"])
def test_cgs_1_code_globs_of_the_wrong_shape_refuses(install, value):
    (install / ".compass" / "config.yml").write_text(
        f"version: 1.0.0\nmode: enforced\nenforcement:\n  code_globs: {value}\n")
    result = _hook(install, "packaging/app.cfg")
    assert result.returncode == 2, (result.returncode, result.stderr)
    text = " ".join(result.stderr.split())
    assert "fix .compass/config.yml and retry" in text, text
    assert "a list of strings" in text, text
