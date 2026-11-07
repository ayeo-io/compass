# compass_pkg.removed_parts - the verbs, flags and settings 9.0.0 removed (ADR-090 to ADR-094)
"""What 9.0.0 removed, named the same way by every reader.

9.0.0 runs an issue in one session (ADR-090). The verbs and flags that
dispatched agents, recorded subtasks, mapped model tiers, stored execution
profiles or started headless sessions are gone. 9.0.0 also keeps one issue
document, the acceptance criteria (ADR-091), so the verbs that wrote or
checked the other documents are gone. 9.0.0 runs every new delivery issue on
one four-stage path (ADR-092), so the delivery approaches, the legacy stages
the path does not keep, the caps rule set and the Definition of Ready checks
are gone from what a project can configure. 9.0.0 keeps only what a reviewer
of one change needs (ADR-093), so the reports across issues, the brief
ingest, the HTML board, the GitHub label sync, the readiness measure and the
follow-up that blocks another issue (`follow-up add --target`) are gone.
9.0.0 runs one fixed set of checks (ADR-094), so an issue has no
configuration layer of its own: `compass issue configure` and `approach
evaluate --reset-config` are gone, and a manifest's `config:` is not read.
The verbs that compared, moved, migrated or tested configurations are gone
with the layers: `compass policy diff`, `policy update`, `policy migrate`
(with `--words` and `--undo`), `preset init` and `preset test`.

A command line that still names a removed verb or flag fails to parse as an
unknown command, and `line_for` gives the one line the parse error adds.
Each removed `compass.yml` key and capability stays valid and is not read;
`compass policy lint` names it through `setting_findings`, with what replaces
it from `REPLACEMENTS` (ADR-098). Since ADR-094 no
layer merges, so a removed catalogue key is not read at all.
`with_mapped_stages` reads a gate that a project's governance copy places at a
legacy stage at the path stage that shows it. Each entry
names the decision record that removed it.
"""
# DEPENDENCY: standard library (copy, fnmatch, re); compass_pkg.stable_ids (constants only). Imported by
# compass_pkg.aliases (the parse error), compass_pkg.effective (the git parent scheme and
# the legacy stage mapping of a governance copy), compass_pkg.settings_lint (the removed
# settings) and compass_pkg.decisions_taken (the removed agent names).
from __future__ import annotations

import copy
import fnmatch
import re

from compass_pkg.stable_ids import (LEGACY_TO_PATH, STAGE_BREAKDOWN, STAGE_DEFINE,
                                    STAGE_IMPLEMENT, STAGE_PLAN, STAGE_REFINE, STAGE_VERIFY)

RELEASE = "9.0.0"

#: The start of a git parent's layer name, `github:<owner>/<repo>@<ref>#<sha>`
#: (8.x `parents.ref_label` wrote it). 9.0.0 refuses one (L-PARENT-REMOVED).
GIT_PARENT_SCHEME = "github:"
#: What a project that extends a git parent does now. A team parent can hold
#: checks its projects owe, so dropping it would lower what each project owes
#: without its own file showing it (ADR-094, open question 6).
GIT_PARENT_FIX = ("Move the checks the team parent adds into the tighten-only settings of "
                  "compass.yml (signoff_labels, require_evidence, agent_review, "
                  "project_checks, capabilities) and delete extends:, or stay on Compass "
                  "8.x until the 9.0.0 upgrade command (#359) rewrites the file")


def drops_removed(kind, name):
    """True when `setting_findings` names what 9.0.0 removed from the layer of
    `kind` named `name`: the project's `compass.yml`, and a git parent. The
    settings lint passes the project's file only, since 9.0.0 refuses a git
    parent (ADR-094)."""
    return kind == "project" or (kind == "parent" and isinstance(name, str)
                                 and name.startswith(GIT_PARENT_SCHEME))


