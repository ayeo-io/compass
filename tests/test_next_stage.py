"""`compass next` reports the stage an issue has reached: the
next-never-leaves-assess issue, scenarios NS-A to NS-I. The current one is in
`docs/system-spec.md`, and the eight it supersedes are in
`docs/system-spec-archive.md`.

The stage is derived from the records on disk. The status line and the rail
take it from the same place, so all three must agree.

Each test builds a project with `compass approach evaluate`, then adds the
records a stage leaves, as the commands write them: documents registered as
`draft` with a path, scenarios, a subtask, a red, scenario-bound test
evidence, passed gates.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
SHIM = ROOT / "bin" / "compass-statusline"
SLUG = "the-issue"
SCENARIOS = ["S-1", "S-2"]

ROUTES = {
    "quick-fix": {"risk": "trivial", "familiarity": "brownfield-mapped",
                  "size": "atomic", "goal": "delivery", "role": "engineer"},
    "feature": {"risk": "contained", "familiarity": "brownfield-mapped",
                "size": "standard", "goal": "delivery", "role": "engineer"},
    # The only route that earns a requirements review.
    "initiative": {"risk": "cross-cutting", "familiarity": "brownfield-unmapped",
                   "size": "large", "goal": "delivery", "role": "engineer"},
}


def _env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDECODE", "NO_COLOR", "COMPASS_COLOR", "COLUMNS")}
    env.update(extra)
    return env


def _issue(root: Path, route: str, *, scenarios=True, criteria=None, review=False,
           review_file=False,
           design=False,
           dist_map=False, subtask=False, red=False, green=(), narrative=(),
           gates_pass=False, landed=False, current_phase=None, raw=None) -> Path:
    """A project at `root` whose one issue carries the named records,
    registered as the commands register them: `draft`, with a path."""
    import yaml
    task = root / ".compass" / "work" / SLUG
    task.mkdir(parents=True)
    (root / ".compass" / "current-task").write_text(SLUG + "\n")
    (task / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "issue": SLUG, "created": "2026-10-02",
        "status": "active", "assessment": ROUTES[route]}, sort_keys=False))
    r = subprocess.run([sys.executable, str(CLI), "approach", "evaluate", "--issue", SLUG,
                        "--write"], cwd=root, capture_output=True, text=True, env=_env())
    assert r.returncode == 0, r.stdout + r.stderr
    (task / "delivery-approach.md").write_text(f"# Delivery approach - {SLUG}\n")
    m = yaml.safe_load((task / "manifest.yml").read_text())
    if scenarios:
        m["scenarios"] = [dict({"id": s, "title": s, "intent": "INT-1", "tests": ["tests/t.py"]},
                               **({"verifiable": "narrative"} if s in narrative else {}))
                          for s in SCENARIOS]
    arts = []
    if criteria:
        arts.append({"id": "ART-AC", "kind": "acceptance-criteria", "status": criteria,
                     "path": "docs/ac.md"})
    if review_file:
        # Written and left unregistered, as commands/refine.md says to do on
        # a route that does not earn the review.
        docs = root / "docs" / "compass" / f"2026-10-02-{SLUG}"
        docs.mkdir(parents=True)
        (docs / "requirements-review.md").write_text("# Requirements review\n")
    if review:
        arts.append({"id": "ART-RR", "kind": "requirements-review", "status": "draft",
                     "path": "docs/rr.md"})
    if design:
        arts.append({"id": "ART-TD", "kind": "technical-design", "status": "draft",
                     "path": "docs/td.md"})
    if dist_map:
        arts.append({"id": "ART-DM", "kind": "distribution-map", "status": "omitted",
                     "reason": "one subtask"})
    # Merged by kind into the list `approach evaluate` seeded, which holds a
    # `draft` entry with no path for every document the route earns. Those
    # placeholders must not count as registered.
    by_kind = {a["kind"]: a for a in arts}
    m["artifacts"] = [by_kind.pop(a.get("kind"), a) for a in (m.get("artifacts") or [])]
    m["artifacts"] += list(by_kind.values())
    if subtask:
        m["subtasks"] = [{"id": "subtask-1", "status": "dispatched"}]
    if red:
        (task / "evidence").mkdir()
        (task / "evidence" / "red.json").write_text("{}")
    m["evidence"] = [{"id": f"EV-T-{s}", "type": "test-run", "path": f"evidence/green-{s}.json",
                      "scenario": s} for s in green]
    if gates_pass:
        for g in m["gates"]:
            g["status"] = "pass"
    if landed:
        m["status"] = "landed"
    if current_phase:
        m["current_phase"] = current_phase
    m.update(raw or {})
    (task / "manifest.yml").write_text(yaml.safe_dump(m, sort_keys=False))
    return task


def _next(root: Path) -> str:
    """The stage `compass next` names, or "done" for all phases complete."""
    r = subprocess.run([sys.executable, str(CLI), "next"], cwd=root,
                       capture_output=True, text=True, env=_env())
    out = r.stdout.strip()
    assert r.returncode == 0, out + r.stderr
    return "done" if out == "all phases complete" else out.split()[0].split("[")[0]


def _statusline(root: Path) -> str:
    r = subprocess.run([str(SHIM)], input=json.dumps({"cwd": str(root)}),
                       capture_output=True, text=True, env=_env(COLUMNS="200"), timeout=30)
    return r.stdout


def _rail_current(root: Path) -> str | None:
    """The stage carrying the rail's current marker, via COMPASS_COLOR=always
    with NO_COLOR, so the rail shows on a pipe without colour codes."""
    r = subprocess.run([sys.executable, str(CLI), "next"], cwd=root, capture_output=True,
                       text=True, env=_env(COMPASS_COLOR="always", NO_COLOR="1",
                                           COLUMNS="200"))
    m = re.search(r"(\w+) ●", r.stdout)
    return m.group(1) if m else None


CASES = {
    # NS-A
    "feature, approach only": (dict(route="feature", scenarios=False), "Define"),
    "quick-fix, approach only": (dict(route="quick-fix", scenarios=False), "Define"),
    "feature, criteria superseded": (dict(route="feature", scenarios=False,
                                          criteria="superseded"), "Define"),
    # NS-B
    # A feature earns no requirements review; refine's record there is the
    # review file, written and left unregistered.
    "feature, criteria draft": (dict(route="feature", criteria="draft"), "Refine"),
    "feature, review written": (dict(route="feature", criteria="draft",
                                     review_file=True), "Plan"),
    "initiative, criteria draft": (dict(route="initiative", criteria="draft"), "Refine"),
    "initiative, criteria without scenarios": (dict(route="initiative", scenarios=False,
                                                    criteria="draft"), "Refine"),
    "initiative, requirements review draft": (dict(route="initiative", criteria="draft",
                                                   review=True), "Plan"),
    # An initiative earns the review, so only a registered one clears refine.
    "initiative, review file unregistered": (dict(route="initiative", criteria="draft",
                                                  review_file=True), "Refine"),
    "quick-fix, scenarios only": (dict(route="quick-fix"), "Implement"),
    # NS-C
    "feature, design draft": (dict(route="feature", criteria="draft", design=True), "Breakdown"),
    "feature, subtask recorded": (dict(route="feature", criteria="draft", design=True,
                                       subtask=True), "Implement"),
    "feature, distribution map omitted": (dict(route="feature", criteria="draft", design=True,
                                               dist_map=True), "Implement"),
    # NS-D
    "feature, red only": (dict(route="feature", criteria="draft", red=True), "Implement"),
    "feature, one green of two": (dict(route="feature", criteria="draft", design=True,
                                       subtask=True, green=["S-1"]), "Implement"),
    # NS-E
    "feature, every green": (dict(route="feature", criteria="draft", green=SCENARIOS), "Verify"),
    "quick-fix, every green": (dict(route="quick-fix", green=SCENARIOS), "Verify"),
    "feature, green but for a narrative": (dict(route="feature", criteria="draft",
                                                green=["S-1"], narrative=["S-2"]), "Verify"),
    # NS-F
    "feature, gates passed": (dict(route="feature", criteria="draft", green=SCENARIOS,
                                   gates_pass=True), "Ship"),
    "feature, landed": (dict(route="feature", criteria="draft", green=SCENARIOS,
                             gates_pass=True, landed=True), "done"),
}


@pytest.mark.parametrize("case", list(CASES))
def test_next_reports_the_stage_the_records_show(tmp_path, case):
    """NS-A to NS-F: each set of records gives the stage the issue has reached."""
    kwargs, expected = CASES[case]
    _issue(tmp_path, **kwargs)
    assert _next(tmp_path) == expected, case


def test_current_phase_overrides_the_records(tmp_path):
    """NS-G: fixtures that set the key keep their meaning."""
    _issue(tmp_path, "feature", criteria="draft", green=SCENARIOS, current_phase="plan")
    assert _next(tmp_path) == "Plan"


@pytest.mark.parametrize("case", [c for c, (_, stage) in CASES.items() if stage != "done"])
def test_status_line_and_rail_name_the_same_stage(tmp_path, case):
    """NS-H: the status line and the rail name the same stage as `compass next`."""
    kwargs, expected = CASES[case]
    _issue(tmp_path, **kwargs)
    assert _next(tmp_path) == expected
    assert f" · {expected} · " in _statusline(tmp_path), (case, _statusline(tmp_path))
    assert _rail_current(tmp_path) == expected, case


def test_a_landed_issue_reads_done_on_the_status_line(tmp_path):
    """NS-H, the finished case: no stage is current, so the rail has no
    current marker and the status line says done."""
    _issue(tmp_path, "feature", criteria="draft", green=SCENARIOS, gates_pass=True, landed=True)
    assert " · done · " in _statusline(tmp_path)
    assert _rail_current(tmp_path) is None


MALFORMED = {
    "artifacts not a list": {"artifacts": 5},
    "evidence not a list": {"evidence": 7},
    "scenarios not a list": {"scenarios": 3},
    "subtasks not a list": {"subtasks": "subtask-1"},
    "a list as an evidence scenario": {"evidence": [{"type": "test-run", "scenario": ["A"]}]},
    "a list as a scenario id": {"scenarios": [{"id": ["A"]}]},
    "junk entries": {"artifacts": [5, None], "evidence": ["x"], "scenarios": [1]},
}


@pytest.mark.parametrize("case", list(MALFORMED))
def test_a_malformed_manifest_still_names_a_stage(tmp_path, case):
    """NS-I: a hand-edited manifest gets a stage, not a traceback, and the
    status line keeps its line."""
    _issue(tmp_path, "feature", criteria="draft", raw=MALFORMED[case])
    r = subprocess.run([sys.executable, str(CLI), "next"], cwd=tmp_path,
                       capture_output=True, text=True, env=_env())
    assert r.returncode == 0 and r.stdout.split()[0].isalpha(), (case, r.stdout, r.stderr)
    assert "Traceback" not in r.stderr, r.stderr
    assert f" · {_next(tmp_path)} · " in _statusline(tmp_path), case
