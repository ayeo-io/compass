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

#: The shipped default: the check set since 9.0.0 (ADR-094).
PRESET = None
# The shipped default declares the four path stages and only the modes its two
# approaches name since 9.0.0 (ADR-092). The renamed words are in use in the
# frozen `default@7` preset and the 8.0.4 views, so their presence is read there,
# and the live preset and views are held to hold no old word.
FROZEN = ROOT / "governance" / "presets" / "default@7"
POLICY_VIEW = ROOT / "governance" / "routing-policy.yml"

OLD_WORDS = {"full", "light", "full-plus-backfill"}
RANKS = {"skipped": 0, "collapsed": 1, "lightweight": 2, "thorough": 3,
         "thorough-with-follow-up": 4}
SPECIAL = {"multiagent", "reproduce-first", "expedited", "explore", "conclude",
           "graduate-or-discard"}


def _preset(name, folder=PRESET):
    if folder is None:
        from check_set_files import shipped
        return shipped(name)
    return yaml.safe_load((folder / name).read_text(encoding="utf-8"))


def _policy_8_0_4_text():
    import tarfile
    import compat_baseline as cb
    with tarfile.open(cb.GOVERNANCE_8_0_4) as tar:
        return tar.extractfile("governance/routing-policy.yml").read().decode("utf-8")


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


def _view_words(text=None):
    """The same words in the legacy routing policy view, or in `text`."""
    policy = yaml.safe_load(text if text is not None else POLICY_VIEW.read_text(encoding="utf-8"))
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
    assert {"thorough", "lightweight"} <= words
    frozen = {word for _, word in _modes(_preset("stages.yml", FROZEN))
              + _approach_words(_preset("approaches.yml", FROZEN))[0]}
    assert not frozen & OLD_WORDS, sorted(frozen & OLD_WORDS)
    assert {"thorough", "lightweight", "thorough-with-follow-up"} <= frozen, (
        "each renamed word is in use, so this check has something to find")
    # 9.0.0 declares no approach `artifacts:` map (ADR-091), so no document depth is
    # left to read in the live default.
    assert depths == [], depths


# --- VR-A2 ---------------------------------------------------------------------

BIG = {"risk": "critical", "familiarity": "brownfield-mapped", "size": "large",
       "goal": "delivery", "role": "engineer", "labels": []}


def _old_words(text):
    """`text` of a routing policy, spelled in the words before the rename."""
    for new, old in (("thorough-with-follow-up", "full-plus-backfill"),
                     ("lightweight", "light")):
        text = re.sub(rf"(?<![\w-]){new}(?![\w-])", old, text)
    text = re.sub(r"(?<![\w-])thorough(?![\w-])", "full", text)
    text = re.sub(r"\bsize: medium\b", "size: standard", text)
    return re.sub(r"(\[[^\]]*)\bmedium\b", r"\1standard", text)


def _route_8_0_4(policy=None):
    """The 8.0.4 evaluator's result for `BIG`. 9.0.0 writes no stage modes for a new
    issue (ADR-092 decision 1), so the words the evaluator gives a stage are judged
    on the 8.0.4 governance copy, the last release that routed approaches."""
    import compat_baseline as cb
    from compass_pkg import routing
    return routing.evaluate_route(dict(BIG), routing.prepare_policy(policy or cb.policy_8_0_4()))


def _path_write(make_task, run_cli):
    task_dir = make_task("big", {"schema_version": "2.0", "assessment": dict(BIG)})
    result = run_cli("approach", "evaluate", "--issue", "big", "--write", timeout=60)
    assert result.returncode == 0, result
    manifest = yaml.safe_load((task_dir / "manifest.yml").read_text(encoding="utf-8"))
    # The four-stage path stores no stage modes (ADR-092 decision 1).
    assert manifest["delivery_approach"] == "delivery", manifest
    assert manifest["evidence_required"] and "stages" not in manifest, manifest
    return manifest


def test_vr_a2_the_evaluator_writes_the_new_words_and_keeps_the_approach(
        project, make_task, run_cli):
    result = _route_8_0_4()
    assert result["delivery_approach"] == "full"
    stages = set(result["stages"].values())
    assert stages <= set(RANKS) | SPECIAL, stages
    assert "thorough" in stages and not stages & OLD_WORDS, stages
    manifest = _path_write(make_task, run_cli)
    # 9.0.0 registers no document (ADR-091), so the manifest holds no depth to check.
    assert "artifacts" not in manifest, manifest.get("artifacts")


def test_vr_a2_a_policy_copy_in_the_old_words_still_writes_the_new_ones(
        project, make_task, run_cli, tmp_path_factory):
    """A project that copied `governance/` before the rename keeps the old
    words in its policy; the result the evaluator gives does not."""
    view = project / "governance" / "routing-policy.yml"
    view.write_text(_old_words(view.read_text(encoding="utf-8")), encoding="utf-8")
    manifest = _path_write(make_task, run_cli)
    assert not {a.get("depth") for a in manifest.get("artifacts") or []} & OLD_WORDS
    # The same respelling of the 8.0.4 copy, read as a project reads its copy.
    import compat_baseline as cb
    from compass_pkg import effective
    root = tmp_path_factory.mktemp("old-words") / "project"
    (root / ".compass" / "work").mkdir(parents=True)
    cb.add_governance_copy(root, source=cb.GOVERNANCE_8_0_4)
    copy = root / "governance" / "routing-policy.yml"
    copy.write_text(_old_words(copy.read_text(encoding="utf-8")), encoding="utf-8")
    assert "full-plus-backfill" in copy.read_text(encoding="utf-8")
    resolution = effective.resolve_live(str(root))
    policy = effective.EffectiveView("live", None, None, resolution.resolved,
                                     resolution.versions).evaluator_policy()
    result = _route_8_0_4(policy)
    assert not set(result["stages"].values()) & OLD_WORDS, result["stages"]
    assert not {a.get("depth") for a in result.get("artifacts") or []} & OLD_WORDS


