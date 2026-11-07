"""The frozen governance views keep their version and content (issue
governance-drift-detection).

`governance/routing-policy.yml` and `governance/guardrails.yml` declare a
version, and their content is pinned to it, so a change cannot go unseen. The
issue also added the drift report, which compared a project's copy of these
files with the framework's. 9.0.0 removed the drift report and the
`governance_drift` setting (ADR-098), and `TRC-A3` and `TRC-B1` to `TRC-B7`,
which tested it, with them. The views stay for the legacy readers, so the pins
stay.

Spec: governance-drift-detection/acceptance-criteria.md (`TRC-A1`, `TRC-A2`,
      `TRC-B8`).
"""
from __future__ import annotations

import hashlib
import json
import pathlib

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
GOVERNANCE = ROOT / "governance"
HASHES = ROOT / "tests" / "fixtures" / "governance-content-hashes.json"

GOV_FILES = ("routing-policy.yml", "guardrails.yml")


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
            f"{entry.get('version')}. {name} is frozen since 9.0.0 (ADR-094) and "
            f"read only by the legacy readers, so neither may move: restore the "
            f"file from git")
        assert entry.get("sha256") == actual, (
            f"{name} content changed without its version moving.\n"
            f"  declared version: {version}\n"
            f"  pinned  sha256  : {entry.get('sha256')}\n"
            f"  actual  sha256  : {actual}\n"
            f"{name} is frozen since 9.0.0 (ADR-094), so do not edit it: only "
            f"its first line may change. The shipped defaults are in "
            f"governance/check-set.yml; restore {name} from git, which keeps "
            f"{HASHES.relative_to(ROOT)} as it is.")


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