#: Why each decision record removed its parts, as the parse error says it.
REASONS = {
    "ADR-090": "Compass runs each issue in one session",
    "ADR-091": "Compass needs only the acceptance criteria",
    "ADR-092": "Compass runs every delivery issue on one four-stage path",
    "ADR-093": "Compass keeps only what a reviewer of one change needs",
    "ADR-094": "Compass runs one fixed set of checks",
    "ADR-098": "Compass ends the 8.x legacy readers",
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
    (("intent", "ingest"), "compass intent ingest",
     "write the Summary and Intent of acceptance-criteria.md from the brief", "ADR-093"),
    (("retro",), "compass retro",
     "sdd-bench is the measurement; compass check and compass approach show read one issue",
     "ADR-093"),
    (("rework-scan",), "compass rework-scan", "nothing replaces it", "ADR-093"),
    (("issue", "friction"), "compass issue friction", "nothing replaces it", "ADR-093"),
    (("board",), "compass board", "compass flow lists every issue", "ADR-093"),
    (("flow", "--html"), "compass flow --html",
     "compass flow prints the issues; no page is written", "ADR-093"),
    (("issue", "github", "sync"), "compass issue github sync",
     "compass issue link set keeps the link; no label is written", "ADR-093"),
    (("readiness",), "compass readiness",
     "nothing measures the repository; the hooks and compass check guard each change",
     "ADR-093"),
    (("init", "--readiness"), "compass init --readiness",
     "compass init sets up the project; nothing measures it", "ADR-093"),
    (("follow-up", "add", "--target"), "compass follow-up add --target",
     "link the follow-up to a GitHub issue with --github", "ADR-093"),
    (("issue", "configure"), "compass issue configure",
     "the issue layer was removed; record a waiver with compass waiver add", "ADR-094"),
    (("approach", "evaluate", "--reset-config"), "compass approach evaluate --reset-config",
     "an issue has no config layer", "ADR-094"),
    (("policy", "diff"), "compass policy diff",
     "one check set ships; compass policy show prints it with its digest", "ADR-094"),
    (("policy", "update"), "compass policy update",
     "one check set ships with each release; nothing to move between", "ADR-094"),
    (("preset", "init"), "compass preset init",
     "presets were removed; a project sets tighten-only settings in compass.yml", "ADR-094"),
    (("preset", "test"), "compass preset test",
     "presets were removed; a project sets tighten-only settings in compass.yml", "ADR-094"),
    (("preset",), "compass preset",
     "presets were removed; a project sets tighten-only settings in compass.yml", "ADR-094"),
    # The two flags come before the verb, so each gets its own line.
    (("policy", "migrate", "--words"), "compass policy migrate --words",
     "compass.yml is read as settings only; the upgrade guide names the 9.0.0 settings",
     "ADR-094"),
    (("policy", "migrate", "--undo"), "compass policy migrate --undo",
     "run it on 8.x before upgrading; the upgrade guide names the 9.0.0 settings",
     "ADR-094"),
    (("policy", "migrate"), "compass policy migrate",
     "run compass policy migrate on 8.x; the upgrade guide names the 9.0.0 settings",
     "ADR-094"),
    (("approach", "evaluate", "--offline"), "compass approach evaluate --offline",
     "git parents were removed; nothing is fetched", "ADR-094"),
    (("policy", "lint", "--offline"), "compass policy lint --offline",
     "git parents were removed; nothing is fetched", "ADR-094"),
    (("policy", "show", "--offline"), "compass policy show --offline",
     "git parents were removed; nothing is fetched", "ADR-094"),
    (("policy", "lint", "--issue"), "compass policy lint --issue",
     "an issue has no config layer; the classifier was removed", "ADR-094"),
    (("policy", "lint", "--exhaustive"), "compass policy lint --exhaustive",
     "an issue has no config layer; the classifier was removed", "ADR-094"),
)

#: The ten agent names 9.0.0 removed with the `agents/` folder. The shipped
#: catalogue still names them as document owners, and an older decision ledger
#: as deciders, so both still read.
AGENT_NAMES = ("architect", "builder", "orchestrator", "planner", "product-marketer",
               "product-owner", "reviewer", "router", "spec-author", "verifier")


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
#: removed it. `governance_drift` went with the drift report (ADR-098). A key with a dot is one entry of a catalogue, `<catalogue>.<id>`.
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
    "prices": ("the dollars per million tokens that priced an issue's usage", "ADR-093"),
    "github_labels": ("whether Compass wrote an issue's labels to its linked GitHub issue",
                      "ADR-093"),
    "readiness": ("the readiness signals compass readiness measured and the floor an "
                  "autonomous issue had to meet", "ADR-093"),
    "governance_drift": ("whether compass policy lint failed when a governance copy "
                         "lacked a rule or check the framework ships", "ADR-098"),
}

