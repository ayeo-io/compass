"""Scenarios WCL-13 and WCL-15 of the issue `word-ceilings-and-lld`.

The technical design template's Work units table gains a Low-level design
column that links each unit's low-level design, and `template show` prints
the `low-level-design` kind. The distribution map's subtask table, its
catalogue entry and the scripts that read the table do not change. The map
itself may gain other lines: issue `one-unit-breakdown` (ADR-071) added its
`units:` line, and `multiagent_check.py` reads that line as well as the table.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

from test_artifact_catalogue_fields import _cli, _scratch  # noqa: E402

PRESET = ROOT / "governance" / "presets" / "default"
LLD_HEADINGS = ["Signatures", "Contracts", "File-level plan", "Tests this unit writes"]
WORK_UNIT_COLUMNS = ["Unit", "Scenario group(s) it satisfies", "Code surface it touches",
                     "Independent of", "Low-level design"]

#: The scripts that read the distribution map's subtask table.
MAP_READERS = ("scripts/multiagent.sh", "scripts/integrate.sh")


# The two scripts' variable names and messages say "approach" where they said
# "route", because "route" is a verb only (ADR-044, issue
# `retired-words-in-prose-and-output`). The map is read the same way, so the
# comparison undoes that rename only.
_RENAMED = ((b"APPROACH_DOC", b"ROUTE"), (b"approach cap", b"route cap"),
            (b"If the approach is solo", b"If the route is solo"))


def _unrenamed(data):
    for new, old in _RENAMED:
        data = data.replace(new, old)
    return data


def _origin_main(rel):
    """The bytes of `rel` on origin/main, or a skip when that ref is absent."""
    run = subprocess.run(["git", "show", "origin/main:%s" % rel], cwd=ROOT,
                         capture_output=True)
    if run.returncode != 0:
        pytest.skip("origin/main is not available here: %s" % run.stderr.decode().strip())
    return run.stdout


def _artifacts(text):
    return yaml.safe_load(text)["artifacts"]


def _headings(text):
    return [line[3:].strip() for line in text.splitlines() if line.startswith("## ")]


def _subtask_table_header(text):
    return next(line for line in text.splitlines() if line.startswith("| Subtask "))


def _work_units_header(text):
    lines = text.splitlines()
    at = lines.index("## Work units")
    header = next(line for line in lines[at + 1:] if line.startswith("| Unit "))
    return [cell.strip() for cell in header.strip().strip("|").split("|")]


# --- WCL-13: template show prints the low-level design and the linked table ---------

def test_wcl_13_template_show(tmp_path):
    root = _scratch(tmp_path)
    code, out, err = _cli(root, "issue", "template", "show", "low-level-design")
    assert code == 0, out + err
    assert "# Low-level design" in out
    assert "<!-- compass:render document-header -->" in out
    assert _headings(out) == LLD_HEADINGS

    code, out, err = _cli(root, "issue", "template", "show", "technical-design",
                          "--depth", "thorough")
    assert code == 0, out + err
    assert _work_units_header(out) == WORK_UNIT_COLUMNS
    # The shape-of-the-change prose sends a full-approach author's signatures to
    # the unit's low-level design.
    shape = out.split("## The shape of the change", 1)[1].split("\n## ", 1)[0]
    assert "low-level design" in shape and "full" in shape and "signature" in shape

    # The design's sections lists in the catalogue are unchanged.
    now = _artifacts((PRESET / "artifacts.yml").read_text(encoding="utf-8"))
    before = _artifacts(_origin_main("governance/presets/default/artifacts.yml"))
    assert now["technical-design"]["sections"] == before["technical-design"]["sections"]


# --- WCL-15: the distribution map is unchanged ---------------------------------------

def test_wcl_15_distribution_map_unchanged():
    rel = "templates/distribution-map.md"
    assert (_subtask_table_header((ROOT / rel).read_text(encoding="utf-8"))
            == _subtask_table_header(_origin_main(rel).decode("utf-8")))
    now = _artifacts((PRESET / "artifacts.yml").read_text(encoding="utf-8"))
    before = _artifacts(_origin_main("governance/presets/default/artifacts.yml"))
    assert now["distribution-map"] == before["distribution-map"]
    for reader in MAP_READERS:
        assert _unrenamed((ROOT / reader).read_bytes()) == _unrenamed(
            _origin_main(reader)), reader
    # Unit is still the first column of the design's Work units table, which the
    # distribution map is read from.
    text = (ROOT / "templates" / "technical-design.md").read_text(encoding="utf-8")
    assert _work_units_header(text)[0] == "Unit"
