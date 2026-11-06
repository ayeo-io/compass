# compass_pkg.policy_effective - the effective view of a configuration chain
"""What a configuration chain resolves to, as `compass policy show` prints it.

Each resolved field is one row: its value, the layer that wrote it and how
(add, replace or set), and the waiver that excuses it. A chain that the lint's
`layer` or `merge` group refuses cannot be resolved. The text and JSON
renderings are in this module so the two views of one result cannot
disagree. The JSON shape is a public contract (`docs/policy-lint.md`).
"""
# DEPENDENCY: standard library (dataclasses, datetime, json);
# compass_pkg.catalogue_spec, locks, waivers, core, and compass_pkg.policy_lint
# (its `layer` and `merge` groups, and the JSON schema version). Imported by
# compass_pkg.policy_cmd.
from __future__ import annotations

import datetime
import json
from dataclasses import dataclass, field

from compass_pkg import locks, waivers
from compass_pkg import catalogue_spec as spec
from compass_pkg.core import CompassError
from compass_pkg.policy_lint import JSON_SCHEMA_VERSION, _layer_group, _merge_group


@dataclass
class Row:
    path: str
    value: object
    source: str
    op: str
    waiver: object = None
    note: object = None


@dataclass
class Effective:
    layers: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    issue: object = None


# The stage lists a capability switches on: until it is on, the evaluator
# reads them and nothing blocks on them, so the view says so.
INACTIVE_UNTIL = {("stages", "entry"): "entry-exit-evaluation",
                  ("stages", "exit"): "entry-exit-evaluation"}


def _label(layer, meta):
    if layer.kind == "parent" and meta:
        return f"{meta.get('id', layer.name)}@{meta.get('version', '')}"
    return layer.name


def _waiver_record(waiver):
    body = waiver.body if isinstance(waiver.body, dict) else {}
    given = body.get("approved_on")
    return {"id": waiver.id, "scope": waiver.scope,
            "approved_by": body.get("approved_by"),
            "approved_on": given.isoformat() if hasattr(given, "isoformat")
            else (str(given) if given is not None else None)}


def _waived_fields(chain):
    """`{(layer name, catalogue, entry, field): waiver record}`."""
    out = {}
    for layer in chain:
        if layer.kind == "parent":
            continue
        found, _ = waivers.find(layer.doc, "issue" if layer.kind == "issue" else "project")
        for waiver in found:
            for name in waiver.fields:
                out[(layer.name, waiver.catalogue, waiver.entry, name)] = _waiver_record(waiver)
    return out


def _top_rows(chain, labels):
    """The rows for `capabilities`, `owner` and `approvers`: each name takes
    the value of the last layer that holds it. `labels` maps a layer name to
    the source shown."""
    def gather(section):
        held = {}
        for layer in chain:
            value = layer.doc.get(section)
            if isinstance(value, dict):
                for name, item in value.items():
                    held[name] = (item, layer, "set" if name in held else "add")
        return [Row(f"{section}.{name}", item, labels[layer.name], op)
                for name, (item, layer, op) in sorted(held.items())]

    owner = None
    for layer in chain:
        if "owner" in layer.doc:
            owner = Row("owner", layer.doc["owner"], labels[layer.name],
                        "set" if owner else "add")
    return gather("capabilities") + ([owner] if owner else []) + gather("approvers")


