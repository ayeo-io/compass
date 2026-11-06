"""The README's animated explainer is drawn from the shipped policy.

`scripts/render-explainer.py` runs each example assessment through
`evidence_required.evaluate` and draws the evidence the policy returns. The committed
`assets/compass-explainer.svg` must be what the script writes, so the README
cannot disagree with `governance/routing-policy.yml`.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "render-explainer.py"
COMMITTED = ROOT / "assets" / "compass-explainer.svg"


def _load():
    spec = importlib.util.spec_from_file_location("render_explainer", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fresh():
    return subprocess.run([sys.executable, str(SCRIPT), "--out", "/dev/stdout"],
                          capture_output=True, text=True, timeout=60, check=True).stdout


def test_the_committed_explainer_is_what_the_script_writes():
    assert COMMITTED.is_file(), "assets/compass-explainer.svg is missing"
    check = subprocess.run([sys.executable, str(SCRIPT), "--check"],
                           capture_output=True, text=True, timeout=60)
    assert check.returncode == 0, (
        "assets/compass-explainer.svg is stale: run scripts/render-explainer.py\n"
        + check.stderr)


def test_two_renders_write_the_same_bytes():
    module = _load()
    policy = module.load_yaml(module.POLICY)
    assert module.render(policy) == module.render(policy)


def test_each_scene_draws_the_evidence_the_policy_computes():
    import sys
    sys.path.insert(0, str(ROOT / "cli"))
    from compass_pkg import evidence_required
    from compass_pkg.stable_ids import PATH_STAGE_IDS
    module = _load()
    policy = module.load_yaml(module.POLICY)
    computed = module.scenes(policy)
    svg = module.render(policy)
    # The three example assessments land on three different evidence rows, so
    # the picture shows the evidence changing, not one row three times.
    rows = [s["row"] for s in computed]
    assert len(set(rows)) == len(rows), rows
    for scene, (_, assessment) in zip(computed, module.SCENES):
        fresh = evidence_required.evaluate(dict(assessment), policy)
        assert scene["row"] == fresh["rules_fired"][0]
        assert scene["evidence"] == fresh["evidence_required"]
        # Each owed token is drawn at one stage, so the bars add up to it.
        assert sum(scene["items"].values()) == len(scene["evidence"]) + 1
        assert scene["label"] in svg
        assert str(len(scene["evidence"])) in scene["label"]
        assert scene["caption"] in svg
    # One bar per stage of the path, each with its height animated.
    assert module.STAGE_IDS == PATH_STAGE_IDS
    assert svg.count('<rect x=') == len(PATH_STAGE_IDS)
    assert svg.count('attributeName="height"') == len(PATH_STAGE_IDS)


def test_the_explainer_holds_no_script_and_names_its_source():
    text = COMMITTED.read_text(encoding="utf-8")
    assert "<script" not in text
    assert "scripts/render-explainer.py" in text
    assert "governance/routing-policy.yml" in text
    # Every animation loops, so a reader who arrives late still sees all three.
    assert re.search(r'repeatCount="indefinite"', text)


def test_the_readme_embeds_the_explainer_through_an_img_tag():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'src="assets/compass-explainer.svg"' in readme
    assert "<svg" not in readme, "GitHub strips inline SVG; the README must use <img>"
