"""`compass policy update` for a git parent (issue `policy-update-git-parents`).

A project pinned to a commit of a git parent moves to the commit its `@<ref>` now
names. The tests build a local git repository, point `COMPASS_PARENT_REMOTE_BASE`
at its folder and add commits to it, so nothing reaches the network. A script
named `git` on the PATH stands in for a host that cannot be reached.

Scenario ids: `PUG-1` to `PUG-13`. Each test name starts with its scenario id.
"""
from __future__ import annotations

import dataclasses
import datetime
import json
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
from parent_fixtures import REAL_GIT, _git, make_remote  # noqa: E402

CLI = ROOT / "cli" / "compass"
TODAY = datetime.date(2026, 10, 8)

# The parent tightens the regular ceiling from 2 to 1. The project raises it to 5
# and holds a waiver for that.
V1 = {"schema": 1, "owner": "platform-team",
      "approaches": {"regular": {"set": {"subtask_ceiling": 1}}}}
# The waived field's parent value moves from 1 to 2.
MOVED = {"schema": 1, "owner": "platform-team",
         "approaches": {"regular": {"set": {"subtask_ceiling": 2}}}}
# Only the owner changes: no waived field moves.
OTHER = {**V1, "owner": "platform-team-two"}
# The waived field moves, and a different person approves project waivers.
MOVED_APPROVERS = {**MOVED, "approvers": {"project-waiver": ["morgan"]}}

PROJECT = """\
# The project's configuration.
schema: 1
extends: github:acme/bank@main#{sha}   # the team parent
owner: jed72

approaches:
  regular:
    set:
      subtask_ceiling: 5
    waiver:
      reason: Our work splits into more parallel subtasks than the parent allows.
      approved_by: jed72
      approved_on: 2026-10-05
"""

NO_WAIVER = """\
schema: 1
extends: github:acme/bank@main#{sha}
owner: jed72
"""

MAP_FORM = """\
schema: 1
extends:
  from: github:acme/bank@main#{sha}
owner: jed72
"""


def _dump(doc):
    return yaml.safe_dump(doc, sort_keys=False)


class Terminal:
    """The person at the keyboard: it answers each question in turn."""

    def __init__(self, *answers):
        self.answers, self.asked = list(answers), []

    def __call__(self, prompt):
        self.asked.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)