def resolve_effective(parent, project, issue=None, *, meta=None, slug=None,
                      git_parents=()):
    """The `Effective` view of a chain: every resolved field with its value,
    the layer that wrote it and how, and the waiver that excuses it.
    `git_parents` are `parents.Parent`s, root first, between `parent` and the
    project; each is its own source. A chain that does not load or merge
    cannot be resolved, so it raises `CompassError` and points to
    `policy lint`."""
    chain = [layer for layer in (parent, *[p.layer for p in git_parents], project, issue)
             if layer is not None]
    versions = {p.layer.name: p.version or None for p in git_parents}
    state = {"chain": chain, "today": datetime.date.today()}
    # A warning, such as a removed setting (ADR-090), does not stop resolution.
    problems = [f for f in _layer_group(state) if f.level == "error"] or [
        f for f in _merge_group(state) if f.level == "error"]
    if problems:
        first = problems[0]
        raise CompassError(
            f"nothing can be resolved: {first.code} [{first.layer}] {first.path}: "
            f"{first.message} ({len(problems)} problem(s); run compass policy lint)")
    labels = {layer.name: layer.name if layer.name in versions else _label(layer, meta)
              for layer in chain}
    waived = _waived_fields(chain)
    rows = _top_rows(chain, labels)
    on = {r.path.split(".", 1)[1] for r in rows
          if r.path.startswith("capabilities.") and r.value is True}
    held = locks.lock_set(chain)
    for catalogue in spec.CATALOGUES:
        for entry_id, entry in sorted((state["config"].get(catalogue) or {}).items()):
            for name in spec.FIELDS[catalogue]:
                # A lock is read from the layers, not from the merged entry: the
                # merge keeps `locked` only on checks and gates, and keeps it
                # after an unlock lifts it.
                if name not in entry or name == "locked":
                    continue
                path = f"{catalogue}.{entry_id}.{name}"
                written = (state["provenance"].get(path)
                           or state["provenance"].get(f"{catalogue}.{entry_id}")
                           or {"layer": chain[0].name, "operation": "add"})
                needs = INACTIVE_UNTIL.get((catalogue, name))
                rows.append(Row(
                    path, entry[name], labels[written["layer"]], written["operation"],
                    waived.get((written["layer"], catalogue, entry_id, name)),
                    f"inactive: {needs} off" if needs and needs not in on else None))
            lock = held.get(f"{catalogue}.{entry_id}")
            if lock:
                kind = next(l.kind for l in chain if l.name == lock.layer)
                rows.append(Row(f"{catalogue}.{entry_id}.locked", lock.level,
                                labels[lock.layer], "add" if kind == "parent" else "set"))
    return Effective(
        layers=[{"name": l.name, "kind": l.kind,
                 "version": versions[l.name] if l.name in versions
                 else (meta or {}).get("version") if l.kind == "parent" else None,
                 "digest": l.digest} for l in chain],
        rows=rows, issue=slug)


def _show(value, limit=44):
    text = value if isinstance(value, str) else json.dumps(
        value, default=str, ensure_ascii=False, separators=(", ", ": "))
    return text if len(text) <= limit else text[:limit - 3] + "..."


def _source_text(row):
    said = row.op
    if row.waiver:
        who = row.waiver["approved_by"]
        said += (f", waiver by {who}, {row.waiver['approved_on']}"
                 if row.waiver["scope"] == "project" else f", waiver {who}")
    return f"{row.source} ({said})" + (f"  ({row.note})" if row.note else "")


def effective_json(effective):
    """The view as the documented dictionary."""
    return {
        "schema": JSON_SCHEMA_VERSION,
        "scope": {"kind": "issue" if effective.issue else "project",
                  "issue": effective.issue, "resolved": "live"},
        "layers": [dict(layer) for layer in effective.layers],
        "fields": [{"path": r.path, "value": r.value, "source": r.source, "op": r.op,
                    "waiver": r.waiver, "note": r.note} for r in effective.rows],
    }


def effective_text(effective, notice=None):
    scope = f"issue {effective.issue}" if effective.issue else "project"
    names = [l["name"] if l["version"] is None else f"{l['name']}@{l['version']}"
             for l in effective.layers]
    lines = [f"compass policy show: {scope} - layers: {', '.join(names)}"]
    lines += [notice] if notice else []
    lines += ["  This is what the configuration resolves to now. compass check and the "
             "evaluator judge an issue that has a stored generation by that "
             "generation, which can differ from this view."]
    if effective.issue:
        lines.append("  Resolved from the live project file and the issue's own layer, "
                     "not from its stored generation.")
    width = min(max((len(r.path) for r in effective.rows), default=0), 56)
    shown = [_show(r.value) for r in effective.rows]
    value_width = max((len(s) for s in shown), default=0)
    lines += [f"{r.path:<{width}}  {text:<{value_width}}  {_source_text(r)}"
              for r, text in zip(effective.rows, shown)]
    return lines
