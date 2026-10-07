# compass_pkg.locks - what a lock protects, and who may lift one
"""Locks, unlocks and conformance (ADR-039).

A lock (`locked: true` or `locked: hard` on an entry) lets a lower layer
tighten the entry and refuses a change that loosens it or cannot be compared.
The comparison is the classifier's, over the one field table
(`catalogue_spec.OBLIGATION_FIELDS`), projected to the footprint of the
locked entries: the facts that mention them. A waiver is never an input, so
no waiver excuses a lock refusal. A project lifts a `true` lock with
`unlock: true` and a waiver that its `owner` approved; no unlock lifts a hard
lock. A project that unlocks a framework entry is reported non-conformant by
`compass check`, `compass issue receipt` and `compass approach summary`.

This module reads layer documents and configurations that its caller hands it,
and reads no preset. The shipped lock set is written once, in the preset's
`locked` markers. An unlock's waiver must pass `waivers.check` (its shape, a date
not in the future, an approver with authority); the owner-only rule is this
module's and applies on top. Nothing here prints; the commands print
what `conformance_lines` returns.
"""
# DEPENDENCY: standard library (copy, datetime, itertools, json, os, textwrap, dataclasses);
# compass_pkg.catalogue_spec, compass_pkg.atomic_io (the strict loader),
# compass_pkg.classify (the grid, `scan` and its per-point callback, the
# comparison rules, `where`, `plain` and `Refused`; only classify may import the
# evaluator, so this module reaches what it owes through `Scan.obligations`),
# compass_pkg.merge, compass_pkg.waivers (check), compass_pkg.layers (Layer),
# compass_pkg.legacy_views (the preset's lock summary, read lazily) and
# compass_pkg.core (CompassError). Imported by compass_pkg.check_cmd,
# compass_pkg.receipt and compass_pkg.routing, which print its report.
from __future__ import annotations

import copy
import datetime
import itertools
import json
import os
import textwrap
from collections import namedtuple
from dataclasses import dataclass, replace

from compass_pkg import catalogue_spec as spec
from compass_pkg import classify, merge, waivers
from compass_pkg.atomic_io import load_yaml_strict
from compass_pkg.core import CompassError
from compass_pkg.layers import Layer

Lock = namedtuple("Lock", "level layer")
Unlock = namedtuple("Unlock", "entry layer ok reason")
Conformance = namedtuple("Conformance", "status unlocked refused")


LEVELS = (True, "hard")


def _level(value):
    """A lock level, or None for any other value. `1` is not a level, though
    `1 == True`."""
    if value is True or value == "hard":
        return value
    return None


def declared_locks(doc):
    """`{"catalogue.id": True | "hard"}` for the locks one layer document
    declares: an entry's `locked`, or the `locked` inside its `set:`. The
    merge keeps `locked` only as a field of checks and gates, so a stage, an
    approach or a rule set loses it there. The locks are read from the
    layer's own document for that reason."""
    found = {}
    for catalogue in spec.CATALOGUES:
        entries = doc.get(catalogue)
        for entry_id, entry in (entries.items() if isinstance(entries, dict) else ()):
            if not isinstance(entry, dict):
                continue
            level = _level(entry.get("locked"))
            changes = entry.get("set")
            if level is None and isinstance(changes, dict):
                level = _level(changes.get("locked"))
            if level is not None:
                found[f"{catalogue}.{entry_id}"] = level
    return found


def _unlock_reason(entry, body, layer, owner, locks):
    """Why an unlock is refused, or None when it stands."""
    if layer.kind != "project":
        return (f"only the project layer can unlock; a {layer.kind} layer "
                f"cannot (ADR-039)")
    if not isinstance(owner, str) or not owner:
        return "the project names no owner, and only the owner approves an unlock"
    waiver = body.get("waiver")
    if not isinstance(waiver, dict) or not waiver:
        return "an unlock needs a waiver on the entry"
    if not str(waiver.get("reason") or "").strip():
        return "the waiver gives no reason"
    approved = waiver.get("approved_by")
    if approved != owner:
        return (f"the waiver is approved by {approved if approved else 'no one'}, "
                f"and only the owner {owner} approves an unlock")
    catalogue, _, entry_id = entry.partition(".")
    record = waivers.Waiver(f"project:{entry}", "project", catalogue, entry_id,
                            "set", (), waiver)
    faults = [f for f in waivers.check(record, today=datetime.date.today(),
                                       project=layer.doc, parent=None)
              if f.level == "error"]
    if faults:
        return f"the waiver fails the waiver check: {faults[0].message}"
    if locks is not None:
        held = locks.get(entry)
        if held is None:
            return "the entry is not locked, so there is nothing to unlock"
        if _level(getattr(held, "level", held)) == "hard":
            return "a hard lock cannot be unlocked by anyone"
    return None


