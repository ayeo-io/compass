"""Contract 5: the pre-tool hook's decisions on a recorded corpus of tool calls.

Version 6.0.0 moves the two settings the hook reads from the project's
`.compass/config.yml` - `enforcement.code_globs` and `initialised` - into a
new project file and a state file. The hook's decisions must not change with
them. A user who upgrades must find that the same edit is allowed or refused
for the same reason as before.

The corpus in `tests/fixtures/compat/contract-5-hook.yml` was captured once
from the 5.6.0 hook by `tests/compat_hook.py`. This test runs every entry
against the hook as it is now and compares the exit status, the refusal code
and any recorded phrase. The corpus is never regenerated from new code: a
regenerated corpus would agree with whatever the new code does, and the
contract would then check nothing.

Scenario id: `TRC-001` (issue `compat-hook-corpus`).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

import compat_hook

ENTRIES = compat_hook.load()


@pytest.fixture(scope="module")
def install():
    """One copy of the framework for every entry. Each entry still builds its
    own project, so no run sees another run's state."""
    base = Path(tempfile.mkdtemp(prefix="c5run-"))
    yield compat_hook.install(base / "framework"), base
    shutil.rmtree(base, ignore_errors=True)


def test_contract_5_the_corpus_covers_every_state():
    """A state no entry uses is a state the contract does not check."""
    assert {entry["state"] for entry in ENTRIES} == set(compat_hook.STATES)


@pytest.mark.parametrize("entry", ENTRIES, ids=[e["id"] for e in ENTRIES])
def test_contract_5_the_hook_decides_as_recorded(install, entry):
    if entry["state"] in compat_hook.NEEDS_NON_ROOT and os.geteuid() == 0:
        pytest.skip("the root user reads a file whose permissions forbid it")
    hook_root, base = install
    exit_code, code, _out, err = compat_hook.run_entry(hook_root, base, entry)
    assert (exit_code, code) == (entry["exit"], entry["code"]), err
    if "stderr_contains" in entry:
        assert entry["stderr_contains"] in err
    if "stderr_excludes" in entry:
        assert entry["stderr_excludes"] not in err


def test_contract_5_can_fail_when_code_globs_is_dropped(install):
    """Proves the comparison above can fail. The recorded entry blocks an
    edit only because `enforcement.code_globs` names `packaging/**`. With
    that key removed, as a migration that lost it would, the same call must
    give a different decision from the one recorded."""
    hook_root, base = install
    entry = next(e for e in ENTRIES if e["id"] == "edit-glob-dir-match-no-red")
    assert entry["decision"] == "block"

    def drop_globs(project):
        (project / ".compass" / "config.yml").write_text(
            "version: 1.0.0\nmode: enforced\n")

    exit_code, _code, _out, _err = compat_hook.run_entry(
        hook_root, base, entry, mutate=drop_globs)
    assert exit_code != entry["exit"]


# SH-7: the same corpus, for a project that keeps its settings in `compass.yml`
# and the state file. The recorded decisions are unchanged: the move
# must not change what the hook allows or refuses.

#: A state whose settings file cannot be read at all cannot be moved.
_NOT_MOVABLE = {"config-unreadable"}


def move_settings(project):
    """Turn the project's `.compass/config.yml` into what a migrated project
    holds: the settings in `compass.yml` (`mode` renamed `adoption`), and
    `initialised` and `records_signed_since` in the state file. A file
    that does not parse is moved whole, so it stays broken."""
    import yaml

    old = project / ".compass" / "config.yml"
    if not old.exists():          # a project that never opted in
        return
    text = old.read_text()
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        data = None
    old.unlink()
    if not isinstance(data, dict):
        (project / "compass.yml").write_text(text)
        return
    state = {k: data.pop(k) for k in ("initialised", "records_signed_since")
             if k in data}
    if "mode" in data:
        data["adoption"] = data.pop("mode")
    # `schema:` first, as migration writes it: it marks the file as Compass's.
    data = {"schema": 1, **data}
    (project / "compass.yml").write_text(yaml.safe_dump(data, sort_keys=False))
    if state:
        (project / ".compass" / "state.yml").write_text(
            yaml.safe_dump(state, sort_keys=False))


MOVABLE = [e for e in ENTRIES if e["state"] not in _NOT_MOVABLE]


@pytest.mark.parametrize("entry", MOVABLE, ids=[e["id"] for e in MOVABLE])
def test_contract_5_decides_the_same_with_settings_in_compass_yml(install, entry):
    hook_root, base = install
    exit_code, code, _out, err = compat_hook.run_entry(
        hook_root, base, entry, mutate=move_settings)
    assert (exit_code, code) == (entry["exit"], entry["code"]), err
    if "stderr_contains" in entry:
        assert entry["stderr_contains"] in err
    if "stderr_excludes" in entry:
        assert entry["stderr_excludes"] not in err


def test_contract_5_every_moved_compass_yml_carries_the_schema_marker(install):
    """Migration writes `schema:` into each `compass.yml` it creates, because
    that key is how a project holding both files tells Compass's file from
    another product's. The conversion above stands in for migration, so it
    must write the key, or the corpus would not test what migration makes.
    A file that does not parse is moved whole and has no key to check."""
    import yaml

    hook_root, base = install
    seen = []

    def move_and_record(project):
        move_settings(project)
        moved = project / "compass.yml"
        if moved.exists():
            try:
                seen.append(yaml.safe_load(moved.read_text()))
            except yaml.YAMLError:
                pass

    for entry in MOVABLE:
        compat_hook.run_entry(hook_root, base, entry, mutate=move_and_record)
    moved = [data for data in seen if isinstance(data, dict)]
    assert moved, "no entry moved a settings file"
    assert [d for d in moved if "schema" not in d] == []


def test_contract_5_the_moved_corpus_can_fail_when_the_hook_ignores_compass_yml(
        install):
    """A hook that read only the old file would allow the glob entry once the
    settings had moved, so the moved run above would then differ."""
    hook_root, base = install
    entry = next(e for e in ENTRIES if e["id"] == "edit-glob-dir-match-no-red")

    def move_and_forget_the_globs(project):
        move_settings(project)
        (project / "compass.yml").write_text("adoption: enforced\n")

    exit_code, _code, _out, _err = compat_hook.run_entry(
        hook_root, base, entry, mutate=move_and_forget_the_globs)
    assert exit_code != entry["exit"]
