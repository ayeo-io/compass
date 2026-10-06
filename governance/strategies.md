# Strategies

Strategies are the many soft things. They are **directional** (they say how the
team tends to work, and what it prefers), **assessed** not checked (a reviewer
judges whether a strategy was followed - there is no pass/fail artifact), and
**accretive** (cheap to add, expected to evolve, fine to drop). A strategy
*biases* a decision. It does not block one. A guardrail always beats a strategy.

**No strategy fails `compass check`.** None is mechanically checkable; each is
assessed by the `reviewer` agent at `verify` under the review dimension tagged
beneath its heading, and a strategy not followed is a note and a conversation.

The evidence behind these rules - the incidents, measurements and worked
examples - is in `governance/strategies-rationale.md`. It is read when a rule
looks arbitrary, not per issue.

This file ships with a small set of **default method strategies** - the way
Compass works by default. Below them are **practice strategies**, about how
people write and verify. Below both is a **project strategies** section that
starts empty and grows as the team forms opinions. An empty project section is
a valid, complete state - see `README.md` on gradient-not-threshold.

---

## Default method strategies

These ship on. They are how Compass satisfies the guardrails by default. You
would need a deliberate, recorded reason to deviate. A spike can suspend the
first two, and a project can refine any of them.

### BDD: behaviour as Given/When/Then (`S1`)

**Acceptance criteria are Given/When/Then scenarios, and those same scenarios
are the acceptance check at Verify.**

- This is the shipped-on way to satisfy "acceptance defined before it is
  built" (`G2`).
- The scenario file is the shared artifact every role reads - see
  `docs/roles-guide.md`.
- **`G2` does not need a Gherkin scenario.** It needs acceptance stated
  and checkable.

### TDD: red, green, refactor (`S2`)

**Write the failing test first, watch it fail for the right reason, write the
minimal code to pass, then refactor.**

- This is the shipped-on way to satisfy "tested before it lands" (`G1`). The
  pre-tool hook enforces red-before-green by default.
- TDD serves two purposes:
  - Governance: red-before-green makes "tested before it lands" checkable -
    there is a test, and it was there first.
  - Design feedback: a hard-to-write test is the design speaking. A test
    that is painful to set up, or needs elaborate mocking, is a design
    problem. TDD is less about testing and more about good design.
- Suspended on a **spike**, so exploration is not throttled.
- **A spike cannot suspend `G1`.** Anything a spike graduates into production
  must be tested before it lands.

### Simplest thing that satisfies the guardrail (`S3`)

**Prefer the simplest change that clears the guardrails and the delivery approach's gates.**

- Not the cleverest, not the most general, not the most future-proof.
- Complexity is added in response to a demonstrated need, not in anticipation
  of one.

### Persistence over conversation (`S4`)

**Decisions, specs, approaches and rationale live in files, not only in a chat
transcript.**

- `.compass/work/<issue>/`, `governance/`, `docs/`.
- A later session, or a different agent, resumes from disk.
- If it is not written down, it did not happen.

### Intermittency is failure (`S5`)

**A test that fails then passes without an intervening source change is never
trusted as a pass.**

- A rerun-to-green is not a clean green. It is the loss of the most useful
  signal a test suite produces, hiding a real failure behind timing,
  environment state, or shared mutable setup.
- When a test reruns to green: fix the root cause, or quarantine it in
  `governance/quarantine.yml` with a tracking issue.
- The `no-trusted-rerun` check reads the `attempts` and `rerun_without_change`
  fields from evidence records and refuses to clear silently when a rerun is
  unaccounted for.

*Pairs with "evidence, not assertion" (`G4`).*

### Regression baseline: green before, re-run after, on shared surface (`S6`)

*Assessed under the `governance` dimension.*

**When a change touches shared or critical surface, run a designated regression
suite green before the change, keep the change additive or guarded, and re-run
it after.**

- Applies when `risk` is cross-cutting or critical.
- Record both runs as `test-run` evidence on `verify.regression`.
- This is "tested before it lands" (`G1`) applied to the non-regression of
  untouched behaviour: it catches a high-consequence break in code you did
  not mean to change.
- The designated suite is a project setting -
  `project.regression_baseline_suite` in `compass.yml` (or `.compass/config.yml` without one), falling back to
  `project.test_command`.
- The implement stage prompts for the baseline up front, not as an afterthought.
  `compass approach evaluate` surfaces it under `applicable_strategies` when
  the assessment matches (`RP-ADV-001`).
- It adds no guardrail and no new gate, and does not block shipping when
  absent. It reuses the existing `verify.regression` gate.

