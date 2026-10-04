"""All four BDD reference adapters (issue bdd-adapters-and-skill-length).

Compass ships reference adapters for pytest-bdd, cucumber-js, behave and
godog, and these tests run each one. The rule they enforce: an example no
job runs is an example nobody can trust. So an adapter ships only with CI
that runs it, and a test that skips because a runner is absent says so
rather than reporting success.

Spec: bdd-adapters-and-skill-length/acceptance-criteria.md (TRC-A1..A4,
      `TRC-B1`, `TRC-B2`, `TRC-C1`).
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
ADAPTERS = ROOT / "examples" / "bdd-adapters"
WORKFLOW = ROOT / ".github" / "workflows" / "compass.yml"

EXPECTED = {"pytest-bdd", "cucumber-js", "behave", "godog"}

# (executable that must exist, setup command an adopter runs, run command)
#
# The setup step is part of the documented flow, not test scaffolding: an
# adopter clones the example and installs its dependencies. Those dependencies
# are deliberately not committed, so the test does what the README says.
RUNNERS = {
    "pytest-bdd":   ("python3", None,
                     ["python3", "-m", "pytest", "tests/", "-q"]),
    "behave":       ("behave",  None, ["behave", "features/"]),
    "cucumber-js":  ("npm",     ["npm", "install", "--silent", "--no-audit",
                                 "--no-fund"],
                     ["npx", "cucumber-js"]),
    "godog":        ("go",      ["go", "mod", "download"],
                     ["go", "test", "./..."]),
}


def _runner_usable(name):
    """Is this adapter's runner actually present? A skip must be honest about
    which one is missing, never a quiet pass."""
    exe = RUNNERS[name][0]
    if shutil.which(exe) is None:
        return False, f"`{exe}` is not installed"
    if name == "pytest-bdd":
        if importlib.util.find_spec("pytest_bdd") is None:
            return False, "pytest-bdd is not importable"
    return True, ""


def _bdd_module():
    """The package module that owns the tag selector.

    Not the entry point: it re-exports with `import *`, which by design skips
    leading-underscore names, and `_bdd_tag_selector` is internal.
    """
    sys.path.insert(0, str(ROOT / "cli"))
    try:
        from compass_pkg import bdd  # noqa: PLC0415
        return bdd
    finally:
        sys.path.remove(str(ROOT / "cli"))


# --- group A ---------------------------------------------------------------

def test_trc_a1_each_runner_should_have_a_worked_project():
    present = {p.name for p in ADAPTERS.iterdir() if p.is_dir()}
    assert present == EXPECTED, (
        f"the plan names four runners.\n  missing: {sorted(EXPECTED - present)}"
        f"\n  extra  : {sorted(present - EXPECTED)}")
    for name in sorted(EXPECTED):
        d = ADAPTERS / name
        assert (d / "README.md").is_file(), f"{name}: no README"
        cfg = yaml.safe_load((d / ".compass" / "config.yml").read_text())
        assert (cfg.get("project") or {}).get("bdd_runner"), (
            f"{name}: config declares no bdd_runner")
        # Asked for through the resolver: an issue's documents live under
        # `docs/compass/<created>-<slug>/` and the manifest's registry says
        # where. Testing for a file beside the manifest asserts the old layout.
        import sys as _sys
        _sys.path.insert(0, str(ROOT / "cli"))
        from compass_pkg.core import FOUND, resolve_artifact
        task_dir = d / ".compass" / "work" / "reset-password"
        state, _path, reason = resolve_artifact(str(task_dir),
                                                "acceptance-criteria")
        assert state == FOUND, f"{name}: no spec ({state}: {reason})"


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_trc_a2_each_adapter_should_run_the_extracted_feature_and_pass(name, tmp_path):
    exe, setup, run_cmd = RUNNERS[name]
    usable, why = _runner_usable(name)
    if not usable:
        pytest.skip(f"{name}: {why} on this machine - the CI job for this "
                    f"adapter is what proves it (TRC-B1)")
    work = tmp_path / name
    # Exclude anything a setup step regenerates. Copying an installed
    # node_modules moves its .bin symlinks, which are relative and break -
    # and the setup step reinstalls it anyway, which is what an adopter does.
    shutil.copytree(ADAPTERS / name, work,
                    ignore=shutil.ignore_patterns("node_modules", "*.feature",
                                                  "__pycache__"))
    if setup:
        s = subprocess.run(setup, cwd=str(work), capture_output=True,
                           text=True, timeout=900)
        assert s.returncode == 0, (
            f"{name}: the documented setup step failed:\n{s.stderr[-800:]}")

    out_flag = []
    if name != "pytest-bdd":
        out_flag = ["--out", "features/reset-password.feature"]
    r = subprocess.run(
        [sys.executable, str(CLI), "bdd", "extract", "--issue",
         "reset-password", *out_flag],
        cwd=str(work), capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, f"{name}: extract failed:\n{r.stderr[-500:]}"

    # `make test` runs the suite with plugin autoload off, and pytest-bdd is
    # a plugin: the adapter's own run must turn it back on, as an adopter's
    # shell has it (#114).
    env = {k: v for k, v in os.environ.items()
           if k != "PYTEST_DISABLE_PLUGIN_AUTOLOAD"}
    r = subprocess.run(run_cmd, cwd=str(work), capture_output=True,
                       text=True, timeout=600, env=env)
    assert r.returncode == 0, (
        f"{name}: the documented run command failed:\n{r.stdout[-2000:]}\n"
        f"{r.stderr[-1000:]}")
    combined = r.stdout + r.stderr
    assert re.search(r"3 scenario|ok\s|3 passed", combined), (
        f"{name}: the runner did not report three scenarios:\n{combined[-1500:]}")


def test_trc_a3_every_adapter_should_share_the_same_four_documented_steps():
    for name in sorted(EXPECTED):
        text = (ADAPTERS / name / "README.md").read_text(encoding="utf-8")
        for phrase, what in (("bdd_runner", "declaring the runner"),
                             ("compass bdd extract", "extracting"),
                             ("bdd_steps_dir", "binding steps"),
                             ("bdd_run_command", "running")):
            assert phrase in text, f"{name}: README omits {what}"


# godog is deliberately excluded. Its -godog.* flags exist only if the suite
# calls BindCommandLineFlags, which the idiomatic programmatic setup does not -
# so probing it returns "flag provided but not defined". Probing it would
# report every tag unbound and fail a passing suite, so it reports
# "unverified" instead, which is the honest answer.
SELECTOR_RUNNERS = {"pytest-bdd", "behave", "cucumber-js"}


def test_trc_a4_the_tag_selector_should_know_every_shipped_runner():
    mod = _bdd_module()
    for name in sorted(EXPECTED):
        cfg = yaml.safe_load(
            (ADAPTERS / name / ".compass" / "config.yml").read_text())
        runner = cfg["project"]["bdd_runner"]
        sel = mod._bdd_tag_selector(runner, [])
        if name in SELECTOR_RUNNERS:
            assert sel is not None, (
                f"{runner} has no tag selector, so `compass bdd verify` falls "
                f"back to scraping - which cannot tell 'nothing bound' from "
                f"'this runner does not print ids'")
            assert sel("TRC-A1"), f"{runner}: selector produced no arguments"
        else:
            assert sel is None, (
                f"{runner} gained a tag selector. If its flags really are "
                f"bindable now, verify a probe against the shipped adapter "
                f"before trusting it - the last one accused a passing suite.")


# --- group B: the adapters are actually run --------------------------------

def test_trc_b1_every_adapter_should_be_exercised_by_a_ci_job():
    wf = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    all_jobs = yaml.safe_dump(wf.get("jobs") or {})
    for name in sorted(EXPECTED):
        assert f"bdd-adapters/{name}" in all_jobs, (
            f"no CI job runs examples/bdd-adapters/{name}. An example no job "
            f"runs is an example nobody can trust - Compass ships none "
            f"without one.")


def test_trc_b2_an_adapter_whose_runner_is_absent_should_skip_loudly():
    """The skip must name the missing runner. A test that skips silently
    shows a green tick over an assertion nobody ran."""
    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert "pytest.skip(" in src, "no skip path exists"
    m = re.search(r"pytest\.skip\((.*?)\)\n", src, re.S)
    assert m and "{why}" in m.group(1), (
        "the skip does not say why it skipped")
    assert "{name}" in m.group(1), (
        "the skip does not name which adapter was skipped")
    assert "_runner_usable" in src, (
        "nothing decides usability, so a skip could hide a real failure")


# --- group C ---------------------------------------------------------------

def test_trc_c1_the_review_skill_should_be_within_its_stated_length():
    body = (ROOT / "skills" / "receiving-code-review" / "SKILL.md").read_text(
        encoding="utf-8").split("---", 2)[2]
    words = len(body.split())
    assert words <= 320, (
        f"the skill is {words} words. The improvement plan asked for ~200-300; "
        f"320 allows for the tilde. It shipped at 433 under a 500-word bound "
        f"that was set loose enough to pass what had already been written.")
    lowered = body.lower()
    for phrase in ("check each suggestion", "push back", "say what you did"):
        assert phrase in lowered, (
            f"trimming removed '{phrase}' - the three things the skill exists "
            f"to say")