def unlock_findings(layer, locks=None):
    """One `Unlock(entry, layer, ok, reason)` for each entry of `layer` that
    carries `unlock: true`. `locks` is the lock set the layer sits under;
    without it the findings cannot tell a hard lock or an entry that is not
    locked, so those are not refused."""
    out = []
    doc = layer.doc
    for catalogue in spec.CATALOGUES:
        entries = doc.get(catalogue)
        for entry_id, body in (entries.items() if isinstance(entries, dict) else ()):
            if not isinstance(body, dict) or body.get("unlock") is not True:
                continue
            entry = f"{catalogue}.{entry_id}"
            reason = _unlock_reason(entry, body, layer, doc.get("owner"), locks)
            out.append(Unlock(entry, layer.name, reason is None, reason or ""))
    return out


def _lift(held, layer):
    """The lock set after the entries `layer` validly unlocks."""
    held = dict(held)
    for found in unlock_findings(layer, held):
        if found.ok:
            held.pop(found.entry, None)
    return held


def _declare(held, layer):
    """The lock set with the locks `layer` declares. The higher level stays."""
    held = dict(held)
    for entry, level in declared_locks(layer.doc).items():
        old = held.get(entry)
        if old is None or LEVELS.index(level) > LEVELS.index(old.level):
            held[entry] = Lock(level, layer.name)
    return held


def lock_set(layers):
    """`{"catalogue.id": Lock(level, layer)}` for the layers, root first. Each
    layer lifts the entries it validly unlocks, then adds its own locks, so
    an unlock lifts what the layers above declared and never what the same
    layer declares."""
    held = {}
    for layer in layers:
        held = _lift(held, layer)
        if layer.kind != "issue":     # an issue layer cannot lock (ADR-035)
            held = _declare(held, layer)
    return held


# What a locked entry covers, written as the keys of the shared field table
# (`catalogue_spec.OBLIGATION_FIELDS`). `existence` and the `rules.<set>.<id>`
# keys are the two facts the table has no key for.
CHECK_FACTS = tuple(f for f in spec.OBLIGATION_FIELDS if f.startswith("checks."))
LISTS_A_CHECK_SITS_IN = ("stages.entry", "stages.exit", "gates.checks")
GATE_FACTS = ("gates.checks", "gates.accepts", "gates.stage", "approaches.gates")
STAGE_FACTS = ("existence", "stages.order", "stages.entry", "stages.exit",
               "approaches.stages")
APPROACH_FACTS = ("existence", "approaches.ships")

# The rule effects that an obligation fact carries, and the fact.
RULE_EFFECT_FACTS = {"gate": "approaches.gates",
                     "require_artifact": "evaluation.required_artifacts",
                     "block_phase": "evaluation.blocked_stages",
                     "require_skill": "evaluation.required_skills"}


def _split(entry):
    catalogue, _, entry_id = entry.partition(".")
    return catalogue, entry_id


def _artifact_id(value):
    value = str(value)
    return value[:-3] if value.endswith(".md") else value


class Footprint:
    """What the locks protect in one configuration: the locked entries that
    exist in it, grouped by catalogue, and the effects of the locked rule
    sets. `absent` lists a lock whose entry the configuration lacks, so it
    protects nothing yet."""

    def __init__(self):
        self.checks = set()
        self.gates = set()
        self.stages = set()
        self.approaches = set()
        self.rules = {}
        self.rule_gates = set()
        self.rule_artifacts = set()
        self.rule_blocks = set()
        self.rule_skills = set()
        self.rule_identity = {}
        self.absent = ()
        self.levels = {}
        self.owners = {}
        self.rule_defs = {}

    def rule_values(self, field):
        """The values a locked rule set adds to one fact, and the locked gates
        for the gate set."""
        if field == "approaches.gates":
            return self.rule_gates | self.gates
        return {"evaluation.required_artifacts": self.rule_artifacts,
                "evaluation.blocked_stages": self.rule_blocks,
                "evaluation.required_skills": self.rule_skills}.get(field, set())

    def facts(self, entry):
        """The keys of the field table (and `existence`) that `entry` covers,
        or an empty tuple for an entry that is not locked here."""
        catalogue, entry_id = _split(entry)
        if catalogue == "checks" and entry_id in self.checks:
            return CHECK_FACTS + LISTS_A_CHECK_SITS_IN
        if catalogue == "gates" and entry_id in self.gates:
            return GATE_FACTS
        if catalogue == "stages" and entry_id in self.stages:
            return STAGE_FACTS
        if catalogue == "approaches" and entry_id in self.approaches:
            return APPROACH_FACTS
        if catalogue == "rules" and entry_id in self.rules:
            found = sorted({RULE_EFFECT_FACTS[effect] for effect in self.rules[entry_id]
                            if effect in RULE_EFFECT_FACTS})
            found += [f"rules.{entry_id}.{rule}" for (name, rule) in sorted(
                self.rule_identity) if name == entry_id]
            found += [f"rules.{entry_id}.kind", f"rules.{entry_id}.hit"]
            found += [f"rules.{entry_id}.{rule}" for rule in self.rule_defs[entry_id]["ids"]
                      if (entry_id, rule) not in self.rule_identity]
            return tuple(found)
        return ()


