# compass_pkg.replay - replay assessments under two configurations
"""Compare two configurations by classifying them and by replaying
assessments under both (`compass policy diff`, ADR-036 and ADR-037).

This module has four parts: the references (`default@6`, `project`, a path
and the others) that name a configuration; the replay of the grid, the label
combinations and the archive; the comparison of open issues; and the one
document the result becomes. It reads files and runs `git show`, writes no
file of the project (the `git show` copy goes to a temporary folder), and
changes none of the modules it calls.
"""
# DEPENDENCY: standard library (dataclasses, itertools, json, os, subprocess,
# tempfile, textwrap); compass_pkg.atomic_io (digest, load_yaml_strict),
# catalogue_check, catalogue_spec (LABEL_CAP), the classifier module (the
# classify and build_grid functions, json_shape_errors), core (CompassError,
# load_yaml), legacy_adapter (adapt), manifest (the issue statuses), merge, the
# obligations module (its function of that name, Refused, COMPARED_FACTS,
# assessment_vocabulary), policy_lint (load_parent) and waivers (find,
# describe, recheck) and parents (resolve_chain, ParentError). Only
# compass_pkg.policy_cmd imports it.
from __future__ import annotations

import dataclasses
import itertools
import json
import os
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass, field

from compass_pkg import catalogue_check, classify, legacy_adapter, manifest, merge
from compass_pkg import catalogue_spec as spec
from compass_pkg import obligations, parents, policy_lint, waivers
from compass_pkg.atomic_io import StrictYamlError, digest, load_yaml_strict
from compass_pkg.core import CompassError, load_yaml, manifest_path

JSON_SCHEMA_VERSION = 1

PROJECT_FILE = "compass.yml"

# What a person types for each reference, and the label each one gets.
DEFAULT_REF = "default"
SHIPPED_MAJOR = "6"


# --- the references ------------------------------------------------------------------

@dataclass
class Config:
    """One side of a comparison: the resolved configuration, the capability
    switches that are on, and where it came from. `ref` is the label (never a
    path outside the project) and `kind` is `default`, `project`, `legacy`,
    `git`, `file` or `parent` (a git parent written as in `extends:`).
    `default_version` is the version of the shipped default
    underneath, or None for `legacy`."""
    ref: str
    kind: str
    config: dict
    capabilities: tuple = ()
    provenance: dict = field(default_factory=dict)
    default_version: object = None

    @property
    def digest(self):
        return digest({"config": self.config, "capabilities": list(self.capabilities)})

    def to_json(self):
        return {"ref": self.ref, "kind": self.kind,
                "default_version": self.default_version, "digest": self.digest,
                "capabilities": list(self.capabilities)}


def default_refs(refs):
    """`(A, B)` from the references given: none compares the project file at
    git `HEAD` with the working file, one compares the project with it."""
    refs = list(refs)
    if len(refs) > 2:
        raise CompassError(f"compass policy diff takes at most two references, "
                           f"found {len(refs)}")
    if not refs:
        return "git:HEAD", "project"
    if len(refs) == 1:
        return "project", refs[0]
    return refs[0], refs[1]


def _on(documents):
    """The capability switches that are on after `documents`; a later layer
    overrides an earlier one."""
    state = {}
    for doc in documents:
        capabilities = doc.get("capabilities") if isinstance(doc, dict) else None
        state.update(capabilities or {})
    return tuple(sorted(k for k, v in state.items() if v is True))


def _shipped():
    parent, meta = policy_lint.load_parent()
    config, provenance = merge.apply({}, parent.doc, "parent", "default", {})
    return parent, meta, config, provenance


def _shown(path, root):
    absolute, base = os.path.abspath(path), os.path.abspath(root)
    inside = absolute.startswith(base + os.sep)
    shown = os.path.relpath(absolute, base) if inside else os.path.basename(absolute)
    return shown.replace(os.sep, "/")


def _overlay(label, kind, doc):
    """The shipped default with one project layer over it, resolved. A layer
    that fails its own check or does not merge is a refusal that names the
    reference."""
    parent, meta, config, provenance = _shipped()
    problems = catalogue_check.check_layer(doc, "project")
    if problems:
        raise CompassError(f"{label}: {problems[0]} ({len(problems)} problem(s); "
                           f"run compass policy lint --file)")
    try:
        merged, provenance = merge.apply(config, doc, "project", "project", provenance)
    except merge.MergeError as exc:
        said = "; ".join(f"{code} {where}: {message}" for code, where, message in exc.errors)
        raise CompassError(f"{label}: {said} (run compass policy lint --file)")
    return Config(label, kind, merged, _on([parent.doc, doc]), provenance,
                  meta.get("version"))


