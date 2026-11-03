"""Run the TypeScript reference example from a Compass test.

`examples/atdd-adapters/typescript/` needs Node 22.13 or later, which runs its
TypeScript files with `--experimental-strip-types` and its store with
`node:sqlite`. Its layering test also needs the example's pinned packages,
which `npm ci` installs into its `node_modules/`. The Python suite must pass on
a machine without them, so a test that needs one skips and names what is
missing. The CI job `atdd-adapter-typescript` sets COMPASS_REQUIRE_TYPESCRIPT=1,
and there a missing piece fails the test instead, so the job cannot pass on
tests that never ran.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "atdd-adapters" / "typescript"
MODULES = EXAMPLE / "node_modules"
NODE_AT_LEAST = (22, 13)
REQUIRE = "COMPASS_REQUIRE_TYPESCRIPT"


#: The example's runner adapter, run as its npm scripts run it. Compass tests call
#: node directly, so npm writes no cache or log into the fixture project.
RUN = ("node", "--experimental-strip-types", "--disable-warning=ExperimentalWarning",
       "tests/acceptance/run.ts")
LAYERING = (*RUN, "tests/acceptance/layering.test.ts")


def _node_version():
    node = shutil.which("node")
    if node is None:
        return None
    run = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
    found = re.match(r"v(\d+)\.(\d+)", run.stdout.strip())
    return (int(found.group(1)), int(found.group(2))) if found else None


def missing(packages=False):
    """What this machine lacks to run the example, or None. `packages`: the
    test also needs the example's `node_modules/`."""
    version = _node_version()
    if version is None:
        return "node is not on PATH; the TypeScript reference example needs Node 22.13 or later"
    if version < NODE_AT_LEAST:
        return (f"node on PATH is {version[0]}.{version[1]}; the TypeScript reference example "
                f"needs Node 22.13 or later")
    if shutil.which("npm") is None:
        return "npm is not on PATH; the TypeScript reference example runs through npm scripts"
    if packages and not (MODULES / "typescript").is_dir():
        return ("examples/atdd-adapters/typescript/node_modules is missing; run `npm ci` in "
                "that folder to install the example's pinned packages")
    return None


def need(packages=False):
    """Skip the calling test when the machine lacks Node, npm or the example's
    packages, naming what is missing; fail instead when COMPASS_REQUIRE_TYPESCRIPT is set."""
    reason = missing(packages)
    if reason is None:
        return
    if os.environ.get(REQUIRE):
        pytest.fail(f"{REQUIRE} is set, but {reason}")
    pytest.skip(reason)


def copy(dest: Path) -> Path:
    """Copy the example to `dest`, without its packages, and link `node_modules`
    to the example's own when it is installed."""
    shutil.copytree(EXAMPLE, dest, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("node_modules"))
    if MODULES.is_dir():
        (dest / "node_modules").symlink_to(MODULES, target_is_directory=True)
    return dest


def environment(folder: Path, extra=None) -> dict:
    """The environment a run of the example gets: the caller's, without the
    variables an outer run set, and with a temporary folder inside the test's own."""
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("ACCEPTANCE_", "TODO_", "COMPASS_JUNIT", "PYTEST_", "npm_"))}
    scratch = folder.parent / "tmp"
    scratch.mkdir(exist_ok=True)
    env["TMPDIR"] = str(scratch)
    env.update(extra or {})
    return env


def npm(folder: Path, script: str, *args: str, env=None) -> subprocess.CompletedProcess:
    """`npm run --silent <script> -- <args>` in `folder`."""
    return subprocess.run(["npm", "run", "--silent", script, "--", *args], cwd=folder,
                          env=environment(folder, env), capture_output=True, text=True,
                          timeout=300)


def output(run: subprocess.CompletedProcess) -> str:
    return f"exit {run.returncode}\n--- stdout\n{run.stdout}\n--- stderr\n{run.stderr}"


def passed(run: subprocess.CompletedProcess) -> int:
    """The `pass` count node's spec report prints."""
    found = re.search(r"^ℹ pass (\d+)$", run.stdout, re.M)
    return int(found.group(1)) if found else 0