# --- VR-A3 ---------------------------------------------------------------------

def _cells(html):
    return re.findall(r'<td data-stage="[a-z]+" class="[^"]+">([^<]+)</td>', html)


def test_vr_a3_render_prints_each_stage_weight_in_the_new_words(run_cli):
    result = run_cli("approach", "render", timeout=30)
    assert result.returncode == 0, result
    cells = _cells(result.stdout)
    assert cells, "the table has no stage cells"
    assert not set(cells) & OLD_WORDS, sorted(set(cells) & OLD_WORDS)
    names = re.findall(r'<tr data-approach="([^"]+)">', result.stdout)
    assert names == ["spike", "delivery"], names
    # The 8.0.4 views, read through the renderer, still name every renamed word.
    from compass_pkg.approach_diagram import render
    old = render(yaml.safe_load(_policy_8_0_4_text()), "balanced")
    assert not set(_cells(old)) & OLD_WORDS, sorted(set(_cells(old)) & OLD_WORDS)
    assert {"thorough", "lightweight", "thorough-with-follow-up"} <= set(_cells(old))
    assert re.findall(r'<tr data-approach="([^"]+)">', old) == [
        "spike", "quick-fix", "regular", "hotfix", "full"]
    owed = " ".join(re.findall(r"[a-z-]+ \((?:thorough|lightweight|full|light)\)",
                               result.stdout + old))
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
    for stage, body in _preset("stages.yml", FROZEN)["stages"].items():
        for mode, spec in (body.get("modes") or {}).items():
            if "rank" in (spec or {}):
                ranks.setdefault(mode, set()).add(spec["rank"])
    assert {mode: sorted(r) for mode, r in ranks.items()} == {
        mode: [rank] for mode, rank in RANKS.items() if mode in ranks}
    ordered = sorted(ranks, key=lambda mode: RANKS[mode])
    assert ordered == ["skipped", "collapsed", "lightweight", "thorough",
                       "thorough-with-follow-up"]


def test_vr_a4_the_legacy_adapter_ranks_match_the_preset():
    from compass_pkg import legacy_adapter
    assert legacy_adapter.MODE_RANKS == RANKS


# --- VR-A5 ---------------------------------------------------------------------

def test_vr_a5_the_special_modes_and_the_two_ends_keep_their_names():
    declared = {mode for stage in _preset("stages.yml", FROZEN)["stages"].values()
                for mode in stage.get("modes") or {}}
    assert SPECIAL <= declared, sorted(SPECIAL - declared)
    live = {mode for stage in _preset("stages.yml")["stages"].values()
            for mode in stage.get("modes") or {}}
    assert live <= set(RANKS) | SPECIAL, sorted(live - set(RANKS) - SPECIAL)
    assert {"collapsed", "skipped"} <= declared
    from compass_pkg import stable_ids
    assert stable_ids.ARTIFACT_DEPTHS == ("lightweight", "thorough")


# --- VR-A6 ---------------------------------------------------------------------

def test_vr_a6_the_regenerated_views_hold_no_old_depth_word():
    policy, modes, depths = _view_words()
    words = {word for _, word in modes}
    assert not words & OLD_WORDS, sorted(words & OLD_WORDS)
    assert not {d for _, d in depths} & OLD_WORDS
    assert {"thorough", "lightweight"} <= words
    _, old_modes, _ = _view_words(_policy_8_0_4_text())
    old = {word for _, word in old_modes}
    assert not old & OLD_WORDS, sorted(old & OLD_WORDS)
    assert {"thorough", "lightweight", "thorough-with-follow-up"} <= old
    ranks = policy.get("stage_mode_ranks") or {}
    ranked = {mode for stage in ranks.values() for mode in stage}
    assert not ranked & OLD_WORDS, sorted(ranked & OLD_WORDS)


def test_vr_a6_the_regenerated_views_evaluate_as_before_the_rename():
    """The baseline is the 5.6.0 capture, in the old words; the comparison maps
    its inputs and the evaluator's outputs through the rename table in
    `compat_baseline` (a documented bridge), then compares.

    The views are those of the 8.0.4 governance copy, the last release that routed
    delivery approaches, which were generated in the new words. 9.0.0 replaces the
    live default's approaches (ADR-092), so the live views route no approach to
    compare."""
    import compat_baseline as cb
    header, rows = cb.load_routing()
    grid_rows = [r for r in rows if r["kind"] in ("grid", "archive")]
    # From 7.0.0 the view spells documents and stages as the catalogue does (ADR-070).
    differences = cb.routing_differences(cb.policy_8_0_4(), header, grid_rows, layered=True)
    assert differences == [], "\n".join(differences[:10])
