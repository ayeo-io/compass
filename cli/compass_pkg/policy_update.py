# compass_pkg.policy_update - `compass policy update` for the shipped default and git parents
"""Move a project from one shipped default major to another, or from one commit of
its git parent to another (ADR-039).

`plan` reads the project's `compass.yml` and the two defaults the framework
keeps, resolves the project's layer over each, classifies the difference, and
re-checks every project waiver field by field (`waivers.recheck_move`). It
reads only: no file is written, and nothing is asked.

The framework ships one default in the folder `default` under its presets
folder. A major it no longer ships under that name stays beside it as
`default@<n>`, so a project still on it can be compared with the new one.
`policy_lint.load_parent` reads each folder; this module only lists them.

A project whose `extends:` names a git parent (`github:<owner>/<repo>@<ref>#<sha>`)
moves the pin instead. The remote's `<ref>` is resolved to a commit (`git ls-remote`),
the commit is fetched, and the two pins play the part of the two defaults: the same
waiver re-check, the same terminal re-approval and the same single write, with `#<sha>`
rewritten in place of the major. A host that cannot be reached is `offline`, which is
not a refusal: nothing was decided.
"""
# DEPENDENCY: standard library (copy, dataclasses, datetime, json, os, re, tempfile,
# textwrap); compass_pkg.atomic_io, catalogue_check, core, layers, merge,
# parent_states, parents, policy_lint, replay, waivers.
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
from compass_pkg import parent_states, parents
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
class GitMove:
    """The two pins of a git parent. `label` is `github:<owner>/<repo>@<ref>`.
    `new_sha` is None when the ref could not be resolved (offline)."""
    label: str
    old_sha: str
    new_sha: object = None
    old_version: object = None
    new_version: object = None

    @staticmethod
    def _shown(label, sha):
        return f"{label}#{sha[:7]}" if sha else label

    @property
    def old_ref(self):
        return self._shown(self.label, self.old_sha)

    @property
    def new_ref(self):
        return self._shown(self.label, self.new_sha)


@dataclass
class Plan:
    """What a move would do. `waivers` lists every project waiver. A plan
    with `merge_errors` is a move that leaves the project's file broken:
    nothing past the waivers is computed for it. `git` is set for a git
    parent, whose move is `current` and `target` as shipped majors otherwise.
    `offline` says why a git move could not be planned, and `invalid` lists
    the faults of a new parent commit."""
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
    git: object = None
    offline: str = ""
    invalid: list = field(default_factory=list)

    @property
    def old_ref(self):
        return self.git.old_ref if self.git else layers.default_extends(self.current)

    @property
    def new_ref(self):
        return self.git.new_ref if self.git else layers.default_extends(self.target)

    @property
    def move_to(self):
        """What `rewrite_text` writes: a major, or the new full sha."""
        return self.git.new_sha if self.git else self.target

    @property
    def nothing_to_do(self):
        if self.git:
            return self.git.new_sha is not None and self.git.new_sha == self.git.old_sha
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
    """`(layer documents, version, resolved config, provenance)` of one default.
    The documents are those the project's layer sits over, nearest last."""
    parent, meta = policy_lint.load_parent(directory=directory)
    try:
        config, prov = merge.apply({}, parent.doc, "parent", "default", {})
    except merge.MergeError as exc:
        raise CompassError(f"{os.path.basename(directory)} does not resolve: "
                           f"{exc.errors[0][2]}") from None
    return (parent.doc,), meta["version"], config, prov


def _resolved_git(directory, chain, check=False):
    """`_resolved` for a chain of git parents (furthest first) over the default
    in `directory`: the default's version stands for the whole, and the
    parents' own faults are returned as text, not raised, so the move is
    refused with the cause."""
    default = _resolved(directory)
    if check:
        # Every lint group, as `compass policy lint` runs them, so a pin is
        # never written that the lint then refuses.
        base, _ = policy_lint.load_parent(directory=directory)
        report = policy_lint.lint_chain(base, None, extra_parents=[f.layer for f in chain])
        problems = [f"{f.code} [{f.layer}] {f.path}: {f.message}" for f in report.errors]
        if problems:
            return None, problems
    docs, config, prov = list(default[0]), default[2], default[3]
    for found in chain:
        try:
            config, prov = merge.apply(config, found.layer.doc, "parent", found.layer.name,
                                       prov)
        except merge.MergeError as exc:
            return None, [f"{code} [{found.layer.name}] {where}: {message}"
                          for code, where, message in exc.errors]
        docs.append(found.layer.doc)
    return (tuple(docs), default[1], config, prov), []