def _load_file(path, label, kind):
    try:
        doc = load_yaml_strict(path)
    except StrictYamlError as exc:
        text = str(exc)
        text = text[len(os.fspath(path)):] if text.startswith(os.fspath(path)) else f": {text}"
        raise CompassError(f"{label}{text}")
    return _overlay(label, kind, doc)


def _default(label, kind):
    parent, meta, config, provenance = _shipped()
    return Config(label, kind, config, _on([parent.doc]), provenance, meta.get("version"))


def _default_ref(ref):
    """The shipped default for `default`, `default@6` and `default@6.0.0`,
    with or without the `compass:` prefix an `extends:` line uses."""
    body = ref[len("compass:"):] if ref.startswith("compass:") else ref
    _, _, wanted = body.partition("@")
    parent, meta, _, _ = _shipped()
    version = str(meta.get("version", ""))
    if wanted in ("", SHIPPED_MAJOR, version):
        if "@" in body and not wanted:
            raise CompassError(f"'{ref}' names no version; write default@{SHIPPED_MAJOR}")
        return _default(f"default@{SHIPPED_MAJOR}", "default")
    raise CompassError(f"'{ref}': only default@{SHIPPED_MAJOR} ships "
                       f"(version {version}), so {body} cannot be compared")


def _legacy(root):
    names = ("routing-policy.yml", "guardrails.yml")
    paths = [os.path.join(root, "governance", name) for name in names]
    missing = [n for n, p in zip(names, paths) if not os.path.isfile(p)]
    if missing:
        raise CompassError(f"legacy: the project holds no copied governance "
                           f"({', '.join(missing)} missing from governance/)")
    doc = legacy_adapter.adapt(load_yaml(paths[0]), load_yaml(paths[1]))
    config, provenance = merge.apply({}, doc, "parent", "legacy", {})
    return Config("legacy", "legacy", config, _on([doc]), provenance, None)


def _git(root, *argv):
    try:
        return subprocess.run(["git", *argv], cwd=root, capture_output=True, text=True)
    except OSError as exc:
        raise CompassError(f"git cannot be run: {exc}")


def _git_ref(ref, root):
    revision = ref[len("git:"):]
    if not revision or revision.startswith("-"):
        raise CompassError(f"'{ref}' is not a git revision")
    found = _git(root, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}")
    if found.returncode != 0:
        raise CompassError(f"'{ref}': git has no revision '{revision}' here (is this a "
                           f"git repository?)")
    if _git(root, "cat-file", "-e", f"{revision}:{PROJECT_FILE}").returncode != 0:
        return _default(ref, "git")
    shown = _git(root, "show", f"{revision}:{PROJECT_FILE}")
    if shown.returncode != 0:
        raise CompassError(f"'{ref}': git cannot read {PROJECT_FILE} at '{revision}'")
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, PROJECT_FILE)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(shown.stdout)
        return _load_file(path, ref, "git")


def _parent_ref(ref, root, fetch):
    """The shipped default with the git parent `ref` and the parents it
    extends over it, resolved. `ref` is written as in `extends:`. A parent is
    data, so each layer must pass the parent layer check before it merges (no
    settings key, no `unlock:`). Nothing the parent carries is run. An uncached
    pin is fetched into the project's cache only when `fetch` is true."""
    try:
        chain = parents.resolve_chain(root, ref, fetch=fetch)
    except parents.ParentError as exc:
        raise CompassError(f"{ref}: {exc}")
    shipped, meta, config, provenance = _shipped()
    documents = [shipped.doc]
    for found in chain:
        layer = found.layer
        problems = catalogue_check.check_layer(layer.doc, "parent")
        if problems:
            raise CompassError(f"{ref}: {layer.name}: {problems[0]} ({len(problems)} "
                               f"problem(s); run compass policy lint)")
        try:
            config, provenance = merge.apply(config, layer.doc, "parent", layer.name,
                                             provenance)
        except merge.MergeError as exc:
            said = "; ".join(f"{code} {where}: {message}" for code, where, message in exc.errors)
            raise CompassError(f"{ref}: {said} (run compass policy lint)")
        documents.append(layer.doc)
    return Config(ref, "parent", config, _on(documents), provenance, meta.get("version"))


