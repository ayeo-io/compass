# Guardrails

Guardrails are the few hard limits. They are **checkable** (cleared with
evidence, never a claim), **blocking** (a failed guardrail stops the work),
and **sticky** (slow to add, slower to remove). A guardrail always beats a
strategy.

This file ships with five **default guardrails** active. Compass runs one
fixed check set (ADR-094), so no project can remove or loosen one. A project
can only add to the set, with the tighten-only settings of its `compass.yml`
(see `docs/configuration.md`). Only a project that copied this file under 5.x
can omit a shipped guardrail, and `compass check` reports the omission. That
project keeps running on its copy until #359.

**This document explains; the check set enforces.** The check set,
`governance/check-set.yml`, is the machine-readable authority for *how each
guardrail is checked* - it names the mechanical check behind every guardrail,
and `compass check` runs those checks against an issue's `manifest.yml` and
`evidence/`. Where this prose and that file could be read to differ on a
mechanical detail, the check set wins. `governance/guardrails.yml` is the
frozen 8.x view, read only for a project that copied the governance files
(see "The fixed check set" below).

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
- Checked at Verify and again at ship time. The manifest's evidence registry
  carries the recorded run.
- `suite-passed` also needs a failure observed first: a red or an
  acceptance record on an issue that declares scenarios. On an issue
  created on or after 2026-11-03, each scenario that is not narrative needs
  a red bound to it, of either loop, dated no later than its first green,
  unless an acceptance declared before that green closes it. A scenario's
  first green is the earliest green bound to it or unbound, and a green run
  again keeps the time of its first run in `first_timestamp`.
  The check names each scenario with no red, and each whose red is after
  its first green. An older issue keeps the earlier rule, and the pass
  detail gives a notice that names what it lacks under the new one
  (ADR-088). `cli/compass_pkg/red_first.py` holds the rules.

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

The check `dod-evidence-typed` applies it to the Definition of Done. On an
issue created from 2026-11-04 each item needs a record in the manifest: evidence
with `--meets`, a person's approval or a follow-up that defers it. On a path
issue that follow-up must link to a GitHub issue (`--github`), and the
check that every follow-up is resolved has nothing to check (ADR-093). On an older
issue it reads the checklists of `verification-report.md`, where an unticked
box needs an `(evidence: EV-<id>)` or `(follow-up: FU-<id>)` tag that resolves,
in the Definition of Done and the section of every other exit list (`<Stage>
exit list`). `compass ship-commit` runs this one check before it lands, and
refuses while it fails (`definition-of-done-open`). A waiver that makes it
advisory prints one line, and the landing goes on. A path issue (ADR-092)
owes the Definition of Done only when its `evidence_required` lists
`definition-of-done`, and it is judged once every gate has passed; the items
are the build exit list (`dod_due`).

The check `evidence-matches-tree` judges a landed issue by the newest test
record's `file_sha256` and `file_modes`: the SHA-256 and the mode of each
changed file and each declared test as the record saw it, compared with the
same files in `land_commit` as a checkout writes them. A
record written before that field is judged by its `changes_id`, as before.
The CLI writes the same digests, and the digest of each record file, to
`evidence/SHA256SUMS`, so a reader can check them with `sha256sum -c` and no
Compass installed (ADR-089).

### A human signs off on the irreversible (`G5`)

**A change that cannot be cleanly undone gets an explicit human checkpoint
before it lands.**

- Applies to an issue labelled `auth`, `payments`, `personal-data` or
  `migrations`: a change that can breach auth, move money, expose personal
  data or lose data that cannot be restored.
- No delivery approach removes this.

The routing policy (`routing-policy.md`) is what makes sure such changes are
*routed* to where the checkpoint happens; this guardrail is what makes the <!-- vocabulary-scan: allow - route is a verb here -->
checkpoint non-negotiable.