#: The rule set and the rule effects whose only use was to pick an approach. No
#: configuration's approach is read on the four-stage path (ADR-092), so a
#: comparison that takes the approaches from one side (`with_removed_from`) takes
#: these from it too: the shapes that lean towards an approach, and each rule whose
#: effects all raise, forbid or fix the stages of one.
APPROACH_RULE_SETS = ("default_shapes",)
APPROACH_EFFECTS = ("force_minimum_approach", "forbid_approach", "never_skip")

#: Each removed effect of a shipped rule a project layer can still restate, keyed by
#: `rules.<set>.rules.<id>.then.<effect>`. `RP-FLOOR-002` forced the define stage to
#: thorough, and the four-stage path has no stage modes (ADR-092); its skill stays.
EFFECTS = {
    "rules.floors.rules.RP-FLOOR-002.then.require_phase": (
        "the stage RP-FLOOR-002 forced to thorough, which the four-stage path has no "
        "mode for", "ADR-092"),
}

#: The issue-layer key that picks one of the 8.x approaches (ADR-092). Over a
#: configuration that does not declare the approach it is left out of the merge.
#: 9.0.0 resolves no issue layer (ADR-094); only `compass policy lint --issue`
#: still reads one, until the layers go.
ISSUE_KEYS = {
    "approach": ("the delivery approach the issue picked, which the configuration does "
                 "not declare", "ADR-092"),
}

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


#: The `extends:` value `compass migrate` replaces with `acceptance_strategy: off`.
#: A pin of the shipped default below @8 keeps `S17` off (ADR-094 open question 7),
#: so the setting that keeps it off replaces the pin (ADR-098 decision 7).
STRATEGY_OFF = "acceptance_strategy: {state: off, reason: ...}"

#: What replaces each removed `compass.yml` key, keyed as `compass policy lint`
#: names it: `(settings, migrated)`. `settings` is the tuple of settings that
#: replace the key, empty when nothing does. `migrated` is True when `compass
#: migrate` rewrites the key (ADR-098 decision 6). The `extends` rows are keyed
#: by the major the value pins (`extends_row`); a key with `*` names a rule
#: path (`replacement_of`). Every key of `settings_lint.REMOVED`, `SETTINGS`,
#: `SETTING_FIELDS`, `SWITCHES`, `EFFECTS` and `CAPABILITIES` has a row, and
#: `tests/test_lint_names_replacements.py` fails on a missing one.
REPLACEMENTS = {
    # The catalogs and keys of ADR-094 (`settings_lint.REMOVED`).
    "dimensions": ((), False),
    "stages": ((), False),
    "rules": (("require_evidence",), True),
    "checks": (("project_checks",), True),
    "gates": (("signoff_labels", "project_checks"), True),
    "vocabulary": ((), False),
    "extends": ((), False),
    "extends@6": ((STRATEGY_OFF,), True),
    "extends@7": ((STRATEGY_OFF,), True),
    "extends@8": ((), True),
    "preset": ((), True),
    "preset_index": ((), True),
    "approvers.project-waiver": ((), True),
    # The keys of ADR-090 to ADR-093 and ADR-098 (`SETTINGS`).
    "models": ((), True),
    "multiagent": ((), True),
    "living_spec": ((), True),
    "artifacts": ((), True),
    "approaches": ((), True),
    **{f"stages.{stage}": ((), False) for stage in LEGACY_STAGES},
    "rules.caps": ((), False),
    **{f"checks.{check}": ((), False) for check in READY_CHECKS},
    "prices": ((), True),
    "github_labels": ((), True),
    "readiness": ((), True),
    "governance_drift": ((), True),
    # `SWITCHES`, `SETTING_FIELDS`, `EFFECTS` and `CAPABILITIES`.
    "github_labels.page": ((), True),
    **{f"project.{field}": ((), True) for field in (
        "build_command", "lint_command", "format_check_command", "typecheck_command",
        "secret_scan", "structured_logging")},
    "rules.floors.rules.RP-FLOOR-002.then.require_phase": ((), True),
    "capabilities.artifact-freshness": ((), False),
    # An approach effect of any rule, or of a rule set's hit policy (VD-008).
    **{f"rules.*.{effect}": ((), True) for effect in APPROACH_EFFECTS},
}


