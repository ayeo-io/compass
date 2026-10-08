# compass_pkg.policy_update - `compass policy update` for the shipped default
"""Move a project from one shipped default major to another (ADR-039).

`plan` reads the project's `compass.yml` and the two defaults the framework
keeps, resolves the project's layer over each, classifies the difference, and
re-checks every project waiver field by field (`waivers.recheck_move`). It
reads only: no file is written, and nothing is asked.

The framework ships one default in the folder `default` under its presets
folder. A major it no longer ships under that name stays beside it as
`default@<n>`, so a project still on it can be compared with the new one.
`policy_lint.load_parent` reads each folder; this module only lists them.
"""
# DEPENDENCY: standard library (copy, dataclasses, datetime, json, os, re, tempfile,
# textwrap); compass_pkg.atomic_io, catalogue_check, core, layers, merge,
# policy_lint, replay, waivers.
from __future__ import annotations

import copy
import dataclasses
import datetime
import json
import os
import re
import tempfile
import textwrap
from dataclasses import dataclass, field

from compass_pkg import catalogue_check, layers, merge, policy_lint, replay, waivers
from compass_pkg.atomic_io import StrictYamlError, atomic_write_text, load_yaml_strict
from compass_pkg.core import FRAMEWORK_ROOT, CompassError

PRESETS = os.path.join("governance", "presets")
_KEPT = re.compile(r"^default@(\d+)$")


def _major_of(version):
    return int(str(version).split(".", 1)[0])


def available_defaults(framework_root=None):
    """`{major: preset folder}` for the shipped default and every major the
    framework keeps beside it. A kept folder whose `preset.yml` names another
    major is a fault in the framework, so it raises."""
    base = os.path.join(os.fspath(framework_root or FRAMEWORK_ROOT), PRESETS)
    found = {}
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else ():
        kept = _KEPT.match(name)
        if name != "default" and not kept:
            continue
        directory = os.path.join(base, name)
        try:
            meta = load_yaml_strict(os.path.join(directory, "preset.yml"))
        except StrictYamlError as exc:
            raise CompassError(str(exc)) from None
        major = _major_of(meta.get("version", ""))
        if kept and major != int(kept.group(1)):
            raise CompassError(f"{name}/preset.yml is version {meta.get('version')}, not "
                               f"major {kept.group(1)}")
        if major in found:
            raise CompassError(f"the framework holds default@{major} twice")
        found[major] = directory
    return found


@dataclass
class WaiverView:
    """One project waiver in a move. `status` is `kept` (no waived field's
    parent value changed) or `invalidated`; a re-approval later sets
    `reapproved`. `allowed` is who may approve it; `fault` says why nobody
    can."""
    id: str
    catalogue: str
    entry_id: str
    body: dict
    status: str = "kept"
    invalidations: list = field(default_factory=list)
    allowed: list = field(default_factory=list)
    fault: object = None
    approved_by: object = None
    approved_on: object = None

    @property
    def entry(self):
        return f"{self.catalogue}.{self.entry_id}"


@dataclass
class Plan:
    """What a move would do. `waivers` lists every project waiver. A plan
    with `merge_errors` is a move that leaves the project's file broken:
    nothing past the waivers is computed for it."""
    path: str = ""
    text: str = ""
    doc: dict = field(default_factory=dict)
    current: int = 0
    target: int = 0
    versions: dict = field(default_factory=dict)
    waivers: list = field(default_factory=list)
    merge_errors: list = field(default_factory=list)
    classification: object = None
    replay: object = None

    @property
    def nothing_to_do(self):
        return self.current == self.target

    @property
    def invalidated(self):
        return [w for w in self.waivers if w.status == "invalidated"]


def _extends(doc, path):
    """The major named by the `extends:` of a project file (a string, or a map
    with `from`)."""
    value = doc.get("extends") if isinstance(doc, dict) else None
    if value is None:
        raise CompassError(f"{path} has no extends: line, so there is no major to move; "
                           f"add extends: {layers.default_extends(6)} first")
    name, major = layers.parse_extends(value.get("from") if isinstance(value, dict) else value)
    if name != "default":
        raise CompassError(f"{path}: extends names compass:{name}, and only the shipped "
                           f"default can be moved by this command")
    return major


