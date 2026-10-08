# compass_pkg.receipt_provenance - where each named entry of a receipt came from
"""The "Provenance" section of `compass issue receipt`.

For an issue that runs against a stored generation, this names each fired
rule, check, lock, unlock and waiver with the layer that set it: the default
preset with its major and version, a git parent with its reference, pinned sha
and version, the project, or the issue. The generation number is in the title,
because an issue runs against one generation.

It reads the view of the stored generation and the manifest, and nothing else:
no file, no check run. An issue with no stored generation gets no lines, so its
receipt does not change.
"""
# DEPENDENCY: standard library (textwrap); compass_pkg.locks (the shipped lock
# summary, for a lock the merge does not keep on the resolved entry).
from __future__ import annotations

import re
import textwrap

from compass_pkg import locks

TITLE = "Provenance"
KIND_WIDTH = 14
INDENT = " " * (2 + KIND_WIDTH + 1)

# The layer names a step carries; every other name is a git parent.
PROJECT = "project"
ISSUE = "issue"


def _labels(versions):
    """`{layer name: label}` for the layers a generation was resolved with."""
    out = {}
    for position, parent in enumerate(versions.get("parents") or []):
        version = parent.get("version") or "unversioned"
        if parent.get("source") == "git":
            sha = str(parent.get("sha") or "")
            out[f"{parent.get('ref')}#{sha[:7]}"] = f"{parent.get('ref')}#{sha[:12]} ({version})"
        elif position == 0 and parent.get("source") == "legacy":
            out["default"] = f"governance copies ({version})"
        elif position == 0:
            out["default"] = f"{str(parent.get('ref')).removeprefix('compass:')} ({version})"
    # The order the layers apply in, which is the order the groups print in.
    out[PROJECT] = "project (compass.yml)"
    out[ISSUE] = "issue (config: in manifest.yml)"
    return out


def _label(labels, name):
    return labels.get(name, str(name))


def _steps(provenance, path):
    return ((provenance.get("fields") or {}).get(path) or {}).get("steps") or []


def _rule_layer(view, labels, rule_id):
    """The label of the layer that set a fired rule."""
    for set_id, rule_set in (view.resolved.get("rules") or {}).items():
        members = rule_set.get("rules") if isinstance(rule_set, dict) else None
        if not isinstance(members, dict) or rule_id not in members:
            continue
        own = _steps(view.provenance, f"rules.{set_id}.rules.{rule_id}")
        if own:
            return _label(labels, own[-1]["layer"])
        # Stored before each rule had a step of its own: only the rule set's
        # layers are known, and the receipt does not guess among them.
        names = []
        for step in _steps(view.provenance, f"rules.{set_id}.rules"):
            if step["layer"] not in names:
                names.append(step["layer"])
        if len(names) == 1:
            return _label(labels, names[0])
        return "unknown, rule set changed by " + ", ".join(_label(labels, n) for n in names)
    return "unknown, not in the stored configuration"


def _check_facts(view):
    """`{check id: (origin layer, [(layer, op)])}`: the layer that added each
    check, and each later layer's operation on it."""
    facts = {}
    for path, record in (view.provenance.get("fields") or {}).items():
        match = re.fullmatch(r"checks\.([^.]+)(?:\.[^.]+)?", path)
        if not match:
            continue
        steps = record.get("steps") or []
        if path == f"checks.{match.group(1)}" and steps:
            facts.setdefault(match.group(1), [steps[0]["layer"], []])[0] = steps[0]["layer"]
            continue
        entry = facts.setdefault(match.group(1), [None, []])
        entry[1] += [(s["layer"], s["op"]) for s in steps if s["op"] != "add"]
    return {k: (v[0], v[1]) for k, v in facts.items() if v[0]}


def _lock_of(view, labels, entry):
    """`(level, layer label)` of the lock on a catalogue entry, or None."""
    catalogue, _, entry_id = entry.partition(".")
    body = (view.resolved.get(catalogue) or {}).get(entry_id)
    if isinstance(body, dict) and body.get("locked"):
        steps = _steps(view.provenance, f"{entry}.locked")
        return body["locked"], _label(labels, steps[-1]["layer"] if steps else "default")
    parents = view.versions.get("parents") or []
    if parents and parents[0].get("source") == "shipped":
        held = (locks.shipped_locks() or {}).get(entry)
        if held:
            return held.level, labels.get("default", "default")
    return None


