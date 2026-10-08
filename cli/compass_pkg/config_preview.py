# compass_pkg.config_preview - what a change to an issue's `config:` would do
"""The preview `compass issue configure` prints, and the waiver re-check a
reassess runs. It answers four questions about a proposed overlay:

- which resolved fields change, against the generation in force;
- how the classifier reads the issue layer over the project's configuration,
  and whether the layered lint would refuse the chain at commit;
- what the issue owes at its own assessment, before and after (the single
  assessment form of the comparison `policy diff` makes over the whole grid,
  so a later `policy diff` calls the same functions for two references);
- which approvals and waivers the change would invalidate.

It reads and resolves; it writes nothing.
"""
# DEPENDENCY: compass_pkg.catalogue_spec, classify, core (CompassError),
# effective, policy_lint. The waiver re-check is in `effective`.
from __future__ import annotations

from compass_pkg import classify, effective, policy_lint
from compass_pkg import catalogue_spec as spec
from compass_pkg.core import CompassError

SCHEMA = 1
HEADER_KEYS = ("schema", "issue", "generation")
NEXT_STEP = '/compass:assess --reassess --reason "..."'


def _flatten(value, prefix=""):
    """`{dotted path: leaf}` for a nested mapping. A list, a scalar and an
    empty mapping are leaves, so a list compares as a whole."""
    if isinstance(value, dict) and value:
        out = {}
        for key in value:
            out.update(_flatten(value[key], f"{prefix}.{key}" if prefix else str(key)))
        return out
    return {prefix: value}


def field_changes(before, after):
    """The resolved fields that differ, sorted by path: `[{path, before,
    after}]`. A field in only one side shows `None` for the other."""
    old = _flatten({k: v for k, v in before.items() if k not in HEADER_KEYS})
    new = _flatten({k: v for k, v in after.items() if k not in HEADER_KEYS})
    return [{"path": path, "before": old.get(path), "after": new.get(path)}
            for path in sorted(set(old) | set(new)) if old.get(path) != new.get(path)]


def _capabilities(chain):
    state = {}
    for layer in chain:
        state.update(layer.doc.get("capabilities") or {})
    return tuple(sorted(k for k, v in state.items() if v is True))


def _catalogues(resolved):
    return {k: v for k, v in resolved.items() if k in spec.CATALOGUES}


def _text(value):
    return value if isinstance(value, str) else str(value)


def classification_of(details):
    """`{result, reason, scan, first_point}` for the issue layer over the
    configuration the project gives, as the classifier reads it."""
    chain, configs = details["chain"], details["configs"]
    layer = chain[-1] if chain and chain[-1].kind == "issue" else None
    if layer is None:
        return {"result": "equivalent", "scan": "identical",
                "reason": "the issue has no configuration layer", "first_point": None}
    try:
        found = classify.classify(
            configs[-2], configs[-1], parent_capabilities=_capabilities(chain[:-1]),
            child_capabilities=_capabilities(chain), child_issue=layer.doc,
            parent_name="project", child_name="issue")
    except CompassError as exc:
        return {"result": "not-run", "reason": _text(exc), "scan": "none",
                "first_point": None}
    shown = found.to_json()
    return {"result": shown["result"], "reason": shown["reason"], "scan": shown["scan"],
            "first_point": shown["first_mixed"] or shown["first_looser"]}


def assessment_effect(manifest, before, after):
    """What the issue owes at its own assessment under `before` and under
    `after`, each a `Resolution` with its `details`, as
    `({approach, result, changes, refused}, the mode of each stage before)`."""
    def side(resolution, overlay):
        chain = resolution.details["chain"]
        return (_catalogues(resolution.resolved), _capabilities(chain), overlay)

    assessment = manifest.get("assessment") or {}
    old, new = side(before, _overlay(before)), side(after, _overlay(after))
    try:
        got = classify.compare_at(old[0], new[0], assessment, parent_capabilities=old[1],
                                  child_capabilities=new[1], parent_issue=old[2],
                                  child_issue=new[2])
    except CompassError as exc:
        return ({"approach": {"before": None, "after": None}, "result": "not-run",
                 "changes": [], "refused": {"before": None, "after": _text(exc)}}, {})
    return ({"approach": {"before": got.approach[0], "after": got.approach[1]},
             "result": got.result,
             "changes": [{"fact": c.fact, "field": c.field, "key": c.key,
                          "outcome": c.outcome, "before": classify.plain(c.parent),
                          "after": classify.plain(c.child)} for c in got.changes],
             "refused": ({"before": got.refused[0], "after": got.refused[1]}
                         if any(got.refused) else None)}, got.stage_modes[0])


