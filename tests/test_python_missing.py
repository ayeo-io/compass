"""A missing or old python3 is said at install and at session start, not
discovered at the first blocked edit: the python-dependency-said-early
issue, GitHub issue #271.

The tests run the scripts with a PATH that holds only the tools they need,
so the machine's own python3, including macOS's /usr/bin stub, is hidden.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SESSION_HOOK = ROOT / "hooks" / "session-start.sh"
CHECK_LIB = ROOT / "scripts" / "lib" / "python-check.sh"
INSTALL = ROOT / "scripts" / "install.sh"
CONTRACT = ROOT / "docs" / "safety-contract.md"
BASH = shutil.which("bash") or "/bin/bash"
TOOLS = ("dirname", "cat", "git", "head", "sed", "tr")


def _toolbin(tmp_path: Path, python_body: str | None) -> Path:
    """A bin directory with the plain tools and, optionally, a stub python3."""
    d = tmp_path / "bin"
    d.mkdir()
    for tool in TOOLS:
        real = shutil.which(tool)
        if real:
            (d / tool).symlink_to(real)
    if python_body is not None:
        stub = d / "python3"
        stub.write_text("#!/bin/sh\n" + python_body + "\n")
        stub.chmod(0o755)
    return d


def _old_python() -> str:
    """A python3 that reports 3.9.6 and fails the 3.10 check."""
    return 'echo 3.9.6; exit 1'


def _broken_python() -> str:
    """A python3 that does not run, like macOS's developer-tools placeholder."""
    return 'echo "xcode-select: note: install the command line developer tools" >&2; exit 1'


def _full_toolbin(tmp_path: Path, python_body: str | None) -> Path:
    """Every tool in /usr/bin and /bin, and jq, except python: the
    installer needs far more than the hook."""
    d = tmp_path / "fullbin"
    d.mkdir()
    dirs = ["/usr/bin", "/bin"]
    jq = shutil.which("jq")
    if jq:
        (d / "jq").symlink_to(jq)
    for base in dirs:
        for entry in sorted(Path(base).iterdir()):
            if entry.name.startswith("python") or (d / entry.name).exists():
                continue
            (d / entry.name).symlink_to(entry)
    if python_body is not None:
        stub = d / "python3"
        stub.write_text("#!/bin/sh\n" + python_body + "\n")
        stub.chmod(0o755)
    return d


def _project(tmp_path: Path, compass: bool = True) -> Path:
    root = (tmp_path / "proj").resolve()
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    if compass:
        (root / ".compass" / "work").mkdir(parents=True)
    return root


def _session(root: Path, bin_dir: Path):
    env = {"PATH": str(bin_dir), "HOME": str(root)}
    payload = json.dumps({"hook_event_name": "SessionStart", "source": "startup",
                          "cwd": str(root)})
    return subprocess.run([BASH, str(SESSION_HOOK)], input=payload, cwd=str(root),
                          env=env, capture_output=True, text=True, timeout=60)


def _says_what_to_do(text: str) -> None:
    assert "Python 3.10" in text, text
    assert "refuses code edits" in text or "refuses the code edits" in text, text
    assert "every edit" not in text, "only code edits are refused"
    assert "install" in text.lower(), text


