# compass_pkg.removed_parts - the verbs, flags and settings 9.0.0 removed (ADR-090, ADR-091)
"""What 9.0.0 removed, named the same way by every reader.

9.0.0 runs an issue in one session (ADR-090). The verbs and flags that
dispatched agents, recorded subtasks, mapped model tiers, stored execution
profiles or started headless sessions are gone. 9.0.0 also keeps one issue
document, the acceptance criteria (ADR-091), so the verbs that wrote or
checked the other documents are gone.

A command line that still names a removed verb or flag fails to parse as an
unknown command, and `line_for` gives the one line the parse error adds.
Each removed `compass.yml` key and capability stays valid and is not read;
`compass policy lint` names it through `setting_findings`. Each entry names
the decision record that removed it.
"""
# DEPENDENCY: standard library only. Imported by compass_pkg.aliases (the parse
# error), compass_pkg.merge (the catalogue a project layer can no longer change)
# and compass_pkg.policy_lint (the removed settings).
from __future__ import annotations

RELEASE = "9.0.0"

#: Why each decision record removed its parts, as the parse error says it.
REASONS = {
    "ADR-090": "Compass runs each issue in one session",
    "ADR-091": "Compass needs only the acceptance criteria",
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

#: Each removed `compass.yml` key: what it set, and the decision record that
#: removed it.
SETTINGS = {
    "models": ("the model and effort of each tier", "ADR-090"),
    "multiagent": ("where multiagent worktrees go and how many are allowed", "ADR-090"),
    "living_spec": ("when a landing re-derived the living spec, docs/system-spec.md",
                    "ADR-091"),
    "artifacts": ("the documents an issue owes and their headings", "ADR-091"),
}

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


def setting_findings(chain):
    """`(layer, path, message)` for each removed key or capability a project layer holds."""
    out = []
    for layer in chain:
        if layer.kind != "project" or not isinstance(layer.doc, dict):
            continue
        out += [(layer, key, setting_note(key)) for key in SETTINGS if key in layer.doc]
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