def resolve_ref(ref, root, cwd=None, fetch=False):
    """The `Config` a reference names, or a `CompassError` that names it.
    The keywords win over a file of the same name. `fetch` lets a git parent
    that is not cached be fetched."""
    root = os.fspath(root)
    if ref.startswith("github:"):
        return _parent_ref(ref, root, fetch)
    if ref in (DEFAULT_REF, f"compass:{DEFAULT_REF}") or ref.startswith(
            ("default@", f"compass:{DEFAULT_REF}@")):
        return _default_ref(ref)
    if ref == "project":
        path = os.path.join(root, PROJECT_FILE)
        return _load_file(path, "project", "project") if os.path.isfile(path) \
            else _default("project", "project")
    if ref == "legacy":
        return _legacy(root)
    if ref.startswith("git:"):
        return _git_ref(ref, root)
    if ref.startswith("generation:"):
        raise CompassError(f"'{ref}': the generation store has not landed, so a stored "
                           f"generation cannot be compared yet")
    path = os.path.join(os.fspath(cwd or os.getcwd()), ref) if ref else ""
    if ref and os.path.isfile(path):
        return _load_file(path, f"file:{_shown(path, root)}", "file")
    raise CompassError(f"'{ref}' is not a configuration reference and no such file "
                       f"exists; use default@{SHIPPED_MAJOR}, project, legacy, "
                       f"git:<revision>, a github: git parent or a path to a compass.yml")


# --- one assessment under both sides ------------------------------------------------------

# The facts a replay compares: the approach first, then the facts the
# classifier compares (in the order `Obligations` declares them), then the
# rules that fired. `approach` and `rules_fired` are outcomes, not
# obligations, so only a replay reports them.
FACTS = ("approach",
         *(f.name for f in dataclasses.fields(obligations.Obligations)
           if f.name in obligations.COMPARED_FACTS), "rules_fired")

IDENTICAL = "the configurations are identical"


def _plain(value):
    """A value as plain JSON: mappings with sorted keys, sets sorted."""
    if isinstance(value, dict):
        return {str(k): _plain(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(v) for v in value), key=str)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _outcome(config, capabilities, assessment, issue=None):
    """`("runs", Obligations)`, `("refused", reason)` (a routing conflict) or
    `("cannot-run", message)` (the evaluator rejects this assessment, such as
    a value the configuration's vocabulary lacks)."""
    try:
        got = obligations.obligations(config, assessment, capabilities=capabilities,
                                      issue=issue)
    except CompassError as exc:
        return ("cannot-run", str(exc))
    if isinstance(got, obligations.Refused):
        return ("refused", got.reason)
    return ("runs", got)


def _say(outcome):
    kind, value = outcome
    return "runs" if kind == "runs" else f"{kind.replace('-', ' ')}: {value}"


def _difference(field_name, key, before, after):
    return {"field": field_name, "key": key, "before": before, "after": after}


def _differences(before, after):
    """Each difference between two outcomes as `field`, `key`, `before` and
    `after`. A fact that maps names to values gives one difference for each
    name whose value differs. Two sides that do not both run give one
    `evaluation` difference, unless they match."""
    if before[0] != "runs" or after[0] != "runs":
        if before == after:
            return []
        return [_difference("evaluation", None, _say(before), _say(after))]
    out = []
    for name in FACTS:
        x, y = _plain(getattr(before[1], name)), _plain(getattr(after[1], name))
        if x == y:
            continue
        if isinstance(x, dict) and isinstance(y, dict):
            out += [_difference(name, key, x.get(key), y.get(key))
                    for key in sorted(set(x) | set(y)) if x.get(key) != y.get(key)]
        else:
            out.append(_difference(name, None, x, y))
    return out


def _accepts(config, dimension, value):
    vocabulary = obligations.assessment_vocabulary(config.get("dimensions") or {})
    return value is None or dimension not in vocabulary or value in vocabulary[dimension]