def _capabilities(*docs):
    state = {}
    for doc in docs:
        state.update(doc.get("capabilities") or {})
    return tuple(sorted(k for k, v in state.items() if v is True))


def _over(label, docs, version, config, prov, layer):
    """The `replay.Config` of `layer` over a default, or the merge errors."""
    merged, merged_prov = merge.apply(config, layer, "project", "project", prov)
    return merged, replay.Config(label, "project", merged,
                                 _capabilities(*docs, layer), merged_prov, version)


def _views(found, invalidations, doc, above):
    """The views of the project's waivers. `above` is the document of the layer
    just above the project, which names who may approve (ADR-039)."""
    by_id = {}
    for change in invalidations:
        by_id.setdefault(change.waiver_id, []).append(change)
    out = []
    for waiver in found:
        allowed, fault = waivers.allowed_approvers(waiver, doc, above)
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
    try:
        spec = parents.spec_of(doc.get("extends") if isinstance(doc, dict) else None)
    except parents.ParentError as exc:
        raise CompassError(f"compass.yml: {exc}") from None
    defaults = available_defaults(framework_root)
    if spec:
        return _plan_git(Plan(path, text, doc), root, spec, to, defaults)
    current = _extends(doc, "compass.yml")
    target = _target(to, current, defaults)
    made = Plan(path, text, doc, current, target)
    if current == target:
        return made
    if current not in defaults:
        raise CompassError(f"default@{current} is not kept by this CLI, so the move to "
                           f"default@{target} cannot be checked against it")
    old, new = _resolved(defaults[current]), _resolved(defaults[target])
    made.versions = {"from": str(old[1]), "to": str(new[1])}
    return _compare(made, root, old, new, f"default@{current}", f"default@{target}")


def _compare(made, root, old, new, old_label, new_label):
    """Fill `made` from the project's layer over each side: the waiver
    re-check across the two parents, the classification and the replay. A side
    is `(layer documents, version, resolved config, provenance)`. The
    waivers are approved by the layer just above the project in the new side."""
    doc = made.doc
    layer, _ = layers.split_project_file(doc)
    problems = catalogue_check.check_layer(layer, "project")
    if problems:
        raise CompassError(f"compass.yml fails its own check: {problems[0]} "
                           f"(run compass policy lint)")
    try:
        old_merged, side_a = _over(f"{old_label} + project", old[0], old[1], old[2],
                                   old[3], layer)
    except merge.MergeError as exc:
        raise CompassError(f"compass.yml does not resolve over {old_label}: "
                           f"{exc.errors[0][2]} (run compass policy lint)") from None
    found, faults = waivers.find(layer, "project")
    if faults:
        raise CompassError(f"a waiver in compass.yml is malformed: {faults[0].message} "
                           f"(run compass policy lint)")
    moved = waivers.recheck_move(found, old[2], old_merged, new[2])
    made.waivers = _views(found, moved, doc, new[0][-1])
    try:
        _, side_b = _over(f"{new_label} + project", new[0], new[1], new[2], new[3], layer)
    except merge.MergeError as exc:
        made.merge_errors = list(exc.errors)
        return made
    shown = replay.diff(side_a, side_b, replay.read_archive(root))
    made.classification = shown["classification"]
    made.replay = {"sets": shown["replay"]["sets"],
                   "changed": len(shown["replay"]["changes"])}
    return made


# --- a git parent -----------------------------------------------------------------------

def _chain_parents(root, extends, *, fetch):
    """The git parents a project's `extends:` resolves to, furthest ancestor
    first. This is the only place a parent is looked up. The parent that a
    move re-pins is the last one, and the ancestors behind it are the ones
    its own `extends:` names."""
    return parents.resolve_chain(root, extends, fetch=fetch)

