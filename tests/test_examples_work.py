"""Every shipped example does what the framework says it does.

Every example passes `compass check` and `compass bdd extract`.
`examples/README.md` tells an adopter that `compass check --issue <slug>`
passes inside any example, and reference material is the first thing a
newcomer runs, so an example that fails the guardrail it is demonstrating
teaches exactly the wrong lesson.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import tempfile

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
EXAMPLES = ROOT / "examples"


def _route_examples():
    """Example directories that carry a Compass issue (not the BDD adapters)."""
    out = []
    for d in sorted(EXAMPLES.iterdir()):
        if not d.is_dir() or d.name == "bdd-adapters":
            continue
        work = d / ".compass" / "work"
        if not work.is_dir():
            continue
        for t in sorted(work.iterdir()):
            if (t / "manifest.yml").is_file():
                out.append((d.name, t.name))
    return out


ROUTE_EXAMPLES = _route_examples()


def _sandbox(name):
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="compass-ex-"))
    shutil.copytree(EXAMPLES / name, tmp / name)
    return tmp, tmp / name


def test_there_are_route_examples_to_check():
    """Guards the guard: a parametrised test over an empty list passes silently."""
    assert len(ROUTE_EXAMPLES) >= 2, (
        f"expected the shipped route walkthroughs, found {ROUTE_EXAMPLES}")


@pytest.mark.parametrize("name,slug", ROUTE_EXAMPLES)
def test_every_example_passes_its_own_check(name, slug):
    """examples/README.md promises this."""
    tmp, work = _sandbox(name)
    try:
        r = subprocess.run([sys.executable, str(CLI), "check", "--issue", slug],
                           cwd=str(work), capture_output=True, text=True,
                           timeout=120)
        assert r.returncode == 0, (
            f"{name}: `compass check --issue {slug}` fails, but "
            f"examples/README.md tells adopters it passes:\n{r.stdout[-1800:]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.parametrize("name,slug", ROUTE_EXAMPLES)
def test_every_example_spec_extracts(name, slug):
    """`compass bdd extract` must read the framework's own specs.

    A spec with no scenario the extractor recognises fails with 'contains no
    Gherkin scenarios', which reads as 'your spec is malformed'.
    """
    tmp, work = _sandbox(name)
    try:
        spec = work / ".compass" / "work" / slug / "acceptance-criteria.md"
        if not spec.is_file():
            pytest.skip(f"{name} is a Spike - no spec by design")
        r = subprocess.run(
            [sys.executable, str(CLI), "bdd", "extract", "--issue", slug],
            cwd=str(work), capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, (
            f"{name}: extract failed on a spec the framework ships:\n"
            f"{r.stdout}{r.stderr}")
        out = work / ".compass" / "work" / slug / "acceptance-criteria.feature"
        assert out.is_file(), f"{name}: no feature file written"
        n = out.read_text().count("\n  Scenario:")
        declared = len(
            (yaml.safe_load((work / ".compass" / "work" / slug / "manifest.yml")
                            .read_text()) or {}).get("scenarios") or [])
        assert n == declared, (
            f"{name}: extracted {n} scenarios but manifest.yml declares {declared}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_every_bdd_adapter_has_a_ci_job():
    """An example no job runs is an example nobody can trust."""
    wf = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "compass.yml").read_text())
    jobs = yaml.safe_dump(wf.get("jobs") or {})
    adapters = [d.name for d in (EXAMPLES / "bdd-adapters").iterdir()
                if d.is_dir()]
    assert adapters, "no BDD adapters found"
    for a in adapters:
        assert f"bdd-adapters/{a}" in jobs, (
            f"no CI job runs examples/bdd-adapters/{a}")
