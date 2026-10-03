"""Pytest fixtures for the Compass CLI test suite.

These tests are hermetic: each test gets its own temporary project directory
with a fresh `.compass/` layout, and the CLI is invoked via `subprocess.run`
in that directory. Nothing is shared between tests.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# --- locate the CLI and the framework root ----------------------------------
# tests/ lives at the framework root, so the CLI is next to it.
FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
CLI_PATH = FRAMEWORK_ROOT / "cli" / "compass"

# The suite resolves YAML through the same mechanism every other entry point
# does, rather than whatever happens to be on this machine: put cli/ on
# sys.path and import compass_pkg before importing yaml, so the bundled copy
# at cli/vendor/yaml/ wins here too (DD-2). With this in place, the whole
# existing suite running green against the bundled parser IS the parity
# evidence for bundling - there is no separate parity proof to write.
sys.path.insert(0, str(FRAMEWORK_ROOT / "cli"))
import compass_pkg  # noqa: E402  (side effect: puts cli/vendor at sys.path[0])
import yaml  # noqa: E402


@pytest.fixture(scope="session")
def cli_path() -> Path:
    """Absolute path to the compass CLI executable."""
    assert CLI_PATH.is_file(), f"compass CLI not found at {CLI_PATH}"
    return CLI_PATH


@pytest.fixture(scope="session")
def framework_root() -> Path:
    """The compass framework root (containing governance/, schemas/, cli/)."""
    return FRAMEWORK_ROOT


# --- the temp project layout -----------------------------------------------

DEFAULT_GOVERNANCE_FILES = ("routing-policy.yml", "guardrails.yml")


def _copy_governance(src_root: Path, dest: Path) -> None:
    """Copy the shipped governance/ files into a temp project so the test can
    mutate them without touching the real repo."""
    src = src_root / "governance"
    dst = dest / "governance"
    dst.mkdir(parents=True, exist_ok=True)
    for name in DEFAULT_GOVERNANCE_FILES:
        shutil.copyfile(src / name, dst / name)
    # also copy the .md files (lint doesn't need them, but it's hygienic)
    for md in src.glob("*.md"):
        shutil.copyfile(md, dst / md.name)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A fresh Compass project on disk.

    Layout:
        <tmp>/
          governance/routing-policy.yml + guardrails.yml   (copies of shipped)
          .compass/config.yml                              (mode: enforced)
          .compass/work/                                   (empty)
    """
    _copy_governance(FRAMEWORK_ROOT, tmp_path)
    compass_dir = tmp_path / ".compass"
    (compass_dir / "work").mkdir(parents=True, exist_ok=True)
    (compass_dir / "config.yml").write_text(
        "version: 1.0.0\nmode: enforced\n", encoding="utf-8"
    )
    return tmp_path


def write_red_record(task_dir, scenario=None, *, valid=True):
    """Write a red record and its marker, the way `compass tdd-red` does.

    The hook reads the record beside the marker and checks its digest, so a
    fixture that models a recorded failure must write both.

    `valid=False` writes a record whose content no longer matches its digest -
    for tests that model an edited record.
    """
    import hashlib

    evidence = Path(task_dir) / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    name = "red-" + scenario.replace("/", "_") if scenario else "red"

    payload = {
        "command": "pytest -q",
        "scenario": scenario,
        "exit_code": 1,
        "passed": False,
        "timestamp": "2026-08-27T00:00:00+00:00",
        "log_excerpt": "1 failed",
        "record_id": "fixture0000000000",
    }
    body = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    payload["content_digest"] = "sha256:" + hashlib.sha256(body).hexdigest()
    if not valid:
        payload["exit_code"] = 0        # edited after stamping
    (evidence / f"{name}.json").write_text(json.dumps(payload, indent=2),
                                           encoding="utf-8")
    (Path(task_dir) / ".red").write_text("", encoding="utf-8")
    return evidence / f"{name}.json"


@pytest.fixture
def red_record():
    """Fixture form of write_red_record, for tests that take fixtures."""
    return write_red_record