def _level(level):
    return "hard" if level == "hard" else "true"


def _wrapped(kind, label, items, width):
    """One group: its kind, the layer, then ids that wrap on a new line rather
    than being cut."""
    head = f"  {kind:<{KIND_WIDTH}} {label} - "
    lines, current, fresh = [], head, True
    for i, item in enumerate(items):
        piece = item + ("," if i < len(items) - 1 else "")
        if fresh and len(current) + len(piece) <= width:
            current += piece
        elif not fresh and len(current) + 1 + len(piece) <= width:
            current += " " + piece
        else:
            lines.append(current.rstrip())
            current = INDENT + piece
        fresh = False
    lines.append(current)
    return lines


def _sentence(kind, subject, text, width):
    return textwrap.wrap(f"  {kind:<{KIND_WIDTH}} {subject} - {text}", width=width,
                         subsequent_indent=INDENT, break_long_words=False,
                         break_on_hyphens=False)


def _groups(kind, pairs, labels, width):
    """Rows for `pairs` of `(layer label, item)`, one group per label, in the
    order the layers apply."""
    order = list(labels.values())
    found = {}
    for label, item in pairs:
        found.setdefault(label, [])
        if item not in found[label]:
            found[label].append(item)
    out = []
    for label in sorted(found, key=lambda l: order.index(l) if l in order else len(order)):
        out += _wrapped(kind, label, found[label], width)
    return out


def lines(view, task, listed_checks=(), width=100):
    """The section as lines, or none for an issue with no stored generation."""
    if view is None or view.source != "generation":
        return []
    labels = _labels(view.versions)
    rows = []

    fired = [r.get("id") if isinstance(r, dict) else r for r in task.get("policy_rules_fired") or []]
    rows += _groups("rules fired", [(_rule_layer(view, labels, str(r)), str(r)) for r in fired],
                    labels, width)

    waiver_records = sorted((view.provenance.get("waivers") or {}).values(),
                            key=lambda w: str(w.get("id")))
    unlocked = list((view.resolved.get("conformance") or {}).get("unlocked") or [])
    entries = [f"checks.{c}" for c in listed_checks]
    entries += unlocked + [w.get("entry") for w in waiver_records if w.get("entry")]

    facts = _check_facts(view)
    default_layer = "default"
    named = list(dict.fromkeys(
        [c for c in listed_checks if c in facts]
        + [e.split(".", 1)[1] for e in entries if e.startswith("checks.") and e.split(".", 1)[1] in facts]
        + [c for c, (origin, changes) in facts.items()
           if origin != default_layer or changes]))
    rows += _groups("checks", [(_label(labels, facts[c][0]), c) for c in named], labels, width)
    changes = []
    for check in named:
        ops = {}
        for layer, op in facts[check][1]:
            ops.setdefault(layer, [])
            if op not in ops[layer]:
                ops[layer].append(op)
        changes += [(_label(labels, layer), f"{check} ({'+'.join(found)})")
                    for layer, found in ops.items()]
    rows += _groups("check changes", changes, labels, width)

    held = []
    for entry in dict.fromkeys(entries):
        lock = _lock_of(view, labels, entry)
        if lock:
            held.append((lock[1], f"{entry} ({_level(lock[0])})"))
    rows += _groups("locks", held, labels, width)

    landed = task.get("status") == "landed"
    stamp = str(task.get("land_timestamp") or "")[:10]
    for record in waiver_records:
        scope = record.get("scope")
        status = record.get("status") or "valid"
        if scope == ISSUE and landed and stamp:
            status = f"expired at land {stamp}"
        text = f"{_label(labels, scope)}, approved by {record.get('approved_by')}"
        if record.get("approved_on"):
            text += f" on {record['approved_on']}"
        rows += _sentence("waiver", str(record.get("id")), f"{text}, {status}", width)

    for entry in unlocked:
        lock = _lock_of(view, labels, entry)
        lifted = (f"lifts a {_level(lock[0])} lock set by {lock[1]}" if lock
                  else "lifts a lock the stored configuration does not name")
        rows += _sentence("unlock", entry, f"{_label(labels, PROJECT)}, waiver project:{entry}; "
                          f"{lifted}", width)

    title = f"{TITLE} (generation {view.generation})"
    if not rows:
        rows = ["  no rule fired, and no check, waiver, lock or unlock is named"]
    return [title, "-" * len(title)] + rows
