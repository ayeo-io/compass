# compass_pkg.removed_parts - the verbs, flags and settings 9.0.0 removed (ADR-090 to ADR-092)
"""What 9.0.0 removed, named the same way by every reader.

9.0.0 runs an issue in one session (ADR-090). The verbs and flags that
dispatched agents, recorded subtasks, mapped model tiers, stored execution
profiles or started headless sessions are gone. 9.0.0 also keeps one issue
document, the acceptance criteria (ADR-091), so the verbs that wrote or
checked the other documents are gone. 9.0.0 runs every new delivery issue on
one four-stage path (ADR-092), so the delivery approaches, the legacy stages
the path does not keep, the caps rule set and the Definition of Ready checks
are gone from what a project can configure.

A command line that still names a removed verb or flag fails to parse as an
unknown command, and `line_for` gives the one line the parse error adds.
Each removed `compass.yml` key and capability stays valid and is not read;
`compass policy lint` names it through `setting_findings`. A removed key of a
catalogue (the approaches, a legacy stage, a rule set or a check) is left out
of a project layer by `without_removed` before the merge and the schema check
read it. Each entry names the decision record that removed it.
"""
# DEPENDENCY: compass_pkg.stable_ids (constants only). Imported by compass_pkg.aliases (the parse
# error), compass_pkg.merge (the catalogue a project layer can no longer change)
# and compass_pkg.policy_lint (the removed settings).
from __future__ import annotations

from compass_pkg.stable_ids import (STAGE_BREAKDOWN, STAGE_DEFINE, STAGE_IMPLEMENT, STAGE_PLAN,
                                    STAGE_REFINE, STAGE_VERIFY)

RELEASE = "9.0.0"

#: Why each decision record removed its parts, as the parse error says it.
REASONS = {
    "ADR-090": "Compass runs each issue in one session",
    "ADR-091": "Compass needs only the acceptance criteria",
    "ADR-092": "Compass runs every delivery issue on one four-stage path",
}

#: Each removed command line, as tokens, what replaces it, and the decision
#: record that removed it. A token that starts with `--` is a flag found
#: anywhere after the tokens before it.
COMMANDS = (
    (("run",), "compass run",
     "run the stage in your own session", "ADR-090"),
    (("issue", "subtask"), "compass issue subtask",
     "the session builds each unit of the distribution map itself", "ADR-090"),
    (("profile",), "compass profile", "nothing replaces it", "ADR-090"),
    (("approach", "show", "--model"), "compass approach show --model",
     "a stage command passes no model", "ADR-090"),
    (("approach", "show", "--effort"), "compass approach show --effort",
     "a stage command passes no effort", "ADR-090"),
    (("retro", "--models"), "compass retro --models",
     "no subtask records a model tier", "ADR-090"),
    (("analyze",), "compass analyze",
     "compass check runs the guardrails; no consistency report replaces it", "ADR-091"),
    (("issue", "receipt"), "compass issue receipt",
     "compass approach show lists the issue's gates and compass check judges its evidence",
     "ADR-091"),
    (("issue", "render"), "compass issue render",
     "compass check and compass approach show read the records; no block is written",
     "ADR-091"),
    (("spec", "sync"), "compass spec sync",
     "no living spec is derived, so there is nothing to merge and re-derive", "ADR-091"),
    (("issue", "template", "show"), "compass issue template show",
     "the one document's template is templates/acceptance-criteria.md", "ADR-091"),
    (("issue", "artifact", "set"), "compass issue artifact set",
     "no document is registered or given a status; compass check reads the records",
     "ADR-091"),
    (("issue", "artifact-path"), "compass issue artifact-path",
     "the one document is docs/compass/<created>-<slug>/acceptance-criteria.md", "ADR-091"),
    (("evidence", "approve", "--artifact"), "compass evidence approve --artifact",
     "no document waits for approval; approve a human check with --check", "ADR-091"),
    (("evidence", "request", "--artifact"), "compass evidence request --artifact",
     "no document waits for approval; ask for a human check with --check", "ADR-091"),
    (("plan", "lint"), "compass plan lint",
     "no technical design is written, so there is no plan to scan", "ADR-091"),
    (("_derive-system-spec",), "compass _derive-system-spec",
     "no living spec is derived; the issue records hold each landed scenario", "ADR-091"),
)