# Faults of the environment, not of the commit: a new commit that causes one of
# these cannot be judged, so the error is raised, not turned into a refusal.
_ENVIRONMENT = ("L-PARENT-FETCH", "L-PARENT-CACHE", "L-PARENT-NOT-CACHED",
                "L-PARENT-SHA-MISMATCH")


def _trust_cache(root, chain, where):
    """Stop the move when a cached copy in `chain` is not the file that was
    fetched, or cannot be shown to be. The cache is ignored by git, so an edit
    to it is not visible in review, and it would decide the waiver re-check and
    the approvers."""
    for held in chain:
        state = parent_states.read(root, held)
        if not state.why:
            continue
        # Only a digest that no longer matches means an edit; a missing record
        # means nothing says what was fetched.
        edited = "no longer matches" in state.why
        said = (f"was edited ({state.why})" if edited else
                f"cannot be checked ({state.why}); nothing records what was fetched")
        raise CompassError(f"the cached copy of {held.sha[:7]} of {held.ref}, in {where}, "
                           f"{said}. Delete it under .compass/cache/parents/ and run the "
                           f"command again to fetch it afresh")


def _offline_plan(made, spec, why):
    made.git = GitMove(parents.ref_label(spec), spec.sha)
    made.offline = why
    return made


def _plan_git(made, root, spec, to, defaults):
    """The `Plan` for moving a git parent's pin to the commit its ref names
    now. Needs the network for the ref and for any commit not yet cached; a
    host that cannot be reached gives an `offline` plan, and any other git
    fault is raised."""
    if to is not None:
        raise CompassError("--to names a shipped default major, and this project extends a "
                           "git parent: the pin moves to the commit its @<ref> names now. "
                           "Change the ref in compass.yml to follow another one")
    label = parents.ref_label(spec)
    if parents.offline():
        return _offline_plan(made, spec, "COMPASS_OFFLINE is set, so the ref was not looked "
                                         "up and nothing was changed")
    extends = made.doc.get("extends")
    try:
        new_sha = parents.resolve_ref(spec)
        if new_sha is None:
            raise CompassError(f"{label}: the remote has no such ref ({spec.ref}); check the "
                               f"spelling in compass.yml")
        if len(spec.sha) == 40 and spec.sha == new_sha:
            made.git = GitMove(label, new_sha, new_sha)
            return made
        old_chain = _chain_parents(root, extends, fetch=True)
        old = old_chain[-1]
        _trust_cache(root, old_chain, "the chain of the current pin")
        made.git = GitMove(label, old.sha, new_sha, old.version or None)
        if old.sha == new_sha:
            return made
        try:
            new_chain = _chain_parents(root, f"{label}#{new_sha}", fetch=True)
        except parents.ParentError as exc:
            if parents.unreachable(exc.detail):
                raise
            # A fault in the new commit's own ancestors was caused by the parent's
            # owners, so it is a refusal; a fault fetching the commit itself is not.
            ours = exc.layer == "project"
            if exc.code in _ENVIRONMENT and (ours or exc.code != "L-PARENT-FETCH"):
                raise
            made.invalid = [f"{exc.code} [{exc.layer}] {exc.path}: {exc.detail}"]
            return made
        # The new chain was fetched before any write, so a copy in the cache can
        # have been edited since. It is checked before anything is read from it.
        _trust_cache(root, new_chain, "the chain of the new commit")
    except parents.ParentError as exc:
        if parents.unreachable(exc.detail):
            return _offline_plan(made, spec, f"{label} could not be reached ({exc.detail}); "
                                             f"nothing was changed")
        raise
    new = new_chain[-1]
    made.git.new_version = new.version or None
    shipped = defaults[max(defaults)]
    before, faults = _resolved_git(shipped, old_chain)
    if before is None:
        raise CompassError(f"the current pin {old.sha[:7]} of {label} fails its own check: "
                           f"{faults[0]} (run compass policy lint)")
    after, faults = _resolved_git(shipped, new_chain, check=True)
    if after is None:
        made.invalid = faults
        return made
    return _compare(made, root, before, after, old.layer.name, new.layer.name)


# --- the text edit --------------------------------------------------------------------

