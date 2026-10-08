# Guardrails

Guardrails are the few hard limits. They are **checkable** (cleared with
evidence, never a claim), **blocking** (a failed guardrail stops the work),
and **sticky** (slow to add, slower to remove). A guardrail always beats a
strategy.

This file ships with five **default guardrails** active. A project can *add*
guardrails below them; it can also remove one, and `compass check` reports
the omission. `/compass:init` copies this file into the project so the team
can extend it.

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

### A human signs off on the irreversible (`G5`)

**A change that cannot be cleanly undone gets an explicit human checkpoint
before it lands.**

- Applies to anything that can lose data, move money, or breach auth or
  privacy.
- No delivery approach removes this.

The routing policy (`routing-policy.md`) is what makes sure such changes are
*routed* to where the checkpoint happens; this guardrail is what makes the
checkpoint non-negotiable.

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
  counted apart; it does not fail the run.
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
  parameter (`higher`, `lower` or `none`, default `none`), whether the check
  runs project code (`command-passes` alone), and the path of its fixture
  corpus. It also answers "installed version" and "installed major" of an
  implementation.
- The corpus is `tests/fixtures/check-corpus/<implementation>/<case>/`. Each
  case has an `expected.yml` holding a verdict (`pass`, `fail` or
  `nothing-to-check`) and a short description of the input, never the detail
  text. The input is built by `tests/check_corpus_runner.py`, which runs the
  implementation and computes the verdict. A test fails when a label differs
  from the computed verdict.
- `tests/fixtures/check-corpus/versions.lock.yml` holds, per implementation,
  its version and a digest of its computed verdicts. The build fails when a
  digest changes and the major version does not, and when the installed major
  differs from the locked one. A change that changes a verdict must bump the
  major and update the lock file in the same change.
- Within a major, compatibility is shown on the corpus cases only. A change of
  behaviour that no case exercises is not detected.
- `compass policy lint` refuses a check whose `impl:` names an implementation
  the registry does not hold. The runtime ignores `impl:` for now: a check runs
  the implementation that carries its name. The refusal of a major-version
  mismatch at run time comes with stored configuration generations.

## Locks and conformance

`cli/compass_pkg/locks.py` protects the framework's guarantees when a layer
changes the shipped default. `architecture/decisions/ADR-039-waivers-locks-and-unlocks.md`
decides the rules. The module has no command yet, so lint and `policy
effective` will print what it returns.

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

  Labels in floors, shapes, caps, role rules and immovable gates always count,
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
  `compass check`, `compass issue receipt` and `compass approach summary` print
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
