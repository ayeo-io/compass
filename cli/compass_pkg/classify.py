# compass_pkg.classify - compare two configurations by what each owes
"""Compare two resolved configurations by the obligations each owes (ADR-037).

The grid is every closed assessment crossed with every subset of the labels a
predicate names. Values no predicate can tell apart are one class, so the grid
is exact and smaller than the raw one. At each point `obligations` runs under
both configurations and the facts are compared by the kind the field table
(`catalogue_spec.OBLIGATION_FIELDS`) gives each field.

`Classification.to_json()` is the one place the result becomes a document.
The later `policy` commands print `json.dumps(c.to_json(), indent=2)` and
build their text from the same dictionary.
"""
# DEPENDENCY: standard library (copy, dataclasses, hashlib, itertools, json);
# compass_pkg.catalogue_spec, compass_pkg.core (CompassError,
# reading_matches, the `when` key map), compass_pkg.obligations (the obligations function,
# Refused, the dimension orders) and, for a check parameter's direction,
# compass_pkg.check_registry. Nothing imports this module yet.
from __future__ import annotations

import hashlib
import itertools
import json
from dataclasses import dataclass, field

from compass_pkg import obligations
from compass_pkg.catalogue_spec import (ARTIFACT_DEPTHS, CEILING_DIRECTIONS, LABEL_CAP,
                                        OBLIGATION_FIELDS, ON_SKIPPED, SEVERITIES)
from compass_pkg.catalogue_spec import TIGHTER as DIRECTIONS
from compass_pkg.core import WHEN_KEY_MAP, CompassError, reading_matches
from compass_pkg.obligations import (Refused, assessment_vocabulary,
                                     dimension_orders)

JSON_SCHEMA_VERSION = 1

# Keys whose value is a condition on the assessment.
WHEN_KEYS = ("when", "blocking_when", "applies_when")
CLOSED = ("enum", "ordered-enum")


# --- atoms ---------------------------------------------------------------------

def atoms_of(when):
    """The tests one condition makes of the assessment, as the evaluator reads
    it: `("in", dimension, values)`, `("at_least", dimension, threshold)` and
    `("labels_any", values)`, in the order they are written."""
    out = []
    if not isinstance(when, dict):
        return out
    for key, val in when.items():
        key = WHEN_KEY_MAP.get(key, key)
        if key == "any_of":
            for clause in (val if isinstance(val, list) else [val]):
                out.extend(atoms_of(clause))
        elif isinstance(val, dict) and "at_least" in val:
            out.append(("at_least", key, val["at_least"]))
        elif key == "labels_any":
            out.append(("labels_any", tuple(val if isinstance(val, list) else [val])))
        else:
            out.append(("in", key, tuple(val if isinstance(val, list) else [val])))
    return out


def collect_atoms(*documents):
    """The atoms of every condition anywhere in the given configurations and
    issue layers, without repeats, in document order. The walk does not know
    which catalogue a condition sits in, so one added later is still found."""
    found = []

    def add(atoms):
        for atom in atoms:
            if atom not in found:
                found.append(atom)

    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key in WHEN_KEYS and isinstance(value, dict):
                    add(atoms_of(value))
                else:
                    walk(value)
        elif isinstance(node, (list, tuple)):
            for item in node:
                walk(item)

    for document in documents:
        walk(document)
    return found


# --- the grid ------------------------------------------------------------------

@dataclass(frozen=True)
class ValueClass:
    """Values of one dimension that every predicate answers alike. `kind` is
    `both` when each configuration accepts them, and `one-side` when only one
    does and a predicate reads them, so the point cannot be evaluated."""
    values: tuple
    kind: str


