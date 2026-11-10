"""`trail.md` checks with the real `sha256sum`, in a clone, with no Compass on PATH.

Step 5 of #356 [Commit the issue record with the code and add trail.md]. The
issue's "how to check": on a finished issue, `sha256sum -c` over the digests
in `trail.md` passes on a machine without Compass.

The test builds a git repository, takes one quick fix through the CLI (start
with a request link and a requester, a real failing pytest run recorded with
`tdd-red`, the fix, `quick-fix finish`, the person's ship approval and a
second `finish`). The project's `compass.yml` names only the owner, so the
record mode is committed, and the second `finish` lands through `compass
ship-commit`, which writes `trail.md` and commits the issue record with the
fix (step 6). The test does not commit anything by hand except the base. It then clones the repository
from a `file://` path, so nothing reaches the network, and runs the check in
the clone with `PATH=/usr/bin:/bin:/sbin`, where neither the `compass`
launcher nor its package is reachable.

`sha256sum` is used when that PATH holds it (macOS has `/sbin/sha256sum`),
else `shasum -a 256`. The macOS `sha256sum` reads the standard input only
when given `-`, so the piped form is `sha256sum -c -`; `shasum` reads it
either way.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "two_command_e2e", ROOT / "scripts" / "two-command-e2e.py")
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)
CLI = ROOT / "cli" / "compass"
SLUG = "fix-f"
TRAIL = f".compass/work/{SLUG}/trail.md"
SYSTEM_PATH = "/usr/bin:/bin:/sbin"
SUM_LINE = re.compile(r"^[0-9a-f]{64}  ")
HEADINGS = ["## 1. Who asked", "## 2. What was agreed", "## 3. Red, for each scenario",
            "## 4. Green", "## 5. Who approved, and by what authority",
            "## 6. What shipped"]


def _tool():
    """The checker on the system PATH, as an argument list, or None."""
    if shutil.which("sha256sum", path=SYSTEM_PATH):
        return ["sha256sum"]
    if shutil.which("shasum", path=SYSTEM_PATH):
        return ["shasum", "-a", "256"]
    return None


def _git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout.strip()


def _compass(cwd, *args):
    done = subprocess.run([sys.executable, str(CLI), *args], cwd=cwd,
                          capture_output=True, text=True)
    return done


def _ok(cwd, *args):
    done = _compass(cwd, *args)
    assert done.returncode == 0, done.stdout + done.stderr
    return done


def _pytest():
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-o", "addopts=", "tests/test_f.py"]


@pytest.fixture(scope="module")
def landed(tmp_path_factory):
    """A repository whose quick fix landed and whose record, with its trail,
    is committed."""
    root = tmp_path_factory.mktemp("trail") / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src" / "__init__.py").write_text("")
    # The person who approves is the project's owner.
    (root / "compass.yml").write_text(f"owner: {e2e.APPROVER}\n")
    (root / "src" / "f.py").write_text("def f():\n    return 1\n")
    (root / "tests" / "test_f.py").write_text(
        "from src.f import f\n\n\ndef test_f():\n    assert f() == 2\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    _ok(root, "quick-fix", "start", SLUG,
        "--risk", "trivial - one line", "--familiarity",
        "brownfield-mapped - the file and its test exist",
        "--size", "atomic - one line", "--intent", "f returns 2",
        "--scenario", "Given f, when called, then it returns 2.",
        "--scenario-id", "TRC-001", "--test", "tests/test_f.py",
        "--request", "https://example.com/tickets/1", "--requester", "Dana Smith")
    loop = ["--loop", "outer", "--scenario", "TRC-001"]
    _ok(root, "tdd-red", "--issue", SLUG, *loop, "--", *_pytest())
    (root / "src" / "f.py").write_text("def f():\n    return 2\n")
    where = ["--candidate", "local", "--client", "cli"]
    finish = ["quick-fix", "finish", "--issue", SLUG, "-m", "Fix f",
              "--release-note", "f returns 2", "--loop", "outer", *where, "--", *_pytest()]
    # `finish` keeps the red recorded with `tdd-red` and records the green. It
    # commits nothing until a person gives the ship approval.
    first = _ok(root, *finish)
    assert "Nothing is committed" in first.stdout, first.stdout
    assert e2e.person_approves(root) == [1]
    # The record mode is committed: this `finish` lands through `ship-commit`,
    # which writes `trail.md` and commits the record with the fix.
    second = _ok(root, *finish)
    assert "checked and committed" in second.stdout, second.stdout
    return root


def test_the_land_commit_holds_the_fix_and_its_record(landed):
    """The trail is checked at the land commit, which is HEAD: it holds the
    fix, the trail and the files the trail names, and no per-checkout file."""
    held = _git(landed, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert "src/f.py" in held and TRAIL in held, held
    assert f".compass/work/{SLUG}/manifest.yml" in held, held
    assert not [p for p in held if "/generations/" in p or p.endswith(".lock")
                or p.endswith("/.tdd-state.json")], held
    assert _git(landed, "status", "--porcelain", "--", ".compass/work") == ""
    assert _compass(landed, "trail", "--check", "--issue", SLUG).returncode == 0


@pytest.fixture
def clone(landed, tmp_path):
    fresh = tmp_path / "fresh"
    _git(tmp_path, "clone", "-q", landed.as_uri(), str(fresh))
    return fresh


def _system(cwd, command):
    """Run `command` with bash on the system PATH only, so no Compass is reachable."""
    env = {"PATH": SYSTEM_PATH, "HOME": str(cwd), "LC_ALL": "C"}
    return subprocess.run(["/bin/bash", "-c", command], cwd=cwd, env=env,
                          capture_output=True, text=True)


def _sum_lines(trail):
    return [line for line in trail.read_text().splitlines() if SUM_LINE.match(line)]


def test_compass_is_not_reachable_on_the_system_path(clone):
    found = _system(clone, "command -v compass")
    assert found.returncode != 0 and found.stdout == "", found.stdout


def test_sha256sum_checks_every_sum_line_in_a_clone_without_compass(clone):
    tool = _tool()
    if tool is None:
        pytest.skip("neither sha256sum nor shasum is on " + SYSTEM_PATH)
    lines = _sum_lines(clone / TRAIL)
    assert lines, (clone / TRAIL).read_text()
    stdin = "-" if tool == ["sha256sum"] else ""
    piped = _system(clone, f"grep -E '^[0-9a-f]{{64}}  ' {TRAIL} | {' '.join(tool)} -c {stdin}")
    assert piped.returncode == 0, piped.stdout + piped.stderr
    assert piped.stdout.count(": OK") == len(lines), piped.stdout
    # The piped form is what the trail's own header prints.
    assert f"grep -E '^[0-9a-f]{{64}}  ' {TRAIL} | sha256sum -c -" in (clone / TRAIL).read_text()


def test_plain_sha256sum_over_the_trail_passes_with_the_prose_lines(clone):
    tool = _tool()
    if tool is None:
        pytest.skip("neither sha256sum nor shasum is on " + SYSTEM_PATH)
    plain = _system(clone, f"{' '.join(tool)} -c {TRAIL}")
    assert plain.returncode == 0, plain.stdout + plain.stderr


def test_one_changed_byte_in_a_hashed_file_fails_and_is_named(clone):
    tool = _tool()
    if tool is None:
        pytest.skip("neither sha256sum nor shasum is on " + SYSTEM_PATH)
    green = clone / ".compass" / "work" / SLUG / "evidence" / "green-TRC-001.outer.json"
    assert f".compass/work/{SLUG}/evidence/green-TRC-001.outer.json" in (clone / TRAIL).read_text()
    data = bytearray(green.read_bytes())
    data[0] = ord(" ") if data[0] != ord(" ") else ord("\t")
    green.write_bytes(bytes(data))
    stdin = "-" if tool == ["sha256sum"] else ""
    failed = _system(clone, f"grep -E '^[0-9a-f]{{64}}  ' {TRAIL} | {' '.join(tool)} -c {stdin}")
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert re.search(r"green-TRC-001\.outer\.json: FAILED", failed.stdout), failed.stdout


def test_the_trail_names_the_tested_code_and_the_spec(clone):
    text = (clone / TRAIL).read_text()
    lines = _sum_lines(clone / TRAIL)
    named = {line.split("  ", 1)[1] for line in lines}
    assert {"src/f.py", "tests/test_f.py", f".compass/work/{SLUG}/manifest.yml",
            f".compass/work/{SLUG}/evidence/SHA256SUMS",
            f".compass/work/{SLUG}/evidence/red-TRC-001.outer.json"} <= named, named
    assert any(p.startswith("docs/compass/") and p.endswith(f"-{SLUG}/acceptance-criteria.md")
               for p in named), named
    code = hashlib.sha256((clone / "src" / "f.py").read_bytes()).hexdigest()
    assert f"{code}  src/f.py" in lines
    assert "Dana Smith asked at https://example.com/tickets/1" in text
    assert "Compass does not check who the requester is." in text
    assert "TRC-001 failed at" in text and "TRC-001 passed at" in text


def test_the_sections_follow_the_order_of_the_issue(clone):
    text = (clone / TRAIL).read_text()
    at = [text.index(h) for h in HEADINGS]
    assert at == sorted(at), at


def test_check_says_out_of_date_after_a_manifest_write_and_matches_after_trail(landed):
    assert _compass(landed, "trail", "--check", "--issue", SLUG).returncode == 0
    manifest = landed / ".compass" / "work" / SLUG / "manifest.yml"
    held = manifest.read_bytes()
    try:
        _ok(landed, "issue", "link", "set", "--issue", SLUG, "--requester", "Lee Jones")
        stale = _compass(landed, "trail", "--check", "--issue", SLUG)
        assert stale.returncode == 1, stale.stdout + stale.stderr
        assert "out of date" in stale.stdout and "line" in stale.stdout, stale.stdout
        _ok(landed, "trail", "--issue", SLUG)
        assert _compass(landed, "trail", "--check", "--issue", SLUG).returncode == 0
    finally:
        manifest.write_bytes(held)
        _ok(landed, "trail", "--issue", SLUG)
        assert _git(landed, "status", "--porcelain", "--", f".compass/work/{SLUG}") == ""