def _fill_modes(changes, modes):
    """A stage whose mode the issue's layer sets has no `mode` field before:
    the stage's mode comes from the approach. Show the mode the issue has."""
    for change in changes:
        parts = change["path"].split(".")
        if (len(parts) == 3 and parts[0] == "stages" and parts[2] == "mode"
                and change["before"] is None and modes.get(parts[1]) is not None):
            change["before"] = modes[parts[1]]
    return changes


def _overlay(resolution):
    layer = resolution.details["loaded"].issue
    return layer.doc if layer is not None else None


def _kind(record_id):
    return "waiver" if str(record_id).startswith("waiver:") else "approval"


def plan_resolution(root, task_dir, manifest, slug):
    """`(resolution, invalidated, resolve_with)` for the issue's `manifest`:
    the configuration it resolves to, with each stale issue waiver left out so
    its field reverts to the parent's value; the records that makes invalid
    (`{id: reason}`); and the manifest the resolution was made from. A commit
    stores the resolution and writes the manifest as it is."""
    stored = effective.stored_documents(task_dir, manifest)
    first = effective.resolve_live(root, manifest, slug, task_dir)
    if stored is None:
        return first, {}, manifest
    stale, entries = effective.stale_waivers(stored, first.details)
    if not entries:
        return first, {}, manifest
    adjusted = effective.without_entries(manifest, entries)
    return (effective.resolve_live(root, adjusted, slug, task_dir),
            effective.invalidated_records(stored, stale), adjusted)


# --- the preview ---------------------------------------------------------------------

def _reasons(report):
    return [f"{f.code} {f.path}: {f.message}" for f in report.errors]


def build(root, task_dir, manifest, overlay, slug, base="config"):
    """The preview document for `overlay` as the issue's `config:`, in the
    key order the JSON contract fixes. `manifest` is the issue's manifest as
    it is on disk. `base` says what the overlay was built on: `config` or
    `pending proposal`. Raises `CompassError` when the project's own layers cannot
    be resolved; a proposal that cannot be resolved, or that the lint would
    refuse, is a `refused` verdict and not an error."""
    stored = effective.stored_documents(task_dir, manifest)
    held = manifest["generation"]
    proposed = dict(manifest)
    if overlay:
        proposed["config"] = overlay
    else:
        proposed.pop("config", None)
    current = effective.resolve_live(root, manifest, slug, task_dir)
    reasons, after, invalidated = [], None, {}
    try:
        after, invalidated, _ = plan_resolution(root, task_dir, proposed, slug)
    except CompassError as exc:
        reasons.append(_text(exc))
    doc = {"schema": SCHEMA, "issue": slug, "generation": held, "proposed": held + 1,
           "verdict": "refused", "reasons": reasons,
           "proposal": f".compass/work/{slug}/generations/{held + 1}/proposed.yml",
           "base": base}
    if after is None:
        doc.update(changes=[], classification={
            "result": "not-run", "reason": "the proposal does not resolve", "scan": "none",
            "first_point": None}, assessment={
            "approach": {"before": None, "after": None}, "result": "not-run", "changes": [],
            "refused": None}, invalidates=[], next=NEXT_STEP)
        return doc
    reasons += _reasons(policy_lint.lint_loaded(after.details["loaded"]))
    doc["verdict"] = "refused" if reasons else "accepted"
    shown, modes = assessment_effect(manifest, current, after)
    doc["changes"] = _fill_modes(field_changes(stored["resolved"], after.resolved), modes)
    doc["classification"] = classification_of(after.details)
    doc["assessment"] = shown
    doc["invalidates"] = [{"id": rid, "kind": _kind(rid), "reason": why}
                          for rid, why in sorted(invalidated.items())]
    doc["next"] = NEXT_STEP
    return doc