#: The ten agent names 9.0.0 removed with the `agents/` folder. The shipped
#: catalogue still names them as document owners, and an older decision ledger
#: as deciders, so both still read.
AGENT_NAMES = ("architect", "builder", "orchestrator", "planner", "product-marketer",
               "product-owner", "reviewer", "router", "spec-author", "verifier")

#: The verification note's template, which 9.0.0 deleted (ADR-091): one
#: rendered block with no `## ` heading. The frozen presets list no heading for
#: it at `lightweight`, so `compass policy lint` reads the kind as this text.
SINGLE_BLOCK_TEMPLATE = "<!-- compass:render verification-note -->\n<!-- /compass:render -->\n"

#: The legacy stages the four-stage path does not keep (ADR-092). The path keeps
#: `assess` and `ship`, so a project can still change those two.
LEGACY_STAGES = (STAGE_DEFINE, STAGE_REFINE, STAGE_PLAN, STAGE_BREAKDOWN, STAGE_IMPLEMENT,
                 STAGE_VERIFY)

#: The seven Definition of Ready checks (ADR-092). They are human checks with no
#: implementation, so `check_registry.REMOVED` does not list them; a stored
#: generation that lists them still judges them from its own lists.
READY_CHECKS = ("dor-summary-filled", "dor-problem-traces-up", "dor-behavior-is-gwt",
                "dor-traceability-ids", "dor-affected-surface-named", "dor-no-open-questions",
                "dor-approach-still-fits")

#: Each removed `compass.yml` key: what it set, and the decision record that
#: removed it. A key with a dot is one entry of a catalogue, `<catalogue>.<id>`.
SETTINGS = {
    "models": ("the model and effort of each tier", "ADR-090"),
    "multiagent": ("where multiagent worktrees go and how many are allowed", "ADR-090"),
    "living_spec": ("when a landing re-derived the living spec, docs/system-spec.md",
                    "ADR-091"),
    "artifacts": ("the documents an issue owes and their headings", "ADR-091"),
    "approaches": ("the delivery approaches, the mode of each stage and the gates each owes",
                   "ADR-092"),
    **{f"stages.{stage}": (f"the legacy {stage} stage, which the four-stage path does not "
                           f"keep", "ADR-092") for stage in LEGACY_STAGES},
    "rules.caps": ("the caps rule set, which limited the worktrees of a critical change",
                   "ADR-092"),
    **{f"checks.{check}": ("a Definition of Ready check, which a path issue does not owe",
                           "ADR-092") for check in READY_CHECKS},
}

#: The rule set and the rule effects whose only use was to pick an approach. No
#: configuration's approach is read on the four-stage path (ADR-092), so a
#: comparison that takes the approaches from one side (`with_removed_from`) takes
#: these from it too: the shapes that lean towards an approach, and each rule whose
#: effects all raise, forbid or fix the stages of one.
APPROACH_RULE_SETS = ("default_shapes",)
APPROACH_EFFECTS = ("force_minimum_approach", "forbid_approach", "never_skip")

#: The fields that list check ids, per catalogue. A project layer that names a removed
#: check in one of them has the id left out, so the merge finds no unknown reference.
#: `merge.REFERENCES` holds the same fields; `artifacts` is removed as a whole.
CHECK_LIST_FIELDS = {"gates": ("checks",), "stages": ("entry", "exit")}

#: Each removed capability (a key under `capabilities:`): what it turned on,
#: and the decision record that removed it. A project names it only when it
#: turns the capability on.
CAPABILITIES: dict = {
    "artifact-freshness": ("whether a change to a document marked the documents that "
                           "depend on it stale", "ADR-091"),
}


def _matches(argv, tokens):
    words = [t for t in tokens if not t.startswith("--")]
    flags = [t for t in tokens if t.startswith("--")]
    if list(argv[:len(words)]) != words:
        return False
    rest = argv[len(words):]
    return all(any(a == f or a.startswith(f + "=") for a in rest) for f in flags)


def removal_of(tokens):
    """`(release, decision record)` when the command `tokens` names was removed, or None."""
    for removed, _name, _instead, adr in COMMANDS:
        if _matches(list(tokens), removed):
            return RELEASE, adr
    return None