def test_missing_python_is_said_at_session_start(tmp_path):
    """PY-A."""
    root = _project(tmp_path)
    r = _session(root, _toolbin(tmp_path, None))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    _says_what_to_do(out["systemMessage"])
    _says_what_to_do(out["hookSpecificOutput"]["additionalContext"])
    assert out["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "not found" in out["systemMessage"]


def test_old_python_is_said_with_its_version(tmp_path):
    """PY-B."""
    root = _project(tmp_path)
    r = _session(root, _toolbin(tmp_path, _old_python()))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    _says_what_to_do(out["systemMessage"])
    assert "3.9.6" in out["systemMessage"], out["systemMessage"]


def test_a_python_that_does_not_run_is_said(tmp_path):
    """PY-A: a python3 on the PATH that does not run is not a version."""
    root = _project(tmp_path)
    r = _session(root, _toolbin(tmp_path, _broken_python()))
    out = json.loads(r.stdout)
    _says_what_to_do(out["systemMessage"])
    assert "did not run" in out["systemMessage"], out["systemMessage"]


def test_odd_output_cannot_break_the_json(tmp_path):
    """PY-B: output that is not digits and dots is treated as a python3 that
    does not run, so nothing it prints reaches the JSON."""
    root = _project(tmp_path)
    r = _session(root, _toolbin(tmp_path, 'echo \'3.9"}\\\\x\'; exit 1'))
    out = json.loads(r.stdout)
    assert "did not run" in out["systemMessage"]


def test_a_repository_that_never_opted_in_hears_nothing(tmp_path):
    """PY-C."""
    root = _project(tmp_path, compass=False)
    r = _session(root, _toolbin(tmp_path, None))
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""


def test_a_good_python_keeps_the_contract(tmp_path):
    """PY-C: with Python 3.10+, the hook still injects the contract."""
    root = _project(tmp_path)
    env = dict(os.environ)
    env.pop("CLAUDE_PROJECT_DIR", None)
    r = subprocess.run([BASH, str(SESSION_HOOK)], input="{}", cwd=str(root), env=env,
                       capture_output=True, text=True, timeout=60)
    out = json.loads(r.stdout)
    assert "systemMessage" not in out
    assert "Compass operating contract" in out["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("body, expected", [
    (None, "missing"),
    (_broken_python(), "broken"),
    (_old_python(), "old 3.9.6"),
    ("echo 3.12.1; exit 0", "ok 3.12.1"),
])
def test_the_shared_check_reports_each_case(tmp_path, body, expected):
    """PY-D: one function, used by the hook and the installer."""
    bin_dir = _toolbin(tmp_path, body)
    r = subprocess.run([BASH, "-c", f'. "{CHECK_LIB}"; compass_python_status'],
                       env={"PATH": str(bin_dir)}, capture_output=True, text=True)
    assert r.stdout.strip() == expected, r.stdout + r.stderr


@pytest.mark.parametrize("body, said", [
    (None, "not found"),
    (_old_python(), "3.9.6 (too old)"),
])
def test_install_warns_and_still_installs(tmp_path, body, said):
    """PY-D: a real install into a throwaway project, with no usable python3."""
    target = tmp_path / "target"
    target.mkdir()
    env = {"PATH": str(_full_toolbin(tmp_path, body)), "HOME": str(tmp_path)}
    r = subprocess.run([BASH, str(INSTALL), "--project", str(target)], env=env,
                       capture_output=True, text=True, timeout=120)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert said in out, out
    assert "WARNING: Compass needs Python 3.10 or later" in out, out
    assert out.index("WARNING") < out.index("Installing"), "warn before installing"
    assert (target / ".claude" / "commands" / "compass").exists(), out


def test_install_names_a_good_python(tmp_path):
    """PY-D: with Python 3.10 or later, the installer names it and does not warn."""
    target = tmp_path / "target"
    target.mkdir()
    env = {"PATH": str(_full_toolbin(tmp_path, "echo 3.12.1; exit 0")), "HOME": str(tmp_path)}
    r = subprocess.run([BASH, str(INSTALL), "--project", str(target)], env=env,
                       capture_output=True, text=True, timeout=120)
    assert "3.12.1 (Python 3.10 or later" in r.stdout, r.stdout
    assert "WARNING: Compass needs" not in r.stdout


def _contract_rows() -> dict:
    text = CONTRACT.read_text(encoding="utf-8")
    section = text.split("### Compass needs Python 3.10 or later", 1)
    assert len(section) == 2, "the safety contract has no Python section"
    body = section[1].split("\n### ", 1)[0]
    rows = {}
    for line in body.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].startswith("`"):
            rows[cells[0]] = cells[1:]
    return rows


def test_the_safety_contract_states_the_degraded_mode():
    """PY-E: a row per hook and the CLI, each matching what the hook does
    (checked by running them; see the section's own note)."""
    rows = _contract_rows()
    for name in ("`scripts/install.sh`", "`hooks/session-start.sh`", "`hooks/pre-tool.sh`",
                 "`hooks/post-tool.sh`", "`hooks/stop.sh`", "`compass`"):
        assert name in rows, name
    missing, old = rows["`hooks/pre-tool.sh`"]
    assert "python-missing" in missing and "reader-failed" in missing
    assert "code edit" in missing and "every edit" not in missing
    assert "permit" not in missing.lower() and "permit" not in old.lower()
    stop_missing, stop_old = rows["`hooks/stop.sh`"]
    assert "did not run" in stop_missing and "as usual" in stop_old
    hook = (ROOT / "hooks" / "pre-tool.sh").read_text(encoding="utf-8")
    assert "[python-missing]" in hook


def test_the_single_file_decision_is_recorded():
    """PY-F."""
    adrs = list((ROOT / "architecture" / "decisions").glob("ADR-028-*.md"))
    assert adrs, "no ADR-028"
    text = adrs[0].read_text(encoding="utf-8")
    for fact in ("307 KB", "0.18 s", "0.06 s", "1,018,964 bytes", "zipapp"):
        assert fact in text, fact
