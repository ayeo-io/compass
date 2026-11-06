"""The delivery approaches can be seen without reading YAML.

What each approach does lives in `route_shapes` and `autonomy_checkpoints`
in `governance/routing-policy.yml`. `compass approach render` renders them
as one HTML table, one row per approach and one column per stage, with the
stops for a person under the chosen autonomy setting. The shipped policy's
render is committed as `docs/approach-diagram.html`, and a test fails when
the two differ, so the diagram cannot go stale.

Scenario ids: RD-1, RD-2, RD-3, RD-5 and RD-6 (issue `approach-diagram`) and EF-12
(issue `effective-readers`).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
COMMITTED = ROOT / "docs" / "approach-diagram.html"


def _diagram(cwd, *args, env=None):
    return subprocess.run([sys.executable, str(CLI), "approach", "render", *args],
                          cwd=cwd, capture_output=True, text=True, timeout=60,
                          env=None if env is None else {**os.environ, **env})


def _project(tmp_path, autonomy="balanced", policy=None):
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True, exist_ok=True)
    (root / ".compass" / "config.yml").write_text(f"autonomy: {autonomy}\n")
    if policy is not None:
        (root / "governance").mkdir()
        (root / "governance" / "routing-policy.yml").write_text(
            yaml.safe_dump(policy, sort_keys=False))
        for name in ("guardrails.yml",):
            shutil.copy(ROOT / "governance" / name, root / "governance" / name)
    return root


def _v8_policy():
    """The routing policy of the 8.0.4 governance copy. It declares the five 8.x
    approaches over the eight legacy stages, which the shipped default no
    longer does (ADR-092), so the renderer's handling of stops, skipped stages
    and an unlimited ceiling is tested on it."""
    import tarfile
    sys.path.insert(0, str(ROOT / "tests"))
    from compat_baseline import GOVERNANCE_8_0_4
    with tarfile.open(GOVERNANCE_8_0_4) as tar:
        return yaml.safe_load(tar.extractfile("governance/routing-policy.yml").read())


def _row(html, approach):
    match = re.search(rf'<tr data-approach="{re.escape(approach)}">(.*?)</tr>',
                      html, re.S)
    assert match, f"no row for {approach}"
    return match.group(1)


def _cell(row, stage):
    match = re.search(rf'<td data-stage="{stage}"[^>]*>(.*?)</td>', row, re.S)
    assert match, f"no {stage} cell"
    return re.sub(r"<[^>]+>", " ", match.group(1))


# --- RD-1: where a person approves ------------------------------------------

def test_rd_1_controlled_marks_assess_and_specify_of_the_shipped_path(tmp_path):
    result = _diagram(_project(tmp_path), "--autonomy", "controlled")
    assert result.returncode == 0, result.stderr
    delivery = _row(result.stdout, "delivery")
    for stage in ("assess", "specify"):
        assert "stops for you" in _cell(delivery, stage), stage
    for stage in ("build", "ship"):
        assert "stops for you" not in _cell(delivery, stage), stage
    assert '<td data-stage="define"' not in result.stdout


def test_rd_1_balanced_marks_regular_define_and_plan_and_no_quick_fix_stop(tmp_path):
    result = _diagram(_project(tmp_path, policy=_v8_policy()), "--autonomy", "balanced")
    assert result.returncode == 0, result.stderr
    regular = _row(result.stdout, "regular")
    for stage in ("define", "plan"):
        assert "stops for you" in _cell(regular, stage), stage
    for stage in ("assess", "refine", "implement"):
        assert "stops for you" not in _cell(regular, stage), stage
    assert "stops for you" not in _row(result.stdout, "quick-fix")


def test_rd_1_every_cell_names_its_weight_as_a_word(tmp_path):
    html = _diagram(_project(tmp_path), "--autonomy", "balanced").stdout
    policy = yaml.safe_load((ROOT / "governance" / "routing-policy.yml").read_text())
    for approach, shape in policy["route_shapes"].items():
        row = _row(html, approach)
        for stage, weight in shape["stages"].items():
            assert weight in _cell(row, stage), (approach, stage, weight)


# --- RD-2: the autonomy setting ----------------------------------------------

def test_rd_2_the_projects_autonomy_is_the_default(tmp_path):
    html = _diagram(_project(tmp_path, autonomy="autonomous")).stdout
    assert "stops for you" not in html
    assert "autonomous" in html


def test_rd_2_an_unknown_autonomy_is_refused(tmp_path):
    result = _diagram(_project(tmp_path), "--autonomy", "reckless")
    assert result.returncode != 0
    assert "balanced" in result.stderr, result.stderr


# --- RD-3: the project's own policy, through the current names -----------------

def test_rd_3_a_projects_policy_is_shown(tmp_path):
    policy = _v8_policy()
    policy["route_shapes"]["quick-fix"]["stages"]["define"] = "full"
    html = _diagram(_project(tmp_path, policy=policy), "--autonomy", "balanced").stdout
    assert "full" in _cell(_row(html, "quick-fix"), "define")


def test_rd_3_an_old_keyed_policy_shows_the_current_names(tmp_path):
    old = yaml.safe_load(
        (ROOT / "tests" / "fixtures" / "routing-policy-old-route-names.yml").read_text())
    result = _diagram(_project(tmp_path, policy=old), "--autonomy", "balanced")
    assert result.returncode == 0, result.stderr
    for approach in ("quick-fix", "regular", "full"):
        _row(result.stdout, approach)


# --- RD-5: how work comes back -------------------------------------------------

def test_rd_5_the_three_ways_back_are_named(tmp_path):
    html = _diagram(_project(tmp_path), "--autonomy", "balanced").stdout
    for way in ("compass:assess --reassess", "pre-tool hook", "compass check"):
        assert way in html, way


# --- RD-6: the committed diagram cannot go stale ---------------------------------

def test_rd_6_the_committed_diagram_matches_a_fresh_render():
    # Rendered from the shipped policy directly, so no governance/ folder
    # above the test's working directory can change what it compares.
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg.approach_diagram import render
    policy = yaml.safe_load((ROOT / "governance" / "routing-policy.yml").read_text())
    fresh = render(policy, "balanced")
    assert COMMITTED.is_file(), "docs/approach-diagram.html is missing"
    assert COMMITTED.read_text(encoding="utf-8") == fresh, (
        "docs/approach-diagram.html is stale: run `compass approach render "
        "--autonomy balanced --out docs/approach-diagram.html` from a folder "
        "with no governance/ of its own")


def test_rd_6_two_renders_are_identical_and_a_changed_weight_differs(tmp_path):
    first = _diagram(_project(tmp_path), "--autonomy", "balanced").stdout
    assert first == _diagram(_project(tmp_path), "--autonomy", "balanced").stdout
    policy = yaml.safe_load((ROOT / "governance" / "routing-policy.yml").read_text())
    policy["route_shapes"]["delivery"]["stages"]["specify"] = "lightweight"
    other = tmp_path / "other"
    other.mkdir()
    changed = _diagram(_project(other, policy=policy), "--autonomy", "balanced").stdout
    assert changed != first


# --- review 1 -------------------------------------------------------------------

def test_rd_1_the_page_says_these_are_defaults_and_names_what_raises_them(tmp_path):
    html = _diagram(_project(tmp_path), "--autonomy", "balanced").stdout
    assert "defaults" in html
    for raiser in ("floor", "domain label", "governance/routing-policy.md"):
        assert raiser in html, raiser


def test_rd_1_no_subtask_ceiling_reads_as_no_limit(tmp_path):
    html = _diagram(_project(tmp_path, policy=_v8_policy()), "--autonomy", "balanced").stdout
    assert "None" not in _row(html, "full")
    assert "no limit" in _row(html, "full")


def test_rd_1_a_skipped_stage_never_stops(tmp_path):
    policy = _v8_policy()
    policy["route_shapes"]["quick-fix"]["stages"]["refine"] = "skipped"
    policy["autonomy_checkpoints"]["balanced"]["quick-fix"] = ["refine"]
    html = _diagram(_project(tmp_path, policy=policy), "--autonomy", "balanced").stdout
    assert "stops for you" not in _cell(_row(html, "quick-fix"), "refine")


# --- EF-12: a project's compass.yml is the policy the diagram shows ---

def _layered(tmp_path, compass_yml):
    # No .compass/config.yml: a compass.yml that is read owns the settings.
    root = tmp_path / "proj"
    (root / ".compass").mkdir(parents=True, exist_ok=True)
    (root / "compass.yml").write_text(compass_yml, encoding="utf-8")
    return root


LAYERED = """\
schema: 1
approaches:
  delivery:
    set:
      stages: {specify: full, build: full}
      gates: [verify.correctness]
      checkpoints:
        balanced: [build]
