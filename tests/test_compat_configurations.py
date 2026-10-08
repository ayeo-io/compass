"""The compatibility contracts under configurations B and C.

"A project with no configuration behaves as 5.6.0" is checked under three
configurations, and each must equal the 5.6.0 baseline:

- A. No configuration: the shipped default alone. The existing contract files
  run this one (`test_compat_contracts.py`, `_4`, `_5`).
- B. An empty overlay: a `compass.yml` holding `schema: 1` and
  `extends: compass:default@6` and nothing else.
- C. A project that carries a copy of the 5.6.0 governance files, read through
  the legacy adapter.

Configuration D (contracts 4 and 5 only) is the settings moved into
`compass.yml`; `test_compat_contract_5.py` runs it, and contract 4 runs it in
its `with-compass-yml` and `with-config` states.

The baselines are the 5.6.0 captures. Nothing here regenerates one. Each
parametrisation has a partner that plants a fault in the configuration builder
and expects a difference, so a contract that cannot fail is caught.

Scenario id: `IDR-10` (issue `init-docs-release`).
"""
from __future__ import annotations

import copy
import os
import shutil
import tempfile
from pathlib import Path

import pytest
import yaml

import compat_baseline as cb
import compat_commands as cc
import compat_hook
from test_compat_contract_5 import _NOT_MOVABLE, move_settings

BC = ("B", "C")
ALL = BC  # A has its own files and reads the policy file directly


@pytest.fixture(scope="module")
def policies(tmp_path_factory):
    return {k: cb.policy_under(k, tmp_path_factory.mktemp(f"policy-{k}"))
            for k in ALL}


# --- contract 1: routing output -----------------------------------------------

def test_the_spelling_map_changes_only_the_three_known_names():
    """An unexpected name must still differ from the baseline."""
    base = {"required_artifacts": ["intent", "launch-readiness"],
            "blocked_phases": [{"phase": "ship", "until": "x"}]}
    mapped = cb.legacy_spelling(base)
    assert mapped["required_artifacts"] == ["intent.md", "launch-readiness.md"]
    assert mapped["blocked_phases"] == [{"phase": "land", "until": "x"}]
    odd = cb.legacy_spelling({"required_artifacts": ["mystery"],
                              "blocked_phases": [{"phase": "plan", "until": "x"}]})
    assert odd["required_artifacts"] == ["mystery"]
    assert odd["blocked_phases"] == [{"phase": "plan", "until": "x"}]


@pytest.mark.parametrize("kind", ALL)
def test_contract_1_routes_as_the_baseline_under(kind, policies):
    header, rows = cb.load_routing()
    differences = cb.routing_differences(policies[kind], header, rows, layered=True)
    assert differences == [], "\n".join(differences[:10])


@pytest.mark.parametrize("kind", BC)
def test_contract_1_under_the_configuration_can_fail(kind, tmp_path):
    header, rows = cb.load_routing()
    planted = cb.policy_under(kind, tmp_path, fault="routing")
    assert cb.routing_differences(planted, header, rows, first_only=True, layered=True), (
        f"a planted routing fault under {kind} went unseen")


# --- contract 2: what each delivery approach owes -----------------------------

@pytest.mark.parametrize("kind", ALL)
def test_contract_2_owes_what_it_owed_under(kind, policies):
    _, rows = cb.load_routing()
    recorded = yaml.safe_load(cb.OWED.read_text(encoding="utf-8"))
    now = [dict(r, result=cb.legacy_spelling(cb.compact(r["assessment"], policies[kind])))
           for r in rows if r["kind"] == "grid"]
    assert cb.owed_by_approach(now) == recorded["owed"]


@pytest.mark.parametrize("kind", BC)
def test_contract_2_under_the_configuration_can_fail(kind, tmp_path):
    _, rows = cb.load_routing()
    recorded = yaml.safe_load(cb.OWED.read_text(encoding="utf-8"))
    planted = cb.policy_under(kind, tmp_path, fault="routing")
    now = [dict(r, result=cb.legacy_spelling(cb.compact(r["assessment"], planted)))
           for r in rows if r["kind"] == "grid"]
    assert cb.owed_by_approach(now) != recorded["owed"]


# --- contracts 3 and 6: verdicts and readability over the archive sample ------

