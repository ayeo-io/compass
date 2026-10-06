#!/usr/bin/env python3
"""Prove each shipped check's register tests can fail, by breaking the check.

`tests/mutation_proofs.yml` names, for every check under `checks:` in
`governance/guardrails.yml`, a test that feeds the check a broken input
(`fails`) and a test that asserts it passes once the input is right
(`restores`). That proves the tests exist, not that they would notice a
broken check: a test can match a message a passing check also prints, or
pass because another check failed in the same fixture.

This runner breaks the check itself, in a copy of the checkout:

- always pass: the `fails` test must go red;
- always fail: the `restores` test must go red.

It changes no file in the checkout, and exits non-zero naming every entry
whose test stayed green, failed before any mutation, or names a check with
no function. A test marked to skip, or one pytest does not collect, cannot
fail, so it is reported too.

It lives under `.github/`, which the release leaves out: it is for this
repository's CI and maintainers, never for adopters.
"""
from __future__ import annotations

import argparse
import inspect
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[2]

# Each override replaces the check's function at the end of the module that
# defines it. A module that imports the function by name (`check_cmd` does)
# binds it only after the defining module has run to its end, so the
# override is the one every caller gets.
_OVERRIDE = '''

def {name}(*args, **kwargs):  # mutated by check-mutation-runner
    return {result}
'''
_PASS = '(True, "mutated to always pass")'
_FAIL = '(False, "mutated to always fail")'


def _copy_checkout(root: Path, dest: Path) -> None:
    """The tracked files and any untracked, not-ignored ones, as on disk."""
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root, capture_output=True, check=True).stdout
    for raw in out.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        src = root / rel
        if not src.is_file() or src.is_symlink():
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)


def _entries(copy: Path) -> list[dict]:
    sys.path.insert(0, str(copy / "cli"))
    from compass_pkg import core  # the bundled YAML, as evals/compare.py reads it
    return core.yaml.safe_load(
        (copy / "tests" / "mutation_proofs.yml").read_text(encoding="utf-8")) or []


def _targets(copy: Path) -> dict[str, tuple[Path, str]]:
    """Each check id's defining file and function name, from the registry in
    `check_cmd`, never a list kept by hand."""
    sys.path.insert(0, str(copy / "cli"))
    from compass_pkg.check_cmd import CHECK_FNS
    return {check: (Path(inspect.getsourcefile(fn)), fn.__name__)
            for check, fn in CHECK_FNS.items()}


def _passes(copy: Path, node: str) -> tuple[bool, str]:
    """Whether `node` passes in the copy. Bytecode is off: an edit of the
    same size as the original within one second would otherwise reuse the
    unmutated bytecode, and the mutation would never run."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", node],
        cwd=copy, env=env, capture_output=True, text=True)
    return proc.returncode == 0, (proc.stdout + proc.stderr)[-400:]


def _goes_red(copy: Path, file: Path, name: str, result: str, node: str) -> tuple[bool, str]:
    original = file.read_text(encoding="utf-8")
    try:
        file.write_text(original + _OVERRIDE.format(name=name, result=result),
                        encoding="utf-8")
        passed, tail = _passes(copy, node)
        return not passed, tail
    finally:
        file.write_text(original, encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="append",
                        help="only this check id (repeatable)")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT,
                        help="the checkout to copy (default: this repository)")
    args = parser.parse_args(argv)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="check-mutation-") as tmp:
        copy = Path(tmp)
        _copy_checkout(args.root.resolve(), copy)
        targets = _targets(copy)
        stayed_green = []
        for entry in _entries(copy):
            check = entry.get("check")
            if args.check and check not in args.check:
                continue
            if check not in targets:
                stayed_green.append(f"{check}: no function in check_cmd.CHECK_FNS")
                continue
            file, name = targets[check]
            # A test that already fails proves nothing by failing again:
            # each must pass on the unmutated copy first.
            baseline = [field for field in ("fails", "restores")
                        if not _passes(copy, entry[field])[0]]
            if baseline:
                stayed_green.extend(f"{check}: `{f}` ({entry[f]}) fails before "
                                    f"any mutation" for f in baseline)
                print(f"{check}: fails before any mutation: {', '.join(baseline)}")
                continue
            for result, field in ((_PASS, "fails"), (_FAIL, "restores")):
                red, tail = _goes_red(copy, file, name, result, entry[field])
                state = "red" if red else "STAYED GREEN"
                print(f"{check}: {field} with the check "
                      f"{'always passing' if result is _PASS else 'always failing'}: {state}")
                if not red:
                    stayed_green.append(f"{check}: `{field}` ({entry[field]}) stayed green")
    print(f"\n{time.monotonic() - started:.0f}s")
    if stayed_green:
        print("These register tests cannot show that their check works:")
        for line in stayed_green:
            print(f"  {line}")
        return 1
    print("Every register test went red when its check was broken.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
