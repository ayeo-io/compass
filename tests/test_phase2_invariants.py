"""Invariants for the phase-2 additions (issue phase-2-skills-check-and-cli-split).

Two skills and one check were added. The properties that must survive that:
a project which opted into nothing sees no change, every issue already on disk
returns what it returned before, and the framework grew by artifacts and checks
only - no guardrail, gate, assessment dimension, or top-level CLI verb.

Spec: phase-2-skills-check-and-cli-split/acceptance-criteria.md (`TRC-F1`..`TRC-F3`).
"""

# These tests read the per-check detail (name, PASS/FAIL, reason) that
# `compass check --verbose` prints.
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# The archive these tests read: the tracked sample, or this checkout's own
# with COMPASS_FULL_ARCHIVE=1 (tests/archive.py).
sys.path.insert(0, str(ROOT / "tests"))
from archive import archive_root  # noqa: E402
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"


def test_trc_f1_a_project_that_opted_into_nothing_should_see_no_change():
    proj = pathlib.Path(tempfile.mkdtemp(prefix="compass-phase2-"))
    try:
        shutil.copytree(GOVERNANCE, proj / "governance")
        (proj / ".compass" / "work").mkdir(parents=True)
        # This repository holds its settings in compass.yml; an older layout
        # held them in .compass/config.yml. Copy whichever exists.
        for source, target in ((ROOT / "compass.yml", proj / "compass.yml"),
                               (ROOT / ".compass" / "config.yml",
                                proj / ".compass" / "config.yml")):
            if source.is_file():
                shutil.copyfile(source, target)
        r = subprocess.run([sys.executable, str(CLI), "ci"], cwd=str(proj),
                           capture_output=True, text=True, timeout=300)
        assert r.returncode == 0, (
            f"a project that opted into nothing fails compass ci:\n{r.stdout[-2500:]}")
        lowered = r.stdout.lower()
        for word in ("bdd runner", "executable", "scenarios-are-executable"):
            assert word not in lowered, (
                f"compass ci mentions {word!r} for a project that wired no "
                f"runner:\n{r.stdout[-1500:]}")
    finally:
        shutil.rmtree(proj, ignore_errors=True)


def _archive_slugs():
    """(non-spike slugs, spike slugs) in the local archive, or two empty
    lists when there is none.

    A Spike runs `spike_guardrails`, not `G1`-`G5` - the BDD and TDD
    strategies are suspended there by design, so a check about executable
    scenarios correctly never fires. Excluded rather than asserted over.
    A manifest that cannot be read counts as not a spike, so it is checked.
    """
    work = archive_root() / ".compass" / "work"
    if not work.is_dir():
        return [], []
    slugs, spikes = [], []
    for p in sorted(work.iterdir()):
        if not (p / "manifest.yml").is_file():
            continue
        try:
            data = yaml.safe_load((p / "manifest.yml").read_text()) or {}
        except yaml.YAMLError:
            data = {}
        is_spike = isinstance(data, dict) and data.get("delivery_approach") == "spike"
        (spikes if is_spike else slugs).append(p.name)
    return slugs, spikes


_SLUGS, _SPIKES = _archive_slugs()


def test_trc_f2_the_archive_sweep_is_not_empty_and_covers_a_spike():
    """The per-issue sweep below is only a guard if it has issues to check,
    and its spike exclusion is only tested while a spike exists."""
    if not (archive_root() / ".compass" / "work").is_dir():
        return
    assert _SLUGS or _SPIKES, "no tasks on disk - this guard would be empty"
    assert _SPIKES, (
        "no Spike task on disk, so the exclusion above is untested - if every "
        "Spike has been archived, simplify this test rather than leaving a "
        "branch nothing exercises")


# One test per issue, so parallel workers share the sweep. With no local
# archive the list is empty and pytest skips it, as the loop returned early.
@pytest.mark.parametrize("slug", _SLUGS)
def test_trc_f2_adding_the_check_should_not_change_any_existing_tasks_result(slug):
    """Every issue already on disk must still check the way it did.

    The new check runs inside `G1`, which is always active - so a bug in it
    would change the result for every issue in the repository at once. This
    is the guard on that.
    """
    r = subprocess.run(
        [sys.executable, str(CLI), "check", "--verbose", "--issue", slug],
        cwd=str(archive_root()), capture_output=True, text=True, timeout=180)
    line = next((l for l in r.stdout.splitlines()
                 if "scenarios-are-executable" in l), "")
    assert line, (
        f"{slug}: the check did not run - it is registered under G1, which is "
        f"always active on a delivery route, so it should run for every issue")
    # No issue in this repository has wired a runner, so every one of them
    # must take the no-op path, labelled NOTHING TO CHECK since #110. A FAIL
    # here would mean the check is penalising projects for not having opted in.
    assert line.strip().startswith("NOTHING TO CHECK"), (
        f"{slug}: the new check fails a task that wired no runner:\n{line}")
    assert "runner" in line.lower(), (
        f"{slug}: the no-op pass gives no reason:\n{line}")


