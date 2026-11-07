# compass_pkg.policy_cmd - `compass policy lint` and `compass policy show`
"""The two policy verbs over `policy_lint` and `policy_effective`.

9.0.0 removed `policy diff`, `policy update`, `policy migrate`, `preset init`
and `preset test` (ADR-094): one check set ships, so there is nothing to
compare, move between, migrate to or test a preset against.

`policy lint` runs the legacy lint, unchanged, for a project with no
`compass.yml` that Compass reads, and the layered lint for any other project.
`--issue`, `--file` and `policy show` read the chain the write-time lint reads
everywhere, the framework's own repository included. There, `policy lint` with
no arguments runs the legacy lint and then the layered lint, and fails if
either fails. `compass ci` calls the legacy function in `governance`
directly, so its behaviour does not move.
"""
# DEPENDENCY: standard library (os); compass_pkg.core, effective, governance, layers, parents,
# policy_effective, policy_lint, project_settings, terminal.
from __future__ import annotations

import os

from compass_pkg import governance, layers, parents, policy_lint
from compass_pkg import policy_effective, project_settings
from compass_pkg.effective import GOVERNANCE_COPY_NOTICE, has_governance_copy
from compass_pkg.core import (FRAMEWORK_ROOT, CompassError, find_governance, load_manifest,
                              resolve_issue_dir)
from compass_pkg.terminal import mark_handled, resolve_mode


def _is_layered(root):
    """Layered when the project holds a `compass.yml` Compass reads. The
    settings reader's own predicate decides, so the two cannot disagree, and
    `--issue`, `--file` and `policy show` read the chain the write-time lint
    (`effective.resolve_live`) reads. The framework's repository is no
    exception: its governance files are generated views of the preset."""
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


def _is_framework_root(root):
    """True in the framework's own repository, whose governance/ files are
    the shipped set and whose compass.yml is a project layer over them."""
    return os.path.realpath(root) == os.path.realpath(FRAMEWORK_ROOT)


def _legacy_report():
    gov = find_governance()
    errors, _ = governance.legacy_structure(gov)
    return policy_lint.legacy_report(errors, governance.governance_drift(gov),
                                     governance._drift_is_strict())


def _layered_report(args, root, file=None, manifest=None, read_project=True, task_dir=None):
    loaded = policy_lint.load_layers(root, file=file, manifest=manifest, cwd=os.getcwd(),
                                     read_project=read_project, fetch=_may_fetch(args),
                                     task_dir=task_dir)
    return policy_lint.lint_loaded(loaded, exhaustive=bool(getattr(args, "exhaustive", False)))


def _lint_framework(args, root):
    """The no-argument lint in the framework's repository: the legacy lint of
    governance/, then the layered lint of compass.yml over the shipped default,
    which is the chain a write reads. It fails when either fails, so CI
    (`scripts/validate.sh`) reports a chain a write would refuse."""
    # The legacy check runs first. A policy that is not valid YAML raises
    # CompassError there; it is a structure error of the lint, not a crash,
    # and the layered lint is skipped. Other structure errors still let the
    # layered lint run, so both reports print.
    try:
        governance.legacy_structure(find_governance())
    except CompassError as exc:
        errors = [str(exc)]
        if resolve_mode(args) == "json":
            _emit(args, policy_lint.lint_json(policy_lint.legacy_report(errors)), [])
        else:
            print("compass policy lint: FAIL")
            for error in errors:
                print(f"  - {error}")
        return 1
    layered = _layered_report(args, root)
    if resolve_mode(args) == "json":
        legacy = _legacy_report()
        both = policy_lint.Report(
            mode="framework", layers=legacy.layers + layered.layers,
            findings=legacy.findings + layered.findings,
            stopped_after=legacy.stopped_after or layered.stopped_after)
        _emit(args, policy_lint.lint_json(both), [])
        legacy_ok = legacy.ok
    else:
        legacy_ok = governance.cmd_policy_lint(args) == 0
        print("\n".join(policy_lint.lint_text(layered)))
    policy_lint.print_advisories(layered)
    return 0 if legacy_ok and layered.ok else 1


def run_policy_lint(args):
    root = layers.find_project_root(os.getcwd())
    file = getattr(args, "file", None)
    slug = getattr(args, "task", None)
    layered = _is_layered(root)
    if not file and not slug and _is_framework_root(root):
        return _lint_framework(args, root)
    # An issue's config is linted over the shipped default even where the
    # project has no compass.yml, as `effective` resolves it.
    if not file and not slug and not layered:
        if resolve_mode(args) != "json":
            return governance.cmd_policy_lint(args)
        report = _legacy_report()
        _emit(args, policy_lint.lint_json(report), [])
        return 0 if report.ok else 1
    task_dir = resolve_issue_dir(slug) if slug else None
    manifest = load_manifest(task_dir)[0] if slug else None
    report = _layered_report(args, root, file=file, manifest=manifest, read_project=layered,
                             task_dir=task_dir)
    _emit(args, policy_lint.lint_json(report), policy_lint.lint_text(report))
    policy_lint.print_advisories(report)
    return 0 if report.ok else 1


def run_policy_effective(args):
    root = layers.find_project_root(os.getcwd())
    slug = getattr(args, "task", None)
    task_dir = resolve_issue_dir(slug) if slug else None
    manifest = load_manifest(task_dir)[0] if slug else None
    loaded = policy_lint.load_layers(root, manifest=manifest, read_project=_is_layered(root),
                                     fetch=_may_fetch(args), task_dir=task_dir)
    if loaded.findings:
        first = loaded.findings[0]
        raise CompassError(f"nothing can be resolved: {first.code} [{first.layer}] "
                           f"{first.path}: {first.message}")
    effective = policy_effective.resolve_effective(
        loaded.parent, loaded.project, loaded.issue, meta=loaded.meta, slug=slug,
        git_parents=loaded.git_parents)
    notice = GOVERNANCE_COPY_NOTICE if has_governance_copy(root) else None
    _emit(args, policy_effective.effective_json(effective),
          policy_effective.effective_text(effective, notice=notice))
    return 0


ISSUE_HELP = ("issue slug: read that issue's `config:` from its manifest. Without it "
              "no issue is read: there is no COMPASS_ISSUE or current-task fallback")


OFFLINE_HELP = ("read git parents from the cache only and fetch nothing; also set by "
                "COMPASS_OFFLINE=1")


def _issue_option(parser):
    parser.add_argument("--issue", dest="task", metavar="SLUG", help=ISSUE_HELP)
    parser.add_argument("--offline", action="store_true", help=OFFLINE_HELP)


def register(pls):
    """Add `lint` and `show` to the `policy` parsers."""
    ple = pls.add_parser("show", help="show every resolved configuration field "
                         "with its source layer")
    _issue_option(ple)
    ple.set_defaults(func=run_policy_effective, output_kind="report")
    pll = pls.add_parser("lint", help="structurally validate the governance YAML")
    _issue_option(pll)
    pll.add_argument("--file", metavar="PATH",
                     help="lint one compass.yml as a project layer over the shipped default")
    pll.add_argument("--exhaustive", action="store_true",
                     help="run the full grid, not the grouped one (layered projects)")
    pll.set_defaults(func=run_policy_lint, output_kind="report")
