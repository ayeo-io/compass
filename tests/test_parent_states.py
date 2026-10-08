"""The four states of a git parent (issue `parent-states`).

Each git parent is in one of four states, read from the pin, the cache and
`seen.yml`:

| State | Meaning | Lint level |
|---|---|---|
| up to date | the cache holds the pin, and no other commit is known for the ref | info |
| stale | `seen.yml` holds another commit for the ref, so a newer one is known | warning |
| locally modified | the cached `compass.yml` no longer matches the digest recorded at fetch | error |
| both | stale and edited | error |

`compass policy lint` reports the state as a finding and `compass approach
summary` prints a line per parent. Tests build local git repositories in a
temporary folder and point `COMPASS_PARENT_REMOTE_BASE` at them, so nothing
reaches the network. The cache is found by searching for the pinned commit, so
these tests do not depend on how the cache is laid out.

Each test name says which scenario it covers.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import REAL_GIT, _git, issue_project, make_remote, set_extends  # noqa: E402

CLI = ROOT / "cli" / "compass"

STATE_CODES = {"up to date": "S-PARENT-UP-TO-DATE", "stale": "S-PARENT-STALE",
               "locally modified": "S-PARENT-MODIFIED", "both": "S-PARENT-BOTH"}
STATE_LEVELS = {"up to date": "info", "stale": "warning", "locally modified": "error",
                "both": "error"}


def _env(home, base):
    return {"PATH": os.environ.get("PATH", REAL_GIT), "HOME": str(home), "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
            "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1",
            "COMPASS_PARENT_REMOTE_BASE": str(base)}


class Project:
    """A project pinned to a parent that has two commits, `first` and `second`."""

    def __init__(self, tmp_path):
        self.base = tmp_path / "remotes"
        self.first = make_remote(self.base, files={"compass.yml": self._doc("team-a")})
        repo = self.base / "acme" / "bank.git"
        (repo / "compass.yml").write_text(self._doc("team-b"), encoding="utf-8")
        _git(repo, "commit", "--quiet", "-am", "second")
        self.second = _git(repo, "rev-parse", "HEAD")
        self.root, self.task_dir = issue_project(tmp_path, self.pin(self.first))

    @staticmethod
    def _doc(owner):
        return yaml.safe_dump({"schema": 1, "owner": owner})

    @staticmethod
    def pin(sha):
        return f"github:acme/bank@1.2.0#{sha}"

    def move_pin(self, sha):
        set_extends(self.root, self.pin(sha))

    def run(self, *argv):
        done = subprocess.run([sys.executable, str(CLI), *argv], cwd=self.root,
                              env=_env(self.root, self.base), capture_output=True,
                              text=True, timeout=180)
        return done.returncode, done.stdout, done.stderr

    def lint(self):
        code, out, err = self.run("policy", "lint", "--json")
        assert out.strip().startswith("{"), err
        return code, json.loads(out)

    def summary(self):
        code, out, err = self.run("approach", "summary", "--issue", "feature")
        assert code == 0, err
        return out

    def cached(self, sha):
        """The cached `compass.yml` of a commit, wherever the cache keeps it."""
        found = [p for p in (self.root / ".compass" / "cache" / "parents").rglob("compass.yml")
                 if p.parent.name == sha]
        assert len(found) == 1, found
        return found[0]

    def seen(self):
        found = list((self.root / ".compass" / "cache" / "parents").rglob("seen.yml"))
        assert len(found) == 1, found
        return found[0]

    def edit_cache(self, sha):
        path = self.cached(sha)
        text = path.read_text(encoding="utf-8")
        assert "owner: team-a" in text
        path.write_text(text.replace("owner: team-a", "owner: attacker"), encoding="utf-8")

    def make_stale(self):
        """Fetch the second commit as well, then pin the first again: the machine
        now knows a commit for the ref that is not the pin."""
        for sha in (self.first, self.second, self.first):
            self.move_pin(sha)
            code, report = self.lint()
            assert code == 0, report


def _state_findings(report):
    return [f for f in report["findings"] if f["code"].startswith("S-PARENT-")]


def _only_state(report):
    found = _state_findings(report)
    assert len(found) == 1, report["findings"]
    return found[0]


def test_up_to_date(tmp_path):
    """a cached pin, unchanged, with no other commit known."""
    project = Project(tmp_path)
    code, report = project.lint()
    assert code == 0, report
    finding = _only_state(report)
    assert finding["code"] == "S-PARENT-UP-TO-DATE" and finding["level"] == "info"
    assert finding["layer"].startswith("github:acme/bank@1.2.0#"), finding


def test_stale(tmp_path):
    """another commit is known for the ref, and the pin stays put."""
    project = Project(tmp_path)
    project.make_stale()
    code, report = project.lint()
    assert code == 0, "a stale parent warns and never fails"
    finding = _only_state(report)
    assert finding["code"] == "S-PARENT-STALE" and finding["level"] == "warning"
    assert project.second[:7] in finding["message"], finding["message"]
    # An exact-pin fetch overwrites the sha in seen.yml, so the other commit is the
    # one fetched last. It may be older than the pin, so the message never says newer.
    assert "was fetched last on this machine" in finding["message"], finding["message"]
    assert "newer" not in finding["message"], finding["message"]


def test_locally_modified(tmp_path):
    """an edit to the cached file is found and fails the lint."""
    project = Project(tmp_path)
    project.lint()
    project.edit_cache(project.first)
    code, report = project.lint()
    assert code == 1, report
    finding = _only_state(report)
    assert finding["code"] == "S-PARENT-MODIFIED" and finding["level"] == "error"
    assert "no longer matches" in finding["message"], finding["message"]
    # The message tells the person how to clear it, and that works.
    assert "delete the cached copy of" in finding["message"], finding["message"]
    assert "compass policy lint" in finding["message"], finding["message"]
    # The parent layer is named in the report, so the person sees which parent failed.
    assert any(layer["kind"] == "parent" and layer["name"].startswith("github:acme/bank@")
               for layer in report["layers"]), report["layers"]
    shutil.rmtree(project.cached(project.first).parent)
    code, report = project.lint()
    assert code == 0, report
    assert _only_state(report)["code"] == "S-PARENT-UP-TO-DATE"


def test_both(tmp_path):
    """stale and edited."""
    project = Project(tmp_path)
    project.make_stale()
    project.edit_cache(project.first)
    code, report = project.lint()
    assert code == 1, report
    finding = _only_state(report)
    assert finding["code"] == "S-PARENT-BOTH" and finding["level"] == "error"
    assert project.second[:7] in finding["message"], finding["message"]


def _bring_to(project, state):
    if state in ("stale", "both"):
        project.make_stale()
    else:
        project.lint()
    if state in ("locally modified", "both"):
        project.edit_cache(project.first)


@pytest.mark.parametrize("state", list(STATE_CODES))
def test_lint_levels(tmp_path, state):
    """each state has its own code, at its own level."""
    project = Project(tmp_path)
    _bring_to(project, state)
    code, report = project.lint()
    finding = _only_state(report)
    assert (finding["code"], finding["level"]) == (STATE_CODES[state], STATE_LEVELS[state])
    assert code == (1 if STATE_LEVELS[state] == "error" else 0)
    assert report["counts"]["warnings"] == (1 if state == "stale" else 0)


@pytest.mark.parametrize("state", list(STATE_CODES))
def test_summary_line(tmp_path, state):
    """`approach summary` prints one line for the parent, with its state."""
    project = Project(tmp_path)
    _bring_to(project, state)
    out = project.summary()
    lines = [line for line in out.splitlines() if line.startswith("Parent")]
    assert len(lines) == 1, out
    assert f"github:acme/bank@1.2.0" in lines[0] and project.first[:7] in lines[0], lines
    assert lines[0].endswith(f"- {state}"), lines


def test_summary_stays_three_lines_without_a_git_parent(tmp_path):
    project = Project(tmp_path)
    set_extends(project.root, "compass:default@6")
    assert len(project.summary().splitlines()) == 3


def test_summary_never_fetches_or_fails_for_an_uncached_parent(tmp_path):
    project = Project(tmp_path)
    out = project.summary()
    assert "Parent: not read" in out and "L-PARENT-NOT-CACHED" in out, out
    assert not (project.root / ".compass" / "cache").exists(), "summary fetched"
    lines = out.splitlines()[3:]
    assert len(lines) > 1 and all(len(line) <= 100 for line in lines), lines
    assert all(line.startswith("  ") for line in lines[1:]), lines


def test_content_digest_alone_still_proves_the_pin(tmp_path):
    """A seen.yml written before `digests` existed holds `content_digest` only."""
    project = Project(tmp_path)
    project.lint()
    doc = yaml.safe_load(project.seen().read_text(encoding="utf-8"))
    for entry in doc["refs"].values():
        entry.pop("digests")
    project.seen().write_text(yaml.safe_dump(doc), encoding="utf-8")
    code, report = project.lint()
    assert code == 0 and _only_state(report)["code"] == "S-PARENT-UP-TO-DATE", report
    project.edit_cache(project.first)
    code, report = project.lint()
    assert code == 1 and _only_state(report)["code"] == "S-PARENT-MODIFIED", report


def test_an_unreadable_cached_file_is_not_up_to_date(tmp_path, monkeypatch):
    from compass_pkg import parent_states, parents
    project = Project(tmp_path)
    project.lint()
    monkeypatch.setenv("COMPASS_PARENT_REMOTE_BASE", str(project.base))
    found = parents.resolve(project.root, project.pin(project.first))
    project.cached(project.first).unlink()
    state = parent_states.read(project.root, found)
    assert state.state == "locally modified" and "cannot be read" in state.why, state


def test_a_project_file_that_repeats_a_key_does_not_crash_the_summary(tmp_path):
    project = Project(tmp_path)
    (project.root / "compass.yml").write_text("schema: 1\nschema: 2\n", encoding="utf-8")
    code, out, err = project.run("approach", "summary", "--issue", "feature")
    assert "Traceback" not in err, err
    assert code == 0 and "Parent" not in out, (out, err)


def _no_traceback(done):
    code, out, err = done
    assert "Traceback" not in err and "UnicodeDecodeError" not in err, err
    return code, out, err


def test_damaged_seen_does_not_crash(tmp_path):
    """A seen.yml that is not valid text counts as holding no digest."""
    project = Project(tmp_path)
    project.lint()
    project.seen().write_bytes(b"\xff\xfe\x00 not text \x80")
    code, out, err = _no_traceback(project.run("policy", "lint", "--json"))
    report = json.loads(out)
    assert code == 1 and _only_state(report)["code"] == "S-PARENT-MODIFIED", (out, err)
    out = _no_traceback(project.run("approach", "summary", "--issue", "feature"))[1]
    assert "- locally modified" in out, out
    _no_traceback(project.run("policy", "effective"))
    _no_traceback(project.run("approach", "evaluate", "--issue", "feature", "--write"))
    _no_traceback(project.run("check", "--issue", "feature"))


def test_unreadable_project_file_does_not_crash(tmp_path):
    project = Project(tmp_path)
    (project.root / "compass.yml").write_bytes(b"schema: 1\nextends: \xff\xfe\x80\n")
    code, out, err = _no_traceback(project.run("approach", "summary", "--issue", "feature"))
    assert code == 0, (out, err)


def test_digests_not_a_mapping(tmp_path):
    """A hand-damaged `digests` entry is replaced by the next fetch."""
    project = Project(tmp_path)
    project.lint()
    doc = yaml.safe_load(project.seen().read_text(encoding="utf-8"))
    for entry in doc["refs"].values():
        entry["digests"] = "oops"
    project.seen().write_text(yaml.safe_dump(doc), encoding="utf-8")
    project.move_pin(project.second)
    code, out, err = _no_traceback(project.run("policy", "lint", "--json"))
    assert code == 0, (out, err)
    entry = next(iter(yaml.safe_load(project.seen().read_text(encoding="utf-8"))["refs"].values()))
    assert set(entry["digests"]) == {project.second}, entry


def test_no_record(tmp_path):
    """a cached parent that `seen.yml` holds no digest for cannot be
    shown to match a fetch, so it counts as modified."""
    project = Project(tmp_path)
    project.lint()
    project.seen().unlink()
    code, report = project.lint()
    assert code == 1, report
    finding = _only_state(report)
    assert finding["code"] == "S-PARENT-MODIFIED"
    assert "no digest" in finding["message"], finding["message"]
