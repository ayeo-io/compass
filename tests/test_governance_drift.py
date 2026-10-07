"""Governance drift detection (issue governance-drift-detection).

A project that runs `/compass:init` gets a COPY of `governance/`. The framework
later ships new floors and checks; the copy never learns about them; and nothing
reports the divergence. The result is a delivery approach that looks correct,
passes every check, and is quietly missing gates current policy needs.

Reproduced against HEAD before this was written: a `governance/` missing four
floors and five checks computes 7 gates where the shipped policy computes 9, and
`compass policy lint` returns a clean PASS.

The failure is DIRECTIONAL, which is what makes it dangerous - stale governance
never fails loudly, it produces a *lighter* delivery approach. Every artifact
looks right.

Two properties matter as much as the detection:

  * It must not report drift where there is none. A project that reworded a
    rationale, reordered its floors, or added its own rules has not drifted.
    A detector that fires on those gets switched off, and then detects
    nothing.
  * A deliberate omission must be distinguishable from an unseen one. A project
    that considered RP-REQUIRE-003 and rejected it is in a different state from
    one that has never heard of it.

Spec: governance-drift-detection/acceptance-criteria.md (`TRC-A1`..`TRC-A3`,
      `TRC-B1`..`TRC-B8`).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import subprocess
import sys

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
GOVERNANCE = ROOT / "governance"
HASHES = ROOT / "tests" / "fixtures" / "governance-content-hashes.json"

GOV_FILES = ("routing-policy.yml", "guardrails.yml")

# Rules the framework ships that a ~1.5.0 project predates. Used to build a
# realistically stale copy rather than an invented one.
STALE_DROP_FLOORS = ["RP-REQUIRE-001", "RP-REQUIRE-002", "RP-REQUIRE-003",
                     "RP-REQUIRE-004"]
STALE_DROP_CHECKS = ["declared-tests-resolve", "dod-evidence-typed",
                     "consistency-check-passes", "no-trusted-rerun",
                     "command-passes"]


# --- helpers ---------------------------------------------------------------

def content_hash(path: pathlib.Path) -> str:
    """Hash the parsed YAML with sorted keys, EXCLUDING `version:` itself.

    Excluding the version is not optional: including it would make the pin
    self-referential, so bumping the version would change the content the
    version is pinning. Comments are commentary on the mechanism - the
    `rationale:` fields that carry each rule's reasoning are YAML values and so
    are inside the hash already.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data.pop("version", None)
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_project(tmp_path, *, stale=False, waived=None, extra_floor=False,
                 strict=False, broken=False):
    """A project with its own governance/, optionally drifted from shipped."""
    proj = tmp_path / "proj"
    (proj / ".compass" / "work").mkdir(parents=True)
    shutil.copytree(GOVERNANCE, proj / "governance")

    cfg = "version: 1.0.0\nmode: enforced\n"
    if strict:
        cfg += "governance_drift: strict\n"
    (proj / ".compass" / "config.yml").write_text(cfg, encoding="utf-8")

    rp_path = proj / "governance" / "routing-policy.yml"
    gr_path = proj / "governance" / "guardrails.yml"

    if stale:
        rp = yaml.safe_load(rp_path.read_text())
        rg = rp["routing_guardrails"]
        rg["floors"] = [f for f in rg["floors"]
                        if f["id"] not in STALE_DROP_FLOORS]
        rp["routing_strategies"].pop("advisory_strategies", None)
        rp_path.write_text(yaml.safe_dump(rp, sort_keys=False))

        gr = yaml.safe_load(gr_path.read_text())
        for name in STALE_DROP_CHECKS:
            gr["checks"].pop(name, None)
        for g in gr["defaults"]:
            g["checks"] = [c for c in g.get("checks", [])
                           if c not in STALE_DROP_CHECKS]
        gr_path.write_text(yaml.safe_dump(gr, sort_keys=False))

    if waived is not None:
        rp = yaml.safe_load(rp_path.read_text())
        rp["routing_guardrails"]["waived"] = waived
        rp_path.write_text(yaml.safe_dump(rp, sort_keys=False))

    if extra_floor:
        rp = yaml.safe_load(rp_path.read_text())
        rp["routing_guardrails"]["floors"].append({
            "id": "PROJ-FLOOR-001",
            "when": {"risk": "critical"},
            "force_minimum_route": "expedition",
            "rationale": "a rule this project added for itself",
        })
        rp_path.write_text(yaml.safe_dump(rp, sort_keys=False))

    if broken:
        rp_path.write_text("this: is: not: valid: yaml: [\n")

    return proj


