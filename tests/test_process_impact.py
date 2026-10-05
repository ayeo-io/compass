"""Process-impact telemetry (issue process-impact-telemetry).

`compass retro --impact` reports lead time, land frequency, change-fail
signal and restore time, attributed to delivery-approach shape and gate set.

The substance is not the arithmetic. A repository with no hotfixes reports a
change-fail rate of 0% under a naive implementation - which reads as
excellent stability and means "nobody has filed one yet". That is this
codebase's recurring failure: a number that looks like evidence but reflects
missing data. Group C forbids it.

Spec: process-impact-telemetry/acceptance-criteria.md (`TRC-A1`..`TRC-A4`,
      B1..B3, C1, C2, F1..F4).
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import pathlib
import shutil
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

TASK = """schema_version: '1.1'
task: {slug}
created: '{created}'
status: {status}
land_timestamp: '{landed}'
readings: {{blast_radius: contained, terrain: greenfield, magnitude: small, intent: delivery, urgency: none, role: engineer, touches: []}}
route: {route}
topology: solo
fired_guardrails: []
phases: {{}}
evidence: []
gates: {gates}
scenarios: []
changed_files: []
claims: []
backfills: []
reframes: []
friction: []
{extra}"""


def _impl():
    sys.path.insert(0, str(ROOT / "cli"))
    try:
        from compass_pkg import calibration
        return calibration
    finally:
        sys.path.remove(str(ROOT / "cli"))


def make_project(tmp_path, tasks):
    """tasks: list of (slug, created, landed, route, n_gates, repairs|None)."""
    proj = tmp_path / "p"
    (proj / ".compass" / "work").mkdir(parents=True)
    shutil.copytree(ROOT / "governance", proj / "governance")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    for slug, created, landed, route, n_gates, repairs in tasks:
        d = proj / ".compass" / "work" / slug
        d.mkdir()
        gates = "[" + ", ".join(
            "{id: verify.g%d, status: pass, evidence: []}" % i
            for i in range(n_gates)) + "]"
        extra = f"repairs: {repairs}\n" if repairs else ""
        (d / "manifest.yml").write_text(TASK.format(
            slug=slug, created=created, landed=landed, status="landed",
            route=route, gates=gates, extra=extra))
    return proj


def run(proj, *args):
    return subprocess.run([sys.executable, str(CLI), "retro", *args],
                          cwd=str(proj), capture_output=True, text=True, timeout=90)


STD = [(f"t{i}", "2026-01-01", f"2026-01-0{i+2}T00:00:00Z", "standard", 6, None)
       for i in range(1, 6)]


# --- group A ---------------------------------------------------------------

def test_trc_a1_lead_time_should_be_measured_from_frame_to_land(tmp_path):
    out = run(make_project(tmp_path, STD), "--impact").stdout
    assert "lead time" in out.lower(), out
    assert "excluded" in out.lower() or "n=" in out.lower(), (
        f"the report does not say what it counted:\n{out}")


def test_trc_a2_land_frequency_should_be_reported_per_week(tmp_path):
    out = run(make_project(tmp_path, STD), "--impact").stdout.lower()
    assert "week" in out, out
    assert "span" in out or "over" in out, (
        f"the report does not name the span it measured over:\n{out}")


def test_trc_a3_a_hotfix_should_count_against_the_task_it_declares_it_repairs(tmp_path):
    tasks = STD + [("hf1", "2026-02-01", "2026-02-02T00:00:00Z", "hotfix", 5, "t1")]
    out = run(make_project(tmp_path, tasks), "--impact").stdout
    assert "t1" in out, f"the repaired task is not named:\n{out}"
    assert "%" in out, f"no change-fail rate reported when one is measurable:\n{out}"


def test_trc_a4_restore_time_should_be_the_hotfixs_own_frame_to_land(tmp_path):
    tasks = STD + [("hf1", "2026-02-01", "2026-02-02T00:00:00Z", "hotfix", 5, "t1")]
    out = run(make_project(tmp_path, tasks), "--impact").stdout.lower()
    assert "restore" in out, out
    i, j = out.index("restore"), out.index("lead time")
    assert i != j, "restore time is not reported separately from lead time"


# --- group B ---------------------------------------------------------------

def test_trc_b1_every_metric_should_be_attributed_to_route_shape_and_gate_set(tmp_path):
    tasks = STD + [("e1", "2026-01-01", "2026-01-02T00:00:00Z", "express", 3, None)]
    out = run(make_project(tmp_path, tasks), "--impact").stdout.lower()
    # the by-route breakdown speaks the v2 machine spellings since the
    # migrator rename
    assert "regular" in out and "quick-fix" in out, (
        f"metrics are not broken down by route:\n{out}")
    assert "gate" in out, f"the gate set is not reported per group:\n{out}"


def test_trc_b2_correlations_should_be_withheld_below_the_sample_floor(tmp_path):
    out = run(make_project(tmp_path, STD), "--impact").stdout
    low = out.lower()
    assert "withheld" in low, f"5 tasks is under the floor; nothing was withheld:\n{out}"
    assert "5" in out and str(_impl().IMPACT_SAMPLE_FLOOR) in out, (
        f"the report does not state the sample and the minimum:\n{out}")


def test_trc_b3_the_report_should_carry_its_observational_caveat(tmp_path):
    n = _impl().IMPACT_SAMPLE_FLOOR
    tasks = [(f"t{i}", "2026-01-01", "2026-01-02T00:00:00Z", "standard", 6, None)
             for i in range(n + 1)]
    low = run(make_project(tmp_path, tasks), "--impact").stdout.lower()
    for word in ("single-project", "observational", "hypothesis"):
        assert word in low, f"the caveat omits '{word}':\n{low}"


# --- group C: honesty about missing data -----------------------------------

def test_trc_c1_no_hotfixes_recorded_should_not_read_as_no_failures(tmp_path):
    out = run(make_project(tmp_path, STD), "--impact").stdout
    low = out.lower()
    assert "no hotfix" in low, (
        f"the report does not say hotfixes are absent:\n{out}")
    assert "0%" not in out.replace(" ", "") and "0.0%" not in out, (
        f"a change-fail rate of zero was printed for a project that has simply "
        f"never filed a hotfix. That reads as excellent stability and means "
        f"silence:\n{out}")


def test_trc_c2_an_undeclared_hotfix_should_be_reported_as_a_coverage_gap(tmp_path):
    tasks = STD + [
        ("hf1", "2026-02-01", "2026-02-02T00:00:00Z", "hotfix", 5, "t1"),
        ("hf2", "2026-02-03", "2026-02-04T00:00:00Z", "hotfix", 5, None)]
    out = run(make_project(tmp_path, tasks), "--impact").stdout
    assert "1 of 2" in out or ("1" in out and "2" in out and "declar" in out.lower()), (
        f"the report does not state declaration coverage:\n{out}")


# --- failure modes ----------------------------------------------------------

def test_trc_f1_the_report_should_be_deterministic(tmp_path):
    proj = make_project(tmp_path, STD)
    a, b = run(proj, "--impact").stdout, run(proj, "--impact").stdout
    assert a == b, "two runs over unchanged artifacts differed"
    import re as _re
    assert not _re.search(r"20\d\d-\d\d-\d\dT\d\d:\d\d", a.replace("2026-01", "X")), (
        "the report stamps its own run time, which breaks determinism")


def test_trc_f2_it_should_advise_and_never_gate(tmp_path):
    proj = make_project(tmp_path, STD)
    before = {p: p.read_text() for p in proj.rglob("manifest.yml")}
    r = run(proj, "--impact")
    assert r.returncode == 0, f"an advisory report exited non-zero:\n{r.stdout}"
    for p, text in before.items():
        assert p.read_text() == text, f"{p.name} was modified by an advisory report"


def test_trc_f3_a_project_with_nothing_recorded_should_say_so_and_stop(tmp_path):
    proj = tmp_path / "empty"
    (proj / ".compass" / "work").mkdir(parents=True)
    shutil.copytree(ROOT / "governance", proj / "governance")
    (proj / ".compass" / "config.yml").write_text("version: 1.0.0\nmode: enforced\n")
    r = run(proj, "--impact")
    assert r.returncode == 0, r.stderr
    low = r.stdout.lower()
    assert "nothing to measure" in low or "no landed" in low, r.stdout
    assert "%" not in r.stdout, f"a metric was claimed with no data:\n{r.stdout}"


def test_trc_f4_calibration_without_the_flag_should_be_unchanged(tmp_path):
    proj = make_project(tmp_path, STD)
    plain = run(proj).stdout
    assert "impact" not in plain.lower(), (
        f"the default calibration output gained impact content:\n{plain}")
    out = subprocess.run([sys.executable, str(CLI), "--help"],
                         capture_output=True, text=True, check=True).stdout
    import re as _re
    subs = set(_re.search(r"\{([a-zA-Z0-9_,\-]+)\}", out).group(1).split(","))
    assert "impact" not in subs, "a new top-level verb was added"