def _recorded():
    import json
    return json.loads(cb.ARCHIVE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def archive_runs():
    """One project per configuration, each a copy of the archive sample with
    the configuration's files added, and the result of running the CLI over
    each issue in it."""
    runs = {}
    made = []
    try:
        for kind in BC:
            root = cb.archive_under(kind)
            made.append(root)
            runs[kind] = cb.archive_results(root)
        yield runs
    finally:
        for root in made:
            shutil.rmtree(root, ignore_errors=True)


@pytest.mark.parametrize("kind", BC)
def test_contract_3_gives_the_recorded_verdicts_under(kind, archive_runs):
    differences = cb.archive_differences(_recorded()["issues"], archive_runs[kind])
    assert differences == [], "\n".join(differences)


@pytest.mark.parametrize("kind", BC)
def test_contract_6_every_sampled_issue_stays_readable_under(kind, archive_runs):
    unreadable = {slug: r for slug, r in archive_runs[kind].items()
                  if r["lint_exit"] or r["receipt_exit"]}
    assert unreadable == {}


@pytest.mark.parametrize("kind", BC)
def test_contract_3_under_the_configuration_can_fail(kind):
    recorded = _recorded()["issues"]
    slug = next(s for s, r in recorded.items()
                if r["verdicts"].get("suite-passed") == "pass")
    root = cb.archive_under(kind, fault="broken")
    try:
        now = cb.archive_results(root, only={slug})
    finally:
        shutil.rmtree(root, ignore_errors=True)
    assert cb.archive_differences({slug: recorded[slug]}, now), (
        f"a broken {kind} configuration went unseen")


# --- contract 4: CLI exit codes on the command corpus -------------------------

ENTRIES = cc.load()
CASES = [(e, k) for e in ENTRIES for k in BC if cc.entry_applies(e, k)]


@pytest.fixture(scope="module")
def projects(tmp_path_factory):
    return cc.Projects(tmp_path_factory.mktemp("contract-4-config"))


def test_contract_4_configurations_cover_most_of_the_corpus():
    """The states that already hold a settings file or governance of their own
    are not given another, so the count of what is skipped is stated."""
    for kind in BC:
        applied = [e for e in ENTRIES if cc.entry_applies(e, kind)]
        assert len(applied) >= len(ENTRIES) * 0.7, (kind, len(applied), len(ENTRIES))


@pytest.mark.parametrize("entry,kind", CASES,
                         ids=[f"{k}-{e['id']}" for e, k in CASES])
def test_contract_4_exit_code_matches_the_baseline_under(projects, entry, kind):
    outcome = projects.run(entry, configuration=kind)
    assert cc.differences(entry, outcome) == [], (
        f"{entry['id']} under {kind}: {cc.differences(entry, outcome)}\n"
        f"stdout:\n{outcome.stdout}\nstderr:\n{outcome.stderr}")


@pytest.mark.parametrize("kind", BC)
def test_contract_4_under_the_configuration_can_fail(projects, kind):
    """Build the state cleanly, then break the configuration the builder added,
    and run a command that passed at 5.6.0 and reads the configuration."""
    entry = next(e for e in ENTRIES if e["id"] == "policy-lint-shipped")
    assert entry["exit"] == 0
    root = projects.fresh(entry["project"], kind)
    cb.build_configuration(kind, root, "broken")
    outcome = cc.run_in(root, projects.env, entry["argv"])
    assert cc.differences(entry, outcome), (
        f"a broken {kind} configuration went unseen:\n{outcome.stdout}{outcome.stderr}")


# --- contract 5: pre-tool hook decisions --------------------------------------

import test_compat_contract_5 as c5  # noqa: E402

MOVABLE = [e for e in c5.ENTRIES if e["state"] not in _NOT_MOVABLE]


def with_configuration(kind, fault=None):
    """A mutation for a hook corpus project. B holds the settings in a
    `compass.yml` that extends the default; C keeps `.compass/config.yml` and
    adds the 5.6.0 governance copy beside it."""
    def mutate(project):
        if not (project / ".compass").exists():
            return          # a project that never opted in
        if kind == "B":
            move_settings(project)
            moved = project / "compass.yml"
            try:
                data = yaml.safe_load(moved.read_text()) if moved.exists() else None
            except yaml.YAMLError:
                data = None     # a file that does not parse stays as moved
            if isinstance(data, dict):
                moved.write_text(yaml.safe_dump(
                    {"schema": 1, "extends": "compass:default@6",
                     **{k: v for k, v in data.items() if k != "schema"}},
                    sort_keys=False))
                if fault == "drop-settings":
                    moved.write_text("schema: 1\nextends: compass:default@6\n")
        else:
            cb.add_governance_copy(project)
            if fault == "drop-settings":
                (project / ".compass" / "config.yml").write_text(
                    "version: 1.0.0\nmode: enforced\n")
    return mutate


@pytest.mark.parametrize("kind", BC)
@pytest.mark.parametrize("entry", MOVABLE, ids=[e["id"] for e in MOVABLE])
def test_contract_5_decides_as_recorded_under(c5_install, entry, kind):
    if entry["state"] in compat_hook.NEEDS_NON_ROOT and os.geteuid() == 0:
        pytest.skip("the root user reads a file whose permissions forbid it")
    hook_root, base = c5_install
    exit_code, code, _out, err = compat_hook.run_entry(
        hook_root, base, entry, mutate=with_configuration(kind))
    assert (exit_code, code) == (entry["exit"], entry["code"]), err
    if "stderr_contains" in entry:
        assert entry["stderr_contains"] in err
    if "stderr_excludes" in entry:
        assert entry["stderr_excludes"] not in err


@pytest.mark.parametrize("kind", BC)
def test_contract_5_under_the_configuration_can_fail(c5_install, kind):
    hook_root, base = c5_install
    entry = next(e for e in c5.ENTRIES if e["id"] == "edit-glob-dir-match-no-red")
    exit_code, _c, _o, _e = compat_hook.run_entry(
        hook_root, base, entry, mutate=with_configuration(kind, "drop-settings"))
    assert exit_code != entry["exit"]


@pytest.fixture(scope="module")
def c5_install():
    base = Path(tempfile.mkdtemp(prefix="c5cfg-"))
    yield compat_hook.install(base / "framework"), base
    shutil.rmtree(base, ignore_errors=True)
