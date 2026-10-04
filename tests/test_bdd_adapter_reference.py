"""The pytest-bdd reference adapter (issue executable-bdd-and-richer-plans).

`compass bdd extract` produces a .feature file. On its own that proves the
extractor works, not that the output is *usable*. The worked project under
examples/bdd-adapters/pytest-bdd/ closes that gap: a real runner consumes the
real output and reports per-scenario results tagged with their TRC ids.

Why this cannot live in the main suite. pytest-bdd is a pytest PLUGIN, and this
repository disables pytest plugin autoload everywhere by design - Makefile, the
CI workflow, and scripts/release.sh all set PYTEST_DISABLE_PLUGIN_AUTOLOAD=1,
with the reasoning in pytest.ini. Under those runs pytest-bdd never loads. So
the adapter gets its own CI job, with autoload on and pytest-bdd installed, and
the tests below skip locally when it is absent.

A skipped test proves nothing, which is why `TRC-B4` checks that the CI job
actually exists rather than trusting that someone will add it.

Spec: executable-bdd-and-richer-plans/acceptance-criteria.md (TRC-B1..B4).
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ADAPTER = ROOT / "examples" / "bdd-adapters" / "pytest-bdd"
WORKFLOW = ROOT / ".github" / "workflows" / "compass.yml"

pytest_bdd_missing = pytest.mark.skipif(
    __import__("importlib.util", fromlist=["util"]).find_spec("pytest_bdd") is None,
    reason="pytest-bdd is not installed here; the dedicated CI job runs this "
           "for real (see TRC-B4)",
)


def _run_adapter(cwd):
    """Run the adapter exactly as its README documents, with autoload ON."""
    env = dict(os.environ)
    env.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
    subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "bdd", "extract",
         "--issue", "reset-password"],
        cwd=str(cwd), capture_output=True, text=True, check=True, timeout=60,
    )
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd=str(cwd), capture_output=True, text=True, env=env, timeout=180,
    )


# ---------------------------------------------------------------------------
# `TRC-B1` - the adapter runs an extracted feature end to end
# ---------------------------------------------------------------------------

@pytest_bdd_missing
def test_trc_b1_adapter_runs_green_end_to_end(tmp_path):
    work = tmp_path / "adapter"
    shutil.copytree(ADAPTER, work)

    result = _run_adapter(work)
    assert result.returncode == 0, (
        f"the reference adapter is not green:\n{result.stdout[-4000:]}\n"
        f"{result.stderr[-2000:]}")

    # The path `bdd extract` writes, read from the CLI rather than written
    # out here: a hard-coded name went stale when the file was renamed (#407).
    from compass_pkg.bdd import default_extract_path
    feature = pathlib.Path(default_extract_path(
        str(work / ".compass" / "work" / "reset-password")))
    assert feature.is_file(), "extraction produced no feature file"

    # every scenario in the spec was collected and passed, by TRC id
    trc_ids = set(re.findall(r"@(TRC-\w+)", feature.read_text()))
    assert trc_ids, "the extracted feature carries no TRC tags"
    assert "passed" in result.stdout
    assert result.stdout.count("PASSED") >= len(trc_ids), (
        f"expected at least {len(trc_ids)} passing scenarios, got:\n"
        f"{result.stdout[-3000:]}")


# ---------------------------------------------------------------------------
# `TRC-B2` - the README shows every step of the wire-up
# ---------------------------------------------------------------------------

def test_trc_b2_readme_shows_full_wireup():
    readme = ADAPTER / "README.md"
    assert readme.is_file(), "the reference adapter has no README"
    text = readme.read_text(encoding="utf-8")

    # 1. the config keys the adapter needs
    for key in ("bdd_runner", "bdd_features_dir", "bdd_steps_dir",
                "bdd_run_command"):
        assert key in text, f"the README never mentions {key}"

    # 2. the extract command that produces the feature file
    assert re.search(r"compass bdd extract", text), (
        "the README does not show the command that produces the .feature file")

    # 3. a step-definition file binding Given, When and Then
    assert re.search(r"@given", text) and re.search(r"@when", text) \
        and re.search(r"@then", text), (
        "the README does not show step definitions binding all three keywords")

    # 4. the command that runs the acceptance suite
    assert re.search(r"(pytest|bdd_run_command)", text)
    assert "pip install pytest-bdd" in text, (
        "the README does not tell the reader to install the runner")


# ---------------------------------------------------------------------------
# `TRC-B3` - a scenario with no step definition fails loudly
# ---------------------------------------------------------------------------

@pytest_bdd_missing
def test_trc_b3_unbound_step_fails_loudly(tmp_path):
    """Delete one binding from a copy and confirm the runner says which step it
    could not find. An adopter's first mistake is a step they have not bound,
    and the failure has to name it."""
    work = tmp_path / "adapter"
    shutil.copytree(ADAPTER, work)

    steps = next((work / "tests").rglob("*steps*.py"))
    text = steps.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find the @given decorator and the quoted step text inside it. The
    # decorator may wrap a bare string or a parsers.parse(...) call, and may
    # span several lines, so scan rather than matching one shape.
    start = next(i for i, l in enumerate(lines) if l.startswith("@given("))
    end = start + 1
    while end < len(lines) and not lines[end].startswith("def "):
        end += 1
    decorator = "\n".join(lines[start:end])
    m = re.search(r'(["\'])(?P<step>[^"\']*\{?[^"\']*)\1', decorator)
    assert m, f"no quoted step text in the @given decorator:\n{decorator}"
    removed = m.group("step")

    # drop the decorator and the function body that follows it
    end += 1
    while end < len(lines) and (lines[end].startswith((" ", "\t"))
                                or not lines[end].strip()):
        end += 1
    steps.write_text("\n".join(lines[:start] + lines[end:]), encoding="utf-8")

    result = _run_adapter(work)
    assert result.returncode != 0, (
        "removing a step definition did not fail the run")
    key = removed.split("{")[0].strip() or removed[:20]
    assert key[:20] in (result.stdout + result.stderr), (
        f"the failure does not name the unbound step {removed!r}:\n"
        f"{result.stdout[-3000:]}")


# ---------------------------------------------------------------------------
# `TRC-B4` - the adapter is proved by a run, never by a skip
# ---------------------------------------------------------------------------

def test_trc_b4_ci_runs_adapter_not_skips_it():
    assert WORKFLOW.is_file(), "no CI workflow to check"
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    raw = WORKFLOW.read_text(encoding="utf-8")

    jobs = wf.get("jobs") or {}
    adapter_jobs = [name for name, job in jobs.items()
                    if "bdd" in name.lower() or "adapter" in name.lower()]
    assert adapter_jobs, (
        f"no CI job runs the BDD adapter; without one TRC-B1 skips forever "
        f"and proves nothing. Jobs present: {sorted(jobs)}")

    job = jobs[adapter_jobs[0]]
    job_text = yaml.safe_dump(job)

    assert "pytest-bdd" in job_text, (
        "the adapter job does not install pytest-bdd")
    assert "bdd-adapters" in job_text or "bdd extract" in job_text, (
        "the adapter job does not actually run the example project")

    # autoload must NOT be disabled in that job - pytest-bdd is a plugin
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" not in job_text, (
        "the adapter job disables plugin autoload, so pytest-bdd cannot load "
        "and the job would prove nothing")

    # ...while the main suite keeps autoload off and its three dependencies
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" in raw, (
        "the main suite no longer disables plugin autoload")
    main_installs = re.findall(r"pip install ([^\n]+)", raw)
    main_only = [i for i in main_installs if "pytest-bdd" not in i]
    assert main_only, "no main-suite dependency install line found"
    for line in main_only:
        assert "pytest-bdd" not in line, (
            f"pytest-bdd leaked into the main suite's dependencies: {line}")