class _Replay:
    """The two sides and what they have already evaluated."""

    def __init__(self, a, b):
        self.sides = (a, b)
        self.cache = {}

    def outcome(self, side, assessment, issue=None):
        config = self.sides[side]
        key = (side, json.dumps(assessment, sort_keys=True, default=str),
               json.dumps(issue, sort_keys=True, default=str))
        if key not in self.cache:
            self.cache[key] = _outcome(config.config, config.capabilities, assessment, issue)
        return self.cache[key]

    def differences(self, assessment, issue=None):
        return _differences(self.outcome(0, assessment, issue),
                            self.outcome(1, assessment, issue))


# --- the grid ------------------------------------------------------------------------

def _point(name, issue, assessment, represents, differences):
    return {"set": name, "issue": issue, "assessment": _plain(assessment),
            "represents": represents, "differences": differences}


def _scan_grid(run, grid, name, subsets):
    """The changes at each point of the grouped grid, for the given label
    subsets, in the order the classifier scans: each combination of value
    classes, then each subset. `(replayed, changes)`."""
    replayed, changes = 0, []
    for combo in itertools.product(*[classes for _, classes in grid.dimensions]):
        assessment = {dim: cls.values[0] for (dim, _), cls in zip(grid.dimensions, combo)
                      if cls.values[0] is not None}
        represents = {dim: list(cls.values) for (dim, _), cls in zip(grid.dimensions, combo)}
        one_side = [(dim, cls) for (dim, _), cls in zip(grid.dimensions, combo)
                    if cls.kind == "one-side"]
        for subset in subsets:
            point = dict(assessment, labels=list(subset))
            replayed += 1
            if one_side:
                found = [_difference("dimensions.values", dim,
                                     _accepts(run.sides[0].config, dim, cls.values[0]),
                                     _accepts(run.sides[1].config, dim, cls.values[0]))
                         for dim, cls in one_side]
            else:
                found = run.differences(point)
            if found:
                changes.append(_point(name, None, point, represents, found))
    return replayed, changes


# --- the archive ---------------------------------------------------------------------------

@dataclass
class Issue:
    """What a replay reads of one issue: its slug, lifecycle status, recorded
    assessment (None when it has none) and its own `config:` layer (None when
    it has none). `unreadable` is true for a manifest that does not parse as a
    mapping: it is named in the document and nothing else is read from it."""
    slug: str
    status: object
    assessment: object
    config: object = None
    unreadable: bool = False


def read_archive(root):
    """Every issue under `.compass/work/` of the project, by slug. A folder
    with no manifest is left out. A manifest that does not parse as a mapping
    is kept as an unreadable issue, so the document can name it."""
    work = os.path.join(os.fspath(root), ".compass", "work")
    if not os.path.isdir(work):
        return []
    found = []
    for slug in sorted(os.listdir(work)):
        path = manifest_path(os.path.join(work, slug))
        if not os.path.isfile(path):
            continue
        try:
            data = load_yaml(path)
        except CompassError:
            data = None
        if isinstance(data, dict):
            found.append(Issue(slug, data.get("status"), data.get("assessment"),
                               data.get("config")))
        else:
            found.append(Issue(slug, None, None, None, True))
    return found


def _replay_archive(run, archive):
    replayed, changes = 0, []
    for issue in sorted(archive, key=lambda i: i.slug):
        if not isinstance(issue.assessment, dict):
            continue
        replayed += 1
        found = run.differences(issue.assessment)
        if found:
            changes.append(_point("archive", issue.slug, issue.assessment, None, found))
    return replayed, changes


# --- the sets ------------------------------------------------------------------------------

def _set_entry(name, replayed, changes, skipped=None):
    return {"name": name, "replayed": replayed, "changed": len(changes), "skipped": skipped}


def replay_sets(a, b, archive=()):
    """`(sets, changes)`: for each set replayed, its counts, and every
    assessment whose result differs, the sets in the order `grid`, `labels`,
    `archive`."""
    if a.config == b.config and a.capabilities == b.capabilities:
        return [_set_entry(name, 0, [], IDENTICAL)
                for name in ("grid", "labels", "archive")], []
    run = _Replay(a, b)
    grid = classify.build_grid(a.config, b.config)
    replayed, grid_changes = _scan_grid(run, grid, "grid", [()])
    sets, changes = [_set_entry("grid", replayed, grid_changes)], list(grid_changes)
    if len(grid.labels) > spec.LABEL_CAP:
        sets.append(_set_entry("labels", 0, [], (
            f"more than eight named labels: {len(grid.labels)} "
            f"({', '.join(grid.labels)}); the grid is not sampled")))
    else:
        replayed, found = _scan_grid(run, grid, "labels", grid.label_subsets()[1:])
        sets.append(_set_entry("labels", replayed, found))
        changes += found
    replayed, found = _replay_archive(run, archive)
    readable = [i for i in archive if not i.unreadable]
    why = None if replayed else (
        "no archived issue has a recorded assessment" if readable
        else "the project holds no archived issue")
    sets.append(_set_entry("archive", replayed, found, why))
    return sets, changes + found


