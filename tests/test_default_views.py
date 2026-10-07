"""The two legacy policy files are generated views of the default preset.

`governance/routing-policy.yml` and `governance/guardrails.yml` are written by
`scripts/generate-legacy-views.py` from the preset in
`governance/presets/default/`, the sidecar `governance/legacy-views.yml` and a
template the generator owns. These tests compare each view with the generator's
output byte for byte, so a hand edit of a view, or a preset change with no
regeneration, fails and names the command that fixes it.

Scenario ids: `GV-1` to `GV-5` (issue `generated-legacy-views`).
"""
from __future__ import annotations

import importlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

COMMAND = "python3 scripts/generate-legacy-views.py"
SCRIPT = ROOT / "scripts" / "generate-legacy-views.py"
VIEWS = ("governance/routing-policy.yml", "governance/guardrails.yml")


def _views_module():
    assert importlib.util.find_spec("compass_pkg.legacy_views"), \
        "cli/compass_pkg/legacy_views.py is missing"
    return importlib.import_module("compass_pkg.legacy_views")


def _root_copy(tmp_path) -> Path:
    """A root holding only what the generator reads and writes."""
    gov = tmp_path / "governance"
    gov.mkdir(parents=True)
    shutil.copytree(ROOT / "governance" / "presets", gov / "presets")
    for name in ("legacy-views.yml", *(Path(v).name for v in VIEWS)):
        shutil.copy(ROOT / "governance" / name, gov / name)
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


# --- the committed views are the generated text (`GV-1`) ------------------------

def test_gv_1_the_committed_views_equal_the_generated_text():
    views = _views_module()
    generated = views.generate(ROOT)
    assert set(generated) == set(VIEWS)
    for rel in VIEWS:
        committed = (ROOT / rel).read_text(encoding="utf-8")
        assert generated[rel] == committed, (
            f"{rel} is not what the generator writes; regenerate it with: {COMMAND}")
    assert views.stale_views(ROOT) == []


def test_gv_1_a_stale_view_fails_naming_the_command(tmp_path):
    views = _views_module()
    root = _root_copy(tmp_path)
    assert views.stale_views(root) == []
    _edit(root / VIEWS[0], "limit: 3", "limit: 4")
    stale = views.stale_views(root)
    assert len(stale) == 1
    assert VIEWS[0] in stale[0] and COMMAND in stale[0]
    assert VIEWS[1] not in stale[0]


def test_gv_1_every_value_of_both_views_comes_from_the_preset_and_the_sidecar():
    """The parsed views equal a reading of the preset and the sidecar alone."""
    views = _views_module()
    policy, guardrails = views.rebuild(ROOT)
    for rel, built in zip(VIEWS, (policy, guardrails)):
        assert yaml.safe_load((ROOT / rel).read_text(encoding="utf-8")) == built, rel


# --- the header and the three inputs (`GV-2`) -----------------------------------

def test_gv_2_the_header_names_the_command_and_every_input_changes_the_text(
        tmp_path, monkeypatch):
    views = _views_module()
    base = views.generate(ROOT)
    for rel in VIEWS:
        committed = (ROOT / rel).read_text(encoding="utf-8")
        for source, text in (("committed", committed), ("generated", base[rel])):
            head = " ".join(text.splitlines()[:6])
            assert "GENERATED" in head, (source, rel)
            assert "do not edit" in head.lower(), (source, rel)
            assert COMMAND in head, (source, rel)
            assert "governance/presets/default/" in head, (source, rel)

    # A value in the preset.
    root = _root_copy(tmp_path / "preset")
    planted = _plant_rationale(root / "governance/presets/default/rules.yml")
    changed = views.generate(root)
    assert changed[VIEWS[0]] != base[VIEWS[0]]
    assert planted in changed[VIEWS[0]]
    assert changed[VIEWS[1]] == base[VIEWS[1]]

    # A value in the sidecar.
    root = _root_copy(tmp_path / "sidecar")
    _edit(root / "governance/legacy-views.yml", "G5: [land]", "G5: [verify, land]")
    changed = views.generate(root)
    assert changed[VIEWS[1]] != base[VIEWS[1]]
    assert changed[VIEWS[0]] == base[VIEWS[0]]

    # A comment in the template.
    template = importlib.import_module("compass_pkg.legacy_views_template")
    monkeypatch.setitem(template.ENTRY_COMMENTS, ("RP-FLOOR-002", "rationale"),
                        ["# A changed template comment."])
    changed = views.generate(ROOT)
    assert "# A changed template comment." in changed[VIEWS[0]]
    assert changed[VIEWS[0]] != base[VIEWS[0]]
    assert changed[VIEWS[1]] == base[VIEWS[1]]