def _target(to, current, defaults):
    """The major to move to. The request must name a major the framework
    keeps, and moves go forward only."""
    kept = ", ".join(f"default@{n}" for n in sorted(defaults))
    target = max(defaults) if to is None else to
    if target not in defaults:
        raise CompassError(f"default@{target} is not available: this CLI keeps {kept}")
    if target < current and to is None:
        raise CompassError(f"the project extends default@{current}, which is newer than any "
                           f"major this CLI keeps (the newest is default@{target}); install a "
                           f"newer Compass")
    if target < current:
        raise CompassError(f"default@{target} is older than the project's default@{current}; "
                           f"a move goes forward only")
    return target


def _resolved(directory):
    """`(parent layer, version, resolved config, provenance)` of one default."""
    parent, meta = policy_lint.load_parent(directory=directory)
    try:
        config, prov = merge.apply({}, parent.doc, "parent", "default", {})
    except merge.MergeError as exc:
        raise CompassError(f"{os.path.basename(directory)} does not resolve: "
                           f"{exc.errors[0][2]}") from None
    return parent, meta["version"], config, prov


def _capabilities(*docs):
    state = {}
    for doc in docs:
        state.update(doc.get("capabilities") or {})
    return tuple(sorted(k for k, v in state.items() if v is True))


def _over(label, parent, version, config, prov, layer):
    """The `replay.Config` of `layer` over a default, or the merge errors."""
    merged, merged_prov = merge.apply(config, layer, "project", "project", prov)
    return merged, replay.Config(label, "project", merged,
                                 _capabilities(parent.doc, layer), merged_prov, version)


def _views(found, invalidations, doc, new_parent):
    by_id = {}
    for change in invalidations:
        by_id.setdefault(change.waiver_id, []).append(change)
    out = []
    for waiver in found:
        allowed, fault = waivers.allowed_approvers(waiver, doc, new_parent.doc)
        moved = by_id.get(waiver.id, [])
        out.append(WaiverView(waiver.id, waiver.catalogue, waiver.entry, waiver.body,
                              "invalidated" if moved else "kept", moved, allowed,
                              fault.message if fault else None))
    return out


def plan(root, to=None, *, framework_root=None):
    """The `Plan` for moving the project at `root` to default@`to` (the newest
    kept major when `to` is None). Raises `CompassError` when the request or
    the file cannot be used."""
    path = os.path.join(os.fspath(root), layers.PROJECT_FILE)
    if not os.path.isfile(path):
        raise CompassError(f"no compass.yml in {os.fspath(root)}: a project without one runs "
                           f"the shipped default, so there is nothing to move")
    # newline="" keeps a CRLF file's line endings, so the rewrite changes no
    # other byte.
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    try:
        doc = load_yaml_strict(path)
    except StrictYamlError as exc:
        raise CompassError(str(exc)) from None
    current = _extends(doc, "compass.yml")
    defaults = available_defaults(framework_root)
    target = _target(to, current, defaults)
    made = Plan(path, text, doc, current, target)
    if current == target:
        return made
    if current not in defaults:
        raise CompassError(f"default@{current} is not kept by this CLI, so the move to "
                           f"default@{target} cannot be checked against it")
    old, new = _resolved(defaults[current]), _resolved(defaults[target])
    made.versions = {"from": str(old[1]), "to": str(new[1])}
    layer, _ = layers.split_project_file(doc)
    problems = catalogue_check.check_layer(layer, "project")
    if problems:
        raise CompassError(f"compass.yml fails its own check: {problems[0]} "
                           f"(run compass policy lint)")
    try:
        old_merged, side_a = _over(f"default@{current} + project", old[0], old[1], old[2],
                                   old[3], layer)
    except merge.MergeError as exc:
        raise CompassError(f"compass.yml does not resolve over default@{current}: "
                           f"{exc.errors[0][2]} (run compass policy lint)") from None
    found, faults = waivers.find(layer, "project")
    if faults:
        raise CompassError(f"a waiver in compass.yml is malformed: {faults[0].message} "
                           f"(run compass policy lint)")
    moved = waivers.recheck_move(found, old[2], old_merged, new[2])
    made.waivers = _views(found, moved, doc, new[0])
    try:
        _, side_b = _over(f"default@{target} + project", new[0], new[1], new[2], new[3], layer)
    except merge.MergeError as exc:
        made.merge_errors = list(exc.errors)
        return made
    shown = replay.diff(side_a, side_b, replay.read_archive(root))
    made.classification = shown["classification"]
    made.replay = {"sets": shown["replay"]["sets"],
                   "changed": len(shown["replay"]["changes"])}
    return made