@dataclass
class Grid:
    dimensions: tuple = ()          # ((name, (ValueClass, ...)), ...)
    labels: tuple = ()
    domain_sizes: tuple = ()        # the union domain of each dimension
    stopped: bool = False           # the cap stopped the run before a grid
    evaluated: int = 0

    @property
    def closed_points(self):
        return 0 if self.stopped else _product(len(c) for _, c in self.dimensions)

    @property
    def points(self):
        return self.closed_points * 2 ** len(self.labels)

    @property
    def raw_points(self):
        return 0 if self.stopped else _product(self.domain_sizes) * 2 ** len(self.labels)

    @property
    def label_count(self):
        return len(self.labels)

    def label_subsets(self):
        """Every subset of the named labels, by size and then name."""
        return [combo for size in range(len(self.labels) + 1)
                for combo in itertools.combinations(self.labels, size)]


def _product(numbers):
    total = 1
    for n in numbers:
        total *= n
    return total


# The evaluator refuses an assessment that lacks one of these. Any other
# dimension may be omitted, and an omitted one is a value of its own: a rule
# that reads it answers an assessment without it differently from every value.
EVALUATOR_REQUIRED = ("risk", "familiarity", "size")


def _accepts(vocabulary, dimension, value):
    return (value is None or dimension not in vocabulary
            or value in vocabulary[dimension])


def build_grid(parent, child, atoms=None, exhaustive=False, parent_issue=None,
               child_issue=None):
    """The grid two configurations are compared over. `exhaustive` keeps every
    value as its own class, which gives the same verdict as the grouped grid
    (a test holds the two equal)."""
    if atoms is None:
        atoms = collect_atoms(parent, child, parent_issue, child_issue)
    sides = [(config, assessment_vocabulary(config.get("dimensions") or {}),
              dimension_orders(config.get("dimensions") or {})) for config in (parent, child)]
    names, domains = [], {}
    for config, _, _ in sides:
        for name, dimension in (config.get("dimensions") or {}).items():
            if dimension.get("type") not in CLOSED:
                continue
            if name not in domains:
                names.append(name)
                domains[name] = []
            for value in dimension.get("values") or []:
                if value not in domains[name]:
                    domains[name].append(value)
    for name in names:
        if name not in EVALUATOR_REQUIRED:
            domains[name].append(None)          # the assessment omits it
    dimensions = []
    for name in names:
        relevant = [a for a in atoms if a[1] == name and a[0] in ("in", "at_least")]
        groups = {}
        for value in domains[name]:
            answers = []
            for atom in relevant:
                for _, _, orders in (sides if atom[0] == "at_least" else sides[:1]):
                    condition = ({name: list(atom[2])} if atom[0] == "in"
                                 else {name: {"at_least": atom[2]}})
                    answers.append(reading_matches(condition, {name: value}, orders))
            accepted = tuple(_accepts(vocab, name, value) for _, vocab, _ in sides)
            key = (value,) if exhaustive else (tuple(answers), accepted)
            groups.setdefault(key, []).append((value, all(accepted), any(answers)))
        classes = []
        for members in groups.values():
            both, read = members[0][1], any(m[2] for m in members)
            if both:
                classes.append(ValueClass(tuple(m[0] for m in members), "both"))
            elif read:
                classes.append(ValueClass(tuple(m[0] for m in members), "one-side"))
        dimensions.append((name, tuple(classes)))
    labels = tuple(sorted({label for atom in atoms if atom[0] == "labels_any"
                           for label in atom[1]}))
    return Grid(dimensions=tuple(dimensions), labels=labels,
                domain_sizes=tuple(len(domains[n]) for n in names))


# --- comparing one fact -----------------------------------------------------------

TIGHTER_DIRECTIONS = (*DIRECTIONS, "none")

EQUAL, TIGHTER, LOOSER, INCOMPARABLE = "equal", "tighter", "looser", "incomparable"

# The two differences no key of the field table names.
NO_FIELD = ("evaluation.refused", "dimensions.values")


def _set_rule(field, key, p, c, ctx, meta=None):
    """Obligation set: a superset is stricter."""
    p, c = set(p or ()), set(c or ())
    if p == c:
        return EQUAL
    if p < c:
        return TIGHTER
    return LOOSER if c < p else INCOMPARABLE


