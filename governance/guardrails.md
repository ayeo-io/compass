# Guardrails

Guardrails are the few hard limits. They are **checkable** (cleared with
evidence, never a claim), **blocking** (a failed guardrail stops the work),
and **sticky** (slow to add, slower to remove). A guardrail always beats a
strategy.

This file ships with five **default guardrails** active. A project can *add*
guardrails below them. The five are locked: `compass policy lint` refuses a
`compass.yml` that removes or loosens one (`K-LOCK-REFUSED`). A project adds
its own checks and gates in its `compass.yml`, which extends the shipped
default (see `docs/configuration.md`). Only a project that copied this file
under 5.x can omit a shipped guardrail, and `compass check` reports the
omission. That project keeps running on its copy until `compass policy
migrate` converts it.

**This document explains; `guardrails.yml` enforces.** The companion
`governance/guardrails.yml` is the machine-readable authority for *how each
guardrail is checked* - it names the mechanical check behind every guardrail,
and `compass check` runs those checks against an issue's `manifest.yml` and
`evidence/`. Where this prose and that file could be read to differ on a
mechanical detail, `guardrails.yml` wins.

---

## The default guardrails

These five ship on. They are the floor under every delivery approach,
including the lightest.

### Tested before it lands (`G1`)

**No code reaches `main` unless it traces to a declared test and a green test
run is on record.**

- Compass checks that both exist and line up. It does not observe the declared
  test running - see `docs/safety-contract.md` for what a test-run record does
  and does not establish.
- Checked at Verify and again at ship time. `verification-report.md` carries
  the recorded run.

### Acceptance defined before it is built (`G2`)

**No code is written that no stated, checkable acceptance criterion
describes.**

- The criterion exists before the code does.
- The same criterion is the acceptance check at Verify.

### Traceability holds (`G3`)

**Every change keeps two chains intact, continuously - not reconstructed at
the end.**

- **code → acceptance criterion → intent** - every line traces to a criterion;
  every criterion traces to a stated intent.
- **public claim → backing criterion** - every public or marketing claim
  traces to a criterion that, when checked, backs it.
- A broken chain is a failed guardrail.

### Evidence, not assertion (`G4`)

**A guardrail is cleared with artifacts and command output, never with a
claim.**

- "The tests pass" is the recorded run, not the sentence. "It works" clears
  nothing.
- This guardrail is *about* the others: it defines what "cleared" means.

The check `dod-evidence-typed` applies it to the checklists of
`verification-report.md`. An unticked box needs an `(evidence: EV-<id>)` or
`(follow-up: FU-<id>)` tag that resolves. The check reads the Definition of
Done and the section of every other exit list (`<Stage> exit list`), not only
the Definition of Done.

### A human signs off on the irreversible (`G5`)

**A change that cannot be cleanly undone gets an explicit human checkpoint
before it lands.**

- Applies to an issue labelled `auth`, `payments`, `personal-data` or
  `migrations`: a change that can breach auth, move money, expose personal
  data or lose data that cannot be restored.
- No delivery approach removes this.

The routing policy (`routing-policy.md`) is what makes sure such changes are
*routed* to where the checkpoint happens; this guardrail is what makes the
checkpoint non-negotiable.

Critical risk alone does not bring the sign-off (governance decision
`2026-10-12-guardrail-5-triggers-on-the-irreversible-labels`). Critical-risk
code that carries none of the four labels can be reverted at merge, and CI,
review and the other guardrails gate it. `compass approach evaluate` names
the labels when risk is critical and none is set, so an unlabelled migration
is named at assess. A project that wants the sign-off on every critical-risk
change sets the trigger to the four labels or `risk: critical` in
`compass.yml`; `docs/upgrade-7-0-0.md` prints the block. The hard lock refuses
a looser trigger but allows this stricter one.

An issue keeps the trigger stored in its generation, so an issue assessed
before 7.0.0 still needs the sign-off at critical risk.

Its check, `human-approval-present`, reads only evidence of the type
`human-approval`. A person's approval of a document or of a set of decisions
(`compass evidence approve --artifact` and `--decisions`) is recorded as
`artifact-approval`, which this check never reads, so such an approval never
clears a sign-off.

