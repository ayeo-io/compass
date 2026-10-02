"""validate.sh does not fail on the references inside an issue's own documents.

An issue's documents under `docs/compass/<created>-<slug>/` record what was
true when they were written. Many name a script that 4.0.0 renamed.
Rewriting them to satisfy a scanner would
falsify the record, so validate.sh skips them, by the same rule every other
repository-wide scan uses (`issue_layout.is_issue_document`).

The archive is gitignored, so a git checkout never showed the failure. A copy
of a working tree with no `.git` did: validate.sh falls back to a recursive
grep there and read the whole archive. Both paths are tested here, each with a
planted broken reference in a living file to prove the scan still fails.

Scenario id: VSA-1, in the delivery approach of issue
`validate-scan-vs-archive`.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: An issue document naming a script that no longer exists, as the archive does.
RECORD = "docs/compass/2026-01-01-old-issue/acceptance-criteria.md"
RECORD_TEXT = "The builder runs `scripts/retired-helper.sh` to set up worktrees.\n"
#: A living document naming a script that does not exist.
LIVING = "docs/living-note.md"
LIVING_TEXT = "Run `scripts/no-such-helper.sh` first.\n"


def _copy_tracked(dest: Path) -> None:
    """Copy the tracked tree, and nothing else, into `dest`."""
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                           capture_output=True, check=True).stdout
    for rel in filter(None, files.decode().split("\0")):
        src = ROOT / rel
        if src.is_dir():
            continue  # a submodule, which git lists as one path
        # A tracked file missing from the working tree used to be skipped
        # silently, and a later check failed far from the cause. Name it.
        assert src.is_file(), f"tracked file {rel} is missing from the working tree"
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)


def _plant(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


def _validate(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "scripts/validate.sh", "--quiet"], cwd=root,
                          capture_output=True, text=True, timeout=300)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture(scope="module")
def tree(tmp_path_factory) -> Path:
    dest = tmp_path_factory.mktemp("tree")
    _copy_tracked(dest)
    return dest


def _as_git_checkout(src: Path, dest: Path) -> Path:
    shutil.copytree(src, dest)
    _git(dest, "init", "-q")
    _git(dest, "add", "-A")
    # The archive is gitignored in this repository. Force-add the record so
    # the git path meets it too, as a tracked issue document would.
    _git(dest, "add", "-f", RECORD)
    return dest


def test_vsa_1_no_git_copy_skips_an_issue_record(tree, tmp_path):
    root = tmp_path / "copy"
    shutil.copytree(tree, root)
    _plant(root, RECORD, RECORD_TEXT)
    result = _validate(root)
    assert result.returncode == 0, (
        "validate.sh failed on a reference inside an issue record:\n"
        + result.stderr[-2000:])


def test_vsa_1_no_git_copy_still_fails_a_living_file(tree, tmp_path):
    root = tmp_path / "copy"
    shutil.copytree(tree, root)
    _plant(root, RECORD, RECORD_TEXT)
    _plant(root, LIVING, LIVING_TEXT)
    result = _validate(root)
    assert result.returncode == 1
    assert "scripts/no-such-helper.sh" in result.stderr
    assert "scripts/retired-helper.sh" not in result.stderr


def test_vsa_1_git_checkout_skips_a_tracked_issue_record(tree, tmp_path):
    _plant(tree, RECORD, RECORD_TEXT)
    try:
        root = _as_git_checkout(tree, tmp_path / "repo")
    finally:
        (tree / RECORD).unlink()
    result = _validate(root)
    assert result.returncode == 0, (
        "validate.sh failed on a reference inside a tracked issue record:\n"
        + result.stderr[-2000:])


def test_vsa_1_git_checkout_still_fails_a_living_file(tree, tmp_path):
    _plant(tree, RECORD, RECORD_TEXT)
    _plant(tree, LIVING, LIVING_TEXT)
    try:
        root = _as_git_checkout(tree, tmp_path / "repo")
    finally:
        (tree / RECORD).unlink()
        (tree / LIVING).unlink()
    result = _validate(root)
    assert result.returncode == 1
    assert "scripts/no-such-helper.sh" in result.stderr
    assert "scripts/retired-helper.sh" not in result.stderr


def test_vsa_1_the_header_states_the_rule():
    header = (ROOT / "scripts" / "validate.sh").read_text(encoding="utf-8")
    header = header.split("set -euo pipefail", 1)[0]
    assert "docs/compass/<created>-<slug>/" in header, (
        "validate.sh's header must say it skips an issue's own documents")
