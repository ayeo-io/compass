# =============================================================================
# The refusal registry - one shape, one place, for every hook and CLI refusal.
# =============================================================================
# Every refusal used to be a string written by hand at its call site, so
# nothing checked them against each other, and each drift - a retired word,
# an advertised bypass, a raw machine key - was fixed one at a time (spec
# D38). This module is the one place a refusal's wording lives. A call site
# passes a reason code and named parameters; `render()` is the only thing
# that turns them into text.
#
# SHAPE (RT-1). Three lines, in order:
#   Blocked: <what>
#   Why: <reason>
#   Fix: <exact next action> [<code>]
# Plain text - no colour, no markdown - because a refusal is read by a model
# as often as a person (RT-9 also caps it at 60 words, since it lands in
# context).
#
# THE PRIVATE VERB. `compass _refusal <code> key=value ...` renders one
# refusal to stdout, and `compass _refusal --list` renders every code's
# template, unfilled, for docs/refusal-codes.md - generated, so it cannot
# drift from the registry. hooks/pre-tool.sh calls `render()` here directly
# (the narrow `import compass_pkg` every other reader in that hook makes),
# rather than through the verb - `cli/compass` imports every command module
# at start-up, which is a heavier and less portable thing to ask of a
# refusal than the rest of the hook asks of anything else. The one place
# python3 cannot be assumed at all - the reader that discovers python3
# itself is missing - carries a static copy of the `python-missing`
# rendering in shell; tests/test_refusal_registry.py checks the two stay
# identical.
#
# DEPENDENCY: none. This module is Python 3 standard library - `render()`
# is str.format() over the templates above.
# =============================================================================
from __future__ import annotations

from compass_pkg.core import CompassError

#: code -> {"what": ..., "why": ..., "fix": ...}. Each value is a
#: str.format() template; the named fields it reads are the keyword
#: parameters `render()` needs for that code. A call site that passes a
#: field the template does not use, or omits one it does, fails loudly -
#: str.format() raises rather than silently dropping text - because that
#: means the call site and the registry have drifted apart.
REFUSALS: dict[str, dict[str, str]] = {
    "python-missing": {
        "what": "edit to {target} (tool: {tool})",
        "why": "python3 was not found on the PATH, so Compass cannot check "
               "whether this edit is allowed.",
        "fix": "install python3 (3.9+) or put it on PATH, then retry.",
    },
    "reader-failed": {
        "what": "edit to {target} (tool: {tool})",
        "why": "the {reader} could not run. {cause}{detail}",
        "fix": "fix the install and re-try - this is not about your edit.",
    },
    "config-invalid": {
        "what": "edit to {target} (tool: {tool})",
        "why": "'.compass/config.yml' could not be read: {detail}",
        "fix": "fix .compass/config.yml and re-try.",
    },
    "not-initialised": {
        "what": "this edit",
        "why": "no issue has been assessed yet - {detail}.",
        "fix": "run /compass:assess before changing code, or "
               "/compass:quick-fix for a small, low-risk change.",
    },
    "bad-current-task": {
        "what": "this edit",
        "why": "'.compass/current-task' names '{slug}', which is not one "
               "path segment - a slug names a directory directly under "
               ".compass/work/.",
        "fix": "fix .compass/current-task to name a real issue slug, then "
               "retry.",
    },
    "no-delivery-approach": {
        "what": "this edit",
        "why": "issue '{slug}' has no delivery-approach.md - its "
               "assessment did not finish.",
        "fix": "run /compass:assess.",
    },
    "no-acceptance-criteria": {
        "what": "edit to {target} (tool: {tool})",
        "why": "the acceptance-before-code guardrail blocks this: define: "
               "full is set but manifest.yml has no scenarios.",
        "fix": "add the scenarios to acceptance-criteria.md and manifest.yml "
               "(compass scenario add), or re-frame as a spike if this is "
               "exploratory.",
    },
    "red-unsigned": {
        "what": "this edit",
        "why": "the red record for issue '{slug}' carries no identity - no "
               "content_digest - and this project needs one for records "
               "written since records_signed_since: {since_date}.",
        "fix": "run compass tdd-red -- <your failing test command>.",
    },
    "red-marker-no-record": {
        "what": "this edit",
        "why": "the .red marker for issue '{slug}' has no matching record "
               "in evidence/ - the marker alone is not evidence.",
        "fix": "run compass tdd-red -- <your failing test command>.",
    },
    "no-red-on-record": {
        "what": "edit to {target} (tool: {tool}, guarded by {guard})",
        "why": "no failing test is on record for issue '{slug}' - the "
               "red-before-green strategy applies here.",
        "fix": "run compass tdd-red -- <your failing test command>, then "
               "retry this edit.",
    },
}


def codes() -> list[str]:
    """Every reason code, in a stable order.

    What `_refusal --list`, the generated docs page, and the call-site
    coverage check all walk.
    """
    return sorted(REFUSALS)


def render(code: str, **params) -> str:
    """The three-line refusal text for `code`, filled with `params`.

    Raises `KeyError` for a code the registry does not define, or for a
    template field `params` does not give - both mean a call site and the
    registry have drifted apart, and failing loudly is how that gets found.
    """
    try:
        entry = REFUSALS[code]
    except KeyError:
        raise KeyError(f"no such refusal code: {code!r}") from None
    what = entry["what"].format(**params)
    why = entry["why"].format(**params)
    fix = entry["fix"].format(**params)
    return f"Blocked: {what}\nWhy: {why}\nFix: {fix} [{code}]"


def cmd_refusal(args):
    """`compass _refusal <code> key=value ...` and `compass _refusal
    --list`. Private - hooks/pre-tool.sh and docs generation call it; it
    adds no public verb."""
    if getattr(args, "list", False):
        for code in codes():
            entry = REFUSALS[code]
            print(f"### `{code}`\n")
            print(f"**Blocked:** {entry['what']}")
            print(f"**Why:** {entry['why']}")
            print(f"**Fix:** {entry['fix']}\n")
        return 0
    code = getattr(args, "code", None)
    if not code:
        raise CompassError(
            "compass _refusal: give a reason code, e.g. "
            "'compass _refusal no-red-on-record slug=demo target=x'.")
    params = {}
    for kv in getattr(args, "params", None) or []:
        if "=" not in kv:
            raise CompassError(
                f"compass _refusal: expected key=value, got {kv!r}.")
        key, _, value = kv.partition("=")
        params[key] = value
    try:
        text = render(code, **params)
    except KeyError as exc:
        raise CompassError(f"compass _refusal: {exc}") from exc
    print(text)
    return 0