# A way set lists ways to satisfy an obligation, so a smaller one is stricter.
# For these an empty list is no restriction: any agent session may review, and
# anyone may tick a human check.
WIDEST_WHEN_EMPTY = ("checks.reviewers", "checks.approvers")


def _way_rule(field, key, p, c, ctx, meta=None):
    p, c = set(p or ()), set(c or ())
    if p == c:
        return EQUAL
    if field in WIDEST_WHEN_EMPTY:
        if not p:
            return TIGHTER
        if not c:
            return LOOSER
    if c < p:
        return TIGHTER
    return LOOSER if p < c else INCOMPARABLE


def _identity_rule(field, key, p, c, ctx, meta=None):
    return EQUAL if p == c else INCOMPARABLE


def _rank(field, key, value, side, ctx):
    """Where a value sits in its field's declared order, or None."""
    if field == "approaches.stages":
        modes = (((ctx.configs[side].get("stages") or {}).get(key) or {})
                 .get("modes") or {})
        rank = (modes.get(value) or {}).get("rank")
        return rank if isinstance(rank, int) and not isinstance(rank, bool) else None
    order = {"checks.severity": SEVERITIES, "checks.on_skipped": ON_SKIPPED,
             "approaches.artifacts.depth": ARTIFACT_DEPTHS}.get(field, ())
    return order.index(value) if value in order else None


def _ordered_rule(field, key, p, c, ctx, meta=None):
    """Higher in the declared order is stricter. A stage only one side has is
    by existence. A value with no place in the order, or two names that share
    one, cannot be compared."""
    if p == c:
        return EQUAL
    if p is None:
        return TIGHTER
    if c is None:
        return LOOSER
    rp, rc = _rank(field, key, p, 0, ctx), _rank(field, key, c, 1, ctx)
    if rp is None or rc is None or rp == rc:
        return INCOMPARABLE
    return TIGHTER if rc > rp else LOOSER


def _registry_direction(impl, param):
    from compass_pkg.check_registry import REGISTRY
    entry = REGISTRY.get(impl)
    return (entry.tighter.get(param, "none") if entry else "none")


def _direction(field, key, meta, ctx):
    if field == "checks.params":
        check, param = meta
        impls = {(config.get("checks") or {}).get(check, {}).get("impl")
                 for config in ctx.configs}
        if len(impls) != 1:
            return "none"
        impl = impls.pop()
        found = ctx.directions.get(f"checks.params.{impl}.{param}")
        if found is None:
            found = (ctx.tighter or _registry_direction)(impl, param)
    else:
        # The caller's directions come first (they exist for tests), then the
        # field table's, and a ceiling neither names has none.
        found = "none"
        for table in (ctx.directions, CEILING_DIRECTIONS):
            named = (table.get(f"{field}.{key}") if key is not None else None)
            named = named or table.get(field)
            if named:
                found = named
                break
    if found not in TIGHTER_DIRECTIONS:
        raise CompassError(f"the direction of {field} is '{found}'; it must be one "
                           f"of {', '.join(TIGHTER_DIRECTIONS)}")
    return found


def _number(value):
    """A ceiling's size: no ceiling at all is the largest."""
    if value is None:
        return float("inf")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _ceiling_rule(field, key, p, c, ctx, meta=None):
    """As the registry declares: `higher` or `lower` is the stricter way, and
    `none` (the default) makes any change incomparable."""
    if p == c:
        return EQUAL
    direction = _direction(field, key, meta, ctx)
    np_, nc = _number(p), _number(c)
    if direction == "none" or np_ is None or nc is None:
        return INCOMPARABLE
    return TIGHTER if (nc < np_) == (direction == "lower") else LOOSER


# The rule for each compare kind of the field table.
RULES = {"obligation-set": _set_rule, "identity": _identity_rule,
         "ordered": _ordered_rule, "way-set": _way_rule,
         "ceiling": _ceiling_rule}