def footprint(locks, config):
    """The `Footprint` of `locks` in `config`, the configuration the locks
    were declared in. `locks` maps `catalogue.id` to a `Lock` or a bare
    level."""
    out = Footprint()
    absent = []
    groups = {"checks": out.checks, "gates": out.gates, "stages": out.stages,
              "approaches": out.approaches}
    for entry in sorted(locks):
        catalogue, entry_id = _split(entry)
        held = locks[entry]
        out.levels[entry] = getattr(held, "level", held)
        if entry_id not in (config.get(catalogue) or {}):
            absent.append(entry)
        elif catalogue in groups:
            groups[catalogue].add(entry_id)
        elif catalogue == "rules":
            _rule_footprint(out, entry_id, config["rules"][entry_id])
    out.absent = tuple(absent)
    return out


def _rule_footprint(out, set_id, rule_set):
    """Record each effect of the rules of a locked rule set: one an obligation
    fact carries goes to that fact's set, and the rest are protected as the
    rule's own `when` and `then`."""
    effects = set()
    out.rule_defs[set_id] = {
        "kind": (rule_set or {}).get("kind"), "hit": copy.deepcopy((rule_set or {}).get("hit")),
        "ids": tuple(((rule_set or {}).get("rules") or {}))}
    for rule_id, rule in ((rule_set or {}).get("rules") or {}).items():
        then = {k: v for k, v in (rule.get("then") or {}).items() if k != "until"}
        unmapped = {k: v for k, v in then.items() if k not in RULE_EFFECT_FACTS}
        for effect, value in then.items():
            if effect == "gate":
                out.rule_gates.add(value)
            elif effect == "require_artifact":
                value = _artifact_id(value)
                out.rule_artifacts.add(value)
            elif effect == "block_phase":
                out.rule_blocks.add(value)
            elif effect == "require_skill":
                out.rule_skills.add(value)
            if effect in RULE_EFFECT_FACTS:
                effects.add(effect)
                out.owners.setdefault((RULE_EFFECT_FACTS[effect], value),
                                      set()).add(set_id)
        if unmapped:
            out.rule_identity[(set_id, rule_id)] = {
                "when": copy.deepcopy(rule.get("when")), "then": unmapped}
    out.rules[set_id] = effects


LOOSENS = ("looser", "incomparable")


@dataclass(frozen=True)
class Refusal:
    """One thing a lock refuses. `field` is a key of the field table (or
    `existence`), `key` the entry the classifier keyed the change by, `outcome`
    is `looser` or `incomparable`, and `where` is the first assessment the
    change shows at (empty for a change no assessment is needed for)."""
    entry: str
    level: object
    field: str
    key: object
    outcome: str
    parent: object
    child: object
    where: str
    message: str
    layer: str = ""


class Enforcement:
    def __init__(self):
        self.refusals = ()
        self.evaluated = 0

    @property
    def ok(self):
        return not self.refusals


def _word(level):
    return "hard" if level == "hard" else "true"


def _refusal(fp, locks, entry, field, key, outcome, parent, child, where=""):
    level = fp.levels.get(entry)
    layer = getattr(locks.get(entry), "layer", None)
    verb = ("loosens" if outcome == "looser" else "cannot be compared with")
    held = _word(level) + (f", by {layer}" if layer else "")
    shown = f" ({key})" if key is not None else ""
    before, after = classify.plain(parent), classify.plain(child)
    text = (f"{entry} is locked ({held}): {field}{shown} {verb} the locked value - "
            f"{json.dumps(before)} before, {json.dumps(after)} after"
            + (f", at {where}" if where else ""))
    return Refusal(entry, level, field, key, outcome, before, after, where, text)