Of the `human-approval` records, the check counts only one given for
guardrail `G5` (ADR-066). A record that holds a `check`, `waiver`,
`checkpoint`, `artifact` or `decisions` key, or a `guardrail` other than
exactly `G5`, was given for that subject and is set aside, so approving an
unrelated human check never clears the sign-off. A record with none of these
keys, the form earlier sign-offs use, still counts. In Claude Code a person
records the sign-off by typing `/compass:approve` for the request the agent
made with `compass evidence request`; the prompt hook records it, and the
model cannot raise that event (ADR-068). A person can also delegate the
sign-off, for a named agent, a stated time of at most 24 hours and a stated
scope, with `/compass:delegate ... for g5`; the agent then records it with
`compass evidence approve --guardrail` and the value `G5`, with
`--delegated --as <agent>` (ADR-069).
So the guardrail reads, in practice: a person signs off, or delegates the
sign-off for a named agent, time and scope. The person can withdraw a
delegated sign-off with `/compass:reject <record id>`, which writes an
`approval-withdrawal` record; it reverses nothing already done. At a terminal
a person records it with `compass evidence approve --guardrail` and
the value `G5`, giving `--approver`, `--role` and `--scope`. A landed issue that the earlier rule passed is
reported, never failed. The implementation is version 1.2.0: version 1.1.0
counted only a record given for `G5`, and 1.2.0 also skips a record that an
`approval-withdrawal` names while the issue is in flight. The fixture corpus
verdicts did not change, so it keeps major version 1, and no stored
generation is refused.

