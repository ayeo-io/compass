# compass_pkg.policy_cmd - `compass policy lint`, `effective`, `diff`, `migrate` and `update`
"""The five verbs over `policy_lint`, `replay`, `policy_migrate` and `policy_update`.

`policy lint` runs the legacy lint, unchanged, for a project with no
`compass.yml` that Compass reads and for the framework's own repository, and
the layered lint for any other project. `compass ci` calls the legacy
function in `governance` directly, so its behaviour does not move.
"""
# DEPENDENCY: standard library (os, sys); compass_pkg.core, governance, layers,
# parents, policy_lint, policy_migrate, policy_update, project_settings, replay,
# terminal.
from __future__ import annotations

import os
import sys

from compass_pkg import governance, layers, parents, policy_lint, policy_migrate
from compass_pkg import project_settings, replay
from compass_pkg import policy_update
from compass_pkg.core import (FRAMEWORK_ROOT, CompassError, find_governance, load_manifest,
                              resolve_issue_dir)
from compass_pkg.terminal import mark_handled, resolve_mode


def _is_layered(root):
    """Layered when the project holds a `compass.yml` Compass reads. The
    settings reader's own predicate decides, so the two cannot disagree.
    The framework's repository keeps the legacy lint until its own governance
    files are generated views of the preset (ADR-042)."""
    if os.path.realpath(root) == os.path.realpath(FRAMEWORK_ROOT):
        return False
    return project_settings.compass_yml_counts(root)


def _emit(args, document, lines):
    if resolve_mode(args) == "json":
        mark_handled()
        print(policy_lint.dumps(document))
    else:
        print("\n".join(lines))


def _may_fetch(args):
    """Whether this run may fetch an uncached git parent: not with `--offline`
    or `COMPASS_OFFLINE`."""
    return not (getattr(args, "offline", False) or parents.offline())


def run_policy_lint(args):
    root = layers.find_project_root(os.getcwd())
    file = getattr(args, "file", None)
    slug = getattr(args, "task", None)
    layered = _is_layered(root)
    # An issue's config is linted over the shipped default even where the
    # project has no compass.yml, as `effective` resolves it.
    if not file and not slug and not layered:
        if resolve_mode(args) != "json":
            return governance.cmd_policy_lint(args)
        gov = find_governance()
        errors, _ = governance.legacy_structure(gov)
        report = policy_lint.legacy_report(errors, governance.governance_drift(gov),
                                           governance._drift_is_strict())
        _emit(args, policy_lint.lint_json(report), [])
        return 0 if report.ok else 1
    manifest = load_manifest(resolve_issue_dir(slug))[0] if slug else None
    loaded = policy_lint.load_layers(root, file=file, manifest=manifest, cwd=os.getcwd(),
                                     read_project=layered, fetch=_may_fetch(args))
    report = policy_lint.lint_loaded(loaded, exhaustive=bool(getattr(args, "exhaustive", False)))
    _emit(args, policy_lint.lint_json(report), policy_lint.lint_text(report))
    return 0 if report.ok else 1


def run_policy_effective(args):
    root = layers.find_project_root(os.getcwd())
    slug = getattr(args, "task", None)
    manifest = load_manifest(resolve_issue_dir(slug))[0] if slug else None
    loaded = policy_lint.load_layers(root, manifest=manifest, read_project=_is_layered(root),
                                     fetch=_may_fetch(args))
    if loaded.findings:
        first = loaded.findings[0]
        raise CompassError(f"nothing can be resolved: {first.code} {first.path}: "
                           f"{first.message}")
    effective = policy_lint.resolve_effective(
        loaded.parent, loaded.project, loaded.issue, meta=loaded.meta, slug=slug,
        git_parents=loaded.git_parents)
    _emit(args, policy_lint.effective_json(effective), policy_lint.effective_text(effective))
    return 0


def run_policy_migrate(args):
    root = layers.find_project_root(os.getcwd())
    made = policy_migrate.plan(root)
    mode = "apply" if getattr(args, "apply", False) else "dry-run"
    if mode == "apply" and made.result == "ready":
        policy_migrate.apply(root, made)
        made.result = "applied"
    _emit(args, policy_migrate.report_json(made, mode), policy_migrate.report_text(made, mode))
    return 1 if made.result == "blocked" else 0