# The facts a locked rule set can add a value to.
RULE_FACT_VALUES = tuple(RULE_EFFECT_FACTS.values())


def _check_of(fp, field, key):
    """The locked check a change on a check field is about. Every check field
    is keyed by the check's id, which may hold a dot, so it matches exactly. A
    parameter's key is `check.parameter`, and only that field matches by the
    check id and a dot."""
    if key in fp.checks:
        return key
    if field == "checks.params":
        for check in sorted(fp.checks, key=len, reverse=True):
            if isinstance(key, str) and key.startswith(check + "."):
                return check
    return None


def _members(ids, p, c, ctx):
    """For each id, the outcome of its membership of a list that changed:
    present before and after is equal, gone is `looser`, new is `tighter`."""
    p, c = set(p or ()), set(c or ())
    for item in sorted(ids):
        if item in p or item in c:
            yield item, classify.RULES["obligation-set"](
                None, None, {item} & p, {item} & c, ctx)


def _footprint_changes(fp, change, ctx):
    """`(entry, field, key, outcome, parent, child)` for each part of one
    change of the classifier that a lock covers."""
    field, key, p, c = change.field, change.key, change.parent, change.child
    if field.startswith("checks."):
        check = _check_of(fp, field, key)
        if check:
            yield (f"checks.{check}", field, key, change.outcome, p, c)
    elif field in ("stages.entry", "stages.exit", "gates.checks"):
        catalogue = "stages" if field.startswith("stages") else "gates"
        held = fp.stages if catalogue == "stages" else fp.gates
        if key in held:
            yield (f"{catalogue}.{key}", field, key, change.outcome, p, c)
        for check, outcome in _members(fp.checks, p, c, ctx):
            yield (f"checks.{check}", field, key, outcome, {check} & set(p or ()),
                   {check} & set(c or ()))
    elif field == "gates.accepts":
        if key in fp.gates:
            yield (f"gates.{key}", field, key, change.outcome, p, c)
    elif field == "approaches.stages":
        if key in fp.stages and p is not None and c is None:
            yield (f"stages.{key}", field, key, "looser", p, c)
    elif field in RULE_FACT_VALUES:
        held = fp.rule_values(field)
        for item, outcome in _members(held, p, c, ctx):
            yield from _fact_entries(fp, field, item, key, outcome, p, c)


def _fact_entries(fp, field, item, key, outcome, p, c):
    """The locked entries one membership change is about: the gate itself when
    it is locked, and each locked rule set that adds the value."""
    p, c = {item} & set(p or ()), {item} & set(c or ())
    if field == "approaches.gates" and item in fp.gates:
        yield (f"gates.{item}", field, key, outcome, p, c)
    for set_id in sorted(fp.owners.get((field, item), ())):
        yield (f"rules.{set_id}", field, key, outcome, p, c)


def _direct(fp, locks, before, after):
    """Refusals that need no assessment: what a lock protects that no
    evaluation changes."""
    found = []

    def refuse(*args):
        found.append(_refusal(fp, locks, *args))

    for entry in sorted(locks):
        catalogue, entry_id = _split(entry)
        if entry not in fp.absent and entry_id not in (after.get(catalogue) or {}):
            refuse(entry, "existence", None, "looser", "present", "absent")
    for gate in sorted(fp.gates & set(after.get("gates") or {})):
        was, now = before["gates"][gate].get("stage"), after["gates"][gate].get("stage")
        if was != now:
            refuse(f"gates.{gate}", "gates.stage", gate, "incomparable", was, now)
    for approach in sorted(fp.approaches & set(after.get("approaches") or {})):
        was = before["approaches"][approach].get("ships")
        now = after["approaches"][approach].get("ships")
        if was != now:
            refuse(f"approaches.{approach}", "approaches.ships", approach,
                   "incomparable", was, now)
    for (set_id, rule_id), held in sorted(fp.rule_identity.items()):
        rule = (((after.get("rules") or {}).get(set_id) or {}).get("rules") or {}
                ).get(rule_id)
        now = None if rule is None else {
            "when": rule.get("when"),
            "then": {k: v for k, v in (rule.get("then") or {}).items()
                     if k not in RULE_EFFECT_FACTS and k != "until"}}
        if now != held:
            refuse(f"rules.{set_id}", f"rules.{set_id}.{rule_id}", rule_id,
                   "incomparable", held, now)
    for set_id, held in sorted(fp.rule_defs.items()):
        now = (after.get("rules") or {}).get(set_id)
        if now is None:
            continue
        for part in ("kind", "hit"):
            if now.get(part) != held[part]:
                refuse(f"rules.{set_id}", f"rules.{set_id}.{part}", part, "incomparable",
                       held[part], now.get(part))
        for rule_id in held["ids"]:
            if rule_id not in (now.get("rules") or {}):
                refuse(f"rules.{set_id}", f"rules.{set_id}.{rule_id}", rule_id,
                       "incomparable", "present", "removed")
    found += _order_refusals(fp, locks, before, after)
    found += _label_refusals(fp, locks, before, after)
    return found


