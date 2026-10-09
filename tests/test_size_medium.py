"""The size `standard` is now `medium` (issue `vocabulary-and-cli-renames`,
group B).

`standard` retires as a size only. It is still the retired name of the
`regular` delivery approach (`delivery_approach: standard`), and that row is
not a size. Every writer emits `medium`; the readers accept both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

SIZES = ["atomic", "small", "medium", "large", "product"]
ASSESS = ("--assessment", "risk=contained", "--assessment", "familiarity=brownfield-mapped")


# --- VR-B1 ---------------------------------------------------------------------

def test_vr_b1_the_size_dimension_lists_medium_and_not_standard():
    dimensions = yaml.safe_load((ROOT / "governance" / "presets" / "default"
                                 / "dimensions.yml").read_text(encoding="utf-8"))
    assert dimensions["dimensions"]["size"]["values"] == SIZES
    view = yaml.safe_load((ROOT / "governance" / "routing-policy.yml")
                          .read_text(encoding="utf-8"))
    assert view["assessment_vocabulary"]["size"] == SIZES


def test_vr_b1_the_shipped_order_of_sizes_says_medium():
    from compass_pkg import catalogue_spec
    assert catalogue_spec.SHIPPED_ORDERS["size"] == tuple(SIZES)


def test_vr_b1_the_manifest_schema_offers_medium_as_a_size():
    schema = json.loads((ROOT / "schemas" / "manifest.schema.json")
                        .read_text(encoding="utf-8"))
    sizes = schema["properties"]["assessment"]["properties"]["size"]["enum"]
    assert sizes == SIZES, sizes


# --- VR-B2 ---------------------------------------------------------------------

def test_vr_b2_every_baseline_assessment_of_size_standard_routes_alike_as_medium():
    import compat_baseline as cb
    header, rows = cb.load_routing()
    wanted = [r for r in rows if r["kind"] in ("grid", "archive")
              and r["assessment"].get("size") == "standard"]
    assert len(wanted) > 200, f"only {len(wanted)} baseline rows have size standard"
    policy = cb.shipped_policy()
    wrong = []
    for row in wanted:
        medium = dict(row["assessment"], size="medium")
        now = cb.compact(medium, policy)
        if now != row["result"]:
            wrong.append(f"{medium}: {cb._first_difference(row['result'], now)}")
    assert wrong == [], "\n".join(wrong[:10])


# --- VR-B3 ---------------------------------------------------------------------

def test_vr_b3_the_retired_approach_name_standard_is_not_turned_into_a_size(tmp_path):
    from compass_pkg import core
    (tmp_path / "manifest.yml").write_text(yaml.safe_dump({
        "schema_version": "2.0", "task": "t", "delivery_approach": "standard",
        "assessment": {"risk": "contained", "familiarity": "greenfield",
                       "size": "standard"},
        "stages": {"define": "full"}}), encoding="utf-8")
    task, _ = core.load_manifest(str(tmp_path))
    assert task["delivery_approach"] == "regular", task["delivery_approach"]
    assert task["assessment"]["size"] == "medium"
    assert task["stages"] == {"define": "thorough"}


# --- VR-B4 ---------------------------------------------------------------------

def _evaluate(run_cli, size):
    return run_cli("approach", "evaluate", *ASSESS, "--assessment", f"size={size}",
                   "--json", timeout=60)


def test_vr_b4_size_standard_on_the_command_line_equals_medium_and_says_so(run_cli):
    medium = _evaluate(run_cli, "medium")
    assert medium.returncode == 0, medium
    standard = _evaluate(run_cli, "standard")
    assert standard.returncode == 0, standard
    assert json.loads(standard.stdout) == json.loads(medium.stdout)
    assert "size standard is now medium" in standard.stderr, standard.stderr
    assert medium.stderr == "", "the new word needs no notice"
    assert "is now medium" not in standard.stdout, "the notice is on standard error only"