# --- the text edit --------------------------------------------------------------------

# The file is edited as lines so that comments and order survive. Only block
# style is reached: a waiver written as a flow mapping is an error that names
# it, because an edit inside braces cannot be made line by line.

_MAJOR = re.compile(r"(compass:[a-z][a-z0-9-]*@)\d+")
_PLAIN = re.compile(r"^[A-Za-z][A-Za-z0-9_.@-]*$")
_RESERVED = {"yes", "no", "true", "false", "on", "off", "null", "y", "n"}


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _blank(line):
    stripped = line.strip()
    return not stripped or stripped.startswith("#")


def _value(line):
    """The text after the first colon of a `key: value` line, without a
    trailing comment (a `#` after a space) and without surrounding spaces."""
    rest = line.split(":", 1)[1].rstrip("\r\n")
    return re.sub(r"\s+#.*$", "", rest).strip()


def _block(lines, at):
    """The `(first, end)` line range of the lines nested under line `at`."""
    base, end = _indent(lines[at]), at + 1
    for n in range(at + 1, len(lines)):
        if _blank(lines[n]):
            continue
        if _indent(lines[n]) <= base:
            break
        end = n + 1
    return at + 1, end


def _find(lines, span, key):
    """The index of `key:` among the outermost keys of the line range
    `span`, or None."""
    first, end = span
    body = [n for n in range(first, end) if not _blank(lines[n])]
    if not body:
        return None
    outer = _indent(lines[body[0]])
    pattern = re.compile(rf"^{' ' * outer}(['\"]?){re.escape(key)}\1\s*:")
    return next((n for n in body if pattern.match(lines[n])), None)


def _newline(line):
    return "\r\n" if line.endswith("\r\n") else "\n"


def _scalar(name):
    if _PLAIN.match(name) and name.lower() not in _RESERVED:
        return name
    return json.dumps(name)


def _not_in_place(entry):
    return CompassError(
        f"the waiver on {entry} cannot be edited in place: it is not a block mapping under "
        f"that entry (a flow mapping, or no waiver block). Write it in block style, with "
        f"approved_by and approved_on on lines of their own, and run the command again")


def _set_line(lines, at, key, text):
    """Put `key: text` on line `at`, keeping its indent and line ending."""
    lines[at] = f"{' ' * _indent(lines[at])}{key}: {text}{_newline(lines[at])}"


def _set_approval(lines, catalogue, entry_id, approver, day):
    """Write `approved_by` and `approved_on` into the waiver of one entry."""
    entry = f"{catalogue}.{entry_id}"
    top = next((n for n, line in enumerate(lines)
                if re.match(rf"^{re.escape(catalogue)}\s*:", line)), None)
    at = None if top is None or _value(lines[top]) else _find(lines, _block(lines, top),
                                                              entry_id)
    if at is None or _value(lines[at]):
        raise _not_in_place(entry)
    held = _find(lines, _block(lines, at), "waiver")
    if held is None or _value(lines[held]):
        raise _not_in_place(entry)
    span = _block(lines, held)
    by, on = _find(lines, span, "approved_by"), _find(lines, span, "approved_on")
    if by is None or not _value(lines[by]):
        raise _not_in_place(entry)
    _set_line(lines, by, "approved_by", _scalar(approver))
    if on is None:
        lines.insert(by + 1, "")
        on = by + 1
        lines[on] = lines[by]
    _set_line(lines, on, "approved_on", day.isoformat())