def line_for(argv):
    """The line a parse error adds for a removed verb or flag, or None."""
    for tokens, name, instead, adr in COMMANDS:
        if _matches(list(argv), tokens):
            return (f"compass: '{name}' was removed in {RELEASE} ({adr}): {REASONS[adr]}; "
                    f"{instead}.")
    return None


def _note(key, what, adr):
    return (f"'{key}' ({what}) was removed in {RELEASE} ({adr}) and is not "
            f"read; delete it from compass.yml")


#: Each removed switch inside a settings key, as `key.switch`: what it turned on, and
#: the decision record that removed it. A project names it only when it turns it on.
SWITCHES = {
    "github_labels.page": ("posting the issue page as a comment on the linked GitHub issue",
                           "ADR-091"),
}


def setting_note(key):
    """The lint message for a removed `compass.yml` key."""
    return _note(key, *SETTINGS[key])


def capability_note(name):
    """The lint message for a removed capability a project turns on."""
    return _note(f"capabilities.{name}", *CAPABILITIES[name])


def _removed_checks():
    return {key.split(".", 1)[1] for key in SETTINGS if key.startswith("checks.")}


def _items(value):
    """The ids a list field names, written plain or as `{add, remove}`."""
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return [item for part in ("add", "remove")
                for item in (value.get(part) if isinstance(value.get(part), list) else [])]
    return []


def _named_checks(doc):
    """The removed check ids a layer names in a field that lists checks."""
    removed, found = _removed_checks(), set()
    for catalogue, fields in CHECK_LIST_FIELDS.items():
        entries = doc.get(catalogue)
        for entry in (entries.values() if isinstance(entries, dict) else ()):
            if not isinstance(entry, dict):
                continue
            changes = entry.get("set")
            for holder in (entry, changes if isinstance(changes, dict) else {}):
                for field in fields:
                    found |= {item for item in _items(holder.get(field)) if item in removed}
    return found


def removed_key(catalogue, entry_id):
    """The removed `compass.yml` key that the entry `<catalogue>.<entry_id>` falls
    under, such as `approaches` or `stages.plan`, or None when it is kept."""
    if catalogue in SETTINGS:
        return catalogue
    key = f"{catalogue}.{entry_id}"
    return key if key in SETTINGS else None


def with_removed_from(config, like):
    """A copy of the resolved configuration `config` in which every removed entry
    is the one `like` holds (or is absent when `like` has none), and no field that
    lists checks names a removed check. Two configurations compared after this
    differ only in what a project layer can still change."""
    import copy
    out = copy.deepcopy(config)
    for catalogue in {key.split(".", 1)[0] for key in SETTINGS}:
        entries, other = out.get(catalogue), (like.get(catalogue) or {})
        if catalogue in SETTINGS:
            if catalogue in like:
                out[catalogue] = copy.deepcopy(like[catalogue])
            else:
                out.pop(catalogue, None)
            continue
        if not isinstance(entries, dict):
            continue
        for entry_id in set(entries) | set(other):
            if removed_key(catalogue, entry_id) is None:
                continue
            if entry_id in other:
                entries[entry_id] = copy.deepcopy(other[entry_id])
            else:
                entries.pop(entry_id, None)
    _approach_rules_from(out, like)
    removed = _removed_checks()
    for catalogue, fields in CHECK_LIST_FIELDS.items():
        for entry in (out.get(catalogue) or {}).values():
            for field in fields:
                if isinstance(entry, dict) and isinstance(entry.get(field), list):
                    entry[field] = [item for item in entry[field] if item not in removed]
    return out


