# compass_pkg.removed_parts - the verbs, flags and settings 9.0.0 removed (ADR-090)
"""What 9.0.0 removed with the stage agents, named the same way by every reader.

9.0.0 runs an issue in one session (ADR-090). The verbs and flags that
dispatched agents, recorded subtasks, mapped model tiers, stored execution
profiles or started headless sessions are gone. A command line that still
names one fails to parse as an unknown command, and `line_for` gives the one
line the parse error adds.
"""
# DEPENDENCY: standard library only. Imported by compass_pkg.aliases (the parse
# error).
from __future__ import annotations

RELEASE = "9.0.0"
ADR = "ADR-090"

#: Each removed command line, as tokens, and what replaces it. A token that
#: starts with `--` is a flag found anywhere after the tokens before it.
COMMANDS = (
    (("run",), "compass run",
     "run the stage in your own session"),
    (("profile",), "compass profile", "nothing replaces it"),
)

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
