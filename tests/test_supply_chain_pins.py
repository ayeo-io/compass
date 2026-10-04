"""Every action and package CI uses is pinned to an exact version.

The self-check workflow pinned its actions by commit SHA, but the files in
`ci/` that adopters copy pinned by tag, the pip steps installed whatever was
newest, and the cucumber-js job ran `npm install`, which may rewrite its
lockfile (#99). A tag or an unpinned package can change under a run with
nothing in this repository changing.

Scenario id: SP-1 (issue `supply-chain-pins`).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
COPYABLE = sorted((ROOT / "ci").glob("*.yml")) + [ROOT / "ci" / "README.md"]
USES = re.compile(r"^\s*-?\s*uses:\s*(\S+)", re.M)
PIN = re.compile(r"@[0-9a-f]{40}$")


def test_sp_1_every_action_is_pinned_by_commit_sha():
    unpinned = []
    for path in WORKFLOWS + COPYABLE:
        for ref in USES.findall(path.read_text(encoding="utf-8")):
            if ref.startswith("./"):
                continue
            if not PIN.search(ref):
                unpinned.append(f"{path.relative_to(ROOT)}: {ref}")
    assert not unpinned, "actions pinned by tag, not SHA:\n  " + "\n  ".join(unpinned)


def test_sp_1_every_pip_install_takes_exact_versions():
    loose = []
    for path in WORKFLOWS:
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.search(r"pip install (.+)", line)
            if not m:
                continue
            args = m.group(1).split()
            if args[:1] == ["-r"]:
                req = ROOT / args[1]
                assert req.is_file(), f"{path.name}: {args[1]} does not exist"
                for spec in req.read_text(encoding="utf-8").splitlines():
                    spec = spec.split("#")[0].strip()
                    if spec and "==" not in spec:
                        loose.append(f"{args[1]}: {spec}")
                continue
            for spec in args:
                if not spec.startswith("-") and "==" not in spec.strip('"'):
                    loose.append(f"{path.name}: {spec}")
    assert not loose, "packages without an exact version:\n  " + "\n  ".join(loose)


def test_sp_1_node_dependencies_install_from_the_lockfile():
    """A project's dependencies come from its lockfile (`npm ci`); a global
    tool is installed at an exact version."""
    loose = []
    for path in WORKFLOWS + COPYABLE:
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.search(r"npm install (.+)", line)
            if not m:
                continue
            args = m.group(1).split()
            pkgs = [a for a in args if not a.startswith("-")]
            if "-g" not in args or not pkgs or not all(
                    re.search(r".@\d+\.\d+\.\d+$", p) for p in pkgs):
                loose.append(f"{path.relative_to(ROOT)}: {line.strip()}")
    assert not loose, ("use npm ci for a project, or pin a global tool to an "
                       "exact version:\n  " + "\n  ".join(loose))
