# compass_pkg.policy_cmd - `compass policy lint` and `compass policy show`
"""The two policy verbs over the fixed check set (ADR-094).

9.0.0 removed `policy diff`, `policy update`, `policy migrate`, `preset init`
and `preset test`: one check set ships, so there is nothing to compare, move
between, migrate to or test a preset against. It also removed `--offline`
(nothing is fetched), and `policy lint --issue` and `--exhaustive` (an issue
has no config layer and the classifier went).

- `policy lint` lints `compass.yml` as a file of settings (`settings_lint`)
  for a project with a `compass.yml` Compass reads, the framework's own
  repository included. For any other project it runs the structural lint of
  the governance copy (`governance.legacy_structure`). 9.0.0 removed the drift
  report that compared a copy with the framework's, and the framework mode
  that linted the frozen views as well (ADR-098). `--file` lints one
  `compass.yml` as settings. `compass ci` calls the structural lint in
  `governance` directly.
- `policy show` prints the check set, its sha256, the sha256 of `compass.yml`
  and the tighten-only settings it applies. With `--issue` it adds the
  issue's `policy:` block and its waivers.

Both exit 0 when nothing is wrong, 1 when the lint finds an error, and 2 when
the command cannot run, because the release scripts, the `Makefile` and CI
run `lint`.
"""
# DEPENDENCY: standard library (json, os, re); compass_pkg.atomic_io, check_set, core,
# effective, governance, project_settings, settings_lint, terminal, tighten.
from __future__ import annotations

import json
import os
import re

from compass_pkg import check_set, effective, governance, project_settings
from compass_pkg import settings_lint, tighten
from compass_pkg.atomic_io import StrictYamlError, load_yaml_strict
from compass_pkg.core import (CompassError, find_governance, load_manifest,
                              resolve_issue_dir)
from compass_pkg.terminal import mark_handled, resolve_mode

#: The version of the JSON document `policy lint --json` prints.
JSON_SCHEMA_VERSION = 1


def _emit(args, document, lines):
    if resolve_mode(args) == "json":
        mark_handled()
        print(json.dumps(document, indent=2, default=str))
    else:
        print("\n".join(lines))


# --- the legacy lint, for a project with its own governance copy -----------------------

_LEGACY_FILE = re.compile(r"^(?:\[([^\]]+)\]|([\w.-]+\.yml):) ")


def _legacy_split(text):
    """`(file, message)` from a legacy error line that starts `[file]` or
    `file.yml:`, or `("", text)`."""
    found = _LEGACY_FILE.match(text)
    return ((found.group(1) or found.group(2)), text[found.end():]) if found else ("", text)


def _legacy_finding(code, level, path, message):
    return {"code": code, "level": level, "layer": "legacy", "path": path,
            "group": "legacy", "message": message, "detail": None}


def legacy_json(errors):
    """The `--json` document for a project with no `compass.yml`, from the
    structural lint's error lines. The keys are the 8.x ones, so a script that
    reads `result` and `counts` keeps working."""
    out = []
    for text in errors:
        path, message = _legacy_split(text)
        out.append(_legacy_finding("LEGACY-STRUCTURE", "error", path, message))
    out.sort(key=lambda f: (f["path"], f["code"], f["message"]))
    failed = any(f["level"] == "error" for f in out)
    return {
        "schema": JSON_SCHEMA_VERSION,
        "mode": "legacy",
        "result": "fail" if failed else "pass",
        "layers": [{"name": "legacy", "kind": "legacy"}],
        "stopped_after": "legacy" if errors else None,
        "counts": {"errors": sum(f["level"] == "error" for f in out),
                   "warnings": sum(f["level"] == "warning" for f in out)},
        "findings": out,
    }


def _legacy_report():
    errors, _ = governance.legacy_structure(find_governance())
    return legacy_json(errors)


# --- the settings lint -----------------------------------------------------------------

def _shown(path, root):
    """`path` as a person sees it: from the project root when it is inside,
    otherwise the file's own name. An absolute path is machine-specific, so
    it never reaches a finding."""
    absolute, base = os.path.abspath(path), os.path.abspath(root)
    inside = absolute.startswith(base + os.sep)
    return (os.path.relpath(absolute, base) if inside
            else os.path.basename(absolute)).replace(os.sep, "/")


def _read(path, root):
    """The parsed file at `path`. A file that is not there is an input that
    cannot be read (exit 2); a file that does not parse is one finding, on one
    line, that names the file from the project root."""
    if not os.path.isfile(path):
        raise CompassError(f"no such file: {_shown(path, root)}")
    try:
        return load_yaml_strict(path), []
    except (StrictYamlError, OSError) as exc:
        shown = _shown(path, root)
        message = " ".join(str(exc).replace(os.path.abspath(path), shown).split())
        return None, [settings_lint.Finding("L-SETTING-INVALID", "error", shown,
                                            f"cannot be read: {message}")]


def settings_findings(path, root=None):
    """Every finding of the settings lint for the `compass.yml` at `path`, over
    the check set. `root`, the project root, names the file in a finding."""
    doc, findings = _read(path, root or os.path.dirname(os.path.abspath(path)))
    if findings:
        return findings
    return settings_lint.lint(doc, check_set.resolved())


def _ok(findings):
    return not any(f.level == "error" for f in findings)


