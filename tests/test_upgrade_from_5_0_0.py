"""A project made with Compass 5.0.0 keeps working after an upgrade.

`tests/test_upgrade_in_flight.py` covers one upgrade, the bundled PyYAML.
This one takes the 5.0.0 release from the repository's own tag (no network),
makes an issue with its CLI the way 5.0.0's assess stage did, records a red
and a green, and then reads the same project with the working tree's CLI:
the manifest must still load, and `compass check` must give the same
verdict, check by check. Every example manifest 5.0.0 shipped must still
pass `compass issue lint` (issue `upgrade-from-5-0-0`).

Scenario id: UP-1.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
TAG = "v5.0.0"
GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    """The 5.0.0 tree, from the tag. CI fetches the full history, so the tag
    is there; a checkout without it cannot run this test, and says so."""
    has_tag = subprocess.run(["git", "rev-parse", "--verify", "-q", TAG + "^{commit}"],
                             cwd=ROOT, capture_output=True).returncode == 0
    if not has_tag:
        pytest.fail(f"the {TAG} tag is not in this clone; fetch tags to run the "
                    f"upgrade test (CI's checkout fetches full history)")
    out = tmp_path_factory.mktemp("release")
    archive = subprocess.run(["git", "archive", TAG], cwd=ROOT, capture_output=True,
                             check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(out)], input=archive, check=True)
    return out


def _cli(cli, cwd, *args):
    return subprocess.run([sys.executable, str(cli), *args], cwd=cwd,
                          capture_output=True, text=True)


def _project(tmp_path, old_cli):
    """An issue made with the 5.0.0 CLI: assessed, its approach evaluated, a
    scenario, a red and a green."""
    root = tmp_path / "proj"
    (root / "data").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "data" / "greeting.txt").write_text("Hi, %s!\n")
    (root / "tests" / "test_greeting.py").write_text(
        "import pathlib\n\n\ndef test_greeting_says_hello():\n"
        "    p = pathlib.Path(__file__).resolve().parent.parent / 'data' / 'greeting.txt'\n"
        "    assert p.read_text().strip() == 'Hello, %s!'\n")
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "seed"], cwd=root, check=True)
    assert _cli(old_cli, root, "init").returncode == 0
    work = root / ".compass" / "work" / "fix-greeting"
    work.mkdir(parents=True)
    (work / "manifest.yml").write_text(
        "schema_version: '2.0'\nissue: fix-greeting\ncreated: '2026-09-25'\n"
        "status: active\nassessment: {risk: trivial, familiarity: brownfield-mapped, "
        "size: atomic, goal: delivery, role: engineer, labels: []}\n"
        "scenarios: []\nevidence: []\nchanged_files: []\n")
    (root / ".compass" / "current-task").write_text("fix-greeting\n")
    steps = [
        ("approach", "evaluate", "--issue", "fix-greeting", "--write"),
        ("scenario", "add", "TRC-001", "--issue", "fix-greeting", "--title",
         "Given the greeting, when read, then it says hello", "--intent", "INT-1",
         "--test", "tests/test_greeting.py"),
        ("tdd-red", "--issue", "fix-greeting", "--scenario", "TRC-001", "--",
         sys.executable, "-m", "pytest", "-q", "tests/test_greeting.py"),
    ]
    for step in steps:
        r = _cli(old_cli, root, *step)
        assert r.returncode == 0, (step, r.stdout + r.stderr)
    (root / "data" / "greeting.txt").write_text("Hello, %s!\n")
    r = _cli(old_cli, root, "tdd-green", "--issue", "fix-greeting", "--scenario",
             "TRC-001", "--", sys.executable, "-m", "pytest", "-q",
             "tests/test_greeting.py")
    assert r.returncode == 0, r.stdout + r.stderr
    return root


def _verdict(cli, root):
    """Each check's name and result, from `compass check --verbose`."""
    r = _cli(cli, root, "check", "--issue", "fix-greeting", "--verbose")
    rows = {}
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] in ("PASS", "FAIL", "SKIP", "N/A", "WARN") \
                and parts[1].endswith(":"):
            rows[parts[1].rstrip(":")] = parts[0]
    return r.returncode, rows


def test_up_1_the_issue_gets_the_same_verdict_after_the_upgrade(release, tmp_path):
    old_cli = release / "cli" / "compass"
    root = _project(tmp_path, old_cli)
    before_code, before = _verdict(old_cli, root)
    after_code, after = _verdict(CLI, root)
    assert before, "5.0.0's check printed no per-check results"
    assert after_code == before_code, (before_code, after_code)
    changed = {k: (before[k], after.get(k)) for k in before if after.get(k) != before[k]}
    assert not changed, f"checks whose verdict changed on upgrade: {changed}"
    lint = _cli(CLI, root, "issue", "lint", "--issue", "fix-greeting")
    assert lint.returncode == 0, lint.stdout + lint.stderr


def test_up_1_every_example_manifest_from_5_0_0_still_lints(release):
    manifests = sorted((release / "examples").rglob(".compass/work/*/manifest.yml"))
    assert manifests, "5.0.0 shipped no example manifests to read"
    failures = []
    for path in manifests:
        project = path.parents[3]
        slug = path.parent.name
        r = _cli(CLI, project, "issue", "lint", "--issue", slug)
        if r.returncode != 0:
            failures.append(f"{path.relative_to(release)}: {r.stdout.strip()[-200:]}")
    assert not failures, "\n".join(failures)
