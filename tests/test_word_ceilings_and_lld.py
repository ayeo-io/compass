"""Scenarios WCL-20 and WCL-23 of the issue `word-ceilings-and-lld`.

WCL-23 checks that the design-size check, the `word_ceiling` field and the
`low-level-design` kind are declared and documented, and that no locked
entry changed. WCL-20 checks, where this issue's own records exist, that the
issue was judged by its own rules and passed.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_artifact_catalogue_fields import _derive, _mini_root  # noqa: E402

CHECK = "design-within-word-ceiling"
FIELD = "word_ceiling"
KIND = "low-level-design"
SLUG = "word-ceilings-and-lld"
PRESET = ROOT / "governance" / "presets" / "default"


def _yaml(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _origin_main(rel):
    run = subprocess.run(["git", "show", "origin/main:%s" % rel], cwd=ROOT,
                         capture_output=True, text=True)
    if run.returncode != 0:
        pytest.skip("origin/main is not available here: %s" % run.stderr.strip())
    return yaml.safe_load(run.stdout)


def _locked(document, catalogue):
    return {name: body.get("locked") for name, body in (document.get(catalogue) or {}).items()
            if isinstance(body, dict) and "locked" in body}


# --- WCL-23: the check, the field and the kind are declared and documented ----------

def test_wcl_23_declared_and_documented(tmp_path):
    from compass_pkg import check_registry, outside_gate

    checks = _yaml(PRESET / "checks.yml")["checks"]
    entry = checks[CHECK]
    assert (entry["kind"], entry["severity"], entry["on_skipped"]) == (
        "deterministic", "blocking", "not-applicable")
    assert entry["params"] == {"factor": 1.5}
    assert "locked" not in entry

    # No gate or stage list names the check, and every locked key is as on main.
    for name in ("gates.yml", "stages.yml"):
        assert CHECK not in (PRESET / name).read_text(encoding="utf-8"), name
    for name, catalogue in (("gates.yml", "gates"), ("stages.yml", "stages"),
                            ("checks.yml", "checks")):
        before = _origin_main("governance/presets/default/" + name)
        assert _locked(_yaml(PRESET / name), catalogue) == _locked(before, catalogue), name

    # It runs outside every gate, on a spike too, with a versioned implementation and corpus.
    assert CHECK in outside_gate.CHECKS and CHECK in outside_gate.SPIKE_CHECKS
    lock = _yaml(ROOT / "tests" / "fixtures" / "impls" / "versions.lock.yml")["implementations"]
    assert check_registry.installed_version(CHECK) == lock[CHECK]["version"] == "1.0.0"
    assert list((ROOT / "tests" / "fixtures" / "impls" / CHECK).iterdir())
    for name in ("nfr-rows-resolved", "contracts-declared"):
        assert check_registry.installed_version(name) == lock[name]["version"] == "1.0.0"

    # The owning docs name the field, the word rule, the placeholder and the kind.
    catalogue = (ROOT / "docs" / "artifact-catalogue.md").read_text(encoding="utf-8")
    for words in (FIELD, "whitespace-separated token", "<unit>", KIND):
        assert words in catalogue, words
    terms = (ROOT / "governance" / "terminology.yml").read_text(encoding="utf-8")
    glossary = (ROOT / "docs" / "glossary.md").read_text(encoding="utf-8")
    assert FIELD in terms and FIELD in glossary
    # The generated tables match a fresh generation.
    fresh_glossary, fresh_catalogue = _derive(_mini_root(tmp_path), tmp_path, "fresh")
    assert fresh_glossary == glossary and fresh_catalogue == catalogue
    index = (ROOT / "architecture" / "decisions" / "README.md").read_text(encoding="utf-8")
    assert [row for row in index.splitlines() if row.startswith("| [ADR-067]")]

    # No capability switch and no alias governs the check, the field or the kind.
    preset = _yaml(PRESET / "preset.yml")
    for switch in preset.get("capabilities") or {}:
        assert not any(name in switch for name in (CHECK, FIELD, KIND)), switch
    vocabulary = _yaml(PRESET / "vocabulary.yml")["vocabulary"]
    for key, body in vocabulary.items():
        if any(name in key for name in (CHECK, FIELD, KIND)):
            assert body.get("aliases") == [], key
    upgrade = (ROOT / "docs" / "upgrade-7-0-0.md").read_text(encoding="utf-8")
    for words in (CHECK, FIELD, KIND, "--unit", "compass approach evaluate --write"):
        assert words in upgrade, words


# --- WCL-20: this issue reassesses onto the new catalogue and passes ---------------

def _copy(target):
    """A copy of this issue's records and documents and the project file, so the
    check, which records its results, never writes into this checkout."""
    import shutil

    task = _yaml(ROOT / ".compass" / "work" / SLUG / "manifest.yml")
    for rel in (".compass/work/" + SLUG, "docs/compass/%s-%s" % (task["created"], SLUG)):
        shutil.copytree(ROOT / rel, target / rel)
    shutil.copy(ROOT / "compass.yml", target / "compass.yml")
    # Once the issue lands, the check declines on it as a closed issue. The copy is
    # reopened so the test judges the design as it was judged before landing.
    manifest = target / ".compass" / "work" / SLUG / "manifest.yml"
    body = _yaml(manifest)
    for key in ("status", "close_reason", "land_commit"):
        body.pop(key, None)
    manifest.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    return target


def _run(root, *argv):
    import os

    return subprocess.run([sys.executable, str(ROOT / "cli" / "compass"), *argv], cwd=root,
                          capture_output=True, text=True, timeout=600,
                          env=dict(os.environ, CLAUDE_PROJECT_DIR=str(root)))


def test_wcl_20_own_issue_passes(tmp_path):
    manifest = ROOT / ".compass" / "work" / SLUG / "manifest.yml"
    if not manifest.is_file():
        pytest.skip("this issue's records are not here: CI has no archive")
    root = _copy(tmp_path / "copy")
    task = _yaml(manifest)
    assert task["delivery_approach"] == "full"
    assert isinstance(task.get("generation"), int) and task["generation"] >= 2
    resolved = _yaml(manifest.parent / "generations" / str(task["generation"]) / "resolved.yml")
    assert CHECK in resolved["checks"]
    assert FIELD in resolved["artifacts"]["technical-design"]
    assert KIND in resolved["artifacts"]
    units = sorted(a["unit"] for a in task["artifacts"]
                   if a.get("kind") == KIND and a.get("path"))
    assert units == ["U1", "U2", "U3", "U4", "U5", "U6"], units
    done = _run(root, "check", "--issue", SLUG, "--json")
    rows = {row["name"]: row for row in json.loads(done.stdout)["checks"]}
    assert rows[CHECK]["status"] == "pass", rows[CHECK]
    lint = _run(root, "issue", "lint", "--issue", SLUG)
    text = lint.stdout + lint.stderr
    assert "words, over the" not in text and "a work unit with no low-level design" not in text
