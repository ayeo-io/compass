"""Each built-in check implementation is a versioned registry entry.

A configuration names its checks by implementation id, and the CLI runs the
implementation it ships. Recording the id does not preserve the behaviour, so
each implementation carries a version and a fixture corpus (ADR-038). The
build fails when a corpus verdict changes and the major version does not.

The claim is narrow. Across majors the CLI refuses (a later increment, since
it needs stored generations). Within a major, compatibility is shown on the
corpus cases only; a change of behaviour that no case exercises is not
detected. Each corpus case is built by `tests/check_corpus_runner.py`, the
registry's implementation runs on it, and the computed verdict is compared
with the case's `expected.yml`; the lock digest is taken from the computed
verdicts, so a label cannot drift from what the check does.

Scenario ids: `CR-1` to `CR-5` (issue `check-registry`).
"""
from __future__ import annotations

import dataclasses
import hashlib
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import check_registry  # noqa: E402
from compass_pkg.check_cmd import CHECK_FNS  # noqa: E402
from compass_pkg.policy import _lint_errors_guardrails  # noqa: E402

import check_corpus_runner as runner  # noqa: E402

CORPUS = ROOT / "tests" / "fixtures" / "check-corpus"
LOCK = CORPUS / "versions.lock.yml"
PROOFS = ROOT / "tests" / "mutation_proofs.yml"
VERDICTS = ("pass", "fail", "nothing-to-check")


def _labels(impl: str, root: Path = CORPUS) -> dict[str, dict]:
    """The `expected.yml` of every case of one implementation, by case name."""
    base = root / impl
    return {d.name: yaml.safe_load((d / "expected.yml").read_text(encoding="utf-8"))
            for d in sorted(base.iterdir()) if (d / "expected.yml").is_file()}


def label_problems(scratch: Path, root: Path = CORPUS) -> list[str]:
    """Each case whose computed verdict differs from its label, or that has
    no label or no builder."""
    problems = []
    for impl in check_registry.REGISTRY:
        labels = _labels(impl, root)
        computed = runner.computed_verdicts(impl, scratch)
        for name in sorted(set(labels) | set(computed)):
            if name not in labels or name not in computed:
                problems.append(f"{impl}/{name} needs both a label and a builder")
            elif labels[name]["verdict"] != computed[name]:
                problems.append(f"{impl}/{name} is labelled "
                                f"{labels[name]['verdict']} but computes "
                                f"{computed[name]}")
    return problems


def verdict_digest(impl: str, verdicts: dict[str, str]) -> str:
    """Digest of the computed verdicts only, so rewording an `input` line is
    not a change of behaviour, and relabelling a case does not move it."""
    lines = "\n".join(f"{impl}/{name}:{verdict}"
                      for name, verdict in sorted(verdicts.items()))
    return hashlib.sha256(lines.encode("utf-8")).hexdigest()


def current_digests(scratch: Path) -> dict[str, str]:
    return {impl: verdict_digest(impl, runner.computed_verdicts(impl, scratch))
            for impl in check_registry.REGISTRY}


def lock_problems(versions: dict[str, str], digests: dict[str, str],
                  lock: dict[str, dict]) -> list[str]:
    """ADR-038's build rule, one line per problem, naming the implementation.

    `versions` and `digests` are what the code and corpus say now; `lock` is
    what the last change recorded."""
    problems = []
    for impl, version in sorted(versions.items()):
        locked = lock.get(impl)
        if locked is None:
            problems.append(f"{impl} is not in the lock file")
            continue
        major, locked_major = (int(version.split(".")[0]),
                               int(str(locked["version"]).split(".")[0]))
        if major > locked_major:
            problems.append(
                f"{impl} is at major {major} but the lock file records "
                f"{locked_major}; update the lock file in the same change")
        elif major < locked_major:
            problems.append(
                f"{impl} is at major {major} but the lock file records "
                f"{locked_major}; a major never goes back")
        elif digests[impl] != locked["verdicts"]:
            problems.append(
                f"{impl} verdicts changed and its major stayed at {major}; "
                f"bump the major and update the lock file")
    for impl in sorted(set(lock) - set(versions)):
        problems.append(f"{impl} is in the lock file but not in the registry")
    return problems


# --- the registry (`CR-1`, `CR-2`) -----------------------------------------------

def test_cr_1_one_versioned_entry_per_implementation_and_check_fns_derived():
    proofs = {e["check"] for e in yaml.safe_load(PROOFS.read_text(encoding="utf-8"))}
    assert set(check_registry.REGISTRY) == proofs and len(proofs) == 22
    for name, entry in check_registry.REGISTRY.items():
        assert entry.version == "1.0.0", name
        assert isinstance(entry.params_spec, dict), name
        assert set(entry.tighter) <= set(entry.params_spec), name
        for param in entry.params_spec:
            assert entry.tighter.get(param, "none") in check_registry.TIGHTER
        assert entry.executes_project_code is (name == "command-passes"), name
    assert set(check_registry.REGISTRY["command-passes"].params_spec) == {
        "command", "script", "args", "timeout_seconds"}
    assert check_registry.REGISTRY["suite-passed"].params_spec == {}
    assert CHECK_FNS == {n: e.fn for n, e in check_registry.REGISTRY.items()}
    assert CHECK_FNS is check_registry.CHECK_FNS


def test_cr_2_the_registry_answers_the_installed_version_and_major():
    assert check_registry.installed_version("suite-passed") == "1.0.0"
    assert check_registry.installed_major("suite-passed") == 1
    assert check_registry.installed_version("no-such-check") is None
    assert check_registry.installed_major("no-such-check") is None


