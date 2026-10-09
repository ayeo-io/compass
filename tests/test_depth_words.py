"""Depth words (issue `vocabulary-and-cli-renames`, group A).

A stage mode and an artifact depth were renamed: `full` is now `thorough`,
`light` is now `lightweight`, and the longest stage mode is now
`thorough-with-follow-up`. `full` stays the name of a delivery approach, and
`collapsed`, `skipped` and the special modes keep their names. Every writer
emits the new words; the readers accept both (see `test_old_words_read.py`).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

PRESET = ROOT / "governance" / "presets" / "default"
POLICY_VIEW = ROOT / "governance" / "routing-policy.yml"

OLD_WORDS = {"full", "light", "full-plus-backfill"}
RANKS = {"skipped": 0, "collapsed": 1, "lightweight": 2, "thorough": 3,
         "thorough-with-follow-up": 4}
SPECIAL = {"multiagent", "reproduce-first", "expedited", "explore", "conclude",
           "graduate-or-discard"}
NEW_DEPTHS = {"thorough", "lightweight"}


def _preset(name):
    return yaml.safe_load((PRESET / name).read_text(encoding="utf-8"))


def _modes(doc):
    """Every stage mode the preset names: the modes each stage declares and
    the mode each approach gives each stage."""
    found = []
    for stage, body in doc["stages"].items():
        found += [(f"stages.{stage}.modes", mode) for mode in body.get("modes") or {}]
    return found


def _approach_words(doc):
    modes, depths = [], []
    for name, body in doc["approaches"].items():
        modes += [(f"approaches.{name}.stages.{stage}", mode)
                  for stage, mode in (body.get("stages") or {}).items()]
        depths += [(f"approaches.{name}.artifacts.{kind}", depth)
                   for kind, depth in (body.get("artifacts") or {}).items()]
    return modes, depths


def _view_words():
    """The same words in the legacy routing policy view."""
    policy = yaml.safe_load(POLICY_VIEW.read_text(encoding="utf-8"))
    modes, depths = [], []
    for name, shape in policy["route_shapes"].items():
        modes += [(f"route_shapes.{name}.stages.{stage}", mode)
                  for stage, mode in (shape.get("stages") or {}).items()]
        depths += [(f"route_shapes.{name}.artifacts.{kind}", depth)
                   for kind, depth in (shape.get("artifacts") or {}).items()]
    return policy, modes, depths


# --- VR-A1 ---------------------------------------------------------------------

def test_vr_a1_the_default_preset_holds_only_the_new_depth_words():
    modes = _modes(_preset("stages.yml"))
    used, depths = _approach_words(_preset("approaches.yml"))
    words = {word for _, word in modes + used}
    assert words <= set(RANKS) | SPECIAL, sorted(words - set(RANKS) - SPECIAL)
    assert not words & OLD_WORDS, sorted(words & OLD_WORDS)
    assert {"thorough", "lightweight", "thorough-with-follow-up"} <= words, (
        "each renamed word is in use, so this check has something to find")
    depth_words = {depth for _, depth in depths}
    assert depth_words == NEW_DEPTHS, depth_words


# --- VR-A2 ---------------------------------------------------------------------

def test_vr_a2_the_evaluator_writes_the_new_words_and_keeps_the_approach(
        project, make_task, run_cli):
    import yaml as _yaml
    task_dir = make_task("big", {
        "schema_version": "2.0",
        "assessment": {"risk": "critical", "familiarity": "brownfield-mapped",
                       "size": "large", "goal": "delivery", "role": "engineer",
                       "labels": []}})
    result = run_cli("approach", "evaluate", "--issue", "big", "--write", timeout=60)
    assert result.returncode == 0, result
    manifest = _yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert manifest["delivery_approach"] == "full"
    stages = set(manifest["stages"].values())
    assert stages <= set(RANKS) | SPECIAL, stages
    assert "thorough" in stages and not stages & OLD_WORDS, stages
    depths = {a["depth"] for a in manifest["artifacts"] if "depth" in a}
    assert depths and depths <= NEW_DEPTHS, depths


def test_vr_a2_a_policy_copy_in_the_old_words_still_writes_the_new_ones(
        project, make_task, run_cli):
    """A project that copied `governance/` before the rename keeps the old
    words in its policy; the manifest the evaluator writes does not."""
    view = project / "governance" / "routing-policy.yml"
    text = view.read_text(encoding="utf-8")
    for new, old in (("thorough-with-follow-up", "full-plus-backfill"),
                     ("lightweight", "light")):
        text = re.sub(rf"(?<![\w-]){new}(?![\w-])", old, text)
    text = re.sub(r"(?<![\w-])thorough(?![\w-])", "full", text)
    text = re.sub(r"\bsize: medium\b", "size: standard", text)
    text = re.sub(r"(\[[^\]]*)\bmedium\b", r"\1standard", text)
    view.write_text(text, encoding="utf-8")
    task_dir = make_task("big", {
        "schema_version": "2.0",
        "assessment": {"risk": "critical", "familiarity": "brownfield-mapped",
                       "size": "large", "goal": "delivery", "role": "engineer",
                       "labels": []}})
    result = run_cli("approach", "evaluate", "--issue", "big", "--write", timeout=60)
    assert result.returncode == 0, result
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    assert not set(manifest["stages"].values()) & OLD_WORDS, manifest["stages"]
    assert not {a.get("depth") for a in manifest["artifacts"]} & OLD_WORDS


# --- VR-A3 ---------------------------------------------------------------------

def test_vr_a3_render_prints_each_stage_weight_in_the_new_words(run_cli):
    result = run_cli("approach", "render", timeout=30)
    assert result.returncode == 0, result
    cells = re.findall(r'<td data-stage="[a-z]+" class="[^"]+">([^<]+)</td>', result.stdout)
    assert cells, "the table has no stage cells"
    assert not set(cells) & OLD_WORDS, sorted(set(cells) & OLD_WORDS)
    assert {"thorough", "lightweight", "thorough-with-follow-up"} <= set(cells)
    names = re.findall(r'<tr data-approach="([^"]+)">', result.stdout)
    assert names == ["spike", "quick-fix", "regular", "hotfix", "full"], names
    owed = " ".join(re.findall(r"[a-z-]+ \((?:thorough|lightweight|full|light)\)",
                               result.stdout))
    assert "(full)" not in owed and "(light)" not in owed, owed


def test_vr_a3_show_keeps_the_approach_name_full(make_task, run_cli):
    make_task("big", {"delivery_approach": "full",
                      "assessment": {"risk": "critical", "familiarity": "greenfield",
                                     "size": "large"}})
    result = run_cli("approach", "show", "--issue", "big")
    assert result.returncode == 0, result
    assert result.stdout.startswith("Approach: full (risk critical"), result.stdout


# --- VR-A4 ---------------------------------------------------------------------

def test_vr_a4_the_ranks_keep_their_order_under_the_new_names():
    ranks = {}
    for stage, body in _preset("stages.yml")["stages"].items():
        for mode, spec in (body.get("modes") or {}).items():
            if "rank" in (spec or {}):
                ranks.setdefault(mode, set()).add(spec["rank"])
    assert {mode: sorted(r) for mode, r in ranks.items()} == {
        mode: [rank] for mode, rank in RANKS.items() if mode in ranks}
    ordered = sorted(ranks, key=lambda mode: RANKS[mode])
    assert ordered == ["skipped", "collapsed", "lightweight", "thorough",
                       "thorough-with-follow-up"]


def test_vr_a4_the_classifier_ranks_lightweight_below_thorough():
    import classifier_fixtures as fixtures
    from compass_pkg import classify
    parent = fixtures.base()
    for body in parent["stages"].values():
        body["modes"] = {"lightweight": {"rank": 2}, "thorough": {"rank": 3},
                         "reproduce-first": {}}
    for body in parent["approaches"].values():
        body["stages"] = {stage: "thorough" for stage in body["stages"]}
    child = {**parent, "approaches": {name: {**body, "stages": {
        **body["stages"], "implement": "lightweight"}}
        for name, body in parent["approaches"].items()}}
    looser = classify.classify(parent, child)
    tighter = classify.classify(child, parent)
    assert looser.result == "loosening", looser.result
    assert tighter.result == "tightening", tighter.result


def test_vr_a4_the_legacy_adapter_ranks_match_the_preset():
    from compass_pkg import legacy_adapter
    assert legacy_adapter.MODE_RANKS == RANKS


# --- VR-A5 ---------------------------------------------------------------------

def test_vr_a5_the_special_modes_and_the_two_ends_keep_their_names():
    declared = {mode for stage in _preset("stages.yml")["stages"].values()
                for mode in stage.get("modes") or {}}
    assert SPECIAL <= declared, sorted(SPECIAL - declared)
    assert {"collapsed", "skipped"} <= declared
    from compass_pkg import catalogue_spec
    assert catalogue_spec.ARTIFACT_DEPTHS == ("lightweight", "thorough")


# --- VR-A6 ---------------------------------------------------------------------

def test_vr_a6_the_regenerated_views_hold_no_old_depth_word():
    policy, modes, depths = _view_words()
    words = {word for _, word in modes}
    assert not words & OLD_WORDS, sorted(words & OLD_WORDS)
    assert not {d for _, d in depths} & OLD_WORDS
    assert {"thorough", "lightweight", "thorough-with-follow-up"} <= words
    ranks = policy.get("stage_mode_ranks") or {}
    ranked = {mode for stage in ranks.values() for mode in stage}
    assert not ranked & OLD_WORDS, sorted(ranked & OLD_WORDS)


def test_vr_a6_the_regenerated_views_evaluate_as_before_the_rename():
    """The baseline is the 5.6.0 capture, in the old words; the comparison maps
    its inputs and the evaluator's outputs through the rename table in
    `compat_baseline` (a documented bridge), then compares."""
    import compat_baseline as cb
    header, rows = cb.load_routing()
    grid_rows = [r for r in rows if r["kind"] in ("grid", "archive")]
    differences = cb.routing_differences(cb.shipped_policy(), header, grid_rows)
    assert differences == [], "\n".join(differences[:10])
