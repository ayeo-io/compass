"""The four-stage path ids, and the v1 rename that must not reach them (#351).

A new issue runs assess, specify, build and ship. `specify` and `build` are
also v1 stage names, which `cli/migrate-map.yml` maps to `define` and
`implement`. The rename must apply only to a v1 record:

- a `stages:` map that holds a v1-only name (`frame`, `clarify`,
  `distribute` or `land`), or a map under the v1 key `phases:`;
- a friction entry that uses the v1 key `phase`.

An 8.x map holds no v1 name, so it reads exactly as before.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import stable_ids  # noqa: E402
from compass_pkg.core import normalize_spine, shape_stages  # noqa: E402
from compass_pkg.word_map import FALLBACK, map_manifest  # noqa: E402

PATH_MAP = {"assess": "thorough", "specify": "thorough", "build": "thorough",
            "ship": "thorough"}
EIGHT_X_MAP = {"assess": "thorough", "define": "thorough", "refine": "lightweight",
               "plan": "thorough", "breakdown": "skipped", "implement": "thorough",
               "verify": "thorough", "ship": "thorough"}


def test_the_path_ids_and_the_legacy_ids():
    assert stable_ids.PATH_STAGE_IDS == ("assess", "specify", "build", "ship")
    assert stable_ids.SPIKE_STAGE_IDS == ("assess", "build", "ship")
    assert stable_ids.APPROACH_DELIVERY == "delivery"
    assert stable_ids.LEGACY_STAGE_IDS == stable_ids.STAGE_IDS
    assert stable_ids.LEGACY_TO_PATH == {
        "assess": "assess", "define": "specify", "refine": "specify",
        "plan": "specify", "breakdown": "build", "implement": "build",
        "verify": "ship", "ship": "ship"}
    assert set(stable_ids.LEGACY_TO_PATH) == set(stable_ids.LEGACY_STAGE_IDS)
    assert set(stable_ids.LEGACY_TO_PATH.values()) == set(stable_ids.PATH_STAGE_IDS)


def test_a_path_stages_map_keeps_specify_and_build():
    out = normalize_spine({"stages": dict(PATH_MAP)})
    assert out["stages"] == PATH_MAP


def test_a_v1_map_still_maps_specify_and_build():
    out = normalize_spine({"stages": {"frame": "full", "specify": "full",
                                      "build": "light", "land": "full"}})
    assert out["stages"] == {"assess": "thorough", "define": "thorough",
                             "implement": "lightweight", "ship": "thorough"}


def test_a_v1_phases_map_maps_specify_and_build_without_a_v1_only_name():
    # The `phases:` key itself is the v1 spelling of `stages:`.
    out = normalize_spine({"phases": {"specify": "full", "build": "full"}})
    assert out["stages"] == {"define": "thorough", "implement": "thorough"}


def test_an_8x_map_reads_as_before():
    out = normalize_spine({"stages": dict(EIGHT_X_MAP)})
    assert out["stages"] == EIGHT_X_MAP


def test_a_friction_stage_build_stays_build():
    out = normalize_spine({"friction": [{"stage": "build", "category": "over-weight"}]})
    assert out["friction"][0]["stage"] == "build"


def test_a_friction_phase_build_maps_to_implement():
    out = normalize_spine({"friction": [{"phase": "build", "category": "over-weight"}]})
    assert out["friction"][0]["stage"] == "implement"
    assert "phase" not in out["friction"][0]


def test_a_friction_stage_with_a_v1_only_name_still_maps():
    out = normalize_spine({"friction": [{"stage": "land"}]})
    assert out["friction"][0]["stage"] == "ship"


def test_word_map_friction_maps_only_the_v1_key():
    manifest = {"friction": [{"phase": "build"}, {"stage": "build"}]}
    map_manifest(manifest, FALLBACK)
    assert manifest["friction"] == [{"stage": "implement"}, {"stage": "build"}]


def test_shape_stages_keeps_a_path_map_and_maps_a_v1_map():
    assert shape_stages({"stages": dict(PATH_MAP)}) == PATH_MAP
    assert shape_stages({"stages": {"frame": "full", "build": "full"}}) == {
        "assess": "full", "implement": "full"}
    assert shape_stages({"phases": {"build": "full"}}) == {"implement": "full"}
    assert shape_stages({"stages": dict(EIGHT_X_MAP)}) == EIGHT_X_MAP


def test_rename_v1_stage_keys_on_a_list_of_names():
    from compass_pkg import path_stages

    renames = {"frame": "assess", "specify": "define", "build": "implement",
               "land": "ship"}
    assert path_stages.rename_v1_stage_keys(["build", "ship"], renames) == ["build", "ship"]
    assert path_stages.rename_v1_stage_keys(["build", "land"], renames) == [
        "implement", "ship"]
    assert path_stages.rename_v1_stage_keys(["build"], renames, v1=True) == ["implement"]


def test_is_path_issue():
    from compass_pkg import path_stages

    assert path_stages.is_path_issue({"evidence_required": ["scenarios"]})
    assert not path_stages.is_path_issue({"stages": dict(EIGHT_X_MAP)})
    assert not path_stages.is_path_issue(None)


def test_stages_of():
    from compass_pkg import path_stages

    assert path_stages.stages_of({"delivery_approach": "delivery",
                                  "evidence_required": ["scenarios"]}) == \
        stable_ids.PATH_STAGE_IDS
    assert path_stages.stages_of({"delivery_approach": "spike",
                                  "evidence_required": []}) == stable_ids.SPIKE_STAGE_IDS
    legacy = {"delivery_approach": "regular",
              "stages": {"ship": "thorough", "assess": "thorough",
                         "implement": "thorough"}}
    assert path_stages.stages_of(legacy) == ("assess", "implement", "ship")
    assert path_stages.stages_of({"delivery_approach": "regular"}) == \
        stable_ids.LEGACY_STAGE_IDS


def test_path_stage_of():
    from compass_pkg import path_stages

    for legacy, path in stable_ids.LEGACY_TO_PATH.items():
        assert path_stages.path_stage_of(legacy) == path
    for stage in stable_ids.PATH_STAGE_IDS:
        assert path_stages.path_stage_of(stage) == stage
    assert path_stages.path_stage_of("not-a-stage") is None