A person's answer to a checkpoint hand-off (`compass evidence approve
--checkpoint`) is recorded as `checkpoint-approval`. It has no `check` key, and
neither this check, a human check nor a waiver reads the type, so a
`checkpoint-approval` record does not clear `G5`. Answering the define or plan
hand-off is not the sign-off on an irreversible change.

---

## Project guardrails

<!-- Add guardrails specific to this project here. Add slowly. A guardrail
     must be HARD (a real must-never), CHECKABLE (you can produce evidence it
     held), and BLOCKING (failing it stops the work). If it is none of those,
     it is a strategy - put it in strategies.md instead.

     Good project guardrails are usually concrete, measurable floors:
       - "Test coverage does not drop below {{N}}%."  (checkable)
       - "No secret or credential is ever committed."  (checkable)
       - "Every migration has a tested rollback."  (checkable)
       - "p95 API latency stays under {{N}}ms; a >10% regression blocks shipping."
     Leave this section empty rather than padding it. Empty is a valid state. -->

_(none yet - the shipped default guardrails apply as-is)_

---

## How guardrails are enforced

- **`compass check`** runs the checks each guardrail names in `guardrails.yml`
  against the issue's `manifest.yml` and `evidence/`, and reports pass or fail
  with specifics. It also fails an issue whose `assessment:` holds a key
  `schemas/manifest.schema.json` does not allow, which the release's `issue
  lint` would refuse. A check with nothing to inspect, such as a BDD check
  where no runner is wired, is labelled NOTHING TO CHECK, never PASS, and is
  counted apart; it does not fail the run. It also checks the entry and exit
  lists of the stages the issue has reached, under the label
  `stage:<stage>:<entry|exit>` (`docs/entry-exit-evaluation.md`). The shipped
  Definition of Ready and Done checks run only where the capability
  `entry-exit-evaluation` is on; a check a project adds to a list always runs.
  With the capability `artifact-freshness` on, it also reports each tracked
  document as fresh or stale under the label `artifact-freshness`
  (`docs/artifact-freshness.md`). A project with none of these sees no change.
- **`artifacts-approved`** is a blocking check in no gate, run by `compass
  check` and by `compass ship-commit` before the commit. It declines until
  every gate has passed. Then it judges a copy of the issue with the ship exit
  applied, which is the state `ship-commit` would leave, and fails on a
  registered document that reads `draft` or `awaiting-approval`, or that is
  `omitted` with no reason. Each failure names the command that moves the
  document. It is unlocked, so an issue waiver can make it advisory. An issue
  stored on an earlier generation gains it at its next `compass approach
  evaluate --write`. ADR-050 holds the decision.
- **`nfr-rows-resolved` and `contracts-declared`** are two blocking checks that
  read one named section of an issue document. Each is unlocked, has
  `on_skipped: not-applicable`, and sits in no gate and no stage list, so no
  locked guardrail changes and an issue waiver can make either advisory.
  `compass check` runs them, and `artifacts-approved`, after the gate loop
  through one helper, `outside_gate.judged`. ADR-064 holds the decision.
  - `nfr-rows-resolved` reads the spec's Non-functional requirements table. A
    row for each of seven concerns (performance, capacity, compatibility,
    security, privacy, operability, accessibility) names scenario ids the
    manifest holds, or a reason the concern does not apply. At `thorough` depth
    each cited scenario states a number in its Then: a digit on the Then line,
    or on a Then, And or But line after it. A `{{...}}` cell counts as empty.
    The pass detail is "n of n concerns resolved".
  - `contracts-declared` reads the technical design's Data and interfaces
    section when a changed file is a trigger path. The section must hold a
    field table (Name, Type, Required, Meaning, Written by, Read by) or a
    contract table (Inputs, Outputs, Exit codes, Errors) with a data row, or an
    `erDiagram` fence. A table or fence that holds a `{{...}}` placeholder does
    not count.
  - **Trigger paths** are the check's `params` in the configuration:
    `trigger_paths` and `trigger_contents`. A pattern is an `fnmatch` glob on
    the project-relative path, where `*` also matches `/`. A contents pattern
    names a path glob and a text, and the file must hold the text. A project
    cannot extend the list with `add:`, because `params` is a map and the merge
    grammar applies `add:` only to a catalogue field. A project sets the whole
    `trigger_paths` list, the shipped patterns and its own, in its layer, with a
    project waiver, because `tighter` is `none` for the key.
  - **Four conditions make either check decline**, reporting `nothing to
    check`, before it reads a document. The first that holds decides the
    detail:
    1. The manifest has no `generation` key: "the issue predates the section
       checks: its manifest names no stored configuration".
    2. The issue is closed: "the issue is closed".
    3. The document the check reads is not registered with a path: "no
       acceptance-criteria is registered with a path" (or `technical-design`).
    4. The catalogue of the issue's generation does not list the section at the
       depth the document is registered at, and an entry with no `depth` lists
       nothing: "the catalogue of generation N does not list ... for ... at depth
       D".

    `contracts-declared` also declines, with its own detail, when no changed
    file matches a trigger pattern.
  - **A spike** runs these two checks and reads `nothing to check`, because it
    registers no spec or design. A spike does not run `artifacts-approved`.
    `ship-commit` runs `artifacts-approved` only.
  - An issue stored on an earlier generation gains both checks at its next
    `compass approach evaluate --write`.
- **`design-within-word-ceiling`** is a blocking check that fails a technical
  design whose word count is over its `word_ceiling` at the registered depth
  times `params.factor`, 1.5 in the shipped default: 6,000 words at thorough
  and 1,800 at lightweight. It is unlocked, has `on_skipped:
  not-applicable`, and sits in no gate and no stage list. `compass check` runs
  it after the section checks, through `outside_gate.judged`. ADR-067 holds
  the decision.
  - Words are the whitespace tokens of the visible text: rendered block
    interiors, marker lines and HTML comments are left out, and headings,
    prose, tables and code fences count. `compass issue lint` counts the same
    way for its word-limit note.
  - The design's own count decides. Registered low-level designs never lift
    the refusal; on the full approach the failure names each work unit with
    none.
  - It declines, reporting `nothing to check`, on the four conditions of the
    section checks, with the design as the document and "has no word_ceiling
    for technical-design at depth D" as the fourth, and on a fifth: plan exit
    is not yet due, "plan exit is not yet due: the issue is at S".
  - A spike runs it and reads `nothing to check`, because it registers no
    design. An issue stored on an earlier generation gains it at its next
    `compass approach evaluate --write`.
- **An advisory failure** is a check that failed where its effective severity
  is advisory (`severity: advisory`, or a `blocking_when` the assessment does
  not match). It is labelled ADVISORY, never PASS or FAIL, is counted apart
  and does not fail the run. `docs/generation-store.md` has the details.
- **The pre-tool hook** enforces red-before-green in service of `G1`. It is
  approach-aware and does not block on a spike.
- **The `verifier` and `reviewer` agents** at Verify, for the parts that remain
  judgement. `verification-report.md` records each with its evidence.
- **`compass approach evaluate`** at Assess applies the routing rules
  deterministically - see `routing-policy.md` and `routing-policy.yml`.

A guardrail with no way to produce evidence is not a guardrail yet - it is a
strategy that has not been made checkable. If you cannot give it a named check
in `guardrails.yml`, it belongs in `strategies.md`.

**The integrity rule - a declared check must be implemented.**

- `compass policy lint` rejects a guardrail referencing a check the CLI does
  not implement.
- `compass check` fails, rather than warns, if it meets one at run time.
- Adding a project guardrail with a new check means adding that check's
  implementation to the CLI (`CHECK_FNS`) in the same change.

Why it is enforced rather than warned about:
`governance/strategies-rationale.md`, under "The integrity rule".

**The check registry - each implementation carries a version.**

- `cli/compass_pkg/check_registry.py` holds one entry for each built-in check
  implementation. `CHECK_FNS` is derived from it. An entry holds a semantic
  version (all start at `1.0.0`), a parameter spec, a `tighter` value per
  parameter (`higher`, `lower` or `none`, default `none`; a check parameter
  cannot declare `equivalent`, because it has no declared choices, and the
  registry refuses the entry), whether the check
  runs project code (`command-passes` alone), and the path of its fixture
  corpus. It also answers "installed version" and "installed major" of an
  implementation.
- The corpus is `tests/fixtures/impls/<implementation>/<case>/`. Each
  case has an `expected.yml` holding a verdict (`pass`, `fail` or
  `nothing-to-check`) and a short description of the input, never the detail
  text. The input is built by `tests/check_corpus_runner.py`, which runs the
  implementation and computes the verdict. A test fails when a label differs
  from the computed verdict.
- `tests/fixtures/impls/versions.lock.yml` holds, per implementation,
  its `version` and a `verdict_digest` of its computed verdicts.
  `tests/test_impl_versions.py` fails when a digest changes and the major
  version does not, and when the installed major is higher than the locked one.
  A change that changes a verdict must bump the major and update the lock file
  in the same change. `docs/check-implementations.md` lists what each corpus
  exercises and is generated by `scripts/impl-coverage.py`.
- Within a major, compatibility is shown on the corpus cases only. A change of
  behaviour that no case exercises is not detected.
- `compass policy lint` refuses a check whose `impl:` names an implementation
  the registry does not hold. The runtime ignores `impl:` for now: a check runs
  the implementation that carries its name.
- `compass check` refuses a check whose implementation major differs from the one
  the issue's generation recorded, and `compass issue migrate --config` moves the
  generation on. `docs/generation-store.md` states both.

## Locks and conformance

`cli/compass_pkg/locks.py` protects the framework's guarantees when a layer
changes the shipped default. `architecture/decisions/ADR-039-waivers-locks-and-unlocks.md`
decides the rules. `compass policy lint` reports a refused change as
`K-LOCK-REFUSED`, and `compass policy show` prints the resolved configuration.

- **A lock** is `locked: true` or `locked: hard` on an entry. The shipped
  preset declares the framework locks, and a lower layer cannot remove one. An
  issue's `config:` cannot lock an entry, and a `locked:` there adds no lock.
- **The footprint** of a locked entry is what the lock protects:
  - a check: its compared fields, and its place in each stage list and gate;
  - a gate: its check set, its accepted evidence types and its stage;
  - a stage: its existence, its order, and its entry and exit lists;
  - a rule set: its kind, its hit policy, each rule in it and each rule's
    effects;
  - an approach: its existence and its `ships` value.
- **Enforcement** uses the classifier's comparison, projected to the
  footprint. A change that is equal or tighter is allowed. A change that
  loosens the entry, or cannot be compared, is refused with the entry, the
  lock level, the field, both values and the first assessment where it shows.
  Removing the stage, changing `when`, detaching a gate, setting `on_skipped:
  pass`, widening `accepts` or `reviewers`, dropping `approvers`, and changing
  `params` or a human or judged `statement` are each refused.
- **A change of vocabulary is a change to the lock.** If a layer drops or
  renames a dimension value, or closes the label list, so that an assessment a
  locked gate or check applied to can no longer be made, the lock refuses it.
  The evaluator is run on the parent at each such assessment to find the locked
  entries that were in force there.
- **A rule with an effect that no obligation fact carries** (for example a
  minimum approach) protects its `when` too, not only its effect, so a change
  that narrows the rule is refused. A rule that adds a gate, asks for an
  artifact, blocks a stage or asks for a skill is protected through that fact.
- **A waiver never excuses a lock refusal.**
- **An issue's `config:` is enforced at the issue's own assessment.** An issue
  has one assessment in force, so the comparison runs at that single point and
  not over the grid. A project layer is still enforced over the grid, because
  it applies to every assessment the project will see
  (`architecture/decisions/ADR-037-configuration-changes-are-classified-by-effect.md`,
  the amendment of 2026-10-08). Nothing is accepted or refused by the name or
  weight of a route: the field table decides at that point. Naming `full`
  over `regular` is incomparable on the subtask ceiling, and a spike issue
  that picks `full` loses `spike.conclude` and is refused by a lock. The lint
  also runs on an unchanged configuration when the issue's stored assessment
  changed, so a route accepted at one assessment cannot carry onto a spike by
  a reassess that changes nothing else.
- **More than eight named labels is still refused, but only the labels a locked
  entry can read are counted.** The scan keeps a label only where it can reach
  a fact a lock protects, and drops the labels that only these read:
  - advisory, bias and ceiling rules, which change what the evaluator reports
    and which no footprint carries;
  - a check that no locked stage or gate lists and that is not locked itself;
  - a gate that is not locked, adds nothing a locked rule set adds, and holds no
    locked check.

  Labels in floors, shapes, caps, artifact rules and immovable gates always count,
  because they decide the approach and so the gates in force. Once more than
  eight labels a locked entry can read are named, every change to the layer is
  refused, and the refusal reaches the layers below it. An issue's `config:` is
  enforced at one assessment and names no labels, so this refusal does not reach it. The refusal names the labels counted. To lift it, name no more than
  eight of them. For a `true` lock an owner-approved unlock also lifts it. For a
  hard lock nothing else does. An entry or a path the scan does not recognise
  keeps its labels, so a doubtful case makes the count larger and never smaller.
  `enforce(..., scan="full")` counts every label in the layer. It is the
  reference that `tests/test_locks_footprint_scan.py` compares the footprint scan
  with: both give the same refusals on every lock test case and every route
  tried against the shipped policy.
- **A configuration the evaluator rejects** is refused as well, because no
  lock can be shown to hold. An unlock cannot help. The configuration needs
  fixing, and lint reports the fault.
- **`locked: hard`** applies to the guardrail A human signs off on the
  irreversible (`G5`) and its check `human-approval-present`. No unlock
  lifts `G5` and its check, and no waiver excuses them.
- **An unlock** is `unlock: true` on an entry in `compass.yml`, with a waiver
  that gives a reason and is approved by the project's `owner`. An issue, a
  parent or a preset that carries `unlock:` is refused. An unlocked entry is no
  longer enforced for the project or the issue below it.
- **Conformance.** A project that unlocks a framework entry is non-conformant.
  `compass check`, `compass issue receipt` and `compass approach show` print
  `Conformance: non-conformant - this project unlocks framework entries: ...` on
  every run. An unlock of a hard-locked entry, or of an entry the shipped
  default does not lock, is refused, and the commands print `Unlock refused for
  <entry>: <reason>` instead. A project with no `compass.yml`, one that is not
  Compass's (no `schema:`), or one that unlocks nothing sees no new line. A
  `compass.yml` that cannot be read prints `Conformance: not checked`.

The report reads `compass.yml` and the shipped default's lock summary. The
waiver's date and covered revision are checked by the waiver module when it
lands, and the line for what the hook can enforce comes with the receipt
provenance.
