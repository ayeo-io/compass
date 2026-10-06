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