def _nameable(config, label):
    """Whether an assessment can name `label`: the label list is open, or the
    label is one of its common values."""
    dimension = (config.get("dimensions") or {}).get("labels") or {}
    return bool(dimension.get("open") or label in (dimension.get("common") or ()))


def _label_refusals(fp, locks, before, after):
    """A locked gate or check that applies only when a label is named stops
    applying if the label can no longer be named. The evaluator does not read
    the label list, so the classifier sees no change, and a closed list or a
    dropped common label would otherwise switch the entry off."""
    found = []
    for catalogue, ids in (("gates", fp.gates), ("checks", fp.checks)):
        for entry_id in sorted(ids):
            when = (before[catalogue][entry_id] or {}).get("when")
            named = sorted({label for atom in classify.atoms_of(when)
                            if atom[0] == "labels_any" for label in atom[1]})
            for label in named:
                if _nameable(before, label) and not _nameable(after, label):
                    found.append(_refusal(
                        fp, locks, f"{catalogue}.{entry_id}", "dimensions.labels", label,
                        "looser", "can be named", "cannot be named"))
    return found


RELATION = {-1: "before", 0: "level with", 1: "after"}


def _sign(number):
    return (number > 0) - (number < 0)


def _order_refusals(fp, locks, before, after):
    """A locked stage keeps its place against every stage the locking layer
    knew, and a stage that was strictly first stays first."""
    orders = {}
    for name, config in (("before", before), ("after", after)):
        orders[name] = {stage: (body or {}).get("order", 0)
                        for stage, body in (config.get("stages") or {}).items()}
    b, a = orders["before"], orders["after"]
    found = []
    lowest = [stage for stage in b if b[stage] == min(b.values())]
    for stage in sorted(fp.stages & set(a)):
        entry = f"stages.{stage}"
        for other in sorted(set(b) & set(a) - {stage}):
            was, now = _sign(b[stage] - b[other]), _sign(a[stage] - a[other])
            if was != now:
                found.append(_refusal(
                    fp, locks, entry, "stages.order", other, "incomparable",
                    f"{stage} {RELATION[was]} {other}", f"{stage} {RELATION[now]} {other}"))
        if lowest == [stage]:
            for other in sorted(set(a) - set(b)):
                if a[other] <= a[stage]:
                    found.append(_refusal(
                        fp, locks, entry, "stages.order", other, "incomparable",
                        f"{stage} first",
                        f"{other} {RELATION[_sign(a[other] - a[stage])]} {stage}"))
    return found


# The rule sets whose conditions no fact of a footprint carries: an advisory
# strategy or suggestion, a bias and a loop ceiling change what the evaluator
# reports, and no lock covers any of it. A label that only they read cannot
# change what a lock refuses, so the footprint scan does not count it.
IRRELEVANT_RULE_KINDS = ("advisory", "biases", "ceilings")

# `footprint` classifies only the facts, and counts only the labels, a locked
# entry can read. `full` is the reference: every label in the layer, so a test
# can compare the two. Nothing else is a scan.
SCANS = ("footprint", "full")


def _check_scan(scan):
    if scan not in SCANS:
        raise CompassError(f"scan is '{scan}'; it must be one of {', '.join(SCANS)}")


def _lists_with_a_locked_entry(fp, configs):
    """The checks a locked stage or gate lists, and the gates that list a locked
    check, in either configuration. A check in the first set fills a locked
    list, and a gate in the second decides when a locked check is listed."""
    listed, holders = set(), set()

    def names(value):
        return {n for n in (value if isinstance(value, (list, tuple)) else ())
                if isinstance(n, str)}

    for config in configs:
        for stage in fp.stages:
            body = (config.get("stages") or {}).get(stage) or {}
            listed |= names(body.get("entry")) | names(body.get("exit"))
        for gate_id, gate in (config.get("gates") or {}).items():
            checks = names((gate or {}).get("checks"))
            if gate_id in fp.gates:
                listed |= checks
            if checks & fp.checks:
                holders.add(gate_id)
    return listed, holders