---

## Practice strategies

How people write and verify. These do not satisfy a guardrail directly; they
govern the quality of what the guardrails act on.

### Cold reader: write so a stranger can follow it without asking (`S7`)

*Assessed under the `clarity` dimension.*

**Assume the reader has zero prior context.**

Governs, each written to stand on its own: artifacts (intake, acceptance
criteria, delivery-approach record, design, devlog, verification report), code
comments, commit messages, pull-request bodies and review comments.

- **Context before detail.** Say what the thing is and why it matters before
  how it works.
- **No dangling references.** Never "Option 2", "Finding 1/3", "per the
  review", "as discussed", or an internal review number.
- **Say what a link is, in the same sentence** - "#412, which moved rate
  limiting into the gateway" - so it survives a dead link.
- **An identifier carries its meaning on first use** - in agent speech,
  printed output, and generated artifacts. Every mention after is the bare code.
  `compass check` prints `G5 A human signs off on the irreversible`.
- **The plain words come first; the code follows in brackets.**
- **Never drop the code to solve this.** The machine checks read them.
- **Correct a retired name in a comment you were touching anyway.** No sweep,
  no obligation to go looking.
- **Say it once, plainly, then stop.**
- **No agent co-author trailer.** A commit message or pull-request body never
  carries a `Co-Authored-By:` line naming an agent, and never a "Generated
  with" footer.
- `tests/test_plain_language.py` counts identifiers arriving unexplained against
  a recorded baseline. It never fails a build.

*Extends `S4` (persistence over conversation). Pairs with the traceability guardrail: a reference the reader
cannot resolve is not traceability. Restated at the point of use in
`commands/ship.md`.*

### Voice audition: read against a calibration sample (`S8`)

*Assessed under the `clarity` dimension.*

**Any change that writes prose a future session will read or imitate is read
against the calibration sample before it ships.**

- The sample is `skills/compass-runtime/writing-voice-worked-example.md`,
  paired with the "Never stash across a worktree hop" section of
  `skills/worktree-multiagent/SKILL.md`.
- The audition does not lapse. It applies to any future slice that writes
  prose.
- The test: read it aloud - would you say this sentence to a colleague at your
  desk?
- An "after" that shortens form-speak while dropping the facts the "before"
  carried fails the audition. Keeping the facts is the harder half.

*Why a strategy and not a guardrail:* whether a sentence sounds like a person
is a judgement. There is no check that fails on prose a reader would not say
aloud, so this is assessed at review rather than enforced.

*Cross-reference: specialises `S7` with a named calibration sample. The full
tells list is in `skills/compass-runtime/writing-voice.md`.*

### Fresh eyes on a sweep: verification by someone who did not make the change (`S9`)

*Assessed under the `governance` dimension.*

**Any sweep, rename or cleanup touching many files is checked by a fresh agent
that has not seen the change.**

- Given only the stated goal, that agent greps independently and reports the
  residuals it finds, each with file and line.
- It does not read the implementer's summary, and it does not trust it.
- **Check against the primary record for the claim**, not the nearest document
  that mentions it. The primary record is the artifact that would be wrong if
  the claim were false: a pull request's file list for what a change touched, a
  commit for what a commit says, the code for what the code does.

*Why a strategy and not a guardrail:* nothing in `compass check` can confirm
that the agent running a verification sweep is the one who did not write the
change. Agent identity is not a property a check can inspect, and a check that
tried would trust the same self-report this exists to distrust.

*Cross-reference: `S8` - both are about who judges. Pointer at the point of use
in `commands/verify.md`.*

### Mutation proof: a guard is accepted on a failure, not on a pass (`S10`)

*Assessed under the `correctness` dimension.*

**A check, guard or assertion is accepted when it has been shown to fail.**

- Break the thing it guards, watch it go red, restore, watch it go green,
  and record the result.
- **The proof table travels with the change** - what was broken, what failed,
  what passed on restore - recorded where the change is reviewed.
- **Treat a presence-shaped assertion as wrong until a mutation says
  otherwise.**
- **Before mutating, identify the exact text the assertion consumes** - not the
  text you believe it consumes.
- **Account for normalisation.** Normalise the matcher, then mutate what the
  normalised text contains.
- **When a presence check fails, establish whether the rule is absent or the
  matcher is brittle** before touching either.
- **Never loosen a matcher to cure a false negative.**
- **A matcher change makes every proof downstream of it out of date.** Re-prove.
- **Assert what must hold, not the words it is now written in.**
- **Clear any bytecode cache between steps**, and re-run after restoring to
  confirm green before recording the proof.