@dataclass(frozen=True)
class Change:
    """One difference between the obligations at a point."""
    fact: str
    field: str
    key: object
    outcome: str
    parent: object
    child: object


@dataclass
class Point:
    assessment: dict
    represents: dict
    outcome: str = EQUAL
    summary: str = ""
    changes: tuple = ()


class _Context:
    """What a comparison needs besides the two values: each side's
    configuration, the stage order and the direction of each ceiling."""

    def __init__(self, parent, child, directions, tighter):
        self.configs = (parent, child)
        self.directions = directions or {}       # the caller's, for tests
        self.tighter = tighter
        stages = {}
        for config in (parent, child):
            for name, body in (config.get("stages") or {}).items():
                stages.setdefault(name, (body or {}).get("order", 0))
        self.stage_order = sorted(stages, key=lambda n: (stages[n], n))


def _compare(field, key, p, c, ctx, out, meta=None):
    kind = OBLIGATION_FIELDS.get(field)
    if kind is None:            # a field the table omits is not compared
        return
    outcome = RULES[kind](field, key, p, c, ctx, meta)
    if outcome != EQUAL:
        out.append(Change(_FACT_OF[field], field, key, outcome, p, c))


# The fact each field is read from, for the order of a point's changes.
_FACT_OF = {}
for _fact, _fields in {
        "stage_mode": ("approaches.stages",), "entry": ("stages.entry",),
        "exit": ("stages.exit",), "gate_set": ("approaches.gates",),
        "gate_checks": ("gates.checks",), "gate_accepts": ("gates.accepts",),
        "artifacts_owed": ("approaches.artifacts", "approaches.artifacts.depth"),
        "required_skills": ("evaluation.required_skills",),
        "blocked_stages": ("evaluation.blocked_stages",),
        "required_artifacts": ("evaluation.required_artifacts",),
        "checkpoints": ("approaches.checkpoints",),
        "ceilings": ("approaches.subtask_ceiling", "evaluation.max_worktrees",
                     "rules.ceilings"),
        "checks": tuple(f for f in OBLIGATION_FIELDS if f.startswith("checks.")),
        "artifact_depends_on": ("artifacts.depends_on",),
        "artifact_checks": ("artifacts.checks",)}.items():
    for _name in _fields:
        _FACT_OF[_name] = _fact

CHECK_FIELDS = ("kind", "impl", "params", "accepts", "reviewers", "approvers",
                "inputs", "severity", "on_skipped", "statement")


def _keyed(field, p, c, ctx, out, keys=None, both_only=False):
    """Compare a fact that maps a name to a value, for each name in order."""
    for key in (keys if keys is not None else sorted(set(p) | set(c))):
        if both_only and (key not in p or key not in c):
            continue
        _compare(field, key, p.get(key), c.get(key), ctx, out)


