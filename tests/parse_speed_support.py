"""Support for the manifest-parse-speed tests: the exact comparison, the
project builders, the process runners and the code-before-the-change runner.

Nothing here is shipped, and nothing under `cli/` names this module.
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

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CLI_DIR = ROOT / "cli"

#: The switch that turns on the tests comparing with the code before the change.
BEFORE_COMMIT = "COMPASS_BEFORE_COMMIT"
FIXED_AT = "2026-10-09T12:00:00Z"
FIXED_CLOCK = HERE / "fixed_clock.py"


# --- the exact comparison ----------------------------------------------------

def _scalar_differs(a, b):
    if isinstance(a, float):
        return repr(a) != repr(b)
    if isinstance(a, datetime.datetime):
        return repr(a) != repr(b)
    return a != b


def _walk(a, b, where, seen_a, seen_b):
    """The first position where two parsed values differ, as (where, why), or None."""
    if type(a) is not type(b):
        return where, f"type {type(a).__name__} against {type(b).__name__}"
    if isinstance(a, (dict, list)):
        ref_a, ref_b = seen_a.get(id(a)), seen_b.get(id(b))
        if ref_a != ref_b:
            return where, "shared object differs"
        if ref_a is not None:
            return None
        seen_a[id(a)] = seen_b[id(b)] = len(seen_a)
        if len(a) != len(b):
            return where, "length differs"
        if isinstance(a, list):
            for index, (x, y) in enumerate(zip(a, b)):
                found = _walk(x, y, f"{where}[{index}]", seen_a, seen_b)
                if found:
                    return found
            return None
        for (key_a, val_a), (key_b, val_b) in zip(a.items(), b.items()):
            if type(key_a) is not type(key_b) or _scalar_differs(key_a, key_b):
                return where, f"key order or key differs at {key_a!r}"
            found = _walk(val_a, val_b, f"{where}.{key_a}", seen_a, seen_b)
            if found:
                return found
        return None
    if _scalar_differs(a, b):
        return where, f"value {a!r} against {b!r}"
    return None


def exact_difference(a, b):
    """None when two parsed values match exactly, else (where, why).

    Exact means: the same type at every position, and identical text from the
    bundled PyYAML's safe_dump with sort_keys=False. The walk finds the
    position; the text comparison is the stated definition and the backstop."""
    found = _walk(a, b, "$", {}, {})
    if found:
        return found
    if yaml.safe_dump(a, sort_keys=False) != yaml.safe_dump(b, sort_keys=False):
        return "$", "serialised text differs"
    return None


def safe_load_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def parity_failures(read, paths):
    """One message per path where `read` does not give what safe_load gives."""
    failures = []
    for path in paths:
        found = exact_difference(read(path), safe_load_file(path))
        if found:
            failures.append(f"{path}: {found[0]}: {found[1]}")
    return failures


# --- projects ----------------------------------------------------------------

def sample_manifests(sample_root):
    """The archive sample's manifest files, in slug order."""
    work = Path(sample_root) / ".compass" / "work"
    return [work / d / "manifest.yml" for d in sorted(os.listdir(work))
            if (work / d / "manifest.yml").is_file()]


def build_project(dest, sample_root, count=484):
    """A project whose .compass/work holds `count` issue folders, each a copy
    of one sample manifest, taken in turn under distinct slugs."""
    dest = Path(dest)
    sources = sample_manifests(sample_root)
    work = dest / ".compass" / "work"
    for index in range(count):
        folder = work / f"copy-{index:03d}"
        folder.mkdir(parents=True)
        shutil.copyfile(sources[index % len(sources)], folder / "manifest.yml")
    return work


def append_comment(work_root, text):
    """Append a comment line to every manifest: bytes change, data does not.
    The line names the issue folder, so no two manifests share their bytes
    (copies of one sample manifest would otherwise share a parse)."""
    for manifest in sorted(Path(work_root).glob("*/manifest.yml")):
        with open(manifest, "a", encoding="utf-8") as fh:
            fh.write(f"# {text} {manifest.parent.name}\n")


# --- running the CLI ---------------------------------------------------------

def clean_env(home, **extra):
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "NO_COLOR": "1", "COLUMNS": "100",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    env.update(extra)
    return env


