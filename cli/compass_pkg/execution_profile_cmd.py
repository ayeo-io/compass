# compass_pkg.execution_profile_cmd - `compass profile lint|add|show`
"""The three verbs of `compass profile`.

All three run the same check pipeline (`execution_profile.check_file`), so `add`
and `show` accept nothing that `lint` refuses. A refusal prints one line for each
reason, `<code>: <what is wrong>`, on standard output with no header, and exits 2.
`lint` exits 2 on a fault: `policy lint` exits 1, and this verb follows the spec of
the profile. A success prints through `Report`, with `--json` data.

The verb functions are named `cmd_profile_*`; keep them out of
`record_triggers.RENDER_TRIGGERS`, which keys on a function name.
`docs/execution-profiles.md` owns this behaviour.
"""
# DEPENDENCY: standard library (json, os); compass_pkg.core, compass_pkg.execution_profile,
# compass_pkg.execution_profile_store and compass_pkg.terminal.
from __future__ import annotations

import json
import os

from compass_pkg import execution_profile as ep
from compass_pkg import execution_profile_store as store
from compass_pkg.core import find_compass_dir
from compass_pkg.terminal import Report, mark_handled, resolve_mode

REFUSED = 2


def refuse(args, faults):
    """Print the reasons, one line each (a list in `--json`), and return the exit code."""
    mark_handled()
    # A YAML error spans lines; a reason is one line.
    faults = [(code, " ".join(message.split())) for code, message in faults]
    if resolve_mode(args) == "json":
        print(json.dumps([{"code": code, "message": message} for code, message in faults],
                         indent=2))
    else:
        for code, message in faults:
            print(f"{code}: {message}")
    return REFUSED


def project_root():
    return os.path.dirname(find_compass_dir())


def _value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return "null" if value is None else str(value)


def counts(data):
    """The number of references of each kind, for the line that shows them."""
    comps = data["components"]
    return {name: len(comps[name]) for name, _ in ep.COMPONENT_KINDS}


def cmd_profile_lint(args):
    try:
        root = project_root()
    except Exception:  # noqa: BLE001 - outside a project, lint reads the shipped policy
        root = None
    data, faults = ep.check_file(args.file, root)
    if faults:
        return refuse(args, faults)
    shown = counts(data)
    reference = (f"{shown['skills']} skills, {shown['prompt_fragments']} prompt fragments, "
                 f"{shown['tool_guidance']} tool guidance")
    lines = [f"  {name}: {_value(data[name])}" for name in ep.REQUIRED_FIELDS]
    lines.append(f"  references: {reference}")
    report = Report(args, title="compass profile lint")
    report.summary(f"{args.file} is a valid profile file: {data['id']} version {data['version']}")
    report.body("\n".join(lines))
    report.data(valid=True, fields={name: data[name] for name in ep.REQUIRED_FIELDS},
                references=shown, computed_digest=ep.content_digest(data))
    return report.emit()


def cmd_profile_add(args):
    outcome, dest, faults = store.add(project_root(), args.file)
    if faults:
        return refuse(args, faults)
    data, _ = ep.read_text_file(dest)
    relative = os.path.relpath(dest, project_root())
    if outcome == store.ALREADY_STORED:
        line = (f"{data['id']} version {data['version']} is already stored in {relative}; "
                "nothing changed")
    else:
        line = f"Stored {data['id']} version {data['version']} in {relative}"
    report = Report(args, title="compass profile add")
    report.summary(line)
    report.data(outcome=outcome, id=data["id"], version=data["version"], path=relative,
                digest=data["digest"])
    return report.emit()


def _show_lines(result):
    model, settings = result["model"], result["runner_settings"]
    lines = [f"  profile: {result['id']} version {result['version']}",
             f"  digest: {result['digest']}", f"  owner: {result['owner']}",
             f"  approval: {_value(result['approval'])}",
             f"  tier: {model['tier']}", f"  effort: {model['effort']}",
             f"  model: {model['mapped_model']}",
             f"  provider_revision: {_value(model['provider_revision'])}",
             f"  runner_versions: {', '.join(result['runner_versions'])}",
             *(f"  {name}: {settings[name]}" for name in ep.SETTING_CEILING)]
    lines += [f"  component {c['kind']} {c['id']} {c['revision']}"
              for c in result["components"]]
    lines += [f"  {item['code']}: {item['message']}"
              for item in result["reproducibility_limits"]]
    return lines


def cmd_profile_show(args):
    result, faults = store.resolve(project_root(), args.id, args.version)
    if faults:
        return refuse(args, faults)
    report = Report(args, title="compass profile show")
    report.summary(f"{result['id']} version {result['version']} resolves to "
                   f"{len(result['components'])} components")
    report.body("\n".join(_show_lines(result)))
    report.data(**result)
    return report.emit()


def register(sub):
    """Add `compass profile lint|add|show` to the top-level parser."""
    profile = sub.add_parser(
        "profile", help="check, store and resolve execution profiles (fixed ways of working)")
    verbs = profile.add_subparsers(dest="profile_verb", required=True)

    lint = verbs.add_parser("lint", help="check one profile file against every rule")
    lint.add_argument("file", help="the profile file to check")
    lint.set_defaults(func=cmd_profile_lint, output_kind="report")

    add = verbs.add_parser("add", help="store a checked profile file as a new version")
    add.add_argument("file", help="the profile file to store")
    add.set_defaults(func=cmd_profile_add, output_kind="report")

    show = verbs.add_parser("show", help="resolve one stored version to exact revisions")
    show.add_argument("id", help="the profile id")
    show.add_argument("--version", help="the version to show; no version is chosen for you")
    show.set_defaults(func=cmd_profile_show, output_kind="report")