def _approach_rules_from(out, like):
    """Give `out` the approach-picking rules of `like` in place of its own
    (`APPROACH_RULE_SETS`, `APPROACH_EFFECTS`), with the hit policy each needs."""
    import copy
    rules, other = out.get("rules"), like.get("rules") or {}
    if not isinstance(rules, dict):
        return
    for set_id in APPROACH_RULE_SETS:
        if set_id in other:
            rules[set_id] = copy.deepcopy(other[set_id])
        else:
            rules.pop(set_id, None)

    def picks(rule):
        then = rule.get("then") if isinstance(rule, dict) else None
        return isinstance(then, dict) and bool(then) and set(then) <= set(APPROACH_EFFECTS)

    for set_id in set(rules) | set(other):
        if set_id in APPROACH_RULE_SETS:
            continue
        mine, theirs = rules.get(set_id), other.get(set_id)
        if not isinstance(mine, dict) or not isinstance(mine.get("rules"), dict):
            continue
        body = mine["rules"]
        for rule_id in [r for r, rule in body.items() if picks(rule)]:
            del body[rule_id]
        if isinstance(theirs, dict):
            for rule_id, rule in (theirs.get("rules") or {}).items():
                if picks(rule):
                    body[rule_id] = copy.deepcopy(rule)
                    for effect in rule["then"]:
                        if effect in (theirs.get("hit") or {}):
                            mine.setdefault("hit", {})[effect] = theirs["hit"][effect]


def _holds(doc, key):
    """True when a project layer holds the removed key `key`."""
    if "." not in key:
        return key in doc
    catalogue, entry_id = key.split(".", 1)
    entries = doc.get(catalogue)
    return isinstance(entries, dict) and entry_id in entries


def _without_checks(value, removed):
    """A list field, plain or `{add, remove}`, with the removed check ids left out."""
    if isinstance(value, list):
        return [item for item in value if item not in removed]
    if isinstance(value, dict):
        return {part: ([item for item in items if item not in removed]
                       if isinstance(items, list) else items)
                for part, items in value.items()}
    return value


def _empty(value):
    return value == [] or (isinstance(value, dict) and not any(value.values()))


def without_removed(doc):
    """A copy of a project layer's document with every removed key left out: a
    removed top-level key, a removed catalogue entry, and a removed check id in a
    field that lists checks. A `set:` change that named only removed checks is
    left out whole, so the inherited list stays as it is. Nothing here judges the
    value of what it leaves out: a value the old schema refused must not make the
    project file invalid. A parent or an issue layer is never passed here."""
    if not isinstance(doc, dict):
        return doc
    out = {key: value for key, value in doc.items() if key not in SETTINGS}
    removed = _removed_checks()
    for catalogue in {key.split(".", 1)[0] for key in SETTINGS if "." in key}:
        entries = out.get(catalogue)
        if not isinstance(entries, dict):
            continue
        out[catalogue] = {entry_id: entry for entry_id, entry in entries.items()
                          if f"{catalogue}.{entry_id}" not in SETTINGS}
    for catalogue, fields in CHECK_LIST_FIELDS.items():
        entries = out.get(catalogue)
        if not isinstance(entries, dict):
            continue
        kept = {}
        for entry_id, entry in entries.items():
            if not isinstance(entry, dict):
                kept[entry_id] = entry
                continue
            entry = dict(entry)
            for field in fields:
                if field in entry:
                    entry[field] = _without_checks(entry[field], removed)
            changes = entry.get("set")
            if isinstance(changes, dict):
                changes = dict(changes)
                for field in fields:
                    if field in changes:
                        before = changes[field]
                        changes[field] = _without_checks(before, removed)
                        if _empty(changes[field]) and not _empty(before):
                            del changes[field]
                if changes or not entry["set"]:
                    entry["set"] = changes
                else:
                    del entry["set"]
            if entry or not entries[entry_id]:
                kept[entry_id] = entry
        out[catalogue] = kept
    return out


def setting_findings(chain):
    """`(layer, path, message)` for each removed key or capability a project layer holds.
    A removed check named only in a list of checks is reported under its own key."""
    out = []
    for layer in chain:
        if layer.kind != "project" or not isinstance(layer.doc, dict):
            continue
        named = _named_checks(layer.doc)
        out += [(layer, key, setting_note(key)) for key in SETTINGS
                if _holds(layer.doc, key)
                or (key.startswith("checks.") and key.split(".", 1)[1] in named)]
        for path, (what, adr) in SWITCHES.items():
            key, switch = path.split(".", 1)
            held = layer.doc.get(key)
            if isinstance(held, dict) and held.get(switch) is True:
                out.append((layer, path, _note(path, what, adr)))
        capabilities = layer.doc.get("capabilities")
        if isinstance(capabilities, dict):
            out += [(layer, f"capabilities.{name}", capability_note(name))
                    for name in CAPABILITIES if capabilities.get(name) is True]
    return out
