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
        "Assess and record a quick fix in one call. Refuses before writing anything if a dimension has no reason or an unknown value. Otherwise it initialises the project, records the assessment and any --labels (a domain tag such as auth raises the approach's floor and brings the human sign-off), computes the approach, and, if it is a quick fix, writes delivery-approach.md and the one scenario. A heavier approach keeps the assessment and says to continue with /compass:assess.",
    'quick-fix finish':
        "Trace, check, gate and land a quick fix in one call, after checking every precondition: changed paths trace to the scenario, compass check's output becomes evidence, the three quick-fix gates pass, one devlog line is appended, and compass ship-commit lands it. Refuses, with no gate passed and nothing committed, if check fails, another gate is pending, no green is bound, or a path is untraced while several scenarios exist.",
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
        "Structurally validate the governance YAML - including that every guardrail's declared check is actually implemented in the CLI. A guardrail whose check does not exist is not a guardrail, and this is what says so. A project whose root holds a compass.yml is checked layer by layer instead: the shipped default, the project file and, with --issue, that issue's config. The checks run in a fixed order (each layer alone, the merge, the merged result, the locks, then waivers and the classifier) and stop after the first group with an error. When the project's extends: names a git parent, github:<owner>/<repo>@<ref>#<sha>, the parent is a layer between the default and the project: lint fetches the pinned commit into .compass/cache/parents/ if it is not there, reads its compass.yml as data and refuses a ref with no sha, a commit that is not the pinned one and a symbolic link in the tree. --offline reads the cache only and fetches nothing, as COMPASS_OFFLINE=1 does. --json lists every finding with its code, layer and path. Exit 0 passes, 1 fails, 2 means an input could not be read.",
    'policy effective':
        "Print every resolved configuration field - the capabilities, the owner and approvers, and each catalogue entry - with its value, the source layer that wrote it (the shipped default with its version, a git parent with its ref and short commit, the project file or the issue), the operation (add, replace or set) and the waiver that excuses it. A stage list a capability switch has not turned on is marked inactive. With --issue it resolves that issue's config over the live project file. --json gives the same fields in a documented, stable shape. A git parent named in extends: is fetched at its pinned commit when it is not cached; --offline or COMPASS_OFFLINE=1 reads the cache only. Exit 2 when the layers cannot be resolved; run compass policy lint to see why.",
    'policy diff':
        "Compare two configurations two ways. The classifier says whether the second owes more, less or something that cannot be compared, over the whole grid of assessments. The replay then lists each assessment whose result changes, with the approach, gates, checks and other obligations before and after, for the grid, for every combination of the labels the rules name, and for each assessment in the project's archive. A reference is default@6, project, legacy, git:<revision>, a git parent written as in extends: (github:<owner>/<repo>@<ref>#<sha>, shown as the parent with the parents it extends over the shipped default, fetched into the cache unless --offline or COMPASS_OFFLINE=1) or a path to a compass.yml. Two references compare A with B, one compares the project with it, and none compares the project file at git HEAD with the working file. --open also runs each open issue (active, queued or parked) with its own config over both, and lists the issue waivers that would need re-approval. --json prints one complete, stable document. Exit 0 whether or not anything differs, 1 with --exit-code when something does, 2 when a reference cannot be read or resolved. It writes no file of the project, except that a git parent that is not cached is fetched into the cache in .compass/cache/parents/ after one line on stderr.",
    'policy test':
        "Test a team preset. PRESET_DIR (default: the working folder) holds the preset's compass.yml and a compass-fixtures/ folder. The command lints compass.yml as a parent over the shipped default and any git parent it extends, so it fails on unlock:, a settings key, an impl the check registry does not hold and a change to a locked entry, and it runs no fixture until the lint passes. Each .yml file in compass-fixtures/ is one fixture: an assessment and an expect that holds any of approach, gates, stages and checks. A folder inside compass-fixtures/ is a fixture group named by its path, such as meets/banking (folders named with lower-case letters, digits and hyphens, at most 3 deep): the report gives each fixture its group and counts the fixtures, passes, failures and result of each group. A link inside compass-fixtures/ is a problem and is not followed. The report says per fixture whether the computed values match, naming each difference with the expected and the actual value. A fixture that cannot be read is an error, and a preset with no fixtures fails. A pinned git parent is fetched when it is not cached; --offline or COMPASS_OFFLINE=1 reads the cache only. --json prints a documented, stable shape. Exit 0 when everything passes, 1 when the lint, a fixture or the fixture folder fails, 2 when the folder or its compass.yml is missing, cannot be read or is not UTF-8 text. A compass.yml that is readable but malformed YAML is a lint error, so it exits 1. A fixture whose assessment holds a key that is not a dimension or labels, or whose expect.stages is empty, is an error on that fixture.",
    'policy init-preset':
        "Scaffold a team preset repository in DIR, which is created when it is missing: a compass.yml with its schema, the --owner team and one example change to the quick fix approach, compass-fixtures/example.yml, a README.md and a .gitignore. The result passes compass policy test where it stands, and other projects extend it as a git parent. It never overwrites a file: when DIR already holds any of the four files it names them and writes nothing. --json prints a documented, stable shape. Exit 0 when the files are written, 1 when it refuses, 2 when DIR is a file, --owner is empty or has a control character, or a file cannot be written. A failed write can leave some files; the message names them.",
    'policy migrate':
        "Turn a project that runs on copied governance (its own routing-policy.yml and guardrails.yml) and a .compass/config.yml into a compass.yml that holds only what differs from the shipped default, plus the project's settings. It is a dry run unless given --apply: it prints the file it would write, finds the shipped release the copy came from, adopts the defaults that moved since without a waiver, uses the classifier to show that the release plus the local edits is the copy or says what it could not express, and writes nothing. --apply copies each old file into .compass/legacy/ first, writes compass.yml and removes only .compass/config.yml. compass.yml then judges every issue with no stored generation at once, and one with a generation from its next reassess. The governance copies stay as the record of what the project ran. A loosening gets an UNAPPROVED waiver stub and blocks --apply. --json prints a documented, stable shape. Exit 0 for ready, applied or nothing to migrate, 1 when blocked, 2 when it refuses: compass.yml exists, the framework repository, one governance file without the other, or a source that cannot be read.",
    'retro':
        'Aggregate the re-assessment log across every issue and report whether assessment is systematically over- or under-sizing the process. The signal is direction: mostly-up means work is being read lighter than it is. Reads the archive; changes nothing.',
    'rework-scan':
        'Scan the archive for add-then-delete patterns across issues - a file added by one and removed by another inside the configured window. A signal for a person, not a gate.',
    'ship-commit':
        "Commit an issue's recorded changed files and nothing else, so the commit matches what the manifest says the issue touched. Refuses to stage anything the issue never claimed. Takes the message with -m, or from a file with -F.",
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