def extends_row(value):
    """The `REPLACEMENTS` key for an `extends:` of `value`: `extends@6` for a pin
    of the shipped default at @6 or below, `extends@7` for @7, `extends@8` for @8
    or later or no pin, and `extends` for any other value."""
    ref = value.get("from") if isinstance(value, dict) else value
    found = re.fullmatch(r"compass:default(?:@(\d+))?", ref) if isinstance(ref, str) else None
    if not found:
        return "extends"
    major = int(found.group(1)) if found.group(1) else None
    if major is None or major >= 8:
        return "extends@8"
    return "extends@7" if major == 7 else "extends@6"


def replacement_of(path, value=None):
    """`(settings, migrated)` from `REPLACEMENTS` for the removed key at `path`.
    `value` is the key's value, which picks the `extends` row."""
    key = extends_row(value) if path == "extends" else path
    if key in REPLACEMENTS:
        return REPLACEMENTS[key]
    for pattern, row in REPLACEMENTS.items():
        if "*" in pattern and fnmatch.fnmatchcase(path, pattern):
            return row
    raise KeyError(f"no REPLACEMENTS row for the removed key '{path}'")


def replacement_text(path, value=None):
    """The settings that replace the key at `path`, as `--json` gives them, or
    None when nothing replaces it."""
    settings, _ = replacement_of(path, value)
    return " or ".join(settings) if settings else None


def removed_message(key, what, adr, reason=None, value=None):
    """The `L-SETTING-REMOVED` message for the removed key `key`: what it set,
    why it went, and what replaces it (ADR-098 decision 7)."""
    settings, migrated = replacement_of(key, value)
    text = f"'{key}' ({what}) was removed in {RELEASE} ({adr}): {reason or REASONS[adr]}."
    if settings:
        text += " Replacement: " + " or ".join(f"`{s}`" for s in settings) + "."
    else:
        text += " Removed: nothing replaces it."
    if migrated:
        text += " `compass migrate` rewrites it."
    return text


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
    return removed_message(key, what, adr)


#: Each removed switch inside a settings key, as `key.switch`: what it turned on, and
#: the decision record that removed it. A project names it only when it turns it on.
SWITCHES = {
    "github_labels.page": ("posting the issue page as a comment on the linked GitHub issue",
                           "ADR-091"),
}


#: Each removed field of a settings key, as `key.field`: what it set, and the decision
#: record that removed it. A project names it with any value. Unlike a key of `SETTINGS`,
#: the merge keeps it: `project` is a settings key, not a catalogue, so `without_removed`
#: leaves it alone and lint only names it. `project.test_micro_command` is not here:
#: `compass tdd-red` and `tdd-green` still read it.
SETTING_FIELDS = {
    "project.build_command": ("the build command that compass readiness ran", "ADR-093"),
    "project.lint_command": ("the lint command that compass readiness ran", "ADR-093"),
    "project.format_check_command": ("the format check command that compass readiness ran",
                                     "ADR-093"),
    "project.typecheck_command": ("the type-check command that compass readiness ran",
                                  "ADR-093"),
    "project.secret_scan": ("the secret scan declaration that compass readiness read",
                            "ADR-093"),
    "project.structured_logging": ("the structured logging declaration that compass "
                                   "readiness read", "ADR-093"),
}


#: What an approach effect of a rule set, or its hit policy, set (ADR-092 decision 10).
APPROACH_EFFECT_NOTE = ("the approach a rule forces, forbids or fixes the stages of, which "
                        "the four-stage path does not read", "ADR-092")