@pytest.fixture
def make_task(project: Path):
    """Return a callable that materialises an issue directory with a manifest.yml.

    Usage:
        task_dir = make_task("my-slug", {"assessment": {...}, ...})
        # task_dir == project/.compass/work/<slug>
        # .compass/current-task is set to "my-slug"
    """

    def _make(slug: str, body: Dict[str, Any], *, set_current: bool = True) -> Path:
        task_dir = project / ".compass" / "work" / slug
        task_dir.mkdir(parents=True, exist_ok=True)
        # add the keys every manifest needs, unless the caller fully overrides
        body = dict(body)
        body.setdefault("task", slug)
        body.setdefault("created", "2026-05-15")
        path = task_dir / "manifest.yml"
        with path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(body, fh, sort_keys=False)
        # Materialise the files the issue says it changed. An issue claiming
        # correctness over a path that is not on disk is a dead trace, which
        # `changed-code-traces-to-scenario` now fails - so a fixture modelling a
        # well-formed issue needs the file to exist. Tests that deliberately
        # model a missing path create their own manifest.yml or delete the file.
        for cf in (body.get("changed_files") or []):
            if isinstance(cf, dict) and cf.get("path"):
                f = project / cf["path"]
                if not f.exists():
                    f.parent.mkdir(parents=True, exist_ok=True)
                    f.write_text("# fixture file\n", encoding="utf-8")
        if set_current:
            (project / ".compass" / "current-task").write_text(slug, encoding="utf-8")
        return task_dir

    return _make


@pytest.fixture
def write_evidence_file(project: Path):
    """Return a callable that writes an evidence JSON next to the issue dir.

    The `path` returned is relative to the task_dir (i.e. `evidence/green.json`).
    """

    def _write(task_dir: Path, name: str, payload: Dict[str, Any]) -> str:
        ev_dir = task_dir / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        full = ev_dir / name
        with full.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        return f"evidence/{name}"

    return _write


# --- the CLI invocation helper ---------------------------------------------


class CliResult:
    """The return type from `run_cli` - exit code + stdout + stderr."""

    def __init__(self, proc: subprocess.CompletedProcess):
        self.returncode: int = proc.returncode
        self.stdout: str = proc.stdout or ""
        self.stderr: str = proc.stderr or ""
        # convenience: stdout and stderr joined
        self.combined: str = self.stdout + "\n" + self.stderr

    def __repr__(self) -> str:  # makes test failures readable
        return (
            f"CliResult(exit={self.returncode!r})\n"
            f"--- stdout ---\n{self.stdout}\n"
            f"--- stderr ---\n{self.stderr}\n"
        )


@pytest.fixture
def run_cli(cli_path: Path, project: Path):
    """Return a callable that invokes the compass CLI inside `project`.

    Usage:
        result = run_cli("approach", "evaluate", "--issue", "slug", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
    """

    def _run(*args: str, cwd: Optional[Path] = None,
             extra_env: Optional[Dict[str, str]] = None,
             input_text: Optional[str] = None,
             timeout: int = 10) -> CliResult:
        # Default timeout 10s - the CLI's real operations finish in under a
        # second; anything beyond 10s is a hang, and a hang must fail fast
        # rather than wait it out across every test in the suite.
        env = dict(os.environ)
        if extra_env:
            env.update(extra_env)
        proc = subprocess.run(
            [sys.executable, str(cli_path), *args],
            cwd=str(cwd or project),
            capture_output=True,
            text=True,
            env=env,
            input=input_text,
            timeout=timeout,
        )
        return CliResult(proc)

    return _run


# --- governance editing helpers --------------------------------------------


@pytest.fixture
def edit_governance(project: Path):
    """Load + save a governance YAML file in the temp project.

    Usage:
        with edit_governance("guardrails.yml") as g:
            g["defaults"].append({...})
    """

    class _Editor:
        def __init__(self, name: str):
            self.path = project / "governance" / name
            self.data: Dict[str, Any] = yaml.safe_load(self.path.read_text())

        def __enter__(self):
            return self.data

        def __exit__(self, *_):
            with self.path.open("w", encoding="utf-8") as fh:
                yaml.safe_dump(self.data, fh, sort_keys=False)

    return _Editor


# --- fixture file loader (used by test_route_selection) ---------------------


# --- the bare-interpreter harness (DD-6) ------------------------------------
# Shared by every zero-install-CLI scenario (tests/test_zero_install_cli.py,
# `TRC-A1` to `TRC-A7`) and by the release-packaging scenario
# (tests/test_release_packaging.py, `TRC-F6`), which proves that
# `compass approach evaluate` runs for the first time from an unpacked
# release tarball on this same kind of interpreter. One place to build it and prove it is
# genuinely bare (DD-6): "python3 -S" is an approximation of absence and this
# class of test must not accept one.


