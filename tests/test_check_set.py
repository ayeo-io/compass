"""The fixed check set: its file, its pinned digest and its shape.

`governance/check-set.yml` holds every check, gate and evidence type Compass
runs (ADR-094). `cli/compass_pkg/check_set.py` reads it and returns it in the
shape `generations/<n>/resolved.yml` holds.

Until #357 step 8 the tests here also compared the set with the 8.x default
preset, entry by entry and on every point of the contract 1 grid. The preset
went in step 8, after that comparison held, so only the pin and the shape
are checked now.

`tests/fixtures/check-set-digests.yml` pins the file's sha256 for each version.
It is not an owner pin: the change that edits the file raises `version` and
pins the new digest in the same commit.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
import yaml

from compass_pkg import catalogue_spec, check_set, effective
from compass_pkg.core import CompassError

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / "tests" / "fixtures" / "check-set-digests.yml"


def _pins():
    return yaml.safe_load(PINS.read_text(encoding="utf-8"))


def _pin_problem(file, pins):
    """Why the file's bytes do not match the pin for its version, or None."""
    ref = check_set.ref(check_set.load(str(file)))
    if ref not in pins:
        return f"{PINS.name} has no digest for {ref}"
    got = check_set.sha256(str(file))
    if pins[ref] != got:
        return (f"governance/check-set.yml changed, but {PINS.name} still pins {ref} at "
                f"{pins[ref]}; the file is now {got}. Raise `version` and pin the new digest")
    return None


def test_the_resolver_reads_the_check_set(tmp_path):
    """A project with no `compass.yml` resolves to the check set itself."""
    assert effective.resolve_live(str(tmp_path)).resolved == check_set.resolved()


@pytest.fixture(scope="module")
def checks():
    return check_set.resolved()


# --- the file and its digest ------------------------------------------------------

def test_the_set_is_named_by_one_id_and_version():
    assert check_set.ref() == "compass-checks@9.0.0"


def test_the_digest_is_the_sha256sum_of_the_file():
    import hashlib
    want = hashlib.sha256((ROOT / check_set.PATH).read_bytes()).hexdigest()
    assert check_set.sha256() == want
    assert re.fullmatch(r"[0-9a-f]{64}", want)


def test_the_file_bytes_are_pinned_for_its_version():
    assert _pin_problem(ROOT / check_set.PATH, _pins()) is None


def test_a_changed_byte_without_a_new_pin_fails(tmp_path):
    copy_ = tmp_path / "check-set.yml"
    shutil.copy(ROOT / check_set.PATH, copy_)
    copy_.write_text(copy_.read_text(encoding="utf-8") + "\n# one more line\n",
                     encoding="utf-8")
    problem = _pin_problem(copy_, _pins())
    assert problem and "Raise `version`" in problem


def test_a_new_version_without_a_pin_fails(tmp_path):
    copy_ = tmp_path / "check-set.yml"
    text = (ROOT / check_set.PATH).read_text(encoding="utf-8")
    copy_.write_text(text.replace("version: 9.0.0", "version: 9.1.0", 1), encoding="utf-8")
    assert _pin_problem(copy_, _pins()) == f"{PINS.name} has no digest for compass-checks@9.1.0"


# --- the shape ----------------------------------------------------------------------

_TYPES = {"string": str, "list": list, "map": dict, "boolean": bool}


def test_the_catalogues_are_well_formed_as_the_shipped_parent_was(checks):
    """Each entry holds only fields of its catalogue, every required field, and
    each value of the type the field table gives, as the 8.x layer check of
    the shipped parent required."""
    problems = []
    for name in check_set.CATALOGUES + ("vocabulary",):
        fields = catalogue_spec.FIELDS[name]
        for entry_id, entry in checks[name].items():
            path = f"{name}.{entry_id}"
            if not re.match(catalogue_spec.ID_PATTERN, entry_id):
                problems.append(f"{path}: not a valid id")
            problems += [f"{path}.{k}: not a field" for k in entry if k not in fields]
            problems += [f"{path}: missing {f}" for f, spec in fields.items()
                         if spec["required"] and f not in entry]
            for key, value in entry.items():
                want = _TYPES.get((fields.get(key) or {}).get("type"))
                if want is not None and not isinstance(value, want):
                    problems.append(f"{path}.{key}: expected {want.__name__}")
    assert problems == []