def run_compass(cli_dir, args, cwd, home, clock=None, **env_extra):
    """Run `compass <args>`; with `clock` (an ISO instant), under the fixed clock.
    Returns (exit code, stdout, stderr)."""
    cli_dir = Path(cli_dir)
    if clock:
        cmd = [sys.executable, str(FIXED_CLOCK), "--cli", str(cli_dir), "--at", clock,
               "--", *args]
    else:
        cmd = [sys.executable, str(cli_dir / "compass"), *args]
    done = subprocess.run(cmd, cwd=cwd, env=clean_env(home, **env_extra),
                          capture_output=True, text=True, timeout=600)
    return done.returncode, done.stdout, done.stderr


def time_flow(cli_dir, work_root, cwd, home):
    """Wall seconds of one new `compass flow` process, output discarded."""
    cmd = [sys.executable, str(Path(cli_dir) / "compass"), "flow", "--work-root",
           str(work_root)]
    start = time.perf_counter()
    done = subprocess.run(cmd, cwd=cwd, env=clean_env(home), stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, timeout=600)
    elapsed = time.perf_counter() - start
    assert done.returncode == 0, f"compass flow exited {done.returncode}"
    return elapsed


_PARSE_PROBE = """
import sys, time
sys.path.insert(0, sys.argv[1])
import compass_pkg  # puts the bundled PyYAML first
import yaml
paths = open(sys.argv[2], encoding="utf-8").read().split("\\n")
start = time.perf_counter()
for p in paths:
    if p:
        with open(p, encoding="utf-8") as fh:
            yaml.safe_load(fh)
print(time.perf_counter() - start)
"""


def parse_time(cli_dir, work_root, scratch):
    """Seconds one new process takes to read and parse every manifest once with
    the bundled PyYAML."""
    listing = Path(scratch) / "manifest-paths.txt"
    listing.write_text("\n".join(str(p) for p in sorted(Path(work_root).glob("*/manifest.yml"))),
                       encoding="utf-8")
    done = subprocess.run([sys.executable, "-c", _PARSE_PROBE, str(cli_dir), str(listing)],
                          capture_output=True, text=True, timeout=600, check=True)
    return float(done.stdout.strip())


def median_of(count, measure):
    return statistics.median(measure() for _ in range(count))


# --- the code before the change ---------------------------------------------

class BaseCodeUnavailable(AssertionError):
    """The commit that names the code before the change cannot be read."""


def before_commit():
    """The commit named by the switch, or None when the switch is off."""
    value = os.environ.get(BEFORE_COMMIT, "").strip()
    return value or None


def extract_base_code(commit, dest):
    """Copy the CLI at `commit` out of git into `dest/cli`. Raises when the
    commit is not reachable, so an unreachable commit fails a test that has
    the switch on and does not skip it."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    archive = subprocess.run(["git", "archive", commit, "cli"], cwd=ROOT,
                             capture_output=True, timeout=120)
    if archive.returncode != 0:
        raise BaseCodeUnavailable(
            f"{BEFORE_COMMIT}={commit} cannot be read: "
            f"{archive.stderr.decode('utf-8', 'replace').strip()}")
    untar = subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout,
                           capture_output=True, timeout=120)
    if untar.returncode != 0:
        raise BaseCodeUnavailable(f"the archive of {commit} did not unpack")
    return dest / "cli"


def copy_current_code(dest):
    """Copy this tree's CLI (without bytecode) to `dest/cli`."""
    target = Path(dest) / "cli"
    shutil.copytree(CLI_DIR, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


class SwappableCode:
    """One folder path that holds the base code or the current code in turn, so
    no output can differ by the folder name."""

    def __init__(self, parent, base_cli, current_cli):
        self.path = Path(parent) / "cli"
        self._parked = {"base": Path(parent) / "cli-base", "current": Path(parent) / "cli-current"}
        shutil.move(str(base_cli), str(self._parked["base"]))
        shutil.move(str(current_cli), str(self._parked["current"]))
        self.active = None

    def use(self, which):
        if self.active == which:
            return self.path
        if self.active:
            os.rename(self.path, self._parked[self.active])
        os.rename(self._parked[which], self.path)
        self.active = which
        return self.path
