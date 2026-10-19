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
from compass_pkg.project_settings import CONFLICT_FIX, CONFLICT_WHY

#: code -> {"what": ..., "why": ..., "fix": ...}. Each value is a
#: str.format() template; the named fields it reads are the keyword
#: parameters `render()` needs for that code. A call site that omits a
#: field the template uses fails loudly - str.format() raises KeyError -
#: because that means the call site and the registry have drifted apart.
#: An extra field is ignored; str.format() does not check for one.
REFUSALS: dict[str, dict[str, str]] = {
    "python-missing": {
        "what": "edit to {target} (tool: {tool})",
        "why": "python3 was not found on the PATH, so Compass cannot check "
               "whether this edit is allowed.",
        "fix": "install python3 (3.10+) or put it on PATH, then retry.",
    },
    "reader-failed": {
        "what": "edit to {target} (tool: {tool})",
        "why": "the {reader} could not run. {cause}{detail}",
        "fix": "fix the install and retry - this is not about your edit.",
    },
    "config-invalid": {
        "what": "edit to {target} (tool: {tool})",
        "why": "'{file}' could not be read: {detail}",
        "fix": "fix {file} and retry.",
    },
    "settings-conflict": {
        "what": "edit to {target} (tool: {tool})",
        # The same two strings the CLI error is built from, so the hook and
        # the CLI cannot word it differently.
        "why": CONFLICT_WHY,
        "fix": CONFLICT_FIX,
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
    "bad-session-issue": {
        "what": "this edit",
        "why": "no issue can be named for {project}: '{slug}' is not an "
               "issue under its .compass/work/.",
        "fix": "in the session's own project, set COMPASS_ISSUE to a real "
               "slug or unset it. In a worktree, run compass issue use "
               "<slug> there.",
    },
    "tree-not-tied": {
        "what": "this edit",
        "why": "{project} is not tied to the session's repository: it is "
               "not a worktree of it, or git cannot read it.",
        "fix": "edit a worktree of the session's repository, or start the "
               "session in {project}.",
    },
    "working-directory-gone": {
        "what": "edit to {target} (tool: {tool})",
        "why": "the session's working directory was removed and "
               "CLAUDE_PROJECT_DIR is not set, so Compass cannot tell which "
               "project's issue judges this edit.",
        "fix": "restart the session from a folder that exists, then retry.",
    },
    "pointer-moved": {
        "what": "this edit",
        "why": "another session moved .compass/current-task in this "
               "session's own project from this session's issue "
               "'{previous}' to '{slug}', so this edit would count against "
               "the wrong issue.",
        "fix": "in this session, run `compass issue use {previous}` to carry "
               "on, or `compass issue use {slug}` to switch, then retry.",
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
               "thorough is set but manifest.yml has no scenarios.",
        "fix": "add the scenarios to acceptance-criteria.md and manifest.yml "
               "(compass scenario add), or run /compass:assess --reassess "
               "if this is "
               "exploratory.",
    },
    "red-unsigned": {
        "what": "this edit",
        "why": "the red record for issue '{slug}' carries no identity - no "
               "content_digest - and this project needs one for records "
               "written since records_signed_since: {since_date}.",
        "fix": "run compass tdd-red --scenario <id> -- <your failing test "
               "command>.",
    },
    # The fields come from a one-segment slug, the until vocabulary and the
    # state words, so none can carry a newline (ADR-062).
    "waits-for-issue": {
        "what": "edit to {target} (tool: {tool})",
        "why": "issue '{slug}' waits for {dependency} to reach {until}{more}, "
               "and this checkout reads {dependency} as {state}.",
        "fix": "if {dependency} is finished in another checkout, bring its "
               ".compass/work/{dependency}/ folder here; or run compass issue "
               "depends remove {dependency}.",
    },
    "red-marker-no-record": {
        "what": "this edit",
        "why": "the .red marker for issue '{slug}' has no matching record "
               "in evidence/ - the marker alone is not evidence.",
        "fix": "run compass tdd-red --scenario <id> -- <your failing test "
               "command>.",
    },
    "no-red-on-record": {
        "what": "edit to {target} (tool: {tool}, guarded by {guard})",
        "why": "no failing test is on record for issue '{slug}' - the "
               "red-before-green strategy applies here.",
        "fix": "run compass tdd-red --scenario <id> -- <your failing test "
               "command>, then retry this edit.",
    },
    # The approval guards (approval_guard.py, ADR-068 decision 10, ADR-069).
    "approval-request-protected": {
        "what": "{target} (tool: {tool})",
        "why": "approval requests and the approval hook belong to Compass; an "
               "approval binds to the request a person was shown.",
        "fix": "ask for an approval with compass evidence request, then ask the "
               "person to type /compass:approve.",
    },
    "delegation-protected": {
        "what": "{target} (tool: {tool})",
        "why": "a delegation is a person's decision, written only from a typed "
               "/compass:delegate, and its folder holds the check for the code "
               "that confirms one.",
        "fix": "ask the person to type /compass:delegate or /compass:revoke; "
               "never read or write a delegation file yourself.",
    },
    "delegation-caller-mismatch": {
        "what": "delegated approval (--as {named})",
        "why": "Claude Code reports this call as {caller}, and a delegated "
               "approval must name exactly the agent that makes it. A word "
               "the shell could build is refused too.",
        "fix": "run it from the agent the delegation names, with --as set to "
               "that agent's full name, or ask with compass evidence request.",
    },
    "transcript-protected": {
        "what": "{target} (tool: {tool})",
        "why": "the session transcript holds what Compass showed only to the "
               "person, such as the code that confirms a delegation.",
        "fix": "work from the conversation and the files in the project; ask the "
               "person for anything you need from the transcript.",
    },
    # A landing refusal of `compass ship-commit` and `quick-fix finish`
    # (checkpoint_outcomes.landing_refusal), not a hook refusal. `is` and `it`
    # agree with the number of stages named.
    "checkpoint-no-outcome": {
        "what": "landing of issue '{slug}'",
        "why": "{stages} {is} listed in checkpoints with no outcome recorded, so "
               "nothing shows a person answered {it}.",
        "fix": "the person who answers runs compass evidence approve "
               "--checkpoint {stage} --approver <you> --role <role>, for each "
               "stage named, then ship again.",
    },
    # The release-line refusals (release_line.py, ADR-065): a landing of an issue
    # that owes a line and has none, and a line the living spec would read as an
    # issue heading. `compass acceptance record` gives the first for a blank line.
    "release-line-missing": {
        "what": "landing of issue '{slug}'",
        "why": "issue '{slug}' has no release line, and its approach owes one: a "
               "sentence for users that the release notes list.",
        "fix": "give it with --release-note \"<text written for a user>\", then "
               "run the command again.",
    },
    # A landing of an issue whose documents earned an artifact rule its recorded
    # approach does not hold (documents_present.py, ADR-070): a positioning.md
    # written after the issue was assessed, so verify.claims is missing.
    "artifact-rule-not-applied": {
        "what": "landing of issue '{slug}'",
        "why": "{documents} is on disk, so {rules} applies, but the recorded approach "
               "was evaluated before the document was there.",
        "fix": "run compass approach evaluate --issue {slug} --write, pass any gate it "
               "adds, then ship again.",
    },
    # A landing of an issue whose design holds a decision scoped `project` that no
    # record in architecture/decisions/ names (decision_scope.py, ADR-072).
    "project-decision-unrecorded": {
        "what": "landing of issue '{slug}'",
        "why": "technical-design.md scopes {decisions} to the whole project, and no "
               "record in architecture/decisions/ names {it}.",
        "fix": "write {path} with compass adr new, cite its id under the decision, then "
               "ship again.",
    },
    "release-line-heading": {
        "what": "the release line of issue '{slug}'",
        "why": "it starts with #, and the living spec reads a line such as "
               "### <slug> (completed <date>) as one of its issue headings.",
        "fix": "write the release line as plain text that does not start with #, "
               "then run the command again.",
    },
    # A Bash command too long for the pre-tool hook to scan before Claude Code
    # stops it (hooks/pre-tool.sh holds the limit). The refusal never quotes the
    # command: it can hold a secret.
    "bash-command-too-long": {
        "what": "Bash command of {size} bytes",
        "why": "the write guard refuses a command over {limit} bytes because it "
               "cannot scan one in time.",
        "fix": "write the file with the Write tool, or split the command into "
               "smaller steps. For a long commit message, use git commit -F with "
               "a file you wrote.",
    },
    # A Bash command with too many different write targets, variable names or
    # command substitutions, or with substitutions that stay open, for the hook
    # to scan in time (hooks/pre-tool.sh holds the numbers). It never quotes the
    # command.
    "bash-command-too-complex": {
        "what": "Bash command with {has}",
        "why": "the write guard cannot scan a command with {over} in time.",
        "fix": "split the command into smaller steps, or write the file with "
               "the Write tool.",
    },
}


def codes() -> list[str]:
    """Every reason code, in a stable order.

    What `_refusal --list`, the generated docs page, and the call-site
    coverage check all walk.
    """
    return sorted(REFUSALS)


MAX_PARAM_WORDS = 20


def _cap(value) -> str:
    words = str(value).split()
    if len(words) <= MAX_PARAM_WORDS:
        return str(value)
    return " ".join(words[:MAX_PARAM_WORDS]) + " ..."


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
    # A parameter is text from the environment - an exception message, a
    # path. Cutting each to a fixed word count keeps a refusal short
    # enough to read, however long the text it quotes.
    params = {k: _cap(v) for k, v in params.items()}
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
