"""The suite and the release run on parallel workers, and `make ci` checks
only recent issues by default: the faster-suite-and-release issue,
scenarios FS-A, FS-B and FS-D to FS-G in `docs/system-spec.md`.

`make -n` prints the commands a target would run without running them, so
these tests read the flags each target passes. A stub `xdist` package on
PYTHONPATH stands in for an installed `pytest-xdist`.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PARALLEL = "-p xdist.plugin -n auto"


def _make_n(target: str, tmp_path: Path, *, xdist: bool, **env) -> str:
    """The commands `make <target>` would run, with or without `xdist`."""
    stub = tmp_path / "stub"
    stub.mkdir(exist_ok=True)
    # The stub sits first on PYTHONPATH, so it wins over an installed copy:
    # an empty package stands in for pytest-xdist, and one that raises hides
    # a real install, as CI has.
    (stub / "xdist").mkdir(exist_ok=True)
    (stub / "xdist" / "__init__.py").write_text(
        "" if xdist else "raise ImportError('hidden by the test')\n")
    run_env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "COMPASS_FULL_ARCHIVE")}
    run_env["PYTHONPATH"] = str(stub)
    run_env.update(env)
    r = subprocess.run(["make", "-n", target], cwd=ROOT, capture_output=True,
                       text=True, env=run_env)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_make_test_runs_on_parallel_workers_when_xdist_is_installed(tmp_path):
    """With pytest-xdist installed, make test runs the suite on parallel
    workers (FS-A)."""
    assert PARALLEL in _make_n("test", tmp_path, xdist=True)


def test_make_test_runs_in_series_without_xdist(tmp_path):
    """Without pytest-xdist, make test runs the suite in series, as before
    (FS-A)."""
    out = _make_n("test", tmp_path, xdist=False)
    assert "pytest tests/" in out and "xdist" not in out, out


def _latest_tag() -> str:
    r = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], cwd=ROOT,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def test_make_ci_checks_issues_since_the_latest_tag(tmp_path):
    """make ci passes the latest release tag to compass ci (FS-D)."""
    tag = _latest_tag()
    if not tag:
        pytest.skip("this checkout has no tag, so make ci checks every issue")
    out = _make_n("ci", tmp_path, xdist=False)
    assert f"compass ci --since {tag}" in out, out


def test_the_full_archive_opt_in_checks_every_issue(tmp_path):
    """COMPASS_FULL_ARCHIVE=1 makes make ci check every issue (FS-D)."""
    out = _make_n("ci", tmp_path, xdist=False, COMPASS_FULL_ARCHIVE="1")
    assert "compass ci" in out and "--since" not in out, out


def test_release_script_runs_the_suite_on_parallel_workers():
    """scripts/release.sh tests for xdist and passes the parallel flags when
    it imports (FS-E)."""
    text = (ROOT / "scripts" / "release.sh").read_text(encoding="utf-8")
    assert "import xdist" in text, "release.sh does not test for pytest-xdist"
    step = text[text.index('echo "[3] tests"'):text.index('echo "[4]')]
    assert "$XDIST" in step or "${XDIST}" in step, step


def test_ci_installs_xdist_and_runs_in_parallel():
    """The CI self-check job installs pytest-xdist and runs the suite on
    parallel workers (FS-F)."""
    text = (ROOT / ".github" / "workflows" / "compass.yml").read_text(encoding="utf-8")
    job = text[text.index("self-check"):text.index("bdd-adapter")]
    assert re.search(r"pip install[^\n]*pytest-xdist", job), "self-check does not install pytest-xdist"
    assert f"pytest tests/ -q {PARALLEL}" in job, "self-check does not run in parallel"


def test_releasing_md_names_xdist_and_the_full_archive_check():
    """docs/releasing.md says how to install pytest-xdist and names the
    full-archive check (FS-G)."""
    text = (ROOT / "docs" / "releasing.md").read_text(encoding="utf-8")
    assert "pip install pytest-xdist" in text
    assert "COMPASS_FULL_ARCHIVE=1" in text


ARCHIVE = ROOT / ".compass" / "work"


def _swept_slugs(module: str) -> list:
    """The issues the module sweeps, from the module's own list."""
    sys.path.insert(0, str(ROOT))
    try:
        if module.endswith("test_phase2_invariants.py"):
            from tests.test_phase2_invariants import _SLUGS
            return list(_SLUGS)
        from tests.test_record_keeping_integrity import _pre_existing_task_slugs
        return list(_pre_existing_task_slugs())
    finally:
        sys.path.remove(str(ROOT))


@pytest.mark.parametrize("module", ["tests/test_phase2_invariants.py",
                                    "tests/test_record_keeping_integrity.py"])
def test_each_archive_sweep_is_one_test_per_issue(module):
    """The two archive sweeps collect one test per issue, named after it
    (FS-B)."""
    if not ARCHIVE.is_dir():
        pytest.skip("no local issue archive to sweep")
    # `-o addopts=` drops pytest.ini's own `-q`; two of them print only counts.
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                        "-o", "addopts=", "-p", "no:cacheprovider", module], cwd=ROOT,
                       capture_output=True, text=True,
                       env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
    ids = set(re.findall(r"\[([^\]]+)\]", r.stdout))
    expected = set(_swept_slugs(module))
    assert expected, f"{module}: no issue to sweep, so this check proves nothing"
    missing = sorted(expected - ids)
    assert not missing, f"{module}: these issues are not their own test: {missing[:10]}"