# --- the corpus (`CR-3`) ----------------------------------------------------------

def test_cr_3_every_implementation_has_a_verdict_only_corpus():
    for name, entry in check_registry.REGISTRY.items():
        assert (ROOT / entry.corpus) == CORPUS / name, name
        labels = _labels(name)
        assert {c["verdict"] for c in labels.values()} <= set(VERDICTS), name
        assert len(labels) >= 2, name
        # Verdict only: a detail text here would make a rewording look like
        # a change of behaviour.
        for case in labels.values():
            assert set(case) == {"verdict", "input"}, name


def test_cr_3_each_case_computes_the_verdict_its_label_records(tmp_path):
    assert label_problems(tmp_path) == []


def test_cr_3_a_false_label_is_reported_by_case(tmp_path):
    import shutil
    copy = tmp_path / "corpus"
    shutil.copytree(CORPUS, copy)
    label = copy / "suite-passed" / "broken" / "expected.yml"
    label.write_text(label.read_text().replace("verdict: fail", "verdict: pass"))
    problems = label_problems(tmp_path / "scratch", copy)
    assert problems == ["suite-passed/broken is labelled pass but computes fail"]


# --- the lock file (`CR-4`) -------------------------------------------------------

def _now(scratch):
    versions = {n: e.version for n, e in check_registry.REGISTRY.items()}
    return versions, current_digests(scratch)


def _locked(versions, digests):
    return {n: {"version": versions[n], "verdicts": digests[n]} for n in versions}


def test_cr_4_the_committed_lock_matches_the_registry_and_computed_verdicts(tmp_path):
    versions, digests = _now(tmp_path)
    lock = yaml.safe_load(LOCK.read_text(encoding="utf-8"))["implementations"]
    assert lock_problems(versions, digests, lock) == []


def test_cr_4_a_changed_implementation_verdict_fails_and_names_it(tmp_path, monkeypatch):
    versions, digests = _now(tmp_path / "before")
    lock = _locked(versions, digests)
    # The planted change: the implementation now passes whatever it is given,
    # with no label edited and no version bumped.
    entry = check_registry.REGISTRY["suite-passed"]
    monkeypatch.setitem(check_registry.REGISTRY, "suite-passed",
                        dataclasses.replace(entry, fn=lambda task, task_dir: (True, "")))
    problems = lock_problems(versions, current_digests(tmp_path / "after"), lock)
    assert len(problems) == 1 and problems[0].startswith("suite-passed ")
    assert "major" in problems[0]


def test_cr_4_a_higher_major_than_the_lock_fails_until_the_lock_is_updated(tmp_path):
    versions, digests = _now(tmp_path)
    lock = _locked(versions, digests)
    bumped = dict(versions, **{"suite-passed": "2.0.0"})
    problems = lock_problems(bumped, digests, lock)
    assert len(problems) == 1 and "update the lock file" in problems[0]
    updated = dict(lock, **{"suite-passed": {"version": "2.0.0",
                                             "verdicts": digests["suite-passed"]}})
    assert lock_problems(bumped, digests, updated) == []


def test_cr_4_a_lower_major_than_the_lock_fails(tmp_path):
    versions, digests = _now(tmp_path)
    lock = _locked(versions, digests)
    lock["suite-passed"]["version"] = "2.0.0"
    problems = lock_problems(versions, digests, lock)
    assert len(problems) == 1 and "never goes back" in problems[0]


# --- policy lint (`CR-5`) ---------------------------------------------------------

def _policy(name, decl):
    return {"defaults": [{"id": "G9", "checks": [name]}], "checks": {name: decl}}


def test_cr_5_lint_refuses_an_impl_the_registry_does_not_hold_by_name():
    errs = _lint_errors_guardrails(
        _policy("suite-passed", {"description": "x", "impl": "no-such-impl"}))
    assert any("no-such-impl" in e and "registry" in e and "G9" in e
               for e in errs), errs


def test_cr_5_lint_accepts_a_registered_impl_and_a_check_with_none():
    assert _lint_errors_guardrails(
        _policy("suite-passed", {"description": "x", "impl": "suite-passed"})) == []
    assert _lint_errors_guardrails(
        _policy("suite-passed", {"description": "x"})) == []


@pytest.mark.parametrize("decl", ["a string", ["a", "list"]])
def test_cr_5_lint_refuses_a_check_declared_as_a_string_or_list_by_name(decl):
    errs = _lint_errors_guardrails(_policy("suite-passed", decl))
    assert any("suite-passed" in e and "mapping" in e for e in errs), errs


def test_cr_5_an_impl_on_a_default_check_does_not_change_what_runs(
        run_cli, edit_governance, make_task):
    """A project's guardrails.yml must not redirect a default check to a
    weaker implementation. `impl:` is read by lint only until stored
    generations and locks decide who may choose an implementation."""
    with edit_governance("guardrails.yml") as gr:
        gr["checks"]["suite-passed"]["impl"] = "spike-no-production-changes"
    make_task("redirect-probe", {
        "assessment": {"risk": "contained", "familiarity": "brownfield-mapped",
                       "size": "small", "intent": "delivery"},
        "delivery_approach": "regular",
        "scenarios": [{"id": "SCN-001", "intent": "INT-1",
                       "tests": ["tests/test_x.py::test_y"]}],
        "gates": [{"id": "verify.correctness", "status": "pending"}],
    })
    r = run_cli("check", "--issue", "redirect-probe")
    assert r.returncode != 0, r
    assert "no test-run evidence" in (r.stdout + r.stderr), r
