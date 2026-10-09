"""Small resolved configurations for the classifier tests.

The shipped preset has 4,608 grouped points, so a test that classifies a change
to it takes seconds. These configurations have a handful of values on each
dimension, so a test can also run the full grid and compare the two. Each
builder returns a fresh dictionary, so a test changes its own copy.

A configuration here is what `merge.apply` returns: the catalogues, resolved.
"""
from __future__ import annotations

import copy


def check(**over):
    body = {"statement": "The suite passed.", "kind": "deterministic",
            "impl": "suite-passed", "severity": "blocking", "on_skipped": "fail"}
    body.update(over)
    return body


def base():
    """Two dimensions with an order, one without, the labels, two delivery
    approaches (the second owes one more gate), a floor that reads a label
    and two checks, one of them on a gate."""
    return copy.deepcopy({
        "dimensions": {
            "risk": {"type": "ordered-enum", "values": ["contained", "critical"],
                     "tighter": "higher", "required": True},
            "familiarity": {"type": "enum",
                            "values": ["greenfield", "brownfield-unmapped"],
                            "required": True},
            "size": {"type": "ordered-enum", "values": ["small", "large"],
                     "tighter": "higher", "required": True},
            "labels": {"type": "set", "open": True},
        },
        "stages": {
            stage: {"order": order,
                    "modes": {"lightweight": {"rank": 2}, "thorough": {"rank": 3},
                              "reproduce-first": {}}}
            for order, stage in enumerate(("define", "implement", "verify"), 1)
        },
        "approaches": {
            "regular": {
                "weight": 2, "ships": True,
                "stages": {"define": "thorough", "implement": "thorough",
                           "verify": "thorough"},
                "gates": ["verify.correctness"], "artifacts": {},
                "subtask_ceiling": 2,
                "checkpoints": {"controlled": ["define"], "balanced": [],
                                "autonomous": []}},
            "full": {
                "weight": 4, "ships": True,
                "stages": {"define": "thorough", "implement": "thorough",
                           "verify": "thorough"},
                "gates": ["verify.correctness", "verify.security"], "artifacts": {},
                "subtask_ceiling": 2,
                "checkpoints": {"controlled": ["define"], "balanced": ["define"],
                                "autonomous": []}},
        },
        "rules": {
            "default_shapes": {
                "kind": "shapes", "hit": {"lean_toward": "first"},
                "rules": {
                    "S-1": {"order": 1, "when": {"size": "large"},
                            "then": {"lean_toward": "full"}},
                    "S-FALLBACK": {"order": 2, "when": {},
                                   "then": {"lean_toward": "regular"}},
                }},
            "floors": {
                "kind": "floors", "hit": {"force_minimum_approach": "max"},
                "rules": {
                    "F-1": {"order": 1, "when": {"labels_any": ["auth"]},
                            "then": {"force_minimum_approach": "full"}},
                }},
        },
        "checks": {
            "tests-pass": check(),
            "no-secrets": check(impl="no-trusted-rerun"),
        },
        "gates": {
            "verify.correctness": {"kind": "review", "checks": ["tests-pass"],
                                   "accepts": ["test-run"]},
            "verify.security": {"kind": "review", "checks": ["no-secrets"],
                                "accepts": ["security-review", "test-run"]},
            "G1": {"kind": "guardrail", "stage": "verify",
                   "applies_to": {"ships": True}, "checks": ["tests-pass"],
                   "accepts": ["test-run"]},
        },
    })


def with_labels(config, *names):
    """A rule whose `when` names each label, so the labels are in the grid.
    It sets no effect that changes what is owed."""
    out = copy.deepcopy(config)
    out["rules"]["floors"]["rules"]["F-LABELS"] = {
        "order": 9, "when": {"labels_any": list(names)},
        "then": {"force_minimum_approach": "regular"}}
    return out


def preset():
    """The committed default preset merged as one parent layer."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "cli"))
    import yaml
    from compass_pkg import catalogue_spec, merge
    directory = root / "governance" / "presets" / "default"
    parts = []
    for name in catalogue_spec.CATALOGUES:
        part = yaml.safe_load((directory / f"{name}.yml").read_text(encoding="utf-8"))
        parts.append({k: v for k, v in part.items() if k != "schema"})
    config, _ = merge.apply({}, {"schema": 1, **merge.combine(parts)}, "parent",
                            "default")
    return config


def layer(config, doc, kind="project"):
    from compass_pkg import merge
    return merge.apply(config, {"schema": 1, **doc}, kind, f"test-{kind}")[0]


def with_spike(config, when=None):
    """A spike approach and a shape that picks it at critical risk, so that a
    floor which delivers (the label floor) makes the evaluator refuse."""
    out = copy.deepcopy(config)
    out["approaches"]["spike"] = {
        "weight": 0, "ships": False,
        "stages": {"define": "lightweight", "implement": "thorough", "verify": "thorough"},
        "gates": [], "artifacts": {}, "subtask_ceiling": 1, "checkpoints": {}}
    out["rules"]["default_shapes"]["rules"]["S-0"] = {
        "order": 0, "when": when or {"risk": "critical"},
        "then": {"lean_toward": "spike"}}
    return out
