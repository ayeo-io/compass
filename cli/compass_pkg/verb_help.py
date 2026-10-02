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
        "Make this directory a Compass project by creating .compass/ - a config file and the work directory. Safe to run twice: a second run reports that the project is already there and leaves an edited config and any existing work untouched, which is what lets the entry-point commands call it without checking first. It creates project state only; adopting your own governance/ is what the /compass:init slash command offers afterwards, and the shipped governance defaults are in force meanwhile.",
    'bdd verify':
        "Run the project's BDD suite and record which scenarios it actually reported, so a scenario the runner never ran is visible rather than assumed covered. Records what the runner said; it does not judge the result.",
    'changed-file add':
        "Trace a file this issue changed to the scenario that asked for it. The traceability guardrail is maintained as the work happens rather than reconstructed at the end - a chain assembled afterwards records what someone remembered.",
    'scenario add':
        "Add a scenario to the manifest, mirroring the prose in acceptance-criteria.md. The manifest's copy is what compass check reads, so a scenario that exists only in prose is one nothing can verify.",
    'acceptance record':
        'Close an acceptance record with what was actually observed. The pair exists so work without a natural red still leaves evidence a reader can weigh.',
    'acceptance start':
        'Open an honest acceptance record for a change with no natural behavioural red - a config edit, a pure refactor. It states what will be observed instead, so the absence of a failing test is recorded rather than quietly skipped.',
    'adr new':
        'Create the next numbered ADR from the template and register it in the index. Numbers are never reused: a superseded decision keeps its number and its file, and the successor gets a new one.',
    'analyze':
        "Read one issue's artifacts against each other and report where they disagree - a delivery-approach record whose stage weights contradict the manifest, a claim with no scenario behind it, a document the approach earned and nobody wrote. Advisory: it blocks nothing, because a disagreement between documents is a question for a person.",
    'approach summary':
        "Print the three-line decision view for an issue: the delivery approach with the risk, familiarity and size behind it, the gates it must pass, and the two directories its files go in. /compass:go shows these lines to the person before any code, so the output stays exactly three lines.",
    'approach evaluate':
        "Apply governance/routing-policy.yml to an issue's recorded assessment and write the delivery approach back into its manifest: the per-stage weights, the gate set, the subtask ceiling and every policy rule that fired. This is the determinism boundary - the assessment is judgement, and the same assessment with the same policy always produces the same approach.",
    'bdd extract':
        "Turn an issue's acceptance criteria into a .feature file a BDD runner can execute, so the scenarios written as the specification are the same ones that run as the acceptance suite. Writes the file; runs nothing.",
    'check':
        "Run the guardrails.yml checks against an issue's manifest and evidence - the mechanical half of the verify gate. Every scenario has a test, the suite passed with a record on file, changed files trace to a scenario, and every gate marked pass points at evidence of an accepted type. A check that had nothing to inspect is reported apart from one that passed, so a clean run cannot be mistaken for a thorough one.",
    'ci':
        'Run the full mechanical gate suite - the governance policy lint, then the manifest lint and the guardrail checks for every issue on disk. Intended for continuous integration and required green before a release. Gate checks are skipped for an issue that has not started, and the skip is named rather than hidden.',
    'evidence add':
        'Append a typed record to the manifest. The type is validated at write time, because a gate that accepts the wrong kind of evidence is not a gate.',
    'flow':
        "The cross-issue view: what is blocked, what follow-ups are owed, and the periodic digest. Advisory by design - it never gates and never sets an issue's status, because status is inferred from the artifacts on disk.",
    'follow-up resolve':
        "Mark an owed follow-up settled in an issue's manifest. An unresolved follow-up blocks shipping, which is what makes owing one a commitment rather than a note.",
    'gate pass':
        'Mark a gate passed, validating the evidence type at write time against what guardrails.yml says that gate accepts. A mechanical gate cannot be cleared with a written note.',
    'intent ingest':
        'Read a brief that already exists - a local path or an https URL - write a snapshot of it and record where it came from. Fetches over https only: a document altered in transit would shape the acceptance criteria and everything after them. It does NOT write intent.md; reshaping the document is judgement, and happens in the session with questions asked where the source is thin.',
    'issue artifact':
        "Set a document's status in the issue's review pack. Refuses a document the issue never earned, and an omission must carry a reason - an omission with no reason is indistinguishable from a document nobody got to.",
    'issue artifact-path':
        "Print where one of an issue's documents is, resolved through the artifact registry, and exit 0. Exit non-zero and print nothing when it is not there - a caller in bash reads the exit code before it reads the string. The two hooks call this: they are shell and cannot import the resolver, and a second path-resolution implementation in bash is how the shell half and the Python half stop agreeing about where a document lives.",
    'issue dashboard':
        'Render the per-issue review page a reviewer opens first - what is being asked for approval, which documents exist, which were deliberately left out and why. Evidence is linked rather than reproduced. Generated, never hand-edited.',
    'issue lint':
        'Structurally validate an issue manifest against the schema and report every problem at once, naming the key that is wrong rather than the line. An issue that has not started is not asked for an assessment it cannot have.',
    'issue receipt':
        'Render a one-screen account of a landed issue: the four-dimension assessment, the approach computed from it, the gates it cleared and the typed evidence each was cleared with. A view over what is recorded, not a re-run of the checks.',
    'issue set-status':
        'Record an issue as queued, active, parked, landed or abandoned. Only landed makes its scenarios eligible for the derived system spec, so no other value can silently acquire that.',
    'migrate':
        'Bring issue directories written under an older vocabulary up to the current schema - renaming artifacts, mapping manifest keys forward, and repointing the manifest at the files it renamed. Dry-run by default. Refuses before writing anything if two retired filenames claim the same current name.',
    'next':
        'Say which stage of its delivery approach an issue has reached and what comes next, reading the approach rather than guessing. Skipped and collapsed stages are passed over, because the approach already decided they do not run. At a terminal it opens with the route as a rail - done, current, pending, and stages the policy skipped - and ends with the next command. Piped output, and any run with CLAUDECODE set, is the plain line alone, so the model sees no change. NO_COLOR drops the colour; COMPASS_COLOR=never uses ASCII markers and COMPASS_COLOR=always draws the rail even when piped.',
    'plan lint':
        'Scan a technical design for placeholder phrases - TBD, TODO, "implement later". Advisory and always exits 0: a design can be vague without using one of those words, so this is the mechanical floor rather than the judgement.',
    'decision record':
        "Write a new entry in governance/decisions/ for a product decision a person has made, named for today and the slug. The decider comes from `git config compass.decidedBy`, else `user.name`; there is no option for it, because in a session whoever passes an option is the model. Refuses an existing slug, a slug that is not lower-case words joined by hyphens, and an unknown --supersedes slug. An entry never changes; a change of mind is a new entry that supersedes the old one.",
    'decision list':
        "List each entry in governance/decisions/, newest first: the date it was recorded, its slug and the first line of its decision.",
    'decision show':
        "Print one entry from governance/decisions/ by its slug: who decided, when, what it supersedes, the decision, why, and the evidence. Refuses a slug with no entry.",
    'decision check':
        "Compare governance/decisions/ with a base ref: fails, naming the file, when an entry that exists at the ref was changed or removed. New entries pass. A ref git cannot resolve fails rather than checking nothing. compass ci --since runs the same check.",
    'quick-fix start':
        "Assess a quick fix and record it in one call: refuses before writing anything if a dimension has no reason or the policy does not know its value, otherwise initialises the project, writes the manifest's assessment with any --labels (a domain tag such as auth brings the floor and the human sign-off), runs the same evaluator `compass approach evaluate --write` runs, and - only if the computed approach is quick fix - writes delivery-approach.md, registers it and records the one scenario against its intent. If the approach computes heavier than a quick fix, it keeps the assessment and says to continue with /compass:assess rather than writing an approach record and a scenario that do not apply.",
    'quick-fix finish':
        "Check every precondition before writing anything, then trace, check, gate and ship a quick fix in one call: every changed path outside .compass/ traces to its scenario, compass check's output is recorded as command-output evidence, the three quick-fix gates pass against that evidence and the scenario's green, one devlog line is appended, and compass ship-commit lands the change. Refuses - with no gate passed and nothing committed - if check fails, another gate is still pending, no green is bound to a scenario, or a changed path is untraced while several scenarios are on record.",
    'issue diagnose':
        "Explain one run from its issue's own records, after the session is gone: each stage the route ran against the record that shows it, each gate with its evidence, a timeline of every dated record (reds, greens, subtask dispatches, review rounds, reassessments, the landing), the deviations those records show (a stage with no record, a red dated after its green, a green with no red, a failed review round, a gate not passed), and the questions only the transcript could answer. It reads and never writes.",
    'lesson add':
        "Record a one-sentence lesson in `lessons.yml` in the project's `.compass` folder for later sessions in this repository. Who added it comes from `git config compass.decidedBy`, else `user.name`; there is no option for it, and the CLI cannot tell whether the person or the model typed the words. The model is told to use `compass lesson propose` instead. An exact repeat is refused; a rule that contains an existing one replaces it and records `superseded`, while a rule contained in an existing one is kept as a separate lesson. A rule naming a guardrail id is refused, and so is one matching a short list of model names and tool-version shapes: that check is a pattern, not a proof, so some names pass and some ordinary words are refused. A rule over 150 words is refused. `source` records the route a lesson came by, not who typed it. `always` lessons are injected at session start under a 150-word cap; `on_topic` lessons are stored, not yet surfaced.",
    'lesson propose':
        "Hold a lesson in `lessons-pending.yml` in the project's `.compass` folder. It takes effect only on `compass lesson accept`. The model is told to propose rather than add.",
    'lesson accept':
        "Turn a pending proposal into a lesson, recording who accepted it from git config.",
    'lesson list':
        "Print each lesson and each pending proposal, marking `on_topic` lessons as stored, not yet surfaced.",
    'lesson remove':
        "Delete one lesson by its LS- id. The lesson it superseded, if any, is not restored; git keeps the history. Its text is kept, so `compass retro --lessons` does not propose it again.",
    'scenario descope':
        "Record, in the manifest's `failure_modes_descoped`, a failure mode or input class the brief implies that no scenario covers, with the reason it is left out and today's date. The verifier is told to list each in the verification report. Nothing checks that it did, and a hand edit of the manifest can remove an entry, so this is a record and a prompt, not a guarantee. Refuses an empty mode or reason, and a mode already recorded. No gate reads it.",
    'lesson decline':
        "Drop a pending proposal by its LP- id without making it a lesson. Its text is kept, so `compass retro --lessons` does not propose it again.",
    'policy review-rules':
        "Print the rules in governance/review-rules.yml whose file patterns match the paths given to --changed-files, each with whether it blocks, the guardrail or strategy it enforces, what not to flag and the incident behind it. A reviewer reads this instead of every house rule and cites a finding by its RR- id. It reads the project's own governance/, never the shipped copy; --rules reads another file, such as the base branch's copy in CI.",
    'policy lint':
        "Structurally validate the governance YAML - including that every guardrail's declared check is actually implemented in the CLI. A guardrail whose check does not exist is not a guardrail, and this is what says so.",
    'retro':
        'Aggregate the re-assessment log across every issue and report whether assessment is systematically over- or under-sizing the process. The signal is direction: mostly-up means work is being read lighter than it is. Reads the archive; changes nothing.',
    'rework-scan':
        'Scan the archive for add-then-delete patterns across issues - a file added by one and removed by another inside the configured window. A signal for a person, not a gate.',
    'ship-commit':
        "Commit an issue's recorded changed files and nothing else, so the commit matches what the manifest says the issue touched. Refuses to stage anything the issue never claimed.",
    'tdd-green':
        'Run a test command, assert that it PASSES, record the green and clear the red marker. The binding decides the filename, so recording one scenario cannot destroy the record another gate is citing.',
    'tdd-red':
        'Run a test command, assert that it genuinely FAILS, and record the failure plus the marker the pre-tool hook reads. The marker is only ever written after a real failure, which is what makes it evidence rather than a claim. Binding the run to a scenario proves the right thing broke, not merely that something did.',
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