EXPECTED_GUARDRAIL_IDS = {"G1", "G2", "G3", "G4", "G5", "S1", "S2"}
# Each verb below is in the set for its own reason. `plan` is the planning
# stage's live command. `intent` reads a brief that already exists, by path
# or https URL, so a team arriving with one does not retype it - a
# top-level group rather than a subverb, because no subverb owns it.
EXPECTED_SUBCOMMANDS = {
    "approach", "bdd", "check", "analyze", "retro", "ci", "tdd-red",
    "tdd-green", "policy", "plan", "intent", "issue", "adr", "rework-scan", "flow",
    "next", "follow-up", "ship-commit", "gate", "scenario", "changed-file",
    "evidence", "terminology",
    "review-rule", "spec", "preset",  # `review-rule list`, `spec sync`, `preset init|test`
    # `init` creates `.compass/config.yml` and `.compass/work/`, and is safe
    # to run twice. It exists because no other command owns initialisation,
    # and the five entry points call it directly.
    "init",
    # `acceptance` is the recorded path for a change with no natural
    # behavioural red - config, docs, a behaviour-preserving refactor. It is a
    # GROUP (`start`, `record`), so later kinds add a subcommand rather than a
    # verb.
    "acceptance",
    # `quick-fix` (`start`, `finish`) - the mechanical steps of a quick fix
    # in two calls instead of a dozen. A GROUP, for the same reason `bdd`
    # and `acceptance` are.
    "quick-fix",
    # decisions-ledger (ADR-027): a group, record|list|show|check.
    "decision",
    "lesson",  # project-lessons (ADR-029)
    "run",  # headless-runner (ADR-030)
    "record",  # delivery-record (ADR-031)
    "board",  # compass-board (ADR-046): render|refresh - the delivery board page
}
EXPECTED_READING_KEYS = {
    "risk", "familiarity", "size", "goal", "urgency", "role",
    "labels_common",
}


def test_trc_f3_the_framework_should_grow_by_artifacts_and_checks_only():
    g = yaml.safe_load((GOVERNANCE / "guardrails.yml").read_text())
    ids = {x["id"] for x in g["defaults"]} | {x["id"] for x in g["spike_guardrails"]}
    ids |= {x["id"] for x in (g.get("project") or [])}
    assert ids == EXPECTED_GUARDRAIL_IDS, (
        f"the guardrail id set changed: {sorted(ids ^ EXPECTED_GUARDRAIL_IDS)}")

    policy = yaml.safe_load((GOVERNANCE / "routing-policy.yml").read_text())
    assert set(policy["assessment_vocabulary"]) == EXPECTED_READING_KEYS, (
        "the reading vocabulary changed")

    gates = set()
    for shape in policy["route_shapes"].values():
        gates.update(shape.get("gates", []))
    known = {"verify.correctness", "verify.governance", "verify.traceability",
             "verify.regression", "verify.security", "verify.clarity",
             "verify.claims", "verify.analyze", "verify.architecture",
             "spike.conclude"}
    assert gates <= known, f"new gate id(s): {sorted(gates - known)}"

    out = subprocess.run([sys.executable, str(CLI), "--help"],
                         capture_output=True, text=True, check=True).stdout
    m = re.search(r"\{([a-zA-Z0-9_,\-]+)\}", out)
    assert m, out
    assert set(m.group(1).split(",")) == EXPECTED_SUBCOMMANDS, (
        "a new top-level CLI verb appeared. `compass bdd verify` is a "
        "subcommand of the existing `bdd` group, which is exactly why that "
        "group was created rather than a flat verb.")

    # and the additions really are two skills plus one check
    skills = {p.name for p in (ROOT / "skills").iterdir()
              if p.is_dir() and (p / "SKILL.md").is_file()}
    assert {"systematic-debugging", "receiving-code-review"} <= skills
    assert "scenarios-are-executable" in g["checks"]