def setting_note(key):
    """The lint message for a removed `compass.yml` key."""
    found = SETTINGS.get(key) or EFFECTS.get(key) or ISSUE_KEYS.get(key)
    if found is None and key.startswith("rules.") and key.rsplit(".", 1)[-1] in APPROACH_EFFECTS:
        found = APPROACH_EFFECT_NOTE
    return _note(key, *found)


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


def _holds(doc, key):
    """True when a project layer holds the removed key `key`."""
    if "." not in key:
        return key in doc
    catalogue, entry_id = key.split(".", 1)
    entries = doc.get(catalogue)
    return isinstance(entries, dict) and entry_id in entries


def _rule_bodies(doc, set_id, rule_id):
    """The bodies a layer gives rule `rule_id` of rule set `set_id`: a new rule
    set's own `rules:` map, or a `set:` change's `rules:` map (whole, or by `set:`
    or `add:`)."""
    entry = ((doc.get("rules") or {}) if isinstance(doc, dict) else {}).get(set_id)
    if not isinstance(entry, dict):
        return []
    maps = [entry.get("rules")]
    changes = entry.get("set")
    if isinstance(changes, dict):
        inner = changes.get("rules")
        maps.append(inner)
        if isinstance(inner, dict):
            maps += [inner.get("set"), inner.get("add")]
    return [m[rule_id] for m in maps if isinstance(m, dict) and isinstance(m.get(rule_id), dict)]


def held_effects(doc):
    """The `EFFECTS` keys a project layer `doc` sets."""
    out = []
    for key in EFFECTS:
        _, set_id, _, rule_id, _, effect = key.split(".", 5)
        if any(isinstance(body.get("then"), dict) and effect in body["then"]
               for body in _rule_bodies(doc, set_id, rule_id)):
            out.append(key)
    return out


def _rule_holders(entry):
    """The mappings of one rule set entry that can hold `rules:` and `hit:`: the
    entry itself (a new rule set, or a whole replacement) and its `set:` change."""
    changes = entry.get("set")
    return [entry] + ([changes] if isinstance(changes, dict) else [])


def _map_target(value):
    """The mapping a map field changes: `value` itself, or its `set:` in the
    `{set, remove}` form. None when it is not a mapping."""
    if not isinstance(value, dict):
        return None
    if value and set(value) <= {"set", "remove"}:
        return value.get("set") if isinstance(value.get("set"), dict) else None
    return value


def _approach_effects(doc, strip=False):
    """`rules.<set>.rules.<id>.then.<effect>` and `rules.<set>.hit.<effect>` for
    each `APPROACH_EFFECTS` effect, and its hit policy, a layer `doc` sets in a rule
    set other than the shapes. ADR-092 decision 10: no configuration's approach is
    read for a new assessment, so a project rule that forces, forbids or fixes the
    stages of an approach is not read either (VD-008 of #351). With `strip`, `doc`
    is changed in place: each effect is left out, a rule with no effect left is left
    out whole, and a field or a rule set entry left empty by that is left out too,
    so the inherited value stays."""
    out = []
    rules = doc.get("rules") if isinstance(doc, dict) else None
    if not isinstance(rules, dict):
        return out
    for set_id, entry in list(rules.items()):
        if set_id in APPROACH_RULE_SETS or not isinstance(entry, dict):
            continue
        found = _set_approach_effects(set_id, entry, strip)
        out += found
        if strip and found:
            if "set" in entry and not entry["set"]:
                del entry["set"]
            # A new rule set whose every rule and hit policy went names nothing.
            if not entry or ("set" not in entry and not entry.get("rules")
                             and not _map_target(entry.get("hit"))):
                del rules[set_id]
    if strip and not rules:
        del doc["rules"]
    return out


