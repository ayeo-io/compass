"""Every check Compass ships has a mutation proof on record.

The mutation-proof strategy (`governance/strategies.md`) accepts a guard
only on a demonstrated failure: break what it guards, watch it fail,
restore, watch it pass. In August a one-off script
found 20 of 38 checks with no proof at all. It was withdrawn, because keeping
it meant this repository declaring a project guardrail, and every adopter
would have received it. The decision of 5 October 2026
(`governance/decisions/2026-10-05-no-project-guardrails-in-this-repository.md`)
brings the check back here, as a test, so it reaches no adopter.

A proof is a pair of tests: one feeds the check a broken input and asserts
it fails, the other (or the same one) asserts it passes once the input is
put right. Both run on every suite, so a proof cannot go out of date without
the suite saying so. `tests/mutation_proofs.yml` names the pair for each check
under `checks:` in the default preset's `checks.yml`, which
`governance/guardrails.yml` is generated from. Whether a proof is real -
whether the test truly breaks what the check guards - no machine can tell,
and the reviewer judges it.

Scenario ids MPR-1 to MPR-6 (issue `mutation-proof-register`).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import legacy_views  # noqa: E402

GUARDRAILS = ROOT / "governance" / "guardrails.yml"
PRESET = ROOT / "governance" / "presets" / "default"
REGISTER = ROOT / "tests" / "mutation_proofs.yml"
REQUIRED = ("broken", "fails", "restores")


def _checks(preset=PRESET, guardrails=GUARDRAILS):
    """The shipped checks, by name. The preset is the source of the shipped
    defaults, so it is read first; the generated guardrails view answers only
    when the preset's checks file is absent. A human check has no
    implementation to break, so it has no mutation proof and is left out."""
    checks_file = preset / "checks.yml"
    if checks_file.is_file():
        data = yaml.safe_load(checks_file.read_text(encoding="utf-8")) or {}
        return {name: {"description": body.get("statement")}
                for name, body in (data.get("checks") or {}).items()
                if legacy_views.has_implementation(body)}
    data = yaml.safe_load(guardrails.read_text(encoding="utf-8")) or {}
    return data.get("checks") or {}


def _register(register=REGISTER):
    return yaml.safe_load(register.read_text(encoding="utf-8")) or []


def _test_names(path: Path) -> set[str]:
    """Every test function and `Class::method` in a test file, read from its
    syntax tree, so the file is never imported."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.add(f"{node.name}::{sub.name}")
    return names


def _resolves(node_id: str, root=ROOT) -> bool:
    """True when `node_id` names a test pytest collects: a `test_` function
    or `Test` class method in a `test_` file under `tests/`. A helper or a
    production function also exists in a file, but runs no assertion."""
    path, _, name = node_id.partition("::")
    file = root / path
    leaf = name.rsplit("::", 1)[-1]
    if not (path.startswith("tests/") and Path(path).name.startswith("test_")
            and leaf.startswith("test_")
            and ("::" not in name or name.startswith("Test"))):
        return False
    return file.is_file() and name in _test_names(file)


def register_problems(checks, entries, root=ROOT) -> list[str]:
    """Each way the register falls short of the checks, one line each,
    naming the check and the field."""
    if not checks:
        return ["the default preset lists no checks, so there is "
                "nothing to compare the register with"]
    problems = []
    by_check = {}
    for entry in entries:
        name = entry.get("check") if isinstance(entry, dict) else None
        if not name:
            problems.append(f"an entry names no check: {entry!r}")
            continue
        if name in by_check:
            problems.append(f"{name}: on record twice")
        by_check[name] = entry
    for name in checks:
        if name not in by_check:
            problems.append(f"{name}: no mutation proof on record")
    for name, entry in by_check.items():
        if name not in checks:
            problems.append(f"{name}: on record, but the default preset has no "
                            f"such check")
            continue
        for field in REQUIRED:
            if not str(entry.get(field) or "").strip():
                problems.append(f"{name}: `{field}` is missing")
        for field in ("fails", "restores"):
            node_id = str(entry.get(field) or "").strip()
            if node_id and not _resolves(node_id, root):
                problems.append(f"{name}: `{field}` names {node_id}, which "
                                f"is not a test in that file")
    return problems


def test_every_shipped_check_has_a_proof_on_record():
    """MPR-1 to MPR-5, against the real files."""
    problems = register_problems(_checks(), _register())
    assert not problems, ("checks without a usable mutation proof:\n  "
                          + "\n  ".join(problems))


def test_the_repository_still_declares_no_guardrail_of_its_own():
    """MPR-6: the proof check lives here so it never reaches adopters."""
    data = yaml.safe_load(GUARDRAILS.read_text(encoding="utf-8"))
    assert data.get("project") == []


# --- the register test can fail, as the mutation-proof strategy asks ---------
# Each case breaks one thing about a register that is otherwise complete and
# asserts the problem is named. The first asserts the complete one is clean,
# so the failures below come from the break, not from the fixture.

_CHECKS = {"alpha": {}, "beta": {}}
_THIS = "tests/test_mutation_proof_register.py"


def _entry(check, **over):
    entry = {"check": check, "broken": "a broken input",
             "fails": f"{_THIS}::test_every_shipped_check_has_a_proof_on_record",
             "restores": f"{_THIS}::test_every_shipped_check_has_a_proof_on_record"}
    entry.update(over)
    return entry


def test_a_complete_register_has_no_problems():
    assert register_problems(_CHECKS, [_entry("alpha"), _entry("beta")]) == []


def test_a_check_with_no_entry_is_named():
    """MPR-1."""
    problems = register_problems(_CHECKS, [_entry("alpha")])
    assert problems == ["beta: no mutation proof on record"]


def test_an_entry_missing_a_field_is_named_with_the_field():
    """MPR-2."""
    problems = register_problems(_CHECKS, [_entry("alpha", broken=""),
                                           _entry("beta")])
    assert problems == ["alpha: `broken` is missing"]


def test_an_entry_for_a_check_that_is_gone_is_named():
    """MPR-3."""
    problems = register_problems(
        _CHECKS, [_entry("alpha"), _entry("beta"), _entry("gamma")])
    assert problems == ["gamma: on record, but the default preset has no such check"]


def test_no_checks_to_compare_is_a_failure_not_a_pass():
    """MPR-4."""
    assert register_problems({}, [_entry("alpha")])


def test_a_proof_naming_a_missing_test_is_named():
    """MPR-5: a proof the suite cannot run is not a proof."""
    problems = register_problems(
        _CHECKS, [_entry("alpha", fails=f"{_THIS}::test_that_does_not_exist"),
                  _entry("beta")])
    assert problems == [f"alpha: `fails` names {_THIS}::test_that_does_not_exist, "
                        f"which is not a test in that file"]


def test_a_proof_naming_a_helper_or_production_code_is_named():
    """MPR-5: a name that exists but runs no assertion is not a proof."""
    helper = "tests/test_consistency_check_passes.py::_issue"
    production = "cli/compass_pkg/checks.py::_check_suite_passed"
    problems = register_problems(
        _CHECKS, [_entry("alpha", fails=helper),
                  _entry("beta", restores=production)])
    assert problems == [
        f"alpha: `fails` names {helper}, which is not a test in that file",
        f"beta: `restores` names {production}, which is not a test in that file"]


def test_a_check_on_record_twice_is_named():
    """MPR-3: a second entry would silently replace the first."""
    problems = register_problems(
        _CHECKS, [_entry("alpha"), _entry("beta"), _entry("alpha")])
    assert problems == ["alpha: on record twice"]