# --- the open issues -----------------------------------------------------------------------

# The statuses of an issue still in flight: every status that is not terminal.
OPEN_STATUSES = tuple(s for s in manifest.TASK_STATUSES
                      if s not in manifest.TERMINAL_STATUSES)


def _merged(side, layer):
    """`(configuration, None)` with the issue's layer applied, or `(None,
    message)` when the layer is not well formed or does not merge."""
    if layer is None:
        return side.config, None
    problems = catalogue_check.check_layer(layer, "issue")
    if problems:
        return None, problems[0]
    try:
        merged, _ = merge.apply(side.config, layer, "issue", "issue", side.provenance)
    except merge.MergeError as exc:
        return None, str(exc)
    return merged, None


def _invalidated(issue, layer, a, b, merged_a):
    """The issue's waivers that the move from A to B invalidates, each as a
    field whose parent value changed since the approval."""
    found, _ = waivers.find(layer, "issue")
    out = []
    for waiver in found:
        record = waivers.describe(waiver, a.config, merged_a, None)
        for gone in waivers.recheck([record], b.config):
            out.append({"issue": issue.slug, "waiver": gone.waiver_id, "entry": gone.entry,
                        "field": gone.field, "before": _plain(gone.old),
                        "after": _plain(gone.new), "message": gone.reason})
    return out


def _unreadable(issues):
    return sorted(i.slug for i in issues if i.unreadable)


def open_report(a, b, issues):
    """The open issues a move from A to B would change: each is run over A
    and over B with its own `config:` layer. Until the generation store
    exists, A stands for what an issue runs against and B for what it meets
    at its next reassess."""
    flying = sorted((i for i in issues if i.status in OPEN_STATUSES and not i.unreadable),
                    key=lambda i: i.slug)
    listed, expiring = [], []
    for issue in flying:
        layer = issue.config if isinstance(issue.config, dict) else None
        sides, unresolved = [], None
        for name, side in (("a", a), ("b", b)):
            merged, problem = _merged(side, layer)
            if problem:
                unresolved = {"side": name, "message": problem}
                break
            sides.append(merged)
        differences = []
        if unresolved is None:
            if isinstance(issue.assessment, dict):
                differences = _differences(
                    _outcome(sides[0], a.capabilities, issue.assessment, layer),
                    _outcome(sides[1], b.capabilities, issue.assessment, layer))
            if layer is not None:
                expiring += _invalidated(issue, layer, a, b, sides[0])
        if differences or unresolved:
            listed.append({"issue": issue.slug, "status": issue.status,
                           "assessment": _plain(issue.assessment),
                           "differences": differences, "unresolved": unresolved})
    return {"examined": len(flying), "issues": listed, "waivers": expiring,
            "unreadable": _unreadable(issues)}


def _classification(a, b):
    return classify.classify(
        a.config, b.config, parent_capabilities=a.capabilities,
        child_capabilities=b.capabilities, parent_name=a.ref, child_name=b.ref).to_json()


def diff(a, b, archive=(), open=False):
    """The document for two `Config`s: their classification, and the replay
    of the grid, the label combinations and the archive (`Issue`s)."""
    classification = _classification(a, b)
    sets, changes = replay_sets(a, b, archive)
    flying = open_report(a, b, archive) if open else None
    return {
        "schema": JSON_SCHEMA_VERSION,
        "differs": (classification["result"] != "equivalent" or bool(changes)
                    or bool(flying and (flying["issues"] or flying["waivers"]))),
        "a": a.to_json(),
        "b": b.to_json(),
        "classification": classification,
        "replay": {"sets": sets, "changes": changes, "unreadable": _unreadable(archive)},
        "open": flying,
    }


# The text shows this many changes of each set, and counts the rest.
TEXT_LIMIT = 5
TEXT_WIDTH = 100