def _set_approach_effects(set_id, entry, strip):
    """`_approach_effects` for the one rule set entry `entry`, named `set_id`."""
    out = []
    for holder in _rule_holders(entry):
        for field in ("rules", "hit"):
            target = _map_target(holder.get(field))
            if target is None:
                continue
            found = []
            if field == "hit":
                found = [e for e in target if e in APPROACH_EFFECTS]
                out += [f"rules.{set_id}.hit.{e}" for e in found]
                for effect in found if strip else ():
                    del target[effect]
            else:
                for rule_id, body in list(target.items()):
                    then = body.get("then") if isinstance(body, dict) else None
                    effects = [e for e in then if e in APPROACH_EFFECTS] \
                        if isinstance(then, dict) else []
                    out += [f"rules.{set_id}.rules.{rule_id}.then.{e}" for e in effects]
                    found += effects
                    if strip and effects:
                        for effect in effects:
                            del then[effect]
                        if not then:
                            del target[rule_id]
            value = holder.get(field)
            if strip and found and not _map_target(value) \
                    and not (isinstance(value, dict) and value.get("remove")):
                del holder[field]
    return out


def mapped_stages(doc, config):
    """`(gate id, legacy stage, path stage)` for each gate a layer `doc` places at
    a legacy stage that neither the configuration below it, `config`, nor the
    layer itself declares. The merge reads such a gate at the path stage that
    shows the legacy one (`stable_ids.LEGACY_TO_PATH`, ADR-092). A copy of the
    9.0.0 governance files declares only the path stages, so a project guardrail
    it checks at `verify` is read at ship; a copy made before 9.0.0 declares the
    legacy stages and is read as it is."""
    own = (doc.get("stages") or {}) if isinstance(doc, dict) else {}
    held = {**((config or {}).get("stages") or {}), **(own if isinstance(own, dict) else {})}
    out = []
    for gate_id, entry in ((doc.get("gates") or {}) if isinstance(doc, dict) else {}).items():
        if not isinstance(entry, dict):
            continue
        body = entry.get("set") if isinstance(entry.get("set"), dict) else entry
        stage = body.get("stage")
        if isinstance(stage, str) and stage not in held and LEGACY_TO_PATH.get(stage, stage) != stage \
                and LEGACY_TO_PATH[stage] in held:
            out.append((gate_id, stage, LEGACY_TO_PATH[stage]))
    return out


def with_mapped_stages(doc, config):
    """A copy of `doc` with each gate `mapped_stages` names at its path stage."""
    found = mapped_stages(doc, config)
    if not found:
        return doc
    out = copy.deepcopy(doc)
    for gate_id, _, stage in found:
        entry = out["gates"][gate_id]
        body = entry.get("set") if isinstance(entry.get("set"), dict) else entry
        body["stage"] = stage
    return out


def setting_findings(chain):
    """`(layer, path, message)` for each removed key, field or capability a project
    layer or a git parent holds (`drops_removed`). A removed check named only in a list
    of checks is reported under its own key."""
    out = []
    for layer in chain:
        if not drops_removed(layer.kind, layer.name) or not isinstance(layer.doc, dict):
            continue
        named = _named_checks(layer.doc)
        switched = []
        for path, (what, adr) in SWITCHES.items():
            key, switch = path.split(".", 1)
            held = layer.doc.get(key)
            if isinstance(held, dict) and held.get(switch) is True:
                switched.append((layer, path, _note(path, what, adr)))
        # A key whose removed switch is on is named once, by that switch, so the
        # older decision record's note stays where it was (`github_labels.page`).
        under_switch = {path.split(".", 1)[0] for _layer, path, _note_text in switched}
        out += [(layer, key, setting_note(key)) for key in SETTINGS
                if key not in under_switch and (
                    _holds(layer.doc, key)
                    or (key.startswith("checks.") and key.split(".", 1)[1] in named))]
        out += [(layer, key, setting_note(key)) for key in held_effects(layer.doc)]
        out += [(layer, key, setting_note(key)) for key in _approach_effects(layer.doc)]
        out += switched
        for path, (what, adr) in SETTING_FIELDS.items():
            key, field = path.split(".", 1)
            held = layer.doc.get(key)
            if isinstance(held, dict) and field in held:
                out.append((layer, path, _note(path, what, adr)))
        capabilities = layer.doc.get("capabilities")
        if isinstance(capabilities, dict):
            out += [(layer, f"capabilities.{name}", capability_note(name))
                    for name in CAPABILITIES if capabilities.get(name) is True]
    return out
