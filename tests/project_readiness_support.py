"""Fixture projects for the repository-readiness tests.

A fixture project is a temporary Git repository with a `compass.yml`. Its
project commands are small committed shell scripts whose exit code and run
time the test controls, so a test never depends on a real build tool.
`run_compass` runs the repository's own `cli/compass` in a fixture project.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"

#: Identity for the fixture repositories, so a commit never needs the
#: caller's Git configuration.
GIT_IDENTITY = {"GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.com",
                "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.com"}


def environment(home, extra=None):
    """The environment a fixture command runs in. `home` is the fixture's own
    folder, so nothing reads the caller's settings."""
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
           "PYTHONDONTWRITEBYTECODE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
           "COMPASS_RENDER_AFTER": "0", **GIT_IDENTITY}
    env.update(extra or {})
    return env


def git(project, *argv):
    """Run Git in the fixture project and return its output."""
    done = subprocess.run(["git", *argv], cwd=project, env=environment(project),
                          capture_output=True, text=True, check=True)
    return done.stdout


def run_compass(project, *argv, env=None):
    """Run this repository's `cli/compass` in the fixture project. Returns
    `(exit code, stdout, stderr)`."""
    done = subprocess.run([sys.executable, str(CLI), *argv], cwd=project,
                          env=environment(project, env), capture_output=True, text=True,
                          timeout=300)
    return done.returncode, done.stdout, done.stderr


def write_script(project, name, exit_code=0, sleep_seconds=0):
    """A committed-to-be shell script under `scripts/` that sleeps and then
    exits with the code the test chose. Returns its repository-relative path."""
    path = Path(project) / "scripts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["#!/bin/sh"]
    if sleep_seconds:
        lines.append(f"sleep {sleep_seconds}")
    lines.append(f"exit {exit_code}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return f"scripts/{name}"


def make_project(tmp_path, compass_yml=None, files=None, scripts=None, commit=True):
    """A fixture project: a Git repository with `.compass/`, an optional
    `compass.yml` (a mapping or text), extra `files` (path to text) and
    `scripts` (name to `{exit_code, sleep_seconds}`), committed as one commit
    unless `commit` is false. Returns the project folder."""
    project = Path(tmp_path)
    project.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=project,
                   env=environment(project), check=True)
    (project / ".compass").mkdir(exist_ok=True)
    if compass_yml is not None:
        text = compass_yml if isinstance(compass_yml, str) else yaml.safe_dump(
            compass_yml, sort_keys=False)
        (project / "compass.yml").write_text(text, encoding="utf-8")
    for relative, text in (files or {}).items():
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    for name, spec in (scripts or {}).items():
        write_script(project, name, **spec)
    if commit:
        git(project, "add", "-A")
        git(project, "commit", "-q", "--allow-empty", "-m", "fixture")
    return project


RECORD = Path(".compass") / "readiness.yml"


def readiness(project, *argv, env=None):
    """Run `compass readiness` in the fixture project. Returns
    `(exit code, stdout, stderr)`."""
    return run_compass(project, "readiness", *argv, env=env)


def read_record(project):
    """The readiness record the last run wrote, as a mapping."""
    return yaml.safe_load((Path(project) / RECORD).read_text(encoding="utf-8"))


def signal(record, signal_id):
    """One signal's entry in a readiness record or the `--json` output."""
    found = [s for s in record["signals"] if s["id"] == signal_id]
    assert len(found) == 1, (signal_id, record["signals"])
    return found[0]


def marker_script(project, name, body):
    """A shell script under `scripts/` that first appends its name and the
    time to `$READINESS_MARKERS/<name>`, then runs `body`. The marker folder
    is outside the project, so a marker survives the temporary worktree.
    Returns the command that runs it."""
    path = Path(project) / "scripts" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n"
                    'if [ -n "$READINESS_MARKERS" ]; then\n'
                    f'  echo "$(python3 -c "import time; print(time.time())") $(pwd)"'
                    f' >> "$READINESS_MARKERS/{name}"\n'
                    "fi\n" + body.rstrip("\n") + "\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return f"sh scripts/{name}"


def markers(folder):
    """`{script name: [(start time, working folder), ...]}` from a marker folder."""
    found = {}
    for path in sorted(Path(folder).iterdir()):
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            when, _, where = line.partition(" ")
            rows.append((float(when), where))
        found[path.name] = rows
    return found


def worktrees(project):
    """The paths `git worktree list --porcelain` reports, real paths, sorted."""
    out = git(project, "worktree", "list", "--porcelain")
    return sorted(os.path.realpath(line.split(" ", 1)[1])
                  for line in out.splitlines() if line.startswith("worktree "))
