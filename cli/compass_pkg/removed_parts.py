# compass_pkg.removed_parts - the verbs, flags and settings 9.0.0 removed (ADR-090)
"""What 9.0.0 removed with the stage agents, named the same way by every reader.

9.0.0 runs an issue in one session (ADR-090). The verbs and flags that
dispatched agents, recorded subtasks, mapped model tiers, stored execution
profiles or started headless sessions are gone. A command line that still
names one fails to parse as an unknown command, and `line_for` gives the one
line the parse error adds. Two `compass.yml` keys stay valid and are not
read; `compass policy lint` names them through `SETTINGS`.
"""
# DEPENDENCY: standard library only. Imported by compass_pkg.aliases (the parse
# error) and compass_pkg.policy_lint (the removed settings).
from __future__ import annotations

RELEASE = "9.0.0"
ADR = "ADR-090"

#: Each removed command line, as tokens, and what replaces it. A token that
#: starts with `--` is a flag found anywhere after the tokens before it.
COMMANDS = (
    (("run",), "compass run",
     "run the stage in your own session"),
    (("issue", "subtask"), "compass issue subtask",
     "the session builds each unit of the distribution map itself"),
    (("profile",), "compass profile", "nothing replaces it"),
    (("approach", "show", "--model"), "compass approach show --model",
     "a stage command passes no model"),
    (("approach", "show", "--effort"), "compass approach show --effort",
     "a stage command passes no effort"),
    (("retro", "--models"), "compass retro --models",
     "no subtask records a model tier"),
)

#: The ten agent names 9.0.0 removed with the `agents/` folder. The shipped
#: catalogue still names them as document owners, and an older decision ledger
#: as deciders, so both still read.
AGENT_NAMES = ("architect", "builder", "orchestrator", "planner", "product-marketer",
               "product-owner", "reviewer", "router", "spec-author", "verifier")

#: Each removed `compass.yml` key, and what it set.
SETTINGS = {
    "models": "the model and effort of each tier",
    "multiagent": "where multiagent worktrees go and how many are allowed",
}


def _matches(argv, tokens):
    words = [t for t in tokens if not t.startswith("--")]
    flags = [t for t in tokens if t.startswith("--")]
    if list(argv[:len(words)]) != words:
        return False
    rest = argv[len(words):]
    return all(any(a == f or a.startswith(f + "=") for a in rest) for f in flags)


def line_for(argv):
    """The line a parse error adds for a removed verb or flag, or None."""
    for tokens, name, instead in COMMANDS:
        if _matches(list(argv), tokens):
            return (f"compass: '{name}' was removed in {RELEASE} ({ADR}): Compass runs "
                    f"each issue in one session; {instead}.")
    return None


def setting_note(key):
    """The lint message for a removed `compass.yml` key."""
    return (f"'{key}' ({SETTINGS[key]}) was removed in {RELEASE} ({ADR}) and is not "
            f"read; delete it from compass.yml")


def setting_findings(chain):
    """`(layer, key, message)` for each removed key a project layer holds."""
    return [(layer, key, setting_note(key)) for layer in chain
            if layer.kind == "project" and isinstance(layer.doc, dict)
            for key in SETTINGS if key in layer.doc]