def _set_major(lines, target):
    """Rewrite the integer after `@` in `extends:` (or in its `from:`)."""
    at = next((n for n, line in enumerate(lines) if re.match(r"^extends\s*:", line)), None)
    if at is not None and not _value(lines[at]):
        first, end = _block(lines, at)
        at = next((n for n in range(first, end) if re.match(r"^\s+from\s*:", lines[n])), None)
    if at is None:
        raise CompassError("compass.yml: the extends line was not found as text")
    head, _, rest = lines[at].partition(":")
    value = _value(lines[at])
    if len(_MAJOR.findall(value)) != 1:
        raise CompassError("compass.yml: the extends value is not one compass:<name>@<major>")
    lines[at] = head + ":" + rest.replace(value, _MAJOR.sub(rf"\g<1>{target}", value), 1)


def _parse(text):
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, layers.PROJECT_FILE)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        return load_yaml_strict(path)


def _expected(doc, target, approvals):
    """`doc` with the move and the approvals applied as data: the only
    document the edited text may parse to."""
    out = copy.deepcopy(doc)
    held = out["extends"]
    box = held if isinstance(held, dict) else out
    key = "from" if isinstance(held, dict) else "extends"
    box[key] = layers.default_extends(target)
    for catalogue, entry_id, approver, day in approvals:
        body = out[catalogue][entry_id]["waiver"]
        body["approved_by"], body["approved_on"] = approver, day
    return out


def rewrite_text(text, target, approvals):
    """`compass.yml` as text with the major set to `target` and, for each
    `(catalogue, entry, approver, day)` of `approvals`, that waiver's
    `approved_by` and `approved_on`. Nothing else is touched. The result is
    parsed and compared with the old document changed as data, so an edit
    that reaches anything more raises `CompassError` instead of returning."""
    old = _parse(text)
    lines = text.splitlines(keepends=True)
    _set_major(lines, target)
    for approval in approvals:
        _set_approval(lines, *approval)
    new = "".join(lines)
    if _parse(new) != _expected(old, target, approvals):
        raise CompassError("the edit would change more than the major in extends and the "
                           "approvals; nothing was written")
    return new


# --- the decision ---------------------------------------------------------------------

APPROVER_TRIES = 3
YES_WORDS = ("y", "yes")


@dataclass
class Outcome:
    """What a run did. `status` is `applied`, `nothing-to-do` or `refused`;
    a refusal is `(code, message)`. `waivers` are the plan's views with a
    re-approved waiver marked `reapproved`: the plan itself is not changed."""
    plan: Plan
    status: str
    written: bool = False
    refusal: object = None
    waivers: list = field(default_factory=list)

    @property
    def exit_code(self):
        return 1 if self.status == "refused" else 0


def _refused(made, code, message, views=None):
    return Outcome(made, "refused", False, (code, message),
                   views if views is not None else list(made.waivers))


def _describe(view):
    given = view.body.get("approved_by")
    since = view.body.get("approved_on")
    lines = [f"the waiver on {view.entry} (approved by {given}"
             + (f" on {since}" if since else "") + ") needs re-approval:"]
    for change in view.invalidations:
        lines.append(f"  {change.reason}" if change.field is None else
                     f"  {change.field}: the parent value changed from {change.old!r} to "
                     f"{change.new!r}; the project sets {change.project!r}")
    return lines


def _approver(view, ask):
    """The name the owner gives, or None after `APPROVER_TRIES` names outside
    the allowed list. One allowed name is taken on an empty answer."""
    only = view.allowed[0] if len(view.allowed) == 1 else None
    prompt = f"Approver ({', '.join(view.allowed)}): "
    for _ in range(APPROVER_TRIES):
        name = ask(prompt).strip() or only
        if name in view.allowed:
            return name
    return None


def _asked(ask, prompt):
    try:
        return ask(prompt).strip().lower() in YES_WORDS
    except EOFError:
        return False


