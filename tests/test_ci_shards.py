"""The shard command CI uses to split the parallel test pass.

`scripts/ci-shard.py INDEX COUNT` prints the test files of one shard. The
`shard` job in `.github/workflows/compass.yml` hands that list to pytest, so
a file the command drops is a file no shard runs, and a file it prints twice
runs twice. These tests run the command as CI does and compare its lists
with what pytest itself collects.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHARD = ROOT / "scripts" / "ci-shard.py"
SHARDS = 4


def _shard(*args, root: Path | None = None):
    cmd = [sys.executable, str(SHARD), *map(str, args)]
    if root is not None:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=60)


def _lists(count: int, root: Path | None = None) -> list[list[str]]:
    lists = []
    for index in range(count):
        r = _shard(index, count, root=root)
        assert r.returncode == 0, (index, count, r.stdout, r.stderr)
        lists.append(r.stdout.splitlines())
    return lists


def _collected_files() -> set[str]:
    """The test files pytest collects from tests/ under this pytest.ini.

    pytest.ini adds its own -q, so --collect-only -q prints one
    "<path>: <n>" line per collected file.
    """
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                        "tests/"], cwd=ROOT, capture_output=True, text=True,
                       env=env, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    files = {line.rsplit(": ", 1)[0] for line in r.stdout.splitlines()
             if line.endswith(tuple("0123456789")) and ".py: " in line}
    assert files, r.stdout[-2000:]
    return files


def _layout_copy(tmp_path: Path) -> Path:
    """A copy of this checkout's tests/ layout and pytest.ini.

    The shard command decides from paths alone, so every file is copied as
    an empty file; that keeps the copy fast while every name, folder and
    pytest.ini setting stays the same.
    """
    root = tmp_path / "checkout"
    (root / "tests").mkdir(parents=True)
    (root / "pytest.ini").write_text((ROOT / "pytest.ini").read_text())
    for path in (ROOT / "tests").rglob("*"):
        rel = path.relative_to(ROOT)
        if "__pycache__" in rel.parts:
            continue
        if path.is_dir():
            (root / rel).mkdir(parents=True, exist_ok=True)
        else:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).touch()
    return root


def _check_partition(lists: list[list[str]]) -> set[str]:
    flat = [f for shard in lists for f in shard]
    assert len(flat) == len(set(flat)), "a file appears in two shards: " + ", ".join(
        sorted({f for f in flat if flat.count(f) > 1}))
    lengths = [len(shard) for shard in lists]
    assert min(lengths) >= 1, lengths
    assert max(lengths) - min(lengths) <= 1, lengths
    return set(flat)


def test_crt_10_every_file_in_exactly_one_shard(tmp_path):
    """The shards partition the files pytest collects."""
    lists = _lists(SHARDS)
    union = _check_partition(lists)
    collected = _collected_files()
    assert union == collected, {
        "in no shard": sorted(collected - union),
        "not collected by pytest": sorted(union - collected)}
    assert _lists(SHARDS) == lists, "two runs printed different lists"

    # The count is one setting in the workflow, so the split must hold for
    # any count, not only today's.
    for count in (1, 3, 5):
        assert _check_partition(_lists(count)) == union, count

    # A new file, not added to git, lands in exactly one shard.
    root = _layout_copy(tmp_path / "planted")
    (root / "tests" / "test_zz_planted.py").write_text(
        "def test_planted():\n    pass\n")
    lists = _lists(SHARDS, root)
    _check_partition(lists)
    holders = [i for i, shard in enumerate(lists)
               if "tests/test_zz_planted.py" in shard]
    assert len(holders) == 1, holders

    # A renamed file lands in exactly one shard and the old name in none.
    root = _layout_copy(tmp_path / "renamed")
    old = root / "tests" / "test_workflow_pins.py"
    old.rename(root / "tests" / "test_workflow_pins_renamed.py")
    lists = _lists(SHARDS, root)
    _check_partition(lists)
    flat = [f for shard in lists for f in shard]
    assert flat.count("tests/test_workflow_pins_renamed.py") == 1
    assert "tests/test_workflow_pins.py" not in flat


def test_crt_10_follows_pytest_folder_and_name_rules(tmp_path):
    """The command lists what pytest would collect and nothing else: names
    matching python_files, and no folder pytest does not recurse into."""
    root = tmp_path / "checkout"
    tests = root / "tests"
    for rel in ["test_a.py", "b_test.py", "helper.py", "sub/test_c.py",
                ".hidden/test_d.py", "venv/test_e.py", "env1/test_f.py",
                "node_modules/test_g.py", "build/test_h.py"]:
        (tests / rel).parent.mkdir(parents=True, exist_ok=True)
        (tests / rel).write_text("def test_x():\n    pass\n")
    (tests / "env1" / "pyvenv.cfg").write_text("home = /usr\n")
    (root / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")
    lists = _lists(1, root)
    assert lists == [["tests/b_test.py", "tests/sub/test_c.py",
                      "tests/test_a.py"]], lists

    (root / "pytest.ini").write_text(
        "[pytest]\npython_files = check_*.py\nnorecursedirs = sub\n")
    (tests / "check_one.py").write_text("")
    (tests / "sub" / "check_two.py").write_text("")
    (tests / "build" / "check_three.py").write_text("")
    assert _lists(1, root) == [["tests/build/check_three.py",
                                "tests/check_one.py"]]


def test_crt_10_a_shard_with_no_file_fails(tmp_path):
    """A shard with no file must not print an empty list, because pytest
    given no path runs the whole of testpaths."""
    root = tmp_path / "checkout"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_only.py").write_text("")
    r = _shard(1, 2, root=root)
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert r.stdout == ""
    assert "no test files" in r.stderr


@pytest.mark.parametrize("args, reason", [
    (["4", "4"], "not below"),
    (["-1", "4"], "negative"),
    (["0", "0"], "at least 1"),
    (["a", "4"], "whole number"),
    ([], "INDEX and COUNT"),
])
def test_crt_11_bad_arguments_refused(args, reason):
    """Bad arguments exit 2 with the reason and no file."""
    r = _shard(*args)
    assert r.returncode == 2, (args, r.returncode, r.stdout, r.stderr)
    assert r.stdout == "", r.stdout
    assert reason in r.stderr, r.stderr