- **For a search, a result of zero is not believed until the search has been
  run against a case it must find.** Run it against one string you know is
  there and watch it come back. `git grep -n -i -E '\bseam\b'` returned
  nothing in this repository because `git grep -E` does not honour `\b`.

*Why a strategy and not a guardrail:* nothing mechanical can tell whether an
author actually broke the subject. A check demanding proof of a real mutation
would accept a pasted table as readily as a real one, trusting the self-report
the practice exists to replace.

*Cross-reference: `S9` answers who establishes a thing is true, this answers
how. Pointer at the point of use in `commands/verify.md`.*

### Measure before arguing: settle a disagreement with the number (`S11`)

*Assessed under the `correctness` dimension.*

**When a recommendation and an instruction disagree, measure the disputed
quantity and report the numbers before defending either position.**

- The disagreement is almost always about a quantity somebody has guessed - how
  many call sites, how much output, how often it fires.
- Report the numbers plainly and say what they mean for the decision, including
  when they undercut your own position.
- A measurement produced and then argued around lends the argument false
  weight.

*Why a strategy and not a guardrail:* no check can tell whether a quantity was
genuinely in dispute, and demanding a measurement before every disagreement
would tax the ordinary case where somebody simply knows the answer.

*Cross-reference: `S10` - both replace a confident assertion with an
observation. Pointer at the point of use in `CLAUDE.md` and
`commands/verify.md`.*

### Conventional comments: label a review comment before you write it (`S12`)

**A review comment opens with a plain-word label naming what kind it is.**

- **issue** - this is wrong and blocks the merge.
- **suggestion** - a change worth making, and the author may decline it.
- **nitpick** - taste; explicitly not blocking.
- **question** - the reviewer does not know yet and is asking.
- **praise** - worth saying out loud, and worth keeping in the record.

The label goes first, so a reader can tell a blocking comment from a
non-blocking one without reading to the end of the thread. It is not a
substitute for the comment: **issue** still has to say what breaks. The
`reviewer` agent applies it; the author answering the review assesses it.

*Why a strategy and not a guardrail:* nothing mechanical can judge whether a
comment was labelled correctly. A blocking defect filed as a nitpick passes any
check that looks for a word at the front, and it fails worse than no label.

*Cross-reference: `S7` - both are about the reader's cost. Pointer at the point
of use in `agents/reviewer.md` and `skills/receiving-code-review/SKILL.md`.*

### A title is a summary, not a headline (`S13`)

*Assessed under the `clarity` dimension.*

**A pull-request or commit title says what the change does, in the words
someone would search for.**

- "Add rate limiting to the search endpoint". "Fix the timeout error message to
  name the size limit".
- When it does several things, name the main one and leave the rest to the body.

Four shapes it refuses:

- a **slogan** - "Make the record trustworthy again"
- a **theme** - "Clarity week: part two"
- a **play on words** - "Guarding the guards"
- a **"the X that Y" construction** - "The check that could not fail"

- **The test:** if the title would work as a blog post title, it is wrong.
- **A neat formulation belongs in a paragraph, not in a heading.**
- **Scope: pull-request and commit titles. Deliberately not ADR titles.** A
  reader learns the decision from `an-identifier-is-a-key-not-jargon` without
  opening the file.
- **Commit titles follow the same rule**, not a second statement of it -
  two statements of one rule drift apart.
- **The body is a description, not a narrative.**
  `templates/pull-request-body.md` is the shape: what changed, what breaks, how
  to check it, where to look.
- **Trim the story, never the substance.** Length is not the fault.

### Correct every place at once, or you have made it worse (`S14`)

*Assessed under the `clarity` dimension.*

**When a figure, a decision or a claim is corrected, every place stating the
superseded version is corrected in the same change.**

- A correction that leaves the record contradicting itself is worse than the
  original error: the next reader has two answers and no way to tell which is
  current.
- Say what is superseded and why, not only what is now true.
- **A record of what happened keeps its number and gains a note** - a devlog
  entry, a dry-run result, a captured command output, an archived manifest.
  Rewriting one falsifies it.
- **A claim about what is true gets corrected** - a published document, a
  caption, a README line, a registered claim in a manifest. Annotating one
  leaves it false.
- **Re-read the summary last, before calling the artifact finished.**
- **Nothing checks this rule. It depends on a person noticing.**

*Pairs with the claim rules a release announcement follows: say what held,
not a count. Any count a tool produces is a number that moves.*