# The file is edited as lines so that comments and order survive. Only block
# style is reached: a waiver written as a flow mapping is an error that names
# it, because an edit inside braces cannot be made line by line.

_MAJOR = re.compile(r"(compass:[a-z][a-z0-9-]*@)\d+")
_PIN = re.compile(r"(github:[^#\s]+#)[0-9a-f]{7,40}")
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
    """Rewrite the integer after `@` in `extends:` (or in its `from:`), or,
    when `target` is text, the sha after `#` in a git parent's value."""
    at = next((n for n, line in enumerate(lines) if re.match(r"^extends\s*:", line)), None)
    if at is not None and not _value(lines[at]):
        first, end = _block(lines, at)
        at = next((n for n in range(first, end) if re.match(r"^\s+from\s*:", lines[n])), None)
    if at is None:
        raise CompassError("compass.yml: the extends line was not found as text")
    head, _, rest = lines[at].partition(":")
    value = _value(lines[at])
    found = _PIN if isinstance(target, str) else _MAJOR
    if len(found.findall(value)) != 1:
        raise CompassError("compass.yml: the extends value is not one "
                           + ("github:<owner>/<repo>@<ref>#<sha>" if isinstance(target, str)
                              else "compass:<name>@<major>"))
    lines[at] = head + ":" + rest.replace(value, found.sub(rf"\g<1>{target}", value), 1)


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
    box[key] = (_PIN.sub(rf"\g<1>{target}", box[key]) if isinstance(target, str)
                else layers.default_extends(target))
    for catalogue, entry_id, approver, day in approvals:
        body = out[catalogue][entry_id]["waiver"]
        body["approved_by"], body["approved_on"] = approver, day
    return out


def rewrite_text(text, target, approvals):
    """`compass.yml` as text with the major set to `target` (or, when `target`
    is a sha, the pin of a git parent) and, for each
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
    """What a run did. `status` is `applied`, `nothing-to-do`, `refused` or
    `offline`; a refusal, and an offline run, carry `(code, message)`. An
    offline run decided nothing: the host could not be asked. `waivers` are the
    plan's views with a re-approved waiver marked `reapproved`: the plan itself
    is not changed."""
    plan: Plan
    status: str
    written: bool = False
    refusal: object = None
    waivers: list = field(default_factory=list)

    @property
    def exit_code(self):
        return 1 if self.status in ("refused", "offline") else 0


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
                               f"{made.new_ref}? [y/N] "):
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
    if made.offline:
        return Outcome(made, "offline", False, ("offline", made.offline), [])
    if made.nothing_to_do:
        return Outcome(made, "nothing-to-do", waivers=list(made.waivers))
    target = made.new_ref
    if made.invalid:
        more = len(made.invalid) - 1
        return _refused(made, "new-parent-invalid",
                        f"the new commit of the git parent fails its own check: "
                        f"{made.invalid[0]}" + (f" (and {more} more)" if more else "")
                        + ". The pin stays where it is; ask the parent's owners to fix it")
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
    new = rewrite_text(made.text, made.move_to, approvals)
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
    if made.git:
        # A git parent has no major. Its `from` and `to` carry the pin too,
        # as `sha` (null when the ref could not be resolved), after `version`.
        git = made.git
        sides = ({"ref": git.label, "major": None, "version": git.old_version,
                  "sha": git.old_sha},
                 {"ref": git.label, "major": None, "version": git.new_version,
                  "sha": git.new_sha})
    else:
        sides = ({"ref": layers.default_extends(made.current), "major": made.current,
                  "version": versions.get("from")},
                 {"ref": layers.default_extends(made.target), "major": made.target,
                  "version": versions.get("to")})
    return {
        "schema": JSON_SCHEMA_VERSION,
        "status": out.status,
        "written": out.written,
        "from": sides[0],
        "to": sides[1],
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
    versions = made.versions
    shown = f" ({versions['from']} -> {versions['to']})" if versions else ""
    if made.offline:
        return [f"compass policy update: {made.old_ref} (the ref was not resolved)"]
    lines = [f"compass policy update: {made.old_ref} -> {made.new_ref}{shown}"]
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
    target = out.plan.new_ref
    if out.status == "offline":
        return _wrap("offline: ", out.refusal[1])
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