class BareInterpreter:
    """A Python interpreter that has been proven - not assumed - unable to
    import PyYAML from anywhere on its own path."""

    def __init__(self, python_path: Path, mode: str):
        self.python_path = python_path
        self.mode = mode

    def env(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env["PATH"] = f"{self.python_path.parent}{os.pathsep}{env.get('PATH', '')}"
        if extra:
            env.update(extra)
        return env


def _write_bare_fallback_wrapper(wrapper_dir: Path) -> Path:
    """Write a `python3` shim at `wrapper_dir/python3` that always execs the
    real interpreter with `-S -s` (skip site-packages, skip user site).
    Split out from `_build_bare_interpreter` so its isolation can be proven
    directly, independent of whether `venv` happens to be available on the
    machine running the test."""
    wrapper_dir.mkdir(parents=True, exist_ok=True)
    wrapper = wrapper_dir / "python3"
    wrapper.write_text(
        "#!/bin/sh\n"
        f'exec "{sys.executable}" -S -s "$@"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    return wrapper


def _build_bare_interpreter(base_dir: Path) -> BareInterpreter:
    """Build a genuinely empty interpreter and PROVE it is empty before
    handing it back. If the precondition does not hold, this FAILS. It never
    skips: a skipped test passes without checking anything (DD-6)."""
    venv_dir = base_dir / "bare-venv"
    result = subprocess.run(
        [sys.executable, "-m", "venv", "--without-pip", str(venv_dir)],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode == 0:
        python_path = venv_dir / "bin" / "python3"
        if not python_path.exists():
            python_path = venv_dir / "Scripts" / "python.exe"
        mode = "python3 -m venv --without-pip"
    else:
        # Fallback mode: some distributions package venv separately.
        # The scenarios that exercise the shell surfaces (`TRC-A3` to `TRC-A7`)
        # do it by prepending `python_path.parent` to PATH and letting
        # hooks/*.sh and scripts/*.sh find a bare `python3` themselves, so a
        # wrapper script named
        # `python3`, placed first on PATH, is what makes -S -s reach every
        # consumer, not only this function's own check (DD-6).
        # -E is deliberately not part of this: it would also block the
        # PYTHONPATH the CLI's own resolver needs
        # (cli/compass_pkg/__init__.py), so bareness comes from -S -s plus a
        # caller-controlled PYTHONPATH, exactly as env() below already
        # gives for the venv mode too.
        python_path = _write_bare_fallback_wrapper(base_dir / "bare-fallback-bin")
        mode = "python3 -S -s via a PATH wrapper (scrubbed-site fallback)"

    precondition_env = dict(os.environ)
    precondition_env.pop("PYTHONPATH", None)
    precondition = subprocess.run(
        [str(python_path), "-c", "import yaml"], capture_output=True, text=True,
        env=precondition_env, timeout=15,
    )
    assert precondition.returncode != 0, (
        f"the 'bare' interpreter (mode: {mode}) can import yaml - it is not "
        f"bare, so nothing proven against it proves anything:\n"
        f"{precondition.stdout}{precondition.stderr}"
    )
    assert "ModuleNotFoundError" in precondition.stderr, precondition.stderr
    print(f"[TRC-A bare-interpreter harness] mode = {mode}")
    return BareInterpreter(python_path, mode)


@pytest.fixture(scope="session")
def bare_interpreter(tmp_path_factory) -> BareInterpreter:
    base = tmp_path_factory.mktemp("bare-interpreter")
    return _build_bare_interpreter(base)


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def load_route_fixtures() -> List[Dict[str, Any]]:
    """Load the route YAML fixtures in tests/fixtures/routes/."""
    out = []
    rdir = FIXTURES_DIR / "routes"
    for f in sorted(rdir.glob("*.yml")):
        data = yaml.safe_load(f.read_text())
        data["__file__"] = f.name
        out.append(data)
    return out


@pytest.fixture(autouse=True)
def _no_session_issue(monkeypatch):
    """`compass run` sets COMPASS_ISSUE for the sessions it starts, and those
    sessions run this suite. The tests build their own projects, whose
    issues the session's never is, so the variable must not reach them. A
    test about the variable sets it itself."""
    monkeypatch.delenv("COMPASS_ISSUE", raising=False)
