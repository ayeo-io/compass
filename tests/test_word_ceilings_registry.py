"""Scenario WCL-12 of the issue `word-ceilings-and-lld`.

`compass issue artifact set` registers one entry per work unit for the
`low-level-design` kind, `compass issue artifact-path` names a unit's file, and
every reader that lists each round of a repeating kind lists each unit too.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_artifact_catalogue_fields import (  # noqa: E402
    HOME, SLUG, _cli, _doc, _entries, _evaluate, _fixture, _justify_all, _manifest_of,
    _pass_every_gate, _set)

KIND = "low-level-design"
#: The words every refusal of a unit or a unit's path uses to name the pattern.
PATTERN = "U followed by a whole number from 1"


def _full(tmp_path):
    root, task_dir = _fixture(tmp_path, "full", risk="critical", size="large")
    code, out, err = _evaluate(root, *_justify_all(_manifest_of(task_dir)["assessment"]))
    assert code == 0, out + err
    assert _manifest_of(task_dir)["delivery_approach"] == "full"
    return root, task_dir


def test_wcl_12_one_entry_per_unit(tmp_path):
    root, task_dir = _full(tmp_path)
    paths = {}
    for unit in ("U1", "U2"):
        paths[unit] = _doc(root, f"low-level-design/{unit}.md", f"# Low-level design {unit}\n")
        code, out, err = _set(root, KIND, "--unit", unit, "--status", "draft",
                              "--path", paths[unit])
        assert code == 0, out + err
    found = _entries(task_dir, KIND)
    assert [(e["id"], e["unit"], e["path"]) for e in found] == [
        ("ART-LOW_LEVEL_DESIGN-U1", "U1", paths["U1"]),
        ("ART-LOW_LEVEL_DESIGN-U2", "U2", paths["U2"])]
    # Registering a unit again updates its entry and adds none.
    code, out, err = _set(root, KIND, "--unit", "U1", "--status", "approved")
    assert code == 0, out + err
    found = _entries(task_dir, KIND)
    assert len(found) == 2 and found[0]["status"] == "approved"

    # A malformed unit, and a path that is not a unit's home, are refused naming the
    # pattern, and nothing is written.
    before = (task_dir / "manifest.yml").read_bytes()
    for unit in ("U0", "U01", "core"):
        code, out, err = _set(root, KIND, "--unit", unit, "--status", "draft")
        assert code != 0 and PATTERN in out + err, (unit, out + err)
    for rel in (f"{HOME}/low-level-design.md", f"{HOME}/low-level-design/a/U1.md"):
        code, out, err = _set(root, KIND, "--status", "draft", "--path", rel)
        assert code != 0 and PATTERN in out + err, (rel, out + err)
    # A unit that disagrees with the path is refused too.
    code, out, err = _set(root, KIND, "--unit", "U2", "--status", "draft",
                          "--path", paths["U1"])
    assert code != 0 and "U2" in out + err and "U1" in out + err, out + err
    # --unit on a kind that is not per unit is refused.
    code, out, err = _set(root, "technical-design", "--unit", "U1", "--status", "draft")
    assert code != 0 and "--unit" in out + err, out + err
    assert (task_dir / "manifest.yml").read_bytes() == before

    # artifact-path names a unit's file, and refuses to pick one of several.
    code, out, err = _cli(root, "issue", "artifact-path", KIND, "--unit", "U2",
                          "--issue", SLUG)
    assert code == 0 and out.strip().endswith(paths["U2"]), out + err
    code, out, err = _cli(root, "issue", "artifact-path", KIND, "--issue", SLUG)
    assert code != 0 and "U1" in out + err and "U2" in out + err, out + err

    # compass check names each unit by its own entry: U2 is the draft.
    _pass_every_gate(task_dir)
    code, out, err = _cli(root, "check", "--issue", SLUG, "--json")
    rows = {r["name"]: r for r in json.loads(out)["checks"]}
    detail = rows["artifacts-approved"]["detail"]
    assert "ART-LOW_LEVEL_DESIGN-U2" in detail and "low-level-design U2" in detail, detail
    assert "ART-LOW_LEVEL_DESIGN-U1" not in detail, detail

    # The issue page, the board and the receipt list one line per unit.
    code, out, err = _cli(root, "issue", "render", "--issue", SLUG)
    assert code == 0, out + err
    page = (root / HOME / "README.md").read_text(encoding="utf-8")
    board = tmp_path / "board.html"
    code, out, err = _cli(root, "flow", "--html", str(board))
    assert code == 0, out + err
    html = board.read_text(encoding="utf-8")
    code, receipt, err = _cli(root, "issue", "receipt", "--issue", SLUG)
    assert code == 0, receipt + err
    for unit in ("U1", "U2"):
        entry_id = "ART-LOW_LEVEL_DESIGN-" + unit
        lines = [line for line in page.splitlines() if entry_id in line]
        assert len(lines) == 1 and f"low-level-design/{unit}.md" in lines[0], (unit, lines)
        assert entry_id in html and f"low-level-design {unit}" in html, unit
        # The receipt keeps each line to one screen width, so the path can be cut short.
        lines = [line for line in receipt.splitlines() if entry_id in line]
        assert len(lines) == 1 and f"low-level-design {unit}" in lines[0], (unit, receipt)

    # Issue lint lists neither unit file as a stray document.
    code, out, err = _cli(root, "issue", "lint", "--issue", SLUG)
    assert "low-level-design" not in out + err, out + err
