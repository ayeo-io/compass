"""`compass ship-commit` commits the issue record with the code in committed mode.

Step 6 of #356 [Commit the issue record with the code and add trail.md]. In
committed mode (`record_mode`: no `record.commit: false`, no `record.remote`,
and git does not ignore the issue folder) a landing writes the landing into
the manifest before the commit (status `completed`, `land_timestamp`,
`landed_with_record: true`, no `land_commit`), writes `trail.md`, and stages
the issue folder and its documents folder itself. The commit then holds the
record that says the issue landed, and `landing.land_commit` reads that
commit from git.

In kept-out mode nothing under `.compass/` is staged, as before. One test
runs a quick fix against a copy of this repository's own `compass.yml`, which
names a `record.remote`, and proves the commit and the index hold nothing
under `.compass/`. Its record sync goes to a local bare repository through
git's `url.<base>.insteadOf`, and `GIT_ALLOW_PROTOCOL=file` keeps every git
call off the network.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))

from compass_pkg import landing  # noqa: E402

SLUG = "fix-f"
RECORD = f".compass/work/{SLUG}"
TRAIL = f"{RECORD}/trail.md"
SUM_LINE = re.compile(r"^([0-9a-f]{64})  (.+)$")
#: Per-checkout files the commit must never hold (`record_mode.WORK_IGNORE_LINES`).
PER_CHECKOUT = re.compile(r"/generations/|/\.[^/]*\.lock$|/\.red$|/\.acceptance$"
                          r"|/start-state\.json$|/evidence/\.tdd-state\.json$"
                          r"|/approval-requests/pending/")


def _git(cwd, *args, env=None):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout.strip()


def _compass(cwd, *args, env=None):
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd,
                          capture_output=True, text=True, env=env)


def _ok(cwd, *args, env=None):
    done = _compass(cwd, *args, env=env)
    assert done.returncode == 0, done.stdout + done.stderr
    return done


def _pytest():
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-o", "addopts=", "tests/test_f.py"]


def _repo(root, compass_yml=None, gitignore=None):
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "__init__.py").write_text("")
    (root / "src" / "f.py").write_text("def f():\n    return 1\n")
    (root / "tests" / "test_f.py").write_text(
        "from src.f import f\n\n\ndef test_f():\n    assert f() == 2\n")
    if compass_yml is not None:
        (root / "compass.yml").write_text(compass_yml)
    (root / ".gitignore").write_text("__pycache__/\n" + (gitignore or ""))
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


WHERE = ["--loop", "outer", "--candidate", "local", "--client", "cli"]


def _fixed(root, env=None):
    """Start the quick fix, record its red, fix the code and record its green."""
    _ok(root, "quick-fix", "start", SLUG,
        "--risk", "trivial - one line", "--familiarity",
        "brownfield-mapped - the file and its test exist",
        "--size", "atomic - one line", "--intent", "f returns 2",
        "--scenario", "Given f, when called, then it returns 2.",
        "--scenario-id", "TRC-001", "--test", "tests/test_f.py",
        "--request", "https://example.com/tickets/1", "--requester", "Dana Smith", env=env)
    _ok(root, "tdd-red", "--issue", SLUG, "--loop", "outer", "--scenario", "TRC-001",
        "--", *_pytest(), env=env)
    (root / "src" / "f.py").write_text("def f():\n    return 2\n")
    _ok(root, "tdd-green", "--issue", SLUG, "--scenario", "TRC-001", *WHERE,
        "--", *_pytest(), env=env)


def _ready(root):
    """An issue whose gates have passed and whose fix is not committed yet."""
    _fixed(root)
    _ok(root, "quick-fix", "finish", "--issue", SLUG, "--no-commit", "-m", "Fix f",
        "--release-note", "f returns 2", *WHERE, "--", *_pytest())
    return root


def _ship(root, *extra):
    _git(root, "add", "--", "src/f.py")
    return _compass(root, "ship-commit", "--issue", SLUG, "-m", "Fix f", *extra)


def _manifest(root):
    return yaml.safe_load((root / RECORD / "manifest.yml").read_text())


def _manifest_at(root, commit):
    return yaml.safe_load(_git(root, "show", f"{commit}:{RECORD}/manifest.yml"))


def _files(root, commit="HEAD"):
    return _git(root, "show", "--name-only", "--format=", commit).splitlines()


def _trail_mismatches(root, commit="HEAD"):
    """Each sum line of the committed `trail.md` whose file in `commit` differs."""
    out = []
    for line in _git(root, "show", f"{commit}:{TRAIL}").splitlines():
        found = SUM_LINE.match(line)
        if not found:
            continue
        digest, path = found.groups()
        blob = subprocess.run(["git", "cat-file", "blob", f"{commit}:{path}"], cwd=root,
                              capture_output=True)
        if blob.returncode != 0 or hashlib.sha256(blob.stdout).hexdigest() != digest:
            out.append(path)
    return out


def _hook(root, body):
    hook = root / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\n" + body)
    hook.chmod(0o755)


# --- committed mode -------------------------------------------------------------------------

def test_the_commit_holds_the_code_and_the_record(tmp_path):
    root = _ready(_repo(tmp_path / "repo"))
    done = _ship(root)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "issue marked done." in done.stdout, done.stdout
    held = _files(root)
    assert "src/f.py" in held, held
    assert {f"{RECORD}/manifest.yml", TRAIL, ".compass/work/.gitignore",
            f"{RECORD}/evidence/SHA256SUMS"} <= set(held), held
    assert any(p.startswith(f"{RECORD}/evidence/green-") for p in held), held
    assert any(p.startswith("docs/compass/") and p.endswith("/acceptance-criteria.md")
               for p in held), held
    assert not [p for p in held if PER_CHECKOUT.search(p)], held
    # Nothing of the record is left changed or untracked in the work tree.
    assert _git(root, "status", "--porcelain", "--", ".compass/work", "docs") == ""
    assert _trail_mismatches(root) == []
    assert _compass(root, "trail", "--check", "--issue", SLUG).returncode == 0


def test_the_manifest_says_landed_with_the_record_and_names_no_commit(tmp_path):
    root = _ready(_repo(tmp_path / "repo"))
    assert _ship(root).returncode == 0
    task = _manifest(root)
    assert task["status"] == "done" and task["close_reason"] == "completed", task
    assert task["landed_with_record"] is True
    assert task.get("land_timestamp")
    assert "land_commit" not in task
    assert task["release_note"] == "f returns 2"
    head = _git(root, "rev-parse", "HEAD")
    assert landing.land_commit(task, str(root / RECORD)) == head
    # The committed copy is the copy in the work tree.
    assert _manifest_at(root, "HEAD") == task


def test_a_hook_that_rewrites_a_record_file_gets_a_trail_that_matches(tmp_path):
    """A pre-commit hook that rewrites a file `trail.md` names and stops the
    commit: the retry writes `trail.md` again, so the commit holds a match."""
    root = _ready(_repo(tmp_path / "repo"))
    _hook(root, 'if [ ! -f .git/hook-ran ]; then\n'
                '  touch .git/hook-ran\n'
                '  for spec in docs/compass/*-fix-f/acceptance-criteria.md; do\n'
                '    printf "\\n<!-- formatted -->\\n" >> "$spec"\n'
                '  done\n'
                '  exit 1\n'
                'fi\nexit 0\n')
    done = _ship(root)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "after one retry" in done.stdout, done.stdout
    assert "`trail.md` was written again" in done.stdout, done.stdout
    assert "<!-- formatted -->" in _git(root, "show", "HEAD:" + next(
        p for p in _files(root) if p.endswith("/acceptance-criteria.md")))
    assert _trail_mismatches(root) == []
    assert "no longer matches" not in done.stdout
    assert _git(root, "status", "--porcelain", "--", ".compass/work", "docs") == ""


def test_a_hook_that_stages_a_change_during_the_commit_is_named(tmp_path):
    """A hook that changes a named file and stages it inside the commit: the
    landing stands, and `ship-commit` names the file `trail.md` no longer matches."""
    root = _ready(_repo(tmp_path / "repo"))
    _hook(root, 'for spec in docs/compass/*-fix-f/acceptance-criteria.md; do\n'
                '  printf "\\n<!-- formatted -->\\n" >> "$spec"\n'
                '  git add -- "$spec"\n'
                'done\nexit 0\n')
    done = _ship(root)
    assert done.returncode == 0, done.stdout + done.stderr
    assert re.search(r"a git hook changed docs/compass/[^ ]*-fix-f/acceptance-criteria\.md "
                     r"during the commit; `trail\.md` no longer matches it", done.stdout), \
        done.stdout
    assert len(_trail_mismatches(root)) == 1


def test_a_failed_check_after_the_commit_puts_the_working_manifest_back(tmp_path):
    """A hook that stages a path outside the scope during the commit: the commit
    holds a record that says landed, so the working copy says it did not."""
    root = _ready(_repo(tmp_path / "repo"))
    before = _manifest(root)
    _hook(root, 'echo stray > stray.txt\ngit add -- stray.txt\nexit 0\n')
    done = _ship(root)
    assert done.returncode == 2, done.stdout + done.stderr
    assert "NOT marked done" in done.stdout and "stray.txt" in done.stdout, done.stdout
    assert "git reset --soft HEAD^" in done.stdout, done.stdout
    assert _manifest_at(root, "HEAD")["landed_with_record"] is True
    task = _manifest(root)
    assert "land_timestamp" not in task and "landed_with_record" not in task, task
    assert task.get("status") == before.get("status")
    assert _compass(root, "trail", "--check", "--issue", SLUG).returncode == 0


def test_a_refused_landing_leaves_the_record_as_it_was(tmp_path):
    """A commit a hook stops on every try: nothing says landed, and nothing of
    the record stays staged."""
    root = _ready(_repo(tmp_path / "repo"))
    before = (root / RECORD / "manifest.yml").read_bytes()
    _hook(root, "exit 1\n")
    done = _ship(root)
    assert done.returncode != 0, done.stdout + done.stderr
    assert (root / RECORD / "manifest.yml").read_bytes() == before
    staged = _git(root, "diff", "--cached", "--name-only").splitlines()
    assert staged == ["src/f.py"], staged


def test_nothing_staged_commits_the_record_alone(tmp_path):
    root = _ready(_repo(tmp_path / "repo"))
    # Every file the issue traced is committed: the fix and its spec.
    _git(root, "add", "--", "src/f.py", "docs/compass")
    _git(root, "commit", "-q", "-m", "Fix f by hand")
    code = _git(root, "rev-parse", "HEAD")
    done = _compass(root, "ship-commit", "--issue", SLUG, "-m", "Land fix-f")
    assert done.returncode == 0, done.stdout + done.stderr
    head = _git(root, "rev-parse", "HEAD")
    assert head != code
    assert f"landed at HEAD {code[:8]}; the record was committed as {head[:8]}" \
        in done.stdout, done.stdout
    held = _files(root)
    assert held and all(p.startswith((".compass/work/", "docs/compass/")) for p in held), held
    assert _git(root, "log", "-1", "--format=%s") == "Land fix-f"
    task = _manifest(root)
    assert landing.land_commit(task, str(root / RECORD)) == head
    assert "land_commit" not in task
    assert _trail_mismatches(root) == []


def test_an_ignored_issue_folder_is_kept_out_with_one_line(tmp_path):
    root = _ready(_repo(tmp_path / "repo", gitignore=".compass/work/\n"))
    done = _ship(root)
    assert done.returncode == 0, done.stdout + done.stderr
    assert re.search(r"the issue record stays out of the commit, because "
                     r"\.compass/work/fix-f is ignored by \.gitignore:\d+:", done.stdout), \
        done.stdout
    assert not [p for p in _files(root) if p.startswith(".compass/")]
    task = _manifest(root)
    assert task["land_commit"] == _git(root, "rev-parse", "HEAD")
    assert "landed_with_record" not in task


# --- kept-out mode --------------------------------------------------------------------------

def test_kept_out_stages_nothing_under_compass_and_names_the_land_commit(tmp_path):
    root = _ready(_repo(tmp_path / "repo", compass_yml="record:\n  commit: false\n"))
    done = _ship(root)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "stays out of the commit" not in done.stdout
    head = _git(root, "rev-parse", "HEAD")
    assert _files(root) == ["src/f.py"], _files(root)
    task = _manifest(root)
    assert task["land_commit"] == head and "landed_with_record" not in task
    # The trail is written after the `land_commit` write, so it names the commit.
    assert f"in {head}." in (root / TRAIL).read_text()


def test_kept_out_refuses_a_staged_record_path(tmp_path):
    """In kept-out mode the issue folder is outside the scope, so a record
    file staged by hand is refused before anything is committed."""
    root = _ready(_repo(tmp_path / "repo", compass_yml="record:\n  commit: false\n"))
    _git(root, "add", "--", f"{RECORD}/manifest.yml")
    done = _ship(root)
    assert done.returncode != 0, done.stdout + done.stderr
    assert f"{RECORD}/manifest.yml" in done.stdout + done.stderr
    assert _git(root, "rev-list", "--count", "HEAD") == "1"


def test_this_repositorys_compass_yml_keeps_everything_under_compass_out(tmp_path):
    """A quick fix lands with a copy of this repository's real `compass.yml`,
    which names a `record.remote`: nothing under `.compass/` is committed or
    left staged, and the record syncs to a local copy of the remote."""
    settings = (ROOT / "compass.yml").read_text()
    remote = yaml.safe_load(settings)["record"]["remote"]
    bare = tmp_path / "record.git"
    _git(tmp_path, "init", "-q", "--bare", str(bare))
    env = dict(os.environ, XDG_CACHE_HOME=str(tmp_path / "cache"),
               GIT_ALLOW_PROTOCOL="file", GIT_CONFIG_COUNT="1",
               GIT_CONFIG_KEY_0=f"url.{bare.as_uri()}.insteadOf",
               GIT_CONFIG_VALUE_0=remote)
    root = _repo(tmp_path / "repo", compass_yml=settings)
    key = root / ".compass" / "private" / "rival-codes.yml"
    key.parent.mkdir(parents=True)
    key.write_text("rivals:\n  R1:\n    name: Zqxjvname\n")
    _fixed(root, env=env)
    done = _ok(root, "quick-fix", "finish", "--issue", SLUG, "-m", "Fix f",
               "--release-note", "f returns 2", *WHERE, "--", *_pytest(), env=env)
    held = _files(root)
    assert "src/f.py" in held, held
    assert not [p for p in held if p.startswith(".compass/")], held
    staged = _git(root, "diff", "--cached", "--name-only").splitlines()
    assert not [p for p in staged if p.startswith(".compass/")], staged
    task = _manifest(root)
    assert task["land_commit"] == _git(root, "rev-parse", "HEAD"), done.stdout
    assert "landed_with_record" not in task
    synced = _git(tmp_path, "--git-dir", str(bare), "ls-tree", "-r", "--name-only", "main")
    assert f"{RECORD}/manifest.yml" in synced.splitlines(), synced
