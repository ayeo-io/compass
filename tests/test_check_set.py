"""The fixed check set: its file, its pinned digest and its parity with the default.

`governance/check-set.yml` holds every check, gate and evidence type Compass
runs (ADR-094). `cli/compass_pkg/check_set.py` reads it and returns it in the
shape `generations/<n>/resolved.yml` holds.

While `governance/presets/default/` exists, the tests here compare the two
sources. The check set resolves to the configuration the 8.x resolver gave the
default preset for a project with no `compass.yml`, with one difference: the set holds
no `locked:` field, because no layer sits above it. Every accessor of
`EffectiveView` that `compass check` and assess read gives the same answer on
both, and so does `evidence_required.evaluate` on every point of the contract 1
grid under every subset of the `G5` labels.

`tests/fixtures/check-set-digests.yml` pins the file's sha256 for each version.
It is not an owner pin: the change that edits the file raises `version` and
pins the new digest in the same commit.
"""
from __future__ import annotations

import copy
import re
import shutil
from pathlib import Path

import pytest
import yaml

import compat_baseline as cb
from compass_pkg import catalogue_check, check_set, effective
from compass_pkg import evidence_required as er
from compass_pkg.core import CompassError
from compass_pkg.routing import RoutingConflict

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "tests" / "fixtures" / "check-set-digests.yml"
PRESET = ROOT / "governance" / "presets" / "default"


def _pins():
    return yaml.safe_load(PINS.read_text(encoding="utf-8"))


def _pin_problem(file, pins):
    """Why the file's bytes do not match the pin for its version, or None."""
    ref = check_set.ref(check_set.load(str(file)))
    if ref not in pins:
        return f"{PINS.name} has no digest for {ref}"
    got = check_set.sha256(str(file))
    if pins[ref] != got:
        return (f"governance/check-set.yml changed, but {PINS.name} still pins {ref} at "
                f"{pins[ref]}; the file is now {got}. Raise `version` and pin the new digest")
    return None


def _without_locked(node):
    if isinstance(node, dict):
        return {k: _without_locked(v) for k, v in node.items() if k != "locked"}
    if isinstance(node, list):
        return [_without_locked(v) for v in node]
    return node


def _view(resolved):
    return effective.EffectiveView("live", None, None, resolved, {}, {})


def _preset_resolved():
    """The default preset resolved alone, as 8.x `resolve_live` gave it for a
    project with no `compass.yml` and no copy of the governance files: the
    preset's catalogues merged as one parent layer, its capabilities, and its
    evidence types. Since #357 step 7 the resolver reads the check set, so the
    preset is resolved here, through the 8.x merge, for as long as it exists."""
    from compass_pkg import catalogue_spec, layers, merge, policy_lint
    parent, _ = policy_lint.load_parent()
    config = merge.resolve(layers.build_chain(parent))[0]
    evidence = yaml.safe_load((PRESET / "evidence-types.yml").read_text(encoding="utf-8"))
    return {
        "capabilities": dict(parent.doc.get("capabilities") or {}),
        "approach": None,
        "autonomy": "balanced",
        "conformance": {"status": "conformant", "unlocked": []},
        **{name: config[name] for name in catalogue_spec.CATALOGUES if name in config},
        "evidence_types": evidence["evidence_types"],
    }


@pytest.fixture(scope="module")
def live():
    """The default preset as the 8.x resolver gave it for a project with no
    `compass.yml` and no copy of the governance files."""
    return _preset_resolved()


def test_the_resolver_reads_the_check_set(tmp_path):
    """A project with no `compass.yml` resolves to the check set itself."""
    assert effective.resolve_live(str(tmp_path)).resolved == check_set.resolved()


@pytest.fixture(scope="module")
def checks():
    return check_set.resolved()


# --- the file and its digest ------------------------------------------------------

def test_the_set_is_named_by_one_id_and_version():
    assert check_set.ref() == "compass-checks@9.0.0"


def test_the_digest_is_the_sha256sum_of_the_file():
    import hashlib
    want = hashlib.sha256((ROOT / check_set.PATH).read_bytes()).hexdigest()
    assert check_set.sha256() == want
    assert re.fullmatch(r"[0-9a-f]{64}", want)


def test_the_file_bytes_are_pinned_for_its_version():
    assert _pin_problem(ROOT / check_set.PATH, _pins()) is None


def test_a_changed_byte_without_a_new_pin_fails(tmp_path):
    copy_ = tmp_path / "check-set.yml"
    shutil.copy(ROOT / check_set.PATH, copy_)
    copy_.write_text(copy_.read_text(encoding="utf-8") + "\n# one more line\n",
                     encoding="utf-8")
    problem = _pin_problem(copy_, _pins())
    assert problem and "Raise `version`" in problem


def test_a_new_version_without_a_pin_fails(tmp_path):
    copy_ = tmp_path / "check-set.yml"
    text = (ROOT / check_set.PATH).read_text(encoding="utf-8")
    copy_.write_text(text.replace("version: 9.0.0", "version: 9.1.0", 1), encoding="utf-8")
    assert _pin_problem(copy_, _pins()) == f"{PINS.name} has no digest for compass-checks@9.1.0"


# --- the shape ----------------------------------------------------------------------

def test_the_catalogues_are_well_formed_as_the_shipped_parent_was(checks):
    doc = {"schema": 1, "capabilities": checks["capabilities"],
           **{name: checks[name] for name in check_set.CATALOGUES + ("vocabulary",)}}
    assert catalogue_check.check_layer(doc, "parent") == []


