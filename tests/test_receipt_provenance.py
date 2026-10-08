"""Receipt provenance (issue `receipt-provenance`).

`compass issue receipt` names each fired rule, waiver, lock, unlock and check
with the layer that set it, the layer's version and the generation the issue
runs against. These tests build a scratch project, commit a generation with the
real command, render the real receipt and read the section back.

Scenario ids: `RP-1` to `RP-13`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import copy
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import waiver_fixtures as fx  # noqa: E402
from parent_fixtures import REAL_GIT, issue_project, make_remote  # noqa: E402
from test_generation_store import MANIFEST, SLUG, _project  # noqa: E402

CLI = ROOT / "cli" / "compass"
DEFAULT = "default@6 (6.0.0)"
PROJECT = "project (compass.yml)"
ISSUE = "issue (config: in manifest.yml)"
CHECK = "dor-affected-surface-named"
OWNER_WAIVER = {"reason": "The surface is named at plan here.", "approved_by": "jed72",
                "approved_on": "2026-10-05"}


def _env(home, extra=None):
    env = {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(home), "LANG": "C.UTF-8",
           "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
    env.update(extra or {})
    return env


def _run(cwd, *argv, env=None):
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=cwd, env=_env(cwd, env),
                          capture_output=True, text=True, timeout=180)
    return done.returncode, done.stdout, done.stderr


def _assessed(tmp_path, compass_yml=None, labels=(), config=None, evidence=None, env=None):
    """A scratch project whose issue has a committed generation. Returns
    `(root, task_dir)`."""
    manifest = copy.deepcopy(MANIFEST)
    manifest["assessment"]["labels"] = list(labels)
    if config is not None:
        manifest["config"] = config
    if evidence is not None:
        manifest["evidence"] = evidence
    root, task_dir = _project(tmp_path, manifest=manifest,
                              compass_yml={"schema": 1} if compass_yml is None else compass_yml)
    code, out, err = _run(root, "approach", "evaluate", "--issue", SLUG, "--write", env=env)
    assert code == 0, out + err
    return root, task_dir


def _receipt(root, env=None):
    code, out, err = _run(root, "issue", "receipt", "--issue", SLUG, env=env)
    assert code == 0, out + err
    return out


class Row:
    def __init__(self, kind, label, text):
        self.kind, self.label, self.text = kind, label, text

    @property
    def items(self):
        return [item.strip() for item in self.text.split(",")]

    def __repr__(self):
        return f"Row({self.kind!r}, {self.label!r}, {self.text!r})"


def _section(out):
    """`(title, rows)` of the Provenance section, or `(None, [])`. A row starts
    two spaces in; a continuation line is indented further."""
    lines = out.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith("Provenance")]
    if not starts:
        return None, []
    title = lines[starts[0]]
    body = []
    for line in lines[starts[0] + 2:]:
        if not line.strip():
            break
        body.append(line)
    rows = []
    for line in body:
        if line.startswith("  ") and not line.startswith("   "):
            kind, rest = line[2:16].strip(), line[17:]
            # A label too long for its line leaves the " -" at the end of it.
            label, _, text = (rest[:-2] + " - ").partition(" - ") if rest.endswith(" -") \
                else rest.partition(" - ")
            rows.append(Row(kind, label.strip(), text.strip()))
        else:
            rows[-1].text += " " + line.strip()
    for row in rows:
        row.text = re.sub(r"\s+", " ", row.text).strip()
    return title, rows


def _rows(out, kind, label=None):
    return [r for r in _section(out)[1]
            if r.kind == kind and (label is None or r.label == label)]


def _one(out, kind, label=None):
    found = _rows(out, kind, label)
    assert len(found) == 1, (kind, label, _section(out)[1])
    return found[0]


# --- RP-1: a default rule ----------------------------------------------------------------

def test_rp_1_a_default_rule_names_the_preset_its_version_and_the_generation(tmp_path):
    root, _ = _assessed(tmp_path, labels=["auth"])
    out = _receipt(root)
    title, _ = _section(out)
    assert title == "Provenance (generation 1)"
    row = _one(out, "rules fired", DEFAULT)
    assert "RP-FLOOR-003" in row.items
    assert "RP-REQUIRE-002" in row.items


# --- RP-2: a project rule ----------------------------------------------------------------

PROJECT_RULE = {"rules": {"floors": {"set": {"rules": {"set": {"RP-PROJ-001": {
    "order": 9, "when": {"size": "standard"}, "then": {"add_gate": "verify.analyze"},
    "rationale": "The project wants analysis."}}}}}}}


def test_rp_2_a_project_rule_names_the_project_not_the_default(tmp_path):
    root, _ = _assessed(tmp_path, compass_yml={"schema": 1, "owner": "jed72", **PROJECT_RULE},
                        labels=["auth"])
    out = _receipt(root)
    assert _one(out, "rules fired", PROJECT).items == ["RP-PROJ-001"]
    assert "RP-PROJ-001" not in _one(out, "rules fired", DEFAULT).items
    assert "RP-FLOOR-003" in _one(out, "rules fired", DEFAULT).items


# --- RP-3: a git parent -------------------------------------------------------------------

def test_rp_3_a_git_parent_rule_names_the_reference_pin_and_version(tmp_path):
    base = tmp_path / "remotes"
    parent = {"schema": 1, "owner": "platform-team", **{
        "rules": {"floors": {"set": {"rules": {"set": {"RP-ACME-001": {
            "order": 9, "when": {"size": "standard"}, "then": {"add_gate": "verify.analyze"},
            "rationale": "The platform team wants analysis."}}}}}}}}
    sha = make_remote(base, files={"compass.yml": yaml.safe_dump(parent)})
    root, task_dir = issue_project(tmp_path, f"github:acme/bank@1.2.0#{sha}")
    code, out, err = _run(root, "approach", "evaluate", "--issue", "feature", "--write",
                          env={"COMPASS_PARENT_REMOTE_BASE": str(base)})
    assert code == 0, out + err
    code, out, err = _run(root, "issue", "receipt", "--issue", "feature")
    assert code == 0, err
    label = f"github:acme/bank@1.2.0#{sha[:12]} (1.2.0)"
    assert _one(out, "rules fired", label).items == ["RP-ACME-001"]
    assert _rows(out, "rules fired", DEFAULT) == []


# --- RP-4 and RP-5: waivers ---------------------------------------------------------------

def _waived_project():
    return {"schema": 1, "owner": "jed72", "checks": {
        CHECK: {"set": {"severity": "advisory"}, "waiver": dict(OWNER_WAIVER)}}}


def test_rp_4_a_project_waiver_names_its_id_layer_approver_date_and_status(tmp_path):
    root, _ = _assessed(tmp_path, compass_yml=_waived_project())
    row = _one(_receipt(root), "waiver", f"project:checks.{CHECK}")
    assert row.text == f"{PROJECT}, approved by jed72 on 2026-10-05, valid"


def _issue_waiver_case(tmp_path):
    approval = fx.approval(approver="jed72", id="EV-1")
    approval["waiver"] = {"scope": "issue", "entry": f"checks.{CHECK}",
                          "fields": {"severity": {"from": "blocking", "to": "advisory"}}}
    config = {"checks": {CHECK: {"set": {"severity": "advisory"},
                                 "waiver": fx.issue_waiver(approved_by="EV-1")}}}
    return _assessed(tmp_path, compass_yml={"schema": 1, "owner": "jed72"}, config=config,
                     evidence=[approval])


def test_rp_5_an_issue_waiver_names_its_approval_record(tmp_path):
    root, _ = _issue_waiver_case(tmp_path)
    row = _one(_receipt(root), "waiver", f"issue:checks.{CHECK}")
    assert row.text == f"{ISSUE}, approved by EV-1, valid"


def test_rp_5_a_landed_issue_shows_its_issue_waiver_as_expired_at_land(tmp_path):
    root, task_dir = _issue_waiver_case(tmp_path)
    path = task_dir / "manifest.yml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest.update(status="landed", land_timestamp="2026-10-08T10:00:00+00:00")
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    row = _one(_receipt(root), "waiver", f"issue:checks.{CHECK}")
    assert row.text == f"{ISSUE}, approved by EV-1, expired at land 2026-10-08"


def test_rp_5_a_landed_issue_keeps_its_project_waiver_valid(tmp_path):
    root, task_dir = _assessed(tmp_path, compass_yml=_waived_project())
    path = task_dir / "manifest.yml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest.update(status="landed", land_timestamp="2026-10-08T10:00:00+00:00")
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    row = _one(_receipt(root), "waiver", f"project:checks.{CHECK}")
    assert row.text.endswith(", valid")


# --- RP-6 and RP-7: unlocks and locks -----------------------------------------------------

def _unlocked_project():
    return {"schema": 1, "owner": "jed72", "checks": {
        "suite-passed": {"unlock": True, "set": {"severity": "advisory"},
                         "waiver": dict(OWNER_WAIVER)}}}


def test_rp_6_an_unlock_names_the_entry_the_project_its_waiver_and_the_lock(tmp_path):
    root, _ = _assessed(tmp_path, compass_yml=_unlocked_project())
    row = _one(_receipt(root), "unlock", "checks.suite-passed")
    assert row.text == (f"{PROJECT}, waiver project:checks.suite-passed; "
                        f"lifts a true lock set by {DEFAULT}")


def test_rp_7_a_lock_on_a_named_entry_names_its_layer_and_level(tmp_path):
    root, _ = _assessed(tmp_path, compass_yml=_unlocked_project())
    out = _receipt(root)
    assert _one(out, "locks", DEFAULT).items == ["checks.suite-passed (true)"]


def test_rp_7_an_entry_with_no_lock_is_named_in_no_lock_row(tmp_path):
    root, _ = _assessed(tmp_path, compass_yml=_waived_project())
    assert _rows(_receipt(root), "locks") == []


# --- RP-8: checks -------------------------------------------------------------------------

ADDED = {"statement": "A project rule.", "kind": "deterministic", "impl": "scenarios-have-tests",
         "severity": "blocking", "on_skipped": "fail"}


def test_rp_8_a_check_a_project_changed_names_its_origin_and_the_layer_that_changed_it(tmp_path):
    root, _ = _assessed(tmp_path, compass_yml={
        **_waived_project(), "checks": {**_waived_project()["checks"], "arch-rule": ADDED}})
    out = _receipt(root)
    assert _one(out, "checks", DEFAULT).items == [CHECK]
    assert _one(out, "checks", PROJECT).items == ["arch-rule"]
    assert _one(out, "check changes", PROJECT).items == [f"{CHECK} (set)"]


def test_rp_8_a_check_in_a_stage_list_is_named_with_its_origin(tmp_path):
    root, _ = _assessed(tmp_path, compass_yml={
        "schema": 1, "capabilities": {"entry-exit-evaluation": True}})
    out = _receipt(root)
    listed = set()
    in_lists = False
    for line in out.splitlines():
        if line == "Stage lists":
            in_lists = True
        elif in_lists and not line.strip():
            break
        elif in_lists and line.startswith("    "):
            listed.add(line.split()[0])
    assert listed
    named = set(_one(out, "checks", DEFAULT).items)
    assert listed <= named, listed - named


# --- RP-9: an issue without a generation ----------------------------------------------------

def test_rp_9_an_issue_with_no_generation_gets_no_provenance_section(tmp_path):
    root, task_dir = _project(tmp_path)
    out = _receipt(root)
    assert "generation:" not in (task_dir / "manifest.yml").read_text(encoding="utf-8")
    assert "Provenance" not in out


def test_rp_9_an_issue_with_no_generation_in_a_layered_project_gets_no_section(tmp_path):
    root, task_dir = _project(tmp_path, compass_yml={"schema": 1, "owner": "jed72"})
    assert "generation:" not in (task_dir / "manifest.yml").read_text(encoding="utf-8")
    assert "Provenance" not in _receipt(root)


# --- RP-10: a generation stored before per-rule records ------------------------------------

def _drop_rule_steps(task_dir):
    """Rewrite generation 1 as an earlier build stored it: one record per rule
    set and none per rule, with the marker updated to match."""
    from compass_pkg.atomic_io import digest
    folder = task_dir / "generations" / "1"
    path = folder / "provenance.yml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["fields"] = {k: v for k, v in doc["fields"].items()
                     if not re.match(r"rules\.[^.]+\.rules\.", k)}
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    marker = folder / "complete"
    held = yaml.safe_load(marker.read_text(encoding="utf-8"))
    held["files"]["provenance.yml"] = digest(doc)
    marker.write_text(yaml.safe_dump(held, sort_keys=False), encoding="utf-8")


def test_rp_10_an_old_generation_names_the_layers_that_changed_the_rule_set(tmp_path):
    root, task_dir = _assessed(tmp_path, labels=["auth"],
                               compass_yml={"schema": 1, "owner": "jed72", **PROJECT_RULE})
    _drop_rule_steps(task_dir)
    out = _receipt(root)
    row = _one(out, "rules fired", f"unknown, rule set changed by {DEFAULT}, {PROJECT}")
    assert "RP-PROJ-001" in row.items and "RP-FLOOR-003" in row.items


def test_rp_10_an_old_generation_still_credits_a_rule_set_only_the_default_wrote(tmp_path):
    root, task_dir = _assessed(tmp_path, labels=["auth"])
    _drop_rule_steps(task_dir)
    assert "RP-FLOOR-003" in _one(_receipt(root), "rules fired", DEFAULT).items


def test_rp_10_a_fired_rule_the_stored_configuration_lacks_is_named_as_unknown(tmp_path):
    root, task_dir = _assessed(tmp_path)
    path = task_dir / "manifest.yml"
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest["policy_rules_fired"] = [{"id": "RP-GONE-001", "kind": "floor",
                                       "rationale": "A rule since removed."}]
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    row = _one(_receipt(root), "rules fired", "unknown, not in the stored configuration")
    assert row.items == ["RP-GONE-001"]


# --- RP-11: the line cap ----------------------------------------------------------------------

def test_rp_11_every_line_fits_100_columns_and_no_id_is_cut(tmp_path):
    long_id = "a-project-check-with-a-deliberately-long-identifier-" + "x" * 30
    added = {long_id: ADDED, **{f"project-check-number-{n}": ADDED for n in range(12)}}
    root, _ = _assessed(tmp_path, labels=["auth"], compass_yml={
        "schema": 1, "owner": "jed72", "capabilities": {"entry-exit-evaluation": True},
        "checks": {**_unlocked_project()["checks"], **added}, **PROJECT_RULE})
    out = _receipt(root)
    assert max(len(line) for line in out.splitlines()) <= 100
    project_checks = _one(out, "checks", PROJECT).items
    assert long_id in project_checks
    assert len(project_checks) == 13
    text = out[out.index("Provenance"):out.index("Conformance")]
    assert "..." not in text


# --- RP-12: the store records one step per rule ---------------------------------------------

def test_rp_12_a_new_generation_records_the_layer_and_operation_of_each_rule(tmp_path):
    root, task_dir = _assessed(tmp_path, compass_yml={"schema": 1, "owner": "jed72",
                                                      **PROJECT_RULE})
    fields = yaml.safe_load((task_dir / "generations" / "1" / "provenance.yml")
                            .read_text(encoding="utf-8"))["fields"]
    assert fields["rules.floors.rules.RP-PROJ-001"] == {
        "steps": [{"layer": "project", "op": "add"}]}
    assert fields["rules.floors.rules.RP-FLOOR-003"] == {
        "steps": [{"layer": "default", "op": "add"}]}


def _chain(project_rules):
    from compass_pkg import layers
    base = {"schema": 1, "rules": {"floors": {"kind": "floors", "hit": {"force_minimum_approach": "max"},
            "rules": {"R-1": {"order": 1, "when": {}, "then": {}, "rationale": "one"},
                      "R-2": {"order": 2, "when": {}, "then": {}, "rationale": "two"}}}}}
    project = {"schema": 1, "rules": {"floors": {"set": {"rules": project_rules}}}}
    return [layers.Layer("default", "parent", base, "d"),
            layers.Layer("project", "project", project, "p")]


def test_rp_12_a_changed_rule_has_a_step_for_the_layer_that_changed_it():
    from compass_pkg import effective
    history, _, _ = effective._steps(_chain({"set": {"R-1": {
        "order": 1, "when": {}, "then": {}, "rationale": "changed"}}}))
    assert history["rules.floors.rules.R-1"]["steps"] == [
        {"layer": "default", "op": "add"}, {"layer": "project", "op": "set"}]
    assert history["rules.floors.rules.R-2"]["steps"] == [{"layer": "default", "op": "add"}]


def test_rp_12_a_removed_rule_has_a_remove_step():
    from compass_pkg import effective
    history, _, _ = effective._steps(_chain({"remove": ["R-2"]}))
    assert history["rules.floors.rules.R-2"]["steps"] == [
        {"layer": "default", "op": "add"}, {"layer": "project", "op": "remove"}]


# --- RP-13: the owning documents -------------------------------------------------------------

def test_rp_13_the_receipt_page_describes_the_provenance_section():
    text = (ROOT / "docs" / "receipt.md").read_text(encoding="utf-8")
    assert "## Provenance" in text
    for word in ("rules fired", "unlock", "waiver", "lock", "check changes", "generation"):
        assert word in text


def test_rp_13_the_generation_store_page_describes_the_per_rule_records():
    text = (ROOT / "docs" / "generation-store.md").read_text(encoding="utf-8")
    assert "rules.<set>.rules.<id>" in text


def test_rp_13_the_owning_docs_table_names_the_new_module():
    text = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if "cli/compass_pkg/receipt.py" in line)
    assert "cli/compass_pkg/receipt_provenance.py" in row and "docs/receipt.md" in row