def _reapprove(made, ask, say, today):
    """`(views, approvals, refusal)`: ask the owner about each affected
    waiver in the order they sit in the file. The first no ends it."""
    views, approvals = [], []
    for view in made.waivers:
        if view.status != "invalidated":
            views.append(view)
            continue
        if view.fault:
            return None, None, ("nobody-may-approve", f"{view.entry}: {view.fault}")
        for line in _describe(view):
            say(line)
        refusal = ("declined", f"the waiver on {view.entry} was not approved")
        try:
            if not _asked(ask, f"Approve this waiver against "
                               f"{layers.default_extends(made.target)}? [y/N] "):
                return None, None, refusal
            name = _approver(view, ask)
        except EOFError:
            name = None
        if name is None:
            return None, None, refusal
        views.append(dataclasses.replace(view, status="reapproved", approved_by=name,
                                         approved_on=today))
        approvals.append((view.catalogue, view.entry_id, name, today))
    return views, approvals, None


def _unchanged_since_plan(made):
    """Refuse to write over an edit made while the questions waited: the
    plan's text must still be the file's text."""
    try:
        with open(made.path, encoding="utf-8", newline="") as fh:
            now = fh.read()
    except OSError as exc:
        raise CompassError(f"compass.yml cannot be read before the write: {exc}") from None
    if now == made.text:
        return
    old, new = made.text.splitlines(), now.splitlines()
    at = next((n for n in range(min(len(old), len(new))) if old[n] != new[n]),
              min(len(old), len(new)))
    raise CompassError(f"compass.yml has changed since the plan was made (first difference "
                       f"at line {at + 1}), so nothing was written. Run the command again")


def _write(path, text, write):
    try:
        write(path, text)
    except OSError as exc:
        raise CompassError(f"compass.yml was not changed: {exc}") from None


def execute(made, *, yes=False, interactive=False, ask=input, say=print, today=None,
            write=atomic_write_text):
    """Decide the move of `made`, ask on the terminal when it is affected, and
    write once. `--yes` (yes) confirms a move that affects no waiver and
    never re-approves one: a script is not the owner. Without a terminal
    nothing is asked. The move and every approval go out in one atomic write
    of `compass.yml`, or nothing does."""
    today = today or datetime.date.today()
    if made.nothing_to_do:
        return Outcome(made, "nothing-to-do", waivers=list(made.waivers))
    target = layers.default_extends(made.target)
    if made.merge_errors:
        code, where, message = made.merge_errors[0]
        more = len(made.merge_errors) - 1
        return _refused(made, "does-not-resolve",
                        f"compass.yml does not resolve over {target}: {code} {where}: "
                        f"{message}" + (f" (and {more} more)" if more else "")
                        + ". Fix the file, then run the command again")
    affected = made.invalidated
    names = ", ".join(w.entry for w in affected)
    views, approvals = list(made.waivers), []
    if affected and yes:
        return _refused(made, "yes-cannot-reapprove",
                        f"--yes never re-approves a waiver, and these need an allowed "
                        f"approver: {names}. Run the command without --yes on a terminal")
    if affected and not interactive:
        return _refused(made, "no-terminal",
                        f"there is no terminal to ask on, and these waivers need re-approval "
                        f"by an allowed approver: {names}. Run the command on a terminal, "
                        f"or remove the waiver from compass.yml")
    if affected:
        views, approvals, refusal = _reapprove(made, ask, say, today)
        if refusal:
            return _refused(made, *refusal)
    if not yes:
        if not interactive:
            return _refused(made, "needs-confirmation",
                            "the move needs a confirmation: run the command on a terminal, "
                            "or pass --yes (no waiver is affected)")
        if not _asked(ask, f"Move this project to {target}"
                           + (f" and write {len(approvals)} approval(s)" if approvals else "")
                           + "? [y/N] "):
            return _refused(made, "declined", "the move was not confirmed")
    new = rewrite_text(made.text, made.target, approvals)
    _unchanged_since_plan(made)
    _write(made.path, new, write)
    return Outcome(made, "applied", True, None, views)


# --- what a person and a script read ---------------------------------------------------

JSON_SCHEMA_VERSION = 1
TEXT_WIDTH = 100


def _day(value):
    return None if value is None else str(value)


def _field_json(change):
    return {"field": change.field, "old": change.old, "new": change.new,
            "project": change.project, "message": change.reason}


def _waiver_json(view):
    return {"id": view.id, "entry": view.entry, "status": view.status,
            "reason": view.body.get("reason"),
            "approved_by": view.approved_by or view.body.get("approved_by"),
            "approved_on": _day(view.approved_on or view.body.get("approved_on")),
            "fields": [_field_json(c) for c in view.invalidations]}