def _label_reader(fp, before, after):
    """Whether the labels a condition names can reach a fact a lock protects,
    for `classify.collect_atoms`. `path` leads to the entry that holds the
    condition. A label is dropped only where the entry is positively one no
    footprint fact reads:

    - a rule in an advisory, bias or ceiling rule set;
    - a check that is not locked and that no locked stage or gate lists, in
      either configuration, so no lock compares it;
    - a gate that is not locked, adds nothing a locked rule set adds, and
      holds no locked check.

    Any other entry, and any path this does not recognise, keeps its labels, so
    an unrecognised shape makes the scan larger and never smaller."""
    listed, holders = _lists_with_a_locked_entry(fp, (before, after))

    def reads(path):
        if len(path) < 2:
            return True
        catalogue, entry_id = path[0], path[1]
        if catalogue == "rules":
            kinds = {((c.get("rules") or {}).get(entry_id) or {}).get("kind")
                     for c in (before, after) if entry_id in (c.get("rules") or {})}
            return not kinds or not kinds <= set(IRRELEVANT_RULE_KINDS)
        if catalogue == "checks":
            return entry_id in fp.checks or entry_id in listed
        if catalogue == "gates":
            return entry_id in fp.gates or entry_id in fp.rule_gates or entry_id in holders
        return True

    return reads


def _unprovable(field, reason):
    """The refusal for a change the grid cannot be run over. No lock can be
    shown to hold, so the layer is refused as one that cannot be compared."""
    return Refusal("configuration", None, field, None, "incomparable", None, None, "",
                   f"no lock can be shown to hold: {reason}")


def _scan(fp, locks, before, after, kwargs, early_exit, out, scan="footprint"):
    """Evaluate both configurations at every point of the classifier's grid and
    collect what the locks refuse there, the first point of each. The grid's
    labels are those a locked entry can read (`scan="footprint"`) or every
    label in the layer (`scan="full"`)."""
    reader = _label_reader(fp, before, after) if scan == "footprint" else None
    atoms = classify.collect_atoms(before, after, None, kwargs["child_issue"],
                                   label_site=reader)
    grid = classify.build_grid(before, after, atoms, False, None, kwargs["child_issue"])
    if len(grid.labels) > spec.LABEL_CAP:
        hard = any(level == "hard" for level in fp.levels.values())
        remedy = ("a hard lock: nothing else lifts it" if hard else
                  "or unlock the locked entries with a waiver the owner approved")
        counted = ("the labels a locked entry can read. Labels that only advisory, bias or "
                   "ceiling rules read, or that only checks and gates no lock covers read, "
                   "are not counted" if scan == "footprint"
                   else "the labels across the whole layer")
        out.refusals += (_unprovable(
            "grid", f"more than eight named labels: {len(grid.labels)} "
            f"({', '.join(grid.labels)}). The scan counts only {counted}, and does not "
            f"sample, so every change is refused until the layer is narrowed. Name no "
            f"more than eight labels"
            + (f" - this is {remedy}" if hard else f", {remedy}")),)
        return
    try:
        _evaluate_grid(fp, locks, before, after, kwargs, early_exit, out, grid)
    except CompassError as exc:
        # A configuration the evaluator rejects cannot be compared, so the
        # lock cannot be shown to hold. The fault itself is lint's to report.
        out.refusals += (_unprovable("evaluation", f"the evaluator cannot read the "
                                     f"configuration: {exc}. An unlock cannot help; fix the configuration"),)


def _ended_here(fp, change, point, run):
    """The locked entries in force at a point that only the parent can reach.
    A child that no longer accepts an assessment (a vocabulary value dropped
    or renamed, a closed label list) ends every obligation the parent owed
    there, and the classifier reports it without evaluating the obligations.
    A lock refuses what cannot be compared, so the parent is evaluated here and
    each locked gate or check in force at the point is a refusal."""
    gone = ((change.field == "dimensions.values" and change.parent and not change.child)
            or (change.field == "evaluation.refused" and change.parent is None))
    if not gone:
        return
    owed = run.obligations(0, point.assessment)
    if isinstance(owed, classify.Refused):
        return
    listed = set()
    for ids in (*owed.entry.values(), *owed.exit.values(), *owed.gate_checks.values()):
        listed.update(ids)
    after = ("this assessment can no longer be made" if change.field == "dimensions.values"
             else f"the assessment is refused: {change.child}")
    for gate in sorted(fp.gates & set(owed.gate_set)):
        yield (f"gates.{gate}", change.field, change.key, "looser", "in force", after)
    for check in sorted(fp.checks & listed):
        yield (f"checks.{check}", change.field, change.key, "looser", "in force", after)