def _changes(parent, child, ctx):
    """Every difference between two `Obligations`, by fact in the order of the
    dataclass, then field, then key."""
    p, c = parent.compared(), child.compared()
    out = []
    _keyed("approaches.stages", p["stage_mode"], c["stage_mode"], ctx, out,
           keys=ctx.stage_order)
    for fact, field in (("entry", "stages.entry"), ("exit", "stages.exit")):
        _keyed(field, p[fact], c[fact], ctx, out, keys=ctx.stage_order)
    _compare("approaches.gates", None, p["gate_set"], c["gate_set"], ctx, out)
    _keyed("gates.checks", p["gate_checks"], c["gate_checks"], ctx, out)
    _keyed("gates.accepts", p["gate_accepts"], c["gate_accepts"], ctx, out,
           both_only=True)
    _compare("approaches.artifacts", None, set(p["artifacts_owed"]),
             set(c["artifacts_owed"]), ctx, out)
    _keyed("approaches.artifacts.depth", p["artifacts_owed"], c["artifacts_owed"],
           ctx, out, both_only=True)
    for fact in ("required_skills", "blocked_stages", "required_artifacts"):
        _compare(f"evaluation.{fact}", None, p[fact], c[fact], ctx, out)
    _keyed("approaches.checkpoints", p["checkpoints"], c["checkpoints"], ctx, out)
    pc, cc = p["ceilings"], c["ceilings"]
    for name, field in (("subtask_ceiling", "approaches.subtask_ceiling"),
                        ("max_worktrees", "evaluation.max_worktrees")):
        _compare(field, None, pc.get(name), cc.get(name), ctx, out)
    for name in sorted((set(pc) | set(cc)) - {"subtask_ceiling", "max_worktrees"}):
        _compare("rules.ceilings", name, pc.get(name), cc.get(name), ctx, out)
    for check in sorted(set(p["checks"]) & set(c["checks"])):
        pf, cf = p["checks"][check], c["checks"][check]
        for name in CHECK_FIELDS:
            if name == "params":
                for param in sorted(set(pf[name]) | set(cf[name])):
                    _compare("checks.params", f"{check}.{param}",
                             pf[name].get(param), cf[name].get(param), ctx, out,
                             meta=(check, param))
            elif name in pf and name in cf:
                _compare(f"checks.{name}", check, pf[name], cf[name], ctx, out)
    _keyed("artifacts.depends_on", p["artifact_depends_on"],
           c["artifact_depends_on"], ctx, out)
    _keyed("artifacts.checks", p["artifact_checks"], c["artifact_checks"], ctx, out)
    return out


def _point_outcome(changes):
    outcomes = {change.outcome for change in changes}
    if not outcomes:
        return EQUAL
    if INCOMPARABLE in outcomes or {TIGHTER, LOOSER} <= outcomes:
        return "mixed"
    return TIGHTER if outcomes == {TIGHTER} else LOOSER


# --- scanning the grid -------------------------------------------------------------

def _plain(value):
    """A value as plain JSON: sets and tuples are sorted lists, keys sorted."""
    if isinstance(value, dict):
        return {str(k): _plain(value[k]) for k in sorted(value, key=str)}
    if isinstance(value, (set, frozenset)):
        return sorted((_plain(v) for v in value), key=str)
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _digest(*parts):
    text = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _where(assessment):
    shown = [f"{k} {v}" for k, v in assessment.items() if k != "labels"]
    labels = assessment.get("labels") or []
    shown.append("labels " + (", ".join(labels) if labels else "none"))
    return ", ".join(shown)


def _summary(assessment, changes):
    change = next((c for c in changes if c.outcome == LOOSER), None) or next(
        (c for c in changes if c.outcome == INCOMPARABLE), None) or changes[0]
    key = f" ({change.key})" if change.key is not None else ""
    return (f"at {_where(assessment)}: {change.field}{key} is "
            f"{json.dumps(_plain(change.parent))} in the parent and "
            f"{json.dumps(_plain(change.child))} in the child")


def _evaluate(classes, subset, run):
    assessment = {name: cls.values[0] for (name, _), cls in zip(run.dimensions, classes)
                  if cls.values[0] is not None}
    assessment["labels"] = list(subset)
    represents = {name: list(cls.values) for (name, _), cls in zip(run.dimensions, classes)}
    one_side = [(name, cls) for (name, _), cls in zip(run.dimensions, classes)
                if cls.kind == "one-side"]
    if one_side:
        changes = [Change("vocabulary", "dimensions.values", name, INCOMPARABLE,
                          _accepts(run.vocab[0], name, cls.values[0]),
                          _accepts(run.vocab[1], name, cls.values[0]))
                   for name, cls in one_side]
    else:
        owed = []
        for side in (0, 1):
            cache_key = (run.sides[side], json.dumps(assessment, sort_keys=True))
            if run.cache is not None and cache_key in run.cache:
                owed.append(run.cache[cache_key])
                continue
            config, caps, issue = run.inputs[side]
            got = obligations.obligations(config, assessment, capabilities=caps, issue=issue)
            if run.cache is not None:
                run.cache[cache_key] = got
            owed.append(got)
        p, c = owed
        if isinstance(p, Refused) or isinstance(c, Refused):
            same = isinstance(p, Refused) and isinstance(c, Refused) and p.reason == c.reason
            changes = [] if same else [Change(
                "refused", "evaluation.refused", None, INCOMPARABLE,
                p.reason if isinstance(p, Refused) else None,
                c.reason if isinstance(c, Refused) else None)]
        else:
            changes = _changes(p, c, run.ctx)
    point = Point(assessment, represents, _point_outcome(changes), "", tuple(changes))
    if changes:
        point.summary = _summary(assessment, changes)
    return point


