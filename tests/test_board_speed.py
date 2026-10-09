"""How fast the board builds: three timing scenarios of issue `compass-board`.

The board data for a realistic archive, the two commands on this checkout's
own archive, and `--worktrees` over ten worktrees. Each test is marked
`serial`, so it runs after the parallel pass on an idle machine.

The tracked archive sample is copied to build a large archive. Copies of one
manifest have identical bytes, so each copy ends with a comment naming its
folder; otherwise a cache keyed on content would make the timing meaningless.

The first two tests depend on the separate manifest-parsing speed issue and
fail until it lands.
"""
from __future__ import annotations

import datetime
import os
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "cli" / "compass"
sys.path.insert(0, str(ROOT / "cli"))
sys.path.insert(0, str(ROOT / "tests"))

import archive  # noqa: E402

ISSUES = 500
RUNS = 3


def _copy_sample_work(target_work, count=None, tag=""):
    """Copy the sample's issue folders into `target_work`, repeating them
    until `count` folders exist (all of them once when `count` is None).
    Every manifest gets a trailing comment naming its folder."""
    source = archive.sample_root() / ".compass" / "work"
    folders = sorted(p for p in source.iterdir() if (p / "manifest.yml").is_file())
    assert folders, "the archive sample holds no issues"
    target_work.mkdir(parents=True, exist_ok=True)
    wanted = count or len(folders)
    made = 0
    round_no = 0
    while made < wanted:
        for folder in folders:
            if made >= wanted:
                break
            name = folder.name if round_no == 0 else f"{folder.name}-copy{round_no}"
            dest = target_work / name
            shutil.copytree(folder, dest)
            with open(dest / "manifest.yml", "a", encoding="utf-8") as fh:
                fh.write(f"\n# copy {tag}{name}\n")
            made += 1
        round_no += 1
    return made


def _git(cwd, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
         "-c", "commit.gpgsign=false", *args],
        cwd=str(cwd), env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout


def _timed_command(cwd, *args, env=None):
    start = time.monotonic()
    r = subprocess.run([sys.executable, str(CLI), *args], cwd=cwd,
                       capture_output=True, text=True, env=env)
    elapsed = time.monotonic() - start
    assert r.returncode == 0, r.stdout + r.stderr
    return elapsed


def _recorder_env(tmp_path):
    """An environment whose BROWSER records instead of opening anything."""
    recorder = tmp_path / "browser.sh"
    recorder.write_text('#!/bin/sh\necho "$@" >> "$0.log"\n', encoding="utf-8")
    recorder.chmod(0o755)
    env = dict(os.environ)
    env["BROWSER"] = str(recorder)
    return env


@pytest.mark.serial
def test_trc_a4_board_data_speed_on_realistic_archive(tmp_path):
    from compass_pkg import flow
    work = tmp_path / "proj" / ".compass" / "work"
    count = _copy_sample_work(work, ISSUES)
    assert count == ISSUES
    times = []
    for _ in range(RUNS):
        start = time.monotonic()
        parsed = flow.read_checkout(str(work))
        data = flow.board(str(work), today=datetime.date.today(), parsed=parsed)
        times.append(time.monotonic() - start)
        assert data
    median = statistics.median(times)
    assert median < 2.0, f"board data over {ISSUES} issues took {median:.2f}s (runs {times})"


@pytest.mark.serial
def test_trc_a5_commands_speed_on_full_archive(tmp_path):
    if not archive.full_archive():
        pytest.skip(archive.NEEDS_FULL_ARCHIVE)
    env = _recorder_env(tmp_path)
    out = tmp_path / "board.html"
    commands = {
        "compass flow": ["flow"],
        "compass board render --no-open": ["board", "render", "--no-open", "--out", str(out)],
    }
    medians = {}
    for label, args in commands.items():
        times = [_timed_command(ROOT, *args, env=env) for _ in range(RUNS)]
        print(f"{label}: " + ", ".join(f"{t:.2f}s" for t in times))
        medians[label] = statistics.median(times)
    for label, median in medians.items():
        assert median < 2.0, f"{label} took {median:.2f}s (median of {RUNS})"


def _worktree_project(tmp_path, trees=10):
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(main, "commit", "-q", "--allow-empty", "-m", "start")
    (main / ".compass" / "work").mkdir(parents=True)
    for n in range(trees):
        wt = tmp_path / "wt" / f"tree-{n}"
        wt.parent.mkdir(parents=True, exist_ok=True)
        _git(main, "worktree", "add", "-q", "--detach", str(wt))
        _copy_sample_work(wt / ".compass" / "work", tag=f"tree-{n}/")
    return main


@pytest.mark.serial
def test_trc_w6_worktrees_speed(tmp_path):
    main = _worktree_project(tmp_path)
    out = tmp_path / "board.html"
    env = _recorder_env(tmp_path)
    times = [_timed_command(main, "board", "render", "--no-open", "--worktrees",
                            "--out", str(out), env=env) for _ in range(RUNS)]
    median = statistics.median(times)
    assert "Trees read: 11" in out.read_text(encoding="utf-8")
    assert median < 5.0, f"--worktrees over ten worktrees took {median:.2f}s (runs {times})"