def _evaluate_grid(fp, locks, before, after, kwargs, early_exit, out, grid):
    seen = {(r.entry, r.field, r.key) for r in out.refusals}

    def visit(point, run):
        out.evaluated += 1
        for change in point.changes:
            for entry, field, key, outcome, p, c in itertools.chain(
                    _footprint_changes(fp, change, run.ctx),
                    _ended_here(fp, change, point, run)):
                if outcome in LOOSENS and (entry, field, key) not in seen:
                    seen.add((entry, field, key))
                    out.refusals += (_refusal(
                        fp, locks, entry, field, key, outcome, p, c,
                        classify.where(point.assessment)),)
        return early_exit and bool(out.refusals)

    classify.scan(before, after, grid, on_point=visit, **kwargs)


def enforce(locks, before, after, *, before_capabilities=(), after_capabilities=(),
            after_issue=None, directions=None, tighter=None, cache=None,
            early_exit=True, scan="footprint"):
    """What the locks refuse in the change from `before`, the configuration
    they were declared in, to `after`. `locks` maps `catalogue.id` to a `Lock`
    or a level. A change that is equal or tighter is allowed; one that is
    looser or cannot be compared is refused. A waiver is not an input: no
    waiver excuses a lock. With `early_exit` the scan stops at the first
    refusal. `scan` is `footprint` (the labels a locked entry can read) or
    `full` (every label in the layer, the reference the footprint scan is
    tested against)."""
    _check_scan(scan)
    out = Enforcement()
    if not locks or (before == after and tuple(before_capabilities)
                     == tuple(after_capabilities) and after_issue is None):
        return out
    fp = footprint(locks, before)
    out.refusals = tuple(_direct(fp, locks, before, after))
    if out.refusals and early_exit:
        return out
    if fp.checks or fp.gates or fp.stages or fp.rules:
        kwargs = dict(parent_capabilities=before_capabilities,
                      child_capabilities=after_capabilities, parent_issue=None,
                      child_issue=after_issue, directions=directions,
                      tighter=tighter, cache=cache)
        _scan(fp, locks, before, after, kwargs, early_exit, out, scan)
    return out


def _capabilities(layers):
    """The capability switches that are on after `layers`; a later layer
    overrides an earlier one."""
    state = {}
    for layer in layers:
        state.update({k: v for k, v in (layer.doc.get("capabilities") or {}).items()})
    return tuple(sorted(k for k, v in state.items() if v is True))


def _without_unlock(doc):
    """A layer document with its `unlock` keys removed. Only the project layer
    may carry them, and the merge would stop at another layer's before the
    locks could name the refusal."""
    out = dict(doc)
    for catalogue in spec.CATALOGUES:
        entries = doc.get(catalogue)
        if isinstance(entries, dict):
            out[catalogue] = {i: ({k: v for k, v in e.items() if k != "unlock"}
                                  if isinstance(e, dict) else e)
                              for i, e in entries.items()}
    return out


def _unlock_refusal(found, held):
    lock = held.get(found.entry)
    return Refusal(found.entry, getattr(lock, "level", None), "unlock", None, "refused",
                   None, None, "",
                   f"{found.layer} layer: {found.entry}: unlock refused - {found.reason}",
                   found.layer)