Critical risk alone does not bring the sign-off (governance decision
`2026-10-12-guardrail-5-triggers-on-the-irreversible-labels`). Critical-risk
code that carries none of the four labels can be reverted at merge, and CI,
review and the other guardrails gate it. `compass approach evaluate` names
the labels when risk is critical and none is set, so an unlabelled migration
is named at assess. In 8.x a project that wanted the sign-off on every
critical-risk change set the trigger in `compass.yml`
(`docs/upgrade-7-0-0.md` prints the block). Since 9.0.0 a project adds labels
to the trigger with the tighten-only setting `signoff_labels`, and no setting
can loosen it (ADR-094).

An issue keeps the trigger stored in its generation, so an issue assessed
before 7.0.0 still needs the sign-off at critical risk.

Its check, `human-approval-present`, reads only evidence of the type
`human-approval`. A person's approval of a set of decisions (`compass evidence
approve --decisions`) is recorded as `artifact-approval`, which this check never
reads, so such an approval never clears a sign-off. A document approval an
older release recorded has the same type.

Of the `human-approval` records, the check counts only one given for
guardrail `G5` (ADR-066). A record that holds a `check`, `waiver`,
`checkpoint`, `artifact` or `decisions` key, or a `guardrail` other than
exactly `G5`, was given for that subject and is set aside, so approving an
unrelated human check never clears the sign-off. A record with none of these
keys, the form earlier sign-offs use, still counts. In Claude Code a person
records the sign-off by typing `/compass:approve` for the request the agent
made with `compass evidence request`; the prompt hook records it, and the
model cannot raise that event (ADR-068). A person can also delegate the
sign-off with `/compass:delegate --for g5`, after typing back a code that the
hook shows. The delegation can have no end time and cover every issue, and the
person can narrow it with `--agent`, `--until`, `--on` and `--max`. The agent
then records the sign-off with `compass evidence approve --guardrail` and the
value `G5`, with `--issue <slug> --delegated --as <agent>` (ADR-069, amended by
ADR-077).
So the guardrail reads, in practice: a person signs off, or types one
confirmation that lets a session's agents, or one named agent, sign off
irreversible work until the person revokes it. The person can withdraw a
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

- **`compass check`** runs the checks each guardrail names in the issue's
  policy (the check set, or the issue's stored generation) against the issue's `manifest.yml` and `evidence/`, and reports pass or fail
  with specifics. It also fails an issue whose `assessment:` holds a key
  `schemas/manifest.schema.json` does not allow, which the release's `issue
  lint` would refuse. A check with nothing to inspect, such as a BDD check
  where no runner is wired, is labelled NOTHING TO CHECK, never PASS, and is
  counted apart; it does not fail the run. It also checks the entry and exit
  lists of the stages the issue has reached, under the label
  `stage:<stage>:<entry|exit>` (`docs/entry-exit-evaluation.md`). The shipped
  Definition of Done checks, the `build` exit list, run only where the
  capability `entry-exit-evaluation` is on; a check a project adds to a list
  always runs. The shipped default holds no Definition of Ready since 9.0.0
  (ADR-092); a stored generation that lists one still judges it.
  A project with neither sees no change.
- **`land-commit-on-default-branch`** is an advisory row `compass check` adds
  for a landed issue with a `land_commit`, in a clone that records
  `origin/HEAD`. It reports a `land_commit` that origin's default branch does
  not reach, which a squash merge causes, and names `compass issue link set
  --pr`, which moves `land_commit` to the merge commit. It is in no gate and no
  configuration, and it never fails the run (`docs/github-links.md`).
- **`nfr-rows-resolved`** is a blocking check that reads the spec's
  Non-functional requirements table. It has `on_skipped: not-applicable`
  and sits in no gate and no stage list, so no guardrail changes and an
  approved waiver can excuse it on one issue. `compass check`
  runs it after the gate loop through `outside_gate.judged`. ADR-064 holds the
  decision.
  - A row for each of seven concerns (performance, capacity, compatibility,
    security, privacy, operability, accessibility) names scenario ids the
    manifest holds, or a reason the concern does not apply. At `thorough` depth
    each cited scenario states a number in its Then: a digit on the Then line,
    or on a Then, And or But line after it. A `{{...}}` cell counts as empty.
    The pass detail is "n of n concerns resolved".
  - **Four conditions make it decline**, reporting `nothing to check`, before
    it reads the spec. The first that holds decides the detail:
    1. The manifest has no `generation` key.
    2. The issue is closed.
    3. No spec is registered with a path, none is at
       `docs/compass/<created>-<slug>/acceptance-criteria.md`, and the issue
       was created before 2026-11-04. A spec at that fixed path is read
       whatever the date, at the depth of the define stage. An issue created
       on or after 2026-11-04 declines while that file is not written.
    4. For a registered spec, the catalogue of the issue's generation does not
       list the section at the depth the spec is registered at. A generation
       that declares no entry for the spec, as the live default does since
       9.0.0 (ADR-091), is read through the last shipped catalogue,
       `default@7`, which lists it at both depths.
  - A spike runs it and reads `nothing to check`, because it writes no spec.
- **Removed in 9.0.0** (ADR-091): `artifacts-approved`, `contracts-declared`,
  `design-within-word-ceiling` and `borrowed-documents-answered` read documents
  9.0.0 no longer keeps. A stored generation that still declares one reports it
  as nothing to check.
- **`acceptance-applicability-agrees`** is the advisory check of the four-layer
  acceptance strategy (`S17`, in `strategies.md`). It declares
  `severity: advisory` and `on_skipped: not-applicable`, and sits in no gate
  and not in the spike's checks. `compass check` runs it after the
  design-size check, through `outside_gate.judged`, and labels its row "four-layer
  acceptance strategy (`S17`)". The rules it applies are in
  `cli/compass_pkg/acceptance_strategy.py`.
  - It fails, as advice, when the project setting `acceptance_strategy`
    changed since the issue was assessed, or when the applicability stored at
    assess disagrees with the records: a red record puts an issue in scope,
    and an acceptance of kind `validation` or `refactor` with no red takes it
    out. The finding names the re-assess command.
  - It declines, reporting `nothing to check`, when the stored block and the
    setting both say off, and when the stored routing is `suspended`.
  - An issue with no stored block was assessed before the strategy shipped.
    `compass check` adds no row for it and prints, in `--verbose` and
    `--json`, the notice "four-layer acceptance strategy (`S17`): does not
    apply - this issue was assessed before the strategy shipped", so its rows
    and exit code are those of the release it was assessed under.
  - An issue in a project whose `compass.yml` extends the shipped default at
    major 6 or 7 also holds no block; its notice names the `extends:` value.
  - `compass check` refuses, with exit 2, a project whose
    `acceptance_strategy` setting cannot be read, before any check runs. In
    a project pinned at major 6 or 7 the strategy never reads the setting,
    but `compass.yml` must still pass its schema check: `compass policy
    lint`, `compass approach evaluate --write` and `compass check` on an
    issue not yet assessed refuse a bad value. `compass check` on an assessed
    issue reads the configuration stored with the issue and does not refuse
    it.
- **`outer-loop-recorded`** is the outer-loop check of the four-layer
  acceptance strategy (`S17`, ADR-080). It declares `severity: blocking` and
  `on_skipped: not-applicable`, and sits in no gate and not in the spike's
  checks. `compass check` runs it after
  `acceptance-applicability-agrees` and labels its row the same way. The
  rules it applies are in `cli/compass_pkg/outer_loop.py`.
  - It reads the `loop` field that `compass tdd-red --loop outer|inner` and
    `compass tdd-green --loop outer|inner` write. The default is outer on a
    quick fix the strategy applies to, whose one declared test is its
    acceptance test, and on a path issue (ADR-092) whose routing is
    `existing-dsl`, and inner otherwise. A record with no field reads as
    inner. The red that ends stage 1 at refine, or at specify on a path
    issue, counts as an outer-loop red; `acceptance_strategy.stage_one`
    decides which red that is (ADR-081). An
    outer-loop record is written to `red-<id>.outer.json` or
    `green-<id>.outer.json`, so an inner-loop record bound to the same
    scenario does not replace it (ADR-082).
  - It asks `acceptance_strategy.in_scope` whether the strategy applies, and
    declines with "not required: the strategy does not apply" when it does not.
  - On an in-scope issue it fails when no failed red record says loop outer,
    when no registered green says loop outer, when no outer-loop green
    was recorded on the tree as it is now, or when a registered outer-loop
    green names no `candidate` or no `client`, or a client other than api,
    web and cli (ADR-085). One finding names the issue and
    each fault. The tree is the one `evidence-matches-tree` reads; when git
    cannot name it, or no outer-loop green names its tree, the tree is not
    compared and the detail says so.
  - `compass tdd-green` and `compass quick-fix finish` refuse an in-scope
    outer-loop green with no candidate or no client before it runs, and
    `compass evidence add` refuses to register one, so the check finds only
    a record registered another way. `cli/compass_pkg/candidate_client.py`
    holds the rules.
  - It judges the issue, not each scenario. `suite-passed` does not change.
- **`acceptance-support-present`** is the support-code check of the
  four-layer acceptance strategy (`S17`). It declares `severity: advisory`
  and `on_skipped: not-applicable`, and sits in no gate and not in the
  spike's checks. `compass check` runs it after
  `outer-loop-recorded` and labels its row the same way. The rules it applies
  are in `cli/compass_pkg/support_code.py`.
  - It asks `acceptance_strategy.in_scope` whether the strategy applies, and
    declines with "not required: the strategy does not apply" when it does not.
  - It declines with "not yet judged" until a green is on record: the claim
    limit limits what a passing run lets the issue claim.
  - On an in-scope issue it tests that each piece of support code named under
    `project.acceptance_support` (`alias_helper`, `driver_factory`,
    `dsl_root`, `layering_test`) exists inside the project root. It opens no
    file.
  - A missing piece fails it as advice. The finding names each missing piece
    and states the claim limit. The claim limit is: while a piece is missing,
    the issue can claim that its scenarios pass, and not that its acceptance
    tests are isolated from each other (alias helper), run through a driver
    chosen at start-up (driver factory), keep driver detail out of the
    specifications (DSL root) or keep the layer rules (layering test). The
    first issue the strategy applies to builds the missing pieces as its own
    work.
  - The advice never makes `compass check` exit 1.
- **`outer-loop-attempts-recorded`** is the `attempts` check of the four-layer
  acceptance strategy (`S17`, ADR-084). It declares `severity: blocking` and
  `on_skipped: not-applicable`, and sits in no gate and not in the spike's
  checks. `compass check` runs it after
  `outer-loop-recorded` and labels its row the same way. The rules it applies
  are in `cli/compass_pkg/outer_loop.py`.
  - On an in-scope issue it fails each registered outer-loop green with no
    `attempts`, or with a value that is not a whole number of 1 or more. The
    finding names the record and the value.
  - It declines with "not required: the strategy does not apply" when
    `acceptance_strategy.in_scope` says so, and when no outer-loop green is
    registered, which `outer-loop-recorded` reports.
  - An inner-loop green needs no `attempts`. `no-trusted-rerun` does not
    change: it still passes a record with no `attempts`.
- **`isolation-proven`** is the isolation check of the four-layer acceptance
  strategy (`S17`, ADR-086). It declares `severity: blocking` and
  `on_skipped: not-applicable`, and sits in no gate and not in the spike's
  checks. `compass check` runs it after
  `outer-loop-attempts-recorded` and labels its row the same way. The rules
  it applies are in `cli/compass_pkg/isolation.py`.
  - It reads the `isolation-proof` record that `compass isolation record`
    writes: one parallel run of the suite, then each scenario's declared
    tests run twice. `compass evidence add` refuses the type, so a written
    note cannot stand in for it. A record whose `record_id` is not its
    registry entry's, or whose `content_digest` no longer matches what it
    holds, was not written by the command and fails, as does one that names
    no tree where git can name one.
  - On an in-scope issue on the routing `on` or `existing-dsl-isolation` (a
    live defect) it fails when no record is registered, when the record cannot be
    read or lacks a result, when the parallel run failed, when a scenario did
    not pass both runs, when a declared test is in no repeat entry, when the
    record was made on another tree, and when its candidate is not the
    newest outer-loop green's. The finding names the record and each fault.
  - It declines with "not required" when the strategy does not apply and on
    the routing `existing-dsl` (a small, contained change). The row lists a record the
    issue holds, with its result, and the result judges nothing.
- **`layering-test-passed`** is the layering check of the four-layer
  acceptance strategy (`S17`, ADR-086). It declares `severity: blocking` and
  `on_skipped: not-applicable`, and sits in no gate and not in the spike's
  checks. `compass check` runs it after `isolation-proven`
  and labels its row the same way. The rules it applies are in
  `cli/compass_pkg/layering.py`.
  - It reads the `layering` record that `compass layering record` writes from
    one run of the project's own layering test. Compass never reads the test.
    `compass evidence add` refuses the type, and a record its command did not
    write fails as it does for `isolation-proven`. A skipped test does not
    count as a test that ran.
  - On an in-scope issue on the routing `on` it fails when no record is
    registered, when the record cannot be read, when the test failed, when the
    record shows that 0 tests ran, and when it was made on another tree. A
    record with no test count (`tests_ran: null`) is not judged on it, so a
    layering test that is a shell script passes when it exits 0.
  - It declines with "not required" when the strategy does not apply and on
    the routings `existing-dsl` and `existing-dsl-isolation` (a small, contained
    change and a live defect), and lists a record the issue holds, with its result.
  - An approved waiver can excuse it or `isolation-proven` on one issue, as
    for any check (see "A waived check" below). On an issue assessed before
    9.0.0, `compass check` also names each 8.x waiver of one of the
    strategy's checks that the issue's `config:` holds, with its reason and
    whether the issue's generation approved it.
- **An advisory failure** is a check that failed where its effective severity
  is advisory (`severity: advisory`, or a `blocking_when` the assessment does
  not match). It is labelled ADVISORY, never PASS or FAIL, is counted apart
  and does not fail the run. `docs/generation-store.md` has the details.
- **A waived check** is a check that failed on an issue whose approved waiver
  excuses it (`compass waiver add`, approved with a `human-approval` record
  that names the waiver; ADR-094). It is labelled WAIVED, with the waiver, its
  reason, the approver and the record id, is counted apart and does not fail
  the run. A waiver nobody approved changes nothing and is named in a notice.
  `human-approval-present` and the rows of guardrail `G5` are never waived.
  `docs/waivers.md` has the details.
- **The pre-tool hook** enforces red-before-green in service of `G1`. It is
  approach-aware and does not block on a spike.
- **The review at the `verify` stage**, run in the issue's own session (ADR-090), for the
  parts that remain judgement. Each is recorded with its evidence (`compass evidence add`).
- **`compass approach evaluate`** at Assess applies the routing rules
  deterministically - see `routing-policy.md` and the `rules:` of the check
  set.

A guardrail with no way to produce evidence is not a guardrail yet - it is a
strategy that has not been made checkable. If you cannot give it a named check
in the check set, it belongs in `strategies.md`.

**The integrity rule - a declared check must be implemented.**

- `compass policy lint` rejects a check, in the check set with the
  project's tighten-only settings applied, that names an implementation the
  CLI does not hold.
- `compass check` fails, rather than warns, if it meets one at run time.
- A project adds a check of its own only as a `project_checks` setting, which
  runs the implementation `command-passes`. A new kind of check means adding
  its implementation to the CLI (`CHECK_FNS`) and the check to the check set
  in the same change.

Why it is enforced rather than warned about:
`governance/strategies-rationale.md`, under "The integrity rule".

**The check registry - each implementation carries a version.**

- `cli/compass_pkg/check_registry.py` holds one entry for each built-in check
  implementation. `CHECK_FNS` is derived from it. An entry holds a semantic
  version (all start at `1.0.0`), a parameter spec, a `tighter` value per
  parameter (`higher`, `lower`, `superset` or `none`, default `none`; a check
  parameter cannot declare `equivalent`, because it has no declared choices,
  and the registry refuses the entry; `superset` applies to a list parameter
  only, and the registry refuses it on any other), whether the check
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

## The fixed check set

`governance/check-set.yml` holds every check, gate and evidence type Compass
runs, as one file with `id: compass-checks` and a `version` (ADR-094). One
file has one `sha256sum`, so a change can name its rules by one id, one version
and one digest, such as `compass-checks@9.0.0`.

- `cli/compass_pkg/check_set.py` reads the file. `load` checks its shape,
  `sha256` gives the digest as `sha256sum` prints it, and `resolved` returns
  the set in the shape `generations/<n>/resolved.yml` holds. The file is
  parsed once while it is unchanged, because every resolution reads it and
  `compass flow` resolves every issue on the board.
- The set holds no `locked:` field, because no layer sits above it.
  `never_waived` names the two entries no waiver can excuse: the check
  `human-approval-present` and the guardrail `G5`.
- `optional` holds entries that run only when a project turns them on. The one
  entry is the advisory agent review of `docs/judged-checks.md`, for the
  setting `agent_review`.
- `version` is the release that last changed the file. A change that makes a
  check owe less, or removes one, raises the major; a change that adds or
  tightens raises the minor. `tests/fixtures/check-set-digests.yml` pins the
  digest of each version, and `tests/test_check_set.py` fails when the bytes
  change and the pin does not. The change that edits the file pins the new
  digest.

The resolver reads the set (`effective.resolve_live`), with the tighten-only
settings of `compass.yml` applied, for every project but one with its own copy
of the governance files and no `compass.yml`. That is every new generation and
every issue with no `generation:` key, the framework's own repository included.
`compass check` prints `Policy: compass-checks@9.0.0 (sha256 <hex>)` on every
run, and each generation commit writes the manifest's `policy:` block
(`docs/generation-store.md`). `tests/test_check_set_content.py` checks the
content of the set: the catalogue names, the stage-mode ranks, the references
and the checks and evidence types of the frozen `governance/guardrails.yml`.

`acceptance_strategy.pinned_below` still reads `extends: compass:default@6` or
`@7`, which is otherwise a removed setting: such a pin keeps `S17` off until
#359 writes `acceptance_strategy: off` in its place (ADR-094 open question 7).

## No locks

9.0.0 has no locks and no unlocks (ADR-094). Nothing sits above the check
set, so nothing can change an entry a lock would protect: a setting can only
add to the set, and a removed catalogue key in `compass.yml` is not read.

- **What no waiver excuses.** `never_waived` in `governance/check-set.yml`
  names the guardrail A human signs off on the irreversible (`G5`) and its
  check `human-approval-present`, the two `locked: hard` entries of 8.x.
  `compass waiver add` refuses a waiver of either (`docs/waivers.md`).
- **Conformance.** In 8.x a project that unlocked a framework entry was
  non-conformant, and `compass check` and `compass approach show` said so on
  every run. Since 9.0.0 the resolver reads the check set, where no lock
  exists, so neither command prints a conformance line.
- **A stored generation** written by 8.x keeps the `locked:` fields and the
  `conformance` block it stored. They are read as data and enforce nothing.
