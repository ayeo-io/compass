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
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))
from parent_fixtures import REAL_GIT, _git, issue_project, make_remote, set_extends  # noqa: E402

CLI = ROOT / "cli" / "compass"

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
        code, out, err = self.run("approach", "show", "--issue", "feature")
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


def test_summary_stays_three_lines_without_a_git_parent(tmp_path):
    project = Project(tmp_path)
    set_extends(project.root, "compass:default@6")
    assert len(project.summary().splitlines()) == 3


def test_a_project_file_that_repeats_a_key_does_not_crash_the_summary(tmp_path):
    project = Project(tmp_path)
    (project.root / "compass.yml").write_text("schema: 1\nschema: 2\n", encoding="utf-8")
    code, out, err = project.run("approach", "show", "--issue", "feature")
    assert "Traceback" not in err, err
    assert code == 0 and "Parent" not in out, (out, err)


def _no_traceback(done):
    code, out, err = done
    assert "Traceback" not in err and "UnicodeDecodeError" not in err, err
    return code, out, err


def test_unreadable_project_file_does_not_crash(tmp_path):
    project = Project(tmp_path)
    (project.root / "compass.yml").write_bytes(b"schema: 1\nextends: \xff\xfe\x80\n")
    code, out, err = _no_traceback(project.run("approach", "show", "--issue", "feature"))
    assert code == 0, (out, err)
