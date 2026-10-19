"""The shard command CI uses to split the parallel test pass.

`scripts/ci-shard.py INDEX COUNT` prints the test files of one shard. The
`shard` job in `.github/workflows/compass.yml` hands that list to pytest, so
a file the command drops is a file no shard runs, and a file it prints twice
runs twice. These tests run the command as CI does and compare its lists
with what pytest itself collects.
"""
from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHARD = ROOT / "scripts" / "ci-shard.py"
DURATIONS = ROOT / "scripts" / "ci-durations.py"
TABLE = ROOT / "tests" / "ci-durations.json"
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

    The shard command decides from paths and the durations table alone, so
    every other file is copied as an empty file; that keeps the copy fast
    while every name, folder, weight and pytest.ini setting stays the same.
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
    if TABLE.is_file():
        (root / "tests" / TABLE.name).write_text(TABLE.read_text())
    return root


def _check_partition(lists: list[list[str]]) -> set[str]:
    flat = [f for shard in lists for f in shard]
    assert len(flat) == len(set(flat)), "a file appears in two shards: " + ", ".join(
        sorted({f for f in flat if flat.count(f) > 1}))
    lengths = [len(shard) for shard in lists]
    assert min(lengths) >= 1, lengths
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


# --- CRT-22: weights from recorded durations ------------------------------

def _weighted_root(tmp_path: Path, files: list[str],
                   seconds: dict[str, float]) -> Path:
    root = tmp_path / "checkout"
    (root / "tests").mkdir(parents=True)
    for name in files:
        (root / "tests" / name).write_text("def test_x():\n    pass\n")
    (root / "tests" / "ci-durations.json").write_text(json.dumps(
        {"run": 1, "seconds": {f"tests/{k}": v for k, v in seconds.items()}}))
    return root


def _loads(count: int, root: Path) -> list[float]:
    found = []
    for index in range(count):
        r = _shard(index, count, "--loads", root=root)
        assert r.returncode == 0, (index, r.stdout, r.stderr)
        match = re.fullmatch(
            rf"shard {index} of {count} holds \d+ files?, ([\d.]+) seconds\n",
            r.stdout)
        assert match, r.stdout
        found.append(float(match.group(1)))
    return found


def test_crt_22_weights_balance_where_counts_cannot(tmp_path):
    """Two heavy files and six light ones: a split by count puts a light
    file beside a heavy one, so its shard weighs 40 against 30. The split
    by weight gives each shard 30."""
    light = [f"test_{c}.py" for c in "cdefgh"]
    seconds = {"test_a.py": 30, "test_b.py": 30, **{f: 10 for f in light}}
    root = _weighted_root(tmp_path, list(seconds), seconds)
    lists = _lists(SHARDS, root)
    assert lists == [
        ["tests/test_a.py"],
        ["tests/test_b.py"],
        ["tests/test_c.py", "tests/test_e.py", "tests/test_g.py"],
        ["tests/test_d.py", "tests/test_f.py", "tests/test_h.py"],
    ], lists
    assert _loads(SHARDS, root) == [30.0, 30.0, 30.0, 30.0]
    assert _lists(SHARDS, root) == lists, "two runs printed different lists"


def test_crt_22_a_file_missing_from_the_table_gets_the_median(tmp_path):
    """A file the table does not hold still lands in exactly one shard, at
    the median of the table's weights."""
    seconds = {"test_a.py": 10, "test_b.py": 20, "test_c.py": 30}
    root = _weighted_root(tmp_path, [*seconds, "test_new.py"], seconds)
    lists = _lists(2, root)
    flat = [f for shard in lists for f in shard]
    assert flat.count("tests/test_new.py") == 1, lists
    assert sorted(flat) == ["tests/test_a.py", "tests/test_b.py",
                            "tests/test_c.py", "tests/test_new.py"]
    # 10 + 20 + 30 recorded, and 20 for the new file.
    assert _loads(2, root) == [40.0, 40.0]

    # A table entry for a file that no longer exists places nothing.
    (root / "tests" / "test_c.py").unlink()
    flat = [f for shard in _lists(2, root) for f in shard]
    assert sorted(flat) == ["tests/test_a.py", "tests/test_b.py",
                            "tests/test_new.py"]


