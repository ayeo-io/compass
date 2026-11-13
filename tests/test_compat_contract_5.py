"""Contract 5: the pre-tool hook's decisions on a recorded corpus of tool calls.

Version 6.0.0 moves the two settings the hook reads from the project's
`.compass/config.yml` - `enforcement.code_globs` and `initialised` - into a
new project file and a state file. The hook's decisions must not change with
them. A user who upgrades must find that the same edit is allowed or refused
for the same reason as before.

The corpus in `tests/fixtures/compat/contract-5-hook.yml` was captured once
from the 5.6.0 hook by `tests/compat_hook.py`. This test runs every entry
against the hook as it is now and compares the exit status, the refusal code
and any recorded phrase. The builder writes each project in the 9.0.0 shape
(`compass.yml`, `initialized` in the state file, and `delivery_approach` in
the manifest); a second run puts the settings back into the 8.x
`.compass/config.yml`, which 9.x still reads. The corpus is never regenerated from new code: a
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
    assert (exit_code, code) == (entry["exit"], compat_hook.recorded_code(entry)), err
    if "stderr_contains" in entry:
        assert entry["stderr_contains"] in err
    if "stderr_excludes" in entry:
        assert entry["stderr_excludes"] not in err


def test_contract_5_can_fail_when_code_globs_is_dropped(install):
    """Proves the comparison above can fail. The recorded entry blocks an
    edit only because `enforcement.code_globs` names `packaging/**`. With
    that key removed, as a migration that lost it would, the same call must
    give a different decision from the one recorded. A hook that read only
    the old file would also allow the edit, so this fails for it too."""
    hook_root, base = install
    entry = next(e for e in ENTRIES if e["id"] == "edit-glob-dir-match-no-red")
    assert entry["decision"] == "block"

    def drop_globs(project):
        (project / "compass.yml").write_text("schema: 1\nadoption: enforced\n")

    exit_code, _code, _out, _err = compat_hook.run_entry(
        hook_root, base, entry, mutate=drop_globs)
    assert exit_code != entry["exit"]


# SH-7 and VD-037: the same corpus, for a project that still keeps its settings
# and its state in the 8.x `.compass/config.yml`. 9.x reads that file, so the
# recorded decisions must hold for it as well.

#: A state whose settings file cannot be read at all cannot be moved.
_NOT_MOVABLE = {"config-unreadable"}


def move_settings(project):
    """Turn the project's `.compass/config.yml` into what an 8.x migration
    wrote: the settings in `compass.yml` (`mode` renamed `adoption`), and the
    state keys, as stored, in the state file. A file that does not parse is
    moved whole, so it stays broken."""
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
    state = {k: data.pop(k) for k in (compat_hook._OLD_STATE_KEY, "records_signed_since")
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
def test_contract_5_decides_the_same_with_settings_in_old_config_yml(install, entry):
    hook_root, base = install
    exit_code, code, _out, err = compat_hook.run_entry(
        hook_root, base, entry, mutate=compat_hook.to_old_config)
    assert (exit_code, code) == (entry["exit"], compat_hook.recorded_code(entry)), err
    if "stderr_contains" in entry:
        assert entry["stderr_contains"] in err
    if "stderr_excludes" in entry:
        assert entry["stderr_excludes"] not in err


def test_contract_5_the_old_config_run_has_no_9_0_0_files(install):
    """The run above tests the old file only if the builder's `compass.yml`
    and state file are gone after `to_old_config`."""
    hook_root, base = install
    seen = []

    def convert_and_look(project):
        compat_hook.to_old_config(project)
        seen.append(((project / "compass.yml").exists(),
                     (project / ".compass" / "state.yml").exists(),
                     (project / ".compass" / "config.yml").exists()))

    for entry in MOVABLE:
        if entry["state"] != "not-opted-in":
            compat_hook.run_entry(hook_root, base, entry, mutate=convert_and_look)
    assert seen and set(seen) == {(False, False, True)}


def test_contract_5_the_old_config_run_can_fail_when_the_hook_ignores_it(install):
    """A hook that read only `compass.yml` would allow the glob entry once the
    settings were back in the old file without their globs."""
    hook_root, base = install
    entry = next(e for e in ENTRIES if e["id"] == "edit-glob-dir-match-no-red")

    def old_file_without_globs(project):
        compat_hook.to_old_config(project)
        (project / ".compass" / "config.yml").write_text(
            "version: 1.0.0\nmode: enforced\n")

    exit_code, _code, _out, _err = compat_hook.run_entry(
        hook_root, base, entry, mutate=old_file_without_globs)
    assert exit_code != entry["exit"]


def test_contract_5_every_built_compass_yml_carries_the_schema_marker(install):
    """Migration writes `schema:` into each `compass.yml` it creates, because
    that key is how a project holding both files tells Compass's file from
    another product's. The builder stands in for a 9.0.0 project, so it must
    write the key, or the corpus would not test what such a project holds.
    A file that does not parse is written whole and has no key to check."""
    import yaml

    hook_root, base = install
    seen = []

    def record(project):
        built = project / "compass.yml"
        if built.exists():
            try:
                seen.append(yaml.safe_load(built.read_text()))
            except yaml.YAMLError:
                pass

    for entry in MOVABLE:
        compat_hook.run_entry(hook_root, base, entry, mutate=record)
    built = [data for data in seen if isinstance(data, dict)]
    assert built, "no entry built a settings file"
    assert [d for d in built if "schema" not in d] == []


def test_contract_5_the_no_approach_state_alone_lacks_the_approach_key(tmp_path):
    """The hook reads the manifest's `delivery_approach` key alone, so the
    `no-approach` entry refuses only because its state leaves the key out,
    and every other state with an issue writes it."""
    import yaml

    seen = {}
    for state in compat_hook.STATES:
        project, _outside = compat_hook.build(state, tmp_path)
        manifest = project / ".compass" / "work" / compat_hook.SLUG / "manifest.yml"
        if manifest.exists():
            seen[state] = "delivery_approach" in yaml.safe_load(manifest.read_text())
        built = project / "compass.yml"
        if built.exists():
            built.chmod(0o644)
    assert seen and seen == {state: state != "no-approach" for state in seen}
    assert seen["no-approach"] is False


# --- the refusal code is US spelling, the recorded pin is not -------------------

#: The entries that record the old refusal code. The code pin stays as 5.6.0
#: wrote it; the comparison reads it through `compat_hook.RENAMED_CODES`.
_OLD_CODE_ENTRIES = [e for e in ENTRIES
                     if compat_hook.recorded_code(e) != e["code"]]


def _empty_overlay(project):
    """Configuration B: the settings and the state in the old file, beside an
    empty `compass.yml`."""
    compat_hook.to_old_config(project)
    if (project / ".compass").exists():
        (project / "compass.yml").write_text("schema: 1\n")


def _migrated(project):
    """Configuration D: the files `compass policy migrate --apply` wrote on 8.x
    for a 5.6.0 `.compass/config.yml`. 9.0.0 removed that command (ADR-094), so
    the files are written here as 8.0.4 wrote them: the old file copied to
    `.compass/legacy/`, the settings moved into a `compass.yml` that extends the
    shipped default, and the state moved to the state file."""
    import shutil

    import yaml

    compat_hook.to_old_config(project)
    old = project / ".compass" / "config.yml"
    if old.exists():
        legacy = project / ".compass" / "legacy"
        legacy.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old, legacy / "config.yml")
    move_settings(project)
    path = project / "compass.yml"
    if not path.exists():
        return
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError:
        return
    if isinstance(data, dict):
        data = {"schema": data.pop("schema", 1), "extends": "compass:default@8", **data}
        path.write_text(yaml.safe_dump(data, sort_keys=False))


#: A (the 9.0.0 files the builder writes), the 8.x `.compass/config.yml`
#: alone, B (that file beside an empty `compass.yml`) and D (the files an 8.x
#: migration wrote).
_CONFIGS = {"A": None, "old": compat_hook.to_old_config, "B": _empty_overlay,
            "D": _migrated}


def test_trc_058_the_old_code_is_read_under_every_configuration(install):
    hook_root, base = install
    assert len(_OLD_CODE_ENTRIES) >= 4
    for name, mutate in _CONFIGS.items():
        for entry in _OLD_CODE_ENTRIES:
            exit_code, code, _out, err = compat_hook.run_entry(
                hook_root, base, entry, mutate=mutate)
            assert (exit_code, code) == (entry["exit"], compat_hook.recorded_code(entry)), (
                name, entry["id"], err)
            assert code != entry["code"], (name, entry["id"])


def test_trc_058(install, monkeypatch):
    """Every recorded exit code and refusal code matches, and the comparison
    fails when the old code is no longer in the table."""
    hook_root, base = install
    for entry in ENTRIES:
        if entry["state"] in compat_hook.NEEDS_NON_ROOT and os.geteuid() == 0:
            continue
        exit_code, code, _out, err = compat_hook.run_entry(hook_root, base, entry)
        assert (exit_code, code) == (entry["exit"], compat_hook.recorded_code(entry)), (
            entry["id"], err)
    # Empty the table: the recorded code is then no longer read as the current
    # one, so the comparison reports the difference.
    monkeypatch.setattr(compat_hook, "RENAMED_CODES", {})
    entry = _OLD_CODE_ENTRIES[0]
    exit_code, code, _out, _err = compat_hook.run_entry(hook_root, base, entry)
    assert (exit_code, code) != (entry["exit"], compat_hook.recorded_code(entry))
