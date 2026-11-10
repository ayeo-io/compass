# The review dimensions, one checklist each

Reference: read the checklist for the dimension you are applying, not all of them at once. The issue's `evidence_required` list names which dimensions it carries; this says what each asks.

## The review-dimension checklists

`correctness`, `governance` and `traceability` are on every delivery issue -
the default guardrails in review form - and `compass quick-fix finish` passes
their gates from the test records and the output of `compass check`.
`regression`, `security`, `clarity` and `architecture` are owed only where
the project's settings add them (`require_evidence` in `compass.yml`).
Settings can add; they can never remove the first three or an
`immovable_gate`. (Spike runs none of these - it ships nothing, so it has
only its own gate, `spike.conclude`.)

**correctness** - Does the change do what the scenarios describe? Is the green
genuine, or green-by-skipped-test? Do the acceptance scenarios actually exercise
the new behavior, not just run near it?

**governance** - Two distinct checks under one dimension, and keeping them
distinct *is* the check:
- *Guardrails (checked with evidence).* Does the change clear every applicable
  guardrail - the five shipped defaults and any project guardrails? Each is cleared with
  recorded evidence, never a claim. A failed guardrail is a no-pass; a
  guardrail beats any strategy. See the `governance-check` skill.
- *Strategies (assessed as judgment).* Did the work follow the applicable
  default and project strategies - and where it departed, is the departure
  recorded? This is honestly the reviewer's opinion; record it *as* judgment,
  clearly separated from the guardrail evidence. A strategy not followed is a
  note, not an automatic gate failure. On a sweep, rename, or cleanup that
  touches many files, this includes whether verification came from a fresh
  agent rather than the implementer - `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md`
  (an unmigrated 5.x project is refused until it migrates) `S9` names
  the practice. A new or changed guard is accepted on a demonstrated
  failure, not a passing test (`S10`).

**traceability** - Are both chains intact and current - code → scenario →
intent, and claim → scenario? A break is a no-pass. See `traceability.md` in this directory.
Where the project names an owning doc for each code area (Compass does, in
the "Owning docs" table of its `docs/README.md`), a change to an area changes its
owning doc in the same commit, or says why the doc still holds.

**regression** - Does the evidence show nothing that passed before now fails?
When the work has more than one unit, check each unit and then the *combined*
result at ship time - each unit green does not imply the combination is green.

**security** - Owed only where the settings add it. OWASP floor;
dependency-CVE scan where a project security guardrail needs it; evidence is
scan output, not "looks fine."

**clarity** - Owed only where the settings add it. Is the code and are its
tests legible to the next person - names, structure, no surprising control
flow? This is also where the writing-voice tells
named in `skills/compass-runtime/writing-voice.md` are judged - does the
artifact communicate a decision, or does it narrate the pipeline? Run
`scripts/voice-tells.py` over the issue's artifacts for the three tells a fixed string can find; a hit is a note and a conversation, never an automatic gate failure.
The calibration sample it is read
against is named in `${CLAUDE_PLUGIN_ROOT}/governance/strategies.md` (`S8`; an
unmigrated 5.x project is refused until it migrates).
Flag a short code with no plain words in front of it: the fix is to put the
meaning first and the code in brackets, never to delete the code.

**claims** - When the manifest lists claims: does every
public claim trace to a *passing* scenario? Evidence is the manifest's
`claims:`, each backed by a passing scenario.

**Read the claim, not just the link.** `claim-traces-to-scenario` checks that a
claim points at a scenario that exists. It cannot check that what the claim says
is true, and no machine can. This is the one gate in the set whose name promises
less than a reader hears: passing means "traceable", and a reader will take it
as "verified". Every other check here means roughly what it sounds like.

A worked instance: a claim reading *"7 em dashes in publication copy, repaired
to zero"* traced correctly to its scenario and was false - the file had never
contained one, so nothing was repaired. The check passed. The reviewer is what
catches that, by reading the claim against the scenario it points at and asking
whether the sentence is *so*, not whether the id resolves.

Two questions worth asking of every claim, because both failures showed up in
one release: does it say what it counted **and what it did not**, and would it
still be true if someone quoted it on its own six months from now?

## How the review is done

These rules hold on every dimension.

- **Patterns.** Where the design names patterns, check them against the code
  (the named-patterns strategy, `S16`). It is advice: never fail a gate on it.
- **Comments.** Open every comment with a plain-word label - **issue**,
  **suggestion**, **nitpick**, **question**, **praise** (the
  conventional-comments strategy, `S12`) - and label honestly.
- **A disputed quantity.** Where a review comment and the author disagree
  about a quantity - how many call sites, how much output, how often it
  fires - measure the number and report it before defending either position
  (the measure-before-arguing strategy, `S11`).
- **Settled decisions.** Before you recommend a rename or a reversal, read
  `governance/decisions/` if the project has one. A point that collides with
  an entry is "settled by <path>", not a defect.
- **Review rules.** If the project has `governance/review-rules.yml`, run
  `compass review-rule list --changed-files <paths>` and apply the rules it
  prints. Report a breach under the RR- id it breaks, and do not flag what a
  rule's `allowed` list permits.