def enforce_chain(layers, *, directions=None, tighter=None, cache=None,
                  early_exit=True, scan="footprint"):
    """What the locks refuse across a chain of layers, root first. Each layer
    is merged on the one before it, the unlocks it validly carries lift the
    locks declared above it, and what is left is enforced on its change. An
    unlock that is refused is a refusal too. The first layer has nothing above
    it, so nothing binds it. `scan` is as for `enforce`."""
    _check_scan(scan)
    out = Enforcement()
    held, config, capabilities, seen = {}, {}, (), []
    for index, layer in enumerate(layers):
        seen.append(layer)
        refusals = tuple(_unlock_refusal(f, held) for f in unlock_findings(layer, held)
                         if not f.ok)
        doc = layer.doc if layer.kind == "project" else _without_unlock(layer.doc)
        after, _ = merge.apply(config, doc, layer.kind, layer.name)
        held = _lift(held, layer)
        after_capabilities = _capabilities(seen)
        if index:
            result = enforce(held, config, after, before_capabilities=capabilities,
                             after_capabilities=after_capabilities,
                             after_issue=layer.doc if layer.kind == "issue" else None,
                             directions=directions, tighter=tighter, cache=cache,
                             early_exit=early_exit, scan=scan)
            out.evaluated += result.evaluated
            refusals += tuple(
                replace(r, layer=layer.name, message=f"{layer.name} layer: {r.message}")
                for r in result.refusals)
        out.refusals += refusals
        if refusals and early_exit:
            return out
        if layer.kind != "issue":
            held = _declare(held, layer)
        config, capabilities = after, after_capabilities
    return out


def conformance(layer, locks=None):
    """`Conformance(status, unlocked, refused)` for a project layer. It is
    `non-conformant` when the layer validly unlocks at least one entry.
    `unlocked` is the sorted entries, and `refused` is `(entry, reason)` for
    each unlock that does not stand, which unlocks nothing and does not make
    the project non-conformant (lint refuses it). Without `locks` a hard lock
    is not known, so an unlock of one reads as an unlock: that errs towards
    reporting."""
    found = unlock_findings(layer, locks)
    unlocked = tuple(sorted(f.entry for f in found if f.ok))
    refused = tuple(sorted((f.entry, f.reason) for f in found if not f.ok))
    return Conformance("non-conformant" if unlocked else "conformant", unlocked, refused)


def shipped_locks():
    """The lock set the shipped default declares, as `{entry: Lock}`, from the
    summary in its `preset.yml`, or None when that cannot be read. The summary
    is read through `legacy_views`, the one reader of the preset, and no lock
    id is written in this module."""
    try:
        from compass_pkg import legacy_views
        from compass_pkg.core import FRAMEWORK_ROOT
        summary = legacy_views.preset_locks(FRAMEWORK_ROOT)
    except (ImportError, OSError, ValueError, AttributeError):
        return None
    held = {entry: Lock(True, "default") for entry in summary["locked"]}
    held.update({entry: Lock("hard", "default") for entry in summary["hard"]})
    return held


def project_conformance(root, locks=None):
    """`Conformance` for the project file `<root>/compass.yml`, or None when
    there is no such file or it is not Compass's (it has no `schema:`).
    `locks` is the lock set the project sits under; with it, an unlock of a
    hard lock or of an entry that is not locked is refused, not reported as an
    unlock. A file that cannot be read raises `ValueError` or `OSError`,
    naming the file."""
    path = os.path.join(os.fspath(root), "compass.yml")
    if not os.path.isfile(path):
        return None
    doc = load_yaml_strict(path)
    if not isinstance(doc, dict) or "schema" not in doc:
        return None
    return conformance(Layer("project", "project", doc, ""), locks)


def conformance_lines(root, width=100):
    """The lines a command prints about conformance, for the project at
    `root`: none for a project with no `compass.yml`, one that is not
    Compass's or one that unlocks nothing. It never raises, so a command that
    calls it cannot fail because of it. A file that cannot be read gets one
    line that says so, because a check that stops without a word is the
    failure the safety contract rules out."""
    try:
        found = project_conformance(root, shipped_locks())
    except (ValueError, OSError) as exc:
        return textwrap.wrap(f"Conformance: not checked - compass.yml cannot be read: {exc}",
                             width=width, subsequent_indent="  ", break_long_words=False,
                             break_on_hyphens=False)
    return conformance_text(found, width) if found else []


def conformance_text(found, width=100):
    """The lines a command prints for a `Conformance`: one for the status when
    it is non-conformant, and one for each refused unlock. A conformant project
    with nothing refused has none, so a project that departs from nothing sees
    nothing. Each line wraps inside `width`, and a continuation line is
    indented by two spaces."""
    lines = []
    if found.unlocked:
        lines.append("Conformance: non-conformant - this project unlocks framework "
                     "entries: " + ", ".join(found.unlocked))
    lines += [f"Unlock refused for {entry}: {reason}" for entry, reason in found.refused]
    out = []
    for line in lines:
        out += textwrap.wrap(line, width=width, subsequent_indent="  ",
                             break_long_words=False, break_on_hyphens=False)
    return out