def test_crt_22_the_committed_table_partitions_the_collected_files():
    """The committed table is well formed, and the shards it weighs still
    hold every collected file exactly once."""
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    assert isinstance(table["run"], int), table.get("run")
    assert table["seconds"], "the table holds no file"
    for path, seconds in table["seconds"].items():
        assert path.startswith("tests/") and path.endswith(".py"), path
        assert isinstance(seconds, (int, float)) and seconds > 0, (path, seconds)
    union = _check_partition(_lists(SHARDS))
    collected = _collected_files()
    assert union == collected, {
        "in no shard": sorted(collected - union),
        "not collected by pytest": sorted(union - collected)}


def test_crt_22_the_committed_table_covers_the_test_files():
    """A file the table lacks weighs the median, so a table that lists only
    a few files splits the rest by guesswork. The table must hold a
    duration for at least 80 percent of the files the shards split. A table
    built from a full run holds about 86 percent of the files; a table of
    the slowest tests alone held about 8 percent."""
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("ci_shard", SHARD)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(ROOT / "scripts"))
    files = module.test_files(ROOT)
    recorded = module.recorded_seconds(ROOT)
    covered = [f for f in files if f in recorded]
    assert len(covered) >= 0.80 * len(files), (len(covered), len(files))


GH_SHIM = '''#!{python}
import json, os, sys
base = os.environ["FAKE_GH_DIR"]
argv = sys.argv[1:]
table = json.load(open(os.path.join(base, "table.json")))
for entry in table:
    if entry["argv"] == argv:
        sys.stdout.write(entry.get("stdout", ""))
        sys.exit(entry.get("exit", 0))
sys.stderr.write("gh stand-in: no answer for " + " ".join(argv) + "\\n")
sys.exit(97)
'''

STAMP = "2026-10-14T04:11:30.2207631Z"


def _log(job: str, lines: list[str]) -> str:
    return "".join(f"{job}\tRun this shard's tests\t{STAMP} {line}\n"
                   for line in lines)


def _durations(tmp_path: Path, conclusions: list[str]):
    work = tmp_path / "gh"
    (work / "bin").mkdir(parents=True)
    shim = work / "bin" / "gh"
    shim.write_text(GH_SHIM.format(python=sys.executable))
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    jobs = [{"databaseId": 11, "name": "count", "conclusion": "success"}]
    jobs += [{"databaseId": 20 + i, "name": f"shard ({i})", "conclusion": c}
             for i, c in enumerate(conclusions)]
    logs = [
        _log("shard (0)", [
            "4.00s call     tests/test_z.py::test_before_the_section",
            "=" * 29 + " slowest 25 durations " + "=" * 29,
            "83.77s call     tests/test_x.py::test_one",
            "1.50s setup    tests/test_x.py::test_one",
            "2.00s call     tests/sub/test_y.py::test_p[a b]",
            "10 passed in 3.00s",
            "7.00s call     tests/test_z.py::test_after_the_section",
        ]),
        _log("shard (1)", [
            "=" * 29 + " slowest durations " + "=" * 29,
            "0.50s teardown tests/test_x.py::test_two",
            "(3 durations < 0.005s hidden.  Use -vv to show these durations.)",
            "4 passed in 1.00s",
        ]),
    ]
    table = [{"argv": ["run", "view", "123", "--json", "jobs"],
              "stdout": json.dumps({"jobs": jobs})}]
    table += [{"argv": ["run", "view", "--job", str(20 + i), "--log"],
               "stdout": logs[i]} for i in range(len(conclusions))]
    (work / "table.json").write_text(json.dumps(table))
    env = dict(os.environ, FAKE_GH_DIR=str(work),
               PATH=f"{shim.parent}{os.pathsep}{os.environ['PATH']}")
    out = tmp_path / "ci-durations.json"
    r = subprocess.run([sys.executable, str(DURATIONS), "123", "--out", str(out)],
                       cwd=tmp_path, capture_output=True, text=True, env=env,
                       timeout=60)
    return r, out


def test_crt_22_durations_table_rebuilds_from_a_run(tmp_path):
    """The table is the per-file sum of every phase each shard's
    slowest-durations section lists, and a run with a shard that did not
    succeed writes no table."""
    r, out = _durations(tmp_path / "green", ["success", "success"])
    assert r.returncode == 0, (r.stdout, r.stderr)
    table = json.loads(out.read_text())
    assert table == {"run": 123, "seconds": {
        "tests/sub/test_y.py": 2.0, "tests/test_x.py": 85.77}}, table

    r, out = _durations(tmp_path / "cancelled", ["success", "cancelled"])
    assert r.returncode == 1, (r.stdout, r.stderr)
    assert "shard (1)" in r.stderr and "cancelled" in r.stderr, r.stderr
    assert not out.exists()
