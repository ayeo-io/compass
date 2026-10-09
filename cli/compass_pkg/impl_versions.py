# compass_pkg.impl_versions - refuse a check built for another major, and move an issue on
"""What a generation records about versions, and what the CLI does when the
installed ones differ (ADR-038).

A generation's `versions.yml` records the version of each check
implementation the configuration uses, the resolver that built it and the
schema of its files. Compatibility within a major is shown on the fixture
corpus (`tests/test_impl_versions.py`) and nowhere else; across a major the
CLI refuses instead of running code the issue was not assessed against.

- `refusals` is what `compass check` asks. A different implementation major
  refuses that check only. A different resolver or schema major changes what
  every check means, so it refuses the run.
- `compass issue migrate --config` stores a new generation holding the same
  configuration, pinned to the installed versions, with every recorded check
  result invalidated. It is the second of the three ways a generation is
  committed, and `effective.migrate_generation` does it, because `effective`
  is the one module that reads and writes the store.
"""
# DEPENDENCY: standard library (os, dataclasses); compass_pkg.check_registry,
# core, effective.
from __future__ import annotations

import os
from dataclasses import dataclass, field

from compass_pkg import effective
from compass_pkg.check_registry import REGISTRY, installed_major
from compass_pkg.core import CompassError, resolve_issue_dir

COMMAND = "compass issue migrate --config"


@dataclass
class Refusals:
    """`run` is a message when the whole run is refused, else None. `checks`
    maps an implementation id to the message that refuses that check."""
    run: object = None
    checks: dict = field(default_factory=dict)


def _major(version):
    head = str(version).split(".")[0]
    return int(head) if head.isdigit() else None


def _fix(slug):
    return (f"Run `{COMMAND} --issue {slug}` to store a new generation pinned to the "
            f"installed versions; it invalidates the results recorded under the old "
            f"ones, so each check runs again.")


def refusals(task_dir, manifest):
    """The refusals for an issue's run. An issue with no stored generation has
    recorded nothing to differ from, so it gets none."""
    held, recorded = effective.stored_versions(task_dir, manifest)
    if not held:
        return Refusals()
    slug = os.path.basename(os.path.normpath(os.fspath(task_dir)))
    for what, installed in effective.installed_pins().items():
        was = recorded.get(what)
        if was is not None and _major(was) != _major(installed):
            return Refusals(run=(
                f"nothing was run: generation {held} of {slug} was built by {what} "
                f"{was} and this CLI has {what} {installed}, a different major, "
                f"which can change what every check means. {_fix(slug)}"))
    found = {}
    for impl, was in sorted((recorded.get("implementations") or {}).items()):
        now = installed_major(impl)
        if now is not None and _major(was) != now:
            found[impl] = (
                f"refused: {impl} {was} is recorded, {REGISTRY[impl].version} is "
                f"installed, a different major, so it did not run. {_fix(slug)}")
    return Refusals(checks=found)


def cmd_issue_migrate_config(args):
    committed, notes = effective.migrate_generation(resolve_issue_dir(args.task))
    print("\n".join([f"  {committed.message}"] + [f"  {note}" for note in notes]))
    return 0


def cmd_issue_migrate(args):
    """`compass issue migrate`: the work root, or with `--config` one issue's
    pinned generation. The two take different arguments, so a mix is refused."""
    if getattr(args, "config", False):
        stray = [flag for flag, given in (
            ("work root", getattr(args, "root", None)),
            ("--apply", getattr(args, "apply", False)),
            ("--i-have-a-copy", getattr(args, "i_have_a_copy", False))) if given]
        if stray:
            raise CompassError(
                "--config pins one issue's configuration and takes no "
                + ", no ".join(stray) + "; run `compass issue migrate` for the work root.")
        return cmd_issue_migrate_config(args)
    if getattr(args, "task", None):
        raise CompassError(
            "--issue is for --config; `compass issue migrate` without it "
            "examines the work root, which holds every issue.")
    from compass_pkg.migrate import cmd_migrate
    return cmd_migrate(args)


def register(issue_subparsers, issue_arg):
    """Add `compass issue migrate` to the `issue` verb."""
    parser = issue_subparsers.add_parser(
        "migrate",
        help="migrate a 1.x issue tree to schema 2.0 (dry run unless --apply); "
             "with --config, pin one issue's configuration to the installed versions")
    parser.add_argument("root", nargs="?",
                        help="the work root to examine (default: .compass/work)")
    parser.add_argument("--apply", action="store_true",
                        help="execute the changes the dry run reports")
    parser.add_argument("--i-have-a-copy", action="store_true",
                        help="proceed where git cannot restore the work root, because you "
                             "have taken a copy")
    parser.add_argument("--config", action="store_true",
                        help="pin --issue's configuration to the installed versions and "
                             "invalidate every check result recorded under older ones")
    issue_arg(parser)
    parser.set_defaults(func=cmd_issue_migrate, output_kind="report")