class World:
    """A local remote that holds the parent, and a project pinned to its first commit."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp = tmp_path
        self.base = tmp_path / "remotes"
        self.first = make_remote(self.base, files={"compass.yml": _dump(V1)})
        self.repo = self.base / "acme" / "bank.git"
        monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(self.base))
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
        monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("COMPASS_OFFLINE", raising=False)
        self.root = tmp_path / "project"

    def advance(self, doc, tag=None, annotated=False):
        """Commit `doc` as the parent's `compass.yml` and return the commit's sha."""
        (self.repo / "compass.yml").write_text(_dump(doc), encoding="utf-8")
        _git(self.repo, "commit", "--quiet", "-am", "next")
        if tag and annotated:
            _git(self.repo, "tag", "-a", tag, "-m", tag)
        elif tag:
            _git(self.repo, "tag", tag)
        return _git(self.repo, "rev-parse", "HEAD")

    def project(self, text=PROJECT, sha=None):
        self.root.mkdir(exist_ok=True)
        (self.root / ".compass").mkdir(exist_ok=True)
        (self.root / "compass.yml").write_text(text.format(sha=sha or self.first),
                                               encoding="utf-8")
        return self.root

    def text(self):
        return (self.root / "compass.yml").read_text(encoding="utf-8")

    def cached(self, sha):
        return (self.root / ".compass" / "cache" / "parents" / "acme" / "bank" / sha
                / "compass.yml")


@pytest.fixture
def world(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def _update():
    from compass_pkg import policy_update
    return policy_update


def _run(world, *, yes=False, interactive=False, answers=(), to=None, write=None):
    mod = _update()
    term = Terminal(*answers)
    kw = {} if write is None else {"write": write}
    out = mod.run(world.root, to, yes=yes, interactive=interactive, ask=term,
                  say=lambda line: None, today=TODAY, **kw)
    return out, term


# --- PUG-1: the ref's new commit is fetched and the pin is rewritten ----------------------

def test_pug_1_the_new_commit_is_fetched_and_only_the_pin_changes(world):
    second = world.advance(OTHER)
    world.project()
    out, term = _run(world, yes=True)
    assert (out.status, out.written, out.exit_code) == ("applied", True, 0)
    assert term.asked == []
    assert world.text() == PROJECT.format(sha=second)
    assert world.cached(second).is_file()


def test_pug_1_the_map_form_keeps_its_shape(world):
    second = world.advance(OTHER)
    world.project(MAP_FORM)
    out, _ = _run(world, yes=True)
    assert out.status == "applied"
    assert world.text() == MAP_FORM.format(sha=second)


def test_pug_1_an_annotated_tag_resolves_to_the_commit_it_points_at(world):
    second = world.advance(OTHER, tag="v2", annotated=True)
    tag_object = _git(world.repo, "rev-parse", "v2")
    assert tag_object != second
    world.project(NO_WAIVER.replace("@main", "@v2"))
    out, _ = _run(world, yes=True)
    assert out.status == "applied"
    assert world.text() == NO_WAIVER.replace("@main", "@v2").format(sha=second)


def test_pug_1_resolve_ref_names_a_branch_a_tag_and_no_ref(world):
    from compass_pkg import parents
    second = world.advance(OTHER, tag="light")
    spec = parents.spec_of(f"github:acme/bank@main#{world.first}")
    assert parents.resolve_ref(spec) == second
    assert parents.resolve_ref(spec._replace(ref="light")) == second
    assert parents.resolve_ref(spec._replace(ref="nothing-here")) is None


# --- PUG-2: a ref still at the pin has nothing to do --------------------------------------

def test_pug_2_a_ref_at_the_pin_writes_nothing(world):
    world.project()
    before = world.text()
    out, term = _run(world, yes=False, interactive=True)
    assert (out.status, out.written, out.exit_code) == ("nothing-to-do", False, 0)
    assert term.asked == [] and world.text() == before
    assert "nothing to do" in "\n".join(_update().result_lines(out))


# --- PUG-3: the field-level re-check across the two commits ------------------------------

def test_pug_3_a_waiver_on_a_field_that_moved_is_affected(world):
    world.advance(MOVED)
    world.project()
    made = _update().plan(world.root)
    [waiver] = made.waivers
    assert waiver.status == "invalidated" and waiver.entry == "approaches.regular"
    [change] = waiver.invalidations
    assert (change.field, change.old, change.new, change.project) == ("subtask_ceiling", 1, 2, 5)


def test_pug_3_a_change_elsewhere_in_the_parent_leaves_the_waiver_valid(world):
    world.advance(OTHER)
    world.project()
    made = _update().plan(world.root)
    [waiver] = made.waivers
    assert waiver.status == "kept" and waiver.invalidations == []


# --- PUG-4: terminal re-approval and one atomic write -----------------------------------

def test_pug_4_the_allowed_approver_re_approves_and_the_file_is_written_once(world):
    second = world.advance(MOVED)
    world.project()
    writes = []

    def spy(path, text):
        writes.append(text)
        from compass_pkg.atomic_io import atomic_write_text
        atomic_write_text(path, text)

    out, _ = _run(world, interactive=True, answers=("y", "jed72", "y"), write=spy)
    assert out.status == "applied" and len(writes) == 1
    expected = PROJECT.format(sha=second).replace("approved_on: 2026-10-05",
                                                  f"approved_on: {TODAY}")
    assert world.text() == expected
    assert [v.status for v in out.waivers] == ["reapproved"]


def test_pug_4_the_new_parent_names_who_may_approve(world):
    second = world.advance(MOVED_APPROVERS)
    world.project()
    out, term = _run(world, interactive=True, answers=("y", "jed72", "jed72", "morgan", "y"))
    assert out.status == "applied"
    assert "morgan" in world.text() and "approved_by: jed72" not in world.text()
    assert f"#{second}" in world.text()
    assert "morgan" in term.asked[1]


# --- PUG-5: --yes, no terminal and a declined approval refuse ---------------------------

@pytest.mark.parametrize("kwargs, code", [
    ({"yes": True, "interactive": True, "answers": ("y", "jed72", "y")}, "yes-cannot-reapprove"),
    ({"interactive": False}, "no-terminal"),
    ({"interactive": True, "answers": ("n",)}, "declined"),
    ({"interactive": True, "answers": ("y", "x", "x", "x")}, "declined"),
])
def test_pug_5_a_move_that_cannot_be_approved_is_refused_and_writes_nothing(
        world, kwargs, code):
    world.advance(MOVED)
    world.project()
    before = world.text()
    out, _ = _run(world, **kwargs)
    assert (out.status, out.refusal[0], out.written, out.exit_code) == ("refused", code,
                                                                       False, 1)
    assert world.text() == before


# --- PUG-6: offline is not a refusal -----------------------------------------------------

def _unreachable_git(tmp_path):
    """A `git` that fails the way git fails with no route to the host."""
    bin_dir = tmp_path / "offlinebin"
    bin_dir.mkdir()
    script = bin_dir / "git"
    script.write_text(
        "#!/bin/sh\necho \"fatal: unable to access 'https://github.com/acme/bank.git/': "
        "Could not resolve host: github.com\" >&2\nexit 128\n", encoding="utf-8")
    script.chmod(0o755)
    return bin_dir


def test_pug_6_a_remote_that_cannot_be_reached_is_offline(world, monkeypatch):
    world.advance(OTHER)
    world.project()
    before = world.text()
    monkeypatch.setenv("PATH", f"{_unreachable_git(world.tmp)}:{os.environ['PATH']}")
    out, term = _run(world, yes=True)
    assert (out.status, out.written, out.exit_code) == ("offline", False, 1)
    assert out.refusal[0] == "offline" and term.asked == []
    assert world.text() == before
    lines = "\n".join(_update().result_lines(out))
    assert lines.startswith("offline: ") and "not applied" not in lines


def test_pug_6_compass_offline_never_runs_git(world, monkeypatch):
    world.advance(OTHER)
    world.project()
    monkeypatch.setenv("COMPASS_OFFLINE", "1")
    monkeypatch.setenv("PATH", f"{_unreachable_git(world.tmp)}")      # git would fail anyway
    out, _ = _run(world, yes=True)
    assert out.status == "offline" and "COMPASS_OFFLINE" in out.refusal[1]


def test_pug_6_offline_differs_from_a_refusal_in_the_json(world, monkeypatch):
    world.advance(MOVED)
    world.project()
    refused, _ = _run(world)
    monkeypatch.setenv("COMPASS_OFFLINE", "1")
    offline, _ = _run(world)
    mod = _update()
    assert mod.document(refused)["status"] == "refused"
    assert mod.document(offline)["status"] == "offline"
    assert mod.document(offline)["refusal"]["code"] == "offline"
    assert mod.document(offline)["written"] is False


def test_pug_6_a_pin_that_is_not_cached_cannot_be_compared_offline(world, monkeypatch):
    world.advance(OTHER)
    world.project()
    monkeypatch.setenv("COMPASS_OFFLINE", "1")
    out, _ = _run(world, yes=True)
    assert out.status == "offline" and not world.cached(world.first).exists()


def test_pug_6_unreachable_is_told_from_a_missing_repository(world):
    from compass_pkg import parents
    assert parents.unreachable("fatal: unable to access 'https://x/': Could not resolve host: x")
    assert parents.unreachable("ssh: connect to host x port 22: Connection timed out")
    assert not parents.unreachable("fatal: repository '/x' does not exist")
    assert not parents.unreachable("fatal: Authentication failed for 'https://x/'")


# --- PUG-7: a missing ref is an error ----------------------------------------------------

def test_pug_7_a_ref_the_remote_does_not_have_names_the_ref(world):
    from compass_pkg.core import CompassError
    world.project(PROJECT.replace("@main", "@gone"))
    with pytest.raises(CompassError) as caught:
        _update().plan(world.root)
    assert "gone" in str(caught.value) and "no such ref" in str(caught.value)


def test_pug_7_a_repository_that_does_not_exist_is_an_error_not_offline(world):
    from compass_pkg.core import CompassError
    world.project(PROJECT.replace("acme/bank", "acme/missing"))
    with pytest.raises(CompassError) as caught:
        _update().plan(world.root)
    assert "acme/missing" in str(caught.value) and "L-PARENT-FETCH" in str(caught.value)


# --- PUG-8: a new commit that breaks the parent rules is refused --------------------------

def test_pug_8_a_new_commit_with_a_settings_key_is_refused(world):
    world.advance({**OTHER, "allow_project_commands": True})
    world.project()
    before = world.text()
    out, _ = _run(world, yes=True)
    assert (out.status, out.refusal[0], out.written) == ("refused", "new-parent-invalid", False)
    assert "L-SETTINGS-KEY" in out.refusal[1] and world.text() == before


def test_pug_8_a_new_commit_that_the_project_cannot_merge_over_is_refused(world):
    world.advance({"schema": 1, "owner": "platform-team",
                   "checks": {"backfills-paid": {"remove": True}}})
    world.project("""\
