# compass_pkg.path_stages - which stages an issue has, and the v1 rename guard
"""Read an issue's stages on the four-stage path or on the legacy stages.

A path issue (ADR-092) runs assess, specify, build and ship, fixed in
`stable_ids.PATH_STAGE_IDS`, and records `evidence_required` instead of a
`stages:` map. An issue assessed before that keeps its `stages:` map and its
delivery approach, and each legacy stage shows as a path stage through
`stable_ids.LEGACY_TO_PATH`.

`specify` and `build` are also v1 stage names, which `cli/migrate-map.yml`
maps to `define` and `implement`. Applied to every record, that rename would
turn a path stage into a legacy one on load. `rename_v1_stage_keys` applies it
only to a v1 record: one that holds a v1-only stage name, or one the caller
knows is v1 because it uses a v1 key (`phases:`, or a friction entry's
`phase`). An 8.x record holds no v1 name, so it reads as before.

The rename table is a parameter, not read here, so this module names no
retired spelling and imports nothing that reads `cli/migrate-map.yml`.
"""
# DEPENDENCY: compass_pkg.stable_ids only, so `core` and `word_map` can both
# import it without a cycle.
from __future__ import annotations

from compass_pkg.stable_ids import (APPROACH_SPIKE, LEGACY_STAGE_IDS, LEGACY_TO_PATH,
                                    PATH_STAGE_IDS, SPIKE_STAGE_IDS)


def is_path_issue(task):
    """True when the manifest was written for the four-stage path."""
    return isinstance(task, dict) and "evidence_required" in task


def stages_of(task):
    """The stage ids of an issue, in order.

    A path issue has the path stages, or the spike's three. A legacy issue has
    the stages its `stages:` map names, in the legacy order, or all eight
    legacy stages when it has no map. The modes in the map are not judged here.
    """
    if is_path_issue(task):
        if task.get("delivery_approach") == APPROACH_SPIKE:
            return SPIKE_STAGE_IDS
        return PATH_STAGE_IDS
    stages = task.get("stages") if isinstance(task, dict) else None
    if not isinstance(stages, dict) or not stages:
        return LEGACY_STAGE_IDS
    known = tuple(s for s in LEGACY_STAGE_IDS if s in stages)
    return known + tuple(s for s in stages if s not in LEGACY_STAGE_IDS)


def path_stage_of(stage):
    """The path stage that shows `stage`, or None for a name that is no stage."""
    if stage in PATH_STAGE_IDS:
        return stage
    return LEGACY_TO_PATH.get(stage)


def _v1_only(renames):
    # The v1 names that are not also path stage names. Only these prove that a
    # record is v1; `specify` and `build` alone do not.
    return {name for name in renames if name not in PATH_STAGE_IDS}


def rename_v1_stage(name, renames, v1=False):
    """One stage name, renamed when it is v1-only or when the caller knows the
    record is v1 (`v1=True`). Any other name comes back unchanged."""
    if not isinstance(name, str) or name not in renames:
        return name
    if v1 or name in _v1_only(renames):
        return renames[name]
    return name


def rename_v1_stage_keys(stages, renames, v1=False):
    """A stage map (or a list of stage names) with the v1 names renamed, but
    only when it is a v1 record.

    It is v1 when `v1` is True or when it holds a v1-only name. A map keeps
    the value of a current key over the value of the v1 key that renames onto
    it. A list keeps its order.
    """
    names = list(stages)
    is_v1 = v1 or any(isinstance(n, str) and n in _v1_only(renames) for n in names)
    if isinstance(stages, dict):
        if not is_v1:
            return dict(stages)
        mapped = {}
        for key, value in stages.items():
            new = renames.get(key, key)
            if new in mapped and key in renames:
                continue
            mapped[new] = value
        return mapped
    return [rename_v1_stage(n, renames, v1=is_v1) for n in names]