class _Run:
    def __init__(self, parent, child, grid, kwargs):
        self.dimensions = grid.dimensions
        self.cache = kwargs["cache"]
        self.inputs = ((parent, tuple(kwargs["parent_capabilities"]),
                        kwargs["parent_issue"]),
                       (child, tuple(kwargs["child_capabilities"]), kwargs["child_issue"]))
        self.sides = tuple(_digest(*i) for i in self.inputs)
        self.vocab = tuple(assessment_vocabulary(c.get("dimensions") or {})
                           for c in (parent, child))
        self.ctx = _Context(parent, child, kwargs["directions"], kwargs["tighter"])


# --- the result ----------------------------------------------------------------

COUNT_NAMES = ("equal", "tighter", "looser", "mixed")


def _point_json(point):
    if point is None:
        return None
    return {
        "assessment": {k: (list(v) if isinstance(v, (list, tuple)) else v)
                       for k, v in point.assessment.items()},
        "represents": {name: list(values) for name, values in point.represents.items()},
        "outcome": point.outcome,
        "summary": point.summary,
        "changes": [{"fact": c.fact, "field": c.field, "key": c.key,
                     "outcome": c.outcome, "parent": _plain(c.parent),
                     "child": _plain(c.child)} for c in point.changes],
    }


@dataclass
class Classification:
    result: str = "equivalent"
    reason: str = ""
    grid: Grid = None
    exhaustive: bool = False
    complete: bool = True
    scan: str = "full"            # full, early-exit, identical or cap
    parent_name: object = None    # what the caller says was compared
    child_name: object = None
    counts: dict = field(default_factory=lambda: {"equal": 0, "tighter": 0,
                                                  "looser": 0, "mixed": 0})
    first_looser: object = None
    first_tighter: object = None
    first_mixed: object = None

    def to_json(self):
        """The result as the documented dictionary (`JSON_SHAPE`). Every field
        is present for every verdict, in a fixed order, and nothing in it
        depends on a path, a layer name or the time."""
        grid = self.grid or Grid()
        return {
            "schema": JSON_SCHEMA_VERSION,
            "result": self.result,
            "reason": self.reason,
            "scan": self.scan,
            "parent": self.parent_name,
            "child": self.child_name,
            "exhaustive": self.exhaustive,
            "complete": self.complete,
            "grid": {"labels": list(grid.labels), "label_count": grid.label_count,
                     "label_cap": LABEL_CAP, "points": grid.points,
                     "raw_points": grid.raw_points, "evaluated": grid.evaluated},
            "counts": {name: self.counts[name] for name in COUNT_NAMES},
            "first_looser": _point_json(self.first_looser),
            "first_tighter": _point_json(self.first_tighter),
            "first_mixed": _point_json(self.first_mixed),
        }