@pytest.mark.parametrize("change, message", [
    (lambda d: d["gates"]["G1"].__setitem__("locked", True), "gates.G1 holds 'locked'"),
    (lambda d: d.__setitem__("artifacts", {}), "unknown key 'artifacts'"),
    (lambda d: d.pop("evidence_types"), "missing key 'evidence_types'"),
    (lambda d: d.__setitem__("id", "default"), "id must be 'compass-checks'"),
    (lambda d: d["never_waived"].append("gates.G9"), "never_waived names 'gates.G9'"),
    (lambda d: d["optional"].__setitem__("rules", {}), "optional entry 'rules'"),
])
def test_a_file_of_the_wrong_shape_is_refused(tmp_path, change, message):
    doc = check_set.load()
    change(doc)
    file = tmp_path / "check-set.yml"
    file.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(CompassError, match=re.escape(message)):
        check_set.load(str(file))


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(CompassError, match="is missing"):
        check_set.load(str(tmp_path / "check-set.yml"))


def test_never_waived_is_the_hard_lock_of_the_default():
    """The 8.x default's hard locks (`locks.hard` of the preset 9.0.0 removed),
    by the decision 2026-10-06-locks-allow-tightening-and-g5-is-hard, and the ship
    approval of #355: the typed approval is already how a person excuses a
    missing review."""
    assert check_set.load()["never_waived"] == ["checks.human-approval-present",
                                                "checks.ship-approval-present", "gates.G5"]


def test_the_optional_agent_review_is_the_block_the_guide_gives_and_does_not_run(checks):
    """ADR-090 decision 7: the shipped set runs no judged check. The block a project
    turned the agent review on with in 8.x is held under `optional`, for the
    `agent_review` setting the guide gives, and `resolved` leaves it out."""
    text = (ROOT / "docs" / "judged-checks.md").read_text(encoding="utf-8")
    section = text.split("## An agent review", 1)[1].split("\n## ", 1)[0]
    block = yaml.safe_load(section.split("```yaml", 1)[1].split("```", 1)[0])
    assert block == {"agent_review": True}
    held = check_set.load()["optional"]["agent_review"]
    body = held["checks"]["agent-review"]
    flat = " ".join(section.split())
    assert body["statement"] in flat
    for key in ("reviewers", "inputs"):
        assert f"`{key}: [{', '.join(body[key])}]`" in flat, key
    for key in ("severity", "on_skipped"):
        assert f"`{key}: {body[key]}`" in flat, key
    assert held["stages"]["ship"]["entry"] == ["agent-review"]
    assert "agent-review" not in checks["checks"]
    assert not any(c.get("kind") == "judged" for c in checks["checks"].values())
    assert "entry" not in checks["stages"]["ship"]


def test_the_file_is_parsed_once_while_it_is_unchanged(tmp_path, monkeypatch):
    """Every resolution reads the check set, and `compass flow` resolves each
    issue on the board, so a parse per call made the board ten times slower.
    The file is parsed once per version of its bytes; each call gets a copy."""
    file = tmp_path / "check-set.yml"
    shutil.copy(check_set.path(), file)
    parsed = []
    real = check_set.load_yaml_strict
    monkeypatch.setattr(check_set, "load_yaml_strict",
                        lambda path: parsed.append(path) or real(path))
    first = check_set.load(str(file))
    first["gates"].clear()
    assert check_set.load(str(file))["gates"], "a caller's change reached the next caller"
    assert len(parsed) == 1, parsed
    text = file.read_text(encoding="utf-8")
    file.write_text(text.replace("id: compass-checks", "id: other", 1), encoding="utf-8")
    with pytest.raises(CompassError, match="id must be 'compass-checks'"):
        check_set.load(str(file))
    assert len(parsed) == 2, parsed


def test_resolved_is_a_copy(checks):
    first = check_set.resolved()
    first["gates"].clear()
    assert check_set.resolved()["gates"] == checks["gates"]


def test_the_gates_checks_and_evidence_types_are_counted():
    checks = check_set.resolved()
    assert (len(checks["gates"]), len(checks["checks"]), len(checks["evidence_types"])) == \
        (16, 34, 17)