"""


def _with_git_parent(tmp_path, parent_yml):
    """A project whose `compass.yml` extends a local git parent holding
    `parent_yml`, the environment that lets Compass fetch it, and the
    `compass policy lint --json` findings of the fetch."""
    sys.path.insert(0, str(ROOT / "tests"))
    from parent_fixtures import make_remote
    base = tmp_path / "remotes"
    sha = make_remote(base, files={"compass.yml": parent_yml})
    extends = {"from": f"github:acme/bank@1.2.0#{sha}", "approved_by": "jed72",
               "approved_on": "2026-10-06"}
    root = _layered(tmp_path, yaml.safe_dump({"schema": 1, "extends": extends}))
    env = {"COMPASS_PARENT_REMOTE_BASE": str(base)}
    # `approach render` reads the parent cache only; `policy lint` fetches into it.
    lint = subprocess.run([sys.executable, str(CLI), "policy", "lint", "--json"], cwd=root,
                          capture_output=True, text=True, timeout=60,
                          env={**os.environ, **env})
    assert lint.returncode == 0, lint.stdout + lint.stderr
    return root, env, json.loads(lint.stdout)["findings"]


def test_ef_12_a_compass_yml_that_sets_approaches_shows_the_shipped_default(tmp_path):
    html = _diagram(_layered(tmp_path, LAYERED), "--autonomy", "balanced").stdout
    shipped = _diagram(_layered(tmp_path / "plain", "schema: 1\n"), "--autonomy",
                       "balanced").stdout
    assert _row(html, "delivery") == _row(shipped, "delivery")
    assert html.split("<table>")[1] == shipped.split("<table>")[1]


def test_ef_12_a_git_parent_that_sets_approaches_shows_the_shipped_default(tmp_path):
    """A git parent is read like a project layer since 9.0.0 (VD-006 of #351): its
    change to the approaches is left out, so the page shows the shipped rows. The
    rendering of a changed approach is tested on the 8.0.4 copy (`_v8_policy`)."""
    root, env, findings = _with_git_parent(tmp_path, LAYERED)
    assert [(f["code"], f["path"]) for f in findings if f["code"] == "L-SETTING-REMOVED"] \
        == [("L-SETTING-REMOVED", "approaches")], findings
    done = _diagram(root, "--autonomy", "balanced", env=env)
    html = done.stdout
    assert html, done.stderr
    shipped = _diagram(_layered(tmp_path / "plain", "schema: 1\n"), "--autonomy",
                       "balanced").stdout
    assert html.split("<table>")[1] == shipped.split("<table>")[1]


def test_ef_12_the_page_names_the_configuration_it_was_rendered_from(tmp_path):
    layered = _diagram(_layered(tmp_path, "schema: 1\nowner: jed72\n")).stdout
    assert "compass.yml" in layered
    assert "governance/routing-policy.yml" not in layered.split("<h2>")[0].split(
        "Generated by")[1]
    other = tmp_path / "other"
    other.mkdir()
    legacy = _diagram(_project(other)).stdout
    assert "Generated by <code>compass approach render</code> from " \
           "<code>governance/routing-policy.yml</code>" in legacy


def test_ef_12_a_compass_yml_that_cannot_resolve_is_refused(tmp_path):
    bad = "schema: 1\ngates:\n  nosuch: {set: {kind: review}}\n"
    result = _diagram(_layered(tmp_path, bad))
    assert result.returncode != 0
    assert result.stdout == ""
    assert "policy lint" in result.stderr, result.stderr