def _compact(value, limit=60):
    text = json.dumps(value, default=str, ensure_ascii=False, separators=(", ", ": "))
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _wrapped(first, text, rest="    "):
    """`first + text` as lines of at most `TEXT_WIDTH` columns; a continuation
    line starts with `rest`."""
    return textwrap.wrap(first + text, TEXT_WIDTH, subsequent_indent=rest,
                         break_long_words=False, break_on_hyphens=False)


def _where(change):
    """The assessment of a change as one phrase: the dimensions in the order
    of the configuration (a grid point says them), then the labels."""
    assessment = change["assessment"] or {}
    order = list(change["represents"]) if change["represents"] else sorted(assessment)
    shown = [f"{k} {assessment[k]}" for k in order if k in assessment and k != "labels"]
    labels = assessment.get("labels")
    if "labels" in assessment:
        shown.append("labels " + (", ".join(labels) if labels else "none"))
    return ", ".join(shown)


def _difference_lines(differences, indent):
    lines = []
    for item in differences:
        name = item["field"] + (f" {item['key']}" if item["key"] is not None else "")
        before, after = item["before"], item["after"]
        if isinstance(before, list) and isinstance(after, list):
            # Name what moved: a clipped list prints the same text on both sides.
            removed = [x for x in before if x not in after]
            added = [x for x in after if x not in before]
            said = "; ".join(([f"removed {_compact(removed)}"] if removed else [])
                             + ([f"added {_compact(added)}"] if added else []))
            lines += _wrapped(f"{indent}{name}: ", said or f"reordered {_compact(after)}",
                              indent + "  ")
            continue
        if isinstance(before, dict) and isinstance(after, dict):
            # A check or a ceiling table: name only the entries that differ.
            for part in sorted(set(before) | set(after)):
                if before.get(part) != after.get(part):
                    lines += _wrapped(f"{indent}{name} {part}: ", f"{_compact(before.get(part))}"
                                      f" -> {_compact(after.get(part))}", indent + "  ")
            continue
        lines += _wrapped(f"{indent}{name}: ", f"{_compact(before)} -> {_compact(after)}",
                          indent + "  ")
    return lines


def _set_lines(document):
    lines = ["replay:"]
    for entry in document["replay"]["sets"]:
        name = entry["name"]
        if entry["skipped"]:
            lines += _wrapped(f"  {name}: skipped - ", entry["skipped"])
            continue
        lines.append(f"  {name}: {entry['replayed']} replayed, {entry['changed']} changed")
        found = [c for c in document["replay"]["changes"] if c["set"] == name]
        for change in found[:TEXT_LIMIT]:
            who = f"issue {change['issue']}: " if change["issue"] else ""
            lines += _wrapped(f"    at {who}", _where(change), "      ")
            lines += _difference_lines(change["differences"][:TEXT_LIMIT], "      ")
        if len(found) > TEXT_LIMIT:
            lines.append(f"    ... and {len(found) - TEXT_LIMIT} more in {name}; "
                         f"--json lists every one")
    return lines


def _open_lines(section):
    changed = len(section["issues"])
    lines = [f"open issues: {section['examined']} examined, "
             + (f"{changed} would change" if changed else "none would change")]
    for item in section["issues"]:
        head = f"  {item['issue']} ({item['status']}): "
        if item["unresolved"]:
            lines += _wrapped(head, f"cannot merge on {item['unresolved']['side']}: "
                              f"{item['unresolved']['message']}")
            continue
        lines.append(head.rstrip(": ") + ":")
        lines += _difference_lines(item["differences"][:TEXT_LIMIT], "    ")
        if len(item["differences"]) > TEXT_LIMIT:
            lines.append(f"    ... and {len(item['differences']) - TEXT_LIMIT} more; "
                         f"--json lists every one")
    if section["waivers"]:
        lines.append("waivers needing re-approval:")
        for item in section["waivers"]:
            lines += _wrapped(
                f"  {item['issue']} {item['waiver']} {item['field']}: ",
                f"{_compact(item['before'])} -> {_compact(item['after'])}")
    return lines


