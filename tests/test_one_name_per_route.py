"""Each route has one name everywhere.

Three routes had two names: the policy keyed them `express`, `standard` and
`expedition` while everything else said `quick-fix`, `feature` and
`initiative`. The split already caused one defect: `compass retro` weighed
every route as 0 until a translation was added. The maintainer chose the
final names on 5 October 2026 - `quick-fix`, `regular`, `full`, `hotfix`
and `spike` - because `feature` is about to be an issue type and
`initiative` a level of work. Every old name is still read, through one
mapping, as backward compatibility within a major version requires.

Scenario ids: RN-1 to RN-7 (issue `one-name-per-route`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import core, policy  # noqa: E402

ROUTES = ("quick-fix", "regular", "full", "hotfix", "spike")
OLD = {"express": "quick-fix", "standard": "regular", "expedition": "full",
       "feature": "regular", "initiative": "full"}


def _policy():
    return yaml.safe_load((ROOT / "governance" / "routing-policy.yml")
                          .read_text(encoding="utf-8"))


def test_rn_1_every_old_name_maps_to_its_new_name():
    for old, new in OLD.items():
        assert core.canonical_shape(old) == new, old
    for name in ROUTES:
        assert core.canonical_shape(name) == name


def test_rn_1_an_old_manifest_reads_as_the_new_route():
    for old, new in OLD.items():
        assert core.normalize_spine({"delivery_approach": old})[
            "delivery_approach"] == new


def test_rn_2_the_policy_keys_and_references_use_the_route_names():
    data = _policy()
    assert tuple(sorted(data["route_shapes"])) == tuple(sorted(ROUTES))
    text = (ROOT / "governance" / "routing-policy.yml").read_text(encoding="utf-8")
    for line in text.splitlines():
        if "force_minimum_route:" in line and not line.lstrip().startswith("#"):
            assert line.split(":", 1)[1].strip() in ROUTES, line


def test_rn_3_every_list_of_routes_matches_route_shapes():
    shapes = set(_policy()["route_shapes"])
    assert set(policy.CHECKPOINT_ROUTES) == shapes
    schema = json.loads((ROOT / "schemas" / "routing-policy.schema.json")
                        .read_text(encoding="utf-8"))
    current = schema["properties"]["route_shapes"]["anyOf"][0]["required"]
    assert set(current) == shapes
    assert set(core.ROUTE_NAMES) == shapes
    manifest = json.loads((ROOT / "schemas" / "manifest.schema.json")
                          .read_text(encoding="utf-8"))
    approach = manifest["properties"]["delivery_approach"]
    named = set()
    for option in approach.get("anyOf", [approach]):
        named |= set(option.get("enum") or [])
    assert shapes <= named


def test_rn_4_an_unknown_delivery_approach_is_reported():
    import jsonschema
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json")
                        .read_text(encoding="utf-8"))
    approach = schema["properties"]["delivery_approach"]
    jsonschema.validate("regular", approach)
    jsonschema.validate(None, approach)
    try:
        jsonschema.validate("fast-track", approach)
    except jsonschema.ValidationError:
        return
    raise AssertionError("delivery_approach accepts a value that is not a route")


def test_rn_5_the_retro_needs_no_translation():
    source = (ROOT / "cli" / "compass_pkg" / "calibration.py").read_text(
        encoding="utf-8")
    assert 'migrate_map_section("values", {})' not in source, (
        "the retro still copies weights from old names to new")


def test_rn_6_the_approach_documents_carry_the_route_names():
    approaches = ROOT / "approaches"
    for name in ("quick-fix", "regular", "full", "hotfix", "spike"):
        assert (approaches / f"{name}.md").is_file(), name
    for gone in ("feature.md", "initiative.md"):
        assert not (approaches / gone).exists(), gone
    import subprocess
    found = subprocess.run(
        ["git", "grep", "-lE", r"approaches/(feature|initiative)\.md"],
        cwd=ROOT, capture_output=True, text=True).stdout.split()
    assert found == [], f"links to an old approach file: {found}"


def test_rn_7_the_routing_decisions_are_recorded():
    decisions = ROOT / "governance" / "decisions"
    text = " ".join(p.read_text(encoding="utf-8")
                    for p in decisions.glob("2026-10-05-*.md")).lower()
    assert "quick-fix" in text and "regular" in text and "full" in text
    assert "routing policy as configuration" in text


# --- an adopter's policy with the old names --------------------------------
# `tests/fixtures/routing-policy-old-route-names.yml` is the shipped policy
# as it was before the rename: keys `express`, `standard`, `expedition`,
# `force_minimum_route: expedition`, checkpoint rows `feature` and
# `initiative`. An adopter who copied it must get the same approaches.

OLD_POLICY = ROOT / "tests" / "fixtures" / "routing-policy-old-route-names.yml"

ASSESSMENTS = [
    {"risk": r, "familiarity": f, "size": s, "goal": "delivery", "role": "engineer",
     **({"labels": labels} if labels else {})}
    for r in ("trivial", "contained", "cross-cutting", "critical")
    for f in ("greenfield", "brownfield-mapped", "brownfield-unmapped")
    for s in ("atomic", "small", "standard", "large", "product")
    for labels in (None, ["auth"])
]


def test_rn_1_an_old_keyed_policy_computes_the_same_approach_and_names_the_old_keys():
    from compass_pkg.routing import evaluate_route
    old = yaml.safe_load(OLD_POLICY.read_text(encoding="utf-8"))
    for autonomy in ("controlled", "balanced", "autonomous"):
        for readings in ASSESSMENTS:
            before = evaluate_route(readings, old, autonomy)
            after = evaluate_route(readings, _policy(), autonomy)
            for key in ("delivery_approach", "stages", "checkpoints"):
                assert before[key] == after[key], (readings, autonomy, key)
    result = evaluate_route(ASSESSMENTS[0], old)
    assert {"express", "standard", "expedition"} <= set(result["renamed_routes"])
    assert evaluate_route(ASSESSMENTS[0], _policy())["renamed_routes"] == []


def test_rn_1_the_cli_warns_about_old_route_names(tmp_path):
    import subprocess
    project = tmp_path / "p"
    (project / "governance").mkdir(parents=True)
    (project / "governance" / "routing-policy.yml").write_text(
        OLD_POLICY.read_text(encoding="utf-8"), encoding="utf-8")
    (project / "governance" / "guardrails.yml").write_text(
        (ROOT / "governance" / "guardrails.yml").read_text(encoding="utf-8"),
        encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    run = subprocess.run(
        [sys.executable, str(ROOT / "cli" / "compass"), "approach", "evaluate",
         "--assessment", "risk=contained", "--assessment", "size=standard",
         "--assessment", "familiarity=brownfield-mapped",
         "--assessment", "goal=delivery", "--assessment", "role=engineer"],
        cwd=project, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    warning = run.stdout + run.stderr
    assert "expedition" in warning and "full" in warning, warning


def test_rn_3_a_route_named_twice_is_refused_by_the_evaluator():
    import copy
    import pytest
    from compass_pkg.core import CompassError
    from compass_pkg.routing import evaluate_route
    old = yaml.safe_load(OLD_POLICY.read_text(encoding="utf-8"))
    twice = copy.deepcopy(old)
    twice["autonomy_checkpoints"]["balanced"]["standard"] = []
    with pytest.raises(CompassError, match="twice"):
        evaluate_route(ASSESSMENTS[0], twice)


def test_rn_4_issue_lint_reports_an_unknown_approach_without_jsonschema(tmp_path):
    from compass_pkg import policy as policy_mod
    errors = policy_mod.delivery_approach_errors({"delivery_approach": "fast-track"})
    assert errors and "fast-track" in errors[0]
    for name in ROUTES + tuple(OLD) + (None,):
        assert policy_mod.delivery_approach_errors({"delivery_approach": name}) == []


def test_rn_6_the_review_page_shows_the_current_name(tmp_path):
    from compass_pkg import dashboard
    task_dir = tmp_path / "work" / "demo"
    task_dir.mkdir(parents=True)
    (task_dir / "manifest.yml").write_text(
        "issue: demo\ndelivery_approach: feature\n", encoding="utf-8")
    assert dashboard._spine(str(task_dir))["delivery_approach"] == "regular"


def test_rn_6_the_settings_reference_names_the_current_approaches():
    # The autonomy values are described in the settings reference since
    # `compass init` stopped writing a commented settings file.
    doc = (ROOT / "docs" / "configuration.md").read_text(encoding="utf-8")
    block = doc[doc.index("### `autonomy`"):doc.index("### `project`")]
    assert "regular" in block and "quick fix" in block, block
    assert "feature" not in block and "initiative" not in block, block
