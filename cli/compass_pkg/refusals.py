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
    "not-initialized": {
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
        # Never a hand edit of the pointer: the hook records each session's
        # issue, and `compass issue use` is the one way to move it.
        "fix": "run compass issue use <slug> with a real issue slug, then "
               "retry. To list the issues, run compass flow.",
    },
    "bad-session-issue": {
        "what": "this edit",
        "why": "no issue can be named for {project}: '{slug}' is not an "
               "issue under its .compass/work/.",
        # The worktree form. A worktree is judged by its own pointer, so
        # `compass issue use` run there fixes it. The own project has its own
        # code below, because there the same command changes nothing.
        "fix": "run compass issue use <slug> in that worktree, so its "
               ".compass/current-task names a real issue, then retry.",
    },
    # The session's own project, with COMPASS_ISSUE set to a missing issue.
    # COMPASS_ISSUE outranks .compass/current-task there, so `compass issue
    # use` changes nothing, and a running session cannot change its
    # environment. The code name holds the other one's, which a test pins.
    "bad-session-issue-restart": {
        "what": "this edit",
        "why": "no issue can be named for {project}: '{slug}' is not an "
               "issue under its .compass/work/.",
        "fix": "restart the session with COMPASS_ISSUE naming an existing "
               "issue, or without it. A running session cannot change it, "
               "and compass issue use does not override it. A worktree "
               "has its own pointer.",
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
        "why": "issue '{slug}' has no delivery approach in its manifest - its "
               "assessment did not finish.",
        "fix": "run /compass:assess.",
    },
    "no-acceptance-criteria": {
        "what": "edit to {target} (tool: {tool})",
        "why": "the acceptance-before-code guardrail blocks this: define: "
               "thorough is set but manifest.yml has no scenarios.",
        "fix": "add the first scenario to acceptance-criteria.md with compass "
               "scenario add TRC-001 --issue {slug} --intent \"<one sentence>\", "
               "or run /compass:assess --reassess if this is exploratory.",
    },
    # The same guardrail on a path issue (ADR-092), which has no stage modes, so
    # the reason cannot name `define: thorough`.
    "no-scenario": {
        "what": "edit to {target} (tool: {tool})",
        "why": "the acceptance-before-code guardrail blocks this: the issue is on the "
               "four-stage path, which owes scenarios before code, and manifest.yml has "
               "none.",
        "fix": "add the first scenario with compass scenario add TRC-001 --issue "
               "{slug} --intent \"<one sentence>\", or run /compass:assess "
               "--reassess if this is exploratory.",
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
        # The project names the tree whose issue judged the edit: a worktree
        # is judged by its own issue (ADR-074, ADR-078), and the reader must
        # know where to run tdd-red. The wording keeps the longest form
        # under 60 words (tests/test_refusal_registry.py).
        "why": "no failing test is recorded for issue '{slug}' in "
               "{project}.",
        "fix": "run compass tdd-red --scenario <id> -- <failing test "
               "command>, or compass acceptance start --kind <kind> if none "
               "fits.",
    },
    # The approval guards (approval_guard.py, ADR-068 decision 10, ADR-069).
    "approval-request-protected": {
        "what": "{target} (tool: {tool})",
        "why": "an approval binds to the request a person was shown.",
        # One subject flag as the example: a longer list would push a long
        # target over the 60-word cap (tests/test_approval_guard_refusal_text.py).
        "fix": "do not read, change or run these files. Ask with compass "
               "evidence request --checkpoint <stage>; the person answers with "
               "/compass:approve.",
    },
    "delegation-protected": {
        "what": "{target} (tool: {tool})",
        "why": "a delegation is a person's decision, and its folder holds the "
               "check for its confirmation code.",
        "fix": "do not read or write these files; the person types "
               "/compass:delegate or /compass:revoke.",
    },
    "delegation-caller-mismatch": {
        "what": "delegated approval (--as {named})",
        "why": "Claude Code reports this call as {caller}, and a delegated "
               "approval must name exactly the agent that makes it. A word "
               "the shell could build is refused too.",
        "fix": "run it as the named agent, with --as set to its full name, or "
               "ask with compass evidence request --checkpoint <stage> --issue "
               "<slug>.",
    },
    # An agent's approving review of a pull request (approval_guard._review_approval,
    # #355): a review approval by another person is the ship approval.
    "pr-review-protected": {
        "what": "{target} (tool: {tool})",
        "why": "an approving review of a pull request is a person's approval of the "
               "change, and the agent runs gh with that person's login.",
        "fix": "ask a person to review and approve the pull request; a comment review "
               "and a read of the reviews are allowed.",
    },
    "transcript-protected": {
        "what": "{target} (tool: {tool})",
        "why": "the transcript holds what Compass showed only to the person.",
        "fix": "use the project's files, or the Read, Grep, Edit or Write tool "
               "on the auto-memory folder; ask the person for the rest.",
    },
    # A landing refusal of `compass ship-commit` and `quick-fix finish`
    # (checkpoint_outcomes.landing_refusal), not a hook refusal. `is` and `it`
    # agree with the number of stages named.
    "checkpoint-no-outcome": {
        "what": "landing of issue '{slug}'",
        "why": "{stages} {is} listed in checkpoints with no outcome recorded, so "
               "nothing shows a person answered {it}.",
        # An agent approves only under a delegation, so the fix asks and stops,
        # as `scenarios-not-approved` does.
        "fix": "for each stage named, run compass evidence request --checkpoint "
               "{stage} --issue {slug} and stop; the person answers with "
               "/compass:approve. Then ship again.",
    },
    # `compass tdd-red` on a path issue that owes `scenario-approval`, before the
    # `specify` checkpoint has a person's answer (scenario_freeze.refusal, ADR-095).
    # It refuses before the test runs, because the `.red` marker unlocks code edits.
    "scenarios-not-approved": {
        "what": "red for issue '{slug}'",
        "why": "the scenarios of {slug} need a person's approval before code, and "
               "the specify checkpoint has no answer from a person.",
        "fix": "run compass evidence request --checkpoint specify --issue {slug} and "
               "stop; the person answers with /compass:approve. Then run the red again.",
    },
    # The pre-tool hook (ADR-099 decision 5): a code edit on an issue whose
    # scenarios owe a person's approval, before the `specify` checkpoint has a
    # person's answer.
    "code-before-approval": {
        "what": "edit to {target} (tool: {tool})",
        "why": "the scenarios of {slug} need a person's approval before code, and "
               "the specify checkpoint has no answer from a person.",
        "fix": "write the scenarios in the issue's acceptance-criteria.md, run compass "
               "evidence request --checkpoint specify and stop; the person answers "
               "with /compass:approve.",
    },
    # The landing check of `compass ship-commit` (manifest._refuse_open_definition_of_done,
    # ADR-091): `dod-evidence-typed` failed, so the Definition of Done has an open item.
    "definition-of-done-open": {
        "what": "landing of issue '{slug}'",
        "why": "the check dod-evidence-typed failed: {detail}",
        # The detail names the person's command for an item only a person can
        # meet. An agent never runs `evidence approve` here without a delegation.
        "fix": "for each open item, run compass follow-up add FU-<n> --issue {slug} "
               "--defers <item> --github <owner/repo#N> --summary \"<why>\", or "
               "compass evidence add EV-<n> --issue {slug} --type <type> --path "
               "<file> --meets <item>. Then ship again.",
    },
    # The release-line refusals (release_line.py, ADR-065): a landing of an issue
    # that owes a line and has none, and a line the release notes would print as a
    # heading. `compass acceptance record` gives the first for a blank line.
    "release-line-missing": {
        "what": "landing of issue '{slug}'",
        "why": "issue '{slug}' has no release line, and its approach owes one: a "
               "sentence for users that the release notes list.",
        # A landing refusal does not know its verb (manifest.LANDING_REFUSALS),
        # so there `verb` names both verbs that land (release_line.LANDING_VERBS).
        "fix": "run {verb} again with --release-note \"<a sentence for users>\".",
    },
    "release-line-heading": {
        "what": "the release line of issue '{slug}'",
        "why": "it starts with #, so the release notes would print it as a heading.",
        "fix": "run {verb} again with --release-note \"<plain text>\".",
    },
    # The project refusals of `compass migrate` (migrate_9._refuse_project, #359).
    # 9.0.0 reads neither a copied governance folder nor a git parent, so the
    # project moves on 8.x first, or by an edit of compass.yml. Every command
    # that resolves the policy gives the first too (`effective.refuse_governance_copy`).
    "governance-copy-removed": {
        "what": "{verb} in this project",
        "why": "governance/ holds a copy of routing-policy.yml or guardrails.yml and "
               "there is no compass.yml. Compass 9.0.0 does not read copied governance.",
        "fix": "on Compass 8.x, run compass policy migrate to write compass.yml, then run "
               "compass migrate again. docs/upgrade-9-0-0.md lists the steps.",
    },
    "git-parent-removed": {
        "what": "{verb} in this project",
        "why": "compass.yml extends the git parent {parent}, and Compass 9.0.0 removed "
               "git parents.",
        "fix": "move the checks the parent adds into compass.yml (signoff_labels, "
               "require_evidence, agent_review, project_checks), delete extends:, then "
               "run compass migrate again.",
    },
    # A Bash command too long for the pre-tool hook to scan before Claude Code
    # stops it (hooks/pre-tool.sh holds the limit). The refusal never quotes the
    # command: it can hold a secret.
    # `compass check` before it runs any row (`check_cmd.deleted_check_refusal`). Each
    # offending item is named with the command or edit that clears it, in one line.
    "names-deleted-check": {
        "what": "compass check of issue {slug}",
        "why": "{named} - each names a check Compass no longer has.",
        "fix": "{fix}; then rerun compass check --issue {slug}.",
    },
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

#: A lower cap for a code whose fix line is long, so the refusal stays under
#: 60 words. The detail of `definition-of-done-open` starts with the open
#: item's name, which is what the reader needs from it. `names-deleted-check`
#: lists its items in order: a cut list still names the first ones, and the
#: rest are named once those are cleared.
PARAM_WORDS = {"definition-of-done-open": 12, "names-deleted-check": 16}


def _cap(value, limit=MAX_PARAM_WORDS) -> str:
    words = str(value).split()
    if len(words) <= limit:
        return str(value)
    return " ".join(words[:limit]) + " ..."


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
    limit = PARAM_WORDS.get(code, MAX_PARAM_WORDS)
    params = {k: _cap(v, limit) for k, v in params.items()}
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
