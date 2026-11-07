#!/usr/bin/env python3
"""What each verb does, in the words a reader gets from `--help`.

Here rather than beside each `add_parser` call, for two reasons:

- the entry point is capped below 640 lines to keep logic out of it, and 30
  paragraphs of prose would have used those lines for content rather than
  structure;
- a reader reviewing what the CLI claims about itself can read the claims
  together here, instead of tracing them through a parser.

Keyed by the path a person types, because `lint` exists under three groups
and they do different things.

DEPENDENCY: none beyond the standard library. This module is data.
"""
from __future__ import annotations

VERB_DESCRIPTIONS = {
    'init':
        "Make this directory a Compass project by creating .compass/ - a state file and the work directory. Safe to run twice: a second run reports that the project is already there and leaves the state file and any existing work untouched, which is what lets the entry-point commands call it without checking first. It creates project state only and no settings file; writing a compass.yml for the project is what the /compass:init slash command offers afterwards, and the shipped defaults are in force meanwhile.",
    'bdd verify':
        "Run the project's BDD suite and record which scenarios it actually reported, so a scenario the runner never ran is visible rather than assumed covered. Records what the runner said; it does not judge the result.",
    'changed-file add':
        "Trace a file this issue changed to the scenario that asked for it. The traceability guardrail is maintained as the work happens rather than reconstructed at the end - a chain assembled afterwards records what someone remembered.",
    'scenario add':
        "Add a scenario to the manifest, mirroring the prose in acceptance-criteria.md. The manifest's copy is what compass check reads, so a scenario that exists only in prose is one nothing can verify.",
    'scenario tests set':
        "Replace the tests a scenario declares in the manifest, for the case where a declared test id went wrong, such as a test renamed for a good reason. It takes only a test id that `declared-tests-resolve` in compass check would accept, and refuses an unknown scenario, no --test, and an id that does not resolve or is marked skipped. It appends a line naming the old tests, the new tests and --reason to devlog.md when the issue has one. A green recorded before the change does not cover a test file the scenario did not declare before: compass ship-commit refuses it until compass tdd-green runs again.",
    'acceptance record':
        'Close an acceptance record with what was actually observed. The pair exists so work without a natural red still leaves evidence a reader can weigh.',
    'acceptance start':
        'Open an honest acceptance record for a change with no natural behavioral red - a config edit, a pure refactor. It states what will be observed instead, so the absence of a failing test is recorded rather than quietly skipped.',
    'adr new':
        'Create the next numbered ADR from the template and register it in the index. Numbers are never reused: a superseded decision keeps its number and its file, and the successor gets a new one.',
    'approach show':
        "Print the three-line decision view for an issue: the approach with the risk, familiarity and size behind it and whether the session stops for a person, the evidence the change owes (on an issue assessed before 9.0.0, the gates it must pass), and the two directories its files go in. /compass:go shows these lines to the person before any code, so the output stays exactly three lines.",
    'approach evaluate':
        "Apply the routing policy to an issue's recorded assessment and write the result back into its manifest: on the four-stage path the approach `delivery`, the evidence the change owes, the gates derived from it, the checkpoints and every policy rule that fired; on a spike its stages and its gate. The policy comes from the issue's stored generation. With --write it comes from the project's resolved configuration instead: the check set, tightened by the settings in compass.yml. Only an issue with no stored generation, in a project with no compass.yml, reads the governance files. This is the determinism boundary - the assessment is judgment, and the same assessment with the same policy always produces the same evidence. With --write it also commits the issue's next stored generation. The issue's own config: is not read (ADR-094).",
    'bdd extract':
        "Turn an issue's acceptance criteria into a .feature file a BDD runner can execute, so the scenarios written as the specification are the same ones that run as the acceptance suite. Writes the file; runs nothing.",
    'check':
        "Run the guardrails.yml checks against an issue's manifest and evidence - the mechanical half of the verify gate. Every scenario has a test, the suite passed with a record on file, changed files trace to a scenario, and every gate marked pass points at evidence of an accepted type. A check that had nothing to inspect is reported apart from one that passed, so a clean run cannot be mistaken for a thorough one. With the capability entry-exit-evaluation on, it also checks the entry and exit lists of the stages the issue has reached, under the guardrail label stage:<stage>:<entry|exit>.",
    'ci':
        'Run the full mechanical gate suite - the governance policy lint, then the manifest lint and the guardrail checks for every issue on disk. Intended for continuous integration and required green before a release. Gate checks are skipped for an issue that has not started, and the skip is named rather than hidden.',
    'evidence add':
        'Append a typed record to the manifest. The type is validated at write time, because a gate that accepts the wrong kind of evidence is not a gate. With --meets <item> the record also meets an item of the Definition of Done or Ready, which is how an agent records one instead of ticking a page. With --type spike-conclusion, --decision discard | graduate-to-delivery | defer records how a spike closes, and --next-issue names the delivery issue it graduates to; spike-conclusion-present reads both.',
    'evidence approve':
        "Record a person's approval in one of five forms: --check <id> approves a human check that lists approvers or an item of the Definition of Ready or Done, `--guardrail G5` records the sign-off of guardrail `G5` as a human-approval entry with `guardrail: G5` and no check, which human-approval-present counts (it refuses any other guardrail and --decision rejected), --decisions confirms the decisions an agent took for the person, and --checkpoint <stage> answers the hand-off of a checkpoint stage (assess, specify, build or ship on the path; assess, define, refine, plan, implement or verify on an issue assessed before 9.0.0). --checkpoint registers one checkpoint-approval entry, which has no check and so never meets guardrail `G5`, a human check or a waiver, and records the stage's outcome as waited, citing it; --scope defaults to the stage's hand-off. --waiver W-<n> approves one waiver of the issue (compass waiver add): one human-approval entry with waiver, waived_check and waiver_reason, which never clears guardrail `G5`; it refuses a withdrawn or already approved waiver, one with no reason, one of a check the check set never waives, --decision rejected, and a name not in approvers.waiver (else the project's owner). A delegated approval of a waiver needs a delegation typed with --for waivers. It refuses an issue assessed before outcomes were recorded, a stage that is not a checkpoint stage, one the issue does not run or whose record is not written yet, --decision rejected, and a name that is not an approver of the project (any name not an agent when the project declares no approvers or owner, which it says in one line). Every form takes --approver (a person's id; the project's owner is listed as owner), --role and --decision approved (the default) or rejected; --check and --guardrail also need --scope. The command stamps the issue, the issue's generation and the time. --check registers a human-approval entry that names its check, so it never clears the sign-off of guardrail `G5`, and the check then passes only while the newest usable record is an approval by a listed approver for this issue and generation; a later rejection withdraws it. The command needs a terminal on standard input, so an agent session cannot call it, and it refuses the approver agent; its records hold via: terminal. With --delegated --as <agent> and no --approver or --role, an agent records the approval under a delegation a person typed with /compass:delegate: it needs no terminal, the record names the person who delegated as approver with approved_by_agent, delegation and via: delegation, and it refuses unless a delegation in force names exactly that agent and covers the issue, its generation, the form and the labels. In Claude Code a person approves by typing /compass:approve after compass evidence request instead. Exit 0 when the record is written, exit 2 when it is not (no terminal, no such check, a check that is not human or lists no approvers, an approver who is not listed, an empty role or scope, no delegation that covers it).",
    'evidence request':
        "Ask a person for an approval, in one of the five forms of compass evidence approve (--check, --guardrail with the value `G5`, --decisions, --checkpoint or --waiver), with --scope saying what it covers in your words; --check and --guardrail need --scope. It runs the refusals compass evidence approve gives for the subject, with the same words, and writes one pending request under the issue's approval-requests folder, holding the issue, its generation and labels, the subject and a single-use nonce. For the build or ship checkpoint of an issue the four-layer acceptance strategy applies to (refine, implement or verify on an issue assessed before 9.0.0), the request also lists the questions of the stage review it holds, from the atdd skill, and the command prints them. A pending request for the same subject is replaced. Compass shows the request to the person at the end of the agent's turn, and the person answers by typing /compass:approve or /compass:reject. Where the adapter sets COMPASS_APPROVAL_CHANNEL=terminal it prints the exact compass evidence approve command for the person's own terminal instead. A request is not evidence. Exit 0 when written, exit 2 on a refusal.",
    'waiver add':
        "Write a waiver of one check on one issue to its manifest, as W-<n>, with --reason saying why the check may be excused. A waiver excuses nothing until a person approves it: ask with compass evidence request --waiver W-<n> and stop. It refuses an empty reason, a check the check set never waives (human-approval-present, ship-approval-present and the checks of gate `G5`), a check the issue's policy does not hold, and a second waiver in force for the same check. Once approved, compass check shows the check's row as waived, with the reason, the approver and the record id, and counts it apart. Exit 0 when written, exit 2 on a refusal.",
    'waiver withdraw':
        "Withdraw a waiver of the issue. A waiver nobody approved is removed, and a pending request for it is closed. An approved waiver is marked withdrawn with the time, so its approval stays on record and the check runs again. Withdrawing only makes the issue owe more, so an agent may run it. Exit 0 when done, exit 2 when there is no such waiver or it was already withdrawn.",
    'evidence review':
        "Record a judgment against a check of kind judged: --verdict pass or fail, --reason, and --reviewer (agent, agent:<session id> or a person's id). The command digests the check's declared inputs as they are now, writes a review record in the issue's evidence folder and registers it as manual-review evidence for the check. The check then passes only while the newest record says pass, names a reviewer the check lists, and still matches its inputs and the check's definition; when an input changes, the review is re-owed. Exit 0 when the record is written, exit 2 when it is not (no such check, a check that is not judged, no inputs, an input that cannot be found, an empty reason).",
    'flow':
        "The cross-issue view: what is blocked, what follow-ups are owed, and the periodic digest. Advisory by design - it never gates and never sets an issue's status, because status is inferred from the artifacts on disk.",
    'release notes':
        "List the issues completed since a git reference, each with its release line, as text to paste into release notes. --since is required and takes a tag, branch or commit; a reference git cannot resolve to a commit stops the run with exit 2 before any output. An issue is listed when it was completed, its approach ships, and it landed after the reference: its land commit is reachable from HEAD and not from the reference, or the living spec committed at HEAD names it and the spec at the reference does not (a squash merge leaves the land commit off the branch, so the spec decides). 9.0.0 derives no living spec, so only a revision made before 9.0.0 holds one; at any other revision reachability alone decides. Issues are ordered by landing time and then slug, and each prints a heading `### <slug> (completed <date>)` followed by its release line, or `No release line recorded.` for an older issue. Two closing lines follow when they apply: how many listed issues have no release line, and how many completed issues could not be placed against the reference. With no shipping issue since the reference it prints one line saying so. It reads the issue records and git and writes nothing. When the project keeps a names key, a rival name prints as its code.",
    'follow-up add':
        "Record a follow-up in an issue's manifest, with --defers to carry a Definition of Done or Ready item and --github to link the GitHub issue that tracks the work. On a path issue --github is required and a linked follow-up meets the item it defers, resolved or not: an open Definition of Done item must link to an issue. On an issue assessed before 9.0.0 an outstanding follow-up carries the item to ship until it is resolved. This is how a deferral is written down rather than ticked on a page.",
    'follow-up resolve':
        "Mark an owed follow-up settled in an issue's manifest. On an issue assessed before 9.0.0 an unresolved follow-up blocks shipping, which is what makes owing one a commitment rather than a note. On a path issue nothing waits for it: the linked GitHub issue tracks the work.",
    'gate pass':
        'Mark a gate passed, validating the evidence type at write time against what guardrails.yml says that gate accepts. A mechanical gate cannot be cleared with a written note. With --meets <item> the evidence also meets an item of the Definition of Done or Ready.',
    'isolation record':
        "Run the acceptance suite in parallel once, then each scenario's declared tests twice with {tests} in --repeat replaced by their ids, and write the isolation-proof record of the exit codes, the candidate and the client. Each command is split into words and run with no shell. It exits 0 when the record is written, even when a run failed, because isolation-proven judges the record; it exits 2 when --repeat holds no {tests}, the issue declares no test, or the candidate or client is missing or unknown.",
    'layering record':
        "Run the project's own layering test, the command after -- or project.layering_command, and write the layering record: the command, the test path, the exit code, the number of tests that ran when pytest wrote a report, the tree id and the time. It exits 0 when the record is written, even when the test failed, because layering-test-passed judges the record; it exits 2 when there is no command to run.",
    'issue decision add':
        "Record a decision an agent took for the person. With --from-ledger it reads the issue's requirements review, registered or not, and records each ledger entry whose \"Decided by\" names an agent (builder, spec-author, planner or another former agent name), keyed by the ledger id at stage refine. When the ledger now names a person in \"Decided by\" for a decision already recorded, it prints a line for that decision and changes nothing: only compass evidence approve --decisions confirms a decision, and the line says whether the named person is an approver of the project. A second run adds nothing; a reworded question is updated and the status kept; a changed resolution is updated and reopens the decision. With an id, --question, --resolution, --by and --stage it records a decision taken outside the ledger. It refuses a --by that is not an agent, an unknown stage and an id that exists. Exit 0, including when there is nothing to add; exit 2 on a refusal.",
    'issue checkpoint add':
        "Record that the autonomy setting passed a checkpoint hand-off: <stage> --outcome skipped --by <agent> writes the stage's outcome as skipped, by that agent, at the time of the command, and writes no evidence record. The session runs it when the hand-off is not listed in the manifest's checkpoints. A person's answer is recorded with compass evidence approve --checkpoint instead, which replaces a skipped outcome; a skip never replaces it. It refuses, writing nothing, an issue assessed before outcomes were recorded, a stage that is not a checkpoint stage or that the issue does not run, a listed checkpoint (it waits for a person), a stage with a waited outcome, --outcome waited and a --by that is not an agent. A repeat for a stage already skipped changes nothing. compass next names this command for a build or ship hand-off (implement or verify on an issue assessed before 9.0.0) the setting passes on an issue the four-layer acceptance strategy applies to. Exit 0 when recorded or already recorded, exit 2 on a refusal.",
    'issue decision set':
        "Reopen a decision taken for the person, with --status reopened and --reason saying why. It needs a terminal on standard input, because changing a decision is a person's act, and it accepts no other status: a decision becomes confirmed only through compass evidence approve --decisions. A reopened decision keeps the checkpoint waiting. Exit 0 when written, exit 2 when not.",
    'issue lint':
        'Structurally validate an issue manifest against the schema and report every problem at once, naming the key that is wrong rather than the line. An issue that has not started is not asked for an assessment it cannot have.',
    'issue status set':
        "Store an issue's status: backlog (a hold, with --reason) or done. Done needs --close-reason completed, not-planned or duplicate; --duplicate-of SLUG implies duplicate and names the issue that covers this one. Completed is refused while a gate has not passed, and only a completed issue on an approach that ships feeds the derived system spec. Ready, in-progress and in-review are refused: the issue's records move those states. Closing or setting aside an issue clears its blocked flag.",
    'issue status remove':
        "End a backlog hold by deleting the stored status. The state then follows the issue's records. Refuses an issue with no hold and writes nothing.",
    'issue link set':
        "Link an issue to its GitHub issue with --github, as owner/repo#number or the issue's URL on github.com, and store it as the manifest's github field. The target is checked against a strict pattern before it is stored, so nothing that could be read as an option or a shell command reaches gh. Linking writes nothing to GitHub.",
    'issue blocked set':
        "Flag an in-progress or in-review issue as blocked, with --reason saying what it waits for. The flag records the reason and the time, the state does not change, and the flow board shows the issue as blocked. Refuses any other state, names the two that allow it and writes nothing.",
    'issue blocked remove':
        "Clear the blocked flag. Refuses an issue that is not blocked and writes nothing.",
    'issue depends add':
        "Record that this issue waits for another issue, in its depends_on list. --reason says why; --until names the point the other issue must reach: done (the default, closed as completed), in-review, or a stage it must be at or past: specify, build or ship, or a stage of an issue assessed before 9.0.0 (define, refine, plan, breakdown, implement, verify), judged at the path stage it maps to. While this issue is at build and the other has not reached that point, compass next and the board show the wait and the pre-tool hook refuses production-code edits; earlier stages are not blocked. A slug already listed has its entry updated in place. A slug with no manifest in this checkout is written, and the lint finding goes to standard error. Exit 2, writing nothing, for a cycle, the issue's own slug, a slug that is not one path segment, an unknown until value or an empty reason.",
    'issue depends remove':
        "Stop waiting for an issue: remove its entry from depends_on, and the key with the last entry. The other issue does not need a manifest in this checkout. Exit 2, writing nothing, for a slug that is not a dependency of this issue.",
    'issue migrate':
        'Bring issue directories written under an older vocabulary up to the current schema - renaming artifacts, mapping manifest keys forward, and repointing the manifest at the files it renamed. On a done issue it also settles the artifact status: each draft or awaiting-approval entry becomes approved (close reason completed) or superseded (not-planned or duplicate), with the reason "migrated from a 6.0.0 record"; entries in any other status are left as they are, and the dry run reports how many would change. Dry-run by default. Refuses before writing anything if two retired filenames claim the same current name. With --config it works on one issue instead: it stores a new generation of the issue\'s configuration pinned to the check implementation, resolver and CLI versions this CLI has, and marks every check result recorded under the old versions invalidated so each check runs again. Run that when `compass check` refuses a check because its implementation major differs from the one the generation recorded. It changes no configuration: a project edit reaches the issue only through `compass approach evaluate --write`. An issue with no stored generation is adopted as generation 1. A closed issue is refused, and a generation already pinned to the installed versions is left as it is.',
    'next':
        'Say which stage of the path an issue has reached and the one command that comes next, read from its records rather than guessed: assess, specify, build and ship, or on a spike its own stages. An issue assessed before 9.0.0 is shown at the path stage its stage maps to, and its skipped and collapsed stages are passed over. At a terminal it opens with the stages as a rail - done, current, pending - and ends with the next command. Piped output, and any run with CLAUDECODE set, is the plain line alone, so the model sees no change. NO_COLOR drops the color; COMPASS_COLOR=never uses ASCII markers and COMPASS_COLOR=always draws the rail even when piped. With the capability entry-exit-evaluation on, the line also names the entry checks of the current stage that are not met. When the issue has decisions an agent took for the person that nobody has confirmed, the answer depends on the autonomy: at a stage in the checkpoints list that the records show done, the first line reads "Waiting at the <stage> checkpoint" with the count, the decisions and the commands to confirm or reopen them follow, and the next stage is not named; otherwise the stage line is unchanged and the unconfirmed decisions are listed below it. On an issue the four-layer acceptance strategy applies to, a build or ship hand-off (implement or verify on an issue assessed before 9.0.0) the records show done with no outcome reads "Waiting at the <stage> checkpoint" with the compass evidence request command when the checkpoint is listed, and otherwise adds the compass issue checkpoint add command that records it skipped to the stage line; a stage review a person rejected names that stage, with the reason, until a newer outcome is recorded. Exit 0 either way.',
    'decision record':
        "Write a new entry in governance/decisions/ for a product decision a person has made, named for today and the slug. The decider comes from `git config compass.decidedBy`, else `user.name`; there is no option for it, because in a session whoever passes an option is the model. Refuses an existing slug, a slug that is not lower-case words joined by hyphens, and an unknown --supersedes slug. An entry never changes; a change of mind is a new entry that supersedes the old one.",
    'decision list':
        "List each entry in governance/decisions/, newest first: the date it was recorded, its slug and the first line of its decision.",
    'decision show':
        "Print one entry from governance/decisions/ by its slug: who decided, when, what it supersedes, the decision, why, and the evidence. Refuses a slug with no entry.",
    'decision check':
        "Compare governance/decisions/ with a base ref: fails, naming the file, when an entry that exists at the ref was changed or removed. New entries pass. A ref git cannot resolve fails rather than checking nothing. compass ci --since runs the same check.",
    'quick-fix start':
        "Assess and record a change in one call. Refuses before writing anything if a dimension has no reason or an unknown value. It then records the assessment and any --labels and writes the one scenario. It serves every size; a spike (--goal exploration) stops and names /compass:assess.",
    'quick-fix finish':
        "Trace, check, gate and land a change in one call, after checking every precondition: changed paths trace to the scenario, compass check's output becomes evidence, the three immovable gates pass, and compass ship-commit lands it. Refuses, with no gate passed and nothing committed, if check fails, other evidence is owed (a next: line for each), no green is bound, or a path is untraced while several scenarios exist.",
    'issue diagnose':
        "Explain one run from its issue's own records, after the session is gone: each stage the issue ran against the record that shows it, each gate with its evidence, a timeline of every dated record (reds, greens, subtask dispatches, review rounds, reassessments, the landing), the deviations those records show (a stage with no record, a red dated after its green, a green with no red, a failed review round, a gate not passed), and the questions only the transcript could answer. It reads and never writes.",
    'lesson add':
        "Record a one-sentence lesson in `lessons.yml` in the project's `.compass` folder for later sessions in this repository. Who added it comes from `git config compass.decidedBy`, else `user.name`; there is no option for it, and the CLI cannot tell whether the person or the model typed the words. The model is told to use `compass lesson propose` instead. An exact repeat is refused; a rule that contains an existing one replaces it and records `superseded`, while a rule contained in an existing one is kept as a separate lesson. A rule naming a guardrail id is refused, and so is one matching a short list of model names and tool-version shapes: that check is a pattern, not a proof, so some names pass and some ordinary words are refused. A rule over 150 words is refused. `source` records the way a lesson came in, not who typed it. `always` lessons are injected at session start under a 150-word cap; `on_topic` lessons are stored, not yet surfaced.",
    'lesson propose':
        "Hold a lesson in `lessons-pending.yml` in the project's `.compass` folder. It takes effect only on `compass lesson accept`. The model is told to propose rather than add.",
    'lesson accept':
        "Turn a pending proposal into a lesson, recording who accepted it from git config.",
    'lesson list':
        "Print each lesson and each pending proposal, marking `on_topic` lessons as stored, not yet surfaced.",
    'lesson remove':
        "Delete one lesson by its LS- id. The lesson it superseded, if any, is not restored; git keeps the history. Its text is kept in the file as a record.",
    'scenario descope':
        "Record, in the manifest's `failure_modes_descoped`, a failure mode or input class the brief implies that no scenario covers, with the reason it is left out and today's date. The verifier is told to list each in the verification report. Nothing checks that it did, and a hand edit of the manifest can remove an entry, so this is a record and a prompt, not a guarantee. Refuses an empty mode or reason, and a mode already recorded. No gate reads it.",
    'lesson decline':
        "Drop a pending proposal by its LP- id without making it a lesson. Its text is kept in the file as a record.",
    'review-rule list':
        "Print the rules in governance/review-rules.yml whose file patterns match the paths given to --changed-files, each with whether it blocks, the guardrail or strategy it enforces, what not to flag and the incident behind it. A reviewer reads this instead of every house rule and cites a finding by its RR- id. It reads the project's own governance/, never the shipped copy; --rules reads another file, such as the base branch's copy in CI.",
    'policy lint':
        "Lint the project's compass.yml as a file of settings over the one fixed check set (ADR-094). It refuses a key compass.yml cannot hold, a malformed value, a tighten-only setting that would not add to what an issue owes, and a project check that reuses a shipped id, and it checks that every check names an implementation the CLI holds. A key 9.0.0 removed - a catalog such as checks: or gates:, extends: compass:default@<n>, preset - is a warning, L-SETTING-REMOVED, and is not read. An extends: that names a git parent is an error, L-PARENT-REMOVED. A project with no compass.yml has its governance YAML validated as before, including that every guardrail's declared check is implemented. --file lints one compass.yml. --json lists every finding with its code and path. Exit 0 passes, 1 fails, 2 means an input could not be read.",
    'policy show':
        "Print the one fixed check set the project runs - its id and version, such as compass-checks@9.0.0, and the sha256 of its file - the sha256 of compass.yml, and the tighten-only settings it applies. With --issue it adds that issue's policy: block, the digests its stored generation was committed under, and its waivers. --json gives the same fields. Exit 2 when compass.yml cannot be read or extends a git parent.",
    'ship-commit':
        "Commit an issue's recorded changed files and nothing else, so the commit matches what the manifest says the issue touched. Refuses to stage anything the issue never claimed. Takes the message with -m, or from a file with -F. It refuses while the check artifacts-approved fails, naming each document that reads draft or awaiting-approval, or is omitted with no reason, and the command that moves it. It approves the documents the ship stage owns when it lands the issue.",
    'tdd-green':
        "Run a test command, require that it PASSES, record the green and clear the red marker. Each scenario's green has its own file.",
    'tdd-red':
        'Run a test command, require that it FAILS, and record the failure and the marker the pre-tool hook reads. A command that passes, or runs no test, is refused. Bound to a scenario, it shows the right thing broke.',
    'terminology':
        'Print what a term means in this framework - the definition, what it is NOT, and the related words. The vocabulary is frozen and the file is what the scan enforces, so this is the authority rather than a convenience.',
}


def apply_descriptions(root):
    """Attach each description to its parser, after the tree is built.

    Done in one walk rather than at 30 call sites: the entry point holds the
    parser's SHAPE, and what a verb claims about itself is content.
    """
    import argparse

    def walk(parser, path):
        key = " ".join(path)
        if key in VERB_DESCRIPTIONS:
            parser.description = VERB_DESCRIPTIONS[key]
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, child in action.choices.items():
                    walk(child, path + [name])

    walk(root, [])
    return root


def parse_command_line(root, raw):
    """Parse `raw` with the built parser tree, reporting an unknown option
    against the verb it was given to, with that verb's usage, rather than
    the top level's. Each verb's parser records itself as the one to report
    against; a deeper parser's default replaces its parent's, so the parsed
    namespace names the verb that was actually run."""
    import argparse

    def mark(parser):
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for sub in set(action.choices.values()):
                    sub.set_defaults(_usage_parser=sub)
                    mark(sub)

    mark(root)
    args, extra = root.parse_known_args(raw)
    if extra:
        getattr(args, "_usage_parser", root).error(
            "unrecognized arguments: " + " ".join(extra))
    return args
