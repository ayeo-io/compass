# compass_pkg.policy_cmd - `compass policy lint` and `compass policy effective`
"""The two verbs over `policy_lint`.

`policy lint` runs the legacy lint, unchanged, for a project with no
`compass.yml` that Compass reads and for the framework's own repository, and
the layered lint for any other project. `compass ci` calls the legacy
function in `governance` directly, so its behaviour does not move.
"""
# DEPENDENCY: standard library (os); compass_pkg.core, governance, layers,
# policy_lint, project_settings, terminal.
from __future__ import annotations

import os

from compass_pkg import governance, layers, policy_lint, project_settings
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
                                     read_project=layered)
    report = policy_lint.lint_loaded(loaded, exhaustive=bool(getattr(args, "exhaustive", False)))
    _emit(args, policy_lint.lint_json(report), policy_lint.lint_text(report))
    return 0 if report.ok else 1


def run_policy_effective(args):
    root = layers.find_project_root(os.getcwd())
    slug = getattr(args, "task", None)
    manifest = load_manifest(resolve_issue_dir(slug))[0] if slug else None
    loaded = policy_lint.load_layers(root, manifest=manifest, read_project=_is_layered(root))
    if loaded.findings:
        first = loaded.findings[0]
        raise CompassError(f"nothing can be resolved: {first.code} {first.path}: "
                           f"{first.message}")
    effective = policy_lint.resolve_effective(
        loaded.parent, loaded.project, loaded.issue, meta=loaded.meta, slug=slug)
    _emit(args, policy_lint.effective_json(effective), policy_lint.effective_text(effective))
    return 0


ISSUE_HELP = ("issue slug: read that issue's `config:` from its manifest. Without it "
              "no issue is read: there is no COMPASS_ISSUE or current-task fallback")


def _issue_option(parser):
    parser.add_argument("--issue", dest="task", metavar="SLUG", help=ISSUE_HELP)


def register(pls):
    """Add `lint` and `effective` to the `policy` parsers."""
    ple = pls.add_parser("effective", help="show every resolved configuration field "
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
