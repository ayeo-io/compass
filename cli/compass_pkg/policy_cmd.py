# compass_pkg.policy_cmd - `compass policy lint`, `show`, `diff`, `migrate` and `update`
"""The five verbs over `policy_lint`, `replay`, `policy_migrate` and `policy_update`.

`policy lint` runs the legacy lint, unchanged, for a project with no
`compass.yml` that Compass reads, and the layered lint for any other project.
`--issue`, `--file` and `policy show` read the chain the write-time lint reads
everywhere, the framework's own repository included. There, `policy lint` with
no arguments runs the legacy lint and then the layered lint, and fails if
either fails. `compass ci` calls the legacy function in `governance`
directly, so its behaviour does not move.
"""
# DEPENDENCY: standard library (os, sys); compass_pkg.classify, config_words, core, governance,
# layers, parents, policy_lint, policy_migrate, policy_update, project_settings,
# replay, terminal.
from __future__ import annotations

import os
import sys

from compass_pkg import classify, config_words, governance, layers, parents, policy_lint, policy_migrate
from compass_pkg import policy_update, preset_init, preset_test, project_settings, replay
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
    effective = policy_lint.resolve_effective(
        loaded.parent, loaded.project, loaded.issue, meta=loaded.meta, slug=slug,
        git_parents=loaded.git_parents)
    _emit(args, policy_lint.effective_json(effective), policy_lint.effective_text(effective))
    return 0


def run_policy_migrate(args):
    root = layers.find_project_root(os.getcwd())
    if getattr(args, "words", False):
        return _run_words(args, root)
    if getattr(args, "dir", None) is not None or getattr(args, "have_copy", False):
        raise CompassError("policy migrate: DIR and --i-have-a-copy belong to --words, "
                           "which rewrites the project's configuration in the 6.0.0 words")
    made = policy_migrate.plan(root)
    mode = "apply" if getattr(args, "apply", False) else "dry-run"
    if mode == "apply" and made.result == "ready":
        policy_migrate.apply(root, made)
        made.result = "applied"
    _emit(args, policy_migrate.report_json(made, mode), policy_migrate.report_text(made, mode))
    return 1 if made.result == "blocked" else 0


def _run_words(args, root):
    """`policy migrate --words`: rewrite compass.yml and the fixtures in DIR."""
    folder = os.path.join(os.getcwd(), args.dir) if args.dir else root
    made = config_words.plan(root, folder)
    mode = "apply" if getattr(args, "apply", False) else "dry-run"
    if mode == "apply":
        config_words.apply(made, getattr(args, "have_copy", False))
    _emit(args, config_words.report_json(made, mode), config_words.report_text(made, mode))
    return config_words.exit_code(made)


def run_policy_diff(args):
    root = layers.find_project_root(os.getcwd())
    first, second = replay.default_refs(getattr(args, "refs", None) or [])
    fetch = _may_fetch(args)
    a = replay.resolve_ref(first, root, cwd=os.getcwd(), fetch=fetch)
    b = replay.resolve_ref(second, root, cwd=os.getcwd(), fetch=fetch)
    document = replay.diff(a, b, replay.read_archive(root), open=bool(args.open))
    # A kind the second side adds is named on a line of its own. It is not part
    # of the classification: a kind nothing owes changes no obligation.
    added = sorted(set(b.config.get("artifacts") or {}) - set(a.config.get("artifacts") or {}))
    lines = replay.diff_text(document)
    # A swap between two declared choices of a readiness parameter is
    # equivalent, so the classification does not show it. It is named on a
    # line of its own, so it stays visible without a waiver.
    swaps = [f"changes readiness {signal} {param}: {p} -> {c}"
             for signal, param, p, c in classify.declared_choice_swaps(a.config, b.config)]
    lines[1:1] = [f"adds artifact kind {kind}" for kind in added] + swaps
    _emit(args, document, lines)
    return 1 if args.exit_code and document["differs"] else 0


def run_preset_test(args):
    result = preset_test.run(args.preset_dir, replay.evaluate, fetch=_may_fetch(args))
    _emit(args, preset_test.report_json(result), preset_test.text(result))
    policy_lint.print_advisories(result.lint)
    return 0 if preset_test.passed(result) else 1


def run_preset_init(args):
    result, files = preset_init.scaffold(args.dir, args.owner, replay.evaluate)
    _emit(args, preset_init.report_json(args.dir, result, files),
          preset_init.text(args.dir, result, files))
    return 0 if result == "written" else 1


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
    """Add `lint`, `show`, `diff`, `migrate` and `update` to the `policy` parsers."""
    ple = pls.add_parser("show", help="show every resolved configuration field "
                         "with its source layer")
    _issue_option(ple)
    ple.set_defaults(func=run_policy_effective, output_kind="report")
    plm = pls.add_parser("migrate", help="turn copied governance and the old settings file "
                         "into a compass.yml overlay over the shipped default")
    plm.add_argument("--apply", action="store_true",
                     help="write the files; without it nothing is written")
    plm.add_argument("--words", action="store_true",
                     help="instead, rewrite the project's compass.yml and its "
                     "compass-fixtures/ in the 6.0.0 words, keeping comments and layout")
    plm.add_argument("dir", nargs="?", metavar="DIR",
                     help="with --words: the folder that holds compass.yml and "
                     "compass-fixtures/ (default: the project root); it must be inside "
                     "the project")
    plm.add_argument("--i-have-a-copy", dest="have_copy", action="store_true",
                     help="with --words --apply: write files git cannot restore, because "
                     "you have a copy")
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
                     help="default@7, project, legacy, git:<revision>, a git parent written "
                     "as in extends: (github:<owner>/<repo>@<ref>#<sha>) or a path to a "
                     "compass.yml. Two compare A with B, one compares the project with "
                     "it, none compares the project file at git HEAD with the working file")
    pld.add_argument("--offline", action="store_true", help=OFFLINE_HELP)
    pld.add_argument("--open", action="store_true",
                     help="also run each issue in flight or in the backlog over both, "
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


def register_preset(sub):
    """Add the `compass preset` group, with `init` and `test`."""
    group = sub.add_parser("preset", help="team preset repositories")
    verbs = group.add_subparsers(dest="preset_cmd", required=True)
    pst = verbs.add_parser("test", help="run a preset's fixtures and check its locks")
    pst.add_argument("preset_dir", nargs="?", default=".", metavar="PRESET_DIR",
                     help="the folder that holds the preset's compass.yml (default: the "
                     "working folder)")
    pst.add_argument("--offline", action="store_true", help=OFFLINE_HELP)
    pst.set_defaults(func=run_preset_test, output_kind="report")
    psi = verbs.add_parser("init", help="scaffold a team preset repository")
    psi.add_argument("dir", metavar="DIR", help="the folder to write the preset into; it is "
                     "created when it is missing")
    psi.add_argument("--owner", required=True, metavar="NAME",
                     help="the team that owns the preset, written to its compass.yml")
    psi.set_defaults(func=run_preset_init, output_kind="report")