@pytest.mark.parametrize("change, message", [
    (lambda d: d["gates"]["G1"].__setitem__("locked", True), "gates.G1 holds 'locked'"),
    (lambda d: d.__setitem__("artifacts", {}), "unknown key 'artifacts'"),
    (lambda d: d.pop("evidence_types"), "missing key 'evidence_types'"),
    (lambda d: d.__setitem__("id", "default"), "id must be 'compass-checks'"),
    (lambda d: d["never_waived"].append("gates.G9"), "never_waived names 'gates.G9'"),
    (lambda d: d["optional"].__setitem__("rules", {}), "optional entry 'rules'"),
])
def test_a_file_of_the_wrong_shape_is_refused(tmp_path, change, message):
    doc = check_set.load()
    change(doc)
    file = tmp_path / "check-set.yml"
    file.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(CompassError, match=re.escape(message)):
        check_set.load(str(file))


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(CompassError, match="is missing"):
        check_set.load(str(tmp_path / "check-set.yml"))


def test_never_waived_is_the_hard_lock_of_the_default():
    preset = yaml.safe_load((PRESET / "preset.yml").read_text(encoding="utf-8"))
    assert check_set.load()["never_waived"] == preset["locks"]["hard"]


def test_the_optional_agent_review_is_the_block_the_guide_gives_and_does_not_run(checks):
    """ADR-090 decision 7: the shipped set runs no judged check. The block a project
    turned the agent review on with is held under `optional`, for the
    `agent_review` setting, and `resolved` leaves it out."""
    text = (ROOT / "docs" / "judged-checks.md").read_text(encoding="utf-8")
    section = text.split("## An agent review", 1)[1]
    block = yaml.safe_load(section.split("```yaml", 1)[1].split("```", 1)[0])
    held = check_set.load()["optional"]["agent_review"]
    assert held["checks"] == block["checks"]
    assert held["stages"]["ship"]["entry"] == block["stages"]["ship"]["set"]["entry"]["add"]
    assert "agent-review" not in checks["checks"]
    assert not any(c.get("kind") == "judged" for c in checks["checks"].values())
    assert "entry" not in checks["stages"]["ship"]


def test_resolved_is_a_copy(checks):
    first = check_set.resolved()
    first["gates"].clear()
    assert check_set.resolved()["gates"] == checks["gates"]


# --- parity with the live default ---------------------------------------------------

def test_the_set_resolves_to_the_live_default_less_its_locks(live, checks):
    """The resolved mapping equals the live default's, key by key, once the
    `locked:` fields are taken out. The live default declares the two empty
    catalogues `artifacts` and `readiness`; the merge leaves both out, so neither
    is in either mapping."""
    assert set(checks) == set(live)
    assert "artifacts" not in live and "readiness" not in live
    differ = [key for key in live if _without_locked(live[key]) != checks[key]]
    assert differ == []


def test_the_only_difference_is_the_locked_field_of_checks_and_gates(live, checks):
    """So nothing else moves: the paths that hold `locked` in the live default are
    exactly the checks and gates the preset locks, and the set holds none."""
    def paths(node, where=""):
        if isinstance(node, dict):
            found = [where] if "locked" in node else []
            for key, value in node.items():
                found += paths(value, f"{where}.{key}" if where else key)
            return found
        return []
    held = paths(live)
    assert held and all(p.split(".", 1)[0] in ("checks", "gates") for p in held)
    preset = yaml.safe_load((PRESET / "preset.yml").read_text(encoding="utf-8"))["locks"]
    assert set(held) == set(preset["hard"]) | {
        p for p in preset["locked"] if p.split(".", 1)[0] in ("checks", "gates")}
    assert paths(checks) == []


@pytest.mark.parametrize("accessor", [
    "guardrail_gates", "evaluator_policy", "gate_requirements", "command_checks",
    "stage_order", "known_ids", "loop_ceiling_rules"])
def test_every_accessor_compass_check_and_assess_read_is_equal(live, checks, accessor):
    assert getattr(_view(checks), accessor)() == getattr(_view(live), accessor)()


def test_the_gates_checks_and_evidence_types_are_the_live_defaults(live, checks):
    assert checks["gates"] == _without_locked(live["gates"])
    assert checks["checks"] == _without_locked(live["checks"])
    assert checks["evidence_types"] == live["evidence_types"]
    assert (len(checks["gates"]), len(checks["checks"]), len(checks["evidence_types"])) == \
        (16, 32, 16)


def _owed(readings, policy):
    try:
        return er.evaluate(copy.deepcopy(readings), policy)
    except RoutingConflict:
        return "refused"


def test_the_evidence_rows_are_equal_on_every_grid_point(live, checks):
    """Every row of the contract 1 grid (1,200 assessments) under every subset of
    the four `G5` labels (16): 19,200 points. On each, `evidence_required.evaluate`
    gives the same result, refusals included, under the set and the live default."""
    header, rows = cb.load_routing()
    grid = [row["assessment"] for row in rows if row["kind"] == "grid"]
    subsets = list(cb.label_subsets(header["labels"]))
    ours, theirs = _view(checks).evaluator_policy(), _view(live).evaluator_policy()
    differ, points = [], 0
    for assessment in grid:
        readings = {k: v for k, v in assessment.items() if k != "role"}
        readings["size"] = cb.SIZE_NOW.get(readings["size"], readings["size"])
        for labels in subsets:
            readings["labels"] = labels
            points += 1
            if _owed(readings, ours) != _owed(readings, theirs):
                differ.append(dict(readings))
    assert points == 19200
    assert differ == [], f"{len(differ)} of {points} points differ: {differ[:5]}"