def lint(proj):
    return subprocess.run(
        [sys.executable, str(CLI), "policy", "lint"],
        cwd=str(proj), capture_output=True, text=True, timeout=60,
    )


# ---------------------------------------------------------------------------
# `TRC-A1` - the shipped governance declares a version that has moved
# ---------------------------------------------------------------------------

def test_trc_a1_the_shipped_governance_should_declare_a_version_that_has_moved():
    for name in GOV_FILES:
        data = yaml.safe_load((GOVERNANCE / name).read_text())
        version = str(data.get("version", ""))
        assert version, f"{name} declares no version"
        assert version != "1.0.0", (
            f"{name} still declares 1.0.0 - the version that shipped with 1.5.0, "
            f"before four floors and five checks were added. A version that "
            f"never moves cannot signal staleness."
        )
        parts = version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts), (
            f"{name} version {version!r} is not semver")

    # the two files version independently of the plugin
    plugin_version = (ROOT / "VERSION").read_text().strip()
    versions = {str(yaml.safe_load((GOVERNANCE / n).read_text())["version"])
                for n in GOV_FILES}
    assert versions != {plugin_version}, (
        "governance versions track the plugin version; they are meant to move "
        "when their own content changes, which is a different cadence"
    )


# ---------------------------------------------------------------------------
# `TRC-A2` - content may not change without the version moving
# ---------------------------------------------------------------------------

def test_trc_a2_changing_governance_content_without_bumping_its_version_should_fail():
    assert HASHES.is_file(), (
        f"{HASHES.relative_to(ROOT)} does not exist - there is nothing pinning "
        f"governance content to its declared version")
    pinned = json.loads(HASHES.read_text())

    for name in GOV_FILES:
        path = GOVERNANCE / name
        version = str(yaml.safe_load(path.read_text())["version"])
        actual = content_hash(path)

        assert name in pinned, f"{name} has no pinned hash"
        entry = pinned[name]
        assert entry.get("version") == version, (
            f"{name} declares version {version} but the pin records "
            f"{entry.get('version')}. Bump one to match the other:\n"
            f"  - if the content changed, raise the version in "
            f"governance/legacy-views.yml (the file {name} is generated from "
            f"it) and re-record the hash with "
            f"`python3 scripts/generate-legacy-views.py --pin-hashes`\n"
            f"  - if it did not, the pin is stale")
        assert entry.get("sha256") == actual, (
            f"{name} content changed without its version moving.\n"
            f"  declared version: {version}\n"
            f"  pinned  sha256  : {entry.get('sha256')}\n"
            f"  actual  sha256  : {actual}\n"
            f"{name} is generated from the preset, so do not edit it. Raise "
            f"`version:` under `routing_policy` or `guardrails` in "
            f"governance/legacy-views.yml, run "
            f"`python3 scripts/generate-legacy-views.py`, then "
            f"`python3 scripts/generate-legacy-views.py --pin-hashes` to update "
            f"{HASHES.relative_to(ROOT)}.")


# ---------------------------------------------------------------------------
# `TRC-A3` - a project behind the framework's version is told
# ---------------------------------------------------------------------------

def test_trc_a3_a_project_behind_the_frameworks_governance_version_should_be_told(tmp_path):
    proj = make_project(tmp_path, stale=True)
    rp = proj / "governance" / "routing-policy.yml"
    data = yaml.safe_load(rp.read_text())
    data["version"] = "1.0.0"
    rp.write_text(yaml.safe_dump(data, sort_keys=False))

    out = lint(proj).stdout
    shipped = str(yaml.safe_load((GOVERNANCE / "routing-policy.yml").read_text())["version"])
    assert "1.0.0" in out and shipped in out, (
        f"the report names neither version:\n{out}")
    assert "behind" in out.lower(), f"the report does not say the project is behind:\n{out}"


# ---------------------------------------------------------------------------
# `TRC-B1` / B2 - missing rules and checks are named individually
# ---------------------------------------------------------------------------

def test_trc_b1_missing_floors_and_strategies_should_be_named_individually(tmp_path):
    out = lint(make_project(tmp_path, stale=True)).stdout
    for rule in STALE_DROP_FLOORS + ["RP-ADV-001"]:
        assert rule in out, f"{rule} is missing from the project but not named:\n{out}"
    assert "5" in out, f"the report does not state a total count:\n{out}"


