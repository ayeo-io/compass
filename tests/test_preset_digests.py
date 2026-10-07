"""The default preset's digests are pinned.

`tests/fixtures/preset-digests.yml` holds a digest for each file of
`governance/presets/default/` and one for the whole preset. A digest is over
the parsed content, so a comment or a layout change does not move it and a
changed value does. A preset file that changes without its pinned digest
moving fails here, naming the digest file and the command that pins again.

Scenario id: `GV-4` (issue `generated-legacy-views`).
"""
from __future__ import annotations

import importlib
import importlib.util
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

DIGEST_FILE = "tests/fixtures/preset-digests.yml"
PIN_COMMAND = "python3 scripts/generate-legacy-views.py --pin"


def _views():
    assert importlib.util.find_spec("compass_pkg.legacy_views"), \
        "cli/compass_pkg/legacy_views.py is missing"
    views = importlib.import_module("compass_pkg.legacy_views")
    assert hasattr(views, "digest_problems"), \
        "legacy_views.py has no digest_problems: the preset digests are not pinned"
    return views


def _root_copy(tmp_path) -> Path:
    shutil.copytree(ROOT / "governance" / "presets", tmp_path / "governance" / "presets")
    (tmp_path / "tests" / "fixtures").mkdir(parents=True)
    shutil.copy(ROOT / DIGEST_FILE, tmp_path / DIGEST_FILE)
    return tmp_path


def _edit(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {path.name}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _plant_rationale(path: Path, text: str = "A planted rationale.") -> str:
    """Set the first `rationale` in a preset file to `text`, whatever it was,
    so a test does not depend on one rule's wording."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))

    def walk(node):
        if isinstance(node, dict):
            if "rationale" in node:
                node["rationale"] = text
                return True
            return any(walk(v) for v in node.values())
        return False

    assert walk(doc), f"{path.name} holds no rationale"
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return text


def test_gv_4_the_preset_matches_its_pinned_digests():
    assert (ROOT / DIGEST_FILE).is_file(), f"{DIGEST_FILE} is missing"
    problems = _views().digest_problems(ROOT)
    assert problems == [], "\n".join(problems)


def test_gv_4_a_changed_preset_file_fails_naming_the_digest_file(tmp_path):
    views = _views()
    root = _root_copy(tmp_path)
    assert views.digest_problems(root) == []
    _plant_rationale(root / "governance/presets/default/rules.yml")
    problems = views.digest_problems(root)
    assert any("rules.yml" in p for p in problems), problems
    assert all(DIGEST_FILE in p and PIN_COMMAND in p for p in problems), problems
    assert not any("gates.yml" in p for p in problems), problems
    # The whole-preset digest moves with it.
    assert any("whole preset" in p for p in problems), problems


def test_gv_4_a_comment_does_not_move_a_digest(tmp_path):
    views = _views()
    root = _root_copy(tmp_path)
    path = root / "governance/presets/default/rules.yml"
    path.write_text("# a note that changes no value\n" + path.read_text(encoding="utf-8"),
                    encoding="utf-8")
    assert views.digest_problems(root) == []


def test_gv_4_an_added_or_removed_preset_file_fails(tmp_path):
    views = _views()
    root = _root_copy(tmp_path)
    (root / "governance/presets/default/extra.yml").write_text("schema: 1\n", encoding="utf-8")
    assert any("extra.yml" in p for p in views.digest_problems(root))
    (root / "governance/presets/default/extra.yml").unlink()
    (root / "governance/presets/default/vocabulary.yml").unlink()
    assert any("vocabulary.yml" in p for p in views.digest_problems(root))


def test_gv_4_pinning_again_clears_the_failure(tmp_path):
    views = _views()
    root = _root_copy(tmp_path)
    _plant_rationale(root / "governance/presets/default/rules.yml")
    assert views.digest_problems(root)
    views.pin_digests(root)
    assert views.digest_problems(root) == []


def test_gv_4_pinning_again_keeps_the_pins_of_earlier_versions(tmp_path):
    """The stability rule for released versions needs each version's digest to
    check against, so a re-pin adds or updates the current entry only."""
    views = _views()
    root = _root_copy(tmp_path)
    path = root / DIGEST_FILE
    pins = yaml.safe_load(path.read_text(encoding="utf-8"))
    (current,) = pins
    earlier = {"preset": "sha256:" + "1" * 64, "files": {"rules.yml": "sha256:" + "2" * 64}}
    pins["default@5.9.0"] = earlier
    path.write_text(yaml.safe_dump(pins), encoding="utf-8")
    _plant_rationale(root / "governance/presets/default/rules.yml")
    assert views.digest_problems(root)
    views.pin_digests(root)
    after = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert after["default@5.9.0"] == earlier
    assert after[current] != pins[current]
    assert views.digest_problems(root) == []


def test_gv_4_pinning_the_content_hashes_writes_what_the_drift_test_reads(tmp_path):
    """The drift test pins each view's content to its version. The script
    writes that fixture, so an editor is not sent to a generated file."""
    views = _views()
    assert hasattr(views, "pin_content_hashes"), \
        "legacy_views.py cannot write the content-hash fixture"
    import json
    sys.path.insert(0, str(ROOT / "tests"))
    import test_governance_drift as drift
    root = tmp_path
    (root / "governance").mkdir()
    (root / "tests" / "fixtures").mkdir(parents=True)
    for name in ("routing-policy.yml", "guardrails.yml"):
        shutil.copy(ROOT / "governance" / name, root / "governance" / name)
    path = views.pin_content_hashes(root)
    written = json.loads((root / path).read_text(encoding="utf-8"))
    committed = json.loads((ROOT / "tests/fixtures/governance-content-hashes.json")
                           .read_text(encoding="utf-8"))
    assert written == committed
    for name, entry in written.items():
        assert entry["sha256"] == drift.content_hash(root / "governance" / name)