def test_gv_2_each_preset_file_says_the_two_views_are_generated_from_it():
    """From here the preset is the source, and a reader of it must be told so."""
    for path in sorted((ROOT / "governance" / "presets" / "default").glob("*.yml")):
        head = " ".join(path.read_text(encoding="utf-8").splitlines()[:5])
        assert "source of the shipped defaults" in head, path.name
        assert "generated from these files" in head, path.name
        assert COMMAND in head, path.name


def test_gv_2_no_tracked_file_cites_a_line_of_a_generated_view():
    """A line number into a generated view moves at every regeneration, so a
    citation names the key or the section instead. Decision records are a
    dated record of what was true then and are left as written."""
    import re
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                            text=True, check=True).stdout.split("\0")
    cite = re.compile(r"(routing-policy|guardrails)" + r"\.yml:[0-9]+")
    hits = []
    for rel in sorted(r for r in listed if r):
        if rel.startswith(("architecture/", "governance/decisions/")):
            continue
        path = ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [f"{rel}: {m.group(0)}" for m in cite.finditer(text)]
    assert hits == [], "\n".join(hits)


def test_gv_2_the_scan_markers_and_layout_come_from_the_template():
    """The vocabulary-scan marker and the key order are in the generated text."""
    generated = _views_module().generate(ROOT)[VIEWS[0]]
    assert "# vocabulary-scan: allow - machine enum value, see above" in generated
    assert generated.index("RP-LOOP-003") < generated.index("ceiling: review_rounds",
                                                              generated.index("RP-LOOP-003"))
    assert "    - id: RP-LOOP-003\n      ceiling: review_rounds\n      when:" in generated


# --- the register and the derivation read the preset (`GV-3`) -------------------

def test_gv_3_the_register_and_the_derivation_read_the_preset(tmp_path):
    import plain_language_check as plc
    import test_mutation_proof_register as reg

    import inspect
    assert "preset" in inspect.signature(reg._checks).parameters, \
        "the register test reads its checks from the guardrails view only"
    assert "preset" in inspect.signature(plc._guardrail_meanings).parameters, \
        "the plain-language derivation reads the guardrails view only"

    preset = ROOT / "governance" / "presets" / "default"
    assert set(reg._checks()) == set(yaml.safe_load(
        (preset / "checks.yml").read_text(encoding="utf-8"))["checks"])
    # With the preset present the guardrails view is not read at all.
    broken = tmp_path / "guardrails.yml"
    broken.write_text("not: [valid\n", encoding="utf-8")
    assert set(reg._checks(guardrails=broken)) == set(reg._checks())
    # With the preset absent the generated view is the fallback.
    assert set(reg._checks(preset=tmp_path / "none")) == set(reg._checks())

    meanings = plc._guardrail_meanings()
    assert {"G1", "G2", "G3", "G4", "G5"} <= set(meanings)
    # A statement changed in a copy of the preset changes the derived words.
    copy = tmp_path / "default"
    shutil.copytree(preset, copy)
    _edit(copy / "gates.yml", "Traceability holds", "Provenance holds")
    changed = plc._guardrail_meanings(preset=copy, guardrails=broken)
    assert "provenance" in changed["G3"] and "provenance" not in meanings["G3"]


def test_gv_3_the_preset_derivation_equals_the_view_derivation(tmp_path):
    """The preset's gates hold the spike guardrails too, so the derivation must
    pick the default guardrails only, as `defaults:` in the view does."""
    import plain_language_check as plc
    from_preset = plc._guardrail_meanings()
    from_view = plc._guardrail_meanings(preset=tmp_path / "none", guardrails=ROOT / VIEWS[1])
    assert from_preset == from_view
    assert set(from_preset) == {"G1", "G2", "G3", "G4", "G5"}


# --- the script (`GV-5`) --------------------------------------------------------

def _run(*args, root):
    return subprocess.run([sys.executable, str(SCRIPT), "--root", str(root), *args],
                          capture_output=True, text=True, timeout=120)


def test_gv_5_the_script_writes_and_checks(tmp_path):
    assert SCRIPT.is_file(), "scripts/generate-legacy-views.py is missing"
    root = _root_copy(tmp_path)
    assert _run("--check", root=root).returncode == 0
    _edit(root / VIEWS[1], "version: 1.26.0", "version: 1.26.1")
    checked = _run("--check", root=root)
    assert checked.returncode == 1
    assert VIEWS[1] in checked.stdout + checked.stderr
    assert COMMAND in checked.stdout + checked.stderr
    # `--check` writes nothing.
    assert "version: 1.26.1" in (root / VIEWS[1]).read_text(encoding="utf-8")
    written = _run(root=root)
    assert written.returncode == 0, written.stderr
    first = {v: (root / v).read_bytes() for v in VIEWS}
    assert first == {v: (ROOT / v).read_bytes() for v in VIEWS}
    assert _run(root=root).returncode == 0
    assert {v: (root / v).read_bytes() for v in VIEWS} == first
    assert _run("--check", root=root).returncode == 0