def test_trc_b2_missing_guardrail_checks_should_be_named_individually(tmp_path):
    out = lint(make_project(tmp_path, stale=True)).stdout
    for name in STALE_DROP_CHECKS:
        assert name in out, f"check {name} is missing but not named:\n{out}"


# ---------------------------------------------------------------------------
# `TRC-B3`..B5 - waivers
# ---------------------------------------------------------------------------

def test_trc_b3_a_waived_rule_should_read_as_deliberate_not_as_drift(tmp_path):
    proj = make_project(tmp_path, stale=True, waived=[
        {"id": "RP-REQUIRE-003", "reason": "this project has no fitness functions yet"}])
    out = lint(proj).stdout

    assert "waived" in out.lower(), f"the report never mentions waivers:\n{out}"
    # the four remaining drifted floors, not five
    assert "4" in out, f"the drifted count does not exclude the waiver:\n{out}"
    waived_section = out.lower().split("waived", 1)[1]
    # Lowercased because the section is lowercased for comparison. The 3.0.0
    # id sweep renamed every uppercase RG-/RS- id and missed this one, leaving
    # an assertion checking the old id against output produced from the new.
    assert "rp-require-003" in waived_section, (
        f"RP-REQUIRE-003 is not reported under waived:\n{out}")


def test_trc_b4_a_waiver_without_a_reason_should_be_refused(tmp_path):
    proj = make_project(tmp_path, stale=True, waived=[{"id": "RP-REQUIRE-003"}])
    result = lint(proj)
    assert result.returncode != 0, f"a reasonless waiver passed:\n{result.stdout}"
    combined = result.stdout + result.stderr
    assert "RP-REQUIRE-003" in combined
    assert "reason" in combined.lower(), (
        f"the message does not say a waiver needs a reason:\n{combined}")


def test_trc_b5_waiving_a_rule_the_framework_does_not_ship_should_be_refused(tmp_path):
    proj = make_project(tmp_path, waived=[
        {"id": "RG-FLOOR-999", "reason": "typo"}])
    result = lint(proj)
    assert result.returncode != 0, f"a waiver for an unknown rule passed:\n{result.stdout}"
    combined = result.stdout + result.stderr
    assert "RG-FLOOR-999" in combined
    assert "does not exist" in combined.lower() or "unknown" in combined.lower(), (
        f"the message does not explain the id is unknown:\n{combined}")


# ---------------------------------------------------------------------------
# `TRC-B6` / B7 - advisory by default, strict by choice
# ---------------------------------------------------------------------------

def test_trc_b6_drift_should_be_advisory_by_default(tmp_path):
    result = lint(make_project(tmp_path, stale=True))
    assert result.returncode == 0, (
        "drift blocked by default; ADR-006 says an upgrade must not turn every "
        f"existing adopter's build red:\n{result.stdout}")
    assert "RP-REQUIRE-001" in result.stdout, "drift was not reported at all"
    assert "strict" in result.stdout.lower(), (
        f"the report does not say how to make drift blocking:\n{result.stdout}")


def test_trc_b7_a_project_may_opt_into_failing_on_drift(tmp_path):
    result = lint(make_project(tmp_path, stale=True, strict=True))
    assert result.returncode != 0, (
        f"governance_drift: strict did not make drift blocking:\n{result.stdout}")
    for rule in STALE_DROP_FLOORS:
        assert rule in result.stdout, (
            f"strict mode names fewer rules than advisory mode: {rule} absent")


# ---------------------------------------------------------------------------
# `TRC-B8` - the waived block is declared in the schemas
# ---------------------------------------------------------------------------

def test_trc_b8_the_waived_block_should_be_declared_in_the_schema():
    schema = json.loads((ROOT / "schemas" / "routing-policy.schema.json").read_text())
    rg = schema["properties"]["routing_guardrails"]
    assert "waived" in rg.get("properties", {}), (
        "routing-policy.schema.json does not declare `waived`. Neither schema "
        "sets additionalProperties: false, so an undeclared block would "
        "validate by luck - which is this task's own thesis, one layer down.")

    waived = rg["properties"]["waived"]
    item = waived.get("items", {})
    assert set(item.get("required", [])) >= {"id", "reason"}, (
        "a waiver must require both id and reason")
    for field in ("id", "reason"):
        assert item["properties"][field].get("minLength", 0) >= 1, (
            f"{field} may be empty, so a waiver can record no decision")