def document(out):
    """The JSON document of a run: a public shape from 6.0.0, pinned by
    `tests/fixtures/policy-update-json-example.json` and described in
    `docs/policy-update.md`. A refusal is `{code, message}`; the
    classification is the classifier's own JSON, and `replay` counts what a
    replay of the assessments finds under the two defaults."""
    made = out.plan
    versions = made.versions or {}
    return {
        "schema": JSON_SCHEMA_VERSION,
        "status": out.status,
        "written": out.written,
        "from": {"ref": layers.default_extends(made.current), "major": made.current,
                 "version": versions.get("from")},
        "to": {"ref": layers.default_extends(made.target), "major": made.target,
               "version": versions.get("to")},
        "refusal": None if out.refusal is None else
        {"code": out.refusal[0], "message": out.refusal[1]},
        "classification": made.classification,
        "replay": made.replay,
        "waivers": [_waiver_json(v) for v in out.waivers],
    }


def _wrap(first, text, rest="  "):
    return textwrap.wrap(text, TEXT_WIDTH, initial_indent=first, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False)


def _replay_line(sets):
    parts = []
    for one in sets:
        if one["skipped"]:
            parts.append(f"{one['name']} skipped ({one['skipped']})")
        else:
            parts.append(f"{one['name']} {one['replayed']:,} replayed, "
                         f"{one['changed']:,} changed")
    return "replay: " + "; ".join(parts)


def plan_lines(made):
    """The plan as lines for a person: the two defaults, what the move
    changes and each waiver."""
    old, new = layers.default_extends(made.current), layers.default_extends(made.target)
    versions = made.versions
    shown = f" ({versions['from']} -> {versions['to']})" if versions else ""
    lines = [f"compass policy update: {old} -> {new}{shown}"]
    if made.classification:
        lines += _wrap("classification: ", f"{made.classification['result']} - "
                       f"{made.classification['reason']}")
        lines.append(_replay_line(made.replay["sets"]))
    for code, where, message in made.merge_errors[:3]:
        lines += _wrap("does not resolve: ", f"{code} {where}: {message}")
    if not made.waivers:
        return lines + ["waivers: none"]
    lines.append("waivers:")
    for view in made.waivers:
        if view.status != "invalidated":
            lines.append(f"  {view.entry}: stays valid (no waived field's parent value "
                         f"changed)")
            continue
        lines.append(f"  {view.entry}: needs re-approval")
        for change in view.invalidations:
            lines += _wrap("    ", change.reason if change.field is None else
                           f"{change.field}: the parent value changed from {change.old!r} "
                           f"to {change.new!r}; the project sets {change.project!r}", "      ")
    return lines


def result_lines(out):
    """The last lines: what the run did."""
    target = layers.default_extends(out.plan.target)
    if out.status == "nothing-to-do":
        return [f"nothing to do: the project already extends {target}"]
    if out.status == "applied":
        done = [v for v in out.waivers if v.status == "reapproved"]
        return [f"applied: compass.yml now extends {target}"
                + (f", with {len(done)} waiver(s) re-approved by "
                   f"{', '.join(sorted({v.approved_by for v in done}))} on "
                   f"{done[0].approved_on}" if done else "")]
    code, message = out.refusal
    return _wrap(f"not applied ({code}): ", message)


def text(out):
    """The whole report for a run that did not ask anything."""
    if out.status == "nothing-to-do":
        return result_lines(out)
    return plan_lines(out.plan) + result_lines(out)


def run(root, to=None, *, yes=False, interactive=False, ask=input, say=print, today=None,
        framework_root=None, write=atomic_write_text):
    """Plan and carry out a move in one call. The plan is shown through `say`
    before anything is asked; the caller prints `result_lines` afterwards."""
    made = plan(root, to, framework_root=framework_root)
    if interactive and not made.nothing_to_do:
        for line in plan_lines(made):
            say(line)
    return execute(made, yes=yes, interactive=interactive, ask=ask, say=say, today=today,
                   write=write)