def _lint_json(findings):
    return {
        "schema": JSON_SCHEMA_VERSION,
        "mode": "settings",
        "result": "pass" if _ok(findings) else "fail",
        "layers": [{"name": "project", "kind": "project"}],
        "stopped_after": None,
        "counts": {"errors": sum(f.level == "error" for f in findings),
                   "warnings": sum(f.level == "warning" for f in findings)},
        "findings": [_finding_json(f) for f in findings],
    }


def _finding_json(f):
    """One finding of `--json`. An `L-SETTING-REMOVED` finding also names what
    replaces its key, or null when nothing does (ADR-098 decision 7)."""
    out = {"code": f.code, "level": f.level, "layer": "project", "path": f.path,
           "group": "settings", "message": f.message, "detail": None}
    if f.code == "L-SETTING-REMOVED":
        out["replacement"] = f.replacement
    return out


def _lint_text(findings):
    lines = ["compass policy lint: " + ("PASS" if _ok(findings) else "FAIL")]
    for f in findings:
        mark = f"{f.level} " if f.level != "error" else ""
        lines.append(f"  - {mark}{f.code} [project] {f.path}: {f.message}")
    return lines


def run_policy_lint(args):
    root = project_settings.find_project_root(os.getcwd())
    file = getattr(args, "file", None)
    if file:
        findings = settings_findings(file, root)
    elif project_settings.compass_yml_counts(root):
        findings = settings_findings(os.path.join(root, project_settings.COMPASS_YML), root)
    else:
        if resolve_mode(args) != "json":
            return governance.cmd_policy_lint(args)
        report = _legacy_report()
        _emit(args, report, [])
        return 0 if report["result"] == "pass" else 1
    _emit(args, _lint_json(findings), _lint_text(findings))
    return 0 if _ok(findings) else 1


# --- policy show -----------------------------------------------------------------------

def _issue_part(slug):
    task_dir = resolve_issue_dir(slug)
    manifest = load_manifest(task_dir)[0]
    waivers = [w for w in manifest.get("waivers") or [] if isinstance(w, dict)]
    return {"issue": slug, "generation": manifest.get("generation"),
            "policy": manifest.get("policy"),
            "waivers": [{k: w.get(k) for k in ("id", "check", "reason", "withdrawn_at")
                         if w.get(k) is not None} for w in waivers]}


def _show_text(document, notice):
    lines = [f"Policy: {document['check_set']} (sha256 {document['check_set_sha256']})"]
    settings = document["settings_sha256"]
    lines.append(f"Settings: compass.yml (sha256 {settings})" if settings
                 else "Settings: no compass.yml")
    tightened = document["tightened"]
    if tightened:
        lines.append("Tightened:")
        lines += [f"  {key}: {json.dumps(value)}" for key, value in tightened.items()]
    else:
        lines.append("Tightened: nothing")
    issue = document.get("issue")
    if issue:
        lines.append(f"Issue: {issue['issue']}"
                     + (f" (generation {issue['generation']})"
                        if issue.get("generation") is not None else ""))
        block = issue.get("policy")
        if isinstance(block, dict):
            lines.append(f"  policy: {block.get('check_set')} "
                         f"(sha256 {block.get('check_set_sha256')})")
            lines.append(f"  settings: {block.get('settings_sha256')}")
            lines.append(f"  tightened: {json.dumps(block.get('tightened') or {})}")
            lines.append(f"  resolved: {block.get('resolved')}")
        else:
            lines.append("  policy: none recorded (the issue was assessed before 9.0.0)")
        if issue["waivers"]:
            lines.append("  waivers:")
            lines += [f"    {w.get('id')}: {w.get('check')} - {w.get('reason')}"
                      + (" (withdrawn)" if w.get("withdrawn_at") else "")
                      for w in issue["waivers"]]
        else:
            lines.append("  waivers: none")
    if notice:
        lines.append(notice)
    return lines


def run_policy_effective(args):
    root = project_settings.find_project_root(os.getcwd())
    slug = getattr(args, "task", None)
    doc = effective.project_doc(root)
    effective.refuse_git_parent(doc)
    loaded = check_set.load()
    settings_path = os.path.join(root, project_settings.COMPASS_YML)
    document = {
        "check_set": check_set.ref(loaded),
        "check_set_sha256": check_set.sha256(),
        "settings_sha256": (effective.file_sha256(settings_path) if doc is not None
                            else None),
        "tightened": tighten.settings_of(doc),
    }
    if slug:
        document["issue"] = _issue_part(slug)
    notice = effective.GOVERNANCE_COPY_NOTICE if effective.has_governance_copy(root) else None
    _emit(args, document, _show_text(document, notice))
    return 0


ISSUE_HELP = ("issue slug: add that issue's policy: block and waivers. Without it no "
              "issue is read: there is no COMPASS_ISSUE or current-task fallback")


def register(pls):
    """Add `lint` and `show` to the `policy` parsers."""
    ple = pls.add_parser("show", help="show the check set, its digest and the "
                         "tighten-only settings applied")
    ple.add_argument("--issue", dest="task", metavar="SLUG", help=ISSUE_HELP)
    ple.set_defaults(func=run_policy_effective, output_kind="report")
    pll = pls.add_parser("lint", help="lint compass.yml as settings, or the governance "
                         "copy of a project without one")
    pll.add_argument("--file", metavar="PATH",
                     help="lint one compass.yml as settings over the check set")
    pll.set_defaults(func=run_policy_lint, output_kind="report")