def diff_text(document):
    """The document as lines for a person, at most `TEXT_WIDTH` columns wide."""
    classification = document["classification"]
    lines = [f"compass policy diff: {document['a']['ref']} -> {document['b']['ref']}"]
    gone = document["replay"]["unreadable"]
    note = _wrapped("unreadable manifests (not replayed): ", ", ".join(gone)) if gone else []
    if not document["differs"]:
        return lines + ["no difference: the two configurations route and check alike"] + note
    lines += _wrapped("classification: ", f"{classification['result']} - "
                      f"{classification['reason']}", "  ")
    lines += _set_lines(document) + note
    if document["open"] is not None:
        lines += _open_lines(document["open"])
    return lines


# --- the documented shape ---------------------------------------------------------------------

# The documented shape of `diff()`. A string names a JSON type; `("one of",
# ...)` is a closed set of strings; `("or null", shape)` is a shape or null; a
# dictionary is an object with exactly these keys in this order; a one-item
# list is a list of that shape; `"any"` is any JSON value. The
# `classification` value has the classifier's own shape (`classify.JSON_SHAPE`),
# which `classify.json_shape_errors` checks.
SET_NAMES = ("grid", "labels", "archive")
CONFIG_KINDS = ("default", "project", "legacy", "git", "file", "parent")
_CONFIG_SHAPE = {"ref": "string", "kind": ("one of", CONFIG_KINDS),
                 "default_version": ("or null", "string"), "digest": "string",
                 "capabilities": ["string"]}
_DIFFERENCE_SHAPE = {"field": "string", "key": ("or null", "string"), "before": "any",
                     "after": "any"}
_CHANGE_SHAPE = {"set": ("one of", SET_NAMES), "issue": ("or null", "string"),
                 "assessment": "object", "represents": ("or null", "object"),
                 "differences": [_DIFFERENCE_SHAPE]}
_OPEN_ISSUE_SHAPE = {
    "issue": "string", "status": "string", "assessment": ("or null", "object"),
    "differences": [_DIFFERENCE_SHAPE],
    "unresolved": ("or null", {"side": ("one of", ("a", "b")), "message": "string"})}
_WAIVER_SHAPE = {"issue": "string", "waiver": "string", "entry": "string",
                 "field": ("or null", "string"), "before": "any", "after": "any",
                 "message": "string"}
DIFF_JSON_SHAPE = {
    "schema": "integer",
    "differs": "boolean",
    "a": _CONFIG_SHAPE,
    "b": _CONFIG_SHAPE,
    "classification": "object",
    "replay": {"sets": [{"name": ("one of", SET_NAMES), "replayed": "integer",
                         "changed": "integer", "skipped": ("or null", "string")}],
               "changes": [_CHANGE_SHAPE], "unreadable": ["string"]},
    "open": ("or null", {"examined": "integer", "issues": [_OPEN_ISSUE_SHAPE],
                         "waivers": [_WAIVER_SHAPE], "unreadable": ["string"]}),
}

_TYPES = {"string": str, "boolean": bool, "object": dict}


def _shape_errors(value, shape, path, errors):
    if shape == "any":
        return
    if isinstance(shape, tuple) and shape[0] == "or null":
        if value is not None:
            _shape_errors(value, shape[1], path, errors)
    elif isinstance(shape, tuple):
        if value not in shape[1]:
            errors.append(f"{path}: {value!r} is not one of {', '.join(shape[1])}")
    elif isinstance(shape, dict):
        if not isinstance(value, dict):
            errors.append(f"{path}: expected an object")
        elif list(value) != list(shape):
            errors.append(f"{path}: keys are {list(value)}, expected {list(shape)}")
        else:
            for key, sub in shape.items():
                _shape_errors(value[key], sub, f"{path}.{key}", errors)
    elif isinstance(shape, list):
        if not isinstance(value, list):
            errors.append(f"{path}: expected a list")
        else:
            for i, item in enumerate(value):
                _shape_errors(item, shape[0], f"{path}[{i}]", errors)
    elif shape == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{path}: expected an integer")
    elif not isinstance(value, _TYPES[shape]):
        errors.append(f"{path}: expected {shape}")


def diff_shape_errors(document):
    """What differs between a document and `DIFF_JSON_SHAPE`; empty when it
    matches. The `classification` value is checked by
    `classify.json_shape_errors`, and its errors are included."""
    errors = []
    _shape_errors(document, DIFF_JSON_SHAPE, "$", errors)
    if isinstance(document, dict) and isinstance(document.get("classification"), dict):
        errors += [f"$.classification{e[1:]}"
                   for e in classify.json_shape_errors(document["classification"])]
    return errors