schema: 1
extends: github:acme/bank@main#{sha}
owner: jed72

checks:
  backfills-paid:
    set:
      severity: advisory
    waiver:
      reason: Follow-ups are tracked outside the manifest here.
      approved_by: jed72
      approved_on: 2026-10-05
""")
    before = world.text()
    out, _ = _run(world, yes=True)
    assert (out.status, out.refusal[0], out.written) == ("refused", "does-not-resolve", False)
    assert world.text() == before


# --- PUG-9: an edited cache of the current pin stops the move ---------------------------

def test_pug_9_an_edited_cache_of_the_current_pin_is_an_error(world):
    from compass_pkg import parents
    from compass_pkg.core import CompassError
    world.advance(OTHER)
    world.project()
    parents.resolve(world.root, f"github:acme/bank@main#{world.first}", fetch=True)
    world.cached(world.first).write_text(_dump(MOVED), encoding="utf-8")
    with pytest.raises(CompassError) as caught:
        _update().plan(world.root)
    assert "edited" in str(caught.value) and "fetch" in str(caught.value)


# --- PUG-10: a fetched but unwritten move is stale --------------------------------------

def test_pug_10_a_declined_move_leaves_the_newer_commit_known_and_an_applied_one_does_not(world):
    from compass_pkg import parent_states
    second = world.advance(MOVED)
    world.project()
    _run(world, interactive=True, answers=("n",))
    [state], _ = parent_states.project_states(world.root)
    assert (state.state, state.newer) == ("stale", second)
    _run(world, interactive=True, answers=("y", "jed72", "y"))
    [state], _ = parent_states.project_states(world.root)
    assert (state.state, state.sha) == ("up to date", second)


# --- PUG-11: --to is for a shipped major -------------------------------------------------

def test_pug_11_to_is_refused_for_a_git_parent(world):
    from compass_pkg.core import CompassError
    world.project()
    with pytest.raises(CompassError) as caught:
        _update().plan(world.root, 7)
    assert "git parent" in str(caught.value) and "--to" in str(caught.value)


# --- PUG-12: the JSON keeps its keys and adds sha ------------------------------------

def test_pug_12_the_json_of_a_git_move_carries_the_sha(world):
    second = world.advance(OTHER)
    world.project()
    out, _ = _run(world, yes=True)
    doc = _update().document(out)
    assert list(doc) == ["schema", "status", "written", "from", "to", "refusal",
                         "classification", "replay", "waivers"]
    assert doc["from"] == {"ref": "github:acme/bank@main", "major": None, "version": None,
                           "sha": world.first}
    assert doc["to"] == {"ref": "github:acme/bank@main", "major": None, "version": None,
                         "sha": second}
    assert doc["status"] == "applied" and doc["written"] is True
    assert doc["classification"] is not None and doc["replay"] is not None


def test_pug_12_the_shipped_default_json_has_no_sha():
    from compass_pkg import policy_update
    # The existing shape is untouched: the example the docs pin has three keys here.
    example = json.loads((ROOT / "tests" / "fixtures" / "policy-update-json-example.json")
                         .read_text(encoding="utf-8"))
    assert list(example["from"]) == ["ref", "major", "version"]
    assert policy_update.JSON_SCHEMA_VERSION == 1


def _env(world, **extra):
    env = {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(world.tmp),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1", "COMPASS_PARENT_REMOTE_BASE": str(world.base)}
    env.update(extra)
    return env


def _cli(world, *argv, **extra):
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=world.root,
                          env=_env(world, **extra), capture_output=True, text=True,
                          timeout=300)
    return done.returncode, done.stdout, done.stderr


def test_pug_12_the_real_cli_moves_the_pin_and_reports_the_exit_codes(world):
    second = world.advance(OTHER)
    world.project()
    code, out, _ = _cli(world, "policy", "update", "--yes", "--json")
    assert code == 0 and json.loads(out)["to"]["sha"] == second
    assert world.text() == PROJECT.format(sha=second)
    code, out, _ = _cli(world, "policy", "update", "--json")
    assert code == 0 and json.loads(out)["status"] == "nothing-to-do"
    world.advance({**OTHER, "owner": "platform-team-three"})
    code, out, _ = _cli(world, "policy", "update", "--json", COMPASS_OFFLINE="1")
    assert code == 1 and json.loads(out)["status"] == "offline"
    world.project(PROJECT.replace("@main", "@gone"), sha=second)
    code, _, err = _cli(world, "policy", "update", "--yes")
    assert code == 2 and "gone" in err


# --- PUG-13: owning docs and verb help --------------------------------------------------

def test_pug_13_the_owning_docs_and_the_help_describe_the_git_move():
    update = (ROOT / "docs" / "policy-update.md").read_text(encoding="utf-8")
    flat = " ".join(update.split())
    for words in ("git parent", "git ls-remote", "`offline`", "`new-parent-invalid`",
                  "`sha`", "--to", "COMPASS_OFFLINE"):
        assert words in flat, words
    parents_doc = " ".join((ROOT / "docs" / "git-parents.md").read_text(
        encoding="utf-8").split())
    assert "compass policy update" in parents_doc and "moves the pin" in parents_doc
    assert "will resolve a ref to a sha in a later release" not in parents_doc
    from compass_pkg import verb_help
    assert "git parent" in verb_help.VERB_DESCRIPTIONS["policy update"]


def test_pug_13_the_parent_lookup_is_one_function():
    mod = _update()
    assert callable(mod._chain_parents)
    source = Path(mod.__file__).read_text(encoding="utf-8")
    assert len(re.findall(r"parents\.resolve\(", source)) == 1