---

### Well-architected alignment: name the pillars a design touches (`S15`)

*Assessed under the `architecture` dimension, on the regular and full approaches.*

**A technical design names the well-architected pillars the change touches,
and says in a sentence or two what it does about each.**

- The pillars are reliability, security, cost, operational excellence,
  performance efficiency and, where it applies, sustainability.
  `governance/architecture-sources.yml` records where they come from: the
  AWS, Azure and Google Cloud well-architected frameworks, each with the
  date it was last checked.
- Name only the pillars the change touches. A pillar the change does not
  touch is left out, not written up as "no impact".
- Where two pillars pull against each other, such as cost against
  reliability, say which the design favours and why.
- **Advice, not a gate.** Pillar trade-offs are judgement, and judgement
  advises but never gates (ADR-003). The reviewer and the architect assess
  it; no check reads it.


---

### Named patterns: prefer a well-understood pattern, and say why (`S16`)

*Assessed under the `clarity` dimension, on the regular and full approaches.*

**A technical design names the well-understood design patterns it uses, and
where a real choice existed, the one it rejected and why.**

- A named pattern is one a reader can look up: a design pattern, a
  domain-driven design pattern or a named architectural style. Section 4 of
  the design template holds it, with the reason it earns its place.
- Prefer a named pattern to a structure of your own when one fits. A
  reader who knows the pattern understands the code faster.
- The reviewer flags both ways this goes wrong: a novel structure where a
  standard pattern fits, and a pattern applied where none is needed. The
  strategy asks for fit, not for a count of patterns.
- **Advice, not a gate.** Whether a pattern fits is judgement, and judgement
  advises but never gates (ADR-003).

---

## Project strategies

<!-- Add strategies specific to this project here. Add freely - strategies are
     meant to accrete. A strategy is anything directional and assessed: a
     preference, a default, a "how we tend to do X". It does NOT need to be
     checkable or blocking; if it is both of those, it is a guardrail - put it
     in guardrails.md instead.

     These are what the old constitution called "product / engineering / voice
     principles". Group them however helps. Examples of the shape:

       Product strategies
         - "When two valid features compete, we favour depth for existing
            users over breadth for prospective ones."
         - "We never dark-pattern, even when it would convert."

       Engineering strategies
         - "Modular monolith; a module does not reach into another's internals."
         - "A new third-party dependency needs a one-paragraph justification
            and a named alternative considered."

       Voice & positioning strategies
         - "Our voice is plain, exact, and warm. Never 'military-grade'."
         - "We describe what the product cannot yet do honestly, in the open."

     Curate this section - see README.md. A strategy nobody follows is noise;
     drop it. Leave the section empty rather than padding it. -->

### Voice and writing strategies

**House style, this repository.** Compass's own prose follows `S7`, plus two
conventions this repository holds itself to.

- **No em dashes.** Where an em dash would go, write a plain hyphen with spaces
  around it. En dashes stay: they do real work in ranges like `G1`–`G5` and
  `2–3 subtasks`.
- **No agent co-author trailer**, which is `S7`'s last rule stated as the thing
  this repository enforces on itself rather than merely prefers.
- **Conventional commits.** A commit subject opens with a type and an optional
  scope - `fix(hooks): ...`, `docs: ...` - so a log is skimmable and a release
  can be assembled from it. This is *format*; `S7` already governs commit
  **substance**.

The first two are checked by `tests/test_house_style.py`, and all three are
strategies rather than guardrails. What separates them is what the check
protects: the checks in `guardrails.yml` run against an adopting project's
`manifest.yml` and `evidence/` and can block a ship, while
`tests/test_house_style.py` is one of this repository's own source invariants.
It never runs in an adopting project and never touches a gate.

**If you are adopting Compass:** the rules above are a worked example of the
shape a project strategy takes, not something you inherit. `/compass:init`
copies this file wholesale, so **delete this block if your team writes
differently.** `S7` is the part that ships on, and it governs what a commit
message must *say*; how you format the subject line is yours.

---

## How strategies are used

- **`compass approach evaluate`** applies the routing strategies
  (`routing-policy.md`) to compute a default delivery approach.
- **The `reviewer` agent** assesses, at `verify`, whether the work followed the
  applicable strategies, and reports that as judgement, distinct from the
  evidence-backed guardrail checks.
- **`/compass:consult`** is where strategy-versus-strategy tensions get resolved.

A strategy that has hardened into a real must-never - checkable, blocking - has
outgrown this file. Promote it to `guardrails.md`. That should be rare.
