# compass_pkg.receipt_provenance - where each named entry of a receipt came from
"""The "Provenance" section of `compass issue receipt`.

For an issue that runs against a stored generation, this names each fired
rule, check, lock, unlock and waiver with the layer that set it: the default
preset with its major and version, a git parent with its reference, pinned sha
and version, the project's own governance copies, the project, or the issue.
The generation number is in the title, because an issue runs against one
generation.

The module is pure. It reads the view of the stored generation and the
manifest, and it is handed the two things it cannot reach itself: the installed
CLI's shipped lock summary, for a lock the merge does not keep on the resolved
entry (it is labelled with the generation's pinned version, and within one
major the two agree), and the receipt's id-wrapping function. It reads no file
and runs no check. An issue with no stored generation gets no lines, so its
receipt does not change.
"""
# DEPENDENCY: standard library (re, textwrap); compass_pkg.status_words, which
# imports nothing.
from __future__ import annotations

import re
import textwrap

from compass_pkg import status_words

TITLE = "Provenance"
KIND_WIDTH = 14
INDENT = " " * (2 + KIND_WIDTH + 1)

# The layer names a step carries; every other name is a git parent.
PROJECT = "project"
ISSUE = "issue"


def _root(versions):
    """The name of the layer the chain starts from: the project's own governance
    copies, or the shipped default."""
    parents = versions.get("parents") or [{}]
    return "legacy" if parents[0].get("source") == "legacy" else "default"


def _labels(versions):
    """`{layer name: label}` for the layers a generation was resolved with, in
    the order the layers apply."""
    out = {}
    for position, parent in enumerate(versions.get("parents") or []):
        version = parent.get("version") or "unversioned"
        if parent.get("source") == "git":
            sha = str(parent.get("sha") or "")
            out[f"{parent.get('ref')}#{sha[:7]}"] = f"{parent.get('ref')}#{sha[:12]} ({version})"
        elif position == 0 and parent.get("source") == "legacy":
            out["legacy"] = f"governance copies ({version})"
        elif position == 0:
            out["default"] = f"{str(parent.get('ref')).removeprefix('compass:')} ({version})"
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


def _lock_of(view, labels, entry, shipped):
    """`(level, layer label)` of the lock on a catalogue entry, or None.
    `shipped` is `{entry: Lock}` for the installed shipped default."""
    catalogue, _, entry_id = entry.partition(".")
    body = (view.resolved.get(catalogue) or {}).get(entry_id)
    if isinstance(body, dict) and body.get("locked"):
        steps = _steps(view.provenance, f"{entry}.locked")
        return body["locked"], _label(labels, steps[-1]["layer"] if steps
                                      else _root(view.versions))
    parents = view.versions.get("parents") or []
    if parents and parents[0].get("source") == "shipped":
        held = (shipped or {}).get(entry)
        if held:
            return held.level, labels.get("default", "default")
    return None


def _level(level):
    return "hard" if level == "hard" else "true"


def _heading(kind, label, width):
    """`(finished lines, last line)` of a group's heading. A label too long for
    one line breaks between words, and before the `#` of a pinned sha."""
    done, current, empty = [], f"  {kind:<{KIND_WIDTH}} ", True
    for token in re.findall(r"#?[^\s#]+", label):
        gap = "" if empty or token.startswith("#") else " "
        if not empty and len(current) + len(gap) + len(token) > width - 2:
            done.append(current.rstrip())
            current, gap = INDENT, ""
        current += gap + token
        empty = False
    return done, current


def _wrapped(kind, label, items, width, wrap_ids):
    """One group: its kind, the layer, then ids that wrap on a new line rather
    than being cut. A heading that leaves no room for the first id ends its own
    line."""
    done, last = _heading(kind, label, width)
    head = last + " - "
    if len(head) + len(items[0]) <= width:
        return done + wrap_ids(head, items, width, INDENT)
    return done + [last + " -"] + wrap_ids(INDENT, items, width, INDENT)


def _sentence(kind, subject, text, width):
    return textwrap.wrap(f"  {kind:<{KIND_WIDTH}} {subject} - {text}", width=width,
                         subsequent_indent=INDENT, break_long_words=False,
                         break_on_hyphens=False)


def _groups(kind, pairs, labels, width, wrap_ids):
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
        out += _wrapped(kind, label, found[label], width, wrap_ids)
    return out


def lines(view, task, listed_checks=(), shipped_locks=None, wrap_ids=None, width=100):
    """The section as lines, or none for an issue with no stored generation.
    `shipped_locks` is `locks.shipped_locks()`; `wrap_ids(head, ids, width,
    indent)` is the receipt's id wrapper."""
    if view is None or view.source != "generation":
        return []
    labels = _labels(view.versions)
    root = _root(view.versions)
    rows = []

    fired = [r.get("id") if isinstance(r, dict) else r for r in task.get("policy_rules_fired") or []]
    rows += _groups("rules fired", [(_rule_layer(view, labels, str(r)), str(r)) for r in fired],
                    labels, width, wrap_ids)

    facts = _check_facts(view)
    # A stage-list check from the root layer that no layer changed is already
    # shown in the Stage lists section; it is counted here, not repeated.
    plain = [c for c in dict.fromkeys(listed_checks)
             if c in facts and facts[c][0] == root and not facts[c][1]]
    if plain:
        noun = "check" if len(plain) == 1 else "checks"
        rows += _sentence("stage lists", labels[root], f"{len(plain)} {noun} listed above", width)

    waiver_records = sorted((view.provenance.get("waivers") or {}).values(),
                            key=lambda w: str(w.get("id")))
    unlocked = list((view.resolved.get("conformance") or {}).get("unlocked") or [])
    waived = [w.get("entry") for w in waiver_records if w.get("entry")]
    via_entry = [e.split(".", 1)[1] for e in unlocked + waived
                 if e.startswith("checks.") and e.split(".", 1)[1] in facts]
    named = list(dict.fromkeys(
        [c for c in listed_checks if c in facts and c not in plain] + via_entry
        + [c for c, (origin, changes) in facts.items() if origin != root or changes]))
    rows += _groups("checks", [(_label(labels, facts[c][0]), c) for c in named], labels,
                    width, wrap_ids)
    changes = []
    for check in named:
        ops = {}
        for layer, op in facts[check][1]:
            ops.setdefault(layer, [])
            if op not in ops[layer]:
                ops[layer].append(op)
        changes += [(_label(labels, layer), f"{check} ({'+'.join(found)})")
                    for layer, found in ops.items()]
    rows += _groups("check changes", changes, labels, width, wrap_ids)

    held = []
    for entry in dict.fromkeys([f"checks.{c}" for c in named] + unlocked + waived):
        lock = _lock_of(view, labels, entry, shipped_locks)
        if lock:
            held.append((lock[1], f"{entry} ({_level(lock[0])})"))
    rows += _groups("locks", held, labels, width, wrap_ids)

    landed = status_words.is_completed(task)
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
        lock = _lock_of(view, labels, entry, shipped_locks)
        lifted = (f"lifts a {_level(lock[0])} lock set by {lock[1]}" if lock
                  else "lifts a lock the stored configuration does not name")
        rows += _sentence("unlock", entry, f"{_label(labels, PROJECT)}, waiver project:{entry}; "
                          f"{lifted}", width)

    title = f"{TITLE} (generation {view.generation})"
    if not rows:
        rows = ["  no rule fired, and no check, waiver, lock or unlock is named"]
    return [title, "-" * len(title)] + rows