def classify(parent, child, *, parent_capabilities=(), child_capabilities=(),
             parent_issue=None, child_issue=None, directions=None, tighter=None,
             exhaustive=False, early_exit=False, cache=None, parent_name=None,
             child_name=None):
    """`parent_name` and `child_name` say what was compared (a ref, a layer
    name). They are carried into the JSON and read by nothing else."""
    named = dict(parent_name=parent_name, child_name=child_name)
    kwargs = dict(parent_capabilities=parent_capabilities,
                  child_capabilities=child_capabilities, parent_issue=parent_issue,
                  child_issue=child_issue, directions=directions, tighter=tighter,
                  cache=cache)
    atoms = collect_atoms(parent, child, parent_issue, child_issue)
    grid = build_grid(parent, child, atoms, exhaustive, parent_issue, child_issue)
    if (parent == child and tuple(parent_capabilities) == tuple(child_capabilities)
            and parent_issue == child_issue):
        return Classification("equivalent", "the configurations are identical",
                              grid, exhaustive, True, "identical", **named)
    if len(grid.labels) > LABEL_CAP:
        grid.stopped = True
        return Classification(
            "incomparable",
            f"more than eight named set values: {len(grid.labels)} "
            f"({', '.join(grid.labels)}); the grid is not sampled",
            grid, exhaustive, False, "cap", **named)
    run = _Run(parent, child, grid, kwargs)
    out = Classification(grid=grid, exhaustive=exhaustive, **named)
    subsets = grid.label_subsets()
    scanned = 0
    for classes in itertools.product(*[cs for _, cs in grid.dimensions]):
        for subset in subsets:
            point = _evaluate(classes, subset, run)
            scanned += 1
            out.counts["mixed" if point.outcome == "mixed" else point.outcome] += 1
            slot = {LOOSER: "first_looser", TIGHTER: "first_tighter",
                    "mixed": "first_mixed"}.get(point.outcome)
            if slot and getattr(out, slot) is None:
                setattr(out, slot, point)
            if early_exit and _final(out):
                break
        else:
            continue
        break
    grid.evaluated = scanned
    out.complete = scanned == grid.points
    out.scan = "full" if out.complete else "early-exit"
    out.result, out.reason = _verdict(out)
    return out


def _final(out):
    return out.first_mixed is not None or (
        out.first_looser is not None and out.first_tighter is not None)


def _verdict(out):
    counts = out.counts
    if out.first_mixed is not None:
        return "incomparable", out.first_mixed.summary
    if out.first_looser and out.first_tighter:
        return "incomparable", (f"one point owes less ({out.first_looser.summary}) "
                                f"and another owes more ({out.first_tighter.summary})")
    if out.first_looser:
        return "loosening", out.first_looser.summary
    if out.first_tighter:
        return "tightening", (f"{counts['tighter']} of {out.grid.evaluated} points "
                              f"owe more and none owe less")
    return "equivalent", "every point owes the same"


# The documented shape of `to_json()`. A string names a JSON type; `("one of",
# ...)` is a closed set of strings; `("or null", shape)` is a shape or null; a
# dictionary is an object with exactly these keys in this order; a one-item
# list is a list of that shape; `"any"` is any JSON value.
_CHANGE_SHAPE = {"fact": "string", "field": "string", "key": ("or null", "string"),
                 "outcome": ("one of", ("tighter", "looser", "incomparable")),
                 "parent": "any", "child": "any"}
_POINT_SHAPE = {"assessment": "object", "represents": "object",
                "outcome": ("one of", ("tighter", "looser", "mixed")),
                "summary": "string", "changes": [_CHANGE_SHAPE]}
JSON_SHAPE = {
    "schema": "integer",
    "result": ("one of", ("equivalent", "tightening", "loosening", "incomparable")),
    "reason": "string",
    "scan": ("one of", ("full", "early-exit", "identical", "cap")),
    "parent": ("or null", "string"),
    "child": ("or null", "string"),
    "exhaustive": "boolean",
    "complete": "boolean",
    "grid": {"labels": ["string"], "label_count": "integer", "label_cap": "integer",
             "points": "integer", "raw_points": "integer", "evaluated": "integer"},
    "counts": {name: "integer" for name in COUNT_NAMES},
    "first_looser": ("or null", _POINT_SHAPE),
    "first_tighter": ("or null", _POINT_SHAPE),
    "first_mixed": ("or null", _POINT_SHAPE),
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


def json_shape_errors(document):
    """What differs between a document and `JSON_SHAPE`; empty when it matches."""
    errors = []
    _shape_errors(document, JSON_SHAPE, "$", errors)
    return errors