def run_policy_diff(args):
    root = layers.find_project_root(os.getcwd())
    first, second = replay.default_refs(getattr(args, "refs", None) or [])
    a = replay.resolve_ref(first, root, cwd=os.getcwd())
    b = replay.resolve_ref(second, root, cwd=os.getcwd())
    document = replay.diff(a, b, replay.read_archive(root), open=bool(args.open))
    _emit(args, document, replay.diff_text(document))
    return 1 if args.exit_code and document["differs"] else 0


def _terminal_attached():
    """True when a person can answer: input and output are both a terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def _major(value):
    if value is None:
        return None
    if not value.isdecimal():
        raise CompassError(f"--to takes a major number such as 7, not '{value}'")
    return int(value)


def run_policy_update(args):
    root = layers.find_project_root(os.getcwd())
    to = _major(getattr(args, "to", None))
    as_json = resolve_mode(args) == "json"
    # A script reading JSON is not at a keyboard, so it is never asked.
    asking = _terminal_attached() and not as_json
    out = policy_update.run(root, to, yes=bool(args.yes), interactive=asking, ask=input,
                            say=print)
    if as_json:
        _emit(args, policy_update.document(out), [])
    elif asking:
        print("\n".join(policy_update.result_lines(out)))
    else:
        print("\n".join(policy_update.text(out)))
    return out.exit_code


ISSUE_HELP = ("issue slug: read that issue's `config:` from its manifest. Without it "
              "no issue is read: there is no COMPASS_ISSUE or current-task fallback")


OFFLINE_HELP = ("read git parents from the cache only and fetch nothing; also set by "
                "COMPASS_OFFLINE=1")


def _issue_option(parser):
    parser.add_argument("--issue", dest="task", metavar="SLUG", help=ISSUE_HELP)
    parser.add_argument("--offline", action="store_true", help=OFFLINE_HELP)


def register(pls):
    """Add `lint`, `effective`, `diff`, `migrate` and `update` to the `policy` parsers."""
    ple = pls.add_parser("effective", help="show every resolved configuration field "
                         "with its source layer")
    _issue_option(ple)
    ple.set_defaults(func=run_policy_effective, output_kind="report")
    plm = pls.add_parser("migrate", help="turn copied governance and the old settings file "
                         "into a compass.yml overlay over the shipped default")
    plm.add_argument("--apply", action="store_true",
                     help="write the files; without it nothing is written")
    plm.set_defaults(func=run_policy_migrate, output_kind="report")
    pll = pls.add_parser("lint", help="structurally validate the governance YAML")
    _issue_option(pll)
    pll.add_argument("--file", metavar="PATH",
                     help="lint one compass.yml as a project layer over the shipped default")
    pll.add_argument("--exhaustive", action="store_true",
                     help="run the full grid, not the grouped one (layered projects)")
    pll.set_defaults(func=run_policy_lint, output_kind="report")
    pld = pls.add_parser("diff", help="compare two configurations by classification "
                         "and by replaying assessments under both")
    pld.add_argument("refs", nargs="*", metavar="REF",
                     help="default@6, project, legacy, git:<revision> or a path to a "
                     "compass.yml. Two compare A with B, one compares the project with "
                     "it, none compares the project file at git HEAD with the working file")
    pld.add_argument("--open", action="store_true",
                     help="also run each open issue (active, queued or parked) over both, "
                     "and list the issue waivers that would need re-approval")
    pld.add_argument("--exit-code", dest="exit_code", action="store_true",
                     help="exit 1 when anything differs, as git diff --exit-code does")
    pld.set_defaults(func=run_policy_diff, output_kind="report")
    plu = pls.add_parser("update", help="move the project to another shipped default major, "
                         "re-approving the waivers the move affects")
    plu.add_argument("--to", metavar="MAJOR",
                     help="the major to move to, such as 7 (default: the newest major this "
                     "CLI keeps). A move goes forward only")
    plu.add_argument("--yes", action="store_true",
                     help="confirm a move that affects no waiver. It never re-approves a "
                     "waiver: with one affected it refuses")
    plu.set_defaults(func=run_policy_update, output_kind="report")
